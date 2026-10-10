#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
version=2026.4.1.0
archive="openvino_genai_ubuntu24_${version}_x86_64.tar.gz"
url="https://storage.openvinotoolkit.org/repositories/openvino_genai/packages/2026.4.1/linux/$archive"
expected_sha256=b8ba7b6e5ae7899e63e5e3c7f9d022ad8a4207247521e46c507f6f3ef23ea2c5
download_dir="$project_dir/.cache/downloads"
destination="$project_dir/.deps"

mkdir -p "$download_dir" "$destination"
curl --fail --location --continue-at - --output "$download_dir/$archive" "$url"

actual_sha256=$(sha256sum "$download_dir/$archive" | cut -d ' ' -f 1)
if [[ "$actual_sha256" != "$expected_sha256" ]]; then
  echo "Checksum mismatch for $archive" >&2
  exit 1
fi

tar -xzf "$download_dir/$archive" -C "$destination"
echo "OpenVINO GenAI C++ $version installed under $destination"
