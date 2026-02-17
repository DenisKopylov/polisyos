from __future__ import annotations

import pytest

from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    MethodDagNode,
    PlanDataNeed,
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
