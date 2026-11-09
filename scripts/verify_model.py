#!/usr/bin/env python3
"""Validate required assets, provenance, and hashes for a local model."""
import argparse
import hashlib
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REQUIRED_ASSETS = (
    "openvino_model.xml", "openvino_model.bin", "openvino_tokenizer.xml",
    "openvino_tokenizer.bin", "openvino_detokenizer.xml", "openvino_detokenizer.bin",
    "tokenizer_config.json",
)
HASHED_ASSETS = REQUIRED_ASSETS[:-1]


def load_manifest(path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Manifest root must be an object")
    source = manifest.get("source")
    export = manifest.get("export")
    if not isinstance(source, dict) or not isinstance(export, dict):
        raise ValueError("Manifest requires source and export objects")
    for key in ("repository", "checkpoint_path", "license"):
        if not isinstance(source.get(key), str) or not source[key]:
            raise ValueError(f"Manifest source.{key} must be a nonempty string")
    if not isinstance(source.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", source["revision"]):
        raise ValueError("Manifest source.revision must pin a full 40-character commit hash")
    if not isinstance(source.get("checkpoint_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", source["checkpoint_sha256"]):
        raise ValueError("Manifest requires a valid source.checkpoint_sha256")
    if not isinstance(export.get("path"), str) or not export["path"]:
        raise ValueError("Manifest export.path must be a nonempty string")
    if export.get("weight_format") not in ("int4", "int8", "fp16"):
        raise ValueError("Manifest export.weight_format must be int4, int8, or fp16")
    hashes = export.get("sha256")
    if not isinstance(hashes, dict) or not set(HASHED_ASSETS).issubset(hashes):
        raise ValueError("Manifest must hash every model/tokenizer IR asset")
    for name, digest in hashes.items():
        if not isinstance(name, str) or not name or Path(name).name != name or name in (".", ".."):
            raise ValueError("Manifest hash entries must be plain filenames")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Invalid SHA-256 for {name}")
    return manifest


def verify_hash(path, expected):
    with Path(path).open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch for {path}: expected {expected}, got {actual}")


def require_assets(directory, names):
    directory = Path(directory)
    for name in names:
        if not (directory / name).is_file():
            raise ValueError(f"Missing required model asset: {directory / name}")


def verify_export(manifest, directory):
    require_assets(directory, REQUIRED_ASSETS)
    for name, digest in manifest["export"]["sha256"].items():
        verify_hash(Path(directory) / name, digest)


def verify_source(manifest, directory):
    require_assets(directory, ("config.json", "tokenizer_config.json", "tokenizer.json",
                               "model.safetensors", "LICENSE"))
    verify_hash(Path(directory) / "model.safetensors", manifest["source"]["checkpoint_sha256"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dir", nargs="?", type=Path, help="Override the artifact directory")
    parser.add_argument("--manifest", type=Path,
                        default=PROJECT / "models/manifests/qwen2.5-1.5b-int4.json")
    parser.add_argument("--source", action="store_true", help="Verify the source checkpoint instead of the export")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        relative = manifest["source"]["checkpoint_path"] if args.source else manifest["export"]["path"]
        directory = args.model_dir or PROJECT / relative
        (verify_source if args.source else verify_export)(manifest, directory)
    except (OSError, ValueError) as error:
        parser.exit(1, f"verify_model: {error}\n")
    print(f"Verified assets and SHA-256 hashes at {directory.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
