#include "local_llm/context_policy.hpp"

#include <stdexcept>

namespace local_llm {

ContextPolicy::ContextPolicy(std::size_t budget, std::size_t reserved_output)
    : budget_(budget), reserved_output_(reserved_output) {
    if (budget_ == 0 || reserved_output_ == 0 || reserved_output_ >= budget_)
        throw std::invalid_argument("Invalid context policy limits");
}

std::size_t ContextPolicy::formatted_token_count(
    ov::genai::Tokenizer& tokenizer, const ov::genai::ChatHistory& history) const {
    const auto formatted = tokenizer.apply_chat_template(history, true);
    const auto encoded = tokenizer.encode(formatted, ov::genai::add_special_tokens(false));
    return encoded.input_ids.get_shape().at(1);
}

bool ContextPolicy::fits(std::size_t input_tokens) const {
    return input_tokens + reserved_output_ <= budget_;
}

}  // namespace local_llm
