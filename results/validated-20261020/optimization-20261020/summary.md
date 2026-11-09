# Shikai benchmark summary

Generated from raw C++ OpenVINO GenAI metrics.

Unavailable metrics are blank in CSV and shown as N/A here; means exclude them.


## Inference resources

CPU 100% means one logical CPU. RSS is sampled every 50 ms during generation; VmHWM is a process-lifetime peak.
GPU DRM counters are process-wide buffer allocations, not resident VRAM. System GPU buffers can overlap RAM/RSS. Engine percentages sum busy time and may exceed 100%. Missing counters are N/A.

| Setting | Workload | CPU time (ms) | CPU (%) | Sampled RSS peak (MiB) | GPU buffers (MiB) | GPU local buffers (MiB) |
|---|---|---:|---:|---:|---:|---:|
| cpu-4threads | performance | 10852.93 | 372.86 | 1974.81 | N/A | N/A |
| cpu-4threads | quality | 24618.11 | 365.21 | 1971.30 | N/A | N/A |
| cpu-4threads-f16 | performance | 11209.95 | 364.27 | 1979.36 | N/A | N/A |
| cpu-4threads-f16 | quality | 23462.21 | 359.28 | 1974.51 | N/A | N/A |
| cpu-4threads-u8 | performance | 13398.97 | 353.97 | 1975.02 | N/A | N/A |
| cpu-4threads-u8 | quality | 24961.59 | 350.38 | 1971.11 | N/A | N/A |
| cpu-runtime | performance | 10735.72 | 379.30 | 1974.64 | N/A | N/A |
| cpu-runtime | quality | 23914.63 | 351.62 | 1970.97 | N/A | N/A |

## Controlled CPU and KV-cache comparison

KV precision is the requested setting; auto leaves selection to OpenVINO. Quality is a small automatic rubric, not proof of equivalence.

| Profile | Performance tok/s | Performance TTFT (ms) | Quality /2 | Exact quality answers vs runtime |
|---|---:|---:|---:|---|
| cpu-4threads | 17.30 | 1102.86 | 1.17 | 6/6 |
| cpu-4threads-f16 | 16.82 | 1199.85 | 1.33 | 2/6 |
| cpu-4threads-u8 | 12.47 | 1229.95 | 1.17 | 6/6 |
| cpu-runtime | 17.76 | 1087.20 | 1.17 | 6/6 |
