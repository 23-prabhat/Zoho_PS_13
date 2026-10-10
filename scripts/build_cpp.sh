#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="$project_dir/.venv/bin:$PATH"
dependency_dir=$(find "$project_dir/.deps" -mindepth 1 -maxdepth 1 -type d -name 'openvino_genai_*' -print -quit)

if [[ -z "$dependency_dir" ]]; then
  echo "OpenVINO GenAI C++ archive is missing under $project_dir/.deps" >&2
  exit 1
fi

# setupvars.sh supplies the matching OpenVINO, Tokenizers, and GenAI CMake paths.
set +u
source "$dependency_dir/setupvars.sh"
set -u

"$project_dir/.venv/bin/cmake" --preset release
"$project_dir/.venv/bin/cmake" --build --preset release
