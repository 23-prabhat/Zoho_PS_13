# Final submission review - 9 November 2026

The release build and all 28 CTest cases passed, with zero failures and skips.
The updated Python suite has 43 passing cases. Quality regressions also passed
under python -O. Source checkpoint and INT4/INT8/FP16 IR checksums were verified;
pip check passed. verification/ contains the raw logs and network-denial record.
The full native suite ran once; final-script-ctest.txt rechecks the script case
after the five added regressions. No native inference source changed this iteration.

The cache-tuning review fixes stale/incompatible baseline acceptance, incomplete
fixture coverage, invalid timing and allocation-probe failure reporting.
cache-rescreen.json applies the stronger screening to the original November 7
answers/timings. The memory/quality candidate choices are unchanged. This is
re-scoring retained evidence, not a new performance or model-quality experiment.
Historical October/November 3/November 7 snapshots were not modified.

The project summary and research notes explain feature purpose and primary-source
connections. PDF authoring/visual QA and remote publication are separate handoff
records, so this snapshot does not claim a future push or hosted CI outcome.
checksums.json covers every file except itself and this index.
