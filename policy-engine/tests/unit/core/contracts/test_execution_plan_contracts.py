from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from polisyos.core.canon import to_canonical_bytes
from polisyos.core.canon.canon_json import CanonSpec
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


def test_execution_plan_legacy_input_port_wire_omits_new_field() -> None:
    plan = ExecutionPlan(
        plan_id="legacy-byte-control",
        method_dag=[
            MethodDagNode(
                node_id="method-a",
                method_fqn="policy.example@1.0.0",
                reads_slots=["ledger.flow"],
            )
        ],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert plan.model_dump(mode="json")["schema_version"] == "1.0"
    assert "input_ports" not in plan.model_dump(mode="json")["method_dag"][0]
    assert (
        hashlib.sha256(to_canonical_bytes(plan, CanonSpec(forbid_floats=False))).hexdigest()
        == "d9e8c2f93073f5bcd3828f59890a1661c4d5b4cc6931fde39da32bf35435cec1"
    )


def test_execution_plan_input_ports_require_v12_and_exact_abi_keys() -> None:
    source = {"source_kind": "registry_slot", "slot_id": "ledger.flow"}
    node = MethodDagNode(
        node_id="method-a",
        method_fqn="policy.example@1.0.0",
        reads_slots=["period_flow"],
        input_ports={"period_flow": source},
    )

    with pytest.raises(ValueError, match="execution_plan_input_ports_version_mismatch"):
        ExecutionPlan(plan_id="legacy-map", method_dag=[node])
    with pytest.raises(ValueError, match="execution_plan_input_ports_abi_coverage_mismatch"):
        ExecutionPlan(
            plan_id="incomplete-map",
            schema_version="1.2",
            method_dag=[node.model_copy(update={"input_ports": {"other": source}})],
        )

    plan = ExecutionPlan(plan_id="mapped", schema_version="1.2", method_dag=[node])
    assert plan.model_dump(mode="json")["method_dag"][0]["input_ports"] == {"period_flow": source}
