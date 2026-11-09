# Strict answer-quality comparison

Pass rate for declared objective fixtures, including exact output formatting; not general accuracy.
Open-ended explanations are saved separately and excluded from automatic pass rates.

Each fixture has one greedy response per profile. Repeated deterministic answers are not independent samples.
Profiles use the same prompts, output limit, CPU threads and context budget. Weight and cache settings are recorded separately.

| Profile | Objective pass | Fail | Execution errors | Human review pending |
|---|---:|---:|---:|---:|
| int4-auto | 7/22 | 15 | 0 | 2 |
| int4-eviction-1024 | 7/22 | 15 | 0 | 2 |
| int4-prefix-128 | 7/22 | 15 | 0 | 2 |
| int4-prefix-256 | 7/22 | 15 | 0 | 2 |
| int4-prefix-64 | 7/22 | 15 | 0 | 2 |
| int4-prefix-u4 | 8/22 | 14 | 0 | 2 |

## Category breakdown

| Profile | Category | Pass / objective cases |
|---|---|---:|
| int4-auto | abstention | 0/1 |
| int4-auto | arithmetic | 1/3 |
| int4-auto | extraction | 0/2 |
| int4-auto | factual | 3/3 |
| int4-auto | instruction | 3/5 |
| int4-auto | long-context | 0/4 |
| int4-auto | structured-output | 0/2 |
| int4-auto | unit-conversion | 0/2 |
| int4-eviction-1024 | abstention | 0/1 |
| int4-eviction-1024 | arithmetic | 1/3 |
| int4-eviction-1024 | extraction | 0/2 |
| int4-eviction-1024 | factual | 3/3 |
| int4-eviction-1024 | instruction | 3/5 |
| int4-eviction-1024 | long-context | 0/4 |
| int4-eviction-1024 | structured-output | 0/2 |
| int4-eviction-1024 | unit-conversion | 0/2 |
| int4-prefix-128 | abstention | 0/1 |
| int4-prefix-128 | arithmetic | 1/3 |
| int4-prefix-128 | extraction | 0/2 |
| int4-prefix-128 | factual | 3/3 |
| int4-prefix-128 | instruction | 3/5 |
| int4-prefix-128 | long-context | 0/4 |
| int4-prefix-128 | structured-output | 0/2 |
| int4-prefix-128 | unit-conversion | 0/2 |
| int4-prefix-256 | abstention | 0/1 |
| int4-prefix-256 | arithmetic | 1/3 |
| int4-prefix-256 | extraction | 0/2 |
| int4-prefix-256 | factual | 3/3 |
| int4-prefix-256 | instruction | 3/5 |
| int4-prefix-256 | long-context | 0/4 |
| int4-prefix-256 | structured-output | 0/2 |
| int4-prefix-256 | unit-conversion | 0/2 |
| int4-prefix-64 | abstention | 0/1 |
| int4-prefix-64 | arithmetic | 1/3 |
| int4-prefix-64 | extraction | 0/2 |
| int4-prefix-64 | factual | 3/3 |
| int4-prefix-64 | instruction | 3/5 |
| int4-prefix-64 | long-context | 0/4 |
| int4-prefix-64 | structured-output | 0/2 |
| int4-prefix-64 | unit-conversion | 0/2 |
| int4-prefix-u4 | abstention | 0/1 |
| int4-prefix-u4 | arithmetic | 1/3 |
| int4-prefix-u4 | extraction | 1/2 |
| int4-prefix-u4 | factual | 3/3 |
| int4-prefix-u4 | instruction | 3/5 |
| int4-prefix-u4 | long-context | 0/4 |
| int4-prefix-u4 | structured-output | 0/2 |
| int4-prefix-u4 | unit-conversion | 0/2 |

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
- int4-prefix-64/strict-001: Full answer differs from the expected response. Saved answer: "offline private local"
- int4-prefix-64/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- int4-prefix-64/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- int4-prefix-64/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- int4-prefix-64/strict-010: Full answer differs from the expected response. Saved answer: "32"
- int4-prefix-64/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To convert the size of a file from bytes to kilobytes (KiB), you can use the following formula:  \\[ \\text{Size in KiB} = \\frac{\\text{Size in bytes}}{\\text{Bytes per KiB}} \\]  Given that 1 KiB is equal to 1"
- int4-prefix-64/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000000 GB"
- int4-prefix-64/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To calculate the raw storage for exactly 1.5 billion weights using INT4, which uses 4 bits per weight, we need to follow these steps:  1. Determine the number of bits required for 1.5 billion weights. 2. Convert the number of bits to bytes. 3. Convert the number of"
- int4-prefix-64/strict-015: Full answer differs from the expected response. Saved answer: "Reference value: ORBIT-4627"
- int4-prefix-64/strict-016: Full answer differs from the expected response. Saved answer: "The value of `current_code` is `BLUE-205`."
- int4-prefix-64/strict-017: Full answer differs from the expected response. Saved answer: "NOT PROVIDED."
- int4-prefix-64/strict-019: Full answer differs from the expected response. Saved answer: " yet another reference code is HARBOR-6129."
- int4-prefix-64/strict-020: Full answer differs from the expected response. Saved answer: " yeti-1656"
- int4-prefix-64/strict-021: Full answer differs from the expected response. Saved answer: " yet the yet background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int4-prefix-64/strict-022: Full answer differs from the expected response. Saved answer: " currently version: currently version value: currently version value."
- int4-prefix-128/strict-001: Full answer differs from the expected response. Saved answer: "offline private local"
- int4-prefix-128/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- int4-prefix-128/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- int4-prefix-128/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- int4-prefix-128/strict-010: Full answer differs from the expected response. Saved answer: "32"
- int4-prefix-128/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To convert the size of a file from bytes to kilobytes (KiB), you can use the following formula:  \\[ \\text{Size in KiB} = \\frac{\\text{Size in bytes}}{\\text{Bytes per KiB}} \\]  Given that 1 KiB is equal to 1"
- int4-prefix-128/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000000 GB"
- int4-prefix-128/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To calculate the raw storage for exactly 1.5 billion weights using INT4, which uses 4 bits per weight, we need to follow these steps:  1. Determine the number of bits required for 1.5 billion weights. 2. Convert the number of bits to bytes. 3. Convert the number of"
- int4-prefix-128/strict-015: Full answer differs from the expected response. Saved answer: "Reference value: ORBIT-4627"
- int4-prefix-128/strict-016: Full answer differs from the expected response. Saved answer: "The value of `current_code` is `BLUE-205`."
- int4-prefix-128/strict-017: Full answer differs from the expected response. Saved answer: "NOT PROVIDED."
- int4-prefix-128/strict-019: Full answer differs from the expected response. Saved answer: " yet another reference code is HARBOR-6129."
- int4-prefix-128/strict-020: Full answer differs from the expected response. Saved answer: " yeti-1656"
- int4-prefix-128/strict-021: Full answer differs from the expected response. Saved answer: " yet the yet background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int4-prefix-128/strict-022: Full answer differs from the expected response. Saved answer: " currently version: currently version value: currently version value."
- int4-prefix-256/strict-001: Full answer differs from the expected response. Saved answer: "offline private local"
- int4-prefix-256/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- int4-prefix-256/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- int4-prefix-256/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- int4-prefix-256/strict-010: Full answer differs from the expected response. Saved answer: "32"
- int4-prefix-256/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To convert the size of a file from bytes to kilobytes (KiB), you can use the following formula:  \\[ \\text{Size in KiB} = \\frac{\\text{Size in bytes}}{\\text{Bytes per KiB}} \\]  Given that 1 KiB is equal to 1"
- int4-prefix-256/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000000 GB"
- int4-prefix-256/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To calculate the raw storage for exactly 1.5 billion weights using INT4, which uses 4 bits per weight, we need to follow these steps:  1. Determine the number of bits required for 1.5 billion weights. 2. Convert the number of bits to bytes. 3. Convert the number of"
- int4-prefix-256/strict-015: Full answer differs from the expected response. Saved answer: "Reference value: ORBIT-4627"
- int4-prefix-256/strict-016: Full answer differs from the expected response. Saved answer: "The value of `current_code` is `BLUE-205`."
- int4-prefix-256/strict-017: Full answer differs from the expected response. Saved answer: "NOT PROVIDED."
- int4-prefix-256/strict-019: Full answer differs from the expected response. Saved answer: " yet another reference code is HARBOR-6129."
- int4-prefix-256/strict-020: Full answer differs from the expected response. Saved answer: " yeti-1656"
- int4-prefix-256/strict-021: Full answer differs from the expected response. Saved answer: " yet the yet background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int4-prefix-256/strict-022: Full answer differs from the expected response. Saved answer: " currently version: currently version value: currently version value."
- int4-prefix-u4/strict-001: Full answer differs from the expected response. Saved answer: "offline services"
- int4-prefix-u4/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- int4-prefix-u4/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- int4-prefix-u4/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- int4-prefix-u4/strict-010: Full answer differs from the expected response. Saved answer: "Output: 42"
- int4-prefix-u4/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To convert the size of a file from bytes to kilobytes (KiB), you can use the following formula:  \\[ \\text{Size in KiB} = \\frac{\\text{Size in bytes}}{\\text{Bytes per KiB}} \\]  Given that 1 KiB = 102"
- int4-prefix-u4/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000000000000000000000000000000000000000000000000000000000"
- int4-prefix-u4/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To calculate the raw storage for exactly 1.5 billion weights using 4 bits per weight, we need to follow these steps:  1. Determine the number of bits required for 1.5 billion weights. 2. Convert the number of bits to bytes. 3. Convert bytes to gigabytes (GB).  Let"
- int4-prefix-u4/strict-016: Full answer differs from the expected response. Saved answer: "The value of `current_code` is `BLUE-205`."
- int4-prefix-u4/strict-017: Full answer differs from the expected response. Saved answer: "NOT PROVIDED."
- int4-prefix-u4/strict-019: Full answer differs from the expected response. Saved answer: " yet another reference code is 6129"
- int4-prefix-u4/strict-020: Full answer differs from the expected response. Saved answer: " yet. yet  yet still not <strong>yet</strong> still <strong>yet</strong> still <strong>yet</strong> still <strong>yet</strong> still <strong>yet</strong> still <strong>yet</strong> still <strong>yet</strong> still <"
- int4-prefix-u4/strict-021: Full answer differs from the expected response. Saved answer: " yet  yet  background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int4-prefix-u4/strict-022: Full answer differs from the expected response. Saved answer: " yet. yet. background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int4-eviction-1024/strict-001: Full answer differs from the expected response. Saved answer: "offline private local"
- int4-eviction-1024/strict-004: Full answer differs from the expected response. Saved answer: "CPU RAM"
- int4-eviction-1024/strict-005: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json {   \"device\": \"CPU\",   \"offline\": true } ```"
- int4-eviction-1024/strict-006: Expected valid JSON with the exact requested keys, types and values; no surrounding prose. Saved answer: "```json [2, 4, 6] ```"
- int4-eviction-1024/strict-010: Full answer differs from the expected response. Saved answer: "32"
- int4-eviction-1024/strict-012: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To convert the size of a file from bytes to kilobytes (KiB), you can use the following formula:  \\[ \\text{Size in KiB} = \\frac{\\text{Size in bytes}}{\\text{Bytes per KiB}} \\]  Given that 1 KiB is equal to 1"
- int4-eviction-1024/strict-013: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "3000000000000 GB"
- int4-eviction-1024/strict-014: Expected only a finite number and a supported unit within the declared tolerance. Saved answer: "To calculate the raw storage for exactly 1.5 billion weights using INT4, which uses 4 bits per weight, we need to follow these steps:  1. Determine the number of bits required for 1.5 billion weights. 2. Convert the number of bits to bytes. 3. Convert the number of"
- int4-eviction-1024/strict-015: Full answer differs from the expected response. Saved answer: "Reference value: ORBIT-4627"
- int4-eviction-1024/strict-016: Full answer differs from the expected response. Saved answer: "The value of `current_code` is `BLUE-205`."
- int4-eviction-1024/strict-017: Full answer differs from the expected response. Saved answer: "NOT PROVIDED."
- int4-eviction-1024/strict-019: Full answer differs from the expected response. Saved answer: " yet another reference code is HARBOR-6129."
- int4-eviction-1024/strict-020: Full answer differs from the expected response. Saved answer: " yeti-1656"
- int4-eviction-1024/strict-021: Full answer differs from the expected response. Saved answer: " yet the yet background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background background"
- int4-eviction-1024/strict-022: Full answer differs from the expected response. Saved answer: " currently version: currently version value: currently version value."

All raw answers, grader decisions, prompts and native-process metadata accompany this report. A successful evaluation run can contain failed model answers. Execution failures produce a nonzero exit status.
