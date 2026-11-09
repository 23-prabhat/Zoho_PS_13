#!/usr/bin/env python3
"""Compare bounded KV pools, prefix reuse, precision and eviction in native C++.

Each measured conversation starts in a fresh process. Cold turn 1 and subsequent
turns are reported separately; answers and per-process provenance are retained.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
from types import SimpleNamespace

from run_benchmarks import PROJECT, MODELS, run_cpp, write_combined, write_jsonl, quality_score

PROFILES = {
    "baseline": {},
    "prefix-128": dict(prefix_caching=True, num_kv_blocks=128),
    "prefix-256-chunk64": dict(prefix_caching=True, num_kv_blocks=256, max_batched_tokens=64),
    "prefix-128-u8": dict(prefix_caching=True, num_kv_blocks=128, kv_cache_precision="u8"),
    "prefix-128-u4": dict(prefix_caching=True, num_kv_blocks=128, kv_cache_precision="u4"),
    "eviction-256": dict(cache_eviction=True, eviction_recent=64, eviction_max=256),
    "eviction-1024": dict(cache_eviction=True, eviction_max=1024),
}


def mean(rows, key):
    values = [float(row[key]) for row in rows if row.get(key) not in (None, "")]
    return f"{statistics.fmean(values):.2f}" if values else "N/A"


def report(output, rows):
    lines = ["# KV-cache comparison", "",
        "Each repetition is a fresh native process. All three turns belong to the same conversation. "
        "Cold and follow-up TTFT are separate. RSS includes weights, workspace and allocated cache; "
        "it is not a direct KV allocation counter. Requests record the selected precision, not an observed tensor layout.", "",
        "| Profile | Successful conversations | Cold TTFT ms | Follow-up TTFT ms | Mean process peak RSS MiB | Exact code recall |",
        "|---|---:|---:|---:|---:|---:|"]
    for profile in sorted({row["profile"] for row in rows}):
        group = [row for row in rows if row["profile"] == profile and row.get("status") == "ok" and row.get("workload") == "conversation"]
        cold = [row for row in group if row["id"] == "turn-1"]
        warm = [row for row in group if row["id"] != "turn-1"]
        recall = [row for row in group if row["id"] == "turn-2"]
        matched = sum(row["response"].strip() == "HARBOR-6129" for row in recall)
        lines.append(f"| {profile} | {len(cold)} | {mean(cold, 'ttft_ms')} | {mean(warm, 'ttft_ms')} | "
                     f"{mean(group, 'peak_rss_mib')} | {matched}/{len(recall)} |")
    lines += ["", "Exact code recall is an instruction-following/retention check, not model accuracy. "
        "Compare saved answers and cold-vs-warm latency before choosing a profile. "
        "Eviction can remove useful context and is kept experimental. "
        "Small RSS differences cannot establish KV savings. "
        "The installed LLMPipeline API exposes no prefix-hit or cache-allocation counter."]
    quality = [row for row in rows if row.get("workload") == "quality" and row.get("status") == "ok"]
    if quality:
        baseline = {row["id"]: row["response"] for row in quality if row["profile"] == "baseline"}
        lines += ["", "## Independent quality fixtures", "",
            "One greedy answer per fixture; the concept rubric is heuristic, not accuracy. Exact agreement is descriptive and does not prove correctness.", "",
            "| Profile | Cases | Mean rubric /2 | Exact answers vs baseline | Exact three-word instruction |",
            "|---|---:|---:|---:|---:|"]
        for profile in sorted({row["profile"] for row in quality}):
            group = [row for row in quality if row["profile"] == profile]
            comparable = [row for row in group if row["id"] in baseline]
            matched = sum(row["response"] == baseline[row["id"]] for row in comparable)
            strict = [row for row in group if row["id"] == "quality-003"]
            lines.append(f"| {profile} | {len(group)} | {mean(group, 'quality_score')} | {matched}/{len(comparable)} | "
                f"{sum(row['response'].strip() == 'local private offline' for row in strict)}/{len(strict)} |")
    failures = [row for row in rows if row.get("status") == "error"]
    if failures:
        lines += ["", "## Unsupported profiles / errors", ""]
        for row in failures:
            lines.append(f"- {row['profile']}: {' '.join(row['error'].split())}")
    (output / "summary.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--max-new-tokens", type=int, default=16)
    parser.add_argument("--quality-check", action="store_true", help="Also save independent 128-token quality answers for each profile")
    args = parser.parse_args()
    if args.repetitions < 1 or not 1 <= args.max_new_tokens < 512:
        parser.error("Use positive repetitions and 1..511 output tokens")
    output = args.output or PROJECT / "results" / f"kv-{datetime.now():%Y%m%d-%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    prompts = output / "conversation.jsonl"
    write_jsonl(prompts, [
        dict(id="turn-1", prompt="Remember the code HARBOR-6129.\n" +
             "background " * 480 + "\nReply only OK. The code is HARBOR-6129."),
        dict(id="turn-2", prompt="Return only the reference code I gave you."),
        dict(id="turn-3", prompt="What does KV cache store? Answer in one short sentence."),
    ])
    rows = []
    for profile in args.profiles:
        succeeded = False
        for repetition in range(1, args.repetitions + 1):
            settings = dict(repetitions=1, warmup_runs=0, max_new_tokens=args.max_new_tokens,
                threads=4, device="CPU", kv_cache_precision="auto", prefix_caching=False,
                cache_size_gb=0, num_kv_blocks=0, cache_eviction=False, max_batched_tokens=256,
                eviction_start=32, eviction_recent=128, eviction_max=672, conversation=True)
            settings.update(PROFILES[profile])
            try:
                measured = run_cpp(MODELS["int4"], prompts,
                    output / f"{profile}-{repetition}.csv", SimpleNamespace(**settings), context_budget=2048)
            except RuntimeError as error:
                rows.append(dict(profile=profile, run=repetition, status="error", error=str(error)))
                # Unsupported precision / runtime setup is not retried identically.
                break
            for row in measured:
                row.update(profile=profile, run=repetition, workload="conversation")
            rows += measured
            succeeded = True
            write_combined(output / "all-results.csv", rows)
            report(output, rows)
        if args.quality_check and succeeded:
            settings.update(conversation=False, max_new_tokens=128)
            quality_path = PROJECT / "benchmarks/quality_cases.jsonl"
            expected = {case["id"]: case["expected_points"] for case in
                (json.loads(line) for line in quality_path.read_text().splitlines() if line)}
            try:
                measured = run_cpp(MODELS["int4"], quality_path,
                    output / f"{profile}-quality.csv", SimpleNamespace(**settings), context_budget=2048)
                for row in measured:
                    row.update(profile=profile, workload="quality", run=1,
                        quality_score=quality_score(row["response"], expected[row["id"]])[0])
                rows += measured
            except RuntimeError as error:
                rows.append(dict(profile=profile, workload="quality", status="error", error=str(error)))
    write_combined(output / "all-results.csv", rows)
    report(output, rows)
    print(f"KV comparison saved to {output}")
    return 0 if any(row.get("status") == "ok" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
