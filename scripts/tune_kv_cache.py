#!/usr/bin/env python3
"""Quality-aware KV comparison with fresh conversations and direct cache probes."""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import subprocess
from types import SimpleNamespace

from answer_quality import FIXTURES, load_cases, summarize
from evaluate_quality import PROFILES, grade_rows, runtime_settings, write_summary
from run_benchmarks import MODELS, PROJECT, SHIKAI, file_sha256, run_cpp, write_combined, write_jsonl

KV_PROFILES = ["int4-auto", "int4-prefix-64", "int4-prefix-128", "int4-prefix-256", "int4-prefix-u4", "int4-eviction-1024"]


def conversations():
    result={}
    for name,padding in (("short",0),("long",512)):
        result[name]=[
            dict(id="turn-1",category="acknowledgement",prompt="Remember code HARBOR-6129.\n"+"background "*padding+"\nReply only OK.",grader=dict(kind="exact",expected="OK")),
            dict(id="turn-2",category="recall",prompt="Return only the code I gave you.",grader=dict(kind="exact",expected="HARBOR-6129")),
            dict(id="turn-3",category="acknowledgement",prompt="Replace the remembered code with LANTERN-7842. Reply only OK.",grader=dict(kind="exact",expected="OK")),
            dict(id="turn-4",category="updated-recall",prompt="Return only the current code, after the replacement.",grader=dict(kind="exact",expected="LANTERN-7842"))]
    return result


def mean(rows,key):
    try:
        values=[float(r[key]) for r in rows]
    except (ValueError, TypeError, KeyError):
        return None
    if any(not math.isfinite(value) or value < 0 for value in values):
        return None
    return round(statistics.fmean(values),2) if values else None


def validate_reused_baseline(metadata, measured, prompts_hash, binary_hash, manifest_hash, manifest):
    """Reject stale/incompatible inputs even when Python runs with -O."""
    expected_metadata = dict(prompts_sha256=prompts_hash, binary_sha256=binary_hash,
        model_manifest_sha256=manifest_hash, model_revision=manifest["source"]["revision"],
        artifact_hash=manifest["export"]["sha256"]["openvino_model.bin"],
        weight_format="int4", runtime_version="2026.4.1")
    for key, value in expected_metadata.items():
        if metadata.get(key) != value:
            raise ValueError(f"Baseline provenance differs: {key}")
    command = metadata.get("command", [])
    if "--greedy" not in command or "--do-sample" in command:
        raise ValueError("Baseline must use greedy decoding")
    expected_settings = dict(device="CPU", max_new_tokens="64", thread_setting="4",
        kv_cache_precision="auto", prefix_caching="0", context_budget="2048",
        cache_eviction="0", conversation="0", num_kv_blocks="0", cache_size_gb="0",
        max_num_batched_tokens="256", eviction_start="32", eviction_recent="128", eviction_max="672")
    if not measured:
        raise ValueError("Baseline contains no int4-auto results")
    for row in measured:
        if row.get("status", "ok") != "ok":
            raise ValueError("Baseline contains execution errors")
        for key, value in expected_settings.items():
            if str(row.get(key)) != value:
                raise ValueError(f"Baseline runtime differs: {key}")


def measure_allocation(command, output):
    """Keep probe failures in evidence and let the caller fail the overall run."""
    try:
        process = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True, timeout=120)
        output.with_suffix(".txt").write_text(process.stdout + process.stderr)
        if process.returncode:
            return None
        with output.open(newline="") as stream:
            values = [int(row["cache_allocated_bytes"]) for row in csv.DictReader(stream)]
        if not values or any(value <= 0 for value in values):
            raise ValueError("Allocation probe returned no positive reservation")
        return max(values)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        with output.with_suffix(".txt").open("a") as stream:
            stream.write(f"\nAllocation probe failed: {error}\n")
        return None


