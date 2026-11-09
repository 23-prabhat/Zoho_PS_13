# Research basis and implementation decisions

Primary sources were rechecked on 9 November 2026. Literature provides background;
the repository's saved experiments supply its numerical performance claims.

| Primary source | What it establishes | Application to Shikai |
|---|---|---|
| [Qwen2.5 model card](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) and [technical report](https://arxiv.org/abs/2412.15115) | Model family, 1.54B total parameters, grouped-query architecture and checkpoint terms. | Selects a model within the specified range; architecture supports the theoretical KV estimate. |
| [Intel weight-compression documentation](https://docs.openvino.ai/2026/openvino-workflow/model-optimization-guide/weight-compression.html) | Low-bit weight compression and storage/performance trade-offs. | Optimum Intel/NNCF exports the same checkpoint as INT4, INT8 and FP16. |
| [AWQ, Lin et al.](https://arxiv.org/abs/2306.00978) | Activation-aware weight-only quantization research. | Background for low-bit deployment. Shikai does not enable AWQ calibration or claim to implement AWQ. |
| [PagedAttention, Kwon et al.](https://arxiv.org/abs/2309.06180) | Block-based attention-state memory management in serving. | Conceptual basis for understanding OpenVINO's paged runtime; Shikai does not implement vLLM. |
| [Intel continuous-batching guide](https://openvinotoolkit.github.io/openvino.genai/docs/concepts/optimization-techniques/continuous-batching/) | Paged pools, scheduler controls, prefix reuse and chunked prefill. | A native SchedulerConfig exposes bounded blocks/capacity and related options. Installed 2026.4.1 headers define the actual API used. |
| [Intel cache-eviction guide](https://openvinotoolkit.github.io/openvino.genai/docs/concepts/optimization-techniques/kvcache-eviction-algorithm/) | Start/recent/evictable areas, attention scoring and generation-stage eviction. | Exposes NORM_SUM eviction, retains quality failures and avoids claiming prefill savings. |
| [Barad, Aidova and Gorbachev](https://arxiv.org/abs/2311.04951) | OpenVINO speculative-sampling and KV optimization research. | Related work only; the application uses ordinary autoregressive generation. |

The default follows local evidence: INT4 used less process RAM and decoded faster
than FP16 on the declared October workload; CPU decoded faster than Intel UHD on
the separate device workload. Strict November tests show that higher precision
does not solve every model-quality problem. Prefix reuse remains optional because
its latency benefit and answer behavior depend on the workload.

Published throughput numbers from other papers are not used as Shikai measurements.
Cache reservation, process RSS and physical RAM are kept separate. Claims about a
runtime default or online documentation are checked against the pinned installed
headers and recorded settings rather than assumed to apply to every release.
