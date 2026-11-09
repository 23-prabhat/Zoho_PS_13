# Model manifests

Each JSON file records the immutable Qwen source revision and checkpoint SHA-256,
upstream license, exported directory, precision, export command, tool versions,
artifact size, hashes of the six model/tokenizer IR files, and the recorded CPU
smoke test. Paths in these manifests are relative to the repository root.

From the repository root, after following the [setup guide](../../README.md):

```bash
.venv/bin/python scripts/verify_model.py --source
.venv/bin/python scripts/verify_model.py
.venv/bin/python scripts/verify_model.py --manifest models/manifests/qwen2.5-1.5b-int8.json
.venv/bin/python scripts/verify_model.py --manifest models/manifests/qwen2.5-1.5b-fp16.json
```

The default manifest describes INT4. An optional positional model directory overrides
the recorded artifact location. `--source` verifies the checkpoint instead of an
export. Use `--help` for details. Verification needs only the Python standard library
and local artifact files; it performs no download or inference.

Hashes identify the validated artifacts, rather than promising byte-identical exports
on every host. If a fresh export differs, inspect the dependency versions, source
revision, export settings and generated content before deliberately updating the
manifest. Run CPU generation and the inference tests before recording a new smoke
result. A manifest entry is historical evidence, not a substitute for a new test.

Store all checkpoint and exported weights under `models/`; they are ignored. Keep
only documentation and manifests here in Git. Required upstream notices are retained
under [third_party/](../../third_party/) and described in
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
