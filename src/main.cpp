#include <openvino/genai/llm_pipeline.hpp>
#include <openvino/openvino.hpp>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
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
constexpr const char* DEFAULT_MODEL = "models/qwen2.5-1.5b/int4";
constexpr std::size_t CONTEXT_BUDGET = 2048;
constexpr std::size_t DEFAULT_MAX_NEW_TOKENS = 256;

struct Options {
    std::string command = "chat";
    fs::path model = DEFAULT_MODEL;
    std::string device = "CPU";
    std::string prompt;
    fs::path prompt_file;
    fs::path prompts_file = "benchmarks/prompts.jsonl";
    fs::path output = "results/benchmark.csv";
    fs::path config;
    std::size_t max_new_tokens = DEFAULT_MAX_NEW_TOKENS;
    bool help = false;
};

struct Turn { std::string user; std::string assistant; };

struct GenerationStats {
    double load_ms = 0;
    double wall_ms = 0;
    float ttft_ms = 0;
    float tpot_ms = 0;
    float throughput = 0;
    std::size_t input_tokens = 0;
    std::size_t output_tokens = 0;
    std::size_t rss_kib = 0;
    std::size_t peak_rss_kib = 0;
    std::size_t trimmed_turns = 0;
};

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
    const auto value = path.string();
    if (value.find("qwen2.5-1.5b") != std::string::npos) {
        std::string precision = path.filename().string();
        for (auto& character : precision)
            character = static_cast<char>(std::toupper(static_cast<unsigned char>(character)));
        return "Qwen2.5-1.5B-Instruct " + precision;
    }
    return path.filename().string();
}

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
        << "  --max-new-tokens N       Maximum generated tokens\n"
        << "  --config FILE            Benchmark configuration (reserved)\n"
        << "  -h, --help               Show this help\n";
}

Options parse_options(int argc, char* argv[]) {
    Options options;
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
        else if (argument == "--max-new-tokens") options.max_new_tokens = std::stoul(value_after(argument));
        else throw std::invalid_argument("Unknown option: " + argument);
    }
    return options;
}

void validate_model(const fs::path& model_path) {
    const char* required[] = {
        "openvino_model.xml", "openvino_model.bin", "openvino_tokenizer.xml",
        "openvino_tokenizer.bin", "openvino_detokenizer.xml",
        "openvino_detokenizer.bin", "tokenizer_config.json",
    };
    for (const char* file : required) {
        const auto asset = model_path / file;
        if (!fs::is_regular_file(asset))
            throw std::runtime_error("Missing required model asset: " + asset.string());
    }
}

