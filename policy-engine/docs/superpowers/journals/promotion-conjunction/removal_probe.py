# ruff: noqa: T201
# Required stdout receipts for this research instrument.
"""Disable one actual guard in-process, retain its marker, run its behavioral test.

This is an explicit research removal probe, not a product absence instrument.
No repository source is rewritten. Each isolated invocation must return pytest's
actual failure status; a passing test means the guard control is inadequate.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT)]

CASES = {
    "constructor": (
        "scope_insufficient_cannot_mint_authoritative_promotion",
        "test_constructor_refuses_authority_with_retained_scope_markers",
    ),
    "semantic": (
        "scope_insufficient_semantic_scope_mismatch",
        "test_replay_refuses_scope_status_with_removed_semantic_scope",
    ),
    "authority": (
        "scope_insufficient_authority_laundering",
        "test_replay_refuses_authority_with_retained_scope_markers",
    ),
}


class _WitnessReports:
    """Distinguish the selected assertion failing from an unrelated pytest red."""

    def __init__(self) -> None:
        self.reports: list[dict[str, str]] = []

    def pytest_runtest_logreport(self, report: object) -> None:
        self.reports.append(
            {
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "message": getattr(getattr(report.longrepr, "reprcrash", None), "message", ""),
            }
        )

    def confirms(self, *, case: str, test: str, marker: str) -> bool:
        failed = [report for report in self.reports if report["outcome"] == "failed"]
        if len(failed) != 1:
            return False
        report = failed[0]
        expected = (
            "DID NOT RAISE"
            if case == "constructor"
            else f"AssertionError: assert '{marker}' in"
        )
        return (
            report["nodeid"].endswith("::" + test)
            and report["when"] == "call"
            and expected in report["message"]
        )


def run_case(case: str) -> tuple[int, bool]:
    """Mutate one guard for one witness and restore its bytecode afterward."""
    import pytest

    from polisyos.runtime.quality import promotion_sequence as owner

    marker, test = CASES[case]
    function = (
        owner.CanonicalPromotionReceipt._promoted_requires_trace
        if case == "constructor"
        else owner._validate_promotion_receipt_with_bound_session
    )
    path = Path(inspect.getsourcefile(function))
    body = path.read_bytes()
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and any(isinstance(part, ast.Constant) and part.value == marker for part in ast.walk(node))
    ]
    if not matches:
        print(json.dumps({"UNRUN": "guard_not_resolved", "inputs_actually_read": [str(path)]}))
        return 2, False
    guarded = min(matches, key=lambda node: node.end_lineno - node.lineno)
    removed = ast.unparse(guarded.test)
    guarded.test = ast.Name(id="_removal_probe_guard_enabled", ctx=ast.Load())
    definition = tree.body[0]
    definition.decorator_list = []
    definition.body.insert(
        1,
        ast.Assign(
            targets=[ast.Name(id="_removal_probe_guard_enabled", ctx=ast.Store())],
            value=ast.Constant(value=False),
        ),
    )
    ast.fix_missing_locations(tree)
    namespace = dict(function.__globals__)
    exec(compile(tree, str(path), "exec"), namespace)  # noqa: S102 - isolated own-source mutation
    mutated = namespace[function.__name__]
    if marker not in mutated.__code__.co_consts:
        raise RuntimeError("probe_removed_marker")
    original_code = function.__code__
    function.__code__ = mutated.__code__
    print(
        json.dumps(
            {
                "case": case,
                "inputs_actually_read": [
                    {
                        "path": str(path),
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "interpreted_function": function.__qualname__,
                    }
                ],
                "removed_property": removed,
                "retained_marker": marker,
                "selection": (
                    "smallest actual guard containing the selected original failure marker"
                ),
                "unresolved_by_construction": [
                    "other_guards_not_mutated",
                    "external_deployment_not_exercised",
                    "python_import_and_pytest_transitive_reads_not_enumerated",
                ],
            },
            indent=2,
        ),
        flush=True,
    )
    witness = _WitnessReports()
    try:
        result = pytest.main(
            [
                str(ROOT / "tests/unit/runtime/quality/test_promotion_scope_guards.py")
                + "::"
                + test,
                "-vv",
                "-rA",
            ],
            plugins=[witness],
        )
    finally:
        function.__code__ = original_code
    print(f"actual_pytest_exit_code={int(result)}", flush=True)
    confirmed = witness.confirms(case=case, test=test, marker=marker)
    print(json.dumps({"guard_removal_witness_confirmed": confirmed, "reports": witness.reports}))
    return int(result), confirmed


def main() -> int:
    """Run one witness or amortize imports across all independent guard removals."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=[*CASES, "all"])
    args = parser.parse_args()
    if args.case != "all":
        return run_case(args.case)[0]
    from contextlib import redirect_stderr, redirect_stdout

    results = {}
    for case in CASES:
        path = Path(__file__).parent / "raw" / f"removal-{case}.txt"
        with path.open("w") as stream, redirect_stdout(stream), redirect_stderr(stream):
            code, confirmed = run_case(case)
        results[case] = {
            "pytest_exit_code": code,
            "guard_removal_witness_confirmed": confirmed,
            "output": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "inputs_actually_read": [str(path)],
            "selector": "complete captured output of this guard removal; source receipt inside",
            "unresolved_by_construction": [
                "python_import_and_pytest_transitive_reads_not_enumerated",
                "external_deployment_not_exercised",
            ],
        }
        print(json.dumps({case: results[case]}), flush=True)
    return 0 if all(
        row["pytest_exit_code"] == 1 and row["guard_removal_witness_confirmed"]
        for row in results.values()
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
