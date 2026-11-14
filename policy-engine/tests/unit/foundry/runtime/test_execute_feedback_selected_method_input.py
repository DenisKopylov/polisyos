"""Candidate fixed-point execution over one immutable selected monetary input."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    FeedbackConfig,
    FeedbackConfigRef,
    FeedbackConvergenceCertificate,
    FeedbackIterationRecord,
    FeedbackSolveResult,
    FeedbackSolverConfig,
    FeedbackTrace,
    FoundryInputBindings,
)
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import (
    MethodMetadata,
    MethodPatchTargetContract,
    MethodSignature,
    SideEffectProfile,
    SlotSpec,
    SlotType,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.types.units import Units
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case


class _RetainedPeriodFlowMap:
    """Synthetic candidate map: retain half the aggregate stock, then add flow."""

    signature: ClassVar[MethodSignature] = replace(
        PeriodFlowToStock.signature,
        namespace="tests.selected_input_feedback",
        name="retained_period_flow_map",
        input_slots=frozenset(
            {
                *PeriodFlowToStock.signature.input_slots,
                SlotSpec(
                    name="government.balance",
                    slot_type=SlotType.SCALAR,
                    unit=Units.USD,
                    description="Model-declared accumulated stock before this candidate step.",
                ),
            }
        ),
        patch_targets=(
            MethodPatchTargetContract(
                target_parameter="target_slot",
                source_input="period_flow",
            ),
        ),
    )
    metadata: ClassVar[MethodMetadata] = replace(
        PeriodFlowToStock.metadata,
        description=(
            "Synthetic candidate map for exercising a model-declared fixed point over an "
            "annual monetary flow and an accumulated stock."
        ),
        equations={"stock_end": "0.5 * stock_start + period_flow"},
        assumptions={
            "empirical_status": "not_established",
            "authority": "candidate arithmetic only; no publication authority",
            "target_semantics": (
                "The fixture's government.balance is an accumulated model stock, not cash on hand."
            ),
            "flow_semantics": (
                "period_flow is one selected annual period total; no time multiplier is applied."
            ),
        },
        side_effect_profile=SideEffectProfile.PATCH_EMISSION,
        when_to_use="Test the solver-to-selected-input bridge only.",
        when_not_to_use="Never treat this synthetic equation as an empirical policy model.",
        output_interpretation=(
            "The output is a candidate fixed point of this fixture's declared equation only."
        ),
    )

    @staticmethod
    def pure_step(state, params):
        if set(state) != {"government.balance", "period_flow"}:
            raise ValueError("feedback_candidate_input_mapping_invalid")
        stock = float(state["government.balance"])
        period_flow = float(state["period_flow"])
        stock_end = 0.5 * stock + period_flow
        delta = np.asarray(stock_end - stock, dtype=np.float64)
        return {
            "result": stock_end,
            "patch_records": {params["target_slot"]: [{"delta": delta}]},
        }


def _selected_value_sha256(value: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _feedback_config_ref(store, *, max_iter: int = 60):
    config = FeedbackConfig(
        variables=[
            {
                "variable_id": "accumulated_stock",
                "source_kind": "state_path",
                "source_ref": "government_balance",
                "target_kind": "state_path",
                "target_ref": "government_balance",
                "initial_value": 0.0,
                "lower_bound": -100.0,
                "upper_bound": 100.0,
                "scale": 1.0,
            }
        ],
        solver=FeedbackSolverConfig(
            mode="picard",
            homotopy_grid=[0.0, 1.0],
            damping_init=1.0,
            damping_min=1.0,
            max_iter=max_iter,
            anderson_start=max_iter + 1,
            newton_start=max_iter + 1,
            max_restarts=0,
            stagnation_patience=max_iter + 1,
            compute_jacobian_diagnostics=False,
            store_alternative_fixed_points=False,
        ),
        notes=["synthetic_candidate_only:no_empirical_or_cash_claim"],
    )
    artifact = store.put_json(
        config,
        PutOptions(
            kind=FeedbackConfig.ARTIFACT_KIND,
            media_type=FeedbackConfig.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FeedbackConfig.ARTIFACT_SCHEMA_NAME,
                version=FeedbackConfig.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return FeedbackConfigRef.model_validate(artifact.model_dump(mode="python"))


def _execute(case, materialized, feedback_ref):
    from polisyos.core.contracts.foundry import ExecuteRequest

    return execute_foundry(
        case.store,
        ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=materialized.input_bindings_ref,
            feedback_config_ref=feedback_ref,
            return_selected_profile=True,
        ),
    )


def _without_selected_method_values(case, materialized):
    bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
    payload = bindings.model_dump(mode="python", exclude={"selected_method_inputs"})
    payload["schema_version"] = "1.2"
    unbound = FoundryInputBindings.model_validate(payload)
    manifest = case.store.get_manifest(materialized.input_bindings_ref)
    artifact = case.store.put_json(
        unbound,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version="1.2",
            ),
            inputs=[
                edge for edge in manifest.inputs if not edge.role.startswith("method_input.")
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return replace(materialized, input_bindings_ref=artifact)


def _fresh_reader(case, simulation_result_ref):
    product_root = Path(__file__).resolve().parents[4]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(product_root / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    code = """
