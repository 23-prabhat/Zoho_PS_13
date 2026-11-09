#include "local_llm/resource_profiler.hpp"

#include <algorithm>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

#ifdef __linux__
#include <time.h>
#endif

namespace local_llm {
namespace {
std::optional<double> process_cpu_ms() {
#ifdef __linux__
    timespec time{};
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &time) == 0)
        return time.tv_sec * 1000.0 + time.tv_nsec / 1000000.0;
#endif
    return std::nullopt;
}

std::optional<std::size_t> process_rss_kib() {
    std::ifstream status("/proc/self/status");
    std::string line;
    while (std::getline(status, line)) {
        if (line.rfind("VmRSS:", 0) != 0) continue;
        std::istringstream values(line.substr(6));
        std::size_t kib;
        if (values >> kib) return kib;
    }
    return std::nullopt;
}

template <typename T>
void retain_peak(std::optional<T>& peak, const std::optional<T>& current) {
    if (current) peak = peak ? std::max(*peak, *current) : *current;
}

void add(std::optional<std::size_t>& total, std::size_t value) {
    total = total.value_or(0) + value;
}
} // namespace

GpuUsage read_gpu_usage(const std::filesystem::path& fdinfo) {
    GpuUsage result;
    std::set<std::string> clients;
    std::error_code error;
    std::filesystem::directory_iterator files(fdinfo, error);
    const std::filesystem::directory_iterator end;
    for (; !error && files != end; files.increment(error)) {
        std::ifstream input(files->path());
        std::map<std::string, std::string> fields;
        std::string line;
        while (std::getline(input, line)) {
            const auto colon = line.find(':');
            if (colon != std::string::npos && line.rfind("drm-", 0) == 0)
                fields[line.substr(0, colon)] = line.substr(colon + 1);
        }
        if (!fields.count("drm-driver") || !fields.count("drm-client-id")) continue;
        // Duplicated descriptors refer to the same client and must not be summed twice.
        const auto key = fields["drm-driver"] + fields["drm-pdev"] + fields["drm-client-id"];
        if (!clients.insert(key).second) continue;
        for (const auto& [name, text] : fields) {
            std::istringstream value(text);
            std::uint64_t number;
            std::string unit;
            if (!(value >> number)) continue;
            value >> unit;
            if (name.rfind("drm-engine-", 0) == 0 && unit == "ns") {
                result.engine_ns = result.engine_ns.value_or(0) + number;
            } else if (name.rfind("drm-total-", 0) == 0 && name.rfind("drm-total-cycles-", 0) != 0) {
                if (unit == "MiB") number *= 1024;
                else if (unit.empty()) number /= 1024;
                else if (unit != "KiB") continue;
                add(result.buffer_kib, number);
                const auto region = name.substr(10);
                if (region == "memory" || region.rfind("system", 0) == 0)
                    add(result.system_kib, number);
                if (region.rfind("local", 0) == 0 || region.rfind("vram", 0) == 0)
                    add(result.local_kib, number);
            }
        }
    }
    return result;
}

ResourceProfiler::ResourceProfiler(bool sample_gpu, std::size_t interval_ms)
    : sample_gpu_(sample_gpu), started_(std::chrono::steady_clock::now()), cpu_started_(process_cpu_ms()) {
    if (interval_ms == 0) throw std::invalid_argument("Sampling interval must be positive");
    usage_.interval_ms = interval_ms;
    usage_.rss_start_kib = process_rss_kib();
    if (sample_gpu_) gpu_started_ns_ = read_gpu_usage().engine_ns;
    sample();
    worker_ = std::thread([this] {
        std::unique_lock<std::mutex> lock(mutex_);
        while (!wake_.wait_for(lock, std::chrono::milliseconds(usage_.interval_ms), [this] { return stopped_; })) {
            lock.unlock();
            sample();
            lock.lock();
        }
    });
}

ResourceProfiler::~ResourceProfiler() { stop(); }

void ResourceProfiler::sample() {
    retain_peak(usage_.sampled_peak_rss_kib, process_rss_kib());
    if (sample_gpu_) {
        const auto gpu = read_gpu_usage();
        retain_peak(usage_.gpu_buffer_peak_kib, gpu.buffer_kib);
        retain_peak(usage_.gpu_system_peak_kib, gpu.system_kib);
        retain_peak(usage_.gpu_local_peak_kib, gpu.local_kib);
        retain_peak(gpu_latest_ns_, gpu.engine_ns);
    }
    ++usage_.samples;
}

ResourceUsage ResourceProfiler::stop() {
    const auto ended = std::chrono::steady_clock::now();
    const auto cpu_ended = process_cpu_ms();
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (stopped_) return usage_;
        stopped_ = true;
    }
    wake_.notify_one();
    if (worker_.joinable()) worker_.join();
    sample();
    usage_.rss_end_kib = process_rss_kib();
    retain_peak(usage_.sampled_peak_rss_kib, usage_.rss_start_kib);
    retain_peak(usage_.sampled_peak_rss_kib, usage_.rss_end_kib);
    usage_.wall_ms = std::chrono::duration<double, std::milli>(ended - started_).count();
    if (cpu_started_ && cpu_ended && *cpu_ended >= *cpu_started_) {
        usage_.cpu_ms = *cpu_ended - *cpu_started_;
        if (usage_.wall_ms > 0) usage_.cpu_percent = 100.0 * *usage_.cpu_ms / usage_.wall_ms;
    }
    if (gpu_started_ns_ && gpu_latest_ns_ && *gpu_latest_ns_ >= *gpu_started_ns_ && usage_.wall_ms > 0)
        usage_.gpu_engine_percent = (*gpu_latest_ns_ - *gpu_started_ns_) / (usage_.wall_ms * 10000.0);
    return usage_;
}
} // namespace local_llm
