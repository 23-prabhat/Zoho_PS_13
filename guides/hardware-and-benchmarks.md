# Hardware profiling and benchmark methodology

[Back to the project overview](../README.md). Commands below assume the
[default setup](../README.md#setup-and-first-run) is complete and are run from the repository root.
Paths mentioned in the text are relative to that root.

## CPU profiles and counters

Two explicit CPU profiles preserve the same INT4 model, token budget and cache policy:

```bash
./scripts/shikai --config configs/cpu-runtime.json    # OpenVINO chooses CPU threads
./scripts/shikai --config configs/cpu-4threads.json   # four CPU inference threads
./scripts/shikai --threads 4 --kv-cache-precision u8
```

`kv_cache_precision` accepts `auto`, `u8`, `f16`, `bf16`, or `f32`. CLI options override
JSON. `auto` leaves the property unset so OpenVINO chooses it; unsupported explicit
settings fail with the runtime's diagnostic. `./scripts/shikai devices` prints the device's
default precision hint where queryable. This is not a measurement of the compiled
pipeline's effective cache layout. The CPU on this host reports `u8` already, so
explicit U8 should not automatically be described as a new memory saving.

`/stats`, single-response stderr, and benchmark CSVs include process CPU time, CPU
utilization, and RSS sampled during each generation at 50 ms intervals. CPU 100%
means one logical CPU, so a multithreaded process can exceed 100%. The sampled peak
can miss shorter spikes; the existing `peak_rss_mib` remains the OS process-lifetime
high-water mark. CPU time includes all threads in the process, including the sampler.
These are resource measurements, not electrical power measurements.

For GPU inference, the native sampler reads Linux DRM client counters when the driver
provides them. It deduplicates shared file descriptors, reports requested GPU buffer
allocations in system/local memory, and sums engine busy time. These allocation
counters are not resident VRAM measurements and may overlap process RAM. Engine
percentages can exceed 100% when multiple engines run concurrently. Missing driver
counters stay `N/A` rather than becoming zero.

The benchmark orchestrator also optionally samples NVIDIA's installed `nvidia-smi`.
VRAM is matched to the inference PID; device utilization can include other clients.
These NVIDIA measurements cover the whole benchmark child process, including load
and warmup. They are stored separately from generation measurements, with raw samples
in `*.gpu.json`. They add no Python dependency to the deployed C++ executable.

Run controlled comparisons and retain their raw answers and measurements:

```bash
python3 scripts/run_benchmarks.py --suite optimization \
  --repetitions 3 --warmup-runs 1 --max-new-tokens 32
python3 scripts/probe_hardware.py --output results/hardware.json
python3 scripts/run_benchmarks.py --suite devices \
  --threads 4 --repetitions 3 --warmup-runs 1 --max-new-tokens 32
```

The optimization suite compares runtime-selected threads against four threads, then
compares automatic, U8 and FP16 KV-cache requests at four threads. Performance uses
identical short prompts plus a 1,024-token prompt; greedy quality checks save one
128-token-limited answer per existing rubric case plus a long-context code-recall
case. Repeated greedy answers would not
provide independent quality evidence. Hardware comparisons use the same INT4 model,
prompt fixtures and token limits on CPU and every detected OpenVINO GPU.

The device suite records a clear skip when no GPU is exposed, and records runtime
failures rather than silently substituting CPU. Driver installations and permissions
are never modified by the probe or benchmark. A sandbox/container may hide GPU nodes
even when the host supports GPU inference; run the probe on the host before changing
drivers. Keep AC power, power mode and background load consistent for comparisons.

### Optional project-local Intel GPU runtime on Fedora

On the validated laptop, the system OpenCL ICD exposed the RTX 3050, but the model's
OpenVINO GPU kernels failed to compile on that device. The Intel UHD graphics needed
an Intel OpenCL userspace runtime. This optional bootstrap downloads signed Fedora
RPMs and extracts them under `.deps/`; it does not install system packages, modify
kernel drivers, or change render-device permissions:

```bash
bash scripts/setup_gpu_runtime.sh
./scripts/shikai devices
./scripts/shikai generate --device GPU --threads 0 --prompt "Explain local inference briefly."
```

The launcher loads this local runtime automatically when present, isolating Shikai's
OpenCL ICD selection to Intel. Other applications and the system ICD configuration
are unchanged. `SHIKAI_USE_LOCAL_GPU=0 ./scripts/shikai devices` inspects the system
runtime instead. Cached packages can be re-extracted using `--from-cache`; their
filenames and SHA-256 hashes are recorded in `.deps/intel-gpu-runtime/manifest.json`.
GPU device nodes must still be accessible, so run hardware validation on the host
when a sandbox hides them. An Intel iGPU uses shared system RAM; dedicated VRAM
measurements do not apply to that device.

Select the explicit Intel GPU profile with:

```bash
./scripts/shikai --config configs/gpu-intel.json
```

### Hardware validation on 20 October 2026

The controlled CPU study compared runtime-selected threads and four threads on
three short prompts plus a 1,024-token prompt, with three recorded repetitions,
one warmup and 32 output tokens. Mean throughput was 17.76 versus 17.30 tokens/s,
and mean sampled RSS peaks were both about 1,975 MiB. All six quality answers
matched exactly. Automatic CPU threading remains the default; four threads is an
explicit reproducible profile rather than a claimed improvement over auto.

Explicit U8 KV-cache requests did not reduce measured RSS and were slower in this
run. FP16 changed some answers and slightly improved the small rubric, but did not
establish a resource saving. Automatic cache precision remains the default. See
the generated `results/validated-20261020/optimization-20261020/summary.md`, raw CSVs and saved
answers. The long-context code-recall case failed across all CPU profiles.

The host CPU/GPU performance comparison used the same INT4 model, three short
prompts, three recorded repetitions, one warmup and 32 output tokens:

| Device | Mean tok/s | Mean CPU use (100% = one CPU) | Mean sampled RSS peak | Mean GPU system-buffer peak |
|---|---:|---:|---:|---:|
| CPU, four threads | 17.98 | 378.53% | 1958.57 MiB | N/A |
| Intel UHD GPU | 8.84 | 100.70% | 566.05 MiB | 1254.00 MiB |

Intel GPU inference offloads CPU work but was slower for this workload. CPU remains
the default. The six-case automatic quality rubric scored CPU at 1.17/2 and GPU at
0.67/2; the GPU profile is experimental, with no claim of answer equivalence. The
long-context recall case failed on both devices. GPU system-buffer allocations consume shared system RAM and can overlap
other accounting; lower process RSS alone is not evidence of an equivalent reduction
in total physical RAM. These 32-token runs are separate from the earlier 128-token
weight-precision study, and laptop power/thermals were not laboratory controlled.
Full answers, quality scores, counters and hardware provenance are retained under
`results/validated-20261020/intel-gpu-20261020/`. The RTX 3050 kernel-compilation failures are retained
separately under `results/validated-20261020/devices-20261020/`; no successful RTX inference result
is claimed.


## Reproduce the precision, context and quality studies

INT8 and FP16 must also be exported before running `--suite all`. Python orchestration
and SVG plotting use only the standard library. The full study takes substantially
longer than a smoke test:

```bash
.venv/bin/python scripts/run_benchmarks.py --suite all --output results/run-comparison \
  --repetitions 5 --warmup-runs 1 --max-new-tokens 128
```

Each invocation writes an ignored `results/run-*` directory containing raw CSVs,
saved responses, provenance metadata and a Markdown summary. The command above
uses the explicit directory `results/run-comparison`; choose a new directory name
for subsequent runs. To create SVG charts from this run, use the separate plotter:

```bash
.venv/bin/python scripts/plot_results.py results/run-comparison/all-results.csv \
  --output results/run-comparison/figures
```

Use `--help` for the available suites and runtime overrides. Keep errors and missing
counters visible in reports.
See the [curated evidence index](../results/validated-20261020/README.md) and
[scoring rubric](../benchmarks/rubric.md) before interpreting historical figures.
