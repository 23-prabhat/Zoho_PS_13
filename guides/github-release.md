# Files to publish on GitHub

Publish the source needed to build, evaluate and reproduce Shikai. The submission
ZIP is a separate college deliverable that includes the report and screenshot
evidence. Downloaded runtime assets are recreated by the setup scripts.

| Publish | Contents |
|---|---|
| `src/`, `include/` | Native C++ application and public interfaces |
| `CMakeLists.txt`, `CMakePresets.json` | Build and test definitions |
| `scripts/`, `tests/` | Setup, launch, benchmark, strict grading, reproduction and tests |
| `configs/`, `benchmarks/` | Runtime profiles, prompt fixtures, graders and rubrics |
| `requirements/` | Pinned Python preparation/build/report dependencies |
| `models/manifests/`, `models/README.md`, `models/source/.gitkeep` | Model provenance, checksums and storage instructions |
| `results/validated-20261020/`, `results/validated-20261103/`, `results/validated-20261107/`, `results/validated-20261109/` | Reviewed evidence snapshots and their checksum indexes |
| `.github/`, `.gitignore`, `.gitattributes`, `.editorconfig` | CI and repository settings |
| `README.md`, `CONTRIBUTING.md`, `guides/` | Setup, use, evaluation and measured limitations |
| `third_party/`, `THIRD_PARTY_NOTICES.md` | Retained upstream dependency/model notices |

| Keep local | Reason |
|---|---|
| `models/source/` checkpoint files and `models/qwen2.5-1.5b/` exports | Large downloaded/generated model artifacts; publish their manifests |
| `.deps/`, `.venv/`, `.cache/`, `build/`, `tmp/`, `output/` | SDKs, environments, caches, binaries, temporary data and submission output |
| `.aws/`, `.agents/`, `.codex/`, `.env*`, private keys and credentials | Machine/account data |
| `docs/`, `plan.md`, `SUBMISSION_READINESS.md` | Private local report authoring and submission planning |
| `SETU20265SemProjectSelection1.pdf`, `zoho_project_list_software.pdf`, the supplied guidelines PDF | Supplied selection/college documents; not application source |
| Unreviewed generated result folders and private chat transcripts | Publish a reviewed, checksummed snapshot instead |
| Report PDF and submission ZIP | College submission artifacts; any public report copy needs a separate privacy/content review |

The report contains student details. It is available in the college ZIP without
being committed to the source repository. No separate license for original code
has been chosen; retained upstream notices describe their respective components.

## Check the exact current inventory

```bash
.venv/bin/python scripts/check_public_files.py --output output/github-file-audit.json \
  --write-list output/GITHUB_FILES.txt --write-pathspec output/github-pathspec.nul
```

The JSON lists every recommended path, new source files, tracked files needing
review, pending deletions and possible secret material. It checks the actual Git
index as well as the working tree: ignoring a file does not remove an already
tracked file. It performs no staging, commits or remote writes. It does not certify
historical commits or remote branch contents.

The submission handoff also produces `output/GITHUB_FILES.txt` and the exact
NUL-separated `output/github-pathspec.nul`. After reviewing that list, the optional
staging command is:

```bash
git add --pathspec-from-file=output/github-pathspec.nul --pathspec-file-nul
git diff --cached --stat
git diff --cached --check
```

The pathspec contains only the reviewed source/evidence allowlist and recorded
tracked deletions. Commit and push after reviewing those staged changes. Check the
destination repository and branch before publishing. The final college ZIP should
be regenerated after source changes with `scripts/package_submission.py`.
