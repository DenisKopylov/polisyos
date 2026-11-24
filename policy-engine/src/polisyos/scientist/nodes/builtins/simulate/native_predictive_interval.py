"""Project selected native state outcomes under one executable probability law."""

from __future__ import annotations

import math
from typing import ClassVar, Literal

import jax
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from polisyos.core.artifacts import (
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramGraph,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.compile.randomization import (
    TREASURY_SALTS_PROFILE,
    TreasuryPlan,
    build_treasury_plan,
)
from polisyos.foundry.execute import admit_execution_source, prepare_program_graph_mechanism_calls
from polisyos.foundry.execute.executor import (
    apply_patch_map,
    evaluate_selector,
    load_state_snapshot,
)
from polisyos.foundry.execute.mechanisms import LaborMarketMechanism
from polisyos.foundry.methods.catalog.mechanism.runtime_registry import get_mechanism_descriptor
from polisyos.ir.analytics.forecasting_uncertainty import (
    ForecastCalibrationMethod,
    HorizonInterval,
)
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.kernel.slots import SlotScope
from polisyos.scientist.nodes.builtins.simulate.uncertainty_source_projection import (
    PropagationReportV11,
    _load_validated_uncertainty_source_read,
)

_LAW_ROLE = "native_prediction_interval"
_PRODUCER = ProducerInfo(component="scientist.native_predictive_interval@1.0.0", version="1.0.0")


class NativeModelPredictionInterval(BaseModel):
    """One selected future state coordinate and its model-conditional interval."""

    ARTIFACT_KIND: ClassVar[str] = "scientist.native_model_prediction_interval"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.scientist.NativeModelPredictionInterval"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    schema_version: Literal["1.0"] = "1.0"
    law_version: Literal["labor_market.uniform_one_agent_income.v1"] = (
        "labor_market.uniform_one_agent_income.v1"
    )
    interval_semantics: Literal["prediction_interval"] = "prediction_interval"
    probability_scope: Literal["compiled_model_conditional_on_selected_state"] = (
        "compiled_model_conditional_on_selected_state"
    )
    evidence_grade: Literal["candidate"] = "candidate"
    gate_eligible: Literal[False] = False
    observational_calibration: Literal["not_established"] = "not_established"
    effective_sample_size: Literal["not_established"] = "not_established"
    causal_validity: Literal["not_established"] = "not_established"
    metric: str = Field(min_length=1)
    state_slot: Literal["agents.income"] = "agents.income"
    state_path: Literal["agents.income"] = "agents.income"
    unit_id: Literal["usd"] = "usd"
    coordinate: str = Field(min_length=1)
    cutoff: int = Field(gt=0)
    forecast_ref: ArtifactRef
    request_ref: ArtifactRef
    simulation_result_ref: SimulationResultRef
    baseline_ref: StateSnapshotRef
    mechanism_method_fqn: str = Field(min_length=1)
    interval: HorizonInterval
    achieved_model_mass: float = Field(default=1.0, ge=1.0, le=1.0)


def _stock_step_key(plan: TreasuryPlan, node_id: str, seed: int) -> jax.Array:
    """Reconstruct the selected treasury v1 key feeding the registered kernel."""
    key = jax.random.PRNGKey(seed)
    for salt in (plan.stream_salts["default"], plan.node_salts[node_id]):
        key = jax.random.fold_in(key, salt & 0xFFFFFFFF)
        key = jax.random.fold_in(key, salt >> 32)
    return jax.random.split(key)[1]


def _derive_model_prediction(
    store: FileSystemCAS,
    forecast_ref: ArtifactRef,
    request_ref: ArtifactRef,
    *,
    metric: str,
    coordinate: str,
    nominal_level: float,
) -> NativeModelPredictionInterval:
    """Reconcile the forecast source and the compiled one-agent outcome law."""
    from polisyos.scientist.methods.backtesting.native_replay import (
        _edge,
        _edge_ref,
        load_native_forecast,
    )

    if type(nominal_level) is not float or not 0.0 < nominal_level < 1.0:
        raise ValueError("native outcome interval nominal level is invalid")
    forecast, request = load_native_forecast(store, forecast_ref, request_ref)
    if request.profile.time_index != [coordinate] or len(request.profile.targets) != 1:
        raise ValueError("native outcome interval requires one selected forecast coordinate")
    target = request.profile.targets[0]
    if (
        target.metric != metric
        or target.slot_id != "agents.income"
        or target.unit_id != "usd"
        or target.reduction not in {"identity", "mean"}
    ):
        raise ValueError("native outcome interval quantity is outside the selected law")
    simulation_ref = forecast.simulation_refs[0]
    admission = admit_execution_source(store, simulation_ref)
    basis = admission.basis
    if basis is None or admission.mode != "single_step_basis":
        raise ValueError("native outcome interval requires the selected single-step basis")
    registry = load_registry_bundle_content(store, basis.runtime_registry_ref)
    slot = registry.slot_registry.slots[target.slot_id]
    if slot.state_path != "agents.income":
        raise ValueError("native outcome interval state path differs from its law")
    baseline = load_state_snapshot(store, snapshot_ref=basis.base_state_snapshot_ref)
    if (
        baseline.agents.income.shape != (1,)
        or baseline.firms.wage_offer.shape != (1,)
        or not bool(np.asarray(baseline.agents.active)[0])
        or not bool(np.asarray(baseline.firms.active)[0])
    ):
        raise ValueError("native outcome interval requires one active agent and one active firm")

    graph = validate_core_model_json_artifact(ProgramGraph, store, basis.program_graph_ref)
    nodes = {node.node_id: node for node in graph.nodes}
    expected_ops = {"make_mask", "apply_mechanism", "merge_state", "check_constraints"}
    if (
        len(nodes) != 4
        or {node.op.op_kind for node in nodes.values() if node.op is not None} != expected_ops
        or any(node.node_kind != "op" or node.op is None for node in nodes.values())
    ):
        raise ValueError("native outcome interval graph exceeds the supported single law")
    registered_calls = prepare_program_graph_mechanism_calls(
        store,
        program_ref=basis.program_graph_ref,
        exec_plan_ref=basis.exec_plan_ref,
        base_state=baseline,
        mechanism_registry=registry.mechanism_registry,
        steps=(basis.effective_step,),
        actuation_selection_ref=basis.actuation_selection_ref,
    )
    if len(registered_calls) != 1:
        raise ValueError("native outcome interval expects one scheduled mechanism call")
    _, node_id, _, bound_call = registered_calls[0]
    mechanism = getattr(bound_call, "__self__", None)
    node = nodes[node_id]
    if (
        type(mechanism) is not LaborMarketMechanism
        or node.mechanism_type != "labor_market"
        or float(mechanism.employment_threshold) != 0.5
        or node.op is None
        or node.op.op_kind != "apply_mechanism"
    ):
        raise ValueError("native outcome interval requires the registered half-threshold law")
    mask_node = nodes[node.op.params["mask_id"]]
    if mask_node.op is None or mask_node.op.op_kind != "make_mask":
        raise ValueError("native outcome interval target selector is unavailable")
    selector = TypeAdapter(SelectorExpr).validate_python(mask_node.op.params["selector"])
    target_mask, scope = evaluate_selector(
        selector, baseline, selector_field_registry=registry.selector_field_registry
    )
    if scope is not SlotScope.PER_AGENT or tuple(np.asarray(target_mask)) != (True,):
        raise ValueError("native outcome interval target does not select the active agent")

    plan = validate_core_model_json_artifact(ExecPlan, store, basis.exec_plan_ref)
    treasury_ref = _edge_ref(store, basis.exec_plan_ref, "treasury_plan", "foundry.treasury_plan")
    _edge(store, treasury_ref, basis.program_graph_ref, "program_graph")
    treasury = TreasuryPlan.model_validate(load_core_json_artifact(store, treasury_ref))
    if TREASURY_SALTS_PROFILE not in plan.notes or treasury != build_treasury_plan(
        graph, root_seed=plan.random_seed or 0
    ):
        raise ValueError("native outcome interval randomization source differs from its plan")
    patches, _ = mechanism.emit_patches(
        baseline, _stock_step_key(treasury, node_id, basis.effective_seed), target_mask=target_mask
    )
    actual = apply_patch_map(
        baseline,
        patches,
        slot_registry=registry.slot_registry,
        merge_registry=registry.merge_registry,
        default_node_id=node_id,
    )
    point = float(np.asarray(actual.agents.income)[0])
    wage = float(np.asarray(baseline.firms.wage_offer * baseline.agents.skill_level)[0])
    if not math.isfinite(wage) or wage <= 0.0 or point not in (0.0, wage):
        raise ValueError("native outcome interval has unsupported realized support")
    if forecast.values != {metric: [point]}:
        raise ValueError("native outcome interval kernel result differs from the physical output")

    return NativeModelPredictionInterval(
        metric=metric,
        coordinate=coordinate,
        cutoff=request.cutoff,
        forecast_ref=forecast_ref,
        request_ref=request_ref,
        simulation_result_ref=simulation_ref,
        baseline_ref=basis.base_state_snapshot_ref,
        mechanism_method_fqn=get_mechanism_descriptor("labor_market").method_fqn,
        interval=HorizonInterval(
            horizon=1,
            point=point,
            lower=0.0,
            upper=wage,
            coverage_target=nominal_level,
            constructor=ForecastCalibrationMethod.PARAMETRIC,
        ),
    )


def _law_inputs(result: NativeModelPredictionInterval) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(result.forecast_ref, role="native_forecast"),
        input_ref_from_artifact_ref(result.request_ref, role="native_forecast_request"),
        input_ref_from_artifact_ref(result.simulation_result_ref, role="model_execution"),
        input_ref_from_artifact_ref(result.baseline_ref, role="model_baseline"),
    ]


