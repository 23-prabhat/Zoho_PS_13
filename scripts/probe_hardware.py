#!/usr/bin/env python3
"""Read-only GPU readiness diagnostics; does not install drivers or change permissions."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[1]


def command(arguments):
    if shutil.which(str(arguments[0])) is None:
        return {"status":"missing", "output":"command not installed"}
    try:
        environment = os.environ.copy()
        local = PROJECT / ".deps/intel-gpu-runtime"
        if environment.get("SHIKAI_USE_LOCAL_GPU", "1") != "0" and (local / "env.sh").exists():
            directories = [local / "usr/lib64/intel-opencl", local / "usr/lib64", local / "usr/lib64/igc2"]
            environment["LD_LIBRARY_PATH"] = ":".join(map(str, directories)) + ":" + environment.get("LD_LIBRARY_PATH", "")
            environment["OCL_ICD_VENDORS"] = str(local / "icd")
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=10, env=environment)
        return {"status":"ok" if result.returncode == 0 else "error",
                "returncode":result.returncode, "output":(result.stdout + result.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status":"error", "output":str(error)}


def probe():
    runtime = command([str(PROJECT / "scripts/shikai"), "devices"])
    devices = re.findall(r"^\s*●\s+(\S+)\s+(.+)$", runtime["output"], flags=re.MULTILINE)
    gpu_devices = [name for name, _ in devices if name.startswith("GPU")]
    render_nodes = sorted(str(path) for path in Path("/dev/dri").glob("renderD*"))
    report = {
        "openvino":runtime, "devices":[{"id":name, "name":full} for name, full in devices],
        "gpu_devices":gpu_devices, "render_nodes":render_nodes,
        "project_intel_runtime":(PROJECT / ".deps/intel-gpu-runtime/env.sh").exists(),
        "opencl_icds":sorted(str(p) for p in Path("/etc/OpenCL/vendors").glob("*.icd")),
        "pci_graphics":command(["lspci", "-nn", "-d", "::0300"]),
        "opencl":command(["clinfo", "-l"]),
        "nvidia":command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
    }
    manifest = PROJECT / ".deps/intel-gpu-runtime/manifest.json"
    if manifest.exists():
        try: report["project_intel_runtime_manifest"] = json.loads(manifest.read_text())
        except (OSError, ValueError): report["project_intel_runtime_manifest_error"] = "Could not read the local runtime manifest"
    if runtime["status"] != "ok":
        report["gpu_status"] = "runtime_probe_failed"
        report["next_step"] = "Build Shikai and fix the OpenVINO launcher before attempting GPU inference."
    elif gpu_devices:
        report["gpu_status"] = "available"
        report["next_step"] = "Run the devices benchmark suite to compare the same model and prompts on CPU and detected GPUs."
    elif not render_nodes:
        report["gpu_status"] = "unavailable"
        report["next_step"] = ("No DRM render nodes are visible. Check device access on the host or expose GPU devices "
                               "to this environment before changing drivers. No GPU performance or VRAM result is claimed.")
    else:
        report["gpu_status"] = "unavailable"
        report["next_step"] = ("Render nodes exist but OpenVINO exposes no GPU. Check Intel OpenCL compute-runtime "
                               "installation and render-device permissions. NVIDIA CUDA availability alone does not establish OpenVINO support.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-gpu", action="store_true", help="Exit 77 when no OpenVINO GPU is available")
    args = parser.parse_args()
    report = probe()
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")
    if report["openvino"]["status"] != "ok": return 1
    return 77 if args.require_gpu and not report["gpu_devices"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
