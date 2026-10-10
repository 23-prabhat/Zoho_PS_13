#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin="$project_dir/.venv/bin/python"
source_model="$project_dir/models/source/qwen2.5-1.5b-instruct"

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HOME="$project_dir/.cache/huggingface"
export OV_TELEMETRY_USER_ID_DIR="$project_dir/.cache/openvino"

# Fedora's venv exposes both lib and its lib64 symlink. Optimum scans namespace
# paths and otherwise registers the same `openvino` command twice.
run_optimum() {
  "$python_bin" -c '
import os
import sys

seen = set()
deduplicated = []
for entry in sys.path:
    canonical = os.path.realpath(entry or os.getcwd())
    if canonical not in seen:
        seen.add(canonical)
        deduplicated.append(entry)
sys.path[:] = deduplicated

from optimum.commands.optimum_cli import main
main()
' "$@"
}

precision=${1:-int4}
case "$precision" in
  int4)
    run_optimum export openvino \
      --model "$source_model" \
      --task text-generation-with-past \
      --weight-format int4 \
      --group-size 128 \
      --ratio 1.0 \
      "$project_dir/models/qwen2.5-1.5b/int4"
    ;;
  int8|fp16)
    run_optimum export openvino \
      --model "$source_model" \
      --task text-generation-with-past \
      --weight-format "$precision" \
      "$project_dir/models/qwen2.5-1.5b/$precision"
    ;;
  *)
    echo "Usage: $0 {int4|int8|fp16}" >&2
    exit 2
    ;;
esac
