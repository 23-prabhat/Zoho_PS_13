#!/usr/bin/env python3
"""Compare existing weight/cache profiles with versioned objective answer checks."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

from answer_quality import FIXTURES, VERSION, grade_answer, load_cases, summarize
from run_benchmarks import MODELS, PROJECT, file_sha256, run_cpp, write_combined, write_jsonl

PROFILES = {
    "int4-auto": dict(weight="int4"),
    "int8-auto": dict(weight="int8"),
    "fp16-auto": dict(weight="fp16"),
    "fp16-f16-kv": dict(weight="fp16", kv_cache_precision="f16"),
    "int4-prefix-64": dict(weight="int4", prefix_caching=True, num_kv_blocks=64),
    "int4-prefix-128": dict(weight="int4", prefix_caching=True, num_kv_blocks=128),
    "int4-prefix-256": dict(weight="int4", prefix_caching=True, num_kv_blocks=256),
    "int4-prefix-u4": dict(weight="int4", prefix_caching=True, num_kv_blocks=128, kv_cache_precision="u4"),
    "int4-eviction-1024": dict(weight="int4", cache_eviction=True, eviction_max=1024),
}


def runtime_settings(profile, threads=4, max_new_tokens=64, timeout_seconds=600):
    settings = dict(PROFILES[profile])
    weight = settings.pop("weight")
    runtime = dict(repetitions=1, warmup_runs=0, max_new_tokens=max_new_tokens,
        threads=threads, device="CPU", kv_cache_precision="auto", prefix_caching=False,
        cache_size_gb=0, num_kv_blocks=0, cache_eviction=False, max_batched_tokens=256,
        eviction_start=32, eviction_recent=128, eviction_max=672, timeout_seconds=timeout_seconds)
    runtime.update(settings)
    return weight, runtime


def grade_rows(measured, cases, profile):
    by_id = {case["id"]: case for case in cases}
    seen = set()
    rows = []
    for raw in measured:
        row = dict(raw)
        identity = row.get("id")
        if identity not in by_id or identity in seen:
            raise ValueError(f"Unexpected/duplicate generated case: {identity}")
        seen.add(identity)
        case = by_id[identity]
        row.update(profile=profile, suite="strict-quality", category=case["category"])
        if "response" not in row or row.get("status", "ok") != "ok":
            row.update(status="error", strict_status="execution_error", strict_pass="",
                       grading_reason=row.get("error", "Missing generated response"))
        else:
            row.update(grade_answer(case, row["response"]))
        rows.append(row)
    for identity in sorted(set(by_id)-seen):
        rows.append(dict(id=identity, profile=profile, suite="strict-quality", category=by_id[identity]["category"],
            status="error", strict_status="execution_error", strict_pass="", error="No result for fixture"))
    return rows


def write_summary(output, rows, fixtures_sha256):
    summaries = {profile: summarize([r for r in rows if r["profile"] == profile])
                 for profile in sorted({r["profile"] for r in rows})}
    record = dict(grader_version=VERSION, fixtures_sha256=fixtures_sha256,
        scope="Pass rate for declared objective fixtures, including exact output formatting; not general accuracy.",
        manual_review="Open-ended explanations are saved separately and excluded from automatic pass rates.",
        profiles=summaries)
    (output/"summary.json").write_text(json.dumps(record, indent=2)+"\n")
    lines = ["# Strict answer-quality comparison", "", record["scope"], record["manual_review"], "",
        "Each fixture has one greedy response per profile. Repeated deterministic answers are not independent samples.",
        "Profiles use the same prompts, output limit, CPU threads and context budget. Weight and cache settings are recorded separately.", "",
        "| Profile | Objective pass | Fail | Execution errors | Human review pending |",
        "|---|---:|---:|---:|---:|"]
    for profile, item in summaries.items():
        lines.append(f"| {profile} | {item['passed']}/{item['objective_cases']} | {item['failed']} | {item['execution_errors']} | {item['needs_review']} |")
    lines += ["", "## Category breakdown", "", "| Profile | Category | Pass / objective cases |", "|---|---|---:|"]
    for profile in summaries:
        for category in sorted({r["category"] for r in rows if r["profile"] == profile}):
            item = summarize([r for r in rows if r["profile"] == profile and r["category"] == category])
            if item["objective_cases"]:
                lines.append(f"| {profile} | {category} | {item['passed']}/{item['objective_cases']} |")
    lines += ["", "## Failed objective checks", ""]
    for row in rows:
        if row.get("strict_status") == "fail":
            answer = json.dumps(row["response"], ensure_ascii=False).replace("|", "\\|")
            lines.append(f"- {row['profile']}/{row['id']}: {row['grading_reason']}. Saved answer: {answer}")
    lines += ["", "All raw answers, grader decisions, prompts and native-process metadata accompany this report. "
              "A successful evaluation run can contain failed model answers. Execution failures produce a nonzero exit status."]
    (output/"summary.md").write_text("\n".join(lines)+"\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=["int4-auto", "int8-auto", "fp16-auto", "fp16-f16-kv"])
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=600, help="Maximum time for each native profile")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rescore", type=Path, help="Grade an existing strict-run CSV; do not generate new answers")
    args = parser.parse_args()
    if args.max_new_tokens < 1 or args.max_new_tokens >= 2048 or args.threads < 0 or args.timeout_seconds < 1:
        parser.error("Use positive output tokens below 2048 and nonnegative threads")
    cases = load_cases(args.fixtures)
    output = args.output or PROJECT/"results"/f"strict-{datetime.now():%Y%m%d-%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    prompts = output/"prompts.jsonl"
    write_jsonl(prompts, [dict(id=c["id"], prompt=c["prompt"]) for c in cases])
    (output/"fixtures.jsonl").write_bytes(args.fixtures.read_bytes())
    rows = []
    if args.rescore:
        with args.rescore.open(newline="") as stream:
            saved = list(csv.DictReader(stream))
        for profile in sorted({r["profile"] for r in saved}):
            rows += grade_rows([r for r in saved if r["profile"] == profile], cases, profile)
    else:
        for profile in args.profiles:
            weight, runtime = runtime_settings(profile, args.threads, args.max_new_tokens, args.timeout_seconds)
            try:
                measured = run_cpp(MODELS[weight], prompts, output/f"{profile}.csv", SimpleNamespace(**runtime), context_budget=2048)
            except RuntimeError as error:
                measured = [dict(id=case["id"], status="error", error=str(error)) for case in cases]
            rows += grade_rows(measured, cases, profile)
            write_combined(output/"all-results.csv", rows)
            write_summary(output, rows, file_sha256(args.fixtures))
    write_combined(output/"all-results.csv", rows)
    write_summary(output, rows, file_sha256(args.fixtures))
    print(f"Strict quality evidence saved to {output}")
    return int(any(row.get("status") == "error" for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
