# Shikai benchmark summary

Generated from raw C++ OpenVINO GenAI metrics.

Unavailable metrics are blank in CSV and shown as N/A here; means exclude them.


## Inference resources

CPU 100% means one logical CPU. RSS is sampled every 50 ms during generation; VmHWM is a process-lifetime peak.
GPU DRM counters are process-wide buffer allocations, not resident VRAM. System GPU buffers can overlap RAM/RSS. Engine percentages sum busy time and may exceed 100%. Missing counters are N/A.

| Setting | Workload | CPU time (ms) | CPU (%) | Sampled RSS peak (MiB) | GPU buffers (MiB) | GPU local buffers (MiB) |
|---|---|---:|---:|---:|---:|---:|
| CPU/int4 | performance | 7285.99 | 378.53 | 1958.57 | N/A | N/A |
| CPU/int4 | quality | 23083.82 | 368.07 | 1973.66 | N/A | N/A |
| GPU/int4 | performance | 4953.65 | 100.70 | 566.05 | 1254.00 | N/A |
| GPU/int4 | quality | 11843.06 | 100.84 | 353.59 | 1259.65 | N/A |

## CPU and GPU comparison

Same INT4 model, greedy decoding, prompt fixtures and response limits on each detected device. Quality uses one saved answer per case.

| Device | Performance tok/s | Performance TTFT (ms) | Quality /2 |
|---|---:|---:|---:|
| CPU | 17.98 | 199.54 | 1.17 |
| GPU | 8.84 | 1273.70 | 0.67 |
