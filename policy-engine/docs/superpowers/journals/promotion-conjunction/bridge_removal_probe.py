# ruff: noqa: T201
"""Remove each bridge property in memory; preserve markers and restore after its witness."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEST = "tests/integration/runtime_quality/test_evaluation_safety_promotion_bridge.py"
CASES = {
    "source": (
        "test_compiled_source_content_binding_survives_retained_semantic_markers",
        "source CAS binding property was removed",
        "promotion_source_artifact_binding_mismatch",
    ),
    "resolver": (
        "test_opaque_classifier_forwards_real_evidence_repository_to_both_n9_readers",
        "promotion_evidence_resolver",
        "promotion_evidence_resolver",
    ),
    "mode": (
        "test_authoritative_classifier_rejects_foreign_mode_with_identical_candidate_and_world",
        "foreign evaluation mode accepted",
        "value_receipt.evaluation_mode == core.evaluation_mode",
    ),
}


class _WitnessReports:
    def __init__(self) -> None:
        self.reports: list[dict[str, str]] = []

    def pytest_runtest_logreport(self, report: object) -> None:
        self.reports.append({
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "message": getattr(getattr(report.longrepr, "reprcrash", None), "message", ""),
        })

    def confirms(self, test: str, expected: str) -> bool:
        failed = [report for report in self.reports if report["outcome"] == "failed"]
        return len(failed) == 1 and all((
            failed[0]["nodeid"].endswith("::" + test),
            failed[0]["when"] == "call",
            expected in failed[0]["message"],
        ))


def run_case(case: str) -> tuple[int, bool]:
    """Run the intended failing assertion with one removed property, then restore aliases."""
    import pytest

    from polisyos.runtime.http.services.control import evaluation_safety as adapter
    from polisyos.runtime.quality import evaluation_safety as owner

    function = (
        adapter.EvaluationSafetyPersistenceService._read_promotion_source_json
        if case == "source" else owner.verify_near_miss_classification
    )
    test, expected, marker = CASES[case]
    path = Path(inspect.getsourcefile(function))
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    definition = tree.body[0]
    definition.decorator_list = []
    definition.body.insert(1, ast.Assign(
        targets=[ast.Name(id="_removal_probe_retained_marker", ctx=ast.Store())],
        value=ast.Constant(value=marker),
    ))
    count = 0
    if case == "source":
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and any(
                isinstance(part, ast.Constant) and part.value == marker
                for part in ast.walk(node)
            ):
                node.test = ast.Name(id="_removal_probe_guard_enabled", ctx=ast.Load())
                count += 1
        definition.body.insert(1, ast.Assign(
            targets=[ast.Name(id="_removal_probe_guard_enabled", ctx=ast.Store())],
            value=ast.Constant(value=False),
        ))
        if count != 1:
            raise RuntimeError("removal_property_count_not_exact")
    elif case == "resolver":
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                kept = [kw for kw in node.keywords if kw.arg != marker]
                count += len(node.keywords) - len(kept)
                node.keywords = kept
        if count != 2:
            raise RuntimeError("resolver_forwarding_count_not_exact")
    else:
        class RemoveMode(ast.NodeTransformer):
            def visit_Compare(self, node: ast.Compare) -> ast.AST:
                nonlocal count
                if ast.unparse(node) == marker:
                    count += 1
                    return ast.Constant(value=True)
                return self.generic_visit(node)

        tree = RemoveMode().visit(tree)
        if count != 1:
            raise RuntimeError("removal_property_count_not_exact")
    ast.fix_missing_locations(tree)
    namespace = dict(function.__globals__)
    exec(compile(tree, str(path), "exec"), namespace)  # noqa: S102
    mutated = namespace[function.__name__]
    if marker not in mutated.__code__.co_consts:
        raise RuntimeError("retained_marker_missing_from_bytecode")
    original_code = function.__code__
    witness = _WitnessReports()
    print(json.dumps({
        "case": case,
        "inputs_read_scope": "mutation_source_and_selected_witness_files",
        "inputs_actually_read": [
            {"path": str(item), "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
            for item in (Path(__file__), path, ROOT / TEST)
        ],
        "retained_marker": marker,
        "removed_property_count": count,
        "unresolved_by_construction": [
            "pytest_transitive_imports_not_enumerated",
            "external_source_population_outside_selected_fixture",
            "promotion_semantic_acceptance_not_established",
        ],
    }))
    try:
        # Mutate the original object so existing import aliases exercise the same property.
        function.__code__ = mutated.__code__
        code = int(pytest.main([f"{TEST}::{test}", "-q"], plugins=[witness]))
    finally:
        function.__code__ = original_code
    confirmed = code == 1 and witness.confirms(test, expected)
    print(json.dumps({
        "case": case, "pytest_returncode": code, "intended_call_failure": confirmed,
        "reports": witness.reports, "original_code_restored": function.__code__ is original_code,
    }))
    return code, confirmed


def main() -> int:
    """Return zero only when every removed property fails its intended call assertion."""
    outcomes = {case: run_case(case) for case in CASES}
    return 0 if all(code == 1 and confirmed for code, confirmed in outcomes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
