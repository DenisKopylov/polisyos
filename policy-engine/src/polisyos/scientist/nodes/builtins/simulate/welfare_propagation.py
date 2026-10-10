"""Internal welfare propagation implementation helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from statistics import NormalDist
from typing import Any, cast

import numpy as np

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.foundry.uncertainty import PropagationConfig
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, persist_uncertainty_envelope
from polisyos.ir.analytics.welfare import (
    WelfareMethod,
    WelfareSampleBundle,
    persist_welfare_sample_bundle,
)
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    UncertaintyEnvelopeRef,
    WelfareSampleBundleRef,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

from .welfare_covariance import (
    _build_dependence_sampler,
    _build_parameter_covariance,
    _calibration_dependence_sampler,
    _calibration_lineage_inputs,
    _calibration_projection_report_metadata,
    _limited_covariance_outcome,
    _resolve_calibration_covariance,
    _resolve_empirical_row_sampler,
)
from .welfare_draws import (
    _draw_outcome_provenance,
    _DrawAttemptResult,
    _evaluate_welfare_draw,
    _evaluate_welfare_draw_attempt,
    _finite_difference_gradient,
    _finite_difference_step,
    _MonteCarloCounters,
    _MonteCarloDrawSet,
    _raise_welfare_mc_execution_failure,
    _run_welfare_monte_carlo_draws,
    _validate_welfare_draw_outputs,
    _welfare_draw_failure_scope,
    _welfare_draw_set_is_complete,
    _welfare_draw_terminal_outcome,
    _welfare_execution_attempt,
    _welfare_sampled_input_sha256,
)
from .welfare_ge import _invert_sampled_ge_operator
from .welfare_reports import (
    _load_propagation_config,
    _persist_welfare_mc_report,
    _persist_welfare_mc_samples,
)
from .welfare_types import (
    _DEFAULT_CONDITION_THRESHOLD,
    _ERROR_INTERVAL_SEMANTICS_INVALID,
    _ERROR_MONTE_CARLO_NOT_CONVERGED,
    _WELFARE_MC_MAX_EXECUTION_ATTEMPTS,
    _CalibrationCovarianceSource,
    _EnvelopeCollection,
    _extract_std,
    _fail_error,
    _input_envelope_refs,
    _input_ref,
    _persist_json_payload,
    _PropagationOutcome,
    _ResolvedWelfareContext,
)


def _resolve_pe_simulation_envelopes(
    context: _ResolvedWelfareContext,
    available_envelopes: _EnvelopeCollection,
) -> tuple[dict[str, float], dict[str, UncertaintyEnvelope], dict[str, UncertaintyEnvelopeRef]]:
    nominal_params: dict[str, float] = {}
    used_envelopes: dict[str, UncertaintyEnvelope] = {}
    pe_refs: dict[str, UncertaintyEnvelopeRef] = {}
    for label in context.labels:
        for param_name in context.pe_sensitivity.get(label, {}):
            envelope = available_envelopes.envelopes.get(param_name)
            if envelope is not None:
                used_envelopes[param_name] = envelope
                nominal_params[param_name] = float(envelope.point_estimate)
                if param_name in available_envelopes.refs:
                    pe_refs[param_name] = available_envelopes.refs[param_name]
    return nominal_params, used_envelopes, pe_refs


def _add_ge_simulation_envelopes(
    context: _ResolvedWelfareContext,
    available_envelopes: _EnvelopeCollection,
    *,
    nominal_params: dict[str, float],
    used_envelopes: dict[str, UncertaintyEnvelope],
) -> None:
    for param_name in context.ge_context.ge_entry_map:
        envelope = available_envelopes.envelopes.get(param_name)
        if envelope is not None:
            used_envelopes[param_name] = envelope
            nominal_params[param_name] = float(envelope.point_estimate)


def _bind_pe_envelope_refs(
    ctx: ExecutionContext,
    *,
    context: _ResolvedWelfareContext,
    available_envelopes: _EnvelopeCollection,
    used_envelopes: Mapping[str, UncertaintyEnvelope],
    pe_refs: dict[str, UncertaintyEnvelopeRef],
) -> None:
    for param_name in list(pe_refs):
        if param_name not in used_envelopes:
            pe_refs.pop(param_name)
    pe_param_names = {name for mapping in context.pe_sensitivity.values() for name in mapping}
    for param_name, envelope in used_envelopes.items():
        if param_name in pe_param_names and param_name not in pe_refs:
            ref = available_envelopes.refs.get(param_name)
            if ref is not None:
                pe_refs[param_name] = ref
            else:
                pe_refs[param_name] = persist_uncertainty_envelope(
                    _ensure_ir_artifact_store(ctx.store), envelope
                )


def _resolve_simulation_envelopes(
    ctx: ExecutionContext,
    *,
    context: _ResolvedWelfareContext,
    available_envelopes: _EnvelopeCollection,
) -> tuple[dict[str, float], dict[str, UncertaintyEnvelope], dict[str, UncertaintyEnvelopeRef]]:
    nominal_params, used_envelopes, pe_refs = _resolve_pe_simulation_envelopes(
        context, available_envelopes
    )
    _add_ge_simulation_envelopes(
        context,
        available_envelopes,
        nominal_params=nominal_params,
        used_envelopes=used_envelopes,
    )
    _bind_pe_envelope_refs(
        ctx,
        context=context,
        available_envelopes=available_envelopes,
        used_envelopes=used_envelopes,
        pe_refs=pe_refs,
    )
    return nominal_params, used_envelopes, pe_refs


def _evaluate_welfare_response(
    params: Mapping[str, float],
    *,
    context: _ResolvedWelfareContext,
    used_envelopes: Mapping[str, UncertaintyEnvelope],
) -> np.ndarray:
    response = np.array(context.base_response, copy=True)
    for index, label in enumerate(context.labels):
        per_label = context.pe_sensitivity.get(label, {})
        if not per_label:
            continue
        delta = 0.0
        for param_name, coefficient in per_label.items():
            envelope = used_envelopes.get(param_name)
            if envelope is None:
                continue
            baseline = float(envelope.point_estimate)
            current = float(params.get(param_name, float(envelope.point_estimate)))
            denominator = max(abs(float(envelope.point_estimate)), 1.0)
            delta += float(coefficient) * ((current - baseline) / denominator)
        response[index] = float(context.base_response[index]) * (1.0 + delta)
    return response


def _apply_welfare_ge(
    params: Mapping[str, float],
    response: np.ndarray,
    *,
    context: _ResolvedWelfareContext,
    used_envelopes: Mapping[str, UncertaintyEnvelope],
    point_multiplier: np.ndarray | None,
    source_matrix: np.ndarray | None,
    condition_threshold: float,
    sample_domain_error_factory: Any,
) -> np.ndarray:
    ge_context = context.ge_context
    if point_multiplier is None or source_matrix is None or ge_context.source_kind == "none":
        return response
    if ge_context.source_kind == "multiplier":
        multiplier = np.array(point_multiplier, copy=True)
        for param_name, (row_index, column_index) in ge_context.ge_entry_map.items():
            envelope = used_envelopes.get(param_name)
            if envelope is not None:
                multiplier[row_index, column_index] = float(
                    params.get(param_name, float(envelope.point_estimate))
                )
        return multiplier @ response
    coefficients = np.array(source_matrix, copy=True)
    for param_name, (row_index, column_index) in ge_context.ge_entry_map.items():
        envelope = used_envelopes.get(param_name)
        if envelope is not None:
            coefficients[row_index, column_index] = float(
                params.get(param_name, float(envelope.point_estimate))
            )
    multiplier = _invert_sampled_ge_operator(
        coefficients,
        condition_threshold=condition_threshold,
        sample_domain_error_factory=sample_domain_error_factory,
    )
    return multiplier @ response


def _build_simulation_fn(
    ctx: ExecutionContext,
    *,
    context: _ResolvedWelfareContext,
    available_envelopes: _EnvelopeCollection,
    ge_condition_number_threshold: float = _DEFAULT_CONDITION_THRESHOLD,
    sampled_ge_domain_error_factory: Any,
) -> tuple[
    Any, dict[str, float], dict[str, UncertaintyEnvelope], dict[str, UncertaintyEnvelopeRef]
]:
    nominal_params, used_envelopes, pe_refs = _resolve_simulation_envelopes(
        ctx, context=context, available_envelopes=available_envelopes
    )
    weights = np.asarray(context.weights, dtype=np.float64)
    point_multiplier = (
        None
        if context.ge_context.point_multiplier is None
        else np.asarray(context.ge_context.point_multiplier, dtype=np.float64)
    )
    source_matrix = (
        None
        if context.ge_context.source_matrix is None
        else np.asarray(context.ge_context.source_matrix, dtype=np.float64)
    )

    def evaluate(**params: Any) -> dict[str, Any]:
        response = _evaluate_welfare_response(
            params, context=context, used_envelopes=used_envelopes
        )
        total = _apply_welfare_ge(
            params,
            response,
            context=context,
            used_envelopes=used_envelopes,
            point_multiplier=point_multiplier,
            source_matrix=source_matrix,
            condition_threshold=ge_condition_number_threshold,
            sample_domain_error_factory=sampled_ge_domain_error_factory,
        )
        welfare_pe = float(weights @ response)
        welfare_total = float(weights @ total)
        return {
            "welfare": welfare_total,
            "welfare_pe": welfare_pe,
            "welfare_ge": welfare_total - welfare_pe,
        }

    return evaluate, nominal_params, used_envelopes, pe_refs


def _propagate_without_envelopes(
    ctx: ExecutionContext,
    *,
    requested_method: str,
    config_ref: ArtifactRefModel,
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
) -> _PropagationOutcome:
    if calibration_source is not None and calibration_source.issue_codes:
        method_used = (
            WelfareMethod.DELTA
            if requested_method in {"delta", "delta_method"}
            else WelfareMethod.MONTE_CARLO
            if requested_method in {"monte_carlo", "mc"}
            else WelfareMethod.DETERMINISTIC
        )
        return _limited_covariance_outcome(
            ctx,
            config_ref=config_ref,
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
            input_envelopes={},
            input_envelope_refs=input_envelope_refs,
            calibration_source=calibration_source,
            requested_method=requested_method,
            method_used=method_used,
            limitation_code=calibration_source.issue_codes[0],
            dependence_note={"strategy": "calibration_report", "reason": "no_envelopes"},
        )
    report_ref = _persist_json_payload(
        ctx,
        payload={
            "schema_version": "1.0",
            "input_envelope_count": 0,
            "methods": [WelfareMethod.DETERMINISTIC.value],
            "requested_method": requested_method,
        },
        kind="foundry.welfare_propagation_report",
        schema_name="polisyos.foundry.WelfarePropagationReport",
        inputs=_calibration_lineage_inputs(
            calibration_source,
            additional_refs=_input_envelope_refs(input_envelope_refs),
        ),
    )
    return _PropagationOutcome(
        credible_interval=None,
        method_used=WelfareMethod.DETERMINISTIC,
        result_map={},
        method_config_ref=config_ref,
        report_ref=report_ref,
        sample_bundle_ref=None,
        diagnostics={"dependence_applied": False, "requested_method": requested_method},
    )


def _propagate_interval_outer_request(
    ctx: ExecutionContext,
    *,
    requested_method: str,
    config_ref: ArtifactRefModel,
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None,
) -> _PropagationOutcome:
    report_ref = _persist_json_payload(
        ctx,
        payload={
            "schema_version": "1.0",
            "input_envelope_count": len(input_envelopes),
            "methods": [WelfareMethod.INTERVAL_OUTER.value],
            "requested_method": requested_method,
            "reason": "credible_interval_skipped_by_requested_method",
        },
        kind="foundry.welfare_propagation_report",
        schema_name="polisyos.foundry.WelfarePropagationReport",
        inputs=_calibration_lineage_inputs(
            calibration_source,
            additional_refs=_input_envelope_refs(input_envelope_refs),
        ),
    )
    return _PropagationOutcome(
        credible_interval=None,
        method_used=WelfareMethod.INTERVAL_OUTER,
        result_map={},
        method_config_ref=config_ref,
        report_ref=report_ref,
        sample_bundle_ref=None,
        diagnostics={"dependence_applied": False, "requested_method": requested_method},
    )


def _resolve_monte_carlo_sampling(
    ctx: ExecutionContext,
    *,
    config: PropagationConfig,
    config_ref: ArtifactRefModel,
    context: _ResolvedWelfareContext,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None,
    requested_method: str,
) -> tuple[dict[str, Any], Any, Any, Any] | _PropagationOutcome:
    param_names = sorted(input_envelopes)
    calibration_resolution = (
        _resolve_calibration_covariance(
            context.dependence_context,
            calibration_source=calibration_source,
            param_names=param_names,
            input_envelopes=input_envelopes,
            jitter=config.delta_covariance_jitter,
        )
        if calibration_source is not None
        else None
    )
    if calibration_resolution is not None and calibration_resolution.limitation_code:
        return _limited_covariance_outcome(
            ctx,
            config_ref=config_ref,
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
            input_envelopes=input_envelopes,
            calibration_source=calibration_source,
            requested_method=requested_method,
            method_used=WelfareMethod.MONTE_CARLO,
            limitation_code=calibration_resolution.limitation_code,
            dependence_note=calibration_resolution.note,
            input_envelope_refs=input_envelope_refs,
        )
    if calibration_resolution is None:
        dependence_sampler = _build_dependence_sampler(
            context.dependence_context, param_names=param_names
        )
        coordinate_sampler = None
    else:
        assert calibration_resolution.matrix is not None
        dependence_sampler, coordinate_sampler, limitation = _calibration_dependence_sampler(
            calibration_resolution,
            calibration_source=calibration_source,
            param_names=param_names,
            input_envelopes=input_envelopes,
        )
        if limitation is not None:
            return _limited_covariance_outcome(
                ctx,
                config_ref=config_ref,
                simulation_fn=simulation_fn,
                nominal_params=nominal_params,
                input_envelopes=input_envelopes,
                calibration_source=calibration_source,
                requested_method=requested_method,
                method_used=WelfareMethod.MONTE_CARLO,
                limitation_code=limitation,
                dependence_note=dependence_sampler,
                input_envelope_refs=input_envelope_refs,
            )
    empirical_sampler, empirical_limitation = _resolve_empirical_row_sampler(
        param_names,
        input_envelopes,
        calibration_coordinates_active=coordinate_sampler is not None,
    )
    if empirical_limitation is not None:
        return _limited_covariance_outcome(
            ctx,
            config_ref=config_ref,
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
            input_envelopes=input_envelopes,
            input_envelope_refs=input_envelope_refs,
            calibration_source=calibration_source,
            requested_method=requested_method,
            method_used=WelfareMethod.MONTE_CARLO,
            limitation_code=empirical_limitation,
            dependence_note={
                **dependence_sampler,
                "empirical_joint_identity_status": "not_established",
            },
        )
    if empirical_sampler is not None:
        dependence_sampler = empirical_sampler.dependence_note
    return dependence_sampler, coordinate_sampler, empirical_sampler, calibration_resolution


def _propagate_monte_carlo(
    ctx: ExecutionContext,
    *,
    config: PropagationConfig,
    config_ref: ArtifactRefModel,
    requested_method: str,
    context: _ResolvedWelfareContext,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None,
    sample_domain_error_type: type[BaseException],
    sample_param_draw: Any,
) -> _PropagationOutcome:
    sampling = _resolve_monte_carlo_sampling(
        ctx,
        config=config,
        config_ref=config_ref,
        context=context,
        simulation_fn=simulation_fn,
        nominal_params=nominal_params,
        input_envelopes=input_envelopes,
        input_envelope_refs=input_envelope_refs,
        calibration_source=calibration_source,
        requested_method=requested_method,
    )
    if isinstance(sampling, _PropagationOutcome):
        return sampling
    dependence_sampler, coordinate_sampler, empirical_sampler, calibration_resolution = sampling
    draws = _run_welfare_monte_carlo_draws(
        config,
        input_envelopes=input_envelopes,
        dependence_sampler=dependence_sampler,
        coordinate_sampler=coordinate_sampler,
        empirical_sampler=empirical_sampler,
        simulation_fn=simulation_fn,
        sample_domain_error_type=sample_domain_error_type,
        sample_param_draw=sample_param_draw,
        calibration_resolution=calibration_resolution,
    )
    return _summarize_welfare_monte_carlo(
        ctx,
        config=config,
        requested_method=requested_method,
        context=context,
        input_envelopes=input_envelopes,
        input_envelope_refs=input_envelope_refs,
        calibration_source=calibration_source,
        draws=draws,
        config_ref=config_ref,
    )


def _summarize_welfare_monte_carlo(
    ctx: ExecutionContext,
    *,
    config: PropagationConfig,
    requested_method: str,
    context: _ResolvedWelfareContext,
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None,
    draws: _MonteCarloDrawSet,
    config_ref: ArtifactRefModel,
) -> _PropagationOutcome:
    provenance = _draw_outcome_provenance(draws)
    complete_draws = _welfare_draw_set_is_complete(draws)
    incomplete_draw_count = int(provenance["failed_draw_count"]) + int(
        provenance["unattempted_draw_count"]
    )
    if not incomplete_draw_count and len(draws.welfare) < int(config.mc_min_valid_samples):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo propagation did not reach the minimum valid sample budget",
            details={
                "valid_samples": len(draws.welfare),
                "required": int(config.mc_min_valid_samples),
            },
        )
    result_map, interval, sample_bundle_ref, summary, complete_draws = _persist_welfare_mc_samples(
        ctx,
        config=config,
        draws=draws,
        input_envelopes=input_envelopes,
        input_envelope_refs=input_envelope_refs,
        calibration_source=calibration_source,
        context=context,
        requested_method=requested_method,
        provenance=provenance,
    )
    report_ref = _persist_welfare_mc_report(
        ctx,
        draws=draws,
        input_envelopes=input_envelopes,
        input_envelope_refs=input_envelope_refs,
        calibration_source=calibration_source,
        context=context,
        requested_method=requested_method,
        provenance=provenance,
        summary=summary,
        complete_draws=complete_draws,
        sample_bundle_ref=sample_bundle_ref,
    )
    return _PropagationOutcome(
        credible_interval=interval,
        method_used=WelfareMethod.MONTE_CARLO,
        result_map=result_map,
        method_config_ref=config_ref,
        report_ref=report_ref,
        sample_bundle_ref=sample_bundle_ref,
        diagnostics={
            "dependence_applied": bool(draws.dependence_sampler.get("applied")),
            "dependence_sampling": draws.dependence_sampler,
            "requested_method": requested_method,
            "draw_outcome_provenance": provenance,
            **(
                {"draw_summary": summary}
                if summary is not None and complete_draws
                else {"conditional_draw_summary": summary}
                if summary is not None
                else {}
            ),
            "limitation_codes": ["welfare_mc_incomplete_draws"] if not complete_draws else [],
        },
    )


def _propagate_credible_interval(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    welfare_params: Mapping[str, Any],
    context: _ResolvedWelfareContext,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None = None,
    sample_domain_error_type: type[BaseException],
    sample_param_draw: Any,
) -> _PropagationOutcome:
    config = _load_propagation_config(state)
    requested_method = _resolve_requested_welfare_method(config, welfare_params)
    config_ref = _persist_json_payload(
        ctx,
        payload=config.model_dump(mode="json"),
        kind="foundry.welfare_method_config",
        schema_name="polisyos.foundry.WelfareMethodConfig",
    )
    if not input_envelopes:
        return _propagate_without_envelopes(
            ctx,
            requested_method=requested_method,
            config_ref=config_ref,
            input_envelope_refs=input_envelope_refs,
            calibration_source=calibration_source,
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
        )
    if requested_method in {"interval_outer", "robust_set", "none", "deterministic"}:
        return _propagate_interval_outer_request(
            ctx,
            requested_method=requested_method,
            config_ref=config_ref,
            input_envelopes=input_envelopes,
            input_envelope_refs=input_envelope_refs,
            calibration_source=calibration_source,
        )
    if requested_method in {"delta", "delta_method"}:
        return _propagate_delta_interval(
            ctx,
            config=config,
            config_ref=config_ref,
            context=context,
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
            input_envelopes=input_envelopes,
            input_envelope_refs=input_envelope_refs,
            calibration_source=calibration_source,
            requested_method=requested_method,
        )
    return _propagate_monte_carlo(
        ctx,
        config=config,
        config_ref=config_ref,
        requested_method=requested_method,
        context=context,
        simulation_fn=simulation_fn,
        nominal_params=nominal_params,
        input_envelopes=input_envelopes,
        input_envelope_refs=input_envelope_refs,
        calibration_source=calibration_source,
        sample_domain_error_type=sample_domain_error_type,
        sample_param_draw=sample_param_draw,
    )


def _resolve_requested_welfare_method(
    config: PropagationConfig,
    welfare_params: Mapping[str, Any],
) -> str:
    if "credible_method" in welfare_params:
        source, requested = "credible_method", welfare_params["credible_method"]
    elif "method" in welfare_params:
        source, requested = "method", welfare_params["method"]
    else:
        source, requested = "preferred_method", config.preferred_method
    if not isinstance(requested, str) or not requested.strip():
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            "Welfare propagation method must be a non-empty string when provided",
            details={"field": source, "received_type": type(requested).__name__},
        )
    text = requested.strip().lower()
    aliases = {
        "mc": "monte_carlo",
        "delta_method": "delta",
        "robust": "robust_set",
        "interval": "interval_outer",
    }
    normalized = aliases.get(text, text)
    supported = {
        "auto",
        "monte_carlo",
        "delta",
        "interval_outer",
        "robust_set",
        "none",
        "deterministic",
    }
    if normalized not in supported:
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            "Welfare propagation method is not supported by this consumer",
            details={"field": source, "requested_method": text},
        )
    return normalized


def _propagate_delta_interval(
    ctx: ExecutionContext,
    *,
    config: PropagationConfig,
    config_ref: ArtifactRefModel,
    context: _ResolvedWelfareContext,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef] | None = None,
    calibration_source: _CalibrationCovarianceSource | None,
    requested_method: str,
) -> _PropagationOutcome:
    param_names = sorted(input_envelopes)
    gradient, base_value = _finite_difference_gradient(
        simulation_fn=simulation_fn,
        nominal_params=nominal_params,
        input_envelopes=input_envelopes,
    )
    calibration_resolution = (
        _resolve_calibration_covariance(
            context.dependence_context,
            calibration_source=calibration_source,
            param_names=param_names,
            input_envelopes=input_envelopes,
            jitter=config.delta_covariance_jitter,
        )
        if calibration_source is not None
        else None
    )
    if calibration_resolution is not None and calibration_resolution.limitation_code:
        return _limited_covariance_outcome(
            ctx,
            config_ref=config_ref,
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
            input_envelopes=input_envelopes,
            calibration_source=calibration_source,
            requested_method=requested_method,
            method_used=WelfareMethod.DELTA,
            limitation_code=calibration_resolution.limitation_code,
            dependence_note=calibration_resolution.note,
            input_envelope_refs=input_envelope_refs,
        )
    if calibration_resolution is None:
        covariance, dependence_applied, dependence_note = _build_parameter_covariance(
            context.dependence_context,
            param_names=param_names,
            input_envelopes=input_envelopes,
        )
    else:
        assert calibration_resolution.matrix is not None
        covariance = calibration_resolution.matrix
        dependence_applied = calibration_resolution.dependence_applied
        dependence_note = calibration_resolution.note
    gradient_vector = np.asarray([gradient[name] for name in param_names], dtype=np.float64)
    variance = float(gradient_vector @ covariance @ gradient_vector) if param_names else 0.0
    variance = max(variance, 0.0)
    std = math.sqrt(variance)
    z_value = NormalDist().inv_cdf((1.0 + float(config.confidence_level)) / 2.0)
    credible_interval = (
        float(base_value - z_value * std),
        float(base_value + z_value * std),
    )
    report_ref = _persist_json_payload(
        ctx,
        payload={
            "schema_version": "2.0" if calibration_source is not None else "1.0",
            "input_envelope_count": len(input_envelopes),
            "methods": [WelfareMethod.DELTA.value],
            "requested_method": requested_method,
            "gradient": gradient,
            "covariance": covariance.tolist(),
            "delta_std": float(std),
            "dependence_sampling": dependence_note,
            "calibration_report_ref": (
                str(calibration_source.report_ref.artifact_id)
                if calibration_source is not None
                else None
            ),
            "covariance_order": list(param_names),
            **_calibration_projection_report_metadata(
                calibration_source,
                covariance_note=dependence_note,
                uncertainty_status="candidate",
            ),
        },
        kind="foundry.welfare_propagation_report",
        schema_name="polisyos.foundry.WelfarePropagationReport",
        inputs=_calibration_lineage_inputs(
            calibration_source,
            dependence_ref=context.dependence_structure_ref,
            additional_refs=_input_envelope_refs(input_envelope_refs or {}),
        ),
    )
    return _PropagationOutcome(
        credible_interval=credible_interval,
        method_used=WelfareMethod.DELTA,
        result_map={
            "welfare": {
                "point_estimate": float(base_value),
                "gradient": gradient,
                "delta_std": float(std),
            }
        },
        method_config_ref=config_ref,
        report_ref=report_ref,
        sample_bundle_ref=None,
        diagnostics={
            "dependence_applied": dependence_applied,
            "dependence_sampling": dependence_note,
            "requested_method": requested_method,
            "delta_gradient": gradient,
            "delta_std": float(std),
        },
    )