std::string read_text(const fs::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot open file: " + path.string());
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

std::size_t read_proc_kib(const std::string& key) {
    std::ifstream status("/proc/self/status");
    std::string line;
    while (std::getline(status, line)) {
        if (line.rfind(key, 0) == 0) {
            std::istringstream values(line.substr(key.size()));
            std::size_t kib = 0;
            values >> kib;
            return kib;
        }
    }
    return 0;
}

void print_header(const fs::path& model, const std::string& device, double load_ms) {
    const auto rule = std::string(66, '-');
    std::cout << paint("38;5;208", "  ◉") << "  " << paint("1", "Shikai")
              << " v" << VERSION << '\n'
              << "     " << model_label(model) << " · OpenVINO GenAI · " << device << '\n'
              << "     " << fs::current_path().string() << '\n'
              << paint("2", rule) << '\n'
              << "  Try \"Explain quantization like I am a beginner\"\n"
              << paint("2", rule) << '\n'
              << "  " << model_label(model) << " | ready | load "
              << std::fixed << std::setprecision(0) << load_ms << " ms\n";
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

ov::genai::ChatHistory make_history(const std::vector<Turn>& turns, const std::string& prompt) {
    ov::genai::ChatHistory history;
    for (const auto& turn : turns) {
        history.push_back({{"role", "user"}, {"content", turn.user}});
        history.push_back({{"role", "assistant"}, {"content", turn.assistant}});
    }
    history.push_back({{"role", "user"}, {"content", prompt}});
    return history;
}

std::size_t formatted_token_count(ov::genai::Tokenizer& tokenizer,
                                  const ov::genai::ChatHistory& history) {
    const auto formatted = tokenizer.apply_chat_template(history, true);
    const auto encoded = tokenizer.encode(formatted, ov::genai::add_special_tokens(false));
    return encoded.input_ids.get_shape().at(1);
}

GenerationStats collect_stats(ov::genai::PerfMetrics& metrics, double load_ms,
                              double wall_ms, std::size_t trimmed_turns = 0) {
    return {load_ms, wall_ms, metrics.get_ttft().mean, metrics.get_tpot().mean,
            metrics.get_throughput().mean, metrics.get_num_input_tokens(),
            metrics.get_num_generated_tokens(), read_proc_kib("VmRSS:"),
            read_proc_kib("VmHWM:"), trimmed_turns};
}

struct LoadedPipeline {
    explicit LoadedPipeline(const Options& options)
        : started(std::chrono::steady_clock::now()),
          pipeline(fs::absolute(options.model).string(), options.device),
          load_ms(std::chrono::duration<double, std::milli>(
              std::chrono::steady_clock::now() - started).count()) {}
    std::chrono::steady_clock::time_point started;
    ov::genai::LLMPipeline pipeline;
    double load_ms;
};

ov::genai::GenerationConfig generation_config(std::size_t max_new_tokens) {
    ov::genai::GenerationConfig config;
    config.max_new_tokens = max_new_tokens;
    config.do_sample = false;
    return config;
}

int run_devices() {
    ov::Core core;
    std::cout << paint("1", "Available OpenVINO devices") << "\n";
    for (const auto& device : core.get_available_devices()) {
        std::string full_name;
        try { full_name = core.get_property(device, ov::device::full_name); }
        catch (...) { full_name = "name unavailable"; }
        std::cout << "  " << paint("38;5;208", "●") << ' ' << std::left
                  << std::setw(8) << device << full_name << '\n';
    }
    return 0;
}

int run_chat(const Options& options) {
    validate_model(options.model);
    LoadedPipeline loaded(options);
    auto tokenizer = loaded.pipeline.get_tokenizer();
    const auto config = generation_config(options.max_new_tokens);
    std::vector<Turn> turns;
    std::optional<GenerationStats> last_stats;
    print_header(options.model, options.device, loaded.load_ms);

    std::string prompt;
    while (true) {
        std::cout << "\n" << paint("1;38;5;208", ">") << ' ' << std::flush;
        if (!std::getline(std::cin, prompt) || prompt == "/exit") break;
        if (prompt.empty()) continue;
        if (prompt == "/help") { print_chat_help(); continue; }
        if (prompt == "/stats") { print_stats(last_stats); continue; }
        if (prompt == "/reset") {
            turns.clear();
            last_stats.reset();
            std::cout << "Conversation reset.\n";
            continue;
        }

        std::size_t trimmed_turns = 0;
        auto history = make_history(turns, prompt);
        auto input_tokens = formatted_token_count(tokenizer, history);
        while (input_tokens + options.max_new_tokens > CONTEXT_BUDGET && !turns.empty()) {
            turns.erase(turns.begin());
            ++trimmed_turns;
            history = make_history(turns, prompt);
            input_tokens = formatted_token_count(tokenizer, history);
        }
        if (input_tokens + options.max_new_tokens > CONTEXT_BUDGET) {
            std::cout << "Prompt rejected: " << input_tokens << " input + "
                      << options.max_new_tokens << " output tokens exceed the "
                      << CONTEXT_BUDGET << "-token context budget.\n";
            continue;
        }
        if (trimmed_turns)
            std::cout << paint("33", "Context: removed " + std::to_string(trimmed_turns) +
                " oldest turn(s).") << '\n';

        std::cout << '\n';
        auto streamer = [](const std::string& text) {
            std::cout << text << std::flush;
            return ov::genai::StreamingStatus::RUNNING;
        };
        const auto start = std::chrono::steady_clock::now();
        auto result = loaded.pipeline.generate(history, config, streamer);
        const auto wall_ms = std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - start).count();
        if (result.texts.empty()) throw std::runtime_error("Model returned no text");
        turns.push_back({prompt, result.texts.front()});
        last_stats = collect_stats(result.perf_metrics, loaded.load_ms, wall_ms, trimmed_turns);
        std::cout << "\n\n" << paint("2", model_label(options.model) + " | " +
            std::to_string(last_stats->input_tokens) + " in / " +
            std::to_string(last_stats->output_tokens) + " out | " +
            std::to_string(static_cast<int>(last_stats->throughput)) + " tok/s") << '\n';
    }
    std::cout << "\nGoodbye.\n";
    return 0;
}

int run_generate(Options options) {
    if (!options.prompt_file.empty()) options.prompt = read_text(options.prompt_file);
    if (options.prompt.empty())
        throw std::invalid_argument("generate requires --prompt TEXT or --prompt-file FILE");
    validate_model(options.model);
    LoadedPipeline loaded(options);
    auto history = make_history({}, options.prompt);
    const auto start = std::chrono::steady_clock::now();
    auto result = loaded.pipeline.generate(history, generation_config(options.max_new_tokens));
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

int run_benchmark(const Options& options) {
    validate_model(options.model);
    const auto prompts = load_benchmark_prompts(options.prompts_file);
    LoadedPipeline loaded(options);
    if (options.output.has_parent_path()) fs::create_directories(options.output.parent_path());
    std::ofstream output(options.output);
    if (!output) throw std::runtime_error("Cannot create output: " + options.output.string());
    output << "id,model,device,input_tokens,output_tokens,load_ms,ttft_ms,tpot_ms,throughput_tok_s,wall_ms,rss_mib,peak_rss_mib\n";
    std::cout << "Benchmarking " << model_label(options.model) << " on " << options.device
              << " with " << prompts.size() << " prompt(s).\n";
    for (const auto& [id, prompt] : prompts) {
        const auto start = std::chrono::steady_clock::now();
        auto result = loaded.pipeline.generate(make_history({}, prompt),
                                               generation_config(options.max_new_tokens));
        const auto wall_ms = std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - start).count();
        auto stats = collect_stats(result.perf_metrics, loaded.load_ms, wall_ms);
        output << id << ',' << model_label(options.model) << ',' << options.device << ','
               << stats.input_tokens << ',' << stats.output_tokens << ',' << stats.load_ms << ','
               << stats.ttft_ms << ',' << stats.tpot_ms << ',' << stats.throughput << ','
               << stats.wall_ms << ',' << stats.rss_kib / 1024.0 << ','
               << stats.peak_rss_kib / 1024.0 << '\n';
        std::cout << "  " << id << ": " << stats.input_tokens << " in / "
                  << stats.output_tokens << " out, " << std::fixed << std::setprecision(2)
                  << stats.throughput << " tok/s\n";
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
