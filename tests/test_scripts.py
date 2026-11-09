#!/usr/bin/env python3
"""Preparation and reporting regressions; no downloads or inference required."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import download_model
import run_benchmarks
import verify_model
import probe_hardware
import package_submission
import benchmark_kv
from gpu_monitor import NvidiaMonitor


class ScriptTests(unittest.TestCase):
    def test_submission_allowlist_includes_new_source_and_excludes_local_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("README.md", ".github/workflows/ci.yml", "guides/kv-cache.md",
                         "models/README.md", "src/new.cpp", "tests/__pycache__/bad.pyc",
                         "scripts/.env", "models/weights/private.bin", ".aws/credentials"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            selected = package_submission.source_files(root)
            self.assertTrue({"README.md", ".github/workflows/ci.yml", "guides/kv-cache.md",
                             "models/README.md", "src/new.cpp"}.issubset(selected))
            self.assertFalse({"tests/__pycache__/bad.pyc", "scripts/.env",
                              "models/weights/private.bin", ".aws/credentials"}.intersection(selected))

    def test_kv_report_separates_cold_followup_and_quality_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [dict(profile="baseline", status="ok", workload="conversation", id="turn-1",
                         ttft_ms="1000", peak_rss_mib="2000", response="OK"),
                    dict(profile="baseline", status="ok", workload="conversation", id="turn-2",
                         ttft_ms="100", peak_rss_mib="2000", response="HARBOR-6129"),
                    dict(profile="baseline", status="ok", workload="quality", id="quality-003",
                         quality_score=2, response="local private offline")]
            benchmark_kv.report(Path(folder), rows)
            report = (Path(folder) / "summary.md").read_text()
            self.assertIn("1000.00 | 100.00 | 2000.00 | 1/1", report)
            self.assertIn("| baseline | 1 | 2.00 | 1/1 | 1/1 |", report)

    def test_curated_evidence_matches_recorded_checksums(self):
        snapshots = sorted((PROJECT / "results").glob("validated-*"))
        self.assertTrue(snapshots, "No reviewed evidence snapshots")
        for evidence in snapshots:
            checksums = json.loads((evidence / "checksums.json").read_text())
            self.assertTrue(checksums, "Curated evidence checksum index is empty")
            for relative, expected in checksums.items():
                with self.subTest(snapshot=evidence.name, artifact=relative):
                    artifact = (evidence / relative).resolve()
                    self.assertTrue(artifact.is_relative_to(evidence.resolve()))
                    with artifact.open("rb") as stream:
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    self.assertEqual(actual, expected, "Evidence changed; inspect the original measurement before replacing its checksum")

    def test_all_checked_in_precision_manifests_are_valid(self):
        manifests = sorted((PROJECT / "models/manifests").glob("*.json"))
        self.assertEqual(len(manifests), 3)
        for path in manifests:
            with self.subTest(manifest=path.name):
                manifest = verify_model.load_manifest(path)
                self.assertEqual(manifest["source"]["revision"], "989aa7980e4cf806f80c7fef2b1adb7bc71aa306")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.model = self.root / "model"
        self.source = self.root / "source"
        self.model.mkdir()
        self.source.mkdir()
        self.manifest = json.loads((PROJECT / "models/manifests/qwen2.5-1.5b-int4.json").read_text())
        self.manifest["export"]["path"] = str(self.model)
        self.manifest["source"]["checkpoint_path"] = str(self.source)
        hashes = {}
        for name in verify_model.REQUIRED_ASSETS:
            content = ("fixture-" + name).encode()
            (self.model / name).write_bytes(content)
            if name in verify_model.HASHED_ASSETS:
                hashes[name] = hashlib.sha256(content).hexdigest()
        self.manifest["export"]["sha256"] = hashes
        for name in ("model.safetensors", "config.json", "tokenizer_config.json", "tokenizer.json", "LICENSE"):
            (self.source / name).write_bytes(b"checkpoint")
        self.manifest["source"]["checkpoint_sha256"] = hashlib.sha256(b"checkpoint").hexdigest()
        self.manifest_path = self.root / "manifest.json"
        self.save_manifest()

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def verify(self, *arguments):
        return subprocess.run([sys.executable, str(PROJECT / "scripts/verify_model.py"),
            "--manifest", str(self.manifest_path), *arguments], capture_output=True, text=True)

    def test_verifier_detects_missing_and_corrupt_exports(self):
        self.assertEqual(self.verify().returncode, 0)
        weight = self.model / "openvino_model.bin"
        weight.write_bytes(b"corrupt")
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256 mismatch", result.stderr)
        weight.unlink()
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required model asset", result.stderr)

    def test_verifier_checks_source_hash_and_directory_override(self):
        self.assertEqual(self.verify(str(self.source), "--source").returncode, 0)
        (self.source / "model.safetensors").write_bytes(b"wrong source")
        self.assertIn("SHA-256 mismatch", self.verify("--source").stderr)
        self.assertNotEqual(self.verify(str(self.root / "absent")).returncode, 0)

    def test_manifest_requires_immutable_revision_and_safe_hash_paths(self):
        self.manifest["source"]["revision"] = "main"
        self.save_manifest()
        self.assertIn("full 40-character commit", self.verify().stderr)
        self.manifest["source"]["revision"] = "a" * 40
        self.manifest["export"]["sha256"]["../outside.bin"] = "0" * 64
        self.save_manifest()
        self.assertIn("plain filenames", self.verify().stderr)

    def test_downloader_pins_revision_and_verifies_download(self):
        snapshot = Mock(return_value=str(self.source))
        fake_hub = types.SimpleNamespace(snapshot_download=snapshot)
        arguments = ["--manifest", str(self.manifest_path), "--output", str(self.source),
                     "--local-files-only"]
        with patch.dict(sys.modules, {"huggingface_hub":fake_hub}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(download_model.main(arguments), 0)
            snapshot.assert_called_once_with(repo_id=self.manifest["source"]["repository"],
                revision=self.manifest["source"]["revision"], local_dir=str(self.source), local_files_only=True)
            (self.source / "model.safetensors").write_bytes(b"corrupt")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                download_model.main(arguments)
            self.assertEqual(error.exception.code, 1)

    def test_downloader_reports_provider_errors(self):
        fake_hub = types.SimpleNamespace(snapshot_download=Mock(side_effect=RuntimeError("download failed")))
        error_output = io.StringIO()
        with patch.dict(sys.modules, {"huggingface_hub":fake_hub}), contextlib.redirect_stderr(error_output):
            with self.assertRaises(SystemExit) as error:
                download_model.main(["--manifest", str(self.manifest_path)])
            self.assertEqual(error.exception.code, 1)
        self.assertIn("download failed", error_output.getvalue())

    def test_reports_and_charts_handle_missing_and_zero_metrics(self):
        rows = [dict(suite="performance", precision="int4", input_tokens="40", ttft_ms="",
                     throughput_tok_s="", peak_rss_mib="100", rss_mib="100", estimated_kv_mib="1"),
                dict(suite="context", precision="int4", input_tokens="40", ttft_ms="0",
                     throughput_tok_s="", peak_rss_mib="100", rss_mib="100", estimated_kv_mib="1"),
                dict(suite="quality", precision="int4", input_tokens="40", ttft_ms="",
                     throughput_tok_s="", peak_rss_mib="100", rss_mib="100", estimated_kv_mib="1", quality_score="0")]
        summary = self.root / "summary.md"
        run_benchmarks.write_report(summary, rows)
        self.assertIn("| INT4 | N/A | N/A | 100.00 |", summary.read_text())
        self.assertIn("| 40 | 0.00 | N/A |", summary.read_text())
        self.assertEqual(run_benchmarks.metric_mean([{"value":"-1000"}, {"value":"nan"}, {"value":""}], "value"), "N/A")
        data = self.root / "results.csv"
        run_benchmarks.write_combined(data, rows)
        figures = self.root / "figures"
        result = subprocess.run([sys.executable, str(PROJECT / "scripts/plot_results.py"),
            str(data), "--output", str(figures)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((figures / "context-ttft.svg").is_file())
        self.assertTrue((figures / "quality-scores.svg").is_file())
        self.assertFalse((figures / "precision-throughput.svg").exists())

    def test_context_benchmark_reserves_output_capacity(self):
        with patch.object(run_benchmarks, "run_cpp", return_value=[]) as run:
            run_benchmarks.context_suite(self.root, types.SimpleNamespace())
        self.assertEqual(run.call_args.kwargs["max_tokens"], 32)
        self.assertEqual(run.call_args.kwargs["context_budget"], 2080)

    def test_nvidia_monitor_attributes_vram_to_inference_pid(self):
        monitor = NvidiaMonitor(42, False)
        monitor.query = Mock(side_effect=[[["42", "GPU-A", "123"], ["99", "GPU-B", "999"]],
                                         [["GPU-A", "80"], ["GPU-B", "95"]]])
        monitor.sample()
        report = monitor.stop()
        self.assertEqual(report["process_peak_vram_mib"], 123)
        self.assertEqual(report["device_mean_util_percent"], 80)
        self.assertEqual(len(report["samples"]), 1)
        self.assertIn("device-wide", report["utilization_scope"])
        self.assertIsNone(NvidiaMonitor(42, False).stop()["process_peak_vram_mib"])

    def test_hardware_probe_distinguishes_gpu_from_cpu(self):
        runtime = {"status":"ok", "output":"  ● CPU  Example CPU\n  ● GPU.0  Example GPU\n"}
        with patch.object(probe_hardware, "command", side_effect=[runtime, {}, {}, {}]):
            report = probe_hardware.probe()
        self.assertEqual(report["gpu_devices"], ["GPU.0"])
        self.assertEqual(report["gpu_status"], "available")

    def test_benchmark_forwards_explicit_runtime_threads_and_precision(self):
        output = self.root / "benchmark.csv"
        output.write_text("id,input_tokens,output_tokens\nprompt,30,1\n")
        prompts = self.root / "prompts.jsonl"
        prompts.write_text('{"id":"prompt","prompt":"hello"}\n')
        args = types.SimpleNamespace(repetitions=1, warmup_runs=0, max_new_tokens=1, threads=0,
            device="CPU", kv_cache_precision="u8", prefix_caching=False, cache_size_gb=0, cache_eviction=False)
        process = Mock(returncode=0, pid=42)
        process.communicate.return_value=("", None)
        with patch.object(run_benchmarks.subprocess, "Popen", return_value=process) as popen, \
             patch.object(run_benchmarks.subprocess, "check_output", return_value="test-revision"):
            rows = run_benchmarks.run_cpp(PROJECT / "models/qwen2.5-1.5b/int4", prompts, output, args)
        command = popen.call_args.args[0]
        self.assertEqual(command[command.index("--threads") + 1], "0")
        self.assertEqual(command[command.index("--kv-cache-precision") + 1], "u8")
        self.assertIn("--no-prefix-caching", command)
        self.assertEqual(rows[0]["kv_cache_precision"], "u8")
        metadata = json.loads(output.with_suffix(".metadata.json").read_text())
        self.assertEqual(metadata["command"], command)
        self.assertEqual(metadata["prompts_sha256"], hashlib.sha256(prompts.read_bytes()).hexdigest())
        self.assertIn("git_dirty", metadata)


if __name__ == "__main__":
    unittest.main()
