"""Prove a selected float64 period flow is preserved by stock execution."""

from __future__ import annotations

import json
from decimal import Decimal
from io import BytesIO

import numpy as np

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import ExecuteRequest, MethodExecutionBundle, StateDelta
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.foundry.runtime.test_selected_method_inputs import (
    _fresh_process_read,
    _independent_value_sha256,
)


def test_selected_one_dollar_flow_is_not_silently_lost_in_float32_stock(tmp_path):
    """Keep the one-dollar arithmetic distinction visible through persisted output."""
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
    )
    try:
        materialized = materialize_selected_method_input_case(
            case,
            metadata,
            ratio_value=Decimal("-1"),
            denominator_value=Decimal("1"),
        )
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        (selected,) = bindings.selected_method_inputs or ()
        selected_value = np.load(
            BytesIO(case.store.get_bytes(selected.npy_value_ref)), allow_pickle=False
        )
        assert selected_value.shape == ()
        assert selected_value.dtype == np.dtype(np.float64)
        assert float(selected_value) == -1.0
        base_state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        initial_stock = float(base_state.government_balance)
        assert initial_stock == 10_000_000_000.0

        executed = execute_foundry(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                return_selected_profile=True,
            ),
        )
        if not executed.ok:
            assert executed.simulation_result_ref is None
            assert "method_patch_arithmetic_precision_not_representable" in executed.notes, (
                f"public_execute_refused_without_typed_precision_reason:{executed.notes!r}"
            )
            return
        assert executed.simulation_result_ref is not None
        assert executed.method_execution_bundle_ref is not None

        capture = validate_core_model_json_artifact(
            MethodExecutionBundle, case.store, executed.method_execution_bundle_ref
        )
        (occurrence,) = (item for item in capture.occurrences if item.node_kind == "method")
        assert occurrence.status == "succeeded" and occurrence.dispatch is not None
        (argument,) = occurrence.dispatch.input_slot_values
        assert argument.slot_id == "period_flow" and argument.status == "captured"

        delta_edge = next(
            edge
            for edge in case.store.get_manifest(executed.simulation_result_ref).inputs
            if edge.role == "state_delta"
        )
        delta = validate_core_model_json_artifact(
            StateDelta,
            case.store,
            ArtifactRef(
                artifact_id=delta_edge.artifact_id,
                manifest_profile_sha256=delta_edge.manifest_profile_sha256,
                kind=StateDelta.ARTIFACT_KIND,
                media_type="application/json",
            ),
        )
        (operation,) = delta.ops
        value = np.load(BytesIO(case.store.get_bytes(operation.value_ref)), allow_pickle=False)
        observed = {
            "initial_stock": initial_stock,
            "selected_flow": float(selected_value),
            "selected_sha256": selected.value_sha256,
            "method_status": occurrence.status,
            "argument_sha256": argument.value_sha256,
            "argument_dtype": argument.runtime_dtype,
            "state_delta_slot": operation.slot_id,
            "state_delta_op": operation.op,
            "state_delta_value": float(value),
        }

        cold = FileSystemCAS(case.store_root)
        try:
            admitted = admit_execution_source(cold, executed.simulation_result_ref)
            state = load_state_snapshot(
                cold, snapshot_ref=admitted.simulation_result.state_snapshot_ref
            )
            observed["final_stock"] = float(state.government_balance)
        finally:
            close = getattr(cold, "close", None)
            if callable(close):
                close()

        observed.update(_fresh_process_read(case, executed.simulation_result_ref))
        expected_sha256 = _independent_value_sha256(-1.0)
        expected = {
            "initial_stock": 10_000_000_000.0,
            "selected_sha256": expected_sha256,
            "argument_sha256": expected_sha256,
            "state_delta_slot": "government.balance",
            "state_delta_op": "add",
            "state_delta_value": -1.0,
            "final_stock": 9_999_999_999.0,
            "stock": 9_999_999_999.0,
        }
        actual = {key: observed[key] for key in expected}
        assert actual == expected, (
            "selected flow must survive as a one-dollar stock decrement; "
            f"expected={json.dumps(expected, sort_keys=True)} "
            f"observed={json.dumps(observed, sort_keys=True)}"
        )
    finally:
        case.close()
