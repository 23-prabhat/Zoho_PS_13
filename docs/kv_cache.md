# KV cache

During autoregressive decoding, each transformer layer stores attention keys and
values for previous tokens. This avoids recomputing those projections for every new
token, but memory grows with retained context length.

For Qwen2.5-1.5B (28 layers, 2 KV heads, head dimension 128), assuming two-byte cache
elements and one active sequence:

```text
KV bytes ≈ 2 × 28 × tokens × 2 × 128 × 2 = 28 KiB × tokens
```

| Actual tokens | Estimated KV tensor size | Measured process RSS | TTFT |
|---:|---:|---:|---:|
| 125 | 3.42 MiB | 1969.23 MiB | 766.39 ms |
| 509 | 13.92 MiB | 2025.16 MiB | 3161.84 ms |
| 1,021 | 27.92 MiB | 2025.33 MiB | 6339.92 ms |
| 2,045 | 55.92 MiB | 2044.91 MiB | 13474.00 ms |

The RSS increase is larger than the simple KV estimate because RSS also includes
model weights, activations, temporary buffers, allocator retention, and runtime state.
The estimate is explanatory; it is not a direct OpenVINO allocation counter.

The two-byte assumption does not describe the measured effective cache format.
`--kv-cache-precision` requests auto/U4/U8/FP16/BF16/FP32 independently of weight
precision. This CPU advertises a U8 default hint; explicit U8 did not establish
additional RSS savings. Auto remains the default. The compiled pipeline's effective
layout has not been measured.

The application reuses one `LLMPipeline` and supplies complete `ChatHistory` for each
request; it does not promise KV reuse across chat turns. Its
2,048-token policy bounds normal interactive history by deleting oldest complete
turns. `/reset` clears logical history but does not promise that the operating-system
RSS immediately falls. The default keeps cross-request prefix caching and eviction
disabled. Separate optional-policy probes found that prefix caching lowered mean TTFT
for three requests sharing a 480-word prefix from 3.61 s to 1.75 s; decode throughput
was nearly unchanged. A one-run eviction probe executed successfully but was slightly
slower, so no general memory or quality benefit is claimed. These controls are OpenVINO
scheduler policies and are distinct from application-level history trimming.

## November implementation

The opt-in cpu-prefix profile retains 128 blocks for prefix reuse; /reset rebuilds
that pipeline to release retained cache ownership. The cache-probe command now
measures reserved allocation directly through ContinuousBatchingPipeline. These
counters belong to the diagnostic pipeline, not an inferred LLMPipeline metric.
U4, prefill chunking and configurable eviction are available for controlled tests.
See the [KV guide](../guides/kv-cache.md) and the [November 3 evidence](../results/validated-20261103/README.md) for that study.

## Strict November 7 comparison and final review

The exploratory 64-block automatic prefix pool measured 104.22 ms mean follow-up
TTFT versus 1363.13 ms baseline in the new conversation workload. Its separate
short-prompt diagnostic reserved 32.38 MiB versus 64.75 MiB for 128 blocks. U4/128
reserved 73.50 MiB and passed more declared checks; it is a different quality/memory
trade-off. A separate 64-block probe completed the 1792-input + 256-output boundary.
Reservations are not application RSS, and successful allocation is not answer quality.

These synthetic, short-output laptop experiments do not establish a universal
optimum. Prefix reuse and eviction remain opt-in. The final screening rejects
incomplete fixture coverage, invalid timing and lost baseline passes; probe failures
are reported as execution failures. [Saved re-screening](../results/validated-20261109/cache-rescreen.json)
kept the original candidate choices unchanged without generating new timings.

See [answer-quality methods](../guides/answer-quality.md) for constraints and failure cases.
