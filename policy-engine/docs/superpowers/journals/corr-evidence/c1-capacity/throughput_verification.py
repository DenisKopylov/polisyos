"""Capture one bounded synthetic throughput gate with its actual return code."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import inspect
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
MODES = (
    "baseline",
    "zero_memory_slope",
    "skip_owner_structure",
    "unbounded_workers",
    "reuse_level_inputs",
    "skip_input_binding",
)


def child(mode: str, selected_test: str) -> int:
    """Remove the actual property in memory while retaining its report markers."""
    if mode == "zero_memory_slope":
        analysis = importlib.import_module(PREFIX + "throughput_analysis")
        analysis._slope = lambda points: 0.0
        selected_test = ".ThroughputTests.test_actual_marked_process_memory_growth_and_origin"
    elif mode == "skip_owner_structure":
        probe = importlib.import_module(PREFIX + "contract_probe")
        probe._validate_extraction_response = lambda parsed, **kwargs: parsed
        selected_test = (
            ".ThroughputTests.test_marked_sdk_real_owner_bounded_queue_errors_and_candidate_only"
        )
    elif mode in {"unbounded_workers", "reuse_level_inputs", "skip_input_binding"}:
        name = "throughput_declaration" if mode == "skip_input_binding" else "throughput_runner"
        owner = importlib.import_module(PREFIX + name)
        function = {
            "unbounded_workers": "_run_level",
            "reuse_level_inputs": "level_members",
            "skip_input_binding": "read_selected_work",
        }[mode]
        tree = ast.parse(
            "from __future__ import annotations\n" + inspect.getsource(getattr(owner, function))
        )
        changed = 0
        for node in ast.walk(tree):
            if (
                mode == "unbounded_workers"
                and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "min"
            ):
                node.func.id = "max"
                changed += 1
            elif (
                mode == "reuse_level_inputs"
                and isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "start" for target in node.targets
                )
            ):
                node.value = ast.Constant(0)
                changed += 1
            elif (
                mode == "skip_input_binding"
                and isinstance(node, ast.If)
                and any(
                    isinstance(value, ast.Name) and value.id == "actual"
                    for value in ast.walk(node.test)
                )
            ):
                node.test = ast.Constant(False)
                changed += 1
        if changed != 1:
            raise ValueError("throughput_removal_target_not_unique")
        exec(  # noqa: S102 - isolated in-memory property removal, never caller code.
            compile(ast.fix_missing_locations(tree), "<throughput-removal>", "exec"), owner.__dict__
        )
        selected_test = (
            ".ThroughputTests.test_marked_sdk_real_owner_bounded_queue_errors_and_candidate_only"
            if mode == "unbounded_workers"
            else (
                ".ThroughputTests.test_complete_input_only_frame_disjoint_interleaved_and_fake_identity"
            )
        )
    suite = unittest.defaultTestLoader.loadTestsFromName(PREFIX + "test_throughput" + selected_test)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--test", default="")
    parser.add_argument("--mode", choices=MODES, default="baseline")
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    if args.child:
        return child(args.mode, args.test)
    if args.output is None:
        raise ValueError("throughput_gate_capture_path_required")
    command = [
        sys.executable,
        "-m",
        PREFIX + "throughput_verification",
        "--child",
        "--mode",
        args.mode,
        "--test",
        args.test,
    ]
    basis = Path(__file__).parent
    sources = sorted(
        {
            *basis.glob("*throughput*.py"),
            basis / "process_telemetry.py",
            basis / "contract_probe.py",
            basis / "capacity_common.py",
            Path("src/polisyos/data_forge/domains/academic/batch/article_extractor.py"),
            Path("src/polisyos/data_forge/domains/academic/batch/reextraction_transport.py"),
        }
    )
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)  # noqa: S603
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    unchanged = before == after
    capture = {
        "synthetic": True,
        "authority_status": "candidate_measurement",
        "argv": command,
        "removal_mode": args.mode,
        "returncode": result.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "source_sha256": before,
        "source_unchanged_during_gate": unchanged,
        "capture_returncode": result.returncode if unchanged else 125,
    }
    with args.output.open("x") as stream:
        json.dump(capture, stream, indent=2, allow_nan=False)
        stream.write("\n")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return capture["capture_returncode"]


if __name__ == "__main__":
    raise SystemExit(main())
