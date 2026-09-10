"""Synthetic bounded OS workload with an independently addressed native observer."""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import resource
import sqlite3
import struct
import subprocess
import sys
import time
from pathlib import Path

MODULE = "docs.superpowers.journals.corr-evidence.c1-capacity.telemetry_fixture"


def _native() -> dict[str, int | float]:
    # Independent representation of the pinned SDK ABI; do not import the observer.
    buffer = (ctypes.c_ubyte * 160)()
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    read = library.proc_pid_rusage
    read.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    read.restype = ctypes.c_int
    if read(os.getpid(), 2, ctypes.byref(buffer)) != 0:
        raise OSError(ctypes.get_errno(), "fixture_native_counter_unavailable")
    timebase = (ctypes.c_uint32 * 2)()
    system = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    function = system.mach_timebase_info
    function.argtypes = [ctypes.c_void_p]
    function.restype = ctypes.c_int
    if function(ctypes.byref(timebase)) != 0 or timebase[1] == 0:
        raise RuntimeError("fixture_timebase_unavailable")
    return {
        "user_ns": struct.unpack_from("=Q", buffer, 16)[0] * timebase[0] / timebase[1],
        "disk_read_bytes": struct.unpack_from("=Q", buffer, 144)[0],
        "disk_write_bytes": struct.unpack_from("=Q", buffer, 152)[0],
    }


def _work(root: Path) -> None:
    time.sleep(0.5)  # Give the independent parent sampler a pre-work observation.
    before = _native()
    cpu_before = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    pages = bytearray(32 * 1024 * 1024)
    for index in range(0, len(pages), 4096):
        pages[index] = 1
    deadline = time.process_time() + 0.4
    accumulator = 1
    while time.process_time() < deadline:
        for _ in range(10_000):
            accumulator = (accumulator * 1664525 + 1013904223) & 0xFFFFFFFF
    prefix = b'{"synthetic":true,"scope":"bounded_disk_telemetry_fixture"}\n'
    data = prefix + os.urandom(1024 * 1024 - len(prefix))
    expected = hashlib.sha256(data * 32).hexdigest()
    path = root / "synthetic-io.bin"
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        fcntl.fcntl(fd, 48, 1)  # SDK F_NOCACHE, on before writes and reads.
        for _ in range(32):
            offset = 0
            while offset < len(data):
                offset += os.write(fd, data[offset:])
        os.fsync(fd)
        fcntl.fcntl(fd, 51)  # SDK F_FULLFSYNC.
        os.lseek(fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while block := os.read(fd, 1024 * 1024):
            digest.update(block)
            size += len(block)
    finally:
        os.close(fd)
    after = _native()
    cpu_after = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    payload = {
        "synthetic": True,
        "pid": os.getpid(),
        "native_user_seconds_delta": (after["user_ns"] - before["user_ns"]) / 1e9,
        "resource_user_seconds_delta": cpu_after - cpu_before,
        "disk_read_bytes_delta": after["disk_read_bytes"] - before["disk_read_bytes"],
        "disk_write_bytes_delta": after["disk_write_bytes"] - before["disk_write_bytes"],
        "file_hash_equal": digest.hexdigest() == expected,
        "file_bytes": size,
        "touched_memory_bytes": len(pages),
        "accumulator": accumulator,
    }
    (root / "child-observed.json").write_text(json.dumps(payload) + "\n")
    checkpoint = root / "work.sqlite"
    if checkpoint.exists():
        with sqlite3.connect(checkpoint) as con:
            con.executemany(
                "INSERT INTO work_items(id,status) VALUES (?,?)",
                [(f"synthetic:{index}", "completed") for index in range(3)],
            )
    time.sleep(1)  # Retain touched pages and final counters for independent observation.


def main() -> None:
    """Run parent/child work, or an intentionally idle stop-control process."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=("parent", "child", "sleep", "write", "brief"), default="parent"
    )
    parser.add_argument("--private-note")
    args = parser.parse_args()
    if args.mode == "brief":
        time.sleep(0.4)
    elif args.mode == "sleep":
        time.sleep(60)
    elif args.mode in {"child", "write"}:
        _work(args.root)
    else:
        subprocess.run(  # noqa: S603 - fixed synthetic child module, never shell.
            [sys.executable, "-m", MODULE, "--root", str(args.root), "--mode", "child"],
            check=True,
        )


if __name__ == "__main__":
    main()
