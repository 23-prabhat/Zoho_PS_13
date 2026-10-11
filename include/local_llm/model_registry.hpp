#pragma once

#include <filesystem>
#include <string>

namespace local_llm {

class ModelRegistry {
public:
    static void validate(const std::filesystem::path& model_path);
    static std::string label(const std::filesystem::path& model_path);
};

}  // namespace local_llm
