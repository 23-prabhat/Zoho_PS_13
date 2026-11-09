# Validation, strict answer checks and cache screening - 7 November 2026

This snapshot retains new evidence separately from the October and November 3 records.
All failed model answers remain visible. Synthetic fixture pass rates include exact
formatting and do not estimate general model accuracy.

- `quality/`: 24 fixed prompts per profile: 22 objective checks and two explanations
  awaiting review. INT4/auto passed 7/22; INT8/auto, FP16/auto and FP16/FP16-cache
  each passed the same 9/22. All four exact long-context tasks failed in every profile.
  Arithmetic and formatting failures are both retained; see individual answers.
- `kv/`: six cache profiles; two fresh short and two fresh long four-turn
  conversations per profile (96 generated turns). Independent quality contains
  24 answers per profile; matching earlier baseline answers were explicitly reused.
  Mean follow-up TTFT was 1363.13 ms for baseline, 104.22 ms for auto/64 blocks,
  123.42 ms for auto/128 and 128.29 ms for U4/128. Diagnostic reservations were
  32.38, 64.75 and 73.50 MiB respectively. U4 passed more declared checks but used
  more cache. The memory and quality candidates are separate Pareto trade-offs.
  The 64-block diagnostic also completed 1792 input plus 256 output tokens at 100%
  reported usage without allocation failure. Its answer was unusable and is saved.
- `reproduction/`: a separately created environment installed the pinned export
  dependencies from indexes. A fresh copy of the pinned checkpoint was downloaded
  and verified. The isolated source workflow then used those prepared inputs,
  re-extracted the checksum-verified cached SDK, exported INT4, built from source,
  passed all six model-free CTest cases and three offline turns under enforced
  socket denial. All new model/tokenizer IR reference hashes matched. The new
  executable has its own recorded hash; byte-identical native builds are not claimed.
- `verification/`: release build, 28 CTest passes with zero skips/failures, and 38
  model-free Python tests covering grading, cache screening and publication boundaries.
- `publication/`: current source/index inventory and obvious-secret/path checks.
  This does not certify old Git commits or remote contents. No commit/push occurred.

The strict comparison uses CPU, four threads, greedy decoding and up to 64 output
tokens. Conversations use up to eight output tokens per turn; direct allocation
probes are separate pipelines. Cache reservations, process RSS and physical RAM
are different metrics. Background download activity and laptop power/thermals were
not controlled, so latency observations are exploratory rather than universal
speedups. Profile order, actual native settings, answers and binary hashes remain
in the raw records. Repeated deterministic outputs are not independent samples.

The native application binary is unchanged from the previous validated build.
The added evaluation/reproduction/publication tools and optional profiles are current
working source. CPU/INT4/auto stays the default; none of the failed strict cases is
represented as solved. An alternative checkpoint is optional for problem 13.

`checksums.json` records every evidence file except this index and itself. Git line
ending conversion is disabled for the snapshot. Keep historical snapshots unchanged.
