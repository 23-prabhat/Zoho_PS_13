# Shikai: public technical project report

This is the public technical summary for **SWFW_5S_13, Local LLM on OpenVINO**,
updated 9 November 2026. The separate college submission PDF carries student details
and the prescribed cover; it is distributed in the submission ZIP.

## Objective and implementation

Shikai runs Qwen2.5-1.5B-Instruct locally through OpenVINO GenAI C++17. Its 1.54B
parameters satisfy the 1–3B requirement. Local IR/tokenizer files support inference
without a hosted service or API key after preparation downloads.

The native application implements streaming chat, single-prompt/file generation,
JSON/CLI profiles, device discovery, benchmark CSV and a direct cache diagnostic.
Chat templates determine actual token counts; output capacity is reserved before
execution. Candidate history permits complete-turn trimming while preserving
committed history on rejected or cancelled requests. Reset clears session state
and rebuilds a prefix-enabled pipeline.

CPU time, sampled process RSS, lifetime RSS peaks and runtime token/latency metrics
explain hardware use. Optional GPU counters remain unavailable when not exposed.
Weights, KV tensors, transcript text, cache reservation and RSS are distinct concepts.

[Architecture](architecture.md) and the [feature-purpose guide](../guides/project-summary.md)
explain every material implementation and why it is needed.

## Why C++ and Python both belong in this solution

Problem 13 explicitly requires the **OpenVINO GenAI C++ API**. C++17 is the deployed
backend: local model loading, streaming generation, conversation ownership,
context/cache controls, cancellation, device discovery and runtime measurements.
Python handles the preparation ecosystem (download, conversion and compression)
and repeatable evaluation of the native child process. It is not an inference
service in the deployed path. This split satisfies the required backend while
making assets and experiments reproducible; no language-speed comparison is claimed.

Hugging Face Hub/Transformers identify and load the source model; CPU PyTorch and
Optimum Intel export it; NNCF compresses weights. OpenVINO GenAI C++ generates text,
Runtime executes the network and OpenVINO Tokenizers handles local text/token
conversion. CMake/Ninja/GCC build it, Bash launches it, and CTest/unittest/CI verify
it. [Technology responsibilities](../guides/technology-and-delivery.md) distinguish
direct project features from transitive and report-production dependencies.

## Model, precision and hardware decisions

The checkpoint revision and hashes are pinned in [manifests](../models/manifests/README.md).
Optimum Intel/NNCF prepares INT4, INT8 and FP16 from the same checkpoint. CPU/INT4,
automatic threads/cache precision, one sequence and a 2048-token input/output budget
are the validated default. The 16 GB i5-13420H laptop workload measured 14.44 tokens/s
for INT4 versus 5.34 for FP16, with mean lifetime peak RSS 1961.95 versus 6291.66 MiB.
The separate CPU/Intel UHD study favored CPU decode speed; GPU remains experimental.

| Measured resource | INT4 | INT8 | FP16 |
|---|---:|---:|---:|
| Export directory, decimal GB | 0.94 | 1.57 | 3.11 |
| Mean process-lifetime peak RAM, decimal GB | 2.06 | 3.26 | 6.60 |
| CPU decode rate, tokens/s | 14.4 | 9.6 | 5.3 |

GB means 10^9 bytes; the RAM row converts the original MiB measurements. These are
observed process peaks in the 15-row precision study, not minimum installed RAM.
Recommended host: the validated i5-13420H-class x86-64 CPU with **16 GB RAM**, Linux
and the pinned native SDK; allow OS/context headroom and additional setup disk space.
The optional Intel UHD/iGPU needs its matching driver/runtime and shares system RAM.

INT4 remains the footprint/speed default, with an explicit quality cost: **7/22**
strict passes versus **9/22** for INT8/FP16. It answered `17 + 25` with `32`, while
the others answered `42`. **INT8 is the quality-leaning alternative**: it retained
the FP16 fixture passes with less memory and faster decode. The unrounded precision
means give 14.44062 / 5.3376006667 = 2.70545, correctly reported as **2.71×**.

