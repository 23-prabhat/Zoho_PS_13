#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

exec "${SHIKAI_TEST_PYTHON:-$project_dir/.venv/bin/python}" "$project_dir/tests/offline_test.py" "$@"
