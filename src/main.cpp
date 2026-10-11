#include <openvino/genai/llm_pipeline.hpp>
#include <openvino/openvino.hpp>

#include "local_llm/chat_session.hpp"
#include "local_llm/context_policy.hpp"
#include "local_llm/device_probe.hpp"
#include "local_llm/metrics.hpp"
#include "local_llm/model_registry.hpp"

#include <chrono>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
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
    bool enable_prefix_caching = false;
    bool enable_eviction = false;
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
        << "Options:\n"
        << "  --model DIR              Local OpenVINO model directory\n"
        << "  --device DEVICE          OpenVINO device, default CPU\n"
        << "  --config FILE            JSON runtime configuration\n"
        << "  --context-budget N       Total input-plus-output token budget\n"
        << "  --max-new-tokens N       Maximum generated tokens\n"
        << "  --repetitions N          Recorded runs per benchmark prompt\n"
        << "  --warmup-runs N          Unrecorded warmup runs per prompt\n"
        << "  --threads N              CPU inference threads (0 = runtime default)\n"
        << "  --prefix-caching         Enable cross-request prefix caching\n"
        << "  --cache-size-gb N        Fixed scheduler cache capacity\n"
        << "  --cache-eviction         Enable bounded KV-cache eviction\n"
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
    options.config = config_path;
}

Options parse_options(int argc, char* argv[]) {
    Options options;
    for (int cursor = 1; cursor < argc; ++cursor) {
        if (std::string(argv[cursor]) == "--config") {
            if (cursor + 1 >= argc) throw std::invalid_argument("--config requires a value");
            options.config = argv[cursor + 1];
        }
    }
    apply_config(options);
    int index = 1;
    if (index < argc && argv[index][0] != '-') options.command = argv[index++];
    const auto value_after = [&](const std::string& option) -> std::string {
        if (index + 1 >= argc) throw std::invalid_argument(option + " requires a value");
        return argv[++index];
    };
    for (; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "-h" || argument == "--help") options.help = true;
        else if (argument == "--model") options.model = value_after(argument);
        else if (argument == "--device") options.device = value_after(argument);
        else if (argument == "--prompt") options.prompt = value_after(argument);
        else if (argument == "--prompt-file") options.prompt_file = value_after(argument);
        else if (argument == "--prompts") options.prompts_file = value_after(argument);
        else if (argument == "--output") options.output = value_after(argument);
        else if (argument == "--config") options.config = value_after(argument);
        else if (argument == "--context-budget") options.context_budget = std::stoul(value_after(argument));
        else if (argument == "--max-new-tokens") options.max_new_tokens = std::stoul(value_after(argument));
        else if (argument == "--repetitions") options.repetitions = std::stoul(value_after(argument));
        else if (argument == "--warmup-runs") options.warmup_runs = std::stoul(value_after(argument));
        else if (argument == "--threads") options.inference_threads = std::stoul(value_after(argument));
        else if (argument == "--prefix-caching") options.enable_prefix_caching = true;
        else if (argument == "--no-prefix-caching") options.enable_prefix_caching = false;
        else if (argument == "--cache-size-gb") options.cache_size_gb = std::stoul(value_after(argument));
        else if (argument == "--cache-eviction") options.enable_eviction = true;
        else if (argument == "--do-sample") options.do_sample = true;
        else if (argument == "--greedy") options.do_sample = false;
        else throw std::invalid_argument("Unknown option: " + argument);
    }
    if (options.context_budget == 0 || options.max_new_tokens == 0 || options.repetitions == 0)
        throw std::invalid_argument("Token limits must be greater than zero");
    if (options.max_new_tokens >= options.context_budget)
        throw std::invalid_argument("max_new_tokens must be smaller than context_budget");
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
              << " cache=" << (options.cache_size_gb ? std::to_string(options.cache_size_gb) + " GiB" : "dynamic")
              << " threads=" << (options.inference_threads ? std::to_string(options.inference_threads) : "runtime") << "\n";
}

