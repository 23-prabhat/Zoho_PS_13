#include "local_llm/metrics.hpp"

#include <fstream>
#include <cmath>
#include <sstream>
#include <string>

namespace local_llm {
namespace {
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
}  // namespace

GenerationMetrics collect_metrics(ov::genai::PerfMetrics& metrics, double load_ms,
                                  double wall_ms, std::size_t trimmed_turns,
                                  const ResourceUsage& resources) {
    const auto available = [](float value) -> std::optional<float> {
        return std::isfinite(value) && value >= 0 ? std::optional<float>(value) : std::nullopt;
    };
    const auto output_tokens = metrics.get_num_generated_tokens();
    auto throughput = available(metrics.get_throughput().mean);
    if (throughput && *throughput == 0) throughput.reset();
    // A single output token provides no interval between decoded tokens.
    return {load_ms, wall_ms, available(metrics.get_ttft().mean),
            output_tokens > 1 ? available(metrics.get_tpot().mean) : std::nullopt,
            output_tokens > 1 ? throughput : std::nullopt, metrics.get_num_input_tokens(),
            output_tokens, read_proc_kib("VmRSS:"),
            read_proc_kib("VmHWM:"), trimmed_turns, resources};
}

}  // namespace local_llm
