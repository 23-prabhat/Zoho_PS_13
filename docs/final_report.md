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

## Model, precision and hardware decisions

The checkpoint revision and hashes are pinned in [manifests](../models/manifests/README.md).
Optimum Intel/NNCF prepares INT4, INT8 and FP16 from the same checkpoint. CPU/INT4,
automatic threads/cache precision, one sequence and a 2048-token input/output budget
are the validated default. The 16 GB i5-13420H laptop workload measured 14.44 tokens/s
for INT4 versus 5.34 for FP16, with mean lifetime peak RSS 1961.95 versus 6291.66 MiB.
The separate CPU/Intel UHD study favored CPU decode speed; GPU remains experimental.

See [quantization](quantization.md), [environment](environment.md) and the
[benchmark report](benchmark_report.md) for methodology, sample counts and raw evidence.

## KV management and answer evaluation

Explicit scheduler controls expose bounded blocks or capacity, prefix reuse,
chunked prefill, precision requests and eviction. A separate native diagnostic
measures reservation; it does not infer cache size from RSS. Prefix reuse improves
matching-prefix follow-ups in recorded workloads; eviction may discard useful
context and does not reduce initial prefill by itself.

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

The solution covers the stated local-inference systems scope. Training, RAG,
persistent memory, speculative decoding and a GUI remain unimplemented extensions.
RTX model compilation failed on the tested stack; NPU and other platforms are
unvalidated. Laptop thermals/load and finite synthetic fixtures limit generalization.
