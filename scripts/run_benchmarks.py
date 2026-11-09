#!/usr/bin/env python3
"""Run Shikai precision, context/KV-cache, and answer-quality experiments."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, re, statistics, subprocess
from copy import copy
from datetime import datetime
from pathlib import Path
from probe_hardware import probe
from gpu_monitor import NvidiaMonitor
from answer_quality import load_cases, summarize

PROJECT = Path(__file__).resolve().parents[1]
SHIKAI = PROJECT / "scripts/shikai"
MODELS = {name: PROJECT / f"models/qwen2.5-1.5b/{name}" for name in ("int4", "int8", "fp16")}

def file_sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("all", "performance", "context", "quality", "threads", "cache", "optimization", "devices"), default="all")
    parser.add_argument("--config", type=Path, default=PROJECT / "configs/benchmark.json")
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--warmup-runs", type=int)
    parser.add_argument("--max-new-tokens", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--device", default="CPU")
    parser.add_argument("--kv-cache-precision", choices=("auto", "u4", "u8", "f16", "bf16", "f32"), default="auto")
    parser.add_argument("--prefix-caching", action="store_true")
    parser.add_argument("--cache-size-gb", type=int, default=0)
    parser.add_argument("--num-kv-blocks", type=int, default=0)
    parser.add_argument("--max-batched-tokens", type=int, default=256)
    parser.add_argument("--eviction-start", type=int, default=32)
    parser.add_argument("--eviction-recent", type=int, default=128)
    parser.add_argument("--eviction-max", type=int, default=672)
    parser.add_argument("--cache-eviction", action="store_true")
    return parser.parse_args()

def run_cpp(model, prompts, output, args, max_tokens=None, context_budget=None):
    command = [str(SHIKAI), "benchmark", "--model", str(model), "--prompts", str(prompts),
        "--output", str(output), "--repetitions", str(args.repetitions),
        "--warmup-runs", str(args.warmup_runs), "--max-new-tokens", str(max_tokens or args.max_new_tokens)]
    if context_budget is not None: command += ["--context-budget", str(context_budget)]
    cache_gb = args.cache_size_gb
    blocks = getattr(args, "num_kv_blocks", 0)
    if args.prefix_caching and not (cache_gb or blocks):
        blocks = 128
    command += ["--threads", str(args.threads), "--device", args.device,
                "--kv-cache-precision", args.kv_cache_precision, "--greedy",
                "--prefix-caching" if args.prefix_caching else "--no-prefix-caching",
                "--cache-eviction" if args.cache_eviction else "--no-cache-eviction",
                "--cache-size-gb", str(cache_gb), "--num-kv-blocks", str(blocks),
                "--max-batched-tokens", str(getattr(args, "max_batched_tokens", 256)),
                "--eviction-start", str(getattr(args, "eviction_start", 32)),
                "--eviction-recent", str(getattr(args, "eviction_recent", 128)),
                "--eviction-max", str(getattr(args, "eviction_max", 672))]
    if getattr(args, "conversation", False): command.append("--conversation")
    process = subprocess.Popen(command, cwd=PROJECT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    nvidia_enabled = args.device.startswith("GPU") and getattr(args, "monitor_nvidia", True)
    monitor = NvidiaMonitor(process.pid, nvidia_enabled).start()
    try:
        stdout, _ = process.communicate(timeout=getattr(args, "timeout_seconds", None))
    except subprocess.TimeoutExpired as error:
        process.terminate()
        try: process.communicate(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.communicate()
        raise RuntimeError(f"Native benchmark exceeded {args.timeout_seconds} seconds") from error
    except BaseException:
        process.terminate()
        try: process.communicate(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.communicate()
        raise
    finally:
        gpu = monitor.stop()
    output.with_suffix(".stdout.txt").write_text(stdout, encoding="utf-8")
    if nvidia_enabled:
        output.with_suffix(".gpu.json").write_text(json.dumps(gpu, indent=2) + "\n")
    if process.returncode != 0:
        with output.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("id", "status", "error"))
            writer.writeheader(); writer.writerow({"id":"benchmark", "status":"error", "error":stdout})
        raise RuntimeError(stdout)
    print(stdout, end="", flush=True)
    with output.open(newline="", encoding="utf-8") as stream:
        result = list(csv.DictReader(stream))
    if not result:
        raise RuntimeError(f"Native benchmark returned no rows: {output}")
    precision = model.name
    manifest = json.loads((PROJECT / f"models/manifests/qwen2.5-1.5b-{precision}.json").read_text())
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True, stderr=subprocess.DEVNULL).strip()
        git_dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=PROJECT, text=True, stderr=subprocess.DEVNULL).strip())
    except (OSError, subprocess.CalledProcessError):
        git_commit, git_dirty = "unavailable", "unknown"
    binary = Path(os.environ.get("SHIKAI_BINARY", str(PROJECT / "build/release/shikai")))
    if not binary.is_absolute(): binary = PROJECT / binary
    metadata = {"run_id": output.parent.name, "timestamp": datetime.now().astimezone().isoformat(),
        "git_commit": git_commit, "git_dirty": git_dirty,
        "binary_sha256": file_sha256(binary) if binary.is_file() else "unavailable",
        "model_revision": manifest["source"]["revision"],
        "artifact_hash": manifest["export"]["sha256"]["openvino_model.bin"],
        "weight_format": precision, "runtime_version": "2026.4.1",
        "thread_setting": str(args.threads), "kv_cache_precision":args.kv_cache_precision,
        "cache_policy": f"prefix={'on' if args.prefix_caching else 'off'};eviction={'on' if args.cache_eviction else 'off'};size_gb={cache_gb};blocks={blocks}",
        "status": "ok", "error": ""}
    output.with_suffix(".metadata.json").write_text(json.dumps({
        **metadata, "command":command, "binary":str(binary),
        "prompts_sha256":file_sha256(prompts),
        "runtime_config":json.loads((PROJECT / "configs/default.json").read_text()),
        "model_manifest_sha256":file_sha256(PROJECT / f"models/manifests/qwen2.5-1.5b-{precision}.json")
    }, indent=2) + "\n")
    if nvidia_enabled:
        metadata.update(gpu_process_run_peak_vram_mib=gpu["process_peak_vram_mib"],
                        gpu_device_run_avg_util_percent=gpu["device_mean_util_percent"],
                        gpu_monitor_samples=len(gpu["samples"]), gpu_monitor_scope=gpu["scope"],
                        gpu_monitor_error=gpu["error"])
    for row in result: row.update(metadata)
    fields = list(result[0])
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(result)
    return result


def optimization_suite(run_dir, args):
    """Same short/long prompts and quality fixtures for CPU and cache comparisons."""
    (run_dir / "hardware.json").write_text(json.dumps(probe(), indent=2) + "\n")
    records = [json.loads(line) for line in (PROJECT / "benchmarks/prompts.jsonl").read_text().splitlines() if line]
    records.append({"id":"long-context", "prompt":" ".join(["cache"] * 990) + " Explain KV cache briefly."})
    prompts = run_dir / "optimization-prompts.jsonl"
    write_jsonl(prompts, records)
    quality_path, quality = comparison_quality(run_dir)
    rows = []
    settings = (("cpu-runtime", 0, "auto"), ("cpu-4threads", 4, "auto"),
                ("cpu-4threads-u8", 4, "u8"), ("cpu-4threads-f16", 4, "f16"))
    for profile, threads, precision in settings:
        case = copy(args); case.threads = threads; case.device = "CPU"; case.kv_cache_precision = precision
        # Keep cache policy constant so thread/cache precision are the only changes.
        case.prefix_caching = False; case.cache_eviction = False; case.cache_size_gb = 0; case.num_kv_blocks = 0
        for workload, path, tokens in (("performance", prompts, args.max_new_tokens),
                                       ("quality", quality_path, max(128, args.max_new_tokens))):
            workload_args = copy(case)
            if workload == "quality":
                # Greedy repeated answers add no independent quality evidence.
                workload_args.repetitions = 1; workload_args.warmup_runs = 0
            try:
                result = run_cpp(MODELS["int4"], path, run_dir / f"{profile}-{workload}.csv", workload_args, max_tokens=tokens)
            except RuntimeError as error:
                rows.append(dict(suite="optimization", profile=profile, workload=workload, status="error",
                                 device="CPU", kv_cache_precision=precision, thread_setting=str(threads), error=str(error)))
                print(f"{profile}/{workload} failed: {error}", flush=True)
                continue
            for row in result:
                row.update(suite="optimization", profile=profile, workload=workload, precision="int4")
                if workload == "quality":
                    score, _ = quality_score(row["response"], quality[row["id"]]["expected_points"])
                    row["quality_score"] = str(score)
            rows += result
    return rows


def comparison_quality(run_dir):
    records = [json.loads(line) for line in (PROJECT / "benchmarks/quality_cases.jsonl").read_text().splitlines() if line]
    records.append(dict(id="quality-long-recall", category="long-context",
        prompt="Remember the reference code HARBOR-6129.\n" + "background " * 990 +
               "\nReturn only the reference code stated at the start.", expected_points=["harbor", "6129"]))
    path = run_dir / "comparison-quality.jsonl"
    write_jsonl(path, records)
    return path, {case["id"]:case for case in records}


def device_suite(run_dir, args):
    hardware = probe()
    (run_dir / "hardware.json").write_text(json.dumps(hardware, indent=2) + "\n")
    rows = []
    quality_path, quality = comparison_quality(run_dir)
    for device in ["CPU", *hardware["gpu_devices"]]:
        case = copy(args); case.device = device
        case.monitor_nvidia = any(d["id"] == device and "nvidia" in d["name"].lower() for d in hardware["devices"])
        if device.startswith("GPU"): case.threads = 0
        for workload, path, tokens in (("performance", PROJECT / "benchmarks/prompts.jsonl", args.max_new_tokens),
                                      ("quality", quality_path, max(128, args.max_new_tokens))):
            workload_args = copy(case)
            if workload == "quality": workload_args.repetitions = 1; workload_args.warmup_runs = 0
            try:
                result = run_cpp(MODELS["int4"], path,
                    run_dir / f"device-{device.replace('.', '-')}-{workload}.csv", workload_args, max_tokens=tokens)
                for row in result:
                    row.update(suite="devices", precision="int4", workload=workload)
                    if workload == "quality":
                        score, _ = quality_score(row["response"], quality[row["id"]]["expected_points"])
                        row["quality_score"] = str(score)
                rows += result
            except RuntimeError as error:
                rows.append(dict(suite="devices", device=device, workload=workload, status="error", error=str(error)))
    if not hardware["gpu_devices"]:
        rows.append(dict(suite="devices", device="GPU", status="skipped", error=hardware["next_step"]))
    return rows

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
    # The largest input fixture needs output capacity beyond its input target.
    budget = max(case["target_input_tokens"] for case in cases) + 32
    result = run_cpp(MODELS["int4"], prompts, run_dir / "context-int4.csv", args,
                     max_tokens=32, context_budget=budget)
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
    from evaluate_quality import grade_rows
    cases = load_cases()
    case_path = run_dir / "strict-quality-prompts.jsonl"
    write_jsonl(case_path, [dict(id=case["id"], prompt=case["prompt"]) for case in cases])
    rows = []
    for precision, model in MODELS.items():
        if not model.exists(): continue
        case_args = copy(args)
        case_args.repetitions = 1; case_args.warmup_runs = 0
        try:
            result = run_cpp(model, case_path, run_dir / f"quality-{precision}.csv", case_args,
                             max_tokens=args.max_new_tokens)
        except RuntimeError as error:
            result = [dict(id=case["id"], status="error", error=str(error)) for case in cases]
        graded = grade_rows(result, cases, precision)
        for row in graded: row.update(suite="quality", precision=precision)
        rows += graded
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
        case = copy(args); case.prefix_caching = enabled; case.cache_eviction = False
        case.num_kv_blocks = getattr(args, "num_kv_blocks", 0) if enabled else 0
        case.cache_size_gb = (args.cache_size_gb or (0 if case.num_kv_blocks else 1)) if enabled else 0
        case.repetitions = 3; case.warmup_runs = 0
        result = run_cpp(MODELS["int4"], prompt_path, run_dir / f"prefix-{'on' if enabled else 'off'}.csv", case, max_tokens=32)
        for row in result: row.update(suite="cache", precision="int4", experiment="prefix", policy="on" if enabled else "off")
        rows += result
    eviction_prompt = run_dir / "eviction-prompt.jsonl"
    write_jsonl(eviction_prompt, [{"id":"eviction-long", "prompt":" ".join(["memory"] * 1000)}])
    for enabled in (False, True):
        case = copy(args); case.cache_eviction = enabled; case.repetitions = 1; case.warmup_runs = 0
        case.prefix_caching = False; case.cache_size_gb = 0; case.num_kv_blocks = 0
        result = run_cpp(MODELS["int4"], eviction_prompt, run_dir / f"eviction-{'on' if enabled else 'off'}.csv", case, max_tokens=64)
        for row in result: row.update(suite="cache", precision="int4", experiment="eviction", policy="on" if enabled else "off")
        rows += result
    return rows

def write_combined(path, rows):
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

def metric_mean(rows, key):
    values = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
    values = [value for value in values if math.isfinite(value) and value >= 0]
    return f"{statistics.fmean(values):.2f}" if values else "N/A"


def write_report(path, rows):
    performance = [r for r in rows if r["suite"] == "performance"]
    context = [r for r in rows if r["suite"] == "context"]
    quality = [r for r in rows if r["suite"] == "quality"]
    lines = ["# Shikai benchmark summary", "", "Generated from raw C++ OpenVINO GenAI metrics.", "",
             "Unavailable metrics are blank in CSV and shown as N/A here; means exclude them.", ""]
    if performance:
        lines += ["## Precision performance", "", "| Precision | Mean TTFT (ms) | Mean throughput (tok/s) | Mean peak RSS (MiB) |", "|---|---:|---:|---:|"]
        for precision in MODELS:
            group = [r for r in performance if r["precision"] == precision]
            if group:
                lines.append(f"| {precision.upper()} | {metric_mean(group, 'ttft_ms')} | {metric_mean(group, 'throughput_tok_s')} | {metric_mean(group, 'peak_rss_mib')} |")
        lines.append("")
    if context:
        lines += ["## Context length and KV-cache estimate", "", "KV uses the Qwen estimate of 28 KiB per cached token. RSS includes weights and all runtime allocations.", "", "| Input tokens | TTFT (ms) | Throughput (tok/s) | RSS (MiB) | Estimated KV (MiB) |", "|---:|---:|---:|---:|---:|"]
        for r in context:
            lines.append(f"| {r['input_tokens']} | {metric_mean([r], 'ttft_ms')} | {metric_mean([r], 'throughput_tok_s')} | {float(r['rss_mib']):.2f} | {r['estimated_kv_mib']} |")
        lines.append("")
    if quality:
        if any("strict_status" in row for row in quality):
            lines += ["## Strict answer checks", "", "Exact/structured/numeric fixture pass rates include output-format compliance; they are not general model accuracy. Open-ended answers require separate human review.", "",
                "| Precision | Objective pass / cases | Failed | Errors | Pending review |", "|---|---:|---:|---:|---:|"]
            for precision in MODELS:
                group = [r for r in quality if r["precision"] == precision]
                if group:
                    s = summarize(group)
                    lines.append(f"| {precision.upper()} | {s['passed']}/{s['objective_cases']} | {s['failed']} | {s['execution_errors']} | {s['needs_review']} |")
        else:
            lines += ["## Legacy keyword coverage", "", "Historical concept coverage /2 is not correctness or model accuracy. Review saved answers.", "", "| Precision | Mean coverage (0-2) |", "|---|---:|"]
            for precision in MODELS:
                group = [r for r in quality if r["precision"] == precision]
                if group: lines.append(f"| {precision.upper()} | {statistics.fmean(float(r['quality_score']) for r in group):.2f} |")
    resources = [r for r in rows if r.get("status", "ok") == "ok" and r.get("cpu_time_ms")]
    if resources:
        lines += ["", "## Inference resources", "", "CPU 100% means one logical CPU. RSS is sampled every 50 ms during generation; VmHWM is a process-lifetime peak.",
                  "GPU DRM counters are process-wide buffer allocations, not resident VRAM. System GPU buffers can overlap RAM/RSS. Engine percentages sum busy time and may exceed 100%. Missing counters are N/A.", "",
                  "| Setting | Workload | CPU time (ms) | CPU (%) | Sampled RSS peak (MiB) | GPU buffers (MiB) | GPU local buffers (MiB) |", "|---|---|---:|---:|---:|---:|---:|"]
        groups = sorted({(r.get("profile", r.get("device", "CPU") + "/" + r.get("precision", "")), r.get("workload", r["suite"])) for r in resources})
        for setting, workload in groups:
            group = [r for r in resources if r.get("profile", r.get("device", "CPU") + "/" + r.get("precision", "")) == setting and r.get("workload", r["suite"]) == workload]
            values = " | ".join(metric_mean(group, key) for key in ("cpu_time_ms", "cpu_util_percent", "sampled_peak_rss_mib", "gpu_buffer_peak_mib", "gpu_local_peak_mib"))
            lines.append(f"| {setting} | {workload} | {values} |")
    optimization = [r for r in rows if r["suite"] == "optimization" and r.get("status") == "ok"]
    if optimization:
        lines += ["", "## Controlled CPU and KV-cache comparison", "", "KV precision is the requested setting; auto leaves selection to OpenVINO. Quality is a small automatic rubric, not proof of equivalence.", "",
                  "| Profile | Performance tok/s | Performance TTFT (ms) | Quality /2 | Exact quality answers vs runtime |", "|---|---:|---:|---:|---|"]
        baseline = {r["id"]:r["response"] for r in optimization if r["profile"] == "cpu-runtime" and r["workload"] == "quality"}
        for profile in sorted({r["profile"] for r in optimization}):
            perf = [r for r in optimization if r["profile"] == profile and r["workload"] == "performance"]
            q = [r for r in optimization if r["profile"] == profile and r["workload"] == "quality"]
            comparable = [r for r in q if r["id"] in baseline]
            matches = sum(r["response"] == baseline[r["id"]] for r in comparable)
            agreement = f"{matches}/{len(comparable)}" if comparable else "N/A"
            lines.append(f"| {profile} | {metric_mean(perf, 'throughput_tok_s')} | {metric_mean(perf, 'ttft_ms')} | {metric_mean(q, 'quality_score')} | {agreement} |")
    devices = [r for r in rows if r["suite"] == "devices" and r.get("status") == "ok"]
    if devices:
        lines += ["", "## CPU and GPU comparison", "", "Same INT4 model, greedy decoding, prompt fixtures and response limits on each detected device. Quality uses one saved answer per case.", "",
                  "| Device | Performance tok/s | Performance TTFT (ms) | Quality /2 |", "|---|---:|---:|---:|"]
        for device in sorted({r["device"] for r in devices}):
            perf = [r for r in devices if r["device"] == device and r["workload"] == "performance"]
            q = [r for r in devices if r["device"] == device and r["workload"] == "quality"]
            lines.append(f"| {device} | {metric_mean(perf, 'throughput_tok_s')} | {metric_mean(perf, 'ttft_ms')} | {metric_mean(q, 'quality_score')} |")
    failures = [r for r in rows if r.get("status") in ("error", "skipped")]
    if failures:
        lines += ["", "## Errors and skipped comparisons", ""]
        for row in failures:
            message = " ".join(row.get("error", "").split()).replace("|", "\\|")
            lines.append(f"- {row.get('profile', row.get('device', 'run'))}: {row['status']} — {message}")
    nvidia = [r for r in rows if r.get("gpu_process_run_peak_vram_mib") not in (None, "")]
    if nvidia:
        lines += ["", "## NVIDIA whole-process measurements", "",
                  "These samples include model loading, warmup and all generations in each benchmark process. VRAM is PID-matched. GPU utilization is device-wide and may include other clients. See the .gpu.json files for raw samples.", "",
                  "| Device | Process peak VRAM (MiB) | Device mean utilization (%) |", "|---|---:|---:|"]
        for device in sorted({r["device"] for r in nvidia}):
            group = [r for r in nvidia if r["device"] == device]
            peak = max(float(r["gpu_process_run_peak_vram_mib"]) for r in group)
            lines.append(f"| {device} | {peak:.2f} | {metric_mean(group, 'gpu_device_run_avg_util_percent')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    args = arguments()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.repetitions = args.repetitions if args.repetitions is not None else config["repetitions"]
    args.warmup_runs = args.warmup_runs if args.warmup_runs is not None else config["warmup_runs"]
    args.max_new_tokens = args.max_new_tokens if args.max_new_tokens is not None else config["max_new_tokens"]
    if args.repetitions < 1 or args.warmup_runs < 0 or args.max_new_tokens < 1 or args.threads < 0: raise SystemExit("invalid run counts or threads")
    if args.num_kv_blocks < 0 or args.cache_size_gb < 0 or args.max_batched_tokens < 1:
        raise SystemExit("invalid cache capacity or prefill chunk size")
    if args.num_kv_blocks and args.cache_size_gb:
        raise SystemExit("Use only one of --num-kv-blocks and --cache-size-gb")
    run_dir = (args.output or PROJECT / "results" / f"run-{datetime.now():%Y%m%d-%H%M%S}").resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    if args.suite in ("all", "performance"): rows += performance_suite(run_dir, args)
    if args.suite in ("all", "context"): rows += context_suite(run_dir, args)
    if args.suite in ("all", "quality"): rows += quality_suite(run_dir, args)
    if args.suite in ("all", "threads"): rows += thread_suite(run_dir, args)
    if args.suite in ("all", "cache"): rows += cache_suite(run_dir, args)
    if args.suite in ("all", "optimization"): rows += optimization_suite(run_dir, args)
    if args.suite in ("all", "devices"): rows += device_suite(run_dir, args)
    write_combined(run_dir / "all-results.csv", rows)
    write_report(run_dir / "summary.md", rows)
    print(f"Benchmark suite complete: {run_dir}")
    return 1 if any(row.get("status") == "error" for row in rows) else 0

if __name__ == "__main__": raise SystemExit(main())
