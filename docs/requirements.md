# Requirement traceability

Selected problem: **SWFW_5S_13, Local LLM on OpenVINO**. The supplied statement
requires a 1–3B model running locally through OpenVINO GenAI C++, with understanding
of inference, quantization, KV management and hardware/performance factors.

| Requirement | Implementation | Evidence |
|---|---|---|
| Local 1–3B model | Qwen2.5-1.5B-Instruct, 1.54B total parameters | [Pinned manifests](../models/manifests/README.md) |
| OpenVINO GenAI C++ backend | C++17 LLMPipeline; native cache diagnostic | [Architecture](architecture.md), [build](../CMakeLists.txt) |
| Entirely local inference | Local model/tokenizer files; offline launcher | [Kernel-enforced three-turn test](../results/validated-20261109/verification/offline.json) |
| Inference and quantization | Prefill/decode explanation; INT4/INT8/FP16 comparisons | [Quantization](quantization.md), [benchmark report](benchmark_report.md) |
| Hardware requirements and utilization | CPU/RAM/GPU records, CPU time, sampled RSS, runtime timing | [Environment](environment.md), [profiling guide](../guides/hardware-and-benchmarks.md) |
| KV-cache management | Bounded pools, precision requests, prefix reuse, chunking, eviction and probes | [KV cache](kv_cache.md), [strict cache evidence](../results/validated-20261107/kv/summary.md) |
| Reproduction and reliability | Pinned inputs, export/build, state/cancellation tests, offline enforcement | [Final validation](../results/validated-20261109/README.md), [isolated reproduction](../results/validated-20261107/reproduction/summary.json) |

All stated systems requirements are covered. This does not certify arbitrary
model answers. A GUI, model training, RAG, persistent memory, cloud deployment and
successful NVIDIA/NPU inference are not required by the selected baseline.

The separate college PDF includes student/project details, work done, screenshots,
system/model specifications, setup and benchmark statistics in the prescribed format.