void print_chat_help() {
    std::cout << "Commands:\n"
              << "  /help   Show this help\n"
              << "  /stats  Show statistics for the previous response\n"
              << "  /reset  Clear conversation history and statistics\n"
              << "  /exit   Exit Shikai\n";
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
              << "  Time to first token:   " << stats->ttft_ms << " ms\n"
              << "  Time per output token: " << stats->tpot_ms << " ms/token\n"
              << "  Throughput:            " << stats->throughput << " tokens/s\n"
              << "  End-to-end time:       " << stats->wall_ms << " ms\n"
              << "  Current process RSS:   " << mib(stats->rss_kib) << " MiB\n"
              << "  Peak process RSS:      " << mib(stats->peak_rss_kib) << " MiB\n"
              << "  Old turns trimmed:     " << stats->trimmed_turns << '\n';
}

GenerationStats collect_stats(ov::genai::PerfMetrics& metrics, double load_ms,
                              double wall_ms, std::size_t trimmed_turns = 0) {
    return local_llm::collect_metrics(metrics, load_ms, wall_ms, trimmed_turns);
}

struct LoadedPipeline {
    static ov::genai::LLMPipeline create(const Options& options) {
        ov::genai::SchedulerConfig scheduler;
        scheduler.max_num_seqs = options.max_num_seqs;
        scheduler.enable_prefix_caching = options.enable_prefix_caching;
        scheduler.cache_size = options.cache_size_gb;
        scheduler.use_cache_eviction = options.enable_eviction;
        if (options.enable_eviction) {
            scheduler.cache_eviction_config = ov::genai::CacheEvictionConfig(
                32, 128, 672, ov::genai::AggregationMode::NORM_SUM);
        }
        ov::AnyMap properties;
        properties.insert(ov::genai::scheduler_config(scheduler));
        if (options.inference_threads > 0)
            properties.insert(ov::inference_num_threads(options.inference_threads));
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

int run_chat(const Options& options) {
    validate_model(options.model);
    LoadedPipeline loaded(options);
    auto tokenizer = loaded.pipeline.get_tokenizer();
    const auto config = generation_config(options);
    local_llm::ChatSession session;
    local_llm::ContextPolicy context(options.context_budget, options.max_new_tokens);
    std::optional<GenerationStats> last_stats;
    const auto previous_handler = std::signal(SIGINT, handle_interrupt);
    print_header(options, loaded.load_ms);

    std::string prompt;
    while (true) {
        std::cout << "\n" << paint("1;38;5;208", ">") << ' ' << std::flush;
        if (!std::getline(std::cin, prompt) || prompt == "/exit") break;
        if (prompt.empty()) continue;
        if (prompt == "/help") { print_chat_help(); continue; }
        if (prompt == "/stats") { print_stats(last_stats); continue; }
        if (prompt == "/reset") {
            session.clear();
            last_stats.reset();
            std::cout << "Conversation reset.\n";
            continue;
        }

        std::size_t trimmed_turns = 0;
        auto history = session.history_with(prompt);
        auto input_tokens = context.formatted_token_count(tokenizer, history);
        while (!context.fits(input_tokens) && !session.empty()) {
            session.remove_oldest();
            ++trimmed_turns;
            history = session.history_with(prompt);
            input_tokens = context.formatted_token_count(tokenizer, history);
        }
        if (!context.fits(input_tokens)) {
            std::cout << "Prompt rejected: " << input_tokens << " input + "
                      << options.max_new_tokens << " output tokens exceed the "
                      << options.context_budget << "-token context budget.\n";
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
        const auto start = std::chrono::steady_clock::now();
        auto result = loaded.pipeline.generate(history, config, streamer);
        const auto wall_ms = std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - start).count();
        if (cancellation_requested) {
            cancellation_requested = 0;
            std::cout << "\n\nGeneration cancelled; the interrupted turn was not added to history.\n";
            continue;
        }
        if (result.texts.empty()) throw std::runtime_error("Model returned no text");
        session.append(prompt, result.texts.front());
        last_stats = collect_stats(result.perf_metrics, loaded.load_ms, wall_ms, trimmed_turns);
        std::cout << "\n\n" << paint("2", model_label(options.model) + " | " +
            std::to_string(last_stats->input_tokens) + " in / " +
            std::to_string(last_stats->output_tokens) + " out | " +
            std::to_string(static_cast<int>(last_stats->throughput)) + " tok/s") << '\n';
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
    const auto start = std::chrono::steady_clock::now();
    auto result = loaded.pipeline.generate(history, generation_config(options));
    const auto wall_ms = std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count();
    if (result.texts.empty()) throw std::runtime_error("Model returned no text");
    std::cout << result.texts.front() << '\n';
    auto stats = collect_stats(result.perf_metrics, loaded.load_ms, wall_ms);
    std::cerr << model_label(options.model) << " | " << stats.input_tokens << " in / "
              << stats.output_tokens << " out | " << std::fixed << std::setprecision(2)
              << stats.throughput << " tok/s\n";
    return 0;
}

std::vector<std::pair<std::string, std::string>> load_benchmark_prompts(const fs::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot open prompts file: " + path.string());
    std::vector<std::pair<std::string, std::string>> prompts;
    std::string line;
    while (std::getline(input, line)) {
        const auto id_key = line.find("\"id\"");
        const auto prompt_key = line.find("\"prompt\"");
        if (id_key == std::string::npos || prompt_key == std::string::npos) continue;
        const auto extract = [&](std::size_t key) {
            const auto colon = line.find(':', key);
            const auto first = line.find('"', colon + 1);
            const auto last = line.find('"', first + 1);
            return line.substr(first + 1, last - first - 1);
        };
        prompts.emplace_back(extract(id_key), extract(prompt_key));
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

int run_benchmark(const Options& options) {
    validate_model(options.model);
    const auto prompts = load_benchmark_prompts(options.prompts_file);
    LoadedPipeline loaded(options);
    if (options.output.has_parent_path()) fs::create_directories(options.output.parent_path());
    std::ofstream output(options.output);
    if (!output) throw std::runtime_error("Cannot create output: " + options.output.string());
    output << "id,repetition,model,device,input_tokens,output_tokens,load_ms,ttft_ms,tpot_ms,throughput_tok_s,wall_ms,rss_mib,peak_rss_mib,response\n";
    std::cout << "Benchmarking " << model_label(options.model) << " on " << options.device
              << " with " << prompts.size() << " prompt(s).\n";
    for (const auto& [id, prompt] : prompts) {
        local_llm::ChatSession session;
        const auto history = session.history_with(prompt);
        for (std::size_t warmup = 0; warmup < options.warmup_runs; ++warmup)
            loaded.pipeline.generate(history, generation_config(options));
        for (std::size_t repetition = 1; repetition <= options.repetitions; ++repetition) {
            const auto start = std::chrono::steady_clock::now();
            auto result = loaded.pipeline.generate(history, generation_config(options));
            const auto wall_ms = std::chrono::duration<double, std::milli>(
                std::chrono::steady_clock::now() - start).count();
            if (result.texts.empty()) throw std::runtime_error("Benchmark generation returned no text");
            auto stats = collect_stats(result.perf_metrics, loaded.load_ms, wall_ms);
            output << id << ',' << repetition << ',' << model_label(options.model) << ','
                   << options.device << ',' << stats.input_tokens << ',' << stats.output_tokens << ','
                   << stats.load_ms << ',' << stats.ttft_ms << ',' << stats.tpot_ms << ','
                   << stats.throughput << ',' << stats.wall_ms << ',' << stats.rss_kib / 1024.0
                   << ',' << stats.peak_rss_kib / 1024.0 << ','
                   << csv_escape(result.texts.front()) << '\n';
            std::cout << "  " << id << " [" << repetition << '/' << options.repetitions
                      << "]: " << stats.input_tokens << " in / " << stats.output_tokens
                      << " out, " << std::fixed << std::setprecision(2)
                      << stats.throughput << " tok/s\n";
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
        throw std::invalid_argument("Unknown command: " + options.command);
    } catch (const std::exception& error) {
        std::cerr << "shikai: " << error.what() << '\n';
        return 1;
    }
}
