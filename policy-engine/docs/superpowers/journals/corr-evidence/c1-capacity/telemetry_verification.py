"""Run the real telemetry witness with its counters or descendant property removed."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import io
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = "docs.superpowers.journals.corr-evidence.c1-capacity"


def main() -> int:
    """Persist complete deciding output and propagate the actual test return code."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("baseline", "zero_cpu", "zero_disk", "without_descendants"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    owner = importlib.import_module(PACKAGE + ".process_telemetry")
    tests = PACKAGE + ".test_process_telemetry"
    if args.mode != "baseline":
        tests += ".ProcessTelemetryTests.test_real_descendant_cpu_disk_memory_and_checkpoint"
    suite = unittest.defaultTestLoader.loadTestsFromName(tests)
    original = owner.read_process_usage

    def zero_counters(pid: int) -> dict:
        value = original(pid)
        if value["status"] == "measured":
            fields = (
                ("cpu_user_seconds", "cpu_system_seconds")
                if args.mode == "zero_cpu"
                else ("disk_read_bytes", "disk_write_bytes")
            )
            for field in fields:
                value[field] = 0
        return value

    mutation = contextlib.nullcontext()
    if args.mode in {"zero_cpu", "zero_disk"}:
        mutation = patch.object(owner, "read_process_usage", zero_counters)
    elif args.mode == "without_descendants":
        mutation = patch.object(owner, "_descendant_pids", lambda _pid, _table: set())
    started = time.monotonic()
    stream = io.StringIO()
    with mutation, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    code = 0 if result.wasSuccessful() else 1
    payload = {
        "synthetic": True,
        "scope": "bounded_local_instrumentation_verification",
        "mode": args.mode,
        "exit_code": code,
        "elapsed_seconds": time.monotonic() - started,
        "output": stream.getvalue(),
        "source_bindings": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                Path(__file__).with_name("process_telemetry.py"),
                Path(__file__).with_name("telemetry_fixture.py"),
                Path(__file__).with_name("test_process_telemetry.py"),
            )
        },
    }
    with args.output.open("x", encoding="utf-8") as file:
        file.write(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    sys.stdout.write(json.dumps(payload, allow_nan=False) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
