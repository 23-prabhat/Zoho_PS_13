#pragma once

#include <iosfwd>

namespace local_llm {
class DeviceProbe {
public:
    static void print(std::ostream& output);
};
}  // namespace local_llm
