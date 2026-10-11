#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if unshare --net true >/dev/null 2>&1; then
  exec unshare --net "$project_dir/scripts/shikai" generate \
    --max-new-tokens 2 --prompt "Say OK"
fi

echo "Network namespaces are not permitted in this environment; offline namespace test skipped." >&2
exit 77
