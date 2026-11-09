# Validation and KV-cache evidence - 3 November 2026

New measurements, retained separately from the historical October snapshot.
The conversation study includes 63 generated answers: seven profiles, three fresh
processes per profile, three turns each. The quality follow-up includes ten
independent fixture answers plus six conversation turns. The allocation diagnostic
contains twelve repeated-prompt measurements across four configurations.

- `conversation/`: full input conversation, raw answers/metrics, per-process settings
  and binary hashes. Baseline follow-up TTFT 3821.68 ms, bounded prefix 236.79 ms.
  Cold TTFT stays near 6.1 seconds. Exact long-context recall fails for every profile.
- `quality/`: independent five-case fixture check, baseline and bounded prefix.
  Answers matched exactly for all five cases, with heuristic rubric mean 1.40/2.
  Both profiles failed the exact three-word instruction. This is not model accuracy.
- `allocation/`: native ContinuousBatchingPipeline allocation counter, including
  free pool blocks. Auto/128 blocks = 64.75 MiB; U4/128 = 73.50 MiB; FP16/128 =
  112.00 MiB; auto/1 GB = 1023.86 MiB. These are not total physical RAM savings.
- `verification/`: fresh three-turn generation with kernel-enforced socket denial,
  host details, current CTest results and source/binary identification.

CPU/INT4 and automatic cache precision remain the default. The bounded prefix
profile is opt-in because long-context answers differ from baseline. Eviction did
not show a useful advantage here; a 64-token prefill chunk raised cold latency.
Newer cache controls do not repair the model's recall/instruction failures.

The conversation and quality studies use the same scheduler behavior but different
build hashes: the later build adds a separate cache diagnostic. Each measurement
records its actual binary hash. Metadata paths retain their original local run
locations; these folders are copies of those completed runs.

The processor is an Intel i5-13420H with approximately 16 GB RAM. Studies ran
sequentially with four inference threads, but laptop power/thermal state and
background load were not laboratory controlled. Compare cold and follow-up timing
separately. Cache allocation belongs to the diagnostic pipeline; LLMPipeline exposes
no equivalent counter in this SDK. All answers and measurement limitations remain
part of the evidence.

`checksums.json` identifies the recorded evidence files, excluding this index and
itself. The previous snapshot is preserved byte-for-byte.

Current validation: all 28 CTest cases passed, with zero skips or failures. A clean
source build from a directory containing spaces also passed all six model-free
cases, reusing the prepared SDK and Python toolchain. No fresh dependency install
or model re-export is claimed for that clean-source check. The original 15-page
report is preserved with a two-page current validation appendix; all 17 pages
were rendered and visually reviewed.

The October verification record predates assembly of the original report; its
submission-state field describes that earlier timestamp. Current handoff state is
recorded here and in the newly generated archive's manifest.
