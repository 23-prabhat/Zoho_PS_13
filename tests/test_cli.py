#!/usr/bin/env python3
"""Black-box CTest cases for the compiled Shikai application."""
import csv, json, os, re, signal, subprocess, sys, tempfile, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT / "scripts/shikai"
FIXTURES = PROJECT / "tests/fixtures"

def run(*arguments, input_text="", timeout=80):
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", NO_COLOR="1")
    return subprocess.run([str(LAUNCHER), *arguments], input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=PROJECT, env=env, timeout=timeout)

def require(condition, message, output=""):
    if not condition: raise AssertionError(f"{message}\n--- output ---\n{output}")

def config_test():
    result = run("--config", str(FIXTURES / "invalid-config.json"))
    require(result.returncode != 0, "invalid configuration unexpectedly succeeded", result.stdout)
    require("context_budget" in result.stdout and "positive integer" in result.stdout,
            "configuration error was not actionable", result.stdout)

def argument_validation_test():
    for option in ("--context-budget", "--max-new-tokens", "--repetitions",
                   "--warmup-runs", "--threads", "--cache-size-gb", "--num-kv-blocks",
                   "--max-batched-tokens", "--eviction-start", "--eviction-recent", "--eviction-max"):
        for value in ("-1", "12oops", "1.5", "999999999999999999999999999999"):
            result = run("generate", option, value, "--prompt", "hello")
            require(result.returncode != 0 and f"{option} requires a nonnegative integer" in result.stdout,
                    f"malformed numeric argument accepted: {option} {value}", result.stdout)
    result = run("generate", "--prompt", "hello", "--threads", "2147483648")
    require(result.returncode != 0 and "runtime integer range" in result.stdout,
            "oversized thread count accepted", result.stdout)
    result = run("generate", "--prompt", "hello", "--prompt-file", "unused.txt")
    require(result.returncode != 0 and "Use only one" in result.stdout,
            "ambiguous prompt sources accepted", result.stdout)
    result = run("generate", "--prompt", "hello", "--threads")
    require(result.returncode != 0 and "--threads requires a value" in result.stdout,
            "launcher masked the missing option value", result.stdout)
    with tempfile.TemporaryDirectory() as temporary:
        for arguments in (("--config", "/missing/shikai.json", "--help"),
                          ("devices", "--config", "/missing/shikai.json")):
            result = subprocess.run([str(LAUNCHER), *arguments], cwd=temporary,
                capture_output=True, text=True, timeout=20)
            require(result.returncode == 0, "discovery depends on runtime configuration", result.stdout + result.stderr)
        for literal in ("--config", "--help", "--prompts"):
            result = subprocess.run([str(LAUNCHER), "generate", "--prompt", literal,
                "--model", str(Path(temporary)/"missing-model")], cwd=temporary,
                capture_output=True, text=True, timeout=20)
            require(result.returncode != 0 and "Missing required model asset" in result.stderr,
                    f"literal prompt text was treated as a flag: {literal}", result.stdout + result.stderr)

def missing_model_test():
    result = run("generate", "--config", str(FIXTURES / "missing-model.json"), "--prompt", "hello")
    require(result.returncode != 0, "missing model unexpectedly succeeded", result.stdout)
    require("Missing required model asset" in result.stdout, "missing asset error not reported", result.stdout)

def context_test():
    prompt = " ".join(["oversized"] * 100)
    result = run("chat", "--config", str(FIXTURES / "small-context.json"), input_text=prompt + "\n/exit\n")
    require(result.returncode == 0, "context test process failed", result.stdout)
    require("Prompt rejected" in result.stdout and "64-token context budget" in result.stdout,
            "oversized prompt was not rejected at configured boundary", result.stdout)

def rejection_history_test():
    prompt = "Remember nonce ZEBRA-741."
    result = run("chat", "--context-budget", "128", "--max-new-tokens", "1",
        input_text=f"{prompt}\n/stats\n" + "oversized " * 150 + f"\n/stats\n{prompt}\n/stats\n/exit\n")
    counts = re.findall(r"Input tokens:\s+(\d+)", result.stdout)
    require(result.returncode == 0 and "Prompt rejected" in result.stdout,
            "oversized request was not cleanly rejected", result.stdout)
    require(len(counts) == 3 and counts[0] == counts[1] and int(counts[2]) > int(counts[0]),
            "rejected prompt changed statistics or discarded committed history", result.stdout)

