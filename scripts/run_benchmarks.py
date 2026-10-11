#!/usr/bin/env python3
"""Run Shikai precision, context/KV-cache, and answer-quality experiments."""
from __future__ import annotations
import argparse, csv, json, re, statistics, subprocess
from copy import copy
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SHIKAI = PROJECT / "scripts/shikai"
MODELS = {name: PROJECT / f"models/qwen2.5-1.5b/{name}" for name in ("int4", "int8", "fp16")}

def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("all", "performance", "context", "quality", "threads", "cache"), default="all")
    parser.add_argument("--config", type=Path, default=PROJECT / "configs/benchmark.json")
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--warmup-runs", type=int)
    parser.add_argument("--max-new-tokens", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--prefix-caching", action="store_true")
    parser.add_argument("--cache-size-gb", type=int, default=0)
    parser.add_argument("--cache-eviction", action="store_true")
    return parser.parse_args()

def run_cpp(model, prompts, output, args, max_tokens=None):
    command = [str(SHIKAI), "benchmark", "--model", str(model), "--prompts", str(prompts),
        "--output", str(output), "--repetitions", str(args.repetitions),
        "--warmup-runs", str(args.warmup_runs), "--max-new-tokens", str(max_tokens or args.max_new_tokens)]
    if args.threads: command += ["--threads", str(args.threads)]
    if args.prefix_caching: command += ["--prefix-caching", "--cache-size-gb", str(args.cache_size_gb or 1)]
    if args.cache_eviction: command += ["--cache-eviction"]
    completed = subprocess.run(command, cwd=PROJECT, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        output.write_text("id,status,error\nbenchmark,error," + json.dumps(completed.stdout) + "\n", encoding="utf-8")
        raise RuntimeError(completed.stdout)
    print(completed.stdout, end="")
    with output.open(newline="", encoding="utf-8") as stream:
        result = list(csv.DictReader(stream))
    precision = model.name
    manifest = json.loads((PROJECT / f"models/manifests/qwen2.5-1.5b-{precision}.json").read_text())
    try: git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError: git_commit = "uncommitted"
    metadata = {"run_id": output.parent.name, "timestamp": datetime.now().astimezone().isoformat(),
        "git_commit": git_commit, "model_revision": manifest["source"]["revision"],
        "artifact_hash": manifest["export"]["sha256"]["openvino_model.bin"],
        "weight_format": precision, "runtime_version": "2026.4.1",
        "thread_setting": str(args.threads or "runtime"),
        "cache_policy": f"prefix={'on' if args.prefix_caching else 'off'};eviction={'on' if args.cache_eviction else 'off'};size_gb={args.cache_size_gb}",
        "status": "ok", "error": ""}
    for row in result: row.update(metadata)
    fields = list(result[0])
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(result)
    return result

def write_jsonl(path, records):
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

def performance_suite(run_dir, args):
    rows = []
    for precision, model in MODELS.items():
        if not model.exists(): continue
        result = run_cpp(model, PROJECT / "benchmarks/prompts.jsonl", run_dir / f"performance-{precision}.csv", args)
        for row in result: row.update(suite="performance", precision=precision)
        rows += result
    return rows

def context_suite(run_dir, args):
    cases = [json.loads(line) for line in (PROJECT / "benchmarks/context_cases.jsonl").read_text().splitlines() if line]
    records = [{"id": case["id"], "prompt": " ".join(["cache"] * max(1, case["target_input_tokens"] - 32))}
               for case in cases]
    prompts = run_dir / "context-prompts.jsonl"
    write_jsonl(prompts, records)
    result = run_cpp(MODELS["int4"], prompts, run_dir / "context-int4.csv", args, max_tokens=32)
    for row in result:
        tokens = int(row["input_tokens"])
        row.update(suite="context", precision="int4", target_input_tokens=row["id"].split("-")[-1],
                   estimated_kv_mib=f"{tokens * 28 / 1024:.2f}")
    return result

def quality_score(answer, expected):
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", answer.lower()).split())
    matched = 0
    for point in expected:
        alternatives = [" ".join(re.sub(r"[^a-z0-9]+", " ", item.lower()).split()) for item in point.split("|")]
        matched += any(alternative in normalized for alternative in alternatives)
    return (2 if matched == len(expected) else 1 if matched else 0), matched

def quality_suite(run_dir, args):
    case_path = PROJECT / "benchmarks/quality_cases.jsonl"
    cases = [json.loads(line) for line in case_path.read_text().splitlines() if line]
    by_id = {case["id"]: case for case in cases}
    rows = []
    for precision, model in MODELS.items():
        if not model.exists(): continue
        result = run_cpp(model, case_path, run_dir / f"quality-{precision}.csv", args,
                         max_tokens=max(96, args.max_new_tokens))
        for row in result:
            case = by_id[row["id"]]
            score, matched = quality_score(row["response"], case["expected_points"])
            row.update(suite="quality", precision=precision, category=case["category"],
                quality_score=str(score), matched_points=str(matched), expected_points=str(len(case["expected_points"])))
        rows += result
    return rows

def thread_suite(run_dir, args):
    rows = []
    for threads in (4, 8, 12):
        case = copy(args); case.threads = threads; case.repetitions = max(2, args.repetitions)
        result = run_cpp(MODELS["int4"], PROJECT / "benchmarks/prompts.jsonl",
                         run_dir / f"threads-{threads}.csv", case, max_tokens=32)
        for row in result: row.update(suite="threads", precision="int4", requested_threads=str(threads))
        rows += result
    return rows

def cache_suite(run_dir, args):
    prompt_path = run_dir / "cache-prompts.jsonl"
    prefix = " ".join(["shared"] * 480)
    write_jsonl(prompt_path, [{"id":"repeated-prefix", "prompt":prefix + " Explain local inference briefly."}])
    rows = []
    for enabled in (False, True):
        case = copy(args); case.prefix_caching = enabled; case.cache_size_gb = 1 if enabled else 0
        case.repetitions = 3; case.warmup_runs = 0
        result = run_cpp(MODELS["int4"], prompt_path, run_dir / f"prefix-{'on' if enabled else 'off'}.csv", case, max_tokens=32)
        for row in result: row.update(suite="cache", precision="int4", experiment="prefix", policy="on" if enabled else "off")
        rows += result
    eviction_prompt = run_dir / "eviction-prompt.jsonl"
    write_jsonl(eviction_prompt, [{"id":"eviction-long", "prompt":" ".join(["memory"] * 1000)}])
    for enabled in (False, True):
        case = copy(args); case.cache_eviction = enabled; case.repetitions = 1; case.warmup_runs = 0
        result = run_cpp(MODELS["int4"], eviction_prompt, run_dir / f"eviction-{'on' if enabled else 'off'}.csv", case, max_tokens=64)
        for row in result: row.update(suite="cache", precision="int4", experiment="eviction", policy="on" if enabled else "off")
        rows += result
    return rows

def write_combined(path, rows):
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

def write_report(path, rows):
    performance = [r for r in rows if r["suite"] == "performance"]
    context = [r for r in rows if r["suite"] == "context"]
    quality = [r for r in rows if r["suite"] == "quality"]
    lines = ["# Shikai benchmark summary", "", "Generated from raw C++ OpenVINO GenAI metrics.", ""]
    if performance:
        lines += ["## Precision performance", "", "| Precision | Mean TTFT (ms) | Mean throughput (tok/s) | Mean peak RSS (MiB) |", "|---|---:|---:|---:|"]
        for precision in MODELS:
            group = [r for r in performance if r["precision"] == precision]
            if group:
                mean = lambda key: statistics.fmean(float(r[key]) for r in group)
                lines.append(f"| {precision.upper()} | {mean('ttft_ms'):.2f} | {mean('throughput_tok_s'):.2f} | {mean('peak_rss_mib'):.2f} |")
        lines.append("")
    if context:
        lines += ["## Context length and KV-cache estimate", "", "KV uses the Qwen estimate of 28 KiB per cached token. RSS includes weights and all runtime allocations.", "", "| Input tokens | TTFT (ms) | Throughput (tok/s) | RSS (MiB) | Estimated KV (MiB) |", "|---:|---:|---:|---:|---:|"]
        for r in context:
            lines.append(f"| {r['input_tokens']} | {float(r['ttft_ms']):.2f} | {float(r['throughput_tok_s']):.2f} | {float(r['rss_mib']):.2f} | {r['estimated_kv_mib']} |")
        lines.append("")
    if quality:
        lines += ["## Automatic answer-quality rubric", "", "0 = no expected point, 1 = partial, 2 = all expected points. Manually review saved responses before final claims.", "", "| Precision | Mean score (0-2) |", "|---|---:|"]
        for precision in MODELS:
            group = [r for r in quality if r["precision"] == precision]
            if group: lines.append(f"| {precision.upper()} | {statistics.fmean(float(r['quality_score']) for r in group):.2f} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    args = arguments()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.repetitions = args.repetitions if args.repetitions is not None else config["repetitions"]
    args.warmup_runs = args.warmup_runs if args.warmup_runs is not None else config["warmup_runs"]
    args.max_new_tokens = args.max_new_tokens if args.max_new_tokens is not None else config["max_new_tokens"]
    if args.repetitions < 1 or args.warmup_runs < 0 or args.max_new_tokens < 1: raise SystemExit("invalid run counts")
    run_dir = (args.output or PROJECT / "results" / f"run-{datetime.now():%Y%m%d-%H%M%S}").resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    if args.suite in ("all", "performance"): rows += performance_suite(run_dir, args)
    if args.suite in ("all", "context"): rows += context_suite(run_dir, args)
    if args.suite in ("all", "quality"): rows += quality_suite(run_dir, args)
    if args.suite in ("all", "threads"): rows += thread_suite(run_dir, args)
    if args.suite in ("all", "cache"): rows += cache_suite(run_dir, args)
    write_combined(run_dir / "all-results.csv", rows)
    write_report(run_dir / "summary.md", rows)
    print(f"Benchmark suite complete: {run_dir}")

if __name__ == "__main__": main()
