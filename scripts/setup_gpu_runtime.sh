#!/usr/bin/env bash
set -euo pipefail

# Optional Fedora userspace OpenCL runtime, isolated inside this project.
# No root, package installation, kernel module, or permission changes are made.
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
package_dir="$project_dir/.cache/gpu-rpms"
destination="$project_dir/.deps/intel-gpu-runtime"
if [[ "${1:-}" != "" && "${1:-}" != "--from-cache" ]]; then
  echo "Usage: bash scripts/setup_gpu_runtime.sh [--from-cache]" >&2
  exit 2
fi
for required in dnf rpm rpm2cpio cpio readelf python3; do
  command -v "$required" >/dev/null || { echo "Missing command: $required" >&2; exit 1; }
done
if [[ ! $(rpm -E '%fedora') =~ ^[0-9]+$ ]]; then
  echo "This optional bootstrap supports Fedora. Use your distribution's Intel OpenCL runtime on other systems." >&2
  exit 1
fi
mkdir -p "$package_dir" "$destination"
if [[ "${1:-}" != "--from-cache" ]]; then
  dnf download --repo=fedora --repo=updates --setopt="cachedir=$project_dir/.cache/dnf-gpu" \
    --resolve --destdir="$package_dir" intel-opencl
fi
shopt -s nullglob
packages=("$package_dir"/*.rpm)
if [[ ${#packages[@]} -eq 0 ]]; then
  echo "No cached Intel GPU RPMs found. Run without --from-cache to download them." >&2
  exit 1
fi
# Fedora's installed signing keys must trust the downloaded packages.
rpm -K "${packages[@]}"
for package in "${packages[@]}"; do
  (cd "$destination" && rpm2cpio "$package" | cpio -id --quiet --no-absolute-filenames)
done
python3 - "$destination" "$package_dir" <<'PY'
import hashlib, json, re, subprocess, sys
from pathlib import Path
root, packages = map(Path, sys.argv[1:])
driver = next(root.glob('usr/lib64/intel-opencl/libigdrcl.so'), None)
if driver is None:
    raise SystemExit('Intel OpenCL library is missing from the extracted packages')
# Recreate SONAME links normally produced by the system ldconfig RPM trigger.
for library in root.glob('usr/lib64/**/*.so*'):
    if not library.is_file() or library.is_symlink(): continue
    result = subprocess.run(['readelf','-d',str(library)],capture_output=True,text=True)
    match = re.search(r'\(SONAME\).*?\[([^]]+)\]', result.stdout)
    if match:
        link = library.parent / match[1]
        if not link.exists(): link.symlink_to(library.name)
icd = root / 'icd'
icd.mkdir(exist_ok=True)
(icd / 'intel.icd').write_text('libigdrcl.so\n')
(root / 'env.sh').write_text('''# Generated project-local Intel OpenCL environment.
shikai_gpu_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export LD_LIBRARY_PATH="$shikai_gpu_dir/usr/lib64/intel-opencl:$shikai_gpu_dir/usr/lib64:$shikai_gpu_dir/usr/lib64/igc2:${LD_LIBRARY_PATH:-}"
export OCL_ICD_VENDORS="$shikai_gpu_dir/icd"
unset shikai_gpu_dir
''')
records=[]
for package in sorted(packages.glob('*.rpm')):
    with package.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    records.append({'file':package.name,'sha256':digest})
(root / 'manifest.json').write_text(json.dumps({'scope':'project-local Fedora Intel OpenCL userspace runtime', 'packages':records},indent=2)+'\n')
print(f'Intel OpenCL userspace runtime prepared at {root}')
print('Use on a host exposing the Intel DRM render device; no system packages were installed.')
PY
