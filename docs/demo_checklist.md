# Demonstration and viva checklist

## Prepare

1. Follow the [README](../README.md), including the OpenCL loader dependency.
2. Run `./scripts/build_cpp.sh` and `.venv/bin/ctest --preset release`.
3. Run `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`.
4. Use AC power and record background-load/power conditions for new measurements.

## Demonstrate

```bash
./scripts/shikai devices
./scripts/shikai generate --prompt "Explain local inference in two sentences."
./scripts/shikai chat --max-new-tokens 48
```

In chat, give a short codename, ask a follow-up, inspect `/stats`, then `/reset`,
`/stats` and `/exit`. Show context rejection with a small explicit budget. Ctrl+C
during generation should cancel the turn and allow another request. Do not expect
a small model to satisfy every exact instruction; inspect saved answers honestly.

Show [precision/context graphs](benchmark_report.md), raw metadata and strict failed
answers. Optional INT8/FP16 variants must be exported and verified before use.
A prefix profile is an explicit latency experiment, not a guaranteed quality upgrade.

## Explain

- Prefill versus autoregressive decode; TTFT versus decode rate.
- Weights versus KV state versus transcript history.
- Reserved output tokens and complete-turn trimming.
- Why fewer CPU threads or lower precision need actual measurement.
- Why RSS, reserved cache, shared GPU buffers and dedicated VRAM cannot be combined.
- Kernel network denial versus offline environment flags alone.
- Exact-fixture compliance versus general model accuracy.
- [Current validation](../results/validated-20261109/README.md) versus historical benchmarks.

Read the [complete project explanation](../guides/project-summary.md) for feature purpose
and the [requirements map](requirements.md) for the selected problem's scope.
