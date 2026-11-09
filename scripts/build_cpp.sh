#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="$project_dir/.venv/bin:$PATH"
dependency_dir="$project_dir/.deps/openvino_genai_ubuntu24_2026.4.1.0_x86_64"

if [[ ! -x "$project_dir/.venv/bin/cmake" || ! -x "$project_dir/.venv/bin/ninja" ]]; then
  echo "Build tools are missing. Create .venv and install requirements/build.lock.txt (or export.lock.txt). See README.md." >&2
  exit 1
fi
if [[ ! -f "$dependency_dir/setupvars.sh" ]]; then
  echo "The pinned OpenVINO GenAI SDK is missing. Run scripts/setup_cpp_runtime.sh first." >&2
  exit 1
fi

# setupvars.sh supplies the matching OpenVINO, Tokenizers, and GenAI CMake paths.
set +u
source "$dependency_dir/setupvars.sh"
set -u

cd "$project_dir"
"$project_dir/.venv/bin/cmake" --preset release
"$project_dir/.venv/bin/cmake" --build --preset release
