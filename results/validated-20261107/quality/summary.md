# Strict answer-quality comparison

Pass rate for declared objective fixtures, including exact output formatting; not general accuracy.
Open-ended explanations are saved separately and excluded from automatic pass rates.

Each fixture has one greedy response per profile. Repeated deterministic answers are not independent samples.
Profiles use the same prompts, output limit, CPU threads and context budget. Weight and cache settings are recorded separately.

| Profile | Objective pass | Fail | Execution errors | Human review pending |
|---|---:|---:|---:|---:|
| fp16-auto | 9/22 | 13 | 0 | 2 |
| fp16-f16-kv | 9/22 | 13 | 0 | 2 |
| int4-auto | 7/22 | 15 | 0 | 2 |
| int8-auto | 9/22 | 13 | 0 | 2 |

## Category breakdown

| Profile | Category | Pass / objective cases |
|---|---|---:|
| fp16-auto | abstention | 1/1 |
| fp16-auto | arithmetic | 2/3 |
| fp16-auto | extraction | 0/2 |
| fp16-auto | factual | 3/3 |
| fp16-auto | instruction | 3/5 |
| fp16-auto | long-context | 0/4 |
| fp16-auto | structured-output | 0/2 |
| fp16-auto | unit-conversion | 0/2 |
| fp16-f16-kv | abstention | 1/1 |
| fp16-f16-kv | arithmetic | 2/3 |
| fp16-f16-kv | extraction | 0/2 |
| fp16-f16-kv | factual | 3/3 |
| fp16-f16-kv | instruction | 3/5 |
| fp16-f16-kv | long-context | 0/4 |
| fp16-f16-kv | structured-output | 0/2 |
| fp16-f16-kv | unit-conversion | 0/2 |
| int4-auto | abstention | 0/1 |
| int4-auto | arithmetic | 1/3 |
| int4-auto | extraction | 0/2 |
| int4-auto | factual | 3/3 |
| int4-auto | instruction | 3/5 |
| int4-auto | long-context | 0/4 |
| int4-auto | structured-output | 0/2 |
| int4-auto | unit-conversion | 0/2 |
| int8-auto | abstention | 1/1 |
| int8-auto | arithmetic | 2/3 |
| int8-auto | extraction | 0/2 |
| int8-auto | factual | 3/3 |
| int8-auto | instruction | 3/5 |
| int8-auto | long-context | 0/4 |
| int8-auto | structured-output | 0/2 |
| int8-auto | unit-conversion | 0/2 |

## Failed objective checks

