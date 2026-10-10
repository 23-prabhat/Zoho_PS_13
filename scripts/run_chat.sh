#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dependency_dir=$(find "$project_dir/.deps" -mindepth 1 -maxdepth 1 -type d -name 'openvino_genai_*' -print -quit)
user_arguments=("$@")

if [[ -z "$dependency_dir" ]]; then
  echo "OpenVINO GenAI C++ archive is missing under $project_dir/.deps" >&2
  exit 1
fi

set +u
source "$dependency_dir/setupvars.sh"
set -u
set -- "${user_arguments[@]}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

exec "$project_dir/build/release/shikai" chat \
  --model "$project_dir/models/qwen2.5-1.5b/int4" "$@"
