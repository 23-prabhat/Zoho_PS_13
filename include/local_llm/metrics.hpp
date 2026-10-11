#pragma once

#include <openvino/genai/perf_metrics.hpp>

#include <cstddef>

namespace local_llm {

struct GenerationMetrics {
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

GenerationMetrics collect_metrics(ov::genai::PerfMetrics& metrics, double load_ms,
                                  double wall_ms, std::size_t trimmed_turns = 0);

}  // namespace local_llm