See [quantization](quantization.md), [environment](environment.md) and the
[benchmark report](benchmark_report.md) for methodology, sample counts and raw evidence.

## KV management and answer evaluation

Explicit scheduler controls expose bounded blocks or capacity, prefix reuse,
chunked prefill, precision requests and eviction. A separate native diagnostic
measures reservation; it does not infer cache size from RSS. Prefix reuse improves
matching-prefix follow-ups in recorded workloads; eviction may discard useful
context and does not reduce initial prefill by itself.

The 3 November three-turn study reduced follow-up TTFT from **3821.68 to 236.79 ms**
(about **16.1×**) with prefix-128, while cold TTFT stayed near **6.1 s**. Separate
allocation diagnostics measured **32.38 MiB for 64 blocks**, **64.75 MiB for 128**
and **1023.86 MiB for a 1 GB requested pool**. U4/128 reserved **73.50 MiB**, more
than automatic cache; it offers a different measured quality/memory trade-off.
Eviction showed no clear benefit in the retained latency/quality experiments.
The 64-block result is from the later November 7 study; workloads and absolute
timings from the two studies are kept separate in the [KV guide](../guides/kv-cache.md).

The versioned strict suite has 22 objective fixtures and two explanation answers.
INT4/auto passed 7/22; the three tested INT8/FP16 alternatives passed 9/22. All four
exact long-context fixtures failed in every weight profile. Formatting is part of
these checks; scores are not general accuracy. Open-ended answers await review.
Cache candidates must preserve baseline passes, cover the same cases/turns and
satisfy declared timing rules. Provenance mismatches and probe failures are errors.

[KV documentation](kv_cache.md) and [evaluation methods](../guides/answer-quality.md)
retain the measured choices and their limits.

## Verification and reproducibility

The final laptop validation passed **28/28 CTest cases**, zero failures/skips,
and **43 Python tests**. The three-turn offline test verifies TCP/UDP socket denial
before generation under inherited kernel enforcement. Isolated reproduction also
validated a new INT4 export, source build and offline inference, with fresh/cached
input origins recorded explicitly. The clean Ubuntu CI workflow installs the native
OpenCL loader and validates compilation plus model-free tests.

[Validation logs](../results/validated-20261109/README.md),
[isolated reproduction](../results/validated-20261107/reproduction/summary.json),
[CI](../.github/workflows/ci.yml) and [research notes](../guides/research-notes.md)
provide supporting evidence. The submission packager verifies every entry hash,
records source-commit identity and runs Python tests against extracted source.

## Reproduce and demonstrate

Follow [README setup](../README.md), then use the [demonstration checklist](demo_checklist.md).
The SDK requires `libOpenCL.so.1` even for CPU mode. Models, SDKs, environments and
build products are recreated locally rather than committed.

## Limitations

Current totals are **28 CTest and 43 Python tests**. October's 22 CTest passes
(one skip) and November 7's 38 Python tests are historical snapshots.
The solution covers the stated local-inference systems scope. Training, RAG,
persistent memory, speculative decoding and a GUI remain unimplemented extensions.
The bundled OpenVINO GPU plugin targets Intel integrated/discrete hardware;
RTX 3050 is outside its supported target list. Its retained compilation failure
documents an unsupported-target attempt, rather than a supported NVIDIA benchmark.
This interpretation follows the official [GPU guide](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/gpu-device.html)
and [supported hardware list](https://docs.openvino.ai/2026/about-openvino/release-notes-openvino/system-requirements.html),
checked 9 November 2026. Device enumeration alone does not establish supported model execution.
NPU and other platforms remain unvalidated. Laptop thermals/load and finite
synthetic fixtures limit generalization; RSS, reserved cache and shared GPU buffers
are distinct accounting categories. No electrical-power savings are measured.
