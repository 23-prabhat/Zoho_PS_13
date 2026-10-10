# Local LLM on OpenVINO

Offline C++17 application for running Qwen2.5-1.5B-Instruct with the OpenVINO GenAI C++ API.

The model is downloaded once from Hugging Face, exported to OpenVINO IR, and then
used completely locally. Hugging Face is not contacted during inference and no API
key is required for this public model.

## Run the validated application

```bash
./scripts/build_cpp.sh
./scripts/run_chat.sh
```

Use `/reset` to clear conversation history and `/exit` to quit. The default model is
`models/qwen2.5-1.5b/int4`; an alternative local export can be supplied with
`./build/release/local-llm --model /path/to/model` after sourcing the SDK's
`setupvars.sh`.

## Recreate the setup

Create a virtual environment with Python 3.11-3.13 (preferred for broad ML package
compatibility), then install the exporter and local Python runtime:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  openvino==2026.4.1 openvino-genai==2026.4.1.0 \
  openvino-tokenizers==2026.4.1.0 optimum-intel nncf \
  huggingface-hub cmake ninja
```

Download the public checkpoint to a project directory. This command downloads model
files; it does not call a hosted inference API:

```bash
hf download Qwen/Qwen2.5-1.5B-Instruct \
  --revision 989aa7980e4cf806f80c7fef2b1adb7bc71aa306 \
  --local-dir models/source/qwen2.5-1.5b-instruct
```

Export it to INT4 OpenVINO IR and install the matching native C++ SDK:

```bash
./scripts/export_models.sh int4
./scripts/setup_cpp_runtime.sh
./scripts/build_cpp.sh
./scripts/run_chat.sh
```

After download/export, disconnecting the network is safe. `run_chat.sh` explicitly
sets Hugging Face and Transformers offline modes.

See `plan.md` for the implementation plan and `models/README.md` for model details.
