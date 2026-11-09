#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
version=2026.4.1.0
archive="openvino_genai_ubuntu24_${version}_x86_64.tar.gz"
url="https://storage.openvinotoolkit.org/repositories/openvino_genai/packages/2026.4.1/linux/$archive"
expected_sha256=b8ba7b6e5ae7899e63e5e3c7f9d022ad8a4207247521e46c507f6f3ef23ea2c5
download_dir="$project_dir/.cache/downloads"
destination="$project_dir/.deps"

case "${1:-}" in
  --help|-h)
    echo "Usage: scripts/setup_cpp_runtime.sh [--from-cache]"
    echo "Verify and extract the pinned Linux x86-64 SDK. Reuse a valid cached archive without network access."
    exit 0 ;;
  ""|--from-cache) ;;
  *) echo "Usage: scripts/setup_cpp_runtime.sh [--from-cache]" >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then
  echo "Usage: scripts/setup_cpp_runtime.sh [--from-cache]" >&2
  exit 2
fi
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo "This SDK bootstrap supports Linux x86-64. See README.md for the validated platform." >&2
  exit 1
fi
for required in sha256sum tar; do
  command -v "$required" >/dev/null || { echo "Missing command: $required" >&2; exit 1; }
done

mkdir -p "$download_dir" "$destination"
cached_sha256=""
if [[ -f "$download_dir/$archive" ]]; then
  cached_sha256=$(sha256sum "$download_dir/$archive" | cut -d ' ' -f 1)
fi
if [[ "$cached_sha256" != "$expected_sha256" ]]; then
  if [[ "${1:-}" == --from-cache ]]; then
    echo "A verified SDK archive is unavailable at $download_dir/$archive. Run without --from-cache to download it." >&2
    exit 1
  fi
  command -v curl >/dev/null || { echo "Missing command: curl" >&2; exit 1; }
  curl --fail --location --retry 3 --continue-at - --output "$download_dir/$archive" "$url"
fi

actual_sha256=$(sha256sum "$download_dir/$archive" | cut -d ' ' -f 1)
if [[ "$actual_sha256" != "$expected_sha256" ]]; then
  echo "Checksum mismatch for $download_dir/$archive. Remove that cached archive and rerun this script." >&2
  exit 1
fi

tar -xzf "$download_dir/$archive" -C "$destination"
echo "OpenVINO GenAI C++ $version installed under $destination"