def generate_context_test():
    prompt = "oversized " * 150
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "prompt.txt"
        source.write_text(prompt)
        prompts = Path(temporary) / "prompts.jsonl"
        prompts.write_text(json.dumps({"id":"oversized", "prompt":prompt}) + "\n")
        cases = [("generate", "--prompt", prompt), ("generate", "--prompt-file", str(source)),
                 ("benchmark", "--prompts", str(prompts), "--output", str(Path(temporary)/"result.csv"))]
        for arguments in cases:
            result = run(*arguments, "--context-budget", "64", "--max-new-tokens", "1")
            require(result.returncode != 0 and "64-token context budget" in result.stdout,
                    "noninteractive generation bypassed its context budget", result.stdout)

def jsonl_test():
    prompt = 'Reply exactly: "HELLO". Path C:\\tmp.\nUnicode: café.'
    identifier = 'quoted,"identifier'
    with tempfile.TemporaryDirectory() as temporary:
        prompts = Path(temporary) / "prompts.jsonl"
        output = Path(temporary) / "results.csv"
        prompts.write_text("\n" + json.dumps({"metadata":{"prompt":"ignore me"},
            "prompt":prompt, "id":identifier}) + "\n", encoding="utf-8")
        benchmark = run("benchmark", "--prompts", str(prompts), "--output", str(output),
                        "--max-new-tokens", "2")
        direct = run("generate", "--prompt", prompt, "--max-new-tokens", "2")
        require(benchmark.returncode == direct.returncode == 0,
                "escaped JSON prompt failed", benchmark.stdout + direct.stdout)
        with output.open(newline="") as stream: rows = list(csv.DictReader(stream))
        counts = re.search(r"\|\s+(\d+) in /", direct.stdout)
        require(len(rows) == 1 and rows[0]["id"] == identifier and counts and
                rows[0]["input_tokens"] == counts[1],
                "JSON escapes or quoted CSV identifier changed the prompt", benchmark.stdout + direct.stdout)
        for invalid in ('{"id":"bad","prompt":"unterminated}', '[]',
                        '{"id":"missing"}', '{"id":1,"prompt":"hello"}',
                        '{"id":"empty","prompt":""}'):
            prompts.write_text("\n" + invalid + "\n")
            result = run("benchmark", "--prompts", str(prompts), "--output", str(output))
            require(result.returncode != 0 and f"{prompts}:2:" in result.stdout,
                    "invalid JSONL record lacked a file/line diagnostic", result.stdout)

def short_metrics_test():
    chat = run("chat", "--max-new-tokens", "1", input_text="Say OK\n/stats\n/exit\n")
    direct = run("generate", "--max-new-tokens", "1", "--prompt", "Say OK")
    require(chat.returncode == direct.returncode == 0 and
            re.search(r"Throughput:\s+N/A tokens/s", chat.stdout) and
            re.search(r"Time per output token:\s+N/A ms/token", chat.stdout) and
            "N/A tok/s" in direct.stdout,
            "one-token responses displayed a fabricated decode metric", chat.stdout + direct.stdout)
    with tempfile.TemporaryDirectory() as temporary:
        prompts = Path(temporary)/"prompts.jsonl"
        output = Path(temporary)/"results.csv"
        prompts.write_text(json.dumps({"id":"short", "prompt":"Say OK"}) + "\n")
        result = run("benchmark", "--prompts", str(prompts), "--output", str(output), "--max-new-tokens", "1")
        require(result.returncode == 0, "short benchmark failed", result.stdout)
        with output.open(newline="") as stream: row = next(csv.DictReader(stream))
        require(row["throughput_tok_s"] == row["tpot_ms"] == "",
                "unavailable decode metrics were not empty CSV cells", result.stdout)

def reset_test():
    result = run("chat", "--max-new-tokens", "8",
        input_text="Reply exactly: BEFORE RESET\n/reset\n/stats\n/exit\n")
    require(result.returncode == 0, "reset test process failed", result.stdout)
    require("Conversation reset." in result.stdout, "reset acknowledgement missing", result.stdout)
    require("No generation statistics yet" in result.stdout, "reset did not clear session statistics", result.stdout)

