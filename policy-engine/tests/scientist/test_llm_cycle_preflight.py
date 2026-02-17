from __future__ import annotations

import pytest

from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot
from polisyos.scientist.llm_cycle import evaluate_iteration, preflight_execution_plan


def test_preflight_returns_structured_diagnostics_for_cycle_and_missing_methods() -> None:
    ensure_causal_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_preflight")
    plan = ExecutionPlan(
        plan_id="plan_preflight",
        run_id="R_preflight",
        method_dag=[
            MethodDagNode(
                node_id="node_a",
                method_fqn="missing.method.a@1.0.0",
                depends_on=["node_b"],
            ),
            MethodDagNode(
                node_id="node_b",
                method_fqn="missing.method.b@1.0.0",
                depends_on=["node_a"],
            ),
        ],
    )
    report = preflight_execution_plan(plan, snapshot)
    codes = {item.code for item in report.diagnostics}
    assert report.ready_to_run is False
    assert "method_catalog.method_missing" in codes
    assert "method_dag.cycle_detected" in codes


@pytest.mark.parametrize(
    ("issue_count", "verdict", "retrieval_quality", "budget_remaining_ratio", "expected"),
    [
        (0, "APPROVE", 1.0, 1.0, "APPROVE"),
        (0, "NEEDS_REVISION", 0.2, 1.0, "REPLAN_DATA"),
        (1, "NEEDS_REVISION", 0.9, 1.0, "REPLAN_METHOD"),
        (5, "NEEDS_REVISION", 0.9, 1.0, "REPLAN_PARAMS"),
        (0, "NEEDS_REVISION", 1.0, 0.0, "STOP_BUDGET"),
    ],
)
def test_evaluator_supports_all_verdict_paths(
    issue_count: int,
    verdict: str,
    retrieval_quality: float,
    budget_remaining_ratio: float,
    expected: str,
) -> None:
    report = evaluate_iteration(
        issue_count=issue_count,
        verdict=verdict,
        retrieval_quality=retrieval_quality,
        budget_remaining_ratio=budget_remaining_ratio,
    )
    assert report.verdict == expected
