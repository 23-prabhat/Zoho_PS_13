# Shikai documentation

Technical documentation for **SWFW_5S_13: Local LLM on OpenVINO**.
Updated 9 November 2026 to match the reviewed implementation and evidence.

| Document | Contents |
|---|---|
| [Architecture](architecture.md) | Preparation, native execution, state ownership and measurement boundaries |
| [Requirements](requirements.md) | Problem statement mapped to implementation and evidence |
| [Quantization](quantization.md) | Checkpoint identity, export formats and measured trade-offs |
| [KV cache](kv_cache.md) | Token budgets, bounded pools, prefix reuse, eviction and direct probes |
| [Environment](environment.md) | Laptop specifications, native dependencies and hosted CI |
| [Benchmark report](benchmark_report.md) | Precision/context/device results, strict answers and limitations |
| [Technical project report](final_report.md) | Public overview of implementation, validation and research |
| [Demonstration](demo_checklist.md) | Commands, expected behavior and viva topics |

The [complete feature-purpose guide](../guides/project-summary.md) explains what
was built and why each part is needed. Start with the [README setup](../README.md)
and [contributor build instructions](../CONTRIBUTING.md) to reproduce it.

Only explicitly reviewed technical files and figures are public. Student details,
report authoring, screenshots/transcripts and intermediate renders under
`docs/submission/` remain local. The full college PDF is delivered in the submission
ZIP; this directory's technical report is the public summary.
