# Local model artifacts

`source/` stores the downloaded Qwen checkpoint. `qwen2.5-1.5b/{fp16,int8,int4}/`
stores the validated OpenVINO exports. Large files are intentionally ignored by Git.

Validated artifact sizes:

- INT4: 936,967,911 bytes (about 894 MiB)
- INT8: 1,568,203,195 bytes (about 1.5 GiB)
- FP16: 3,108,814,933 bytes (about 2.9 GiB)

All three variants passed local CPU generation through the OpenVINO GenAI C++
application. Their provenance, hashes, and smoke-test state are under `manifests/`.

Downloading and exporting may use the network once. The deployed C++ executable must
load only these local directories and must not call Hugging Face or any hosted API.

The pinned source checkpoint is downloaded at revision
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. The validated INT4 export can be
recreated offline with `scripts/export_models.sh int4` after the export environment
has been installed. See `models/manifests/qwen2.5-1.5b-int4.json` for hashes and the
successful CPU smoke test.
