# Results

Generated files and directories here are ignored by default, including native
`benchmark.csv`, hardware probes and orchestrated `run-<id>/` experiments. Commit
only a small, reviewed evidence snapshot with its checksums and raw measurements.

The [20 October 2026 evidence snapshot](validated-20261020/README.md) contains the
selected historical studies, saved responses, hardware records, charts and checksums.
It is explicitly allowed by `.gitignore` so it can accompany a source release.
To publish another snapshot, add its exact directory to that allowlist after
reviewing it for private prompts, credentials, machine identifiers and file size.
Historical records retain original local paths and timestamps as provenance.

The separate `validated-20261103/` snapshot contains enforced offline verification,
new block-pool/prefix/precision/eviction conversation comparisons, independent
quality answers and a native cache-allocation diagnostic. Its README distinguishes
reserved cache, process RSS, cold timing, follow-up timing and model-quality limits.

The [7 November snapshot](validated-20261107/README.md) retains the versioned strict
answer-quality comparison across INT4, INT8 and FP16, quality-aware cache screening,
near-capacity block-pool checks, isolated reproduction logs and publication audit.
Its checksums protect raw failures as well as successful cases. Objective checks
include formatting requirements; they are not general model accuracy. Cache-probe
reservation belongs to a separate diagnostic pipeline and is not total process RAM.

The [9 November final review](validated-20261109/README.md) adds current build,
28-case CTest, 43-case Python, optimized-Python quality, offline and model-hash
verification logs. It re-screens the earlier cache evidence using complete-case,
provenance and error-handling fixes; it does not introduce new benchmark timings.