def _report(result: NativeModelPredictionInterval) -> PropagationReportV11:
    return PropagationReportV11(
        schema_version="1.1",
        input_envelope_count=0,
        output_metric_count=1,
        mapped_param_count=0,
        mapped_params=[],
        mapping_status="candidate_only",
        mapping_source="not_established",
        mapping_basis_status="candidate_only",
        unmapped_metric_ids=[],
        missing_output_metric_ids=[],
        methods=["analytical"],
        diagnostics=[
            {
                "metric_id": result.metric,
                "method": "analytical",
                "diagnostics": {
                    "predicted_quantity": "future_observation_in_selected_model",
                    "interval_semantics": result.interval_semantics,
                    "law_version": result.law_version,
                },
            }
        ],
        incomplete_output_metric_ids=[],
    )


def _simulation_edges(
    base_ref: SimulationResultRef, base: SimulationResult, report_ref: ArtifactRef
) -> list[InputRef]:
    edges = [
        input_ref_from_artifact_ref(base_ref, role="base_simulation_result"),
        input_ref_from_artifact_ref(report_ref, role="propagation_report"),
    ]
    if base.execution_input_basis_ref is not None:
        edges.append(
            input_ref_from_artifact_ref(
                base.execution_input_basis_ref, role="execution_input_basis"
            )
        )
    return edges


