"""Capture only the declared synthetic retention helper tests, never model calls."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--test", default="test_synthetic_retention")
    parser.add_argument("--remove-source", action="store_true")
    parser.add_argument("--remove-work-window", action="store_true")
    parser.add_argument("--remove-observation-identity", action="store_true")
    args = parser.parse_args()
    if args.child:
        if args.remove_source:
            owner = importlib.import_module(PREFIX + "synthetic_retention")
            owner._same_source = lambda actual, expected: None
        if args.remove_work_window:
            owner = importlib.import_module(PREFIX + "retention_analysis")
            owner._work_progress = lambda completed, count: True
        if args.remove_observation_identity:
            owner = importlib.import_module(PREFIX + "synthetic_retention")
            tree = ast.parse(
                "from __future__ import annotations\n" + inspect.getsource(owner.run_worker)
            )
            removed = []

            class RemoveIdentity(ast.NodeTransformer):
                def visit_Expr(self, node: ast.Expr) -> ast.Expr | None:
                    if (
                        isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "_observation_identity"
                    ):
                        removed.append("filename_context")
                        return None
                    return self.generic_visit(node)

                def visit_For(self, node: ast.For) -> ast.For | None:
                    if (
                        isinstance(node.iter, ast.Call)
                        and node.iter.args
                        and isinstance(node.iter.args[0], ast.Constant)
                        and node.iter.args[0].value
                        == "SELECT attempt_id FROM attempts WHERE state='returned'"
                    ):
                        removed.append("database_to_file")
                        return None
                    return self.generic_visit(node)

            tree = RemoveIdentity().visit(tree)
            if sorted(removed) != ["database_to_file", "filename_context"]:
                raise ValueError("retention_identity_removal_not_exact")
            exec(  # noqa: S102 - isolated actual property removal, never external code.
                compile(ast.fix_missing_locations(tree), "<retention-removal>", "exec"),
                owner.__dict__,
            )
        tests = unittest.defaultTestLoader.loadTestsFromName(PREFIX + args.test)
        return 0 if unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful() else 1
    if args.output is None:
        raise ValueError("retention_capture_output_required")
    command = [
        sys.executable,
        "-m",
        PREFIX + "retention_verification",
        "--child",
        "--test",
        args.test,
    ]
    if args.remove_source:
        command.append("--remove-source")
    if args.remove_work_window:
        command.append("--remove-work-window")
    if args.remove_observation_identity:
        command.append("--remove-observation-identity")
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)  # noqa: S603
    packet = {
        "synthetic": True,
        "authority_granted": False,
        "argv": command,
        "returncode": result.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "helper_source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*retention*.py"))
        },
    }
    with args.output.open("x") as stream:
        json.dump(packet, stream, indent=2)
        stream.write("\n")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
