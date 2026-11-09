#include "local_llm/device_probe.hpp"

#include <openvino/openvino.hpp>

#include <iomanip>
#include <ostream>

namespace local_llm {
void DeviceProbe::print(std::ostream& output) {
    ov::Core core;
    for (const auto& device : core.get_available_devices()) {
        std::string full_name;
        try { full_name = core.get_property(device, ov::device::full_name); }
        catch (...) { full_name = "name unavailable"; }
        output << "  ● " << std::left << std::setw(8) << device << full_name << '\n';
        try {
            output << "      Device default KV-cache precision hint: "
                   << core.get_property(device, ov::hint::kv_cache_precision) << '\n';
        } catch (...) {
            output << "      Device default KV-cache precision hint: not queryable\n";
        }
    }
}
}  // namespace local_llm
