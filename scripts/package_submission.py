#!/usr/bin/env python3
"""Package current working source, report and reviewed evidence; verify every byte.

The explicit allowlist includes untracked source without staging or committing it.
Weights, environments, credentials and local authoring material are excluded.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = ("docs/README.md", "docs/architecture.md", "docs/requirements.md",
    "docs/quantization.md", "docs/kv_cache.md", "docs/environment.md",
    "docs/demo_checklist.md", "docs/final_report.md", "docs/benchmark_report.md",
    "docs/assets/precision-throughput.svg", "docs/assets/context-ttft.svg")
ROOT_FILES = (".gitignore", ".editorconfig", ".gitattributes", "CMakeLists.txt",
    "CMakePresets.json", "README.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md",
    "models/README.md", "models/source/.gitkeep", "results/README.md") + PUBLIC_DOCS
SOURCE_FOLDERS = (".github", "src", "include", "scripts", "tests", "configs", "assets/brand",
    "requirements", "benchmarks", "models/manifests", "third_party", "guides",
    "results/validated-20261020", "results/validated-20261103", "results/validated-20261107",
    "results/validated-20261109")
BLOCKED_PARTS = {".git", ".venv", ".deps", ".cache", ".aws", ".codex", ".agents", "__pycache__"}
SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".kdbx"}


def safe_source_path(path):
    return not (BLOCKED_PARTS.intersection(path.parts) or path.suffix.lower() in SENSITIVE_SUFFIXES |
                {".pyc", ".pyo"} or path.name.lower().startswith(".env") or
                path.name.lower() in {"credentials", ".netrc", ".npmrc"})


def source_files(root):
    files = {name: root / name for name in ROOT_FILES
             if (root / name).is_file() and not (root / name).is_symlink() and safe_source_path(Path(name))}
    for folder in SOURCE_FOLDERS:
        for path in sorted((root / folder).rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root)
            if not safe_source_path(relative):
                continue
            if path.stat().st_size > 5 * 1024 * 1024:
                raise ValueError(f"Unexpected large source/evidence file: {relative}")
            files[relative.as_posix()] = path
    return files


def verify_archive(path):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt ZIP entry")
        record = json.loads(archive.read("SUBMISSION_MANIFEST.json"))
        if len(archive.namelist()) != len(set(archive.namelist())) or set(archive.namelist()) != set(record["files"]) | {"SUBMISSION_MANIFEST.json"}:
            raise ValueError("Archive entries differ from manifest")
        for name, expected in record["files"].items():
            if name.startswith("/") or ".." in Path(name).parts or BLOCKED_PARTS.intersection(Path(name).parts):
                raise ValueError(f"Unsafe archive path: {name}")
            data = archive.read(name)
            if len(data) != expected["size_bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise ValueError(f"Manifest mismatch: {name}")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=PROJECT / "output/pdf/PRABHAT-JHA_SWFW_5S_13.pdf")
    parser.add_argument("--output", type=Path, default=PROJECT / "output/PRABHAT-JHA_SWFW_5S_13_PROJECT-FILES.zip")
    args = parser.parse_args()
    if not args.report.is_file():
        parser.error(f"Report is missing: {args.report}")
    sources = source_files(PROJECT)
    files = {"Shikai/" + name: path for name, path in sources.items()}
    files[args.report.name] = args.report
    # Preserve the original captured outputs and figures referenced by the report.
    evidence = PROJECT / "docs/submission"
    for subfolder in ("assets", "academic-assets"):
        for path in sorted((evidence / subfolder).glob("*")):
            if path.is_file() and path.suffix in (".png", ".svg", ".pdf", ".json", ".txt", ".html"):
                files["Shikai/submission-evidence/" + subfolder + "/" + path.name] = path
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip()
        tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=PROJECT).decode().split("\0"))
        source_matches_commit = set(sources).issubset(tracked) and subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *sources], cwd=PROJECT).returncode == 0
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
        source_matches_commit = False
    manifest = dict(created_at=datetime.now().astimezone().isoformat(), entry_report=args.report.name,
        problem_statement="SWFW_5S_13", git_base_commit=commit, git_source_commit=commit,
        source_matches_commit=source_matches_commit,
        source_scope=("Public source matches the recorded Git commit; per-entry hashes identify all delivered files."
                      if source_matches_commit else
                      "Current working source including uncommitted additions; archive hashes identify the delivered version."),
        exclusions=["weights", "SDKs", "environments", "credentials", "private PDFs", "Git metadata", "local authoring scripts"],
        files={})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, path in sorted(files.items()):
                data = path.read_bytes()
                manifest["files"][name] = dict(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                archive.write(path, name)
            archive.writestr("SUBMISSION_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        verify_archive(temporary)
        with tempfile.TemporaryDirectory(prefix="shikai-package-") as folder:
            with zipfile.ZipFile(temporary) as archive:
                archive.extractall(folder)
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], cwd=Path(folder) / "Shikai",
                capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)
    audit = dict(archive=str(args.output), sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
        entries=len(files) + 1, manifest_hashes_verified=True, current_source_files=len(sources),
        packaged_regression_output=result.stdout + result.stderr, report_sha256=hashlib.sha256(args.report.read_bytes()).hexdigest())
    (args.output.parent / "submission-validation.json").write_text(json.dumps(audit, indent=2) + "\n")
    (args.output.parent / "SUBMISSION_CHECKSUMS.txt").write_text(
        f"{audit['sha256']}  {args.output.name}\n{audit['report_sha256']}  pdf/{args.report.name}\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
