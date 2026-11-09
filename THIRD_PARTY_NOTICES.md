# Third-party notices

Shikai uses the following separately licensed model and native dependencies. Copies
of the upstream notices from the validated local artifacts are included in
`third_party/`. These notices do not assign a license to Shikai's own source code.

- **Qwen2.5-1.5B-Instruct**, Qwen team, repository
  `Qwen/Qwen2.5-1.5B-Instruct`, revision
  `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`: Apache-2.0. The checkpoint's license is
  [included here](third_party/qwen2.5-1.5b-instruct/LICENSE). The OpenVINO exports
  convert/compress the original checkpoint into FP16, INT8 and INT4 IR artifacts;
  they are not a separately trained model. The source revision, conversion commands,
  tool versions and resulting artifact hashes are recorded in `models/manifests/`.
- **OpenVINO Runtime 2026.4.1 / OpenVINO GenAI 2026.4.1.0**, Intel Corporation:
  Apache-2.0 for the runtime and GenAI, with separately licensed bundled components.
  [SDK licensing and redistribution notices](third_party/openvino-2026.4.1.0/)
  retain the complete `docs/licensing` directory from the pinned
  `openvino_genai_ubuntu24_2026.4.1.0_x86_64` native archive, including oneDNN,
  oneTBB, runtime and GenAI third-party program notices.
- **OpenVINO Tokenizers 2026.4.1.0**, Intel Corporation: Apache-2.0 with
  separately licensed components; [license and third-party notices](third_party/tokenizers-2026.4.1.0/)
  are copied from the same SDK.

The Python exporter/build environment is pinned in `requirements/export.lock.txt`;
its installed packages retain their upstream licenses in the virtual environment.
The optional Fedora Intel GPU runtime retains package license files under
`.deps/intel-gpu-runtime/usr/share/licenses/` and IGC notices under `usr/lib64/igc2/`.
Its exact downloaded RPM filenames and SHA-256 hashes are recorded by the bootstrap.
Downloaded SDKs, RPMs, virtual environments and model weights are not part of this
source checkout. Keep their original notices with any separately distributed copies.
