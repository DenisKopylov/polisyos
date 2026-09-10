"""Run the exact J native scope once and reconcile its complete pytest identities."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import time


FILES = (
    "tests/unit/runtime/quality/workspace/test_production_case_admission.py",
    "tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py",
    "tests/unit/runtime/quality/workspace/test_production_case_public_contracts.py",
)
HISTORY_FILE = "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py"
HISTORY_TEST = "test_gy_j_history_guards_every_completed_predecessor_epoch"
PREFIX = "GY_J_NATIVE_"
HARNESS_FILES = ("_build/gy_gaps/j_native_wave.py", "_build/gy_gaps/receipt.py")


def emit(kind: str, value: object) -> None:
    print(PREFIX + kind + " " + json.dumps(value, sort_keys=True), flush=True)


def source_fence() -> dict[str, str]:
    """Pin every contained current Python source, with an independent path walk."""
    root = Path.cwd().resolve()
    primary, independent = set(), set()
    for name in ("src", "tools", "tests"):
        source_root = root / name
        for path in source_root.rglob("*.py"):
            resolved = path.resolve()
            if resolved.is_file() and resolved.is_relative_to(source_root) and "__pycache__" not in resolved.parts:
                primary.add(resolved.relative_to(root).as_posix())
        for directory, _, names in os.walk(source_root):
            for filename in names:
                path = (Path(directory) / filename).resolve()
                if filename.endswith(".py") and path.is_file() and path.is_relative_to(source_root) and "__pycache__" not in path.parts:
                    independent.add(path.relative_to(root).as_posix())
    if not primary or primary != independent:
        raise ValueError({"source_inventory_mismatch": {"only_rglob": sorted(primary - independent), "only_os_walk": sorted(independent - primary)}})
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sorted(primary)}


def harness_fence() -> dict[str, str]:
    """Pin the actual runner and recorder separately from the product denominator."""
    return {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in HARNESS_FILES}


def fence_summary(values: dict[str, str]) -> dict:
    return {
        "roots": ["src", "tools", "tests"],
        "file_type": ".py",
        "rglob_denominator": len(values),
        "independent_os_walk_denominator": len(values),
        "path_and_raw_sha256_digest": hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "test_sources": {name: values[name] for name in (*FILES, HISTORY_FILE)},
    }


def population() -> list[str]:
    nodes = []
    for name in (*FILES, HISTORY_FILE):
        text = Path(name).read_text(encoding="utf-8")
        tree = ast.parse(text)
        chosen = lambda value: value.startswith("test_") if name in FILES else value == HISTORY_TEST
        primary = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and chosen(node.name)]
        independent = [match for match in re.findall(r"^(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(", text, re.M) if chosen(match)]
        all_nested = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and chosen(node.name)]
        if not primary or primary != independent or primary != all_nested or len(primary) != len(set(primary)):
            raise ValueError({"test_definition_population_mismatch": name, "ast": primary, "anchored": independent, "complete_ast": all_nested})
        nodes.extend(f"{name}::{test}" for test in primary)
    return nodes


def prior_failure_selection(path: Path, current: list[str]) -> tuple[list[str], dict]:
    raw = path.read_bytes()
    receipt = json.loads(raw)
    if receipt.get("timed_out") is not False:
        raise ValueError("correction requires a complete prior receipt, not a timeout/nonreceipt")
    packets = {}
    for kind in ("POPULATION", "READBACK"):
        prefix = PREFIX + kind + " "
        rows = [json.loads(line[len(prefix):]) for line in receipt["stdout"].splitlines() if line.startswith(prefix)]
        if len(rows) != 1:
            raise ValueError(f"prior receipt requires exactly one {kind} packet")
        packets[kind] = rows[0]
    previous = packets["POPULATION"]["complete_definition_nodes"]
    if set(current) != set(previous):
        raise ValueError({"correction_definition_scope_changed": {"added": sorted(set(current) - set(previous)), "lost": sorted(set(previous) - set(current))}})
    readback = packets["READBACK"]
    if readback["collection_failures"] or readback["reconciliation_issues"]:
        raise ValueError("prior collection/reconciliation was incomplete; run the full scope")
    collected = readback["collected"]
    passed = {row["nodeid"] for row in readback["outcomes"] if row["when"] == "call" and row["outcome"] == "passed" and not row["wasxfail"]}
    negative = {row["nodeid"] for row in readback["outcomes"] if row["outcome"] != "passed" or row["wasxfail"]}
    failed = (set(collected) - passed) | negative
    if not failed or not failed <= set(collected):
        raise ValueError("prior receipt has no exact collected non-passing identity population")
    return sorted(failed), {
        "path": path.as_posix(), "sha256": hashlib.sha256(raw).hexdigest(),
        "prior_returncode": receipt["returncode"],
        "prior_source_fence": packets["POPULATION"]["source_fence"],
        "scope": "exact prior non-passing expanded identities; unaffected identities are not rerun",
    }


def report_row(report: object) -> dict:
    return {"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome, "wasxfail": str(getattr(report, "wasxfail", ""))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-from", type=Path)
    parser.add_argument("--describe-only", action="store_true", help="stdlib reads only; do not import pytest or collect tests")
    args = parser.parse_args()
    before = source_fence()
    harness_before = harness_fence()
    complete = population()
    selected, previous = (prior_failure_selection(args.failed_from, complete) if args.failed_from else (complete, None))
    emit("POPULATION", {
        "mode": "correction" if previous else "complete",
        "complete_definition_nodes": complete,
        "ast_definition_denominator": len(complete),
        "independent_anchored_definition_denominator": len(complete),
        "selected_pytest_arguments": selected if previous else "complete_definition_nodes",
        "source_fence": fence_summary(before), "failed_from": previous,
        "executing_harness_sha256": harness_before,
        "describe_only": args.describe_only,
    })
    if args.describe_only:
        if source_fence() != before or harness_fence() != harness_before:
            raise ValueError("source changed during static description")
        return 0

    import pytest

    collected, outcomes, collection_failures = [], [], []

    class Recorder:
        def pytest_collection_finish(self, session):
            collected.extend(item.nodeid for item in session.items)

        def pytest_collectreport(self, report):
            if report.failed or report.skipped:
                collection_failures.append({"nodeid": report.nodeid, "outcome": report.outcome, "longrepr": str(report.longrepr)})

        def pytest_runtest_logreport(self, report):
            outcomes.append(report_row(report))

        def pytest_sessionfinish(self, session):
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            self.terminal = [report_row(report) for category, reports in reporter.stats.items() for report in reports if category in {"passed", "failed", "error", "skipped", "xfailed", "xpassed"} and hasattr(report, "when")]

    recorder = Recorder()
    started = time.monotonic()
    result = pytest.main(["-q", "-s", "-rA", "--show-capture=no", "--tb=short", *selected], plugins=[recorder])
    elapsed = round(time.monotonic() - started, 3)
    after = source_fence()
    harness_after = harness_fence()
    changed = [{"path": name, "before": before.get(name, "absent"), "after": after.get(name, "absent")} for name in sorted(set(before) | set(after)) if before.get(name, "absent") != after.get(name, "absent")]
    issues = []
    if harness_after != harness_before:
        issues.append({"executing_harness_changed_during_wave": {
            "before": harness_before, "after": harness_after
        }})
    if changed:
        issues.append({"source_changed_during_wave": changed})
    if len(collected) != len(set(collected)):
        issues.append({"duplicate_collected_identities": [name for name, n in Counter(collected).items() if n > 1]})
    expected = set(selected)
    actual = set(collected) if previous else {node.split("[", 1)[0] for node in collected}
    if expected != actual:
        issues.append({"selected_population_mismatch": {"uncollected": sorted(expected - actual), "unexpected": sorted(actual - expected)}})
    emitted = {row["nodeid"] for row in outcomes}
    if emitted != set(collected):
        issues.append({"reported_population_mismatch": {"unreported": sorted(set(collected) - emitted), "uncollected": sorted(emitted - set(collected))}})
    visible = [row for row in outcomes if row["when"] == "call" or row["outcome"] != "passed"]
    identity = lambda row: json.dumps(row, sort_keys=True)
    terminal = getattr(recorder, "terminal", [])
    if Counter(map(identity, visible)) != Counter(map(identity, terminal)):
        issues.append({"pytest_terminal_report_mismatch": {"only_runtest": list((Counter(map(identity, visible)) - Counter(map(identity, terminal))).elements()), "only_terminal": list((Counter(map(identity, terminal)) - Counter(map(identity, visible))).elements())}})
    passed = {row["nodeid"] for row in outcomes if row["when"] == "call" and row["outcome"] == "passed" and not row["wasxfail"]}
    nonpassing = (set(collected) - passed) | {row["nodeid"] for row in outcomes if row["outcome"] != "passed" or row["wasxfail"]}
    exitcode = int(result) if result else (2 if issues or collection_failures or nonpassing else 0)
    emit("READBACK", {
        "collected": collected, "outcomes": outcomes,
        "collected_denominator": len(collected), "reported_identity_denominator": len(emitted),
        "terminal_report_identity_reconciled": not any("pytest_terminal_report_mismatch" in issue for issue in issues),
        "collection_failures": collection_failures, "reconciliation_issues": issues,
        "nonpassing_expanded_identities": sorted(nonpassing),
        "pytest_returncode": int(result), "returncode": exitcode,
        "pytest_elapsed_seconds": elapsed,
        "source_fence_unchanged": after == before,
        "executing_harness_unchanged": harness_after == harness_before,
        "executing_harness_sha256_after": harness_after,
        "source_fence_after_digest": fence_summary(after)["path_and_raw_sha256_digest"],
    })
    return exitcode


if __name__ == "__main__":
    raise SystemExit(main())
