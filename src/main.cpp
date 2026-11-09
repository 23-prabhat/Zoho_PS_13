#include <openvino/genai/llm_pipeline.hpp>
#include <openvino/genai/continuous_batching_pipeline.hpp>
#include <openvino/openvino.hpp>

#include "local_llm/chat_session.hpp"
#include "local_llm/context_policy.hpp"
#include "local_llm/device_probe.hpp"
#include "local_llm/metrics.hpp"
#include "local_llm/model_registry.hpp"

#include <chrono>
#include <algorithm>
#include <charconv>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifdef __linux__
#include <unistd.h>
#endif

namespace {

namespace fs = std::filesystem;
constexpr const char* VERSION = "0.2.0";

struct Options {
    std::string command = "chat";
    fs::path model = "models/qwen2.5-1.5b/int4";
    std::string device = "CPU";
    std::string kv_cache_precision = "auto";
    std::string prompt;
    fs::path prompt_file;
    fs::path prompts_file = "benchmarks/prompts.jsonl";
    fs::path output = "results/benchmark.csv";
    fs::path config = "configs/default.json";
    std::size_t context_budget = 2048;
    std::size_t max_new_tokens = 256;
    std::size_t repetitions = 1;
    std::size_t warmup_runs = 0;
    std::size_t inference_threads = 0;
    std::size_t max_num_seqs = 1;
    std::size_t cache_size_gb = 0;
    std::size_t num_kv_blocks = 0;
    std::size_t max_num_batched_tokens = 256;
    std::size_t eviction_start = 32;
    std::size_t eviction_recent = 128;
    std::size_t eviction_max = 672;
    bool enable_prefix_caching = false;
    bool enable_eviction = false;
    bool conversation = false;
    bool do_sample = false;
    bool help = false;
};

volatile std::sig_atomic_t cancellation_requested = 0;

void handle_interrupt(int) { cancellation_requested = 1; }

using GenerationStats = local_llm::GenerationMetrics;

bool use_color() {
#ifdef __linux__
    return ::isatty(STDOUT_FILENO) != 0;
#else
    return true;
#endif
}

std::string paint(const std::string& code, const std::string& text) {
    return use_color() ? "\033[" + code + "m" + text + "\033[0m" : text;
}

std::string model_label(const fs::path& path) {
    return local_llm::ModelRegistry::label(path);
}

std::string read_text(const fs::path& path);

void print_usage() {
    std::cout
        << "Shikai - local OpenVINO language model\n\n"
        << "Usage:\n"
        << "  shikai [chat] [--model DIR] [--device DEVICE]\n"
        << "  shikai devices\n"
        << "  shikai generate (--prompt TEXT | --prompt-file FILE) [options]\n"
        << "  shikai benchmark [--prompts FILE] [--output FILE] [options]\n\n"
        << "  shikai cache-probe (--prompt TEXT | --prompt-file FILE) --output FILE [options]\n\n"
        << "Options:\n"
        << "  --model DIR              Local OpenVINO model directory\n"
        << "  --device DEVICE          OpenVINO device, default CPU\n"
        << "  --config FILE            JSON runtime configuration\n"
        << "  --context-budget N       Total input-plus-output token budget\n"
        << "  --max-new-tokens N       Maximum generated tokens\n"
        << "  --repetitions N          Recorded runs per benchmark prompt\n"
        << "  --warmup-runs N          Unrecorded warmup runs per prompt\n"
        << "  --threads N              CPU inference threads (0 = runtime default)\n"
        << "  --kv-cache-precision P   auto, u4, u8, f16, bf16, or f32 (device dependent)\n"
        << "  --prefix-caching         Enable cross-request prefix caching\n"
        << "  --no-prefix-caching      Disable cross-request prefix caching\n"
        << "  --cache-size-gb N        Fixed scheduler cache capacity\n"
        << "  --num-kv-blocks N        Fixed cache block pool (0 = automatic)\n"
        << "  --max-batched-tokens N   Scheduler prefill chunk size\n"
        << "  --cache-eviction         Enable bounded KV-cache eviction\n"
        << "  --no-cache-eviction      Disable KV-cache eviction\n"
        << "  --eviction-start N       Retained initial tokens (default 32)\n"
        << "  --eviction-recent N      Retained recent tokens (default 128)\n"
        << "  --eviction-max N         Per-sequence eviction limit (default 672)\n"
        << "  --conversation          Benchmark successive prompts as one conversation\n"
        << "  --do-sample              Enable sampling\n"
        << "  --greedy                 Disable sampling\n"
        << "  -h, --help               Show this help\n";
}

void apply_config(Options& options) {
    const auto config_path = fs::absolute(options.config);
    const auto config = ov::genai::JsonContainer::from_json_string(read_text(config_path));
    if (!config.is_object()) throw std::invalid_argument("Configuration root must be a JSON object");

    const auto string_value = [&](const char* key) -> std::optional<std::string> {
        if (!config.contains(key)) return std::nullopt;
        const auto value = config[key].as_string();
        if (!value) throw std::invalid_argument(std::string("Configuration '") + key + "' must be a string");
        return value;
    };
    const auto size_value = [&](const char* key) -> std::optional<std::size_t> {
        if (!config.contains(key)) return std::nullopt;
        const auto value = config[key].as_int();
        if (!value || *value <= 0) throw std::invalid_argument(std::string("Configuration '") + key + "' must be a positive integer");
        return static_cast<std::size_t>(*value);
    };

    if (const auto value = string_value("model_path")) {
        fs::path configured = *value;
        options.model = configured.is_absolute() ? configured : config_path.parent_path() / configured;
    }
    if (const auto value = string_value("device")) options.device = *value;
    if (const auto value = string_value("kv_cache_precision")) options.kv_cache_precision = *value;
    if (const auto value = size_value("context_budget")) options.context_budget = *value;
    if (const auto value = size_value("max_new_tokens")) options.max_new_tokens = *value;
    if (config.contains("do_sample")) {
        const auto value = config["do_sample"].as_bool();
        if (!value) throw std::invalid_argument("Configuration 'do_sample' must be boolean");
        options.do_sample = *value;
    }
    if (const auto value = size_value("max_num_seqs")) options.max_num_seqs = *value;
    if (config.contains("inference_threads")) {
        const auto value = config["inference_threads"].as_int();
        if (!value || *value < 0) throw std::invalid_argument("Configuration 'inference_threads' must be a nonnegative integer");
        options.inference_threads = static_cast<std::size_t>(*value);
    }
    if (config.contains("cache_size_gb")) {
        const auto value = config["cache_size_gb"].as_int();
        if (!value || *value < 0) throw std::invalid_argument("Configuration 'cache_size_gb' must be a nonnegative integer");
        options.cache_size_gb = static_cast<std::size_t>(*value);
    }
    const auto bool_value = [&](const char* key, bool& target) {
        if (!config.contains(key)) return;
        const auto value = config[key].as_bool();
        if (!value) throw std::invalid_argument(std::string("Configuration '") + key + "' must be boolean");
        target = *value;
    };
    bool_value("enable_prefix_caching", options.enable_prefix_caching);
    bool_value("enable_eviction", options.enable_eviction);
    if (config.contains("num_kv_blocks")) {
        const auto value = config["num_kv_blocks"].as_int();
        if (!value || *value < 0) throw std::invalid_argument("Configuration 'num_kv_blocks' must be a nonnegative integer");
        options.num_kv_blocks = static_cast<std::size_t>(*value);
    }
    if (const auto value = size_value("max_num_batched_tokens")) options.max_num_batched_tokens = *value;
    if (const auto value = size_value("eviction_start")) options.eviction_start = *value;
    if (const auto value = size_value("eviction_recent")) options.eviction_recent = *value;
    if (const auto value = size_value("eviction_max")) options.eviction_max = *value;
    options.config = config_path;
}

Options parse_options(int argc, char* argv[]) {
    Options options;
    int index = 1;
    if (index < argc && argv[index][0] != '-') options.command = argv[index++];
    if (options.command != "chat" && options.command != "generate" &&
        options.command != "benchmark" && options.command != "cache-probe" && options.command != "devices")
        throw std::invalid_argument("Unknown command: " + options.command);
    const auto first_option = index;
    const std::vector<std::string> valued_options{
        "--model", "--device", "--prompt", "--prompt-file", "--prompts", "--output",
        "--config", "--context-budget", "--max-new-tokens", "--repetitions", "--warmup-runs",
        "--threads", "--kv-cache-precision", "--cache-size-gb", "--num-kv-blocks",
        "--max-batched-tokens", "--eviction-start", "--eviction-recent", "--eviction-max"};
    // Skip option values: literal prompt text such as "--config" is not a flag.
    for (int cursor = first_option; cursor < argc; ++cursor) {
        const std::string argument = argv[cursor];
        if (argument == "--help" || argument == "-h") options.help = true;
        if (std::find(valued_options.begin(), valued_options.end(), argument) != valued_options.end()) {
            if (cursor + 1 >= argc) throw std::invalid_argument(argument + " requires a value");
            if (argument == "--config") options.config = argv[cursor + 1];
            ++cursor;
        }
    }
    if (options.help) return options;
    // Help and hardware discovery work without a model or configuration file.
    if (options.command != "devices") apply_config(options);
    const auto value_after = [&](const std::string& option) -> std::string {
        if (index + 1 >= argc) throw std::invalid_argument(option + " requires a value");
        return argv[++index];
    };
    const auto size_after = [&](const std::string& option) -> std::size_t {
        const auto text = value_after(option);
        std::size_t value = 0;
        const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
        if (text.empty() || result.ec != std::errc{} || result.ptr != text.data() + text.size())
            throw std::invalid_argument(option + " requires a nonnegative integer within range");
        return value;
    };
    bool has_prompt = false;
    bool has_prompt_file = false;
    for (; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "-h" || argument == "--help") options.help = true;
        else if (argument == "--model") options.model = value_after(argument);
        else if (argument == "--device") options.device = value_after(argument);
        else if (argument == "--prompt") { options.prompt = value_after(argument); has_prompt = true; }
        else if (argument == "--prompt-file") { options.prompt_file = value_after(argument); has_prompt_file = true; }
        else if (argument == "--prompts") options.prompts_file = value_after(argument);
        else if (argument == "--output") options.output = value_after(argument);
        else if (argument == "--config") options.config = value_after(argument);
        else if (argument == "--context-budget") options.context_budget = size_after(argument);
        else if (argument == "--max-new-tokens") options.max_new_tokens = size_after(argument);
        else if (argument == "--repetitions") options.repetitions = size_after(argument);
        else if (argument == "--warmup-runs") options.warmup_runs = size_after(argument);
        else if (argument == "--threads") options.inference_threads = size_after(argument);
        else if (argument == "--kv-cache-precision") options.kv_cache_precision = value_after(argument);
        else if (argument == "--prefix-caching") options.enable_prefix_caching = true;
        else if (argument == "--no-prefix-caching") options.enable_prefix_caching = false;
        else if (argument == "--cache-size-gb") options.cache_size_gb = size_after(argument);
        else if (argument == "--num-kv-blocks") options.num_kv_blocks = size_after(argument);
        else if (argument == "--max-batched-tokens") options.max_num_batched_tokens = size_after(argument);
        else if (argument == "--eviction-start") options.eviction_start = size_after(argument);
        else if (argument == "--eviction-recent") options.eviction_recent = size_after(argument);
        else if (argument == "--eviction-max") options.eviction_max = size_after(argument);
        else if (argument == "--conversation") options.conversation = true;
        else if (argument == "--cache-eviction") options.enable_eviction = true;
        else if (argument == "--no-cache-eviction") options.enable_eviction = false;
        else if (argument == "--do-sample") options.do_sample = true;
        else if (argument == "--greedy") options.do_sample = false;
        else throw std::invalid_argument("Unknown option: " + argument);
    }
    if (has_prompt && has_prompt_file)
        throw std::invalid_argument("Use only one of --prompt and --prompt-file");
    if (options.inference_threads > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::invalid_argument("--threads exceeds the runtime integer range");
    if (options.context_budget == 0 || options.max_new_tokens == 0 || options.repetitions == 0)
        throw std::invalid_argument("Token limits must be greater than zero");
    if (options.max_new_tokens >= options.context_budget)
        throw std::invalid_argument("max_new_tokens must be smaller than context_budget");
    if (options.num_kv_blocks && options.cache_size_gb)
        throw std::invalid_argument("Use only one of num_kv_blocks and cache_size_gb");
    if (options.enable_prefix_caching && !options.num_kv_blocks && !options.cache_size_gb)
        throw std::invalid_argument("Prefix caching requires a bounded pool: set --num-kv-blocks or --cache-size-gb");
    if (!options.max_num_batched_tokens)
        throw std::invalid_argument("max_num_batched_tokens must be greater than zero");
    if (!options.eviction_start || !options.eviction_recent || !options.eviction_max ||
        options.eviction_start >= options.eviction_max ||
        options.eviction_recent >= options.eviction_max - options.eviction_start)
        throw std::invalid_argument("eviction_max must exceed positive eviction_start + eviction_recent");
    if (options.enable_eviction && (options.eviction_start % 32 || options.eviction_recent % 32 || options.eviction_max % 32))
        throw std::invalid_argument("Eviction token limits must be multiples of 32 on the supported CPU/GPU profiles");
    if (options.conversation && (options.command != "benchmark" || options.repetitions != 1 || options.warmup_runs != 0))
        throw std::invalid_argument("--conversation requires benchmark with --repetitions 1 and --warmup-runs 0; repeat whole conversations in separate processes");
    const std::vector<std::string> precisions{"auto", "u4", "u8", "f16", "bf16", "f32"};
    if (std::find(precisions.begin(), precisions.end(), options.kv_cache_precision) == precisions.end())
        throw std::invalid_argument("kv_cache_precision must be auto, u4, u8, f16, bf16, or f32");
    return options;
}

void validate_model(const fs::path& model_path) {
    local_llm::ModelRegistry::validate(model_path);
}

std::string read_text(const fs::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot open file: " + path.string());
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

void print_header(const Options& options, double load_ms) {
    const auto rule = std::string(66, '-');
    std::cout << paint("38;5;208", "  ◉") << "  " << paint("1", "Shikai")
              << " v" << VERSION << '\n'
              << "     " << model_label(options.model) << " · OpenVINO GenAI · " << options.device << '\n'
              << "     " << fs::current_path().string() << '\n'
              << paint("2", rule) << '\n'
              << "  Try \"Explain quantization like I am a beginner\"\n"
              << paint("2", rule) << '\n'
              << "  " << model_label(options.model) << " | ready | load "
              << std::fixed << std::setprecision(0) << load_ms << " ms | context "
              << options.context_budget << " | max output " << options.max_new_tokens
              << " | " << (options.do_sample ? "sampling" : "greedy") << "\n"
              << "  scheduler: sequences=" << options.max_num_seqs
              << " prefix=" << (options.enable_prefix_caching ? "on" : "off")
              << " eviction=" << (options.enable_eviction ? "on" : "off")
              << " cache=" << (options.num_kv_blocks ? std::to_string(options.num_kv_blocks) + " blocks" :
                  options.cache_size_gb ? std::to_string(options.cache_size_gb) + " GB" : "dynamic")
              << " prefill-chunk=" << options.max_num_batched_tokens
              << " threads=" << (options.inference_threads ? std::to_string(options.inference_threads) : "runtime") << "\n";
    std::cout << "  KV-cache precision request: " << options.kv_cache_precision << "\n";
}

void print_chat_help() {
    std::cout << "Commands:\n"
              << "  /help   Show this help\n"
              << "  /stats  Show statistics for the previous response\n"
              << "  /reset  Clear conversation history and statistics\n"
              << "  /exit   Exit Shikai\n";
}

template <typename T>
std::string metric_text(const std::optional<T>& value,
                        const std::string& unavailable = "N/A", int precision = 2) {
    if (!value) return unavailable;
    std::ostringstream text;
    text << std::fixed << std::setprecision(precision) << *value;
    return text.str();
}

std::optional<double> mib(const std::optional<std::size_t>& kib) {
    return kib ? std::optional<double>(*kib / 1024.0) : std::nullopt;
}

void print_resources(std::ostream& output, const local_llm::ResourceUsage& usage) {
    output << "  Generation CPU time:   " << metric_text(usage.cpu_ms) << " ms\n"
           << "  Average CPU use:       " << metric_text(usage.cpu_percent) << "% (100% = one logical CPU)\n"
           << "  Sampled generation RSS peak: " << metric_text(mib(usage.sampled_peak_rss_kib)) << " MiB\n"
           << "  Resource samples:      " << usage.samples << " (" << usage.interval_ms << " ms interval)\n"
           << "  GPU buffer allocation peak: " << metric_text(mib(usage.gpu_buffer_peak_kib)) << " MiB\n"
           << "  GPU system-memory buffers:  " << metric_text(mib(usage.gpu_system_peak_kib)) << " MiB\n"
           << "  GPU local-memory buffers:   " << metric_text(mib(usage.gpu_local_peak_kib)) << " MiB\n"
           << "  GPU engine use sum:    " << metric_text(usage.gpu_engine_percent) << "%\n";
}

void print_stats(const std::optional<GenerationStats>& stats) {
    if (!stats) {
        std::cout << "No generation statistics yet. Ask Shikai a question first.\n";
        return;
    }
    const auto mib = [](std::size_t kib) { return static_cast<double>(kib) / 1024.0; };
    std::cout << std::fixed << std::setprecision(2)
              << "Last response statistics:\n"
              << "  Model load time:       " << stats->load_ms << " ms\n"
              << "  Input tokens:          " << stats->input_tokens << '\n'
              << "  Output tokens:         " << stats->output_tokens << '\n'
              << "  Time to first token:   " << metric_text(stats->ttft_ms) << " ms\n"
              << "  Time per output token: " << metric_text(stats->tpot_ms) << " ms/token\n"
              << "  Throughput:            " << metric_text(stats->throughput) << " tokens/s\n"
              << "  End-to-end time:       " << stats->wall_ms << " ms\n"
              << "  Current process RSS:   " << mib(stats->rss_kib) << " MiB\n"
              << "  Peak process RSS:      " << mib(stats->peak_rss_kib) << " MiB\n"
              << "  Old turns trimmed:     " << stats->trimmed_turns << '\n';
    print_resources(std::cout, stats->resources);
}

GenerationStats collect_stats(ov::genai::PerfMetrics& metrics, double load_ms,
                              const local_llm::ResourceUsage& resources, std::size_t trimmed_turns = 0) {
    return local_llm::collect_metrics(metrics, load_ms, resources.wall_ms, trimmed_turns, resources);
}

struct LoadedPipeline {
    static ov::genai::SchedulerConfig scheduler_config(const Options& options) {
        ov::genai::SchedulerConfig scheduler;
        scheduler.max_num_seqs = options.max_num_seqs;
        scheduler.enable_prefix_caching = options.enable_prefix_caching;
        scheduler.cache_size = options.cache_size_gb;
        scheduler.num_kv_blocks = options.num_kv_blocks;
        scheduler.max_num_batched_tokens = options.max_num_batched_tokens;
        scheduler.dynamic_split_fuse = true;
        scheduler.use_cache_eviction = options.enable_eviction;
        if (options.enable_eviction) {
            scheduler.cache_eviction_config = ov::genai::CacheEvictionConfig(
                options.eviction_start, options.eviction_recent, options.eviction_max,
                ov::genai::AggregationMode::NORM_SUM);
        }
        return scheduler;
    }

    static ov::AnyMap device_properties(const Options& options) {
        ov::AnyMap properties;
        if (options.inference_threads > 0 && options.device.rfind("CPU", 0) == 0)
            properties.insert(ov::inference_num_threads(options.inference_threads));
        if (options.kv_cache_precision != "auto")
            properties.insert(ov::hint::kv_cache_precision(ov::element::Type(options.kv_cache_precision)));
        return properties;
    }

    static ov::genai::LLMPipeline create(const Options& options) {
        auto properties = device_properties(options);
        properties.insert(ov::genai::scheduler_config(scheduler_config(options)));
        return ov::genai::LLMPipeline(fs::absolute(options.model).string(), options.device, properties);
    }

    explicit LoadedPipeline(const Options& options)
        : started(std::chrono::steady_clock::now()),
          pipeline(create(options)),
          load_ms(std::chrono::duration<double, std::milli>(
              std::chrono::steady_clock::now() - started).count()) {}
    std::chrono::steady_clock::time_point started;
    ov::genai::LLMPipeline pipeline;
    double load_ms;
};

ov::genai::GenerationConfig generation_config(const Options& options) {
    ov::genai::GenerationConfig config;
    config.max_new_tokens = options.max_new_tokens;
    config.do_sample = options.do_sample;
    return config;
}

int run_devices() {
    std::cout << paint("1", "Available OpenVINO devices") << "\n";
    local_llm::DeviceProbe::print(std::cout);
    return 0;
}

std::string context_rejection(std::size_t input_tokens, const Options& options) {
    return "Prompt rejected: " + std::to_string(input_tokens) + " input + " +
        std::to_string(options.max_new_tokens) + " output tokens exceed the " +
        std::to_string(options.context_budget) + "-token context budget.";
}

void require_context(ov::genai::Tokenizer& tokenizer,
                     const ov::genai::ChatHistory& history, const Options& options) {
    const local_llm::ContextPolicy context(options.context_budget, options.max_new_tokens);
    const auto tokens = context.formatted_token_count(tokenizer, history);
    if (!context.fits(tokens)) throw std::invalid_argument(context_rejection(tokens, options));
}

int run_chat(const Options& options) {
    validate_model(options.model);
    auto loaded = std::make_unique<LoadedPipeline>(options);
    auto tokenizer = loaded->pipeline.get_tokenizer();
    const auto config = generation_config(options);
    local_llm::ChatSession session;
    local_llm::ContextPolicy context(options.context_budget, options.max_new_tokens);
    std::optional<GenerationStats> last_stats;
    const auto previous_handler = std::signal(SIGINT, handle_interrupt);
    print_header(options, loaded->load_ms);

    std::string prompt;
    while (true) {
        std::cout << "\n" << paint("1;38;5;208", ">") << ' ' << std::flush;
        if (!std::getline(std::cin, prompt) || prompt == "/exit") break;
        if (prompt.empty()) continue;
        if (prompt == "/help") { print_chat_help(); continue; }
        if (prompt == "/stats") { print_stats(last_stats); continue; }
        if (prompt == "/reset") {
            if (options.enable_prefix_caching) {
                // Release retained KV blocks as well as logical history. Destroy first
                // so reset never needs memory for two loaded models simultaneously.
                loaded.reset();
                loaded = std::make_unique<LoadedPipeline>(options);
                tokenizer = loaded->pipeline.get_tokenizer();
            }
            session.clear();
            last_stats.reset();
            std::cout << "Conversation reset.\n";
            if (options.enable_prefix_caching)
                std::cout << "Prefix cache released; pipeline rebuilt.\n";
            continue;
        }

        std::size_t trimmed_turns = 0;
        auto candidate = session;
        auto history = candidate.history_with(prompt);
        auto input_tokens = context.formatted_token_count(tokenizer, history);
        while (!context.fits(input_tokens) && !candidate.empty()) {
            candidate.remove_oldest();
            ++trimmed_turns;
            history = candidate.history_with(prompt);
            input_tokens = context.formatted_token_count(tokenizer, history);
        }
        if (!context.fits(input_tokens)) {
            std::cout << context_rejection(input_tokens, options) << '\n';
            continue;
        }
        if (trimmed_turns)
            std::cout << paint("33", "Context: removed " + std::to_string(trimmed_turns) +
                " oldest turn(s).") << '\n';

        std::cout << '\n';
        cancellation_requested = 0;
        auto streamer = [](const std::string& text) {
            std::cout << text << std::flush;
            return cancellation_requested ? ov::genai::StreamingStatus::CANCEL
                                          : ov::genai::StreamingStatus::RUNNING;
        };
        local_llm::ResourceProfiler profiler(options.device.rfind("GPU", 0) == 0);
        auto result = loaded->pipeline.generate(history, config, streamer);
        const auto resources = profiler.stop();
        if (cancellation_requested) {
            cancellation_requested = 0;
            std::cout << "\n\nGeneration cancelled; the interrupted turn was not added to history.\n";
            continue;
        }
        if (result.texts.empty()) throw std::runtime_error("Model returned no text");
        candidate.append(prompt, result.texts.front());
        session = std::move(candidate);
        last_stats = collect_stats(result.perf_metrics, loaded->load_ms, resources, trimmed_turns);
        std::cout << "\n\n" << paint("2", model_label(options.model) + " | " +
            std::to_string(last_stats->input_tokens) + " in / " +
            std::to_string(last_stats->output_tokens) + " out | " +
            metric_text(last_stats->throughput) + " tok/s") << '\n';
    }
    std::signal(SIGINT, previous_handler);
    std::cout << "\nGoodbye.\n";
    return 0;
}

int run_generate(Options options) {
    if (!options.prompt_file.empty()) options.prompt = read_text(options.prompt_file);
    if (options.prompt.empty())
        throw std::invalid_argument("generate requires --prompt TEXT or --prompt-file FILE");
    validate_model(options.model);
    LoadedPipeline loaded(options);
    local_llm::ChatSession session;
    auto history = session.history_with(options.prompt);
    auto tokenizer = loaded.pipeline.get_tokenizer();
    require_context(tokenizer, history, options);
    cancellation_requested = 0;
    const auto previous_handler = std::signal(SIGINT, handle_interrupt);
    auto streamer = [](const std::string& text) {
        std::cout << text << std::flush;
        return cancellation_requested ? ov::genai::StreamingStatus::CANCEL
                                      : ov::genai::StreamingStatus::RUNNING;
    };
    local_llm::ResourceProfiler profiler(options.device.rfind("GPU", 0) == 0);
    auto result = loaded.pipeline.generate(history, generation_config(options), streamer);
    const auto resources = profiler.stop();
    std::signal(SIGINT, previous_handler);
    std::cout << '\n';
    if (cancellation_requested) {
        std::cerr << "Generation cancelled.\n";
        return 130;
    }
    if (result.texts.empty()) throw std::runtime_error("Model returned no text");
    auto stats = collect_stats(result.perf_metrics, loaded.load_ms, resources);
    std::cerr << model_label(options.model) << " | " << stats.input_tokens << " in / "
              << stats.output_tokens << " out | " << std::fixed << std::setprecision(2)
              << metric_text(stats.throughput) << " tok/s\n";
    print_resources(std::cerr, resources);
    return 0;
}

std::vector<std::pair<std::string, std::string>> load_benchmark_prompts(const fs::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot open prompts file: " + path.string());
    std::vector<std::pair<std::string, std::string>> prompts;
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (line.find_first_not_of(" \t\r") == std::string::npos) continue;
        try {
            const auto record = ov::genai::JsonContainer::from_json_string(line);
            if (!record.is_object() || !record.contains("id") || !record.contains("prompt"))
                throw std::invalid_argument("record requires string fields 'id' and 'prompt'");
            const auto id = record["id"].as_string();
            const auto prompt = record["prompt"].as_string();
            if (!id || id->empty() || !prompt || prompt->empty())
                throw std::invalid_argument("'id' and 'prompt' must be nonempty strings");
            prompts.emplace_back(*id, *prompt);
        } catch (const std::exception& error) {
            throw std::runtime_error(path.string() + ":" + std::to_string(line_number) +
                                     ": invalid benchmark record: " + error.what());
        }
    }
    if (prompts.empty()) throw std::runtime_error("No benchmark prompts found in " + path.string());
    return prompts;
}

std::string csv_escape(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size() + 2);
    escaped.push_back('"');
    for (const char character : value) {
        if (character == '"') escaped += "\"\"";
        else if (character == '\n' || character == '\r') escaped.push_back(' ');
        else escaped.push_back(character);
    }
    escaped.push_back('"');
    return escaped;
}