def fresh_reset_test():
    prompt = "Reply with one word describing the sky."
    after_reset = run("chat", "--max-new-tokens", "4",
        input_text=f"Remember a private nonce: ALBATROSS-928.\n/reset\n{prompt}\n/stats\n/exit\n")
    fresh = run("chat", "--max-new-tokens", "4", input_text=f"{prompt}\n/stats\n/exit\n")
    reset_counts = re.findall(r"Input tokens:\s+([0-9]+)", after_reset.stdout)
    fresh_counts = re.findall(r"Input tokens:\s+([0-9]+)", fresh.stdout)
    require(after_reset.returncode == 0 and fresh.returncode == 0,
            "fresh-engine reset comparison failed", after_reset.stdout + fresh.stdout)
    require(reset_counts and fresh_counts and reset_counts[-1] == fresh_counts[-1],
            "logical reset retained tokens absent from a fresh engine",
            after_reset.stdout + "\n--- fresh engine ---\n" + fresh.stdout)

def metrics_test():
    result = run("chat", "--max-new-tokens", "8",
        input_text="Reply exactly: METRICS OK\n/stats\n/exit\n")
    require(result.returncode == 0, "metrics test process failed", result.stdout)
    for label in ("Input tokens", "Output tokens", "Time to first token", "Throughput", "Peak process RSS"):
        require(label in result.stdout, f"missing metric: {label}", result.stdout)
    values = re.findall(r"Throughput:\s+([0-9.]+) tokens/s", result.stdout)
    require(values and float(values[-1]) > 0, "throughput was not positive", result.stdout)

def resource_metrics_test():
    result = run("chat", "--max-new-tokens", "4", "--threads", "4",
                 input_text="Explain RAM briefly.\n/stats\n/exit\n")
    require(result.returncode == 0, "profiled chat failed", result.stdout)
    for label in ("Generation CPU time", "Average CPU use", "Sampled generation RSS peak", "Resource samples"):
        require(label in result.stdout, f"missing resource metric: {label}", result.stdout)
    values = re.findall(r"Generation CPU time:\s+([0-9.]+) ms", result.stdout)
    require(values and float(values[0]) > 0, "CPU time was not measured", result.stdout)
    require("GPU buffer allocation peak: N/A" in result.stdout,
            "CPU generation should not invent GPU allocation data", result.stdout)

def kv_config_test():
    for precision in ("auto", "u8", "f16"):
        result = run("generate", "--kv-cache-precision", precision, "--threads", "4",
                     "--prompt", "What is 2 plus 2?", "--max-new-tokens", "4")
        require(result.returncode == 0, f"KV precision {precision} failed", result.stdout)
    invalid = run("--kv-cache-precision", "int3")
    require(invalid.returncode != 0 and "kv_cache_precision must be" in invalid.stdout,
            "invalid cache precision was accepted", invalid.stdout)
    with tempfile.TemporaryDirectory() as temporary:
        config = json.loads((PROJECT / "configs/default.json").read_text())
        config["model_path"] = str(PROJECT / "models/qwen2.5-1.5b/int4")
        config["kv_cache_precision"] = "invalid"
        path = Path(temporary)/"config.json"
        path.write_text(json.dumps(config))
        invalid = run("--config", str(path))
        require(invalid.returncode != 0 and "kv_cache_precision must be" in invalid.stdout,
                "invalid JSON precision was accepted", invalid.stdout)
        override = run("generate", "--config", str(path), "--kv-cache-precision", "u8",
                       "--prompt", "Say OK", "--max-new-tokens", "1")
        require(override.returncode == 0, "CLI did not override JSON cache precision", override.stdout)

def smoke_test():
    result = run("generate", "--max-new-tokens", "8", "--prompt", "What is 2 plus 2?")
    require(result.returncode == 0, "real-model generation failed", result.stdout)
    require("Qwen2.5-1.5B-Instruct INT4" in result.stdout, "active model not reported", result.stdout)
    require(re.search(r"\|\s+[1-9][0-9]* in / [1-9][0-9]* out\s+\|", result.stdout) is not None,
            "generation did not report non-empty token counts", result.stdout)

