#include "local_llm/model_registry.hpp"

#include <cctype>
#include <stdexcept>

namespace local_llm {

void ModelRegistry::validate(const std::filesystem::path& model_path) {
    const char* required[] = {
        "openvino_model.xml", "openvino_model.bin", "openvino_tokenizer.xml",
        "openvino_tokenizer.bin", "openvino_detokenizer.xml",
        "openvino_detokenizer.bin", "tokenizer_config.json",
    };
    for (const char* file : required) {
        const auto asset = model_path / file;
        if (!std::filesystem::is_regular_file(asset))
            throw std::runtime_error("Missing required model asset: " + asset.string());
    }
}

std::string ModelRegistry::label(const std::filesystem::path& path) {
    if (path.string().find("qwen2.5-1.5b") != std::string::npos) {
        auto precision = path.filename().string();
        for (auto& character : precision)
            character = static_cast<char>(std::toupper(static_cast<unsigned char>(character)));
        return "Qwen2.5-1.5B-Instruct " + precision;
    }
    return path.filename().string();
}

}  // namespace local_llm
