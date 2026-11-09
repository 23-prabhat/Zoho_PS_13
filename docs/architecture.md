# Architecture

Shikai separates one-time preparation from offline C++ inference.

```text
Pinned Qwen checkpoint -> Optimum/NNCF exporter -> INT4 / INT8 / FP16 IR
                                                       |
Terminal -> CLI + JSON config -> ChatHistory/context guard
                                                       |
                         ov::genai::LLMPipeline -> OpenVINO -> CPU / Intel GPU
                                                       |
                   streamed text + metrics + benchmark CSV/charts
```

The deployed path is one native C++ process. It does not call Python, a Python
service, Hugging Face inference, or another hosted API. The tokenizer applies Qwen's
chat template. Shikai counts the fully formatted history, reserves output capacity,
and removes oldest complete turns when necessary.

The benchmark command keeps one pipeline loaded across prompts and repetitions.
Python only orchestrates C++ runs, combines CSV records, scores fixtures and draws
charts; it is not the inference implementation.

The executable entry point and command dispatch remain in `src/main.cpp`, while
reusable production logic is compiled into `shikai_core`: `ChatSession` owns committed
turns, `ContextPolicy` performs template-aware budget checks, `collect_metrics`
combines GenAI and Linux measurements, `ModelRegistry` validates local artifacts, and
`DeviceProbe` enumerates OpenVINO devices.

`ResourceProfiler` samples process RSS and optional Linux DRM allocations in a
background thread during generation and records process CPU time. Python adds
optional PID-matched NVIDIA monitoring around a benchmark child process; that
includes loading/warmup and is separate from the native generation interval.

Pipeline construction uses an explicit `SchedulerConfig`. The default is one active
sequence, prefix caching off, eviction off, and dynamic cache allocation. Thread count,
fixed cache size, prefix reuse, and eviction are selectable through JSON or CLI and
printed at startup, so benchmark policy is visible.

November update: block-level KV capacity, prefill chunk size, U4 precision and eviction
areas are configurable. The opt-in prefix profile releases its pipeline on /reset.
The cache-probe command uses ContinuousBatchingPipeline with the same scheduler and
device-property builders to report reserved cache bytes and usage percentages.
See the [KV guide](../guides/kv-cache.md) and [November evidence](../results/validated-20261107/README.md) for measurements.

## Evaluation and release boundaries

The strict evaluator checks full answers, typed JSON and numeric units and keeps
execution failures separate from model failures. Cache screening requires complete
fixture/turn coverage, valid timing and preserved baseline passes. Baseline reuse
checks prompt/binary/model/manifest identity and runtime settings even under Python
optimization; allocation-probe failures cause a nonzero status.

The publication tool and submission packager share an explicit list of public
source and technical docs. Private docs/submission authoring is excluded. The ZIP
records source-commit identity and per-entry hashes and runs the Python tests on
extracted source. [Release scope](../guides/github-release.md) describes the boundary.