def trimming_test():
    turns = "First answer briefly: what is RAM?\nSecond answer briefly: what is CPU?\n/exit\n"
    result = run("chat", "--context-budget", "80", "--max-new-tokens", "16", input_text=turns)
    require(result.returncode == 0, "trimming test failed", result.stdout)
    require("Context: removed 1 oldest turn(s)." in result.stdout,
            "oldest complete turn was not visibly trimmed", result.stdout)

def continuity_test():
    result = run("chat", "--max-new-tokens", "16",
        input_text="Remember this nonce: ZEBRA-741. Reply remembered.\nWhat nonce did I give you?\n/exit\n")
    require(result.returncode == 0, "continuity test failed", result.stdout)
    require("ZEBRA" in result.stdout and "741" in result.stdout,
            "follow-up did not recall the nonce components", result.stdout)

def cancellation_test():
    process = subprocess.Popen([str(LAUNCHER), "chat", "--max-new-tokens", "256"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        cwd=PROJECT, env={**os.environ, "HF_HUB_OFFLINE":"1", "TRANSFORMERS_OFFLINE":"1"})
    process.stdin.write("Write a very long essay about computer architecture.\n"); process.stdin.flush()
    time.sleep(3.5); process.send_signal(signal.SIGINT); time.sleep(1)
    process.stdin.write("Reply exactly: RECOVERED\n/stats\n/exit\n"); process.stdin.flush()
    output, _ = process.communicate(timeout=80)
    require(process.returncode == 0, "cancelled process did not recover", output)
    require("Generation cancelled; the interrupted turn was not added" in output,
            "cancellation rollback message missing", output)
    require("Last response statistics" in output, "generation after cancellation failed", output)

def missing_tokenizer_test():
    source = PROJECT / "models/qwen2.5-1.5b/int4"
    with tempfile.TemporaryDirectory(dir=PROJECT / ".cache") as temporary:
        model = Path(temporary)
        for asset in source.iterdir():
            if not asset.name.startswith("openvino_tokenizer"):
                (model / asset.name).symlink_to(asset)
        result = run("generate", "--model", str(model), "--prompt", "hello")
        require(result.returncode != 0 and "openvino_tokenizer.xml" in result.stdout,
                "missing tokenizer was not identified", result.stdout)

def unavailable_device_test():
    result = run("generate", "--device", "GPU.999", "--max-new-tokens", "2", "--prompt", "hello")
    require(result.returncode != 0, "unavailable GPU unexpectedly succeeded", result.stdout)
    require("GPU" in result.stdout, "device failure did not identify GPU", result.stdout)

def memory_cycles_test():
    commands = []
    for _ in range(20): commands += ["Say OK", "/stats", "/reset"]
    commands.append("/exit")
    result = run("chat", "--max-new-tokens", "1", input_text="\n".join(commands)+"\n", timeout=170)
    require(result.returncode == 0, "20-cycle memory test failed", result.stdout)
    rss = [float(value) for value in re.findall(r"Current process RSS:\s+([0-9.]+) MiB", result.stdout)]
    require(len(rss) == 20, "did not record all 20 memory samples", result.stdout)
    require(max(rss[5:]) - min(rss[5:]) < 256,
            f"post-warmup RSS range was unexpectedly large: {min(rss[5:])}-{max(rss[5:])} MiB", result.stdout)


def cache_options_test():
    cases = [(("--prefix-caching",), "requires a bounded pool"),
             (("--num-kv-blocks", "128", "--cache-size-gb", "1"), "Use only one"),
             (("--max-batched-tokens", "0"), "must be greater than zero"),
             (("--eviction-start", "128", "--eviction-recent", "128", "--eviction-max", "256"), "must exceed"),
             (("--cache-eviction", "--eviction-max", "257"), "multiples of 32"),
             (("--conversation",), "requires benchmark")]
    for arguments, message in cases:
        result = run("generate", "--prompt", "hello", *arguments)
        require(result.returncode != 0 and message in result.stdout, "invalid cache options accepted", result.stdout)


def prefix_reset_test():
    result = run("chat", "--prefix-caching", "--num-kv-blocks", "128", "--max-new-tokens", "2",
        input_text="Remember ZEBRA-741\n/reset\n/stats\nSay OK\n/stats\n/exit\n")
    require(result.returncode == 0 and "Prefix cache released; pipeline rebuilt." in result.stdout and
            "No generation statistics yet" in result.stdout and "Last response statistics" in result.stdout,
            "prefix-cache reset did not rebuild and recover", result.stdout)


def conversation_benchmark_test():
    with tempfile.TemporaryDirectory() as temporary:
        prompts = Path(temporary) / "chat.jsonl"
        output = Path(temporary) / "chat.csv"
        prompts.write_text('\n'.join(json.dumps(dict(id=str(i), prompt=prompt)) for i, prompt in enumerate(
            ["Remember ZEBRA-741", "What did I say?", "Say OK"])) + '\n')
        result = run("benchmark", "--conversation", "--prompts", str(prompts), "--output", str(output),
            "--prefix-caching", "--num-kv-blocks", "128", "--max-batched-tokens", "64", "--max-new-tokens", "2")
        require(result.returncode == 0, "conversation benchmark failed", result.stdout)
        with output.open(newline="") as stream: rows = list(csv.DictReader(stream))
        require(len(rows) == 3 and int(rows[-1]["input_tokens"]) > int(rows[0]["input_tokens"]) and
                all(row["num_kv_blocks"] == "128" and row["conversation"] == "1" and
                    row["max_num_batched_tokens"] == "64" for row in rows),
                "conversation benchmark lost history or cache metadata", result.stdout)


def streaming_generate_test():
    process = subprocess.Popen([str(LAUNCHER), "generate", "--prompt",
        "Write a detailed explanation of computer architecture.", "--max-new-tokens", "256"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=PROJECT)
    try:
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            require(selector.select(timeout=60), "generation did not stream any output")
            first = process.stdout.read(1)
        require(first and process.poll() is None, "response arrived only after process exit")
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=60)
        require(process.returncode == 130 and "Generation cancelled." in stderr,
                "streamed single-prompt generation did not cancel cleanly", stdout + stderr)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def cache_probe_test():
    with tempfile.TemporaryDirectory() as temporary:
        allocations = {}
        for precision in ("auto", "f16"):
            output = Path(temporary) / f"{precision}.csv"
            result = run("cache-probe", "--prompt", "Say OK", "--prefix-caching",
                "--num-kv-blocks", "128", "--kv-cache-precision", precision,
                "--max-new-tokens", "2", "--repetitions", "2", "--output", str(output))
            require(result.returncode == 0, "native cache-allocation probe failed", result.stdout)
            with output.open(newline="") as stream: rows = list(csv.DictReader(stream))
            require(len(rows) == 2 and all(int(row["cache_allocated_bytes"]) > 0 and
                0 < float(row["max_cache_usage_percent"]) <= 100 for row in rows),
                "probe did not report real allocation and usage", result.stdout)
            allocations[precision] = int(rows[0]["cache_allocated_bytes"])
        require(all(value > 0 for value in allocations.values()),
                "cache allocations were not available for both supported CPU settings")

CASES = {"config": config_test, "missing_model": missing_model_test, "context": context_test,
         "arguments": argument_validation_test,
         "rejection_history": rejection_history_test, "generate_context": generate_context_test,
         "jsonl": jsonl_test, "short_metrics": short_metrics_test,
         "resource_metrics": resource_metrics_test, "kv_config": kv_config_test,
         "reset": reset_test, "fresh_reset": fresh_reset_test,
         "metrics": metrics_test, "smoke": smoke_test,
         "trimming": trimming_test, "continuity": continuity_test,
         "cancellation": cancellation_test, "missing_tokenizer": missing_tokenizer_test,
         "unavailable_device": unavailable_device_test, "memory_cycles": memory_cycles_test,
         "cache_options": cache_options_test, "prefix_reset": prefix_reset_test,
         "conversation_benchmark": conversation_benchmark_test, "streaming_generate": streaming_generate_test,
         "cache_probe": cache_probe_test}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in CASES: raise SystemExit("usage: test_cli.py CASE BINARY")
    os.environ["SHIKAI_BINARY"] = str(Path(sys.argv[2]).resolve())
    CASES[sys.argv[1]]()
