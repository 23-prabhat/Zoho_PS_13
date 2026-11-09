#!/usr/bin/env python3
"""Validate an isolated source snapshot, dependency environment, model export and native build.

Defaults install pinned packages and download the pinned checkpoint. Optional
verified local inputs are recorded explicitly; they never count as fresh downloads.
No existing models, build directories, manifests or environments are overwritten.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
from package_submission import PROJECT, source_files


def digest(path):
    with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--prepared-environment",type=Path,help="Use a separately prepared environment; record its origin")
    parser.add_argument("--checkpoint",type=Path,help="Copy and verify a local pinned checkpoint instead of downloading")
    parser.add_argument("--sdk-archive",type=Path,help="Copy a local SDK archive; bootstrap still verifies its SHA-256")
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    source=output/"source"
    source.mkdir()
    record=dict(started_at=datetime.now().astimezone().isoformat(),status="running",stages=[],
        dependency_origin="prepared environment" if args.prepared_environment else "fresh pinned installation",
        checkpoint_origin="verified local copy" if args.checkpoint else "fresh pinned download",
        sdk_origin="verified cached archive" if args.sdk_archive else "fresh pinned download",
        source_files={})
    def save():
        (output/"summary.json").write_text(json.dumps(record,indent=2)+"\n")
    for name,path in source_files(PROJECT).items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        record["source_files"][name]=digest(target)
    env={**os.environ,"PIP_DISABLE_PIP_VERSION_CHECK":"1","PIP_CACHE_DIR":str(output/"pip-cache"),
         "HF_HOME":str(source/".cache/huggingface"),"OV_TELEMETRY_USER_ID_DIR":str(source/".cache/openvino")}
    for key in ("SHIKAI_BINARY", "PYTHONPATH", "PYTHONHOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        env.pop(key,None)
    def run(name,command,timeout=1800):
        log=output/(name+".log")
        started=time.monotonic()
        with log.open("w") as stream:
            process=subprocess.run([str(x) for x in command],cwd=source,env=env,stdout=stream,
                stderr=subprocess.STDOUT,timeout=timeout)
        stage=dict(name=name,command=[str(x) for x in command],returncode=process.returncode,
                   elapsed_seconds=round(time.monotonic()-started,2),log=log.name)
        record["stages"].append(stage);save()
        print(f"{name}: {'passed' if process.returncode==0 else 'failed'}",flush=True)
        if process.returncode:raise RuntimeError(f"{name} failed; inspect {log}")
    save()
    try:
        virtual=source/".venv"
        if args.prepared_environment:
            prepared=args.prepared_environment.resolve()
            if prepared==(PROJECT/".venv").resolve() or not (prepared/"bin/python").is_file():
                raise ValueError("Supply a separate prepared environment, not the project's original .venv")
            virtual.symlink_to(prepared,target_is_directory=True)
            record["prepared_environment"]=str(prepared)
        else:
            run("create-environment",[sys.executable,"-m","venv",virtual])
            run("install-dependencies",[virtual/"bin/python","-m","pip","install","--no-input","--retries","1",
                "--timeout","30","-r",source/"requirements/export.lock.txt"])
        python=virtual/"bin/python"
        run("dependency-consistency",[python,"-m","pip","check"])
        run("installed-versions",[python,"-m","pip","freeze","--all"])
        version_lines=(output/"installed-versions.log").read_text().splitlines()
        versions={name.lower().replace("_","-"):version for line in version_lines if "==" in line
                  for name,version in [line.split("==",1)]}
        for line in (source/"requirements/export.lock.txt").read_text().splitlines():
            match=re.fullmatch(r"([A-Za-z0-9_.-]+)==(\S+)",line.strip())
            if match and versions.get(match[1].lower().replace("_","-"))!=match[2]:
                raise ValueError(f"Prepared dependency differs from lock: {match[1]}")
        record["installed_versions_match_lock"]=True
        run("toolchain",[python,"-c","import sys,platform;print(sys.version);print(platform.platform())"])
        checkpoint=source/"models/source/qwen2.5-1.5b-instruct"
        if args.checkpoint:
            shutil.copytree(args.checkpoint.resolve(),checkpoint,ignore=shutil.ignore_patterns(".cache"))
        else:
            run("checkpoint-download",[python,source/"scripts/download_model.py"],timeout=1800)
        run("source-verification",[python,source/"scripts/verify_model.py","--source"])
        run("int4-export",["bash",source/"scripts/export_models.sh","int4"],timeout=1800)
        export=source/"models/qwen2.5-1.5b/int4"
        sys.path.insert(0,str(source/"scripts"))
        from verify_model import REQUIRED_ASSETS
        for name in REQUIRED_ASSETS:
            if not (export/name).is_file():raise ValueError(f"Export lacks {name}")
        hashes={p.name:digest(p) for p in export.iterdir() if p.is_file()}
        expected=json.loads((source/"models/manifests/qwen2.5-1.5b-int4.json").read_text())["export"]["sha256"]
        record["export_hashes"]=hashes
        record["export_matches_reference_hashes"]=all(hashes.get(k)==v for k,v in expected.items())
        record["original_manifests_modified"]=False
        save()
        if args.sdk_archive:
            cached=source/".cache/downloads";cached.mkdir(parents=True,exist_ok=True)
            shutil.copy2(args.sdk_archive,cached/args.sdk_archive.name)
        run("sdk-bootstrap",["bash",source/"scripts/setup_cpp_runtime.sh",*(["--from-cache"] if args.sdk_archive else [])])
        run("native-build",["bash",source/"scripts/build_cpp.sh"])
        run("model-free-tests",[virtual/"bin/ctest","--preset","release","-L","unit"])
        run("new-export-offline-test",[python,source/"tests/offline_test.py","--output",output/"offline.json"],timeout=120)
        record["native_binary_sha256"]=digest(source/"build/release/shikai")
        record["status"]="passed"
    except Exception as error:
        record.update(status="failed",error=str(error));save();print(error,file=sys.stderr);return 1
    record["finished_at"]=datetime.now().astimezone().isoformat();save()
    print(f"Reproduction evidence: {output}")
    return 0


if __name__=="__main__":raise SystemExit(main())
