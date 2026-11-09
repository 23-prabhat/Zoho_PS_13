#include "local_llm/resource_profiler.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

int main() {
    namespace fs = std::filesystem;
    const auto temporary = fs::temp_directory_path() /
        ("shikai-fdinfo-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directory(temporary);
    try {
        const std::string client = "drm-driver: i915\ndrm-pdev: 0000:00:02.0\ndrm-client-id: 5\n"
            "drm-engine-render: 20000000 ns\ndrm-engine-capacity-render: 1\n"
            "drm-total-memory: 64 MiB\ndrm-resident-memory: 32 MiB\ndrm-total-local0: 128 KiB\n";
        std::ofstream(temporary / "1") << client;
        std::ofstream(temporary / "2") << client; // duplicated descriptor
        std::ofstream(temporary / "3") << "drm-driver: i915\ndrm-pdev: 0000:00:02.0\ndrm-client-id: 6\n"
            "drm-engine-render: 30000000 ns\ndrm-total-memory: 1024\n";
        const auto gpu = local_llm::read_gpu_usage(temporary);
        require(gpu.engine_ns && *gpu.engine_ns == 50000000, "DRM engine/client accounting is wrong");
        require(gpu.buffer_kib && *gpu.buffer_kib == 64 * 1024 + 128 + 1, "DRM allocation units or deduplication is wrong");
        require(gpu.system_kib && *gpu.system_kib == 64 * 1024 + 1, "GPU system buffers were misclassified");
        require(gpu.local_kib && *gpu.local_kib == 128, "GPU local buffers were misclassified");
        require(!local_llm::read_gpu_usage(temporary / "absent").buffer_kib, "Unavailable GPU data was reported as zero");

        local_llm::ResourceProfiler profiler(false, 5);
        std::vector<unsigned char> working_memory(4 * 1024 * 1024, 7);
        volatile std::size_t sum = 0;
        const auto until = std::chrono::steady_clock::now() + std::chrono::milliseconds(80);
        while (std::chrono::steady_clock::now() < until) sum += working_memory[sum % working_memory.size()];
        const auto usage = profiler.stop();
        require(usage.wall_ms >= 80 && usage.samples >= 3, "Resource sampler did not sample the work interval");
#ifdef __linux__
        require(usage.cpu_ms && *usage.cpu_ms > 0 && usage.cpu_percent && *usage.cpu_percent > 0,
                "CPU time/utilization was not measured");
        require(usage.sampled_peak_rss_kib && usage.rss_start_kib &&
                *usage.sampled_peak_rss_kib >= *usage.rss_start_kib, "Generation RSS peak was not retained");
#endif
        require(!usage.gpu_buffer_peak_kib && !usage.gpu_engine_percent, "CPU-only work invented GPU usage");
        require(profiler.stop().samples == usage.samples, "Profiler stop is not idempotent");
    } catch (const std::exception& error) {
        fs::remove_all(temporary);
        std::cerr << error.what() << '\n';
        return 1;
    }
    fs::remove_all(temporary);
    return 0;
}
