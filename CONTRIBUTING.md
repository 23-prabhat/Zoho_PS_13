# Contributing to Shikai

Start with the [README](README.md) for supported platforms and a working chat setup.
Use small, focused changes and explain the behavior being changed and how it was
verified. Include the relevant error, configuration and reproduction command when
reporting a problem. Remove private prompt content and credentials from reports.

## Build and test without model downloads

Native unit tests and preparation/reporting regressions do not require Qwen weights,
PyTorch, export tools, a GPU or an API key. They do need the native SDK and a C++17
compiler. From the repository root on Linux x86-64:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements/build.lock.txt
./scripts/setup_cpp_runtime.sh
./scripts/build_cpp.sh
.venv/bin/ctest --preset release -L unit
```

If you already installed `requirements/export.lock.txt`, the build tools are included.
Preparation/reporting tests alone use only the Python standard library:

```bash
python3.14 -m unittest discover -s tests -p 'test_*.py'
```

The native build script works from any working directory and selects the pinned SDK.
It configures a Release build. For a Debug build, source that SDK in your shell, then
run the debug presets:

```bash
source .deps/openvino_genai_ubuntu24_2026.4.1.0_x86_64/setupvars.sh
.venv/bin/cmake --preset debug
.venv/bin/cmake --build --preset debug
SHIKAI_BINARY="$PWD/build/debug/shikai" .venv/bin/ctest --preset debug -L unit
```

CTest passes the built executable to the CLI test harness. `SHIKAI_BINARY` is also
available for manually exercising a custom build through the launcher.

## Checks before a pull request

```bash
.venv/bin/python -m compileall -q scripts tests
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
for file in scripts/*.sh scripts/shikai tests/*.sh; do bash -n "$file"; done
./scripts/build_cpp.sh
.venv/bin/ctest --preset release -L unit
git diff --check
```

For changes to native inference, history, tokenization, metrics or resource handling,
also prepare INT4 using the README and run the full suite:

```bash
.venv/bin/ctest --preset release
```

The `integration` and `reliability` labels perform real generation. The `offline`
case attempts network namespace isolation, then Linux x86-64 seccomp socket denial
if namespaces are unavailable. It skips only if both mechanisms are unavailable.
Report the actual enforcement mode and any skips. Full-suite tests should run
sequentially to avoid competing for RAM and changing resource measurements.

[GitHub CI](.github/workflows/ci.yml) checks Python/shell syntax, script regressions,
native compilation and model-free CTest cases on Ubuntu 24.04. It downloads the
checksum-pinned native SDK, but no model weights. CI does not establish inference
quality, hardware performance or GPU compatibility. Actions use fixed commit hashes;
dependency update pull requests are configured in
[dependabot.yml](.github/dependabot.yml).

## Code organization and style

Keep inference in C++ and preparation/analysis in Python. Add reusable native behavior
to `shikai_core` with an interface under `include/local_llm/`; keep command handling
in `src/main.cpp`. Configuration files belong in `configs/`. Model provenance belongs
in `models/manifests/`.

Follow the surrounding code and [.editorconfig](.editorconfig): UTF-8, LF line endings,
spaces, four spaces in C++/Python and two in shell/JSON/YAML. Preserve diagnostic
messages, distinguish absent measurements from zero, and keep CPU defaults usable
without GPU drivers. Do not reformat unrelated files.

When updating dependencies, validate a fresh environment, native build, model export,
asset hashes and inference before replacing recorded toolchain pins. The minimal
build lock must agree with the build tools in the export lock. Keep the SDK version
in setup, build and launcher scripts synchronized. Do not update historical evidence
to make a new implementation appear to have produced an old result.

## Repository hygiene

Track source, tests, configuration, dependency pins, notices, model manifests and
reviewed public documentation. Keep generated files out of Git:

- `.venv/`, `.deps/`, `.cache/`, `build/`, local CMake state and compiled binaries.
- Downloaded checkpoints and exported model directories under `models/`.
- New measurements under `results/`; only the explicitly allowed evidence snapshot
  is publishable by default.
- `output/`, local submission `docs/`, private PDFs, local planning/review material,
  editor state, logs and transcripts.
- `.env` files, private keys and local credentials. `.env.example` may contain
  placeholders only; the default application needs no API credentials.

Use `git status --short`, `git diff --stat`, and `git diff --cached` to review the
actual changes selected for a commit. Inspect `git ls-files -ci --exclude-standard`
for files already tracked despite ignore rules. `.gitignore` does not remove files
from the index or history and can be bypassed with `git add -f`; never rely on it
as a complete secret scanner.

To publish new evidence, review prompts, machine identifiers, absolute local paths
and sizes, create checksums, document the workload and limitations, then allow its
exact directory in `.gitignore`. Keep CPU RSS, shared GPU buffer allocation and
dedicated VRAM accounting distinct; see the
[benchmark methodology](guides/hardware-and-benchmarks.md).

The curated snapshot's checksums are checked by the script regression suite. Its
files are excluded from Git line-ending normalization in `.gitattributes`; preserve
this policy for new snapshots so cloning does not change the recorded bytes.

Create the submission from current working source, including untracked additions:

```bash
python3 scripts/package_submission.py
```

The packager verifies every archive entry, includes CI/guides and reviewed evidence,
and runs script regressions against an extracted copy. It uses an explicit source
allowlist and requires the final PDF under `output/pdf/`. The manifest identifies
the actual delivered bytes independently of whether the source has been committed.

The source does not yet have a separately selected project license. Preserve all
[third-party notices](THIRD_PARTY_NOTICES.md) when redistributing their components.

Use [strict answer evaluation](guides/answer-quality.md) when changing weights,
cache precision or conversation scheduling. Report exact fixture passes separately
from manual review and preserve failed answers. The
[GitHub publication guide](guides/github-release.md) provides a read-only inventory
and exact staging paths. `scripts/validate_reproduction.py` records isolated
dependency/export/build/offline checks without replacing existing model manifests.
