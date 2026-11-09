#!/usr/bin/env python3
"""Read-only GitHub source inventory; does not stage, commit, push or read local secrets."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from package_submission import PROJECT, source_files

SECRET_PATTERNS = [re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
                   re.compile(rb"AKIA[0-9A-Z]{16}"), re.compile(rb"ghp_[A-Za-z0-9]{36}")]


def git_paths(root, *arguments):
    if not (root/".git").exists():
        return []
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", *arguments],
                            capture_output=True, check=True)
    return [name.decode("utf-8", errors="surrogateescape") for name in result.stdout.split(b"\0") if name]


def audit(root):
    root=Path(root).resolve()
    allowed=source_files(root)
    tracked=git_paths(root, "--cached")
    untracked=git_paths(root, "--others", "--exclude-standard")
    unexpected_tracked=[name for name in tracked if (root/name).exists() and name not in allowed]
    unexpected_untracked=[name for name in untracked if name not in allowed]
    secret_findings=[]
    for name,path in allowed.items():
        if path.is_symlink():
            secret_findings.append(dict(path=name,reason="Source symlink"))
            continue
        data=path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            secret_findings.append(dict(path=name,reason="Possible secret material; inspect before publishing"))
    return dict(scope="Current files and index only; historical commits and remote repository not certified",
        recommended_files=sorted(allowed), recommended_count=len(allowed),
        new_public_files=sorted(set(untracked)&set(allowed)),
        tracked_paths_to_review=sorted(unexpected_tracked), unexpected_untracked=sorted(unexpected_untracked),
        pending_deletions=sorted(name for name in tracked if not (root/name).exists()),
        secret_findings=secret_findings,
        passed=not (unexpected_tracked or unexpected_untracked or secret_findings),
        excluded=["model weights/checkpoints", "SDKs", "virtual environments", "build products", "caches",
                  "credentials and keys", "submission PDF/ZIP and private authoring material", "raw unreviewed runs"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=PROJECT)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--write-list",type=Path,help="Write the exact reviewed publication list")
    parser.add_argument("--write-pathspec",type=Path,help="Write NUL-delimited literal Git paths; does not stage anything")
    args=parser.parse_args()
    result=audit(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+"\n")
    if args.write_list or args.write_pathspec:
        if not result["passed"]:parser.error("Resolve publication findings before generating staging paths")
        if args.write_list:
            args.write_list.parent.mkdir(parents=True,exist_ok=True)
            args.write_list.write_text("PUBLISH THESE REVIEWED SOURCE/EVIDENCE FILES\n\n"+"\n".join(result["recommended_files"])+
                "\n\nTRACKED DELETIONS TO INCLUDE\n"+"\n".join(result["pending_deletions"])+"\n\nKEEP LOCAL\n"+
                "\n".join(result["excluded"])+"\n")
        if args.write_pathspec:
            args.write_pathspec.parent.mkdir(parents=True,exist_ok=True)
            args.write_pathspec.write_bytes(b"".join(os.fsencode(":(literal)"+name)+b"\0" for name in
                result["recommended_files"]+result["pending_deletions"]))
    print(json.dumps({k:v for k,v in result.items() if k not in ("recommended_files","new_public_files")},indent=2))
    return int(not result["passed"])


if __name__=="__main__":raise SystemExit(main())
