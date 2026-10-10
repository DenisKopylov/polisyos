"""Internal welfare node orchestration helpers."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import Metrics, SimulationResult, SimulationResultRef
from polisyos.ir.analytics.welfare import (
    WelfareBundle,
    WelfareMethod,
    WelfareStatus,
    persist_welfare_bundle,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

from .welfare_context import (
    _collect_input_envelopes,
    _equilibrium_multiplicity_annotation,
    _extract_numeric_metrics,
    _has_explicit_welfare_request,
    _load_model,
    _load_welfare_params,
    _resolve_welfare_context,
    _source_social_weight_handle,
)
from .welfare_reports import (
    _build_robust_interval,
    _bundle_inputs,
    _maybe_build_channel_decomposition_ref,
    _persist_sensitivity_diagnostics,
    _point_total_vector,
    _resolve_bundle_method,
    _resolve_bundle_status,
    _resolve_interval_semantics,
    _resolve_subgroup_welfare,
)
from .welfare_types import (
    _DEFAULT_CONDITION_THRESHOLD,
    _ERROR_WELFARE_OUTPUT_NONFINITE,
    _EXPLICIT_GE_UNCERTAINTY_KEYS,
    _EXPLICIT_WELFARE_RESPONSE_KEYS,
    _WELFARE_LOAD_ERRORS,
    _fail_error,
    _input_ref,
    _PropagationOutcome,
    _WelfareNodeFailure,
)


@dataclass(frozen=True)
class _PreparedWelfareRun:
    sim_result_ref: ArtifactRef
    sim_result: SimulationResult
    collection: Any
    welfare_params: dict[str, Any]
    context: Any
    simulation_fn: Any
    nominal_params: dict[str, float]
    used_input_envelopes: dict[str, Any]
    pe_uncertainty_refs: dict[str, Any]


@dataclass(frozen=True)
class _WelfareEvaluation:
    point_outputs: Mapping[str, Any]
    point_estimate: float
    propagation: _PropagationOutcome
    robust_interval: tuple[float, float]
    robust_diagnostics: dict[str, Any]
    warnings: list[str]
    status: WelfareStatus
    method_used: WelfareMethod
    interval_semantics: Any
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class _PersistedWelfareRun:
    bundle_ref: Any
    simulation_result_ref: SimulationResultRef
    artifacts: list[ArtifactRef]


def _skip_for_missing_simulation(state: ExperimentState) -> NodeOutcome:
    return NodeOutcome(
        status="skip",
        state=state,
        events=[
            NodeEvent(level="info", message="No simulation_result_ref; skip welfare propagation")
        ],
    )


def _load_simulation_inputs(
    ctx: ExecutionContext, state: ExperimentState
) -> tuple[ArtifactRef, SimulationResult, Metrics] | NodeOutcome:
    sim_result_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    if sim_result_ref is None:
        return _skip_for_missing_simulation(state)
    try:
        sim_result = _load_model(ctx, sim_result_ref, SimulationResult)
        metrics = _load_model(ctx, sim_result.metrics_ref, Metrics)
    except _WelfareNodeFailure as exc:
        return NodeOutcome(
            status="fail",
            state=state,
            error=exc.error,
            events=[NodeEvent(level="error", code=exc.error.code, message=exc.error.message)],
        )
    except _WELFARE_LOAD_ERRORS as exc:
        return NodeOutcome(
            status="skip",
            state=state,
            events=[
                NodeEvent(
                    level="warn",
                    message=f"Unable to load simulation outputs for welfare: {exc}",
                )
            ],
        )
    return sim_result_ref, sim_result, metrics


def _prepare_welfare_run(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    sim_result_ref: ArtifactRef,
    sim_result: SimulationResult,
    welfare_params: dict[str, Any],
    numeric_metrics: Mapping[str, float],
    build_simulation_fn: Callable[..., Any],
) -> _PreparedWelfareRun | NodeOutcome:
    collection = _collect_input_envelopes(ctx, state, welfare_params=welfare_params)
    has_calibration_issue = bool(
        collection.calibration_source is not None and collection.calibration_source.issue_codes
    )
    has_explicit_request = _has_explicit_welfare_request(
        welfare_params,
        keys=_EXPLICIT_WELFARE_RESPONSE_KEYS | _EXPLICIT_GE_UNCERTAINTY_KEYS,
    )
    if not collection.envelopes and not has_calibration_issue and not has_explicit_request:
        return NodeOutcome(
            status="skip",
            state=state,
            events=[
                NodeEvent(
                    level="info",
                    code="welfare.inputs_missing",
                    message=(
                        "No welfare target or PE/GE uncertainty inputs supplied; "
                        "skip welfare propagation"
                    ),
                )
            ],
        )
    context = _resolve_welfare_context(
        ctx,
        welfare_params=welfare_params,
        numeric_metrics=numeric_metrics,
        response_size_hint=len(numeric_metrics),
    )
    simulation_fn, nominal_params, used_input_envelopes, pe_uncertainty_refs = build_simulation_fn(
        ctx,
        context=context,
        available_envelopes=collection,
        ge_condition_number_threshold=float(
            welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
        ),
    )
    has_ge_uncertainty = (
        context.ge_context.ge_uncertainty_ref is not None
        or context.ge_context.lower_multiplier is not None
        or context.ge_context.upper_multiplier is not None
    )
    if not used_input_envelopes and not has_ge_uncertainty and not has_calibration_issue:
        return NodeOutcome(
            status="skip",
            state=state,
            events=[
                NodeEvent(
                    level="info",
                    message="No PE or GE uncertainty supplied; skip welfare propagation",
                )
            ],
        )
    return _PreparedWelfareRun(
        sim_result_ref=sim_result_ref,
        sim_result=sim_result,
        collection=collection,
        welfare_params=welfare_params,
        context=context,
        simulation_fn=simulation_fn,
        nominal_params=nominal_params,
        used_input_envelopes=used_input_envelopes,
        pe_uncertainty_refs=pe_uncertainty_refs,
    )


def _evaluate_welfare_run(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    prepared: _PreparedWelfareRun,
    propagate_credible_interval: Callable[..., Any],
) -> _WelfareEvaluation:
    point_outputs = prepared.simulation_fn(**prepared.nominal_params)
    point_estimate = float(point_outputs["welfare"])
    if not math.isfinite(point_estimate):
        raise _fail_error(_ERROR_WELFARE_OUTPUT_NONFINITE, "Nominal welfare output is non-finite")
    propagation = propagate_credible_interval(
        ctx,
        state,
        welfare_params=prepared.welfare_params,
        context=prepared.context,
        simulation_fn=prepared.simulation_fn,
        nominal_params=prepared.nominal_params,
        input_envelopes=prepared.used_input_envelopes,
        input_envelope_refs=prepared.pe_uncertainty_refs,
        calibration_source=prepared.collection.calibration_source,
    )
    robust_interval, robust_diagnostics = _build_robust_interval(
        context=prepared.context,
        nominal_params=prepared.nominal_params,
        input_envelopes=prepared.used_input_envelopes,
    )
    if not all(math.isfinite(value) for value in robust_interval):
        raise _fail_error(
            _ERROR_WELFARE_OUTPUT_NONFINITE,
            "Robust welfare interval contains non-finite values",
        )
    warnings, status = _resolve_bundle_status(
        context=prepared.context,
        used_input_envelopes=prepared.used_input_envelopes,
        dependence_applied=bool(propagation.diagnostics.get("dependence_applied", False)),
    )
    limitation_codes = list(
        prepared.collection.calibration_source.issue_codes
        if prepared.collection.calibration_source is not None
        else ()
    )
    limitation_codes.extend(propagation.diagnostics.get("limitation_codes", ()))
    limitation_codes = list(dict.fromkeys(limitation_codes))
    _append_welfare_limitations(warnings, limitation_codes)
    if limitation_codes:
        status = WelfareStatus.PARTIAL
    method_used = _resolve_bundle_method(
        propagation.method_used,
        credible_interval=propagation.credible_interval,
        robust_interval=robust_interval,
    )
    interval_semantics = _resolve_interval_semantics(
        credible_interval=propagation.credible_interval,
        robust_interval=robust_interval,
    )
    diagnostics = _welfare_diagnostics(prepared, propagation, robust_diagnostics)
    if propagation.report_ref is not None:
        diagnostics["propagation_report_ref"] = str(propagation.report_ref.artifact_id)
    return _WelfareEvaluation(
        point_outputs=point_outputs,
        point_estimate=point_estimate,
        propagation=propagation,
        robust_interval=robust_interval,
        robust_diagnostics=robust_diagnostics,
        warnings=warnings,
        status=status,
        method_used=method_used,
        interval_semantics=interval_semantics,
        diagnostics=diagnostics,
    )


def _append_welfare_limitations(warnings: list[str], limitation_codes: list[str]) -> None:
    for code in limitation_codes:
        if code not in warnings:
            warnings.append(str(code))
    if "welfare_mc_incomplete_draws" in limitation_codes:
        warning = "welfare_mc_partial_nominal_point_conditional_mean"
        if warning not in warnings:
            warnings.append(warning)


def _welfare_diagnostics(
    prepared: _PreparedWelfareRun,
    propagation: _PropagationOutcome,
    robust_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    return {
        **prepared.context.diagnostics,
        "credible_method": propagation.method_used.value,
        "point_estimate_semantics": "nominal_input_evaluation",
        "input_envelope_count": len(prepared.used_input_envelopes),
        "pe_uncertainty_count": len(prepared.pe_uncertainty_refs),
        **propagation.diagnostics,
        "robust": robust_diagnostics,
    }


def _persist_welfare_run(
    ctx: ExecutionContext,
    *,
    prepared: _PreparedWelfareRun,
    evaluation: _WelfareEvaluation,
) -> _PersistedWelfareRun:
    propagation = evaluation.propagation
    context = prepared.context
    sensitivity_ref = _persist_sensitivity_diagnostics(
        ctx,
        simulation_fn=prepared.simulation_fn,
        nominal_params=prepared.nominal_params,
        input_envelopes=prepared.used_input_envelopes,
        robust_interval=evaluation.robust_interval,
    )
    total_vector = _point_total_vector(context, nominal_params=prepared.nominal_params)
    subgroup_welfare = _resolve_subgroup_welfare(
        welfare_params=prepared.welfare_params,
        labels=context.labels,
        total_vector=total_vector,
    )
    channel_ref = _maybe_build_channel_decomposition_ref(
        ctx,
        welfare_params=prepared.welfare_params,
        total_vector=total_vector,
    )
    equilibrium_multiplicity = _equilibrium_multiplicity_annotation(ctx, prepared.sim_result)
    bundle = WelfareBundle(
        welfare_measure=context.welfare_measure,
        model_class=context.model_class,
        ge_multiplier_semantics=context.ge_multiplier_semantics,
        policy_ref=context.policy_ref,
        baseline_ref=context.baseline_ref,
        pe_model_ref=context.pe_model_ref,
        ge_model_ref=context.ge_context.ge_model_ref,
        pe_uncertainty_refs=prepared.pe_uncertainty_refs,
        ge_uncertainty_ref=context.ge_context.ge_uncertainty_ref,
        dependence_structure_ref=context.dependence_structure_ref,
        social_weight_ref=context.social_weight_ref,
        welfare_weights_ref=context.weights_ref,
        channel_decomposition_ref=channel_ref,
        point_estimate=evaluation.point_estimate,
        credible_interval=propagation.credible_interval,
        robust_interval=evaluation.robust_interval,
        interval_semantics=evaluation.interval_semantics,
        channel_decomposition={
            "pe": float(evaluation.point_outputs["welfare_pe"]),
            "ge": float(evaluation.point_outputs["welfare_ge"]),
        },
        subgroup_welfare=subgroup_welfare,
        equilibrium_multiplicity=equilibrium_multiplicity,
        method_used=evaluation.method_used,
        method_config_ref=propagation.method_config_ref,
        sample_bundle_ref=propagation.sample_bundle_ref,
        sensitivity_diagnostics_ref=sensitivity_ref,
        warnings=evaluation.warnings,
        status=evaluation.status,
        diagnostics=evaluation.diagnostics,
        metadata={
            "response_labels": list(context.labels),
            "used_input_params": sorted(prepared.used_input_envelopes),
            "source_social_weight_handle": _source_social_weight_handle(prepared.welfare_params),
            "equilibrium_multiplicity_status": equilibrium_multiplicity.status,
        },
    )
    bundle_inputs = _bundle_inputs(
        sim_result_ref=prepared.sim_result_ref,
        metric_ref=prepared.sim_result.metrics_ref,
        pe_uncertainty_refs=prepared.pe_uncertainty_refs,
        ge_uncertainty_ref=context.ge_context.ge_uncertainty_ref,
        dependence_structure_ref=context.dependence_structure_ref,
        channel_decomposition_ref=channel_ref,
        method_config_ref=propagation.method_config_ref,
        report_ref=propagation.report_ref,
        sample_bundle_ref=propagation.sample_bundle_ref,
        calibration_report_ref=(
            prepared.collection.calibration_source.report_ref
            if prepared.collection.calibration_source is not None
            else None
        ),
        sensitivity_diagnostics_ref=sensitivity_ref,
    )
    bundle_ref = persist_welfare_bundle(
        _ensure_ir_artifact_store(ctx.store), bundle, inputs=bundle_inputs
    )
    updated_result = prepared.sim_result.model_copy(update={"welfare_bundle_ref": bundle_ref})
    updated_payload = ctx.store.put_json(
        updated_result,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.2"),
            inputs=[
                _input_ref(prepared.sim_result_ref, role="base_simulation_result"),
                _input_ref(bundle_ref, role="welfare_bundle"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    updated_ref = SimulationResultRef.model_validate(updated_payload.model_dump(mode="python"))
    artifacts: list[ArtifactRef] = [updated_ref, bundle_ref]
    _append_optional_artifacts(artifacts, context, propagation, channel_ref, sensitivity_ref)
    return _PersistedWelfareRun(
        bundle_ref=bundle_ref,
        simulation_result_ref=updated_ref,
        artifacts=artifacts,
    )


def _append_optional_artifacts(
    artifacts: list[ArtifactRef],
    context: Any,
    propagation: _PropagationOutcome,
    channel_ref: Any,
    sensitivity_ref: Any,
) -> None:
    refs = [
        channel_ref,
        context.ge_context.ge_uncertainty_ref,
        propagation.method_config_ref,
        propagation.report_ref,
        propagation.sample_bundle_ref,
        sensitivity_ref,
    ]
    artifacts.extend(ref for ref in refs if ref is not None)


def execute_welfare_node(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    build_simulation_fn: Callable[..., Any],
    propagate_credible_interval: Callable[..., Any],
) -> NodeOutcome:
    loaded = _load_simulation_inputs(ctx, state)
    if isinstance(loaded, NodeOutcome):
        return loaded
    sim_result_ref, sim_result, metrics = loaded
    welfare_params = _load_welfare_params(state)
    try:
        numeric_metrics = _extract_numeric_metrics(metrics)
        prepared = _prepare_welfare_run(
            ctx,
            state,
            sim_result_ref=sim_result_ref,
            sim_result=sim_result,
            welfare_params=welfare_params,
            numeric_metrics=numeric_metrics,
            build_simulation_fn=build_simulation_fn,
        )
        if isinstance(prepared, NodeOutcome):
            return prepared
        evaluation = _evaluate_welfare_run(
            ctx,
            state,
            prepared=prepared,
            propagate_credible_interval=propagate_credible_interval,
        )
        persisted = _persist_welfare_run(ctx, prepared=prepared, evaluation=evaluation)
    except _WelfareNodeFailure as exc:
        return NodeOutcome(
            status="fail",
            state=state,
            error=exc.error,
            events=[NodeEvent(level="error", code=exc.error.code, message=exc.error.message)],
        )
    return _publish_welfare_success(
        state,
        prepared=prepared,
        evaluation=evaluation,
        persisted=persisted,
    )


def _publish_welfare_success(
    state: ExperimentState,
    *,
    prepared: _PreparedWelfareRun,
    evaluation: _WelfareEvaluation,
    persisted: _PersistedWelfareRun,
) -> NodeOutcome:
    new_state = branch_state(state, write_paths=("artifacts_index",)).state
    new_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = persisted.simulation_result_ref
    new_state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = persisted.bundle_ref
    return NodeOutcome(
        status="ok",
        state=new_state,
        artifacts=persisted.artifacts,
        events=[
            NodeEvent(
                level="info",
                message=(
                    "Propagated welfare bundle "
                    f"(inputs={len(prepared.used_input_envelopes)}, status={evaluation.status.value})"
                ),
            )
        ],
    )
