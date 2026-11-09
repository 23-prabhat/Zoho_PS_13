# Shikai — Offline LLM inference in C++

![Shikai folded S identity](assets/brand/shikai-lockup.svg)

Shikai runs **Qwen2.5-1.5B-Instruct locally** through the OpenVINO GenAI C++ API.
It provides a streaming terminal chat application and a benchmark harness for
comparing model precision, context length, CPU threading and GPU execution.

Reusable vector, transparent PNG and terminal versions are in the [brand asset kit](assets/brand/README.md).

For a complete explanation of each feature, its purpose, the execution flow and
the measured decisions, read the [project summary](guides/project-summary.md).
The [research notes](guides/research-notes.md) connect primary sources to the implementation.

The deployed application is C++17. Python prepares the model and produces benchmark
reports. After the initial downloads and export, inference works offline without
an API key or a hosted inference service.

## What it does

- Streams responses in interactive chat and single-prompt generation modes.
- Keeps bounded conversation history, trims complete turns, and preserves committed
  history when a prompt is rejected or generation is cancelled.
- Reports token latency, throughput, process RAM and CPU use, with optional Linux
  GPU counters when available.
- Supports INT4, INT8 and FP16 exports with pinned source provenance and SHA-256
  verification.
- Saves benchmark measurements, generated answers and run metadata for inspection.

**CPU with INT4 is the validated default.** Intel GPU inference is experimental;
GPU compatibility and answer quality depend on the device and driver. Conversation
memory lasts for the current session; persistent memory and retrieval are not
implemented.

## Setup and first run

### 1. Check prerequisites and clone

The tested environment is **Linux x86-64, Fedora 44, CPython 3.14.8**, a C++17
compiler and OpenVINO 2026.4.1. The bootstrap downloads Intel's Ubuntu 24 x86-64 SDK;
it also worked on the tested Fedora host. Other distributions require compatible
system libraries. Windows, macOS and ARM builds have not been validated.

Install Git, Bash, Python **3.14** with `venv` support, a C++17 compiler (`g++` or
`clang++`), `curl`, `tar`, and standard Linux tools including `sha256sum` and
`readlink`. CMake and Ninja are installed in the next step. A GPU is optional.

The SDK also links to the **OpenCL ICD loader (`libOpenCL.so.1`) even in CPU mode**.
Install `ocl-icd-libopencl1` on Ubuntu 24.04 or `ocl-icd` on Fedora if it is missing:

```bash
# Ubuntu 24.04
sudo apt-get update
sudo apt-get install --yes --no-install-recommends ocl-icd-libopencl1
# Fedora alternative: sudo dnf install ocl-icd
```

The loader alone does not enable GPU inference; CPU use needs no GPU driver setup.

The validation laptop has 16 GB RAM; INT4 generation used about 2 GB process RAM
in the recorded study. Export requires additional memory. Allow at least 15 GB
free disk space for the default setup, including the source checkpoint, Python
environment, downloads and export; additional precisions require more space.

```bash
git clone https://github.com/23-prabhat/Zoho_PS_13.git
cd Zoho_PS_13
```

Run the remaining commands from the repository root. If you already have a
checkout, use its existing directory.

### 2. Install the pinned preparation environment

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements/export.lock.txt
.venv/bin/python -m pip check
```

The lock file targets CPython 3.14 on Linux x86-64 and includes CPU-only PyTorch,
the export tools, CMake and Ninja. Model export uses Python; inference uses the
native SDK installed below. See [Contributing](CONTRIBUTING.md) for a smaller,
build-only setup that needs no model weights or PyTorch.

### 3. Download and export the default model

```bash
.venv/bin/python scripts/download_model.py
./scripts/export_models.sh int4
.venv/bin/python scripts/verify_model.py
```

The public checkpoint is approximately 3.1 GB. The downloader pins revision
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306` and verifies its checkpoint hash.
The INT4 export is approximately 894 MiB. Export runs locally and can take time.

The verifier checks the required files and all recorded model/tokenizer IR hashes.
These hashes describe the validated artifacts; an independently recreated export
may differ. Review the toolchain and artifact contents before updating a manifest.
See [model provenance](models/manifests/README.md) for verification options.

