#pragma once

#include <openvino/genai/perf_metrics.hpp>
#include "local_llm/resource_profiler.hpp"

#include <cstddef>
#include <optional>

namespace local_llm {

struct GenerationMetrics {
    double load_ms = 0;
    double wall_ms = 0;
    std::optional<float> ttft_ms;
    std::optional<float> tpot_ms;
    std::optional<float> throughput;
    std::size_t input_tokens = 0;
    std::size_t output_tokens = 0;
    std::size_t rss_kib = 0;
    std::size_t peak_rss_kib = 0;
    std::size_t trimmed_turns = 0;
    ResourceUsage resources;
};

GenerationMetrics collect_metrics(ov::genai::PerfMetrics& metrics, double load_ms,
                                  double wall_ms, std::size_t trimmed_turns = 0,
                                  const ResourceUsage& resources = {});

}  // namespace local_llm
