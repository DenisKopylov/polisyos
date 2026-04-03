from __future__ import annotations

import importlib.util

import pytest

from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot
from polisyos.scientist.llm_cycle import evaluate_iteration, preflight_execution_plan

_Y0_INSTALLED = importlib.util.find_spec("y0") is not None


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


@pytest.mark.skipif(_Y0_INSTALLED, reason="y0 is installed — symbolic_identify is available, test verifies unavailable scenario")
def test_preflight_blocks_unavailable_symbolic_transport_method() -> None:
    ensure_causal_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_preflight")
    symbolic_fqn = next(
        entry.fqn
        for entry in snapshot.entries
        if "causal.transport.symbolic_identify@" in entry.fqn
    )
    plan = ExecutionPlan(
        plan_id="plan_symbolic_transport",
        run_id="R_preflight",
        method_dag=[
            MethodDagNode(
                node_id="node_symbolic",
                method_fqn=symbolic_fqn,
                depends_on=[],
            )
        ],
    )

    report = preflight_execution_plan(plan, snapshot)

    assert report.ready_to_run is False
    unavailable = next(
        item for item in report.diagnostics if item.code == "method_catalog.method_unavailable"
    )
    assert unavailable.data["disabled_reasons"]
    assert any("unavailable" in reason for reason in unavailable.data["disabled_reasons"])
    assert unavailable.data["capability_matrix"]["runnable"] is False
    assert "alternative_methods" in unavailable.data


def test_preflight_suggests_capability_aware_alternative_for_removed_wrapper() -> None:
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered

    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_preflight")
    plan = ExecutionPlan(
        plan_id="plan_removed_wrapper",
        run_id="R_preflight",
        method_dag=[
            MethodDagNode(
                node_id="node_lp",
                method_fqn="optimization.resource_lp@1.0.0",
                depends_on=[],
            )
        ],
    )

    report = preflight_execution_plan(plan, snapshot)

    missing = next(item for item in report.diagnostics if item.code == "method_catalog.method_missing")
    alternatives = [item["fqn"] for item in missing.data["alternative_methods"]]
    assert "optimization.linear.resource_lp@1.0.0" in alternatives


def test_preflight_enriches_slot_linker_diagnostics_with_replanning_candidates() -> None:
    snapshot = build_method_catalog_snapshot(run_id="R_preflight")
    plan = ExecutionPlan(
        plan_id="plan_slot_linker",
        run_id="R_preflight",
        method_dag=[
            MethodDagNode(
                node_id="node_forecast",
                method_fqn="forecasting.univariate.theta@1.0.0",
            ),
            MethodDagNode(
                node_id="node_panel",
                method_fqn="econometrics.panel.fixed_effects@1.0.0",
                depends_on=["node_forecast"],
            ),
        ],
    )

    report = preflight_execution_plan(plan, snapshot)

    diag = next(item for item in report.diagnostics if item.code == "slot_linker.not_linkable")
    assert diag.data["src_node_id"] == "node_forecast"
    assert diag.data["dst_node_id"] == "node_panel"
    assert diag.data["source_method_fqn"] == "forecasting.univariate.theta@1.0.0"
    assert diag.data["target_method_fqn"] == "econometrics.panel.fixed_effects@1.0.0"
    assert "alternative_methods" in diag.data
    assert "adapter_methods" in diag.data


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
