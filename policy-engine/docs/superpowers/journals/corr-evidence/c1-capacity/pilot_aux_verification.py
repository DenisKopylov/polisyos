"""Capture a bounded stdlib analysis/admission gate without provider access."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", default="test_throughput_admission")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--remove-admission", action="store_true")
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    if args.child:
        if args.remove_admission:
            owner = importlib.import_module(PREFIX + "throughput_admission")
            owner._require_equal = lambda actual, expected, reason: None
        tests = unittest.defaultTestLoader.loadTestsFromName(PREFIX + args.module)
        return 0 if unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful() else 1
    if args.output is None:
        raise ValueError("aux_gate_capture_path_required")
    command = [
        sys.executable,
        "-S",
        "-m",
        PREFIX + "pilot_aux_verification",
        "--child",
        "--module",
        args.module,
    ]
    if args.remove_admission:
        command.append("--remove-admission")
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
    packet = {
        "synthetic": True,
        "authority_status": "candidate_measurement",
        "argv": command,
        "returncode": result.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
    }
    with args.output.open("x") as stream:
        json.dump(packet, stream, indent=2, allow_nan=False)
        stream.write("\n")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
