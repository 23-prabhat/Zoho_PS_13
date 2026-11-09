# Direct cache allocation probe

Native ContinuousBatchingPipeline, same scheduler/property builders as the app. Fixed pools, one sequence, 35 input tokens, 8 output tokens, three calls with an identical prompt. Allocated bytes include free pool blocks and are not RSS or active KV occupancy.

| Setting | Allocated pool MiB | Maximum usage % |
|---|---:|---:|
| auto-128 | 64.75 | 1.5625 |
| u4-128 | 73.50 | 1.5625 |
| f16-128 | 112.00 | 1.5625 |
| auto-1gb | 1023.86 | 0.0988 |

The bounded automatic 128-block pool reserves substantially less than the historical 1 GB prefix pool. U4 is supported on this CPU but reserves MORE than auto at the same block count in this probe. Do not infer memory savings from the requested bit width. This is not a quality or throughput comparison.
