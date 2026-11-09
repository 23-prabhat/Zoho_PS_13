# Weight quantization and model provenance

All variants use Qwen2.5-1.5B-Instruct revision
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. The model card lists 1.54B total
parameters, within the problem's 1–3B range. The checkpoint and exported model/tokenizer
IR hashes are recorded in [manifests](../models/manifests/README.md).

Optimum Intel/NNCF exports INT4, INT8 and FP16. INT4 uses group size 128 and ratio
1.0. AWQ calibration is not enabled; AWQ is related literature, not an implemented
algorithm. Weight compression does not force all activations, operations or KV
state to the same precision.

| Weights | Export-directory size | Mean decode rate | Mean lifetime peak RSS |
|---|---:|---:|---:|
| INT4 | 893.6 MiB | 14.44 tokens/s | 1961.95 MiB |
| INT8 | 1495.6 MiB | 9.62 tokens/s | 3113.25 MiB |
| FP16 | 2964.8 MiB | 5.34 tokens/s | 6291.66 MiB |

The October precision workload used three prompts, five measured repetitions per
format, one warmup per prompt and up to 128 output tokens. INT4 supports the default
low-memory CPU deployment on this laptop. These figures are workload specific and
do not establish equal answer quality. See [raw evidence](../results/validated-20261020/performance-final-20261011/).

The later strict comparison passed 7/22 objective fixtures for INT4/auto and 9/22
for INT8/auto, FP16/auto and FP16/FP16-cache. These include formatting checks, not
general accuracy; all four long-context fixtures failed for every profile.
[Evaluation methods and saved answers](../guides/answer-quality.md) remain inspectable.

Use the README export and verification commands before changing weight format.
[Primary research sources](../guides/research-notes.md) explain the background.
