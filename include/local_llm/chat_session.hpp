#pragma once

#include <openvino/genai/llm_pipeline.hpp>

#include <cstddef>
#include <string>
#include <vector>

namespace local_llm {

struct Turn {
    std::string user;
    std::string assistant;
};

class ChatSession {
public:
    ov::genai::ChatHistory history_with(const std::string& prompt) const;
    void append(std::string user, std::string assistant);
    void clear();
    bool empty() const;
    std::size_t size() const;
    void remove_oldest();

private:
    std::vector<Turn> turns_;
};

}  // namespace local_llm
