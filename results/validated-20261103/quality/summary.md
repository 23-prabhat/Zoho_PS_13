# KV-cache comparison

Each repetition is a fresh native process. All three turns belong to the same conversation. Cold and follow-up TTFT are separate. RSS includes weights, workspace and allocated cache; it is not a direct KV allocation counter. Requests record the selected precision, not an observed tensor layout.

| Profile | Successful conversations | Cold TTFT ms | Follow-up TTFT ms | Mean process peak RSS MiB | Exact code recall |
|---|---:|---:|---:|---:|---:|
| baseline | 1 | 7236.45 | 4218.99 | 2007.62 | 0/1 |
| prefix-128 | 1 | 6026.20 | 228.92 | 2007.14 | 0/1 |

Exact code recall is an instruction-following/retention check, not model accuracy. Compare saved answers and cold-vs-warm latency before choosing a profile. Eviction can remove useful context and is kept experimental. Small RSS differences cannot establish KV savings. The installed LLMPipeline API exposes no prefix-hit or cache-allocation counter.

## Independent quality fixtures

One greedy answer per fixture; the concept rubric is heuristic, not accuracy. Exact agreement is descriptive and does not prove correctness.

| Profile | Cases | Mean rubric /2 | Exact answers vs baseline | Exact three-word instruction |
|---|---:|---:|---:|---:|
| baseline | 5 | 1.40 | 5/5 | 0/1 |
| prefix-128 | 5 | 1.40 | 5/5 | 0/1 |
