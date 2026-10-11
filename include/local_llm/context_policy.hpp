#pragma once

#include <openvino/genai/tokenizer.hpp>

#include <cstddef>

namespace local_llm {

class ContextPolicy {
public:
    ContextPolicy(std::size_t budget, std::size_t reserved_output);
    std::size_t formatted_token_count(ov::genai::Tokenizer& tokenizer,
                                      const ov::genai::ChatHistory& history) const;
    bool fits(std::size_t input_tokens) const;

private:
    std::size_t budget_;
    std::size_t reserved_output_;
};

}  // namespace local_llm