### 4. Install the native SDK and build

```bash
./scripts/setup_cpp_runtime.sh
./scripts/build_cpp.sh
```

The SDK archive is pinned and SHA-256 checked before extraction into `.deps/`.
A valid cached archive is reused without downloading it again. Build output goes
to `build/release/`. Both directories are ignored by Git.

### 5. Run

```bash
./scripts/shikai generate --prompt "Explain offline inference in two sentences."
./scripts/shikai
```

At the chat prompt, use `/help`, `/stats`, `/reset`, or `/exit`. Press Ctrl+C during
generation to cancel the current response. `/reset` clears session history and
previous statistics. The launcher selects the project SDK and sets Hugging Face
and Transformers offline flags.

Optionally install a command for your user account after setup:

```bash
./scripts/install_shikai.sh
shikai --help
```

The installer creates a symlink in `${XDG_BIN_HOME:-$HOME/.local/bin}` and prints
PATH instructions when needed. Moving the checkout requires rerunning it.

## Usage and configuration

```bash
./scripts/shikai --help
./scripts/shikai devices
./scripts/shikai generate --prompt-file /path/to/prompt.txt
./scripts/shikai benchmark --output results/benchmark.csv
./scripts/shikai --config configs/cpu-4threads.json
./scripts/shikai generate --threads 4 --max-new-tokens 64 --prompt "What is quantization?"
```

[configs/default.json](configs/default.json) controls the default behavior:

| Setting | Default | Meaning |
|---|---|---|
| `model_path` | `../models/qwen2.5-1.5b/int4` | Local model export, relative to the config file |
| `device` | `CPU` | OpenVINO execution device |
| `context_budget` | `2048` | Maximum formatted input plus reserved output tokens |
| `max_new_tokens` | `256` | Maximum response length |
| `do_sample` | `false` | Greedy decoding |
| `inference_threads` | `0` | Let OpenVINO choose CPU threads |
| `kv_cache_precision` | `auto` | Let OpenVINO select cache precision |
| `max_num_seqs` | `1` | One sequence at a time |
| `enable_prefix_caching` / `enable_eviction` | `false` | Experimental cache features disabled |
| `cache_size_gb` | `0` | Runtime-managed cache allocation |
| `num_kv_blocks` | `0` | Fixed block pool; mutually exclusive with `cache_size_gb` |
| `max_num_batched_tokens` | `256` | Scheduler prefill chunk size |
| `eviction_start` / `eviction_recent` / `eviction_max` | `32` / `128` / `672` | Experimental eviction token areas |

Explicit CLI options override JSON settings. Relative `--config` and `--model`
arguments use the caller's working directory; model paths *inside* a config use
that config's directory. `--help` lists every supported option.

When history exceeds the token budget, Shikai removes the oldest complete turns
and prints a notice. A prompt that cannot fit on its own is rejected. The same
input-plus-output budget applies to generation and benchmarks. History is committed
only after successful generation.

An opt-in bounded prefix cache can reuse earlier conversation prefixes:

```bash
./scripts/shikai --config configs/cpu-prefix.json
```

Prefix caching requires an explicit pool (`--num-kv-blocks` or `--cache-size-gb`).
It retains computed prefixes and can change floating-point execution and answers.
With prefix caching enabled, `/reset` releases the cached pipeline and rebuilds it;
reset therefore includes model reload time. The default profile keeps prefix reuse
and eviction disabled. See [KV-cache tuning](guides/kv-cache.md) for measured
tradeoffs, U4 support limits, configurable eviction and conversation benchmarks.

To compare weight formats, export each additional variant before selecting it:

```bash
./scripts/export_models.sh int8
.venv/bin/python scripts/verify_model.py --manifest models/manifests/qwen2.5-1.5b-int8.json
./scripts/shikai --config configs/int8.json

./scripts/export_models.sh fp16
.venv/bin/python scripts/verify_model.py --manifest models/manifests/qwen2.5-1.5b-fp16.json
./scripts/shikai --config configs/fp16.json
```

## How the project fits together

```text
User input → CLI/config validation → context budgeting → OpenVINO LLMPipeline
                                        ↑                       ↓
                                 committed history ← streamed response
                                                                ↓
                                                   metrics / benchmark CSV
```

