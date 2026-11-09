# Validated evidence snapshot - 20 October 2026

These are copies of completed measurements, not new benchmark runs. Raw CSVs retain
their original timestamps, model hashes and Git metadata. The October 20 CPU and
Intel GPU studies additionally record the measured executable hash in
`validation.json`. Earlier studies predate that field. All were collected on the
Intel Core i5-13420H laptop with 16 GB RAM, Fedora 44 and the pinned OpenVINO stack.
See `intel-gpu-20261020/hardware.json` for host GPU/runtime provenance.

`quality-cases-legacy.jsonl` preserves the original five-case fixture. Its storage
case included an incorrect accepted alternative, "2.8125 gigabytes", which has been
removed from the current fixture (3 billion bytes = 3 GB, about 2.794 GiB). Historical
scores have not been recomputed or presented as semantic accuracy. Inspect answers
for unit errors, extra words and incomplete/truncated output.

| Study folder | Evidence and scope |
|---|---|
| `performance-final-20261011` | 45 successful rows: INT4/INT8/FP16, three prompts, five recorded repetitions, one warmup, up to 128 output tokens |
| `context-final-20261011` | 125/509/1021/2045 formatted input tokens; prefill latency and theoretical FP16 KV estimate |
| `quality-5rep-20261011` | 75 saved responses: five small rubric cases across three precisions and five greedy repetitions |
| `threads-20261011` | Four/eight/twelve-thread experiment; does not compare against runtime-selected threads |
| `cache-20261011` | Repeated-prefix timing and one-run eviction wiring probe |
| `optimization-20261020` | 72 successful rows: runtime/four-thread and auto/U8/FP16 KV requests; short and 1024-token performance prompts, six quality cases |
| `intel-gpu-20261020` | 30 successful rows: CPU vs Intel UHD GPU; nine performance rows and six saved quality answers per device |
| `devices-20261020` | System NVIDIA ICD attempt: CPU succeeded; RTX 3050 model kernel compilation failed |
| `final-cpu-smoke-20261020` | Rebuilt binary: three successful two-token generations per precision, with new command/config/binary metadata; wiring check only |
| `verification` | Final CTest logs, exact native binary/source hashes and audit validation record; rebuilt Intel GPU generation also passed |

The weight-precision study measured mean INT4/INT8/FP16 throughput of
14.44/9.62/5.34 tokens/s and mean process-lifetime peak RSS of
1961.95/3113.25/6291.66 MiB. For those prompts, INT4 achieved about 2.7 times FP16
throughput and 69% lower peak RSS. INT4 storage is about 894 MiB versus FP16's 2965 MiB.
These are results from this laptop and workload, not universal guarantees.

The later CPU/GPU study used shorter, 32-token outputs: CPU averaged 17.98 tok/s,
Intel UHD GPU 8.84 tok/s. Mean process CPU use was 378.53% vs 100.70%, where 100% is
one logical CPU. Mean sampled RSS peaks were 1958.57 vs 566.05 MiB, but the GPU also
allocated about 1254 MiB in shared system memory. These overlapping accounting
categories must not be subtracted or treated as total physical RAM savings.

Keep these limits with any charts or resume claims:

- The keyword/concept rubric is small and heuristic, not model accuracy. Five
  repeated greedy outputs do not constitute independent quality samples.
- The six-case October 20 quality mean was 1.17/2 on CPU and 0.67/2 on Intel GPU.
  The long-context reference-code recall case failed on both devices and all CPU
  optimization profiles. CPU is the validated default; GPU remains experimental.
- Four threads did not beat runtime-selected threads in the controlled October 20
  comparison. Explicit U8 did not establish additional RAM savings. Automatic
  threading and automatic KV precision remain defaults.
- The 28 KiB/token KV calculation assumes two-byte elements and one sequence. It
  is explanatory, not the measured cache allocation. The CPU advertises a U8
  default precision hint; this does not prove the compiled pipeline's cache layout.
- DRM counters describe GPU buffer allocations, not resident VRAM. Intel UHD uses
  shared memory. NVIDIA samples in failed runs cover loading/compilation, not
  successful inference. No RTX inference speed or VRAM result is claimed.
- RSS sampling has a 50 ms interval; short spikes can be missed. Laptop thermals,
  power mode and background load were not laboratory controlled. Resource counters
  are not electrical power measurements.

`checksums.json` records SHA-256 for the copied evidence files (excluding this
index). Recompute a file's hash to verify the snapshot against its recorded value.
The charts in `figures/` summarize the October 11 studies, not the later GPU study.
