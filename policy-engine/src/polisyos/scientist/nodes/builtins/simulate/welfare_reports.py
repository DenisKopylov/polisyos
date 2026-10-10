"""Internal welfare reports implementation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope
from polisyos.ir.analytics.welfare import (
    ChannelDecompositionTargetKind,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareSampleBundle,
    WelfareStatus,
    build_channel_decomposition_ref,
    persist_welfare_sample_bundle,
)
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    DependenceStructureRef,
    GEUncertaintyBundleRef,
    UncertaintyEnvelopeRef,
    WelfareSampleBundleRef,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

from .welfare_covariance import _calibration_lineage_inputs, _calibration_projection_report_metadata
from .welfare_draws import (
    _draw_outcome_provenance,
    _finite_difference_gradient,
    _MonteCarloDrawSet,
    _welfare_draw_set_is_complete,
)
from .welfare_ge import (
    _coerce_bool,
    _coerce_numeric_sequence,
)
from .welfare_types import (
    _ERROR_CHANNEL_DECOMPOSITION_BUILD_FAILED,
    _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
    _ERROR_INTERVAL_SEMANTICS_INVALID,
    _ERROR_MONTE_CARLO_NOT_CONVERGED,
    _WELFARE_VALIDATION_ERRORS,
    _CalibrationCovarianceSource,
    _dot_interval,
    _extract_std,
    _fail_error,
    _input_envelope_refs,
    _input_ref,
    _matvec_interval,
    _mul_interval,
    _persist_json_payload,
    _ResolvedWelfareContext,
)

logger = get_logger(__name__)


def _load_propagation_config(state: ExperimentState) -> PropagationConfig:
    if "propagation_config" in state.params:
        return _validated_propagation_config(
            state.params["propagation_config"], field_name="propagation_config"
        )
    overrides: dict[str, Any] = {}
    for field_name in PropagationConfig.model_fields:
        prefixed = f"propagation_{field_name}"
        if prefixed in state.params:
            overrides[field_name] = state.params[prefixed]
    if overrides:
        return _validated_propagation_config(overrides, field_name="propagation_* overrides")
    return PropagationConfig()


def _validated_propagation_config(raw: Any, *, field_name: str) -> PropagationConfig:
    """Validate a present propagation config without replacing it with defaults."""
    if not isinstance(raw, Mapping):
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            "Welfare propagation configuration must be a mapping when provided",
            details={"field": field_name, "received_type": type(raw).__name__},
        )
    try:
        return PropagationConfig.model_validate(raw)
    except _WELFARE_VALIDATION_ERRORS as exc:
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            "Welfare propagation configuration is invalid",
            details={"field": field_name, "error_type": type(exc).__name__},
        ) from exc


def _build_robust_interval(
    *,
    context: _ResolvedWelfareContext,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[tuple[float, float], dict[str, Any]]:
    response_lower = np.array(context.base_response, copy=True)
    response_upper = np.array(context.base_response, copy=True)
    for idx, label in enumerate(context.labels):
        per_label = context.pe_sensitivity.get(label, {})
        if not per_label:
            continue
        delta_lower = 0.0
        delta_upper = 0.0
        for param_name, coef in per_label.items():
            env = input_envelopes.get(param_name)
            if env is None:
                continue
            denom = max(abs(float(env.point_estimate)), 1.0)
            lo = (float(env.confidence_interval[0]) - float(env.point_estimate)) / denom
            hi = (float(env.confidence_interval[1]) - float(env.point_estimate)) / denom
            contrib = _mul_interval(float(coef), float(coef), lo, hi)
            delta_lower += contrib[0]
            delta_upper += contrib[1]
        scaled = _mul_interval(
            float(context.base_response[idx]),
            float(context.base_response[idx]),
            1.0 + delta_lower,
            1.0 + delta_upper,
        )
        response_lower[idx], response_upper[idx] = scaled

    if context.ge_context.point_multiplier is None:
        matrix_lower = np.eye(len(context.labels), dtype=np.float64)
        matrix_upper = np.eye(len(context.labels), dtype=np.float64)
    else:
        matrix_lower = (
            np.array(context.ge_context.lower_multiplier, copy=True)
            if context.ge_context.lower_multiplier is not None
            else np.array(context.ge_context.point_multiplier, copy=True)
        )
        matrix_upper = (
            np.array(context.ge_context.upper_multiplier, copy=True)
            if context.ge_context.upper_multiplier is not None
            else np.array(context.ge_context.point_multiplier, copy=True)
        )
        if context.ge_context.source_kind == "multiplier":
            for param_name, (row_idx, col_idx) in context.ge_context.ge_entry_map.items():
                env = input_envelopes.get(param_name)
                if env is None:
                    continue
                matrix_lower[row_idx, col_idx] = float(env.confidence_interval[0])
                matrix_upper[row_idx, col_idx] = float(env.confidence_interval[1])

    total_lower, total_upper = _matvec_interval(
        matrix_lower,
        matrix_upper,
        response_lower,
        response_upper,
    )
    robust_interval = _dot_interval(context.weights, total_lower, total_upper)
    return robust_interval, {
        "response_interval": [response_lower.tolist(), response_upper.tolist()],
        "matrix_bounded": bool(
            context.ge_context.lower_multiplier is not None
            or context.ge_context.upper_multiplier is not None
        ),
    }


def _resolve_bundle_status(
    *,
    context: _ResolvedWelfareContext,
    used_input_envelopes: Mapping[str, UncertaintyEnvelope],
    dependence_applied: bool,
) -> tuple[list[str], WelfareStatus]:
    warnings = list(context.warnings)
    status = WelfareStatus.OK

    if context.ge_context.point_multiplier is None:
        warnings.append("ge_operator_missing_pe_only")
        status = WelfareStatus.PARTIAL
    elif context.ge_context.ge_uncertainty_ref is None:
        warnings.append("ge_multiplier_treated_as_fixed")
        status = WelfareStatus.DEGRADED

    if (
        len(used_input_envelopes) > 1
        and context.dependence_structure_ref is None
        and not dependence_applied
    ):
        warnings.append("dependence_assumed_independent")
        if status is WelfareStatus.OK:
            status = WelfareStatus.DEGRADED
    elif (
        len(used_input_envelopes) > 1
        and context.dependence_structure_ref is not None
        and not dependence_applied
    ):
        warnings.append("dependence_structure_present_but_not_applied")
        if status is WelfareStatus.OK:
            status = WelfareStatus.DEGRADED

    if any(not envelope.gate_eligible for envelope in used_input_envelopes.values()):
        warnings.append("input_uncertainty_not_gate_eligible")
        if status is WelfareStatus.OK:
            status = WelfareStatus.DEGRADED

    return warnings, status


def _resolve_bundle_method(
    propagated_method: WelfareMethod,
    *,
    credible_interval: tuple[float, float] | None,
    robust_interval: tuple[float, float] | None,
) -> WelfareMethod:
    if credible_interval is not None and robust_interval is not None:
        return (
            WelfareMethod.MIXED_NESTED
            if propagated_method is not WelfareMethod.DETERMINISTIC
            else WelfareMethod.INTERVAL_OUTER
        )
    if credible_interval is not None:
        return propagated_method
    if robust_interval is not None:
        return WelfareMethod.INTERVAL_OUTER
    return WelfareMethod.DETERMINISTIC


def _resolve_interval_semantics(
    *,
    credible_interval: tuple[float, float] | None,
    robust_interval: tuple[float, float] | None,
) -> WelfareIntervalSemantics:
    if credible_interval is not None and robust_interval is not None:
        return WelfareIntervalSemantics.MIXED_NESTED
    if credible_interval is not None:
        return WelfareIntervalSemantics.CREDIBLE
    if robust_interval is not None:
        return WelfareIntervalSemantics.ROBUST_OUTER
    return WelfareIntervalSemantics.NONE


def _resolve_subgroup_welfare(
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
    total_vector: np.ndarray,
) -> dict[str, float]:
    raw = welfare_params.get("subgroup_weights")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for name, weights_value in raw.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(weights_value, dict):
            if any(label not in weights_value for label in labels):
                continue
            weights = np.asarray(
                [float(weights_value[label]) for label in labels], dtype=np.float64
            )
        elif isinstance(weights_value, (list, tuple)) and len(weights_value) == len(labels):
            weights = np.asarray([float(value) for value in weights_value], dtype=np.float64)
        else:
            continue
        out[name] = float(weights @ total_vector)
    return out


def _point_total_vector(
    context: _ResolvedWelfareContext,
    *,
    nominal_params: Mapping[str, float],
) -> np.ndarray:
    response = np.array(context.base_response, copy=True)
    for idx, label in enumerate(context.labels):
        per_label = context.pe_sensitivity.get(label, {})
        if not per_label:
            continue
        delta = 0.0
        for param_name, coef in per_label.items():
            if param_name not in nominal_params:
                continue
            baseline = float(nominal_params[param_name])
            denom = max(abs(baseline), 1.0)
            delta += float(coef) * ((float(nominal_params[param_name]) - baseline) / denom)
        response[idx] = float(context.base_response[idx]) * (1.0 + delta)
    if context.ge_context.point_multiplier is None:
        return response
    return np.asarray(context.ge_context.point_multiplier @ response, dtype=np.float64)


def _persist_sensitivity_diagnostics(
    ctx: ExecutionContext,
    *,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    robust_interval: tuple[float, float],
) -> ArtifactRefModel | None:
    if not input_envelopes:
        return None
    gradient, _ = _finite_difference_gradient(
        simulation_fn=simulation_fn,
        nominal_params=nominal_params,
        input_envelopes=input_envelopes,
    )
    rows: list[dict[str, Any]] = []
    for name, env in input_envelopes.items():
        half_width = max(
            (float(env.confidence_interval[1]) - float(env.confidence_interval[0])) / 2.0,
            0.0,
        )
        std = max(_extract_std(env), 0.0)
        grad = float(gradient.get(name, 0.0))
        rows.append(
            {
                "parameter": name,
                "local_gradient": grad,
                "credible_scale": abs(grad) * std,
                "robust_scale": abs(grad) * half_width,
                "interval_half_width": half_width,
                "distribution_family": env.distribution_family.value,
            }
        )
    rows.sort(key=lambda item: (item["robust_scale"], item["credible_scale"]), reverse=True)
    return _persist_json_payload(
        ctx,
        payload={
            "schema_version": "1.0",
            "sensitivity_rows": rows,
            "robust_interval": [float(robust_interval[0]), float(robust_interval[1])],
        },
        kind="foundry.welfare_sensitivity_diagnostics",
        schema_name="polisyos.foundry.WelfareSensitivityDiagnostics",
    )


def _bundle_inputs(
    *,
    sim_result_ref: ArtifactRef,
    metric_ref: ArtifactRef,
    pe_uncertainty_refs: Mapping[str, UncertaintyEnvelopeRef],
    ge_uncertainty_ref: GEUncertaintyBundleRef | None,
    dependence_structure_ref: DependenceStructureRef | None,
    calibration_report_ref: ArtifactRefModel | None,
    channel_decomposition_ref: ArtifactRefModel | None,
    method_config_ref: ArtifactRefModel | None,
    report_ref: ArtifactRefModel | None,
    sample_bundle_ref: WelfareSampleBundleRef | None,
    sensitivity_diagnostics_ref: ArtifactRefModel | None,
) -> list[InputRef]:
    inputs = [
        _input_ref(sim_result_ref, role="simulation_result"),
        _input_ref(metric_ref, role="metrics"),
    ]
    for name, ref in pe_uncertainty_refs.items():
        inputs.append(_input_ref(ref, role=f"pe_uncertainty.{name}"))
    if ge_uncertainty_ref is not None:
        inputs.append(_input_ref(ge_uncertainty_ref, role="ge_uncertainty"))
    if dependence_structure_ref is not None:
        inputs.append(_input_ref(dependence_structure_ref, role="dependence_structure"))
    if calibration_report_ref is not None:
        inputs.append(_input_ref(calibration_report_ref, role="calibration_report"))
    if channel_decomposition_ref is not None:
        inputs.append(_input_ref(channel_decomposition_ref, role="channel_decomposition"))
    if method_config_ref is not None:
        inputs.append(_input_ref(method_config_ref, role="method_config"))
    if report_ref is not None:
        inputs.append(_input_ref(report_ref, role="propagation_report"))
    if sample_bundle_ref is not None:
        inputs.append(_input_ref(sample_bundle_ref, role="sample_bundle"))
    if sensitivity_diagnostics_ref is not None:
        inputs.append(_input_ref(sensitivity_diagnostics_ref, role="sensitivity_diagnostics"))
    return inputs


def _maybe_build_channel_decomposition_ref(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    total_vector: np.ndarray,
) -> ArtifactRefModel | None:
    config = _resolve_channel_decomposition_config(welfare_params)
    if config is None:
        return None

    baseline_microdata_ref = _resolve_channel_artifact_ref(
        ctx,
        config,
        payload_key="baseline_microdata",
        ref_key="baseline_microdata_ref",
        kind="ir.baseline_microdata",
        schema_name="ir.baseline_microdata",
    )
    policy_basis_ref = _resolve_channel_artifact_ref(
        ctx,
        config,
        payload_key="policy_basis",
        ref_key="policy_basis_ref",
        kind="ir.policy_basis",
        schema_name="ir.policy_basis",
    )
    mechanical_inputs_ref = _resolve_channel_artifact_ref(
        ctx,
        config,
        payload_key="mechanical_inputs",
        ref_key="mechanical_inputs_ref",
        kind="ir.mechanical_inputs",
        schema_name="ir.mechanical_inputs",
    )
    if baseline_microdata_ref is None or policy_basis_ref is None or mechanical_inputs_ref is None:
        missing: list[str] = []
        if baseline_microdata_ref is None:
            missing.append("baseline_microdata_ref")
        if policy_basis_ref is None:
            missing.append("policy_basis_ref")
        if mechanical_inputs_ref is None:
            missing.append("mechanical_inputs_ref")
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            "welfare channel decomposition requires baseline, policy basis, and mechanical inputs",
            details={"missing_fields": missing},
        )

    explicit_total_vector = _coerce_numeric_sequence(
        config.get("total_vector"),
        field_name="welfare_channel_decomposition.total_vector",
    )
    try:
        return build_channel_decomposition_ref(
            _ensure_ir_artifact_store(ctx.store),
            target_kind=str(
                config.get(
                    "target_kind",
                    ChannelDecompositionTargetKind.SOCIAL_WELFARE.value,
                )
            ),
            baseline_microdata_ref=baseline_microdata_ref,
            policy_basis_ref=policy_basis_ref,
            mechanical_inputs_ref=mechanical_inputs_ref,
            behavior_model_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="behavior_model",
                ref_key="behavior_model_ref",
                kind="ir.behavior_model",
                schema_name="ir.behavior_model",
            ),
            fiscal_state_model_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="fiscal_state_model",
                ref_key="fiscal_state_model_ref",
                kind="ir.fiscal_state_model",
                schema_name="ir.fiscal_state_model",
            ),
            instrument_set_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="instrument_set",
                ref_key="instrument_set_ref",
                kind="ir.instrument_set",
                schema_name="ir.instrument_set",
            ),
            proof_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="proof",
                ref_key="proof_ref",
                kind="ir.channel_decomposition_proof",
                schema_name="ir.channel_decomposition_proof",
            ),
            uncertainty_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="uncertainty",
                ref_key="uncertainty_ref",
                kind="ir.channel_decomposition_uncertainty",
                schema_name="ir.channel_decomposition_uncertainty",
            ),
            total_vector=explicit_total_vector or total_vector.tolist(),
            block_on_failure=_coerce_bool(config.get("block_on_failure", True)),
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_BUILD_FAILED,
            "Unable to build welfare channel decomposition artifact",
            details={"error": str(exc)},
        ) from exc


def _resolve_channel_decomposition_config(
    welfare_params: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw = welfare_params.get("channel_decomposition")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            "welfare_channel_decomposition must be a JSON object",
        )
    return dict(raw)


def _resolve_channel_artifact_ref(
    ctx: ExecutionContext,
    config: Mapping[str, Any],
    *,
    payload_key: str,
    ref_key: str,
    kind: str,
    schema_name: str,
) -> ArtifactRefModel | None:
    if payload_key in config and ref_key in config:
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"Specify only one of {payload_key} or {ref_key}",
        )
    raw_value = config.get(ref_key, config.get(payload_key))
    if raw_value is None:
        return None
    if isinstance(raw_value, ArtifactRefModel):
        return raw_value
    if isinstance(raw_value, Mapping):
        if {"artifact_id", "kind", "media_type"} <= set(raw_value):
            try:
                return ArtifactRefModel.model_validate(raw_value)
            except ValidationError as exc:
                raise _fail_error(
                    _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
                    f"Invalid artifact ref for {ref_key}",
                    details={"error": str(exc)},
                ) from exc
        return _persist_json_payload(
            ctx,
            payload=raw_value,
            kind=kind,
            schema_name=schema_name,
        )
    raise _fail_error(
        _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
        f"{ref_key} must be an artifact ref or JSON object",
        details={"received_type": type(raw_value).__name__},
    )


def _persist_welfare_mc_samples(
    ctx: ExecutionContext,
    *,
    config: PropagationConfig,
    draws: _MonteCarloDrawSet,
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None,
    context: _ResolvedWelfareContext,
    requested_method: str,
    provenance: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    tuple[float, float] | None,
    WelfareSampleBundleRef | None,
    dict[str, Any] | None,
    bool,
]:
    expected_provenance = _draw_outcome_provenance(draws)
    if dict(provenance) != expected_provenance:
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo sample provenance does not match its draw record",
        )
    complete = _welfare_draw_set_is_complete(draws)
    has_samples = bool(draws.welfare)
    values = np.asarray(draws.welfare, dtype=np.float64)
    result_map: dict[str, Any] = {}
    interval: tuple[float, float] | None = None
    summary: dict[str, Any] | None = None
    sample_ref: WelfareSampleBundleRef | None = None
    if not has_samples:
        return result_map, interval, sample_ref, summary, complete
    summary = {
        "welfare_mean": float(np.mean(values)),
        "welfare_std": float(np.std(values)),
        "welfare_pe_mean": float(np.mean(np.asarray(draws.welfare_pe, dtype=np.float64))),
        "welfare_ge_mean": float(np.mean(np.asarray(draws.welfare_ge, dtype=np.float64))),
    }
    if complete:
        result_map = {
            "welfare": {"point_estimate": summary["welfare_mean"], "draw_count": len(draws.welfare)}
        }
        alpha = max((1.0 - float(config.confidence_level)) / 2.0, 0.0)
        interval = (float(np.quantile(values, alpha)), float(np.quantile(values, 1.0 - alpha)))
    else:
        result_map = {
            "welfare": {
                "conditional_mean": summary["welfare_mean"],
                "successful_draw_count": len(draws.welfare),
                "summary_semantics": provenance["summary_semantics"],
            }
        }
    resolution = draws.calibration_resolution
    sample_ref = persist_welfare_sample_bundle(
        _ensure_ir_artifact_store(ctx.store),
        WelfareSampleBundle(
            welfare_draws=tuple(float(value) for value in draws.welfare),
            welfare_pe_draws=tuple(float(value) for value in draws.welfare_pe),
            welfare_ge_draws=tuple(float(value) for value in draws.welfare_ge),
            metadata={
                "requested_method": requested_method,
                "dependence_strategy": draws.dependence_sampler["strategy"],
                "covered_params": draws.dependence_sampler["covered_params"],
                "draw_outcome_provenance": provenance,
                "calibration_report_ref": (
                    str(calibration_source.report_ref.artifact_id)
                    if calibration_source is not None
                    else None
                ),
                "calibration_covariance_order": (
                    sorted(input_envelopes) if calibration_source is not None else None
                ),
                **(
                    {"calibration_covariance_matrix": resolution.matrix.tolist()}
                    if resolution is not None and resolution.matrix is not None
                    else {}
                ),
                **_calibration_projection_report_metadata(
                    calibration_source,
                    covariance_note=resolution.note if resolution is not None else {},
                    uncertainty_status="candidate",
                ),
            },
        ),
        inputs=_calibration_lineage_inputs(
            calibration_source,
            dependence_ref=context.dependence_structure_ref,
            additional_refs=_input_envelope_refs(input_envelope_refs),
        ),
    )
    return result_map, interval, sample_ref, summary, complete


def _persist_welfare_mc_report(
    ctx: ExecutionContext,
    *,
    draws: _MonteCarloDrawSet,
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef],
    calibration_source: _CalibrationCovarianceSource | None,
    context: _ResolvedWelfareContext,
    requested_method: str,
    provenance: dict[str, Any],
    summary: dict[str, Any] | None,
    complete_draws: bool,
    sample_bundle_ref: WelfareSampleBundleRef | None,
) -> ArtifactRefModel:
    provenance, summary, complete_draws = _reconcile_mc_report_claims(
        draws=draws,
        provenance=provenance,
        summary=summary,
        complete_draws=complete_draws,
    )
    calibration_resolution = draws.calibration_resolution
    welfare_array = np.asarray(draws.welfare, dtype=np.float64)
    return _persist_json_payload(
        ctx,
        payload={
            "schema_version": "2.2" if calibration_source is not None else "1.2",
            "input_envelope_count": len(input_envelopes),
            "methods": ["monte_carlo"],
            "requested_method": requested_method,
            "valid_draw_count": int(welfare_array.shape[0]),
            "draw_outcome_provenance": provenance,
            **(
                {"draw_summary": summary}
                if summary is not None and complete_draws
                else {"conditional_draw_summary": summary}
                if summary is not None
                else {}
            ),
            "dependence_sampling": draws.dependence_sampler,
            "calibration_report_ref": (
                str(calibration_source.report_ref.artifact_id)
                if calibration_source is not None
                else None
            ),
            **(
                {
                    "covariance_order": sorted(input_envelopes),
                    "covariance_matrix": calibration_resolution.matrix.tolist(),
                }
                if calibration_resolution is not None and calibration_resolution.matrix is not None
                else {}
            ),
            **_calibration_projection_report_metadata(
                calibration_source,
                covariance_note=(
                    calibration_resolution.note if calibration_resolution is not None else {}
                ),
                uncertainty_status="candidate",
            ),
        },
        kind="foundry.welfare_propagation_report",
        schema_name="polisyos.foundry.WelfarePropagationReport",
        inputs=_calibration_lineage_inputs(
            calibration_source,
            dependence_ref=context.dependence_structure_ref,
            additional_refs=(
                (
                    *_input_envelope_refs(input_envelope_refs),
                    _input_ref(sample_bundle_ref, role="sample_bundle"),
                )
                if sample_bundle_ref is not None
                else _input_envelope_refs(input_envelope_refs)
            ),
        ),
    )


def _reconcile_mc_report_claims(
    *,
    draws: _MonteCarloDrawSet,
    provenance: Mapping[str, Any],
    summary: Mapping[str, Any] | None,
    complete_draws: bool,
) -> tuple[dict[str, Any], dict[str, float] | None, bool]:
    """Require report claims to match the actual reconciled Monte Carlo draw set."""
    expected_provenance = _draw_outcome_provenance(draws)
    expected_complete = _welfare_draw_set_is_complete(draws)
    expected_summary = None
    if draws.welfare:
        expected_summary = {
            "welfare_mean": float(np.mean(np.asarray(draws.welfare, dtype=np.float64))),
            "welfare_std": float(np.std(np.asarray(draws.welfare, dtype=np.float64))),
            "welfare_pe_mean": float(np.mean(np.asarray(draws.welfare_pe, dtype=np.float64))),
            "welfare_ge_mean": float(np.mean(np.asarray(draws.welfare_ge, dtype=np.float64))),
        }
    if (
        dict(provenance) != expected_provenance
        or (dict(summary) if summary is not None else None) != expected_summary
        or complete_draws is not expected_complete
    ):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo report claims do not reconcile with its draw record",
            details={
                "expected_complete_draws": expected_complete,
                "claimed_complete_draws": complete_draws,
                "expected_successful_draw_count": expected_provenance["successful_draw_count"],
            },
        )
    return expected_provenance, expected_summary, expected_complete