| Path | Responsibility |
|---|---|
| `src/main.cpp` | CLI, configuration, generation and chat orchestration |
| `src/chat_session.cpp`, `src/context_policy.cpp` | Conversation state and token budgeting |
| `src/model_registry.cpp`, `src/device_probe.cpp` | Asset validation and device discovery |
| `src/metrics.cpp`, `src/resource_profiler.cpp` | Timing and resource measurements |
| `include/local_llm/` | Public interfaces for the native modules |
| `configs/` | Reproducible runtime profiles |
| `scripts/` | Download, export, native build, launch and reporting tools |
| `benchmarks/` | Prompt fixtures and the quality rubric |
| `tests/` | Native, script, integration and reliability checks |
| `models/manifests/` | Model revision, export settings and checksums |
| `results/validated-*/` | Reviewed measurements, answers, strict checks and reproduction records |
| `third_party/` | Retained upstream license and notice files |

Downloaded models, SDKs, environments, builds, generated results and `output/` stay
local. The [documentation index](docs/README.md) covers architecture, requirements,
model compression, KV caching, environment, benchmarks and the demonstration.
Private report authoring remains under ignored `docs/submission/`.
Public setup and technical guidance also live in this README,
[CONTRIBUTING.md](CONTRIBUTING.md), and [guides/](guides/hardware-and-benchmarks.md).

## Validation and measured results

After the full setup:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/ctest --preset release -L unit
.venv/bin/ctest --preset release
```

Unit tests require the SDK/build but no weights. The full suite uses the INT4 model
and exercises real generation, context trimming, reset, cancellation, metrics and
memory stability. The three-turn offline test prefers a network namespace and falls
back to an inherited Linux x86-64 seccomp filter that denies all non-AF_UNIX socket
creation. It verifies TCP/UDP socket denial before starting the application. It
skips only when neither enforcement mechanism is available. CI builds the native application and runs model-free checks; full
inference and hardware comparisons remain explicit local checks.

The [final validation](results/validated-20261109/README.md) has **28 passed,
0 skipped, 0 failed** CTest cases, including enforced offline inference. The Python
preparation/reporting suite has 43 passing cases, including adversarial objective-grader
and publication-boundary checks. The
[October validation](results/validated-20261020/README.md) retains its original
22 passes, one skip and 11 script regressions; historical results are unchanged.
The precision study on an i5-13420H laptop with 16 GB RAM measured:

| Weights | Mean throughput | Mean process peak RSS |
|---|---:|---:|
| INT4 | 14.44 tokens/s | 1,961.95 MiB |
| INT8 | 9.62 tokens/s | 3,113.25 MiB |
| FP16 | 5.34 tokens/s | 6,291.66 MiB |

These are workload-specific observations from three prompts, five measured
repetitions per precision and up to 128 output tokens, after one warmup. The saved
responses, original metadata and limitations accompany the raw measurements.

For reproduction commands, CPU/GPU/VRAM accounting and optional Intel GPU setup,
see [Hardware and benchmarks](guides/hardware-and-benchmarks.md).

## Answer quality and measured cache choices

```bash
.venv/bin/python scripts/evaluate_quality.py --output results/strict-comparison
.venv/bin/python scripts/tune_kv_cache.py --output results/kv-quality
```

The versioned evaluation has 22 objective fixtures and two open-ended answers saved
for review. It checks full answers, typed JSON, numeric units, exact instructions
and long-context recall. The regular `--suite quality` benchmark uses these checks.
Historical keyword scores retain their original meaning and evidence.

The [7 November comparison](results/validated-20261107/README.md) measured:

| CPU weight / requested KV | Objective passes | Observed process peak RSS |
|---|---:|---:|
| INT4 / auto | 7/22 | 2,058.06 MiB |
| INT8 / auto | 9/22 | 3,195.59 MiB |
| FP16 / auto | 9/22 | 6,071.95 MiB |
| FP16 / FP16 | 9/22 | 6,432.69 MiB |

These are finite fixture results including output-format compliance, with one
greedy answer per case, four threads and up to 64 output tokens. They are not
general model accuracy. All four profiles failed the four exact long-context
fixtures. FP16 did not outperform INT8 on the declared checks; an FP16 KV request
added no passes. The two explanation answers per profile await manual review.

Optional profiles expose the measured choices:

```bash
./scripts/shikai --config configs/cpu-int8.json
./scripts/shikai --config configs/fp16.json
./scripts/shikai --config configs/cpu-fp16-cache-f16.json
./scripts/shikai --config configs/cpu-prefix-small.json
./scripts/shikai --config configs/cpu-prefix-u4.json
```

The 64-block automatic prefix profile reserved 32.38 MiB in the separate cache
diagnostic, versus 64.75 MiB for 128 blocks. Mean follow-up TTFT in the new synthetic
conversation workload was 104.22 ms versus 1363.13 ms for baseline. No baseline
objective pass was lost. U4 reserved more cache, but passed more of these strict
checks. These expose different speed/memory/quality trade-offs; CPU/INT4/auto remains
the default. Process RAM, diagnostic reservations and model quality remain separate.
See [answer evaluation and reproduction](guides/answer-quality.md) and
[KV controls](guides/kv-cache.md) for methods, raw answers and limitations.

## GitHub source and isolated reproduction

```bash
.venv/bin/python scripts/check_public_files.py --output output/github-file-audit.json \
  --write-list output/GITHUB_FILES.txt --write-pathspec output/github-pathspec.nul