- int4-auto/strict-001: Full answer differs from the expected response. Saved answer: "offline private local"
- int4-auto/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- int4-auto/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- int4-auto/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- int4-auto/strict-010: Full answer differs from the expected response. Saved answer: "32"
- int4-auto/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To convert the size of a file from bytes to kilobytes (KiB), you can use the following formula:  \\[ \\text{Size in KiB} = \\frac{\\text{Size in bytes}}{\\text{Bytes per KiB}} \\]  Given that 1 KiB is equal to 1"
- int4-auto/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000000 GB"
- int4-auto/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To calculate the raw storage for exactly 1.5 billion weights using INT4, which uses 4 bits per weight, we need to follow these steps:  1. Determine the number of bits required for 1.5 billion weights. 2. Convert the number of bits to bytes. 3. Convert the number of"
- int4-auto/strict-015: Full answer differs from the expected response. Saved answer: "Reference value: ORBIT-4627"
- int4-auto/strict-016: Full answer differs from the expected response. Saved answer: "The value of `current_code` is `BLUE-205`."
- int4-auto/strict-017: Full answer differs from the expected response. Saved answer: "NOT PROVIDED."
- int4-auto/strict-019: Full answer differs from the expected response. Saved answer: " yet another reference code is HARBOR-6129."
- int4-auto/strict-020: Full answer differs from the expected response. Saved answer: " yeti-1656"
- int4-auto/strict-021: Full answer differs from the expected response. Saved answer: " yet the yet background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int4-auto/strict-022: Full answer differs from the expected response. Saved answer: " currently version: currently version value: currently version value."
- int8-auto/strict-001: Full answer differs from the expected response. Saved answer: "local, private, offline"
- int8-auto/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- int8-auto/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- int8-auto/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- int8-auto/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "The size of the file, when expressed in KiB (kilobytes), is 1 KiB."
- int8-auto/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000000"
- int8-auto/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "60000000000 GB"
- int8-auto/strict-015: Full answer differs from the expected response. Saved answer: "The reference value for the device CPU with precision INT4 is ORBIT-4627."
- int8-auto/strict-016: Full answer differs from the expected response. Saved answer: "The value of current_code is BLUE-205."
- int8-auto/strict-019: Full answer differs from the expected response. Saved answer: "暧昧的代码是暧昧的背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，背景，"
- int8-auto/strict-020: Full answer differs from the expected response. Saved answer: "(background)暧昧的代码段落 background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int8-auto/strict-021: Full answer differs from the expected response. Saved answer: "暧昧的代码如下：  ```csharp using System; using System.Collections.Generic; using System.Linq; using UnityEngine; using UnityEngine.UI;  public namespace {     public background {         public {             public {                 public {                     public {                         public {                             public {                                 public {                                     public {                                         public {                                             public"
- int8-auto/strict-022: Full answer differs from the expected response. Saved answer: "暧昧的语气：抱歉，我当前版本是 background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- fp16-auto/strict-001: Full answer differs from the expected response. Saved answer: "local, private, offline"
- fp16-auto/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- fp16-auto/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- fp16-auto/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- fp16-auto/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "The size of the file, when expressed in KiB, is 1 KiB."
- fp16-auto/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000.0 GB"
- fp16-auto/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "6000000000 GB"
- fp16-auto/strict-015: Full answer differs from the expected response. Saved answer: "The reference value for the device CPU with precision INT4 is ORBIT-4627."
- fp16-auto/strict-016: Full answer differs from the expected response. Saved answer: "The value of current_code is BLUE-205."
- fp16-auto/strict-019: Full answer differs from the expected response. Saved answer: " limp HARBOR-6129"
- fp16-auto/strict-020: Full answer differs from the expected response. Saved answer: "undelete the limp  limp  limp  limp  limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp"
- fp16-auto/strict-021: Full answer differs from the expected response. Saved answer: " limpia. limpia background=\"1\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background"
- fp16-auto/strict-022: Full answer differs from the expected response. Saved answer: " limp: limp=\"1 background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- fp16-f16-kv/strict-001: Full answer differs from the expected response. Saved answer: "local, private, offline"
- fp16-f16-kv/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- fp16-f16-kv/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- fp16-f16-kv/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- fp16-f16-kv/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "The size of the file, when expressed in KiB, is 1 KiB."
- fp16-f16-kv/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000.0 GB"
- fp16-f16-kv/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "6000000000 GB"
- fp16-f16-kv/strict-015: Full answer differs from the expected response. Saved answer: "The reference value for the device CPU with precision INT4 is ORBIT-4627."
- fp16-f16-kv/strict-016: Full answer differs from the expected response. Saved answer: "The value of current_code is BLUE-205."
- fp16-f16-kv/strict-019: Full answer differs from the expected response. Saved answer: " limp HARBOR-6129"
- fp16-f16-kv/strict-020: Full answer differs from the expected response. Saved answer: "undelete the limp  limp  limp  limp  limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp limp"
- fp16-f16-kv/strict-021: Full answer differs from the expected response. Saved answer: " limpia. limpia background=\"1\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background\" background=\"background"
- fp16-f16-kv/strict-022: Full answer differs from the expected response. Saved answer: " limp: limp=\"1 background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"

All raw answers, grader decisions, prompts and native-process metadata accompany this report. A successful evaluation run can contain failed model answers. Execution failures produce a nonzero exit status.