import hashlib, json, sys
from io import BytesIO
import numpy as np
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import (
    FeedbackConvergenceCertificate, FeedbackSolveResult, FeedbackTrace,
    MethodExecutionBundle, SimulationResult, SimulationResultRef,
)
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.executor import load_state_snapshot
store = FileSystemCAS(sys.argv[1])
result_ref = SimulationResultRef.model_validate_json(sys.argv[2])
result = validate_core_model_json_artifact(SimulationResult, store, result_ref)
admitted = admit_execution_source(store, result_ref)
assert admitted.mode == "single_step_basis"
assert result.feedback_result_ref is not None
feedback = validate_core_model_json_artifact(
    FeedbackSolveResult, store, result.feedback_result_ref
)
assert feedback.converged and feedback.convergence_certificate_ref is not None
certificate = validate_core_model_json_artifact(
    FeedbackConvergenceCertificate, store, feedback.convergence_certificate_ref
)
assert certificate.converged and feedback.trace_ref is not None
trace = validate_core_model_json_artifact(FeedbackTrace, store, feedback.trace_ref)
assert trace.records
bindings_edge = next(edge for edge in store.get_manifest(result_ref).inputs
    if edge.role == "input.input_bindings_ref")
bindings_ref = ArtifactRef(artifact_id=bindings_edge.artifact_id,
    manifest_profile_sha256=bindings_edge.manifest_profile_sha256,
    kind="foundry.input_bindings", media_type="application/json")
bindings = load_input_bindings(store, bindings_ref)
assert admitted.basis.input_bindings_ref.artifact_id == bindings_ref.artifact_id
(selected,) = bindings.selected_method_inputs
selected_value = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
digest = hashlib.sha256()
digest.update(selected_value.dtype.str.encode("ascii"))
digest.update(json.dumps(selected_value.shape, separators=(",", ":")).encode("ascii"))
digest.update(selected_value.tobytes(order="C"))
assert digest.hexdigest() == selected.value_sha256
method_edge = next(edge for edge in store.get_manifest(result_ref).inputs
    if edge.role == "method_execution")
method_ref = ArtifactRef(artifact_id=method_edge.artifact_id,
    manifest_profile_sha256=method_edge.manifest_profile_sha256,
    kind=MethodExecutionBundle.ARTIFACT_KIND, media_type="application/json")
bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, method_ref)
occurrences = [item for item in bundle.occurrences if item.node_kind == "method"]
assert len(occurrences) >= 2
occurrences_by_invocation = {item.invocation_id: item for item in occurrences}
map_evaluations = getattr(trace, "map_evaluations", ())
assert map_evaluations
assert all(item.graph_invocation_id in occurrences_by_invocation for item in map_evaluations)
assert all(item.base_state_ref.artifact_id == bindings.bound_state_snapshot_ref.artifact_id
    for item in map_evaluations)
for occurrence in occurrences:
    assert occurrence.dispatch is not None and occurrence.dispatch.outcome == "succeeded"
    args = {item.slot_id: item for item in occurrence.dispatch.input_slot_values}
    assert args["period_flow"].value_sha256 == selected.value_sha256
final_invocation_id = feedback.final_diagnostics["final_graph_invocation_id"]
assert list(occurrences_by_invocation).count(final_invocation_id) == 1
final_args = {
    item.slot_id: item
    for item in occurrences_by_invocation[final_invocation_id].dispatch.input_slot_values
}
final_state_input = final_args["government.balance"]
final_input_value = np.asarray(feedback.final_state.values[0],
    dtype=np.dtype(final_state_input.runtime_dtype))
