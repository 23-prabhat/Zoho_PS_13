# KV-cache comparison

Each repetition is a fresh native process. All three turns belong to the same conversation. Cold and follow-up TTFT are separate. RSS includes weights, workspace and allocated cache; it is not a direct KV allocation counter. Requests record the selected precision, not an observed tensor layout.

| Profile | Successful conversations | Cold TTFT ms | Follow-up TTFT ms | Mean process peak RSS MiB | Exact code recall |
|---|---:|---:|---:|---:|---:|
| baseline | 3 | 6136.59 | 3821.68 | 2007.55 | 0/3 |
| eviction-1024 | 3 | 6160.89 | 3727.46 | 2008.00 | 0/3 |
| eviction-256 | 3 | 6346.83 | 4160.16 | 2007.68 | 0/3 |
| prefix-128 | 3 | 6122.47 | 236.79 | 2007.35 | 0/3 |
| prefix-128-u4 | 3 | 6522.41 | 256.32 | 2004.55 | 0/3 |
| prefix-128-u8 | 3 | 6346.98 | 276.41 | 2007.35 | 0/3 |
| prefix-256-chunk64 | 3 | 7455.60 | 277.69 | 1968.31 | 0/3 |

Exact code recall is an instruction-following/retention check, not model accuracy. Compare saved answers and cold-vs-warm latency before choosing a profile. Eviction can remove useful context and is kept experimental. Small RSS differences cannot establish KV savings. The installed LLMPipeline API exposes no prefix-hit or cache-allocation counter.
