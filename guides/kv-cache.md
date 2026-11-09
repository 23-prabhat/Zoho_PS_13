# KV-cache tuning for Shikai

Shikai uses the pinned OpenVINO 2026.4.1 SDK. The installed C++ headers, rather than
nightly examples, determine which controls are available. Keep the CPU/INT4 default
as a reference and compare saved answers as well as speed.

## Controls implemented in the application

| Control | Purpose | Tradeoff |
|---|---|---|
| Context/output token limits | Bound retained text and requested response length | Old complete turns may be removed |
| `--prefix-caching --num-kv-blocks 128` | Keep a bounded pool of reusable prefix blocks | Retains data between requests; answers may change |
| `--kv-cache-precision auto/u8/u4/f16/bf16/f32` | Request cache compression independently of model weights | Device support and answer quality vary |
| `--max-batched-tokens 64` | Smaller chunks during prompt processing | Can increase first-token latency |
| `--cache-eviction --eviction-start 32 --eviction-recent 128 --eviction-max 1024` | Limit retained attention context during decoding | Can discard relevant information |

`num_kv_blocks` and `cache_size_gb` are mutually exclusive. Prefix reuse requires
one of them to be nonzero, preventing an accidentally unbounded retained cache.
The runtime determines the number of tokens and bytes in each block for the
selected device/precision; a block count is not a byte measurement.

Eviction areas must be positive multiples of 32 for these CPU/GPU profiles, and the
maximum must exceed the initial plus recent areas. Eviction is applied after
prefill; it does not guarantee that processing a long initial prompt stays within
that token limit. Shikai still checks the complete formatted input/output budget.
The provided eviction profile is experimental. Avoid combining compression and
eviction changes before testing each independently.

## Try the bounded prefix profile

```bash
./scripts/shikai --config configs/cpu-prefix.json
./scripts/shikai --config configs/cpu-prefix.json --kv-cache-precision u4
./scripts/shikai --config configs/cpu-eviction.json
```

The prefix profile uses 128 blocks, automatic precision, four CPU threads, one sequence and the
existing 2,048-token context limit. It is opt-in. `/reset` clears history/statistics
and destroys/rebuilds a prefix-enabled pipeline, releasing retained cache ownership.
Reloading takes time; allocator behavior means process RSS need not immediately
return to its original value.

Prefix matching helps only while the beginning of a request still matches retained
blocks. Trimming the oldest chat turns changes that prefix and can reduce reuse.
A model weight format of INT4 does not imply a four-bit KV cache. Conversely, U4
cache settings do not change the weight format. Auto may already select a compressed
cache; explicit U8 is not automatically an improvement.

## Reproduce measurements

```bash
.venv/bin/python scripts/benchmark_kv.py --repetitions 3 --output results/kv-study
.venv/bin/python scripts/benchmark_kv.py --profiles baseline prefix-128 \
  --repetitions 1 --quality-check --output results/kv-quality
```

The native `benchmark --conversation` mode passes assistant answers into the next
turn. It requires one repetition and zero warmups; repeat whole conversations in
fresh processes. The study keeps cold-turn and follow-up TTFT separate, saves every
answer, and records runtime settings and the native binary hash. Its exact-code
retention check and small independent concept rubric are not general model accuracy.

The new November evidence is under `results/validated-20261103/`. The seven-profile
conversation study measured mean follow-up TTFT of 3821.68 ms for baseline and
236.79 ms for the 128-block prefix profile (about 16.1x faster for follow-up
first-token latency). Cold TTFT stayed around 6.1 seconds. All profiles failed the
exact long-context code-recall check; answers differed between baseline and prefix.
This supports an opt-in speed profile, not a quality-equivalent new default. The October studies
remain unchanged under `results/validated-20261020/`. Laptop power, thermal state
and background load limit comparisons across dates. Never compare a cold pipeline
with a warmed prefix request and call the entire difference a universal speedup.

## Measure allocated cache directly

```bash
./scripts/shikai cache-probe --prompt "Explain KV cache briefly." \
  --prefix-caching --num-kv-blocks 128 --kv-cache-precision u4 \
  --max-new-tokens 16 --repetitions 3 --output results/cache-probe.csv
```

This diagnostic uses the native `ContinuousBatchingPipeline` with the same scheduler
and device-property builders as the application. Its `cache_size_in_bytes` counter
measures reserved cache allocation, including free blocks. Per-generation maximum
and average usage percentages are separate fields. The probe repeats an identical
prompt; it is separate from the application conversation latency study. The
installed `LLMPipeline` API exposes neither cache-allocation nor prefix-hit counters,
so Shikai does not invent either from RSS or from token-count differences.

The direct allocation probe measured 64.75 MiB for automatic precision with 128
blocks, 73.50 MiB for U4 with 128 blocks, 112.00 MiB for FP16 with 128 blocks, and
1023.86 MiB for the automatic 1 GB pool. Thus a bounded pool avoids excessive
reservation, while requesting U4 did not improve on auto in this configuration.
These are reserved-cache counters in the diagnostic pipeline, not total process
RAM savings or a measurement of the application pipeline.

## Updated quality-aware screening (7 November)

`scripts/tune_kv_cache.py` now pairs fresh short/long four-turn conversations with
the 22 objective checks and two separately saved explanation answers. It compares
64/128/256-block automatic prefix pools, U4 and eviction, and flags lost baseline
passes before selecting opt-in candidates. It records memory-focused and
quality-focused candidates separately; it never rewrites defaults.

The 64-block profile reserved 32.38 MiB versus 64.75 MiB for 128 blocks and measured
104.22 ms mean follow-up TTFT versus 1363.13 ms baseline in this new workload.
It retained all baseline passes. It also completed 1792 input plus 256 output tokens
at the tested 2048-token boundary. Use `configs/cpu-prefix-small.json` as the
explicit small-pool profile. Higher context budgets require another capacity test.

U4/128 reserved 73.50 MiB but passed 8/22 independent and 8/16 conversation checks,
versus 7/22 and 2/16 for auto in this workload. Use `configs/cpu-prefix-u4.json` to
explore that trade-off. A failed exact check can reflect formatting, recall or
both; raw answers remain available. Smaller reservation and better answer quality
are separate goals. The default short-prompt diagnostic grows its allocation
dynamically, so its small reading is not a full-context upper bound.

These timings are exploratory: laptop thermals/background downloads were not
controlled, and the conversations use eight output tokens. See
[the strict evaluation guide](answer-quality.md) and
[reviewed evidence](../results/validated-20261107/README.md) for the full methods,
failed answers, baseline-reuse checks and limitations.

## Sources and further options

- [OpenVINO continuous batching](https://openvinotoolkit.github.io/openvino.genai/docs/concepts/optimization-techniques/continuous-batching/): paged blocks, scheduling, prefix reuse and chunked prefill.
- [OpenVINO cache eviction](https://openvinotoolkit.github.io/openvino.genai/docs/concepts/optimization-techniques/kvcache-eviction-algorithm/): eviction/rotation and quality tradeoffs.
- [OpenVINO runtime properties](https://docs.openvino.ai/2026/api/c_cpp_api/group__ov__runtime__cpp__prop__api.html): cache precision and independent K/V controls.

The SDK also contains KVCrush and Adaptive R-KV eviction configurations. These are
further experiments, not enabled or claimed as validated by Shikai. Independent
key/value precision and quantization group sizes deserve model-specific quality
measurements before adding more presets. For a single short-context conversation,
first measure bounded prefix reuse and context sizing: model weights and workspace
can dominate total RSS even when the cache itself becomes smaller.
