#pragma once

#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <mutex>
#include <optional>
#include <thread>

namespace local_llm {

struct GpuUsage {
    std::optional<std::uint64_t> engine_ns;
    std::optional<std::size_t> buffer_kib;
    std::optional<std::size_t> system_kib;
    std::optional<std::size_t> local_kib;
};

// Linux DRM client counters. Missing driver counters remain unavailable, not zero.
GpuUsage read_gpu_usage(const std::filesystem::path& fdinfo = "/proc/self/fdinfo");

struct ResourceUsage {
    double wall_ms = 0;
    std::optional<double> cpu_ms;
    std::optional<double> cpu_percent;  // 100% = one logical CPU; can exceed 100%.
    std::optional<std::size_t> rss_start_kib;
    std::optional<std::size_t> rss_end_kib;
    std::optional<std::size_t> sampled_peak_rss_kib;
    std::optional<std::size_t> gpu_buffer_peak_kib;
    std::optional<std::size_t> gpu_system_peak_kib;
    std::optional<std::size_t> gpu_local_peak_kib;
    std::optional<double> gpu_engine_percent; // Sum of engine busy times / wall time.
    std::size_t samples = 0;
    std::size_t interval_ms = 50;
};

class ResourceProfiler {
public:
    explicit ResourceProfiler(bool sample_gpu = false, std::size_t interval_ms = 50);
    ~ResourceProfiler();
    ResourceProfiler(const ResourceProfiler&) = delete;
    ResourceProfiler& operator=(const ResourceProfiler&) = delete;
    ResourceUsage stop();

private:
    void sample();
    bool sample_gpu_;
    bool stopped_ = false;
    std::chrono::steady_clock::time_point started_;
    std::optional<double> cpu_started_;
    std::optional<std::uint64_t> gpu_started_ns_;
    std::optional<std::uint64_t> gpu_latest_ns_;
    ResourceUsage usage_;
    std::mutex mutex_;
    std::condition_variable wake_;
    std::thread worker_;
};

} // namespace local_llm