int run_cache_probe(Options options) {
    if (!options.prompt_file.empty()) options.prompt = read_text(options.prompt_file);
    if (options.prompt.empty()) throw std::invalid_argument("cache-probe requires --prompt or --prompt-file");
    validate_model(options.model);
    ov::genai::ContinuousBatchingPipeline pipeline(fs::absolute(options.model),
        LoadedPipeline::scheduler_config(options), options.device, LoadedPipeline::device_properties(options));
    auto tokenizer = pipeline.get_tokenizer();
    local_llm::ChatSession session;
    const auto history = session.history_with(options.prompt);
    require_context(tokenizer, history, options);
    if (options.output.has_parent_path()) fs::create_directories(options.output.parent_path());
    std::ofstream output(options.output);
    if (!output) throw std::runtime_error("Cannot create output: " + options.output.string());
    output << "repetition,cache_allocated_bytes,max_cache_usage_percent,avg_cache_usage_percent,ttft_ms,input_tokens,output_tokens,response\n";
    for (std::size_t repetition = 1; repetition <= options.repetitions; ++repetition) {
        auto results = pipeline.generate(std::vector<ov::genai::ChatHistory>{history}, {generation_config(options)});
        if (results.empty() || results.front().m_generation_ids.empty())
            throw std::runtime_error("Cache probe returned no response");
        const auto cache = pipeline.get_metrics();
        auto& result = results.front();
        output << repetition << ',' << cache.cache_size_in_bytes << ',' << cache.max_cache_usage << ','
               << cache.avg_cache_usage << ',' << result.perf_metrics.get_ttft().mean << ','
               << result.perf_metrics.get_num_input_tokens() << ',' << result.perf_metrics.get_num_generated_tokens() << ','
               << csv_escape(result.m_generation_ids.front()) << '\n';
    }
    std::cout << "Cache allocation probe saved to " << options.output
              << ". Allocated bytes include free pool blocks; usage counters describe the probe pipeline.\n";
    return 0;
}

