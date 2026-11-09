# Shikai: complete project summary

Shikai implements SETU software problem **SWFW_5S_13, Local LLM on OpenVINO**.
It runs Qwen2.5-1.5B-Instruct from local model and tokenizer files through the
OpenVINO GenAI **C++17** API. The model card lists 1.54 billion parameters, within
the specified 1–3 billion range. Inference requires neither a hosted model nor an
API key. Initial dependency/model downloads require internet access.

## Problem and purpose

The task is a local inference systems project: deploy a small language model,
understand inference, quantization and KV caching, and measure hardware use and
performance. Shikai turns those requirements into an executable application,
inspectable experiments and a reproducible submission. It does not train a model
or claim that all of the pretrained model's answers are correct.

## Everything implemented and why it is needed

| Implementation | Purpose and necessity | Main location |
|---|---|---|
| Native OpenVINO inference | Satisfies the required C++ backend and executes the local model. | `src/main.cpp`, `CMakeLists.txt` |
| Qwen2.5-1.5B-Instruct | Supplies an instruction model within the required size range that fits the test laptop after compression. | `models/manifests/` |
| Pinned checkpoint downloader | Fixes model identity across comparisons; checks the downloaded checkpoint SHA-256. | `scripts/download_model.py` |
| INT4, INT8 and FP16 exports | Compare storage, decode speed, RAM and answer behavior using one checkpoint. | `scripts/export_models.sh` |
| Model/tokenizer verifier | Detects missing or modified IR assets before interpreting an experiment as reproducible. | `scripts/verify_model.py` |
| Streaming terminal chat | Makes incremental output usable without waiting for a whole answer. | `run_chat` |
| Complete-turn session history | Allows follow-up questions while preserving user/assistant ordering. History is session-local. | `src/chat_session.cpp` |
| Template-aware context guard | Counts actual formatted tokens and reserves output capacity rather than estimating text by characters. | `src/context_policy.cpp` |
| Oldest-turn trimming | Keeps history within the configured budget while retaining recent complete dialogue. | `run_chat` |
| Candidate history before commit | Prevents rejection or cancellation from silently destroying previously committed conversation. | `run_chat` |
| Ctrl+C cancellation | Stops generation; chat can recover, and single-prompt generation returns status 130. | Streaming callbacks |
| `/help`, `/stats`, `/reset`, `/exit` | Expose controls, measurements, session clearing and clean termination. Prefix reset rebuilds its pipeline. | `src/main.cpp` |
| Single-prompt and file input | Supports demonstrations, shell use and repeatable prompts without interactive input. | `run_generate` |
| JSON configuration and CLI overrides | Keep experimental profiles explicit while allowing one setting to be changed for comparison. | `configs/`, option parsing |
| Argument/configuration checks | Reject invalid limits, ambiguous prompt inputs and incompatible cache options with actionable errors. | `parse_options`, `apply_config` |
| Device discovery | Distinguishes detected OpenVINO devices from successful, validated inference. | `src/device_probe.cpp` |
| Token/load/latency measurements | Separate model loading, first-token latency, inter-token timing and decode throughput. | `src/metrics.cpp` |
| CPU and RSS sampler | Measures generation CPU time and process RAM to explain hardware requirements and use. | `src/resource_profiler.cpp` |
| Optional GPU monitoring | Records available Linux DRM buffers/engine work and NVIDIA counters without inventing missing data. | Resource profiler, `scripts/gpu_monitor.py` |
| Bounded KV block pool or GB pool | Exposes explicit runtime cache reservation for controlled experiments. | `SchedulerConfig`, cache profiles |
| Prefix caching | Reuses matching computed prefixes to reduce repeated prefill work; remains opt-in. | Prefix profiles |
| KV precision requests | Separately studies cache precision and weight compression; support is device dependent. | Pipeline device properties |
| Chunked prefill and eviction | Exposes scheduler trade-offs and attention-state retention limits. Eviction may lose useful context. | Scheduler/eviction configuration |
| Direct native cache probe | Measures diagnostic allocated bytes and usage rather than treating RSS as cache size. | `run_cache_probe` |
| JSONL benchmark runner and CSV output | Saves prompts, answers, repetitions, warmups and effective settings for inspection. | `run_benchmark`, `scripts/run_benchmarks.py` |
| Whole-conversation benchmarks | Separates cold first-turn latency from follow-up latency in fresh processes. | `scripts/benchmark_kv.py`, `scripts/tune_kv_cache.py` |
| Hardware probe and charts | Records the machine and visualizes precision, context, threads and device comparisons. | `scripts/probe_hardware.py`, `scripts/plot_results.py` |
| Strict versioned answer checks | Measures complete-response compliance, typed JSON, numeric units, facts and recall with declared expected answers. | `scripts/answer_quality.py`, `benchmarks/quality_strict_v1.jsonl` |
| Saved-answer re-scoring | Makes grader decisions reproducible without paying the cost of another model run. | `scripts/evaluate_quality.py --rescore` |
| Quality-aware cache screening | Rejects candidates that lose baseline passes or fail declared latency/coverage checks; exposes measured trade-offs. | `scripts/tune_kv_cache.py` |
| Isolated reproduction workflow | Rebuilds from a source snapshot, verifies inputs, re-exports INT4 and proves local generation from the new artifacts. | `scripts/validate_reproduction.py` |
| Offline enforcement test | Uses kernel network denial and checks TCP/UDP denial before three turns; environment flags alone are insufficient proof. | `tests/offline_test.py` |
| Native and Python regressions | Check actual state transitions, failure handling, measurements, grading and publication boundaries. | `tests/` |
| CI definition | Automates model-free source checks/builds without committing model weights. Hosted execution is a separate result. | `.github/workflows/ci.yml` |
| Checksum-pinned SDK bootstrap | Selects the tested native runtime and detects corrupt downloads; supports verified cache reuse. | `scripts/setup_cpp_runtime.sh` |
| Offline launcher | Selects the matching SDK/configuration and forces model-hub offline flags. | `scripts/shikai` |
| Optional Intel GPU setup | Provides project-local Fedora userspace libraries for the recorded Intel experiment. | `scripts/setup_gpu_runtime.sh` |
| Public-source inventory | Selects source/evidence and detects disallowed paths or obvious secrets before publication. | `scripts/check_public_files.py` |
| Verified submission ZIP | Includes the PDF, source and reviewed evidence, checks every entry hash and tests extracted scripts. | `scripts/package_submission.py` |
| Third-party notices | Preserves upstream model/runtime license obligations and attribution. | `third_party/`, `THIRD_PARTY_NOTICES.md` |
| Professional report | Explains method, theory, specifications, setup, diagrams, results, screenshots and limitations in the required format. | College submission PDF |

