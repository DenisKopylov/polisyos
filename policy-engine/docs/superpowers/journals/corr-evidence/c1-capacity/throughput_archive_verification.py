"""Capture bounded stdlib archive/trace gates and actual property removals."""

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
MODES = ("baseline", "archive_scan", "archive_identity", "active_window", "plan_owner")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="baseline")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child:
        if args.mode in ("archive_scan", "archive_identity"):
            owner = importlib.import_module(PREFIX + "throughput_archive")
            if args.mode == "archive_scan":
                owner._scan = lambda writer, payload: None
            else:
                owner._equal = lambda actual, expected, reason: None
        elif args.mode == "active_window":
            owner = importlib.import_module(PREFIX + "throughput_trace_analysis")
            owner._within_active = lambda elapsed, end: True
        elif args.mode == "plan_owner":
            owner = importlib.import_module(PREFIX + "throughput_archive")
            owner.runner.load_plan = owner.analysis._sealed
        names = [PREFIX + "test_throughput_archive", PREFIX + "test_throughput_trace"]
        # Removal probes are synthetic-only except the plan-owner preflight.
        # That integration always refuses before copying actual response bytes;
        # never remove its preflight credential scan while using actual inputs.
        selected = {
            "archive_scan": (
                "test_throughput_archive.ThroughputArchiveTests."
                "test_complete_primary_byte_archive_and_trace_secret_refusal"
            ),
            "archive_identity": (
                "test_throughput_archive.ThroughputArchiveTests."
                "test_missing_provider_or_novel_outcome_is_not_complete"
            ),
            "active_window": (
                "test_throughput_trace.ThroughputTraceTests."
                "test_complete_active_window_bins_and_cleanup_are_distinct"
            ),
            "plan_owner": (
                "test_throughput_archive.ThroughputArchiveTests."
                "test_actual_committed_declaration_frame_reaches_archive_preflight"
            ),
        }
        if args.mode in selected:
            names = [PREFIX + selected[args.mode]]
        tests = unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromName(name) for name in names
        )
        return 0 if unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful() else 1
    if args.output is None:
        raise ValueError("archive_verification_output_required")
    command = [
        sys.executable,
        "-m",
        PREFIX + "throughput_archive_verification",
        "--child",
        "--mode",
        args.mode,
    ]
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
    base = Path(__file__).parent
    paths = [
        base / name
        for name in (
            "throughput_archive.py",
            "test_throughput_archive.py",
            "throughput_trace_analysis.py",
            "test_throughput_trace.py",
            "throughput_archive_verification.py",
            "pilot_analysis.py",
            "throughput_runner.py",
            "throughput_declaration.py",
        )
    ]
    capture = {
        "synthetic": True,
        "authority_status": "candidate_measurement",
        "argv": command,
        "mode": args.mode,
        "returncode": result.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
        },
    }
    with args.output.open("x") as stream:
        json.dump(capture, stream, indent=2)
        stream.write("\n")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
