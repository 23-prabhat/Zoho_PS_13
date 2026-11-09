# Environment

Validated environment; hardware comparison refreshed on 2026-10-20:

- Fedora Linux 44, x86-64, kernel 7.2.9
- GCC/G++ 16.2.1 with C++17
- CMake 4.1.2 and Ninja 1.13.2 from the project virtual environment
- Python 3.14.8
- Intel Core i5-13420H, 8 physical cores / 12 logical CPUs
- Approximately 16 GB installed RAM
- OpenVINO Runtime 2026.4.1
- OpenVINO GenAI 2026.4.1.0
- OpenVINO Tokenizers 2026.4.1.0
- Qwen2.5-1.5B-Instruct INT4, INT8 and FP16 exports on CPU
- Intel UHD integrated GPU: successful INT4 inference through project-local Intel OpenCL
- NVIDIA RTX 3050, 6 GB VRAM: detected via system ICD; model kernel compilation failed

`python -m pip check` reports no broken requirements. The C++ executable was linked
against the matching 2026.4.1 native GenAI bundle and passed an offline generation
smoke test.

Native Fedora execution succeeded; Podman and Ubuntu fallback were not used. The
Intel Ubuntu 24 C++ archive was validated on this Fedora host. The optional local
Intel runtime exposes CPU and Intel GPU to Shikai. Sandboxed runs may hide GPU device
nodes; successful GPU validation ran on the host. Exact RPM versions/hashes and
device/runtime provenance are in
`results/validated-20261020/intel-gpu-20261020/hardware.json`.
The GPU bootstrap installed no system packages or kernel drivers.

## Final validation and clean Ubuntu setup

The November 9 full laptop run passed 28 CTest cases with zero skips or failures,
including real INT4 inference under kernel-enforced network denial. The 43 Python
regressions passed. [Logs and binary identity](../results/validated-20261109/verification/summary.json)
are separate from the historical performance records; the November validation
kernel is 7.2.13.

The native SDK needs the OpenCL ICD loader (`libOpenCL.so.1`) even for CPU use.
Install `ocl-icd-libopencl1` on Ubuntu 24.04 or `ocl-icd` on Fedora. The loader alone
is not a vendor GPU driver and does not require GPU hardware for CPU execution.
A clean hosted Ubuntu build exposed this missing prerequisite; the CI workflow now
installs it explicitly.

[Hosted CI](https://github.com/23-prabhat/Zoho_PS_13/actions/runs/42625836104)
passed compilation, 43 Python tests, six model-free CTest cases and CPU discovery
on the reviewed revision. It does not run model-weight inference or validate GPU
performance. [Setup](../README.md) and [build-only instructions](../CONTRIBUTING.md)
document the dependencies; other platforms remain unvalidated.
