#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
install_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"

mkdir -p "$install_dir"
ln -sfn "$project_dir/scripts/shikai" "$install_dir/shikai"

echo "Installed Shikai launcher at $install_dir/shikai"
if [[ ":$PATH:" != *":$install_dir:"* ]]; then
  echo "Add this line to your shell configuration:"
  echo "  export PATH=\"$install_dir:\$PATH\""
fi
