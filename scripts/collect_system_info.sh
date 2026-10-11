#!/usr/bin/env bash
set -euo pipefail

echo "timestamp=$(date --iso-8601=seconds)"
echo "kernel=$(uname -srmo)"
echo "os=$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release | tr -d '\"')"
echo "cpu=$(lscpu | sed -n 's/^Model name:[[:space:]]*//p')"
echo "logical_cpus=$(nproc)"
echo "memory=$(free -h | awk '/^Mem:/ {print $2}')"
echo "compiler=$(g++ --version | head -1)"
echo "cmake=$($(dirname "$0")/../.venv/bin/cmake --version | head -1)"
echo "ninja=$($(dirname "$0")/../.venv/bin/ninja --version)"
"$(dirname "$0")/../.venv/bin/python" - <<'PY'
import openvino, openvino_genai
print(f"openvino={openvino.__version__}")
print(f"openvino_genai={openvino_genai.__version__}")
PY
