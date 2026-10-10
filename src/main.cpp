#include <openvino/genai/llm_pipeline.hpp>

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

constexpr const char* DEFAULT_MODEL = "models/qwen2.5-1.5b/int4";

void print_help() {
    std::cout << "Commands:\n"
              << "  /help   Show this help\n"
              << "  /reset  Clear conversation history\n"
              << "  /exit   Exit the application\n";
}

std::filesystem::path parse_model_path(int argc, char* argv[]) {
    if (argc == 1) {
        return DEFAULT_MODEL;
    }
    if (argc == 3 && std::string(argv[1]) == "--model") {
        return argv[2];
    }
    throw std::invalid_argument("Usage: local-llm [--model MODEL_DIRECTORY]");
}

void validate_model(const std::filesystem::path& model_path) {
    const char* required[] = {
        "openvino_model.xml",
        "openvino_model.bin",
        "openvino_tokenizer.xml",
        "openvino_tokenizer.bin",
        "openvino_detokenizer.xml",
        "openvino_detokenizer.bin",
        "tokenizer_config.json",
    };

    for (const char* file : required) {
        const auto asset = model_path / file;
        if (!std::filesystem::is_regular_file(asset)) {
            throw std::runtime_error("Missing required model asset: " + asset.string());
        }
    }
}

}  // namespace

int main(int argc, char* argv[]) {
    try {
        const auto model_path = std::filesystem::absolute(parse_model_path(argc, argv));
        validate_model(model_path);

        std::cout << "Loading local model from " << model_path << " on CPU...\n";
        ov::genai::LLMPipeline pipeline(model_path.string(), "CPU");

        ov::genai::GenerationConfig config;
        config.max_new_tokens = 256;
        config.do_sample = false;

        ov::genai::ChatHistory history;
        std::cout << "Ready. This session uses local files only. Type /help for commands.\n";

        std::string prompt;
        while (true) {
            std::cout << "\nyou> " << std::flush;
            if (!std::getline(std::cin, prompt) || prompt == "/exit") {
                break;
            }
            if (prompt.empty()) {
                continue;
            }
            if (prompt == "/help") {
                print_help();
                continue;
            }
            if (prompt == "/reset") {
                history.clear();
                std::cout << "Conversation reset.\n";
                continue;
            }

            history.push_back({{"role", "user"}, {"content", prompt}});
            std::cout << "assistant> " << std::flush;
            auto streamer = [](const std::string& text) {
                std::cout << text << std::flush;
                return ov::genai::StreamingStatus::RUNNING;
            };
            auto result = pipeline.generate(history, config, streamer);
            if (result.texts.empty()) {
                throw std::runtime_error("Model generation returned no text");
            }
            history.push_back({{"role", "assistant"}, {"content", result.texts.front()}});
            std::cout << '\n';
        }

        std::cout << "Goodbye.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