## How a request works

1. The launcher loads the matching native SDK environment and default profile.
2. The C++ program validates options and required local model/tokenizer assets.
3. OpenVINO loads/compiles the selected IR model for CPU or the selected device.
4. Shikai combines committed turns with the new prompt and applies the model's
   chat template. It counts formatted input tokens and reserves the output budget.
5. Chat removes oldest complete turns from a candidate if needed. An oversized
   latest prompt is rejected while committed history remains intact.
6. Prefill computes attention state for the prompt. Decode predicts tokens one
   at a time, reusing prior keys/values. The streamer displays incremental text.
7. The profiler measures generation CPU time and samples memory while it runs.
8. On success, chat commits the candidate turn and exposes statistics. On
   cancellation, the interrupted turn is discarded. Benchmark mode saves rows
   and answers; Python adds provenance and produces comparison reports.

## Key technical distinctions for the viva

- **Weights** are pretrained parameters. **KV state** is attention data computed
  for tokens. **Chat history** is text assembled by the application. These are
  different objects with different lifetimes.
- INT4 describes compressed weights, not every operation, activation or cache
  element. A requested cache type is not proof of the compiled element layout.
- Prefill depends strongly on input length; decode produces one output token per
  step. TTFT and steady decode rate answer different performance questions.
- For this model, the theoretical FP16 KV payload is
  `2 × 28 layers × tokens × 2 KV heads × 128 head dimension × 2 bytes`:
  **28 KiB/token**, or **56 MiB at 2048 tokens**, before allocation overhead.
- The application's 2048-token budget is a deliberate local policy. It is not a
  claim that the upstream model supports only 2048 tokens.
- Process RSS includes weights and many runtime allocations. Cache reservation
  includes free blocks. Intel shared GPU buffers are not dedicated VRAM. Do not
  add overlapping counters to claim total physical memory savings.
- CPU utilization uses 100% for one logical CPU, so a multithreaded process can
  exceed 100%. This is not electrical power or energy consumption.
- Prefix caching reuses matching beginnings. Eviction discards attention blocks
  during generation; it does not reduce initial prefill by itself.

## Measured evidence and decisions

The recorded machine is an Intel Core i5-13420H laptop with 16 GB RAM, Intel UHD
graphics and an NVIDIA RTX 3050. The validated software uses Linux x86-64,
OpenVINO 2026.4.1, GenAI/Tokenizers 2026.4.1.0 and Python 3.14 for preparation.
See the environment records for exact kernel/compiler versions by study date.