final_input_hash = hashlib.sha256()
final_input_hash.update(final_input_value.dtype.str.encode("ascii"))
final_input_hash.update(json.dumps(final_input_value.shape, separators=(",", ":")).encode("ascii"))
final_input_hash.update(final_input_value.tobytes(order="C"))
assert final_state_input.value_sha256 == final_input_hash.hexdigest()
state = load_state_snapshot(store, snapshot_ref=admitted.simulation_result.state_snapshot_ref)
print(json.dumps({"stock": float(state.government_balance),
    "solution": feedback.final_state.values[0], "forcing": float(selected_value.item()),
    "calls": len(occurrences), "status": feedback.status}))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(case.store_root),
            simulation_result_ref.model_dump_json(),
        ],
        cwd=product_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    ("ratio_value", "expected_flow", "expected_stock"),
    [
        (Decimal("0.000000000005"), 1.0, 2.0),
        (Decimal("0.00000000001"), 2.0, 4.0),
    ],
)
def test_feedback_solver_consumes_selected_period_flow_and_fresh_reader(
    tmp_path, ratio_value, expected_flow, expected_stock
):
    registry = MethodRegistry.get_instance()
    case, metadata = prepare_selected_method_input_case(
        tmp_path, method_class=_RetainedPeriodFlowMap
    )
    try:
        materialized = materialize_selected_method_input_case(
            case, metadata, ratio_value=ratio_value
        )
        feedback_ref = _feedback_config_ref(case.store)
        executed = _execute(case, materialized, feedback_ref)
        assert executed.ok and executed.simulation_result_ref is not None
        assert executed.method_execution_bundle_ref is not None
        feedback_ref_out = next(
            item.ref for item in executed.derived_refs if item.role == "feedback_result"
        )
        feedback = validate_core_model_json_artifact(
            FeedbackSolveResult, case.store, feedback_ref_out
        )
        assert feedback.converged and feedback.status == "converged"
        assert feedback.trace_ref is not None
        trace = validate_core_model_json_artifact(FeedbackTrace, case.store, feedback.trace_ref)
        assert trace.records and any(
            isinstance(record, FeedbackIterationRecord) for record in trace.records
        )
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        assert bindings.selected_method_inputs is not None
        (selected,) = bindings.selected_method_inputs
        forcing = np.load(BytesIO(case.store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
        assert forcing.shape == () and forcing.dtype == np.dtype(np.float64)
        assert selected.value_sha256 == _selected_value_sha256(forcing)
        assert float(forcing.item()) == pytest.approx(expected_flow)
        assert expected_stock == pytest.approx(2.0 * float(forcing.item()))
        fresh = _fresh_reader(case, executed.simulation_result_ref)
        assert fresh["status"] == "converged"
        assert fresh["forcing"] == pytest.approx(float(forcing.item()))
        assert fresh["solution"] == pytest.approx(expected_stock, abs=1e-5)
        assert fresh["stock"] == pytest.approx(expected_stock, abs=1e-5)
        assert fresh["calls"] >= 2
    finally:
        registry.register(PeriodFlowToStock, override=True)
        case.close()


def test_feedback_nonconvergence_preserves_candidate_without_simulation_result(tmp_path):
    registry = MethodRegistry.get_instance()
    case, metadata = prepare_selected_method_input_case(
        tmp_path, method_class=_RetainedPeriodFlowMap
    )
    try:
        materialized = materialize_selected_method_input_case(
            case, metadata, ratio_value=Decimal("0.000000000005")
        )
        feedback_ref = _feedback_config_ref(case.store, max_iter=1)
        executed = _execute(case, materialized, feedback_ref)
        assert not executed.ok and executed.simulation_result_ref is None
        feedback_ref_out = next(
            item.ref for item in executed.derived_refs if item.role == "feedback_result"
        )
        feedback = validate_core_model_json_artifact(
            FeedbackSolveResult, case.store, feedback_ref_out
        )
        assert not feedback.converged
        assert feedback.status != "converged"
        assert feedback.convergence_certificate_ref is not None
        certificate = validate_core_model_json_artifact(
            FeedbackConvergenceCertificate,
            case.store,
            feedback.convergence_certificate_ref,
        )
        assert not certificate.converged
        assert certificate.status == feedback.status
        assert feedback.trace_ref is not None
        trace = validate_core_model_json_artifact(FeedbackTrace, case.store, feedback.trace_ref)
        assert trace.records
    finally:
        registry.register(PeriodFlowToStock, override=True)
        case.close()


def test_feedback_refuses_declared_flow_port_without_selected_value(tmp_path, monkeypatch):
    registry = MethodRegistry.get_instance()
    case, metadata = prepare_selected_method_input_case(
        tmp_path, method_class=_RetainedPeriodFlowMap
    )
    calls = []

    def forbidden_dispatch(*args, **kwargs):
        calls.append(True)
        raise AssertionError("unbound method input reached dispatch")

    try:
        materialized = materialize_selected_method_input_case(
            case, metadata, ratio_value=Decimal("0.000000000005")
        )
        feedback_ref = _feedback_config_ref(case.store)
        unbound = _without_selected_method_values(case, materialized)
        monkeypatch.setattr(MethodDispatcher, "dispatch", forbidden_dispatch)
        with pytest.raises(ValueError, match="method_input_unbound"):
            _execute(case, unbound, feedback_ref)
        assert calls == []
    finally:
        registry.register(PeriodFlowToStock, override=True)
        case.close()
