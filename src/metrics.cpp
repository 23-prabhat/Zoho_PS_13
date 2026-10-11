#include "local_llm/metrics.hpp"

#include <fstream>
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
                                  double wall_ms, std::size_t trimmed_turns) {
    return {load_ms, wall_ms, metrics.get_ttft().mean, metrics.get_tpot().mean,
            metrics.get_throughput().mean, metrics.get_num_input_tokens(),
            metrics.get_num_generated_tokens(), read_proc_kib("VmRSS:"),
            read_proc_kib("VmHWM:"), trimmed_turns};
}

}  // namespace local_llm
