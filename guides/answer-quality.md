# Answer quality, weight precision and KV-cache tuning

Qwen2.5-1.5B-Instruct satisfies problem 13's 1–3B model requirement. A different
checkpoint is optional. FP16 removes low-bit weight compression, but the original
model can still make factual, instruction-following and long-context errors.
Weight precision, requested KV precision and runtime arithmetic are separate.

## Versioned objective checks

```bash
.venv/bin/python scripts/evaluate_quality.py --output results/strict-comparison
```

The default compares INT4/auto, INT8/auto, FP16/auto and FP16 with an explicit FP16
KV request. All use CPU, four inference threads, greedy decoding, the same 2,048
token context budget and up to 64 output tokens. No repetition is presented as a
new independent quality sample. Native CSVs retain the actual settings and answers.

`benchmarks/quality_strict_v1.jsonl` contains **22 objective fixtures and two
open-ended explanation fixtures**. Categories include exact instruction compliance,
typed JSON, basic facts, arithmetic, unit conversion, extraction, abstention and
four synthetic long-context cases. Padding lengths are explicit word counts; the
native tokenizer records actual formatted input tokens.

- Exact checks compare the entire answer after trimming boundary whitespace.
- Numeric checks require a number and declared unit, with explicit decimal/binary
  conversion tolerances. Wrong units, surrounding prose and non-finite values fail.
- JSON checks reject extra keys, duplicate keys, wrong types, Markdown and prose.
- Open-ended explanations are saved as `needs_review`; they receive no automatic
  correctness credit and are excluded from automatic pass rates.
- Missing responses and runtime failures are execution errors, separate from
  failed model answers. Duplicate/unexpected result IDs are rejected.

These pass rates measure the declared fixtures **including required formatting**.
They are not general model accuracy, semantic equivalence or a statistical estimate
of performance on arbitrary questions. Prompts and expected answers are authored
project fixtures and remain inspectable. A run can finish successfully with failed
model answers; execution errors return a nonzero status.

Raw answers can be rescored without generating new ones:

```bash
.venv/bin/python scripts/evaluate_quality.py \
  --rescore results/strict-comparison/all-results.csv \
  --output results/strict-rescore
```

`run_benchmarks.py --suite quality` uses these strict fixtures too. Older curated
keyword scores are retained under their original methodology; they are never
silently relabeled as correctness or recomputed in place.

## Quality-aware cache comparisons

```bash
.venv/bin/python scripts/tune_kv_cache.py --output results/kv-quality
```

This compares the baseline, 64/128/256-block automatic prefix pools, U4 prefix
cache and 1,024-token eviction. Each repetition starts a fresh native process and
runs a four-turn short or long conversation. The same fixtures check recall before
and after replacing a reference code. Cold/follow-up TTFT and objective decisions
are separated. Independent strict fixtures use 64 output tokens. Cache allocation
probes use a separate diagnostic pipeline and retain reserved bytes/usage counters.

An opt-in candidate must preserve all baseline independent and conversation passes, have no execution
errors, lower follow-up TTFT by at least 20%, and keep cold TTFT within 25% of
baseline. Among eligible candidates, the tool selects the smallest measured
diagnostic reservation. This is an explicit screening rule on finite fixtures,
not proof of semantic equivalence or universal optimality. It also reports a
quality-focused candidate and the non-dominated eligible trade-offs across
independent/conversation passes, latency and reservation. The tool does not
rewrite runtime defaults. Failed cases and manual-review answers remain visible.

The final review requires complete, unique fixture/turn coverage and valid finite
timing for screening. Reused baselines must match prompt, binary, model/manifest
identity, greedy decoding and recorded runtime settings. These checks also run
under `python -O`. A failed, empty or timed-out allocation probe is logged and makes
the overall tuning command fail. The original November candidates remain unchanged
when their saved evidence is re-screened with these stricter validation rules.

Prefix reuse helps matching request beginnings. Eviction trades retained attention
context for capacity during decode; it does not shrink initial prefill by itself.
See the [OpenVINO continuous-batching guide](https://openvinotoolkit.github.io/openvino.genai/docs/concepts/optimization-techniques/continuous-batching/)
and [eviction guide](https://openvinotoolkit.github.io/openvino.genai/docs/concepts/optimization-techniques/kvcache-eviction-algorithm/),
and verify supported controls against the pinned SDK headers. Requesting U4 does
not imply a smaller cache layout than automatic precision.

## Isolated setup and model re-export

```bash
python3 scripts/validate_reproduction.py --output .cache/clean-validation
```

This copies allowlisted source, creates a new environment, installs the export lock,
downloads/verifies the pinned checkpoint, exports INT4, installs the checksum-pinned
SDK, builds the C++ program, runs model-free tests and performs three turns of
generation from the new export under enforced network denial. Each stage saves a
command, return code and log. Outputs remain local.

Optional `--checkpoint`, `--sdk-archive` and `--prepared-environment` inputs support
cached validation and are explicitly identified in the summary. The original
project environment cannot be supplied as the prepared environment. A fresh export
records its own hashes and whether they match reference bytes; no manifest is
silently changed. A semantic smoke test and byte-identical reproduction are
separate results. No full second checkpoint is needed to run this workflow.
