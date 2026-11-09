#!/usr/bin/env python3
"""Fresh three-turn inference under kernel-enforced network restrictions.

Prefer a network namespace; fall back to Linux seccomp denying socket/socketpair
for every address family except AF_UNIX. The filter is inherited across exec and
threads. Offline flags alone never count as an isolation test.
"""
import argparse
import ctypes
import errno
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]


def deny_network():
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise OSError("seccomp fallback supports Linux x86-64")

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                    ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ushort), ("filters", ctypes.POINTER(Filter))]

    # seccomp_data: nr at offset 0, arch at 4, args[0] at 16.
    instructions = [
        (0x20, 0, 0, 4),                 # load architecture
        (0x15, 1, 0, 0xC000003E),       # AUDIT_ARCH_X86_64
        (0x06, 0, 0, 0x80000000),       # kill unexpected architecture
        (0x20, 0, 0, 0),                 # load syscall number
        (0x35, 5, 0, 0x40000000),       # reject x32 ABI syscall aliases
        (0x15, 1, 0, 41),               # socket
        (0x15, 0, 4, 53),               # socketpair; otherwise allow
        (0x20, 0, 0, 16),                # address family
        (0x15, 2, 0, socket.AF_UNIX),     # local IPC remains usable
        (0x06, 0, 0, 0x00050000 | errno.EPERM),
        (0x06, 0, 0, 0x00050000 | errno.EPERM),
        (0x06, 0, 0, 0x7FFF0000),       # SECCOMP_RET_ALLOW
    ]
    filters = (Filter * len(instructions))(*(Filter(*item) for item in instructions))
    program = Program(len(instructions), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Cannot install network-denial seccomp filter")


def check_socket_denial():
    for family in (socket.AF_INET, socket.AF_INET6):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            try:
                connection = socket.socket(family, kind)
            except OSError as error:
                if error.errno == errno.EPERM:
                    continue
                raise
            connection.close()
            raise RuntimeError("Network restriction did not deny an Internet socket")


def restricted_child():
    try:
        deny_network()
        check_socket_denial()
    except (OSError, RuntimeError) as error:
        print(f"Network enforcement unavailable: {error}", file=sys.stderr)
        return 77
    # This new process inherited no network descriptors (close_fds=True).
    os.execv(str(PROJECT / "scripts/shikai"), [str(PROJECT / "scripts/shikai"),
        "chat", "--device", "CPU", "--max-new-tokens", "4"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seccomp-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seccomp_child:
        return restricted_child()
    commands = [str(PROJECT / "scripts/shikai"), "chat", "--device", "CPU", "--max-new-tokens", "4"]
    try:
        namespace = subprocess.run(["unshare", "--net", "true"], capture_output=True).returncode == 0
    except FileNotFoundError:
        namespace = False
    mode = "network namespace" if namespace else "seccomp: only AF_UNIX socket creation allowed"
    command = ["unshare", "--net", *commands] if namespace else [sys.executable, __file__, "--seccomp-child"]
    inputs = "Say hello.\n/stats\nWhat did I ask?\n/stats\nSay goodbye.\n/stats\n/exit\n"
    result = subprocess.run(command, input=inputs, text=True, capture_output=True,
        cwd=PROJECT, close_fds=True, timeout=90,
        env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    counts = re.findall(r"Output tokens:\s+([1-9][0-9]*)", result.stdout)
    passed = result.returncode == 0 and len(counts) == 3 and "Goodbye." in result.stdout
    record = dict(mode=mode, status="passed" if passed else "skipped" if result.returncode == 77 else "failed",
        completed_turns=len(counts), stdout=result.stdout, stderr=result.stderr)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if passed else 77 if result.returncode == 77 else 1


if __name__ == "__main__":
    raise SystemExit(main())
