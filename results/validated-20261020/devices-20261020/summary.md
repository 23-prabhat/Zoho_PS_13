# Shikai benchmark summary

Generated from raw C++ OpenVINO GenAI metrics.

Unavailable metrics are blank in CSV and shown as N/A here; means exclude them.


## Inference resources

CPU 100% means one logical CPU. RSS is sampled every 50 ms during generation; VmHWM is a process-lifetime peak.
GPU DRM counters are process-wide buffer allocations, not resident VRAM. System GPU buffers can overlap RAM/RSS. Engine percentages sum busy time and may exceed 100%. Missing counters are N/A.

| Setting | Workload | CPU time (ms) | CPU (%) | Sampled RSS peak (MiB) | GPU buffers (MiB) | GPU local buffers (MiB) |
|---|---|---:|---:|---:|---:|---:|
| CPU/int4 | performance | 6888.10 | 388.51 | 1958.74 | N/A | N/A |
| CPU/int4 | quality | 21116.71 | 390.03 | 1973.65 | N/A | N/A |

## CPU and GPU comparison

Same INT4 model, greedy decoding, prompt fixtures and response limits on each detected device. Quality uses one saved answer per case.

| Device | Performance tok/s | Performance TTFT (ms) | Quality /2 |
|---|---:|---:|---:|
| CPU | 19.34 | 169.34 | 1.17 |

## Errors and skipped comparisons

- GPU: error — 105 warnings generated. 15 warnings generated. 12 warnings generated. 105 warnings generated. 105 warnings generated. 105 warnings generated. 105 warnings generated. 105 warnings and 145 errors generated. 105 warnings generated. 149 warnings generated. shikai: Exception from src/inference/src/cpp/core.cpp:117: Exception from src/inference/src/dev/plugin.cpp:54: Check 'false' failed at src/plugins/intel_gpu/src/plugin/program_builder.cpp:168: [GPU] ProgramBuilder build failed! Exception from src/plugins/intel_gpu/src/runtime/ocl/ocl_kernel_builder.hpp:73: [GPU] clBuildProgram, error code: -11 CL_BUILD_PROGRAM_FAILURE
- GPU: error — 12 warnings generated. 105 warnings and 145 errors generated. 15 warnings generated. shikai: Exception from src/inference/src/cpp/core.cpp:117: Exception from src/inference/src/dev/plugin.cpp:54: Check 'false' failed at src/plugins/intel_gpu/src/plugin/program_builder.cpp:168: [GPU] ProgramBuilder build failed! Exception from src/plugins/intel_gpu/src/runtime/ocl/ocl_kernel_builder.hpp:73: [GPU] clBuildProgram, error code: -11 CL_BUILD_PROGRAM_FAILURE