The October precision workload used three prompts, five measured repetitions per
precision, one warmup per prompt and up to 128 output tokens:

| Weight format | Mean decode rate | Mean process-lifetime peak RSS |
|---|---:|---:|
| INT4 | 14.44 tokens/s | 1961.95 MiB |
| INT8 | 9.62 tokens/s | 3113.25 MiB |
| FP16 | 5.34 tokens/s | 6291.66 MiB |

INT4 delivered about **2.71× the FP16 decode rate** and **68.8% lower mean peak
RSS** in this workload. This supports CPU/INT4/automatic KV as the default on the
test laptop. The measurements do not establish equal answer quality.

The separate Intel UHD workload measured 8.84 tokens/s on GPU and 17.98 on CPU.
GPU execution lowered CPU work but did not improve decode speed here. NVIDIA
model-kernel compilation failed on the tested stack. GPU remains experimental;
successful RTX/NPU inference is not claimed.

The 7 November strict comparison contained 22 objective tasks and two saved
explanations per profile. INT4/auto passed 7/22; INT8/auto, FP16/auto and
FP16/FP16-cache passed 9/22 each. All four exact long-context tasks failed in all
four profiles. Formatting is part of these checks; this is not general accuracy.
The open-ended explanations remain pending independent review.

The exploratory cache study measured 104.22 ms mean follow-up TTFT for a 64-block
automatic prefix pool versus 1363.13 ms baseline. Its separate cache diagnostic
reserved 32.38 MiB versus 64.75 MiB for 128 blocks. U4 reserved 73.50 MiB and
passed more declared checks. These are distinct trade-offs. Short synthetic
conversations and uncontrolled laptop conditions limit generalization.

## Final review and fixes on 9 November 2026

- All **28 CTest cases passed**, with zero failures and zero skips, including real
  INT4 inference, cancellation, context behavior and enforced offline operation.
- All **43 model-free Python tests passed**. Five new regressions cover incomplete
  comparisons, invalid timing, stale baseline provenance and allocation-probe
  success/failure handling. Quality tests also passed with Python optimization.
- Baseline reuse now checks model/prompt/binary/manifest identity, greedy decoding
  and all recorded comparison settings using ordinary exceptions, so `python -O`
  cannot remove validation.
- Cache screening requires complete fixture/turn coverage. Invalid or nonfinite
  timings cannot qualify a candidate. Failed/missing allocation diagnostics cause
  a nonzero overall run status and retain a diagnostic log.
- Source checkpoint and INT4/INT8/FP16 IR checksums were verified; historical
  evidence was preserved. No new performance figures were invented.
- Private report authoring is ignored consistently with the publication allowlist.
  Public source includes this explanation; student details remain in the ZIP.
- The PDF tables have visible cell boundaries, wrapped headers, fixed widths and
  repeating header rows. The final PDF is rendered and checked before packaging.
- The first clean Ubuntu CI build exposed a missing OpenCL ICD loader. The SDK
  links `libOpenCL.so.1` even in CPU mode. CI now installs `ocl-icd-libopencl1`, and
  setup documents that dependency (`ocl-icd` on Fedora) separately from GPU drivers.

The new evidence is in `results/validated-20261109/`; earlier snapshots retain
their original methods, timestamps, results and hashes.

## Demonstration and reproduction

After the README setup, run from the repository root:

```bash
./scripts/shikai devices
./scripts/shikai generate --prompt "Explain local inference in two sentences."
./scripts/shikai chat --max-new-tokens 48
# In chat: ask a short question, ask a follow-up, /stats, /reset, /stats, /exit.
.venv/bin/ctest --preset release
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python scripts/evaluate_quality.py --output results/my-strict-run
```

The strict run generates real answers and can contain failed model answers without
an execution failure. Use a new output directory for each run. For measured prefix
reuse, select `configs/cpu-prefix-small.json`; inspect quality as well as latency.

## Submission and boundaries

The college upload is **PRABHAT-JHA_SWFW_5S_13_PROJECT-FILES.zip**, containing the
named PDF and complete additional source/evidence files. The PDF includes student
details, project details, work done, real screenshots, system/model information,
setup, architecture, benchmark tables/figures, citations and known limitations.
The ZIP includes a per-entry SHA-256 manifest and excludes downloaded weights,
SDKs, environments, credentials and build products. README setup recreates assets.

Persistent memory, RAG, model training/fine-tuning, speculative decoding and a GUI
are not implemented. They are not mandatory for the selected problem. The project
demonstrates local inference engineering and measured trade-offs; model correctness
and support on other devices require separate validation.

Research sources and their relationship to the implementation are documented in
[research-notes.md](research-notes.md). Setup is in [README.md](../README.md).