def persist_native_model_prediction(
    store: FileSystemCAS,
    forecast_ref: ArtifactRef,
    request_ref: ArtifactRef,
    *,
    metric: str,
    coordinate: str,
    nominal_level: float,
) -> SimulationResultRef:
    """Persist an interval report derived from the selected physical forecast.

    The returned SimulationResult selects the exact report and law while the
    original physical execution remains available under its original ref.
    """
    result = _derive_model_prediction(
        store,
        forecast_ref,
        request_ref,
        metric=metric,
        coordinate=coordinate,
        nominal_level=nominal_level,
    )
    base = validate_core_model_json_artifact(SimulationResult, store, result.simulation_result_ref)
    if base.propagation_report_ref is not None:
        raise ValueError("native outcome interval cannot replace an existing propagation report")
    inputs = _law_inputs(result)
    law_ref = store.put_json(
        result,
        PutOptions(
            kind=result.ARTIFACT_KIND,
            media_type=result.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=result.ARTIFACT_SCHEMA_NAME, version=result.ARTIFACT_SCHEMA_VERSION
            ),
            producer=_PRODUCER,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    report = _report(result)
    report_ref = store.put_json(
        report,
        PutOptions(
            kind=report.ARTIFACT_KIND,
            media_type=report.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=report.ARTIFACT_SCHEMA_NAME, version=report.ARTIFACT_SCHEMA_VERSION
            ),
            producer=_PRODUCER,
            inputs=[*inputs, input_ref_from_artifact_ref(law_ref, role=_LAW_ROLE)],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    projection = base.model_copy(update={"propagation_report_ref": report_ref})
    selected = store.put_json(
        projection.to_artifact_payload(),
        PutOptions(
            kind=base.ARTIFACT_KIND,
            media_type=base.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=base.ARTIFACT_SCHEMA_NAME, version=base.schema_version),
            producer=_PRODUCER,
            inputs=_simulation_edges(result.simulation_result_ref, base, report_ref),
        ),
        return_selected_profile=True,
    )
    return SimulationResultRef.model_validate(selected.model_dump(mode="python"))


def _require_lineage(store: FileSystemCAS, ref: ArtifactRef, expected: list[InputRef]) -> None:
    manifest = store.get_manifest(ref)
    if manifest.producer != _PRODUCER or sorted(
        manifest.inputs, key=lambda item: item.role
    ) != sorted(expected, key=lambda item: item.role):
        raise ValueError("native outcome interval selected lineage mismatch")


def load_native_model_prediction(
    store: FileSystemCAS,
    derived_ref: SimulationResultRef,
    forecast_ref: ArtifactRef,
    request_ref: ArtifactRef,
    *,
    metric: str,
    coordinate: str,
    nominal_level: float,
) -> NativeModelPredictionInterval:
    """Reopen the exact report, outcome and conditional interval without redispatch."""
    from polisyos.scientist.methods.backtesting.native_replay import _edge_ref

    if derived_ref.manifest_profile_sha256 is None:
        raise ValueError("native outcome interval requires an exact selected SimulationResult")
    projection = _load_validated_uncertainty_source_read(store, derived_ref)
    report = projection.propagation_report
    report_ref = projection.simulation_result.propagation_report_ref
    if report_ref is None or report_ref.manifest_profile_sha256 is None:
        raise ValueError("native outcome interval requires an exact selected PropagationReport")
    law_ref = _edge_ref(store, report_ref, _LAW_ROLE, NativeModelPredictionInterval.ARTIFACT_KIND)
    retained = validate_core_model_json_artifact(NativeModelPredictionInterval, store, law_ref)
    if (
        retained.forecast_ref != forecast_ref
        or retained.request_ref != request_ref
        or retained.metric != metric
        or retained.coordinate != coordinate
        or retained.interval.coverage_target != nominal_level
    ):
        raise ValueError("native outcome interval does not match the requested forecast cell")
    inputs = _law_inputs(retained)
    _require_lineage(store, law_ref, inputs)
    _require_lineage(
        store, report_ref, [*inputs, input_ref_from_artifact_ref(law_ref, role=_LAW_ROLE)]
    )
    base = validate_core_model_json_artifact(
        SimulationResult, store, retained.simulation_result_ref
    )
    _require_lineage(
        store, derived_ref, _simulation_edges(retained.simulation_result_ref, base, report_ref)
    )
    expected = _derive_model_prediction(
        store,
        forecast_ref,
        request_ref,
        metric=metric,
        coordinate=coordinate,
        nominal_level=nominal_level,
    )
    if (
        retained != expected
        or report != _report(expected)
        or projection.simulation_result
        != base.model_copy(update={"propagation_report_ref": report_ref})
    ):
        raise ValueError("native outcome interval differs from the selected law or result")
    return retained
