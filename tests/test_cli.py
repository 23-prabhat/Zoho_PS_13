#!/usr/bin/env python3
"""Black-box CTest cases for the compiled Shikai application."""
import os, re, signal, subprocess, sys, tempfile, time
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
    result = run("generate", "--device", "GPU", "--max-new-tokens", "2", "--prompt", "hello")
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

CASES = {"config": config_test, "missing_model": missing_model_test, "context": context_test,
         "reset": reset_test, "fresh_reset": fresh_reset_test,
         "metrics": metrics_test, "smoke": smoke_test,
         "trimming": trimming_test, "continuity": continuity_test,
         "cancellation": cancellation_test, "missing_tokenizer": missing_tokenizer_test,
         "unavailable_device": unavailable_device_test, "memory_cycles": memory_cycles_test}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in CASES: raise SystemExit("usage: test_cli.py CASE BINARY")
    CASES[sys.argv[1]]()
