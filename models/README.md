# Local model artifacts

`source/` stores the downloaded Qwen checkpoint. `qwen2.5-1.5b/{fp16,int8,int4}/`
stores generated OpenVINO exports. Large files are intentionally ignored by Git.

Downloading and exporting may use the network once. The deployed C++ executable must
load only these local directories and must not call Hugging Face or any hosted API.

The pinned source checkpoint is downloaded at revision
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. The validated INT4 export can be
recreated offline with `scripts/export_models.sh int4` after the export environment
has been installed. See `models/manifests/qwen2.5-1.5b-int4.json` for hashes and the
successful CPU smoke test.
