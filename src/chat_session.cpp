#include "local_llm/chat_session.hpp"

#include <stdexcept>

namespace local_llm {

ov::genai::ChatHistory ChatSession::history_with(const std::string& prompt) const {
    ov::genai::ChatHistory history;
    for (const auto& turn : turns_) {
        history.push_back({{"role", "user"}, {"content", turn.user}});
        history.push_back({{"role", "assistant"}, {"content", turn.assistant}});
    }
    history.push_back({{"role", "user"}, {"content", prompt}});
    return history;
}

void ChatSession::append(std::string user, std::string assistant) {
    turns_.push_back({std::move(user), std::move(assistant)});
}

void ChatSession::clear() { turns_.clear(); }
bool ChatSession::empty() const { return turns_.empty(); }
std::size_t ChatSession::size() const { return turns_.size(); }

void ChatSession::remove_oldest() {
    if (turns_.empty()) throw std::logic_error("Cannot trim an empty chat session");
    turns_.erase(turns_.begin());
}

}  // namespace local_llm
