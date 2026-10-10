from __future__ import annotations

from datetime import datetime

import pytest

from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    IterationState,
    MethodCatalogSnapshot,
    MethodDagNode,
    PlanDataNeed,
    ReproducibilityManifest,
)


def test_execution_plan_stable_hash_is_deterministic() -> None:
    plan = ExecutionPlan(
        plan_id="plan_test",
        run_id="R_test",
        data_needs=[PlanDataNeed(metric="macro.gdp", geography="PL")],
        method_dag=[
            MethodDagNode(
                node_id="m1",
                method_fqn="causal.inference.synthetic_control@1.0.0",
            )
        ],
    )
    left = plan.stable_hash()
    right = plan.stable_hash()
    assert left == right
    assert isinstance(left, str)
    assert len(left) >= 32


def test_method_dag_node_requires_fqn() -> None:
    with pytest.raises(Exception):
        MethodDagNode(node_id="m1", method_fqn="")


def test_execution_plan_defaults_are_aware_utc() -> None:
    plan = ExecutionPlan(plan_id="plan_utc")
    snapshot = MethodCatalogSnapshot(snapshot_id="snapshot_utc")
    state = IterationState(run_id="R_utc")
    manifest = ReproducibilityManifest(run_id="R_utc")

    assert plan.created_at.tzinfo is not None
    assert snapshot.generated_at.tzinfo is not None
    assert state.started_at.tzinfo is not None
    assert state.updated_at.tzinfo is not None
    assert manifest.created_at.tzinfo is not None


def test_execution_plan_rejects_naive_datetime_inputs() -> None:
    with pytest.raises(ValueError, match="Naive datetimes are not allowed"):
        ExecutionPlan(plan_id="plan_naive", created_at=datetime(2026, 1, 1, 12, 0, 0))
