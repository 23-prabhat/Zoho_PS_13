# Shikai benchmark summary

Generated from raw C++ OpenVINO GenAI metrics.

Unavailable metrics are blank in CSV and shown as N/A here; means exclude them.

## Precision performance

| Precision | Mean TTFT (ms) | Mean throughput (tok/s) | Mean peak RSS (MiB) |
|---|---:|---:|---:|
| INT4 | 675.80 | 15.12 | 1957.17 |
| INT8 | 657.00 | 10.45 | 3110.78 |
| FP16 | 2022.74 | 4.64 | 5237.00 |


## Inference resources

CPU 100% means one logical CPU. RSS is sampled every 50 ms during generation; VmHWM is a process-lifetime peak.
GPU DRM counters are process-wide buffer allocations, not resident VRAM. System GPU buffers can overlap RAM/RSS. Engine percentages sum busy time and may exceed 100%. Missing counters are N/A.

| Setting | Workload | CPU time (ms) | CPU (%) | Sampled RSS peak (MiB) | GPU buffers (MiB) | GPU local buffers (MiB) |
|---|---|---:|---:|---:|---:|---:|
| CPU/fp16 | performance | 4661.59 | 306.70 | 5237.01 | N/A | N/A |
| CPU/int4 | performance | 2738.17 | 354.03 | 1957.17 | N/A | N/A |
| CPU/int8 | performance | 1696.16 | 298.97 | 3110.78 | N/A | N/A |
