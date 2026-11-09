#!/usr/bin/env python3
"""Download and verify the checkpoint pinned by a Shikai model manifest."""
import argparse
import os
from pathlib import Path

from verify_model import PROJECT, load_manifest, verify_source


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=PROJECT / "models/manifests/qwen2.5-1.5b-int4.json")
    parser.add_argument("--output", type=Path, help="Override the checkpoint directory")
    parser.add_argument("--local-files-only", action="store_true",
                        help="Use existing files/cache without accessing the network")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        source = manifest["source"]
        destination = args.output or PROJECT / source["checkpoint_path"]
        # Keep Hugging Face state inside the project rather than the user's home.
        os.environ.setdefault("HF_HOME", str(PROJECT / ".cache/huggingface"))
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=source["repository"], revision=source["revision"],
                          local_dir=str(destination), local_files_only=args.local_files_only)
        verify_source(manifest, destination)
    except Exception as error:
        parser.exit(1, f"download_model: {error}\n")
    print(f"Verified pinned checkpoint at {destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