int run_benchmark(const Options& options) {
    validate_model(options.model);
    const auto prompts = load_benchmark_prompts(options.prompts_file);
    LoadedPipeline loaded(options);
    auto tokenizer = loaded.pipeline.get_tokenizer();
    if (options.output.has_parent_path()) fs::create_directories(options.output.parent_path());
    std::ofstream output(options.output);
    if (!output) throw std::runtime_error("Cannot create output: " + options.output.string());
    output << "id,repetition,model,device,input_tokens,output_tokens,load_ms,ttft_ms,tpot_ms,throughput_tok_s,wall_ms,rss_mib,peak_rss_mib,response,"
              "cpu_time_ms,cpu_util_percent,sampled_peak_rss_mib,rss_start_mib,rss_end_mib,resource_samples,sample_interval_ms,"
              "gpu_buffer_peak_mib,gpu_system_peak_mib,gpu_local_peak_mib,gpu_engine_percent,kv_cache_precision,thread_setting,context_budget,max_new_tokens,"
              "prefix_caching,num_kv_blocks,cache_size_gb,max_num_batched_tokens,cache_eviction,eviction_start,eviction_recent,eviction_max,conversation\n";
    std::cout << "Benchmarking " << model_label(options.model) << " on " << options.device
              << " with " << prompts.size() << " prompt(s).\n";
    local_llm::ChatSession session;
    for (const auto& [id, prompt] : prompts) {
        const auto history = session.history_with(prompt);
        require_context(tokenizer, history, options);
        for (std::size_t warmup = 0; warmup < options.warmup_runs; ++warmup)
            loaded.pipeline.generate(history, generation_config(options));
        for (std::size_t repetition = 1; repetition <= options.repetitions; ++repetition) {
            local_llm::ResourceProfiler profiler(options.device.rfind("GPU", 0) == 0);
            auto result = loaded.pipeline.generate(history, generation_config(options));
            const auto resources = profiler.stop();
            if (result.texts.empty()) throw std::runtime_error("Benchmark generation returned no text");
            auto stats = collect_stats(result.perf_metrics, loaded.load_ms, resources);
            output << csv_escape(id) << ',' << repetition << ',' << csv_escape(model_label(options.model)) << ','
                   << csv_escape(options.device) << ',' << stats.input_tokens << ',' << stats.output_tokens << ','
                   << stats.load_ms << ',' << metric_text(stats.ttft_ms, "", 6) << ','
                   << metric_text(stats.tpot_ms, "", 6) << ','
                   << metric_text(stats.throughput, "", 6) << ',' << stats.wall_ms << ',' << stats.rss_kib / 1024.0
                   << ',' << stats.peak_rss_kib / 1024.0 << ','
                   << csv_escape(result.texts.front()) << ','
                   << metric_text(resources.cpu_ms, "", 6) << ',' << metric_text(resources.cpu_percent, "", 6) << ','
                   << metric_text(mib(resources.sampled_peak_rss_kib), "", 6) << ','
                   << metric_text(mib(resources.rss_start_kib), "", 6) << ','
                   << metric_text(mib(resources.rss_end_kib), "", 6) << ','
                   << resources.samples << ',' << resources.interval_ms << ','
                   << metric_text(mib(resources.gpu_buffer_peak_kib), "", 6) << ','
                   << metric_text(mib(resources.gpu_system_peak_kib), "", 6) << ','
                   << metric_text(mib(resources.gpu_local_peak_kib), "", 6) << ','
                   << metric_text(resources.gpu_engine_percent, "", 6) << ','
                   << options.kv_cache_precision << ',' << options.inference_threads << ','
                   << options.context_budget << ',' << options.max_new_tokens << ','
                   << options.enable_prefix_caching << ',' << options.num_kv_blocks << ','
                   << options.cache_size_gb << ',' << options.max_num_batched_tokens << ','
                   << options.enable_eviction << ',' << options.eviction_start << ','
                   << options.eviction_recent << ',' << options.eviction_max << ',' << options.conversation << '\n';
            if (options.conversation) session.append(prompt, result.texts.front());
            std::cout << "  " << id << " [" << repetition << '/' << options.repetitions
                      << "]: " << stats.input_tokens << " in / " << stats.output_tokens
                      << " out, " << std::fixed << std::setprecision(2)
                      << metric_text(stats.throughput) << " tok/s\n";
        }
    }
    std::cout << "Results saved to " << options.output << '\n';
    return 0;
}

}  // namespace

int main(int argc, char* argv[]) {
    try {
        const auto options = parse_options(argc, argv);
        if (options.help) { print_usage(); return 0; }
        if (options.command == "devices") return run_devices();
        if (options.command == "chat") return run_chat(options);
        if (options.command == "generate") return run_generate(options);
        if (options.command == "benchmark") return run_benchmark(options);
        if (options.command == "cache-probe") return run_cache_probe(options);
        throw std::invalid_argument("Unknown command: " + options.command);
    } catch (const std::exception& error) {
        std::cerr << "shikai: " << error.what() << '\n';
        return 1;
    }
}