python3 scripts/validate_reproduction.py --output .cache/clean-validation
```

The [GitHub file guide](guides/github-release.md) explains the source/evidence
allowlist and local exclusions. The inventory checks the current index without
staging or publishing. The reproduction tool uses an isolated source snapshot,
records dependency/download origins, exports INT4, builds and tests generation
under enforced network denial. Optional cached inputs are identified explicitly.

Known limits: the small keyword rubric is not model accuracy; long-context recall
failed in recorded comparisons; Intel GPU output quality differed from CPU; RTX
3050 model kernel compilation failed on the tested runtime. No successful RTX or
NPU inference is claimed. Missing runtime metrics appear as `N/A`, with blank CSV
cells, rather than fabricated zeroes.

## Troubleshooting

| Problem | Action |
|---|---|
| Python packages cannot be resolved | Use CPython 3.14 on Linux x86-64 with the pinned lock file; check access to PyPI and the CPU PyTorch index. |
| Build tools or SDK missing | Complete setup steps 2 and 4. For a build without model export, use the build-only instructions in `CONTRIBUTING.md`. |
| `Missing required model asset` | Finish download/export and run `verify_model.py`; check the selected config and model path. |
| SHA-256 mismatch | Check the exact source revision/tool versions. For SDK corruption, remove the named cached archive and download again. Do not bypass verification. |
| Shared library cannot be loaded | Use `./scripts/shikai`, which sources the matching SDK environment; verify system library compatibility with that SDK. |
| GPU unavailable or compilation fails | Run `devices` and `scripts/probe_hardware.py` on the host; use `--device CPU` for the validated path. |
| Prompt rejected or response cut short | Inspect the context/output budgets; use `/reset` to clear history or explicitly adjust the limits. |
| An optional metric shows `N/A` | The runtime or driver did not expose a valid measurement; see the profiling guide. |

For changes and reproducibility requirements, read [Contributing](CONTRIBUTING.md).
Upstream model/runtime terms are documented in
[Third-party notices](THIRD_PARTY_NOTICES.md). No separate license has yet been
selected for the original project source; the upstream licenses apply to their
respective components.

## Refresh the submission

```bash
python3 scripts/package_submission.py
```

The packager reads current source through an explicit allowlist, includes CI,
guides and reviewed evidence, verifies every entry against a SHA-256 manifest,
and runs preparation/reporting regressions against the extracted package. This
includes uncommitted additions without changing the Git index. Weights, SDKs,
environments and private local material are excluded.

Legacy reports can receive a validation appendix using
`scripts/update_submission_report.py` after installing the optional
`requirements/report.lock.txt` in a separate environment. Its input evidence is
`results/validated-20261103/`; repeating the command replaces the appendix.
The current submission report integrates these findings with a linked index,
repository link and requirements/feature review. Its local authoring material is
under `docs/submission/`; the legacy updater refuses to overwrite that navigation.
