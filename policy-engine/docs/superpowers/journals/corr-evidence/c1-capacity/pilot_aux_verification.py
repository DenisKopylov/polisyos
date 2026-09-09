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
from typing import Any

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", default="test_throughput_admission")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--remove-admission", action="store_true")
    parser.add_argument("--remove-knee", action="store_true")
    parser.add_argument("--child", action="store_true")
    parser.add_argument(
        "--remove-pilot", choices=("identity", "unknown_usage", "boolean", "archive_scan", "memory")
    )
    args = parser.parse_args()
    if args.child:
        if args.remove_knee:
            owner = importlib.import_module(PREFIX + "throughput_reanalysis")
            owner._comparison_established = lambda current, previous: True
        if args.remove_admission:
            owner = importlib.import_module(PREFIX + "throughput_admission")
            owner._require_equal = lambda actual, expected, reason: None
        if args.remove_pilot:
            owner = importlib.import_module(PREFIX + "pilot_analysis")
            if args.remove_pilot == "identity":
                owner._require_identity = lambda actual, expected, reason: None
            elif args.remove_pilot == "unknown_usage":
                original = owner._aggregate_usage

                def aggregate(
                    attempts: list[dict[str, Any]], rates: dict[str, float]
                ) -> dict[str, Any]:
                    return original(
                        [
                            {**row, "provider_usage": row["provider_usage"] or (0, 0)}
                            for row in attempts
                        ],
                        rates,
                    )

                owner._aggregate_usage = aggregate
            elif args.remove_pilot == "boolean":
                owner._boolean = lambda value: isinstance(value, (bool, str))
            elif args.remove_pilot == "memory":
                owner._Regression.slope = lambda self: 0.0
            elif args.remove_pilot == "archive_scan":
                # Remove the preflight scan from the real archive function, retaining writes.
                import ast
                import inspect

                tree = ast.parse(
                    "from __future__ import annotations\n"
                    + inspect.getsource(owner.archive_primary)
                )
                removed = 0
                for node in ast.walk(tree):
                    if isinstance(node, ast.For):
                        before = len(node.body)
                        node.body = [
                            line
                            for line in node.body
                            if not (
                                isinstance(line, ast.Expr)
                                and isinstance(line.value, ast.Call)
                                and isinstance(line.value.func, ast.Attribute)
                                and line.value.func.attr == "check_payload"
                            )
                        ]
                        removed += before - len(node.body)
                if removed != 1:
                    raise ValueError("pilot_archive_scan_removal_not_unique")
                exec(  # noqa: S102 - isolated real-property removal, never external code.
                    compile(ast.fix_missing_locations(tree), "<pilot-removal>", "exec"),
                    owner.__dict__,
                )
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
    if args.remove_knee:
        command.append("--remove-knee")
    if args.remove_pilot:
        command.extend(["--remove-pilot", args.remove_pilot])
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
