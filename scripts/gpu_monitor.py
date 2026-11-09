"""Optional NVIDIA benchmark monitoring using the installed nvidia-smi command.

VRAM is matched to the actual inference PID. Utilization is device-wide and may
include other clients. Measurements cover the full child lifetime, including load
and warmup; they are not presented as individual generation measurements.
"""
import csv
import math
import shutil
import subprocess
import threading
import time


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


class NvidiaMonitor:
    def __init__(self, pid, enabled, interval=0.2):
        self.pid = pid
        self.interval = interval
        self.samples = []
        self.error = ""
        self.enabled = enabled and shutil.which("nvidia-smi") is not None
        self.stop_event = threading.Event()
        self.thread = None
        if enabled and not self.enabled:
            self.error = "nvidia-smi is not installed; NVIDIA counters unavailable"

    def query(self, query):
        result = subprocess.run(["nvidia-smi", query, "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return list(csv.reader(result.stdout.splitlines(), skipinitialspace=True))

    def sample(self):
        processes = self.query("--query-compute-apps=pid,gpu_uuid,used_gpu_memory")
        matching = [row for row in processes if len(row) == 3 and row[0].strip() == str(self.pid)]
        devices = self.query("--query-gpu=uuid,utilization.gpu") if matching else []
        utilization = {row[0].strip():number(row[1]) for row in devices if len(row) == 2}
        for _, uuid, memory in matching:
            self.samples.append(dict(timestamp=time.time(), pid=self.pid, gpu_uuid=uuid.strip(),
                process_vram_mib=number(memory), device_util_percent=utilization.get(uuid.strip())))

    def start(self):
        if self.enabled:
            def loop():
                while not self.stop_event.is_set():
                    try:
                        self.sample()
                    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                        self.error = str(error)
                        break
                    self.stop_event.wait(self.interval)
            self.thread = threading.Thread(target=loop, daemon=True)
            self.thread.start()
        return self

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()
        memory = [s["process_vram_mib"] for s in self.samples if s["process_vram_mib"] is not None]
        utilization = [s["device_util_percent"] for s in self.samples if s["device_util_percent"] is not None]
        return dict(source="nvidia-smi", scope="entire inference process lifetime, including load and warmup",
            utilization_scope="device-wide; may include other processes", sample_interval_ms=self.interval*1000,
            process_peak_vram_mib=max(memory) if memory else None,
            device_mean_util_percent=sum(utilization)/len(utilization) if utilization else None,
            samples=self.samples, error=self.error)