def choose_candidates(conversation_rows, quality_rows, allocations):
    baseline_quality = [r for r in quality_rows if r["profile"] == "int4-auto"]
    baseline_conversations = [r for r in conversation_rows if r["profile"] == "int4-auto"]
    quality_ids = {r["id"] for r in baseline_quality}
    def conversation_key(row):
        return row.get("family"), row.get("run"), row["id"]
    conversation_ids = {conversation_key(r) for r in baseline_conversations}
    baseline_valid = bool(quality_ids and conversation_ids) and not any(
        r.get("status") == "error" for r in baseline_quality + baseline_conversations)
    baseline={r["id"]:r for r in quality_rows if r["profile"]=="int4-auto" and r.get("strict_status")=="pass"}
    conversation_baseline={(r.get("family"),r.get("run"),r["id"]) for r in conversation_rows
                           if r["profile"]=="int4-auto" and r.get("strict_status")=="pass"}
    warm_baseline=mean([r for r in conversation_rows if r["profile"]=="int4-auto" and r["id"]!="turn-1" and r.get("status")=="ok"],"ttft_ms")
    cold_baseline=mean([r for r in conversation_rows if r["profile"]=="int4-auto" and r["id"]=="turn-1" and r.get("status")=="ok"],"ttft_ms")
    decisions={}
    for profile in sorted({r["profile"] for r in quality_rows}):
        group=[r for r in quality_rows if r["profile"]==profile]
        conv=[r for r in conversation_rows if r["profile"]==profile]
        by_id={r["id"]:r for r in group}
        regressions=[identity for identity in baseline if by_id.get(identity,{}).get("strict_status")!="pass"]
        conversation_passes={(r.get("family"),r.get("run"),r["id"]) for r in conv if r.get("strict_status")=="pass"}
        conversation_regressions=sorted(conversation_baseline-conversation_passes,key=str)
        warm=mean([r for r in conv if r["id"]!="turn-1" and r.get("status")=="ok"],"ttft_ms")
        cold=mean([r for r in conv if r["id"]=="turn-1" and r.get("status")=="ok"],"ttft_ms")
        errors=sum(r.get("status")=="error" for r in group+conv)
        complete=(len(group) == len(quality_ids) and set(by_id) == quality_ids and
                  len(conv) == len(conversation_ids) and {conversation_key(r) for r in conv} == conversation_ids)
        eligible=(profile!="int4-auto" and baseline_valid and complete and bool(baseline) and not errors and not regressions and not conversation_regressions
                  and warm_baseline is not None and cold_baseline is not None and warm is not None and cold is not None
                  and warm<=warm_baseline*.8 and cold<=cold_baseline*1.25)
        decisions[profile]=dict(quality=summarize(group),conversation=summarize(conv),
            warm_ttft_ms=warm,cold_ttft_ms=cold,regressions_on_baseline_passes=regressions,
            conversation_regressions_on_baseline_passes=conversation_regressions,
            complete_fixture_coverage=complete,
            probe_reserved_bytes=allocations.get(profile),eligible_opt_in_candidate=eligible)
    eligible=[p for p,d in decisions.items() if d["eligible_opt_in_candidate"] and d["probe_reserved_bytes"] is not None]
    selected=min(eligible,key=lambda p:decisions[p]["probe_reserved_bytes"]) if eligible else None
    quality_selected=max(eligible,key=lambda p:(decisions[p]["quality"]["passed"],decisions[p]["conversation"]["passed"],
        -decisions[p]["probe_reserved_bytes"])) if eligible else None
    def objectives(profile):
        d=decisions[profile]
        return (d["quality"]["passed"],d["conversation"]["passed"],-d["warm_ttft_ms"],-d["cold_ttft_ms"],-d["probe_reserved_bytes"])
    frontier=[p for p in eligible if not any(all(a>=b for a,b in zip(objectives(other),objectives(p))) and
        any(a>b for a,b in zip(objectives(other),objectives(p))) for other in eligible if other!=p)]
    return dict(profiles=decisions,experimental_candidate=selected,memory_focused_candidate=selected,
        quality_focused_candidate=quality_selected,eligible_pareto_frontier=frontier,default_change_justified=False,
        selection_rule="No lost baseline objective or conversation passes and no execution errors; follow-up TTFT at least 20% lower and cold TTFT no more than 25% higher. Select least diagnostic reservation among eligible profiles.",
        limits="Finite synthetic fixtures do not prove answer equivalence. Cache-probe reservations are separate from application RSS; default remains unchanged.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles",nargs="+",choices=KV_PROFILES,default=KV_PROFILES)
    parser.add_argument("--repetitions",type=int,default=2)
    parser.add_argument("--baseline-quality",type=Path,help="Reuse an existing int4-auto strict-run CSV with matching fixture hash/settings")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if "int4-auto" not in args.profiles or args.repetitions<1:parser.error("Include int4-auto and positive repetitions")
    output=args.output or PROJECT/"results"/f"kv-quality-{datetime.now():%Y%m%d-%H%M%S}"
    output.mkdir(parents=True,exist_ok=False)
    cases=load_cases()
    quality_prompts=output/"quality-prompts.jsonl"
    write_jsonl(quality_prompts,[dict(id=c["id"],prompt=c["prompt"]) for c in cases])
    fixture_hash=file_sha256(FIXTURES)
    conv_rows=[];quality_rows=[];allocations={}
    families=conversations()
    for profile in args.profiles:
        weight,runtime=runtime_settings(profile,max_new_tokens=8)
        runtime["conversation"]=True
        for family,conversation in families.items():
            prompts=output/f"{family}-conversation.jsonl"
            write_jsonl(prompts,[dict(id=c["id"],prompt=c["prompt"]) for c in conversation])
            for repetition in range(1,args.repetitions+1):
                try:
                    measured=run_cpp(MODELS[weight],prompts,output/f"{profile}-{family}-{repetition}.csv",SimpleNamespace(**runtime),context_budget=2048)
                except RuntimeError as error:
                    measured=[dict(id=c["id"],status="error",error=str(error)) for c in conversation]
                graded=grade_rows(measured,conversation,profile)
                for row in graded:row.update(family=family,run=repetition,suite="kv-conversation")
                conv_rows+=graded
                write_combined(output/"conversation-results.csv",conv_rows)
        if profile=="int4-auto" and args.baseline_quality:
            metadata=json.loads((args.baseline_quality.parent/"int4-auto.metadata.json").read_text())
            with args.baseline_quality.open(newline="") as stream:
                measured=[r for r in csv.DictReader(stream) if r["profile"]=="int4-auto"]
            manifest_path = PROJECT/"models/manifests/qwen2.5-1.5b-int4.json"
            validate_reused_baseline(metadata, measured, file_sha256(quality_prompts),
                file_sha256(PROJECT/"build/release/shikai"), file_sha256(manifest_path),
                json.loads(manifest_path.read_text()))
            (output/"baseline-reuse.json").write_text(json.dumps(dict(path=str(args.baseline_quality),sha256=file_sha256(args.baseline_quality),
                native_metadata=metadata,scope="Earlier independent quality run; conversation timings are fresh"),indent=2)+"\n")
        else:
            _,quality_runtime=runtime_settings(profile,max_new_tokens=64)
            try:
                measured=run_cpp(MODELS[weight],quality_prompts,output/f"{profile}-quality.csv",SimpleNamespace(**quality_runtime),context_budget=2048)
            except RuntimeError as error:
                measured=[dict(id=c["id"],status="error",error=str(error)) for c in cases]
        quality_rows+=grade_rows(measured,cases,profile)
        write_combined(output/"quality-results.csv",quality_rows)
        write_summary(output,quality_rows,fixture_hash)
        probe=output/f"{profile}-allocation.csv"
        command=[str(SHIKAI),"cache-probe","--prompt","Say OK.","--output",str(probe),"--max-new-tokens","8","--repetitions","3","--threads","4",
            "--num-kv-blocks",str(runtime["num_kv_blocks"]),"--kv-cache-precision",runtime["kv_cache_precision"],
            "--prefix-caching" if runtime["prefix_caching"] else "--no-prefix-caching",
            "--cache-eviction" if runtime["cache_eviction"] else "--no-cache-eviction","--eviction-max",str(runtime["eviction_max"])]
        allocations[profile] = measure_allocation(command, probe)
        decision=choose_candidates(conv_rows,quality_rows,allocations)
        (output/"recommendation.json").write_text(json.dumps(decision,indent=2)+"\n")
    print(f"Quality-aware KV evidence saved to {output}")
    return int(any(r.get("status")=="error" for r in conv_rows+quality_rows) or
               any(value is None for value in allocations.values()))


if __name__=="__main__":raise SystemExit(main())
