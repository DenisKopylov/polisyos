"""Internal welfare context implementation helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal
from numbers import Real
from typing import Any, Literal

import numpy as np

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import DataSnapshot
from polisyos.core.contracts.foundry import (
    EquilibriumMultiplicityReport,
    FeedbackSolveResult,
    Metrics,
    SimulationResult,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.ir.analytics import EquilibriumMultiplicityWelfareAnnotation
from polisyos.ir.analytics.dependence_structure import load_dependence_structure
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, load_uncertainty_envelope
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    DependenceStructureRef,
    UncertaintyEnvelopeRef,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import ensure_social_weight_manifest_artifact

from .welfare_ge import (
    _coerce_artifact_ref,
    _coerce_dependence_matrix,
    _coerce_str_list,
    _correlation_from_covariance,
    _resolve_ge_context,
    _stabilize_correlation_matrix,
)
from .welfare_types import (
    _ERROR_DEPENDENCE_SPEC_INVALID,
    _ERROR_WELFARE_DIMENSION_MISMATCH,
    _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
    _ERROR_WELFARE_OUTPUT_NONFINITE,
    _WELFARE_LOAD_ERRORS,
    _WELFARE_VALIDATION_ERRORS,
    _CalibrationCovarianceSource,
    _EnvelopeCollection,
    _EnvelopeOrigin,
    _fail_error,
    _load_artifact_json,
    _persist_json_payload,
    _ResolvedDependenceContext,
    _ResolvedWelfareContext,
)

logger = get_logger(__name__)


def _envelope_origin(
    *,
    source_role: str,
    ref: ArtifactRefModel | None,
) -> _EnvelopeOrigin:
    artifact_key = None
    if ref is not None:
        artifact_key = (ref.kind, str(ref.artifact_id))
    return _EnvelopeOrigin(artifact_key=artifact_key, source_role=source_role)


def _load_model(ctx: ExecutionContext, ref: ArtifactRef, model_cls):
    payload = _load_artifact_json(ctx, ref)
    if model_cls is Metrics and isinstance(payload, Mapping):
        # Metrics accepts bool through Pydantic's numeric union coercion; inspect the
        # uncoerced artifact with the same admission boundary before that information is lost.
        _extract_numeric_metrics(payload)
    return model_cls.model_validate(payload)


def _equilibrium_multiplicity_annotation(
    ctx: ExecutionContext,
    sim_result: SimulationResult,
) -> EquilibriumMultiplicityWelfareAnnotation:
    if sim_result.feedback_result_ref is None:
        return EquilibriumMultiplicityWelfareAnnotation(status="not_checked")
    try:
        feedback = _load_model(ctx, sim_result.feedback_result_ref, FeedbackSolveResult)
    except _WELFARE_LOAD_ERRORS:
        return EquilibriumMultiplicityWelfareAnnotation(
            status="unresolved",
            materiality_note="feedback_result_unavailable_for_multiplicity_annotation",
        )
    report_ref = feedback.multiplicity_report_ref
    if report_ref is None:
        return EquilibriumMultiplicityWelfareAnnotation(status="not_checked")
    generic_ref = ArtifactRefModel.model_validate(report_ref.model_dump(mode="python"))
    try:
        report = _load_model(ctx, report_ref, EquilibriumMultiplicityReport)
    except _WELFARE_LOAD_ERRORS:
        return EquilibriumMultiplicityWelfareAnnotation(
            status="unresolved",
            report_ref=generic_ref,
            selection_dependence=True,
            materiality_note="equilibrium_multiplicity_report_unavailable",
        )
    count = int(report.global_diagnostics.num_equilibria)
    unresolved = int(report.global_diagnostics.num_unresolved)
    status: Literal["unique", "multiple", "unresolved", "not_checked"]
    if count > 1:
        status = "multiple"
    elif unresolved > 0:
        status = "unresolved"
    elif count == 1:
        status = "unique"
    else:
        status = "unresolved"
    return EquilibriumMultiplicityWelfareAnnotation(
        status=status,
        report_ref=generic_ref,
        selection_dependence=status in {"multiple", "unresolved"},
        materiality_note=(
            f"equilibria={count}; unresolved_starts={unresolved}; "
            f"bifurcation_candidates={len(report.bifurcation_candidates)}"
        ),
        metadata={
            "num_equilibria": count,
            "num_unresolved": unresolved,
            "bifurcation_candidate_count": len(report.bifurcation_candidates),
        },
    )


def _load_welfare_params(state: ExperimentState) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    raw_config = state.params.get("welfare_config")
    if isinstance(raw_config, dict):
        resolved.update(raw_config)
    for key, value in state.params.items():
        if key.startswith("welfare_"):
            resolved[key[8:]] = value
    return resolved


def _has_explicit_welfare_request(
    welfare_params: Mapping[str, Any],
    *,
    keys: frozenset[str],
) -> bool:
    for key in keys:
        if welfare_params.get(key) is not None:
            return True
        prefixed_key = f"welfare_{key}"
        if welfare_params.get(prefixed_key) is not None:
            return True
    return False


def _coerce_welfare_numeric_scalar(value: object, *, allow_numeric_string: bool = False) -> float:
    """Convert a supported real scalar without accepting boolean or arbitrary objects."""
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("boolean values are not welfare numeric scalars")
    if not isinstance(value, (Real, Decimal)) and not (
        allow_numeric_string and isinstance(value, str)
    ):
        raise TypeError("value is outside the declared welfare numeric input types")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("welfare numeric scalar could not be represented as float") from exc
    if not math.isfinite(numeric):
        raise ValueError("welfare numeric scalar must be finite")
    return numeric


def _admit_welfare_numeric_scalar(value: object, *, field_name: str) -> float:
    try:
        return _coerce_welfare_numeric_scalar(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            f"{field_name} values must be finite real numeric scalars",
            details={"field": field_name, "received_type": type(value).__name__},
        ) from exc


def _admit_welfare_numeric_mapping(
    values: Mapping[object, object], *, field_name: str
) -> dict[str, float]:
    admitted: dict[str, float] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                f"{field_name} mapping keys must be non-empty strings",
                details={"field": field_name},
            )
        admitted[key] = _admit_welfare_numeric_scalar(value, field_name=field_name)
    return admitted


def _admit_welfare_numeric_sequence(
    values: list[object] | tuple[object, ...], *, field_name: str
) -> np.ndarray:
    return np.asarray(
        [_admit_welfare_numeric_scalar(value, field_name=field_name) for value in values],
        dtype=np.float64,
    )


def _extract_numeric_metrics(metrics: Metrics | Mapping[str, Any]) -> dict[str, float]:
    values = metrics.values if isinstance(metrics, Metrics) else metrics.get("values", {})
    if not isinstance(values, Mapping):
        return {}
    out: dict[str, float] = {}
    for key, value in values.items():
        try:
            numeric = _coerce_welfare_numeric_scalar(value, allow_numeric_string=True)
        except (TypeError, ValueError, OverflowError) as exc:
            if isinstance(value, (bool, np.bool_)):
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "Simulation metrics cannot use boolean values as welfare scalars",
                    details={"metric": str(key)},
                ) from exc
            continue
        out[str(key)] = numeric
    return out


def _admit_input_envelope(
    name: str,
    envelope: UncertaintyEnvelope,
    *,
    source_role: str,
    envelopes: dict[str, UncertaintyEnvelope],
    refs: dict[str, UncertaintyEnvelopeRef],
    origins: dict[str, _EnvelopeOrigin],
    calibration_issues: set[str],
    origin_ref: ArtifactRefModel | None = None,
    ref: UncertaintyEnvelopeRef | None = None,
) -> None:
    """Admit one envelope while preserving its source and calibration conflict state."""
    previous = envelopes.get(name)
    previous_origin = origins.get(name)
    current_origin = _envelope_origin(source_role=source_role, ref=origin_ref)
    if previous is not None and previous_origin is not None:
        same_source = (
            current_origin.artifact_key is not None
            and current_origin.artifact_key == previous_origin.artifact_key
        )
        same_content = previous.model_dump(mode="json") == envelope.model_dump(mode="json")
        if same_source and same_content:
            return
        if (
            previous_origin.source_role == "calibration_report"
            or source_role == "calibration_report"
        ):
            calibration_issues.add("calibration_envelope_conflict")
            if previous_origin.source_role == "calibration_report":
                return
    elif previous is not None and (
        previous_origin is None
        or previous_origin.source_role == "calibration_report"
        or source_role == "calibration_report"
    ):
        # Equal values without a shared content-addressed origin are not evidence that
        # two producers admitted the same envelope.
        calibration_issues.add("calibration_envelope_conflict")
        if previous_origin is not None and previous_origin.source_role == "calibration_report":
            return
    envelopes[name] = envelope
    origins[name] = current_origin
    if ref is None:
        refs.pop(name, None)
    else:
        refs[name] = ref


def _load_calibration_report_envelopes(
    ctx: ExecutionContext,
    report: CalibrationReport,
    calibration_ref: ArtifactRefModel,
    *,
    admit: Any,
) -> list[str]:
    """Load report-owned envelopes and admit them with their exact source refs."""
    loaded_names: list[str] = []
    if report.uncertainty_envelope_refs:
        for name, ref in report.uncertainty_envelope_refs.items():
            key = str(name)
            loaded_names.append(key)
            admit(
                key,
                load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), ref),
                source_role="calibration_report",
                origin_ref=ref,
                ref=ref,
            )
    elif report.uncertainty_envelopes:
        for name, envelope in report.uncertainty_envelopes.items():
            key = str(name)
            loaded_names.append(key)
            admit(
                key,
                envelope,
                source_role="calibration_report",
                origin_ref=calibration_ref,
            )
    return loaded_names


def _calibration_fields_from_report(
    report: CalibrationReport,
    *,
    loaded_names: list[str],
    projection_present: bool,
    projection_status: str,
    issues: set[str],
) -> tuple[str, ...]:
    """Resolve calibration field order and record unsupported projection states."""
    if report.coordinate_projection is not None:
        fields = report.coordinate_projection.field_order
        if report.uncertainties is not None and not set(fields) <= set(loaded_names):
            issues.add("calibration_covariance_invalid")
    else:
        fields = tuple(loaded_names) or tuple(str(name) for name in report.calibrated_params)
        if report.uncertainties is not None:
            legacy_identity = (
                report.schema_version == "1.0"
                and set(report.uncertainties.params) == set(report.calibrated_params)
                and len(report.uncertainties.params) == len(report.calibrated_params)
            )
            if projection_status == "incomplete":
                issues.add("calibration_projection_incomplete")
            elif projection_status == "unsupported":
                issues.add("calibration_projection_unsupported")
            elif not legacy_identity:
                issues.add("calibration_projection_missing")
    if not loaded_names and report.uncertainties is not None:
        issues.add(
            "calibration_projection_missing"
            if not projection_present
            else "calibration_covariance_invalid"
        )
    return tuple(fields)


def _collect_inline_envelopes(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    calibration_fields: tuple[str, ...],
    calibration_issues: set[str],
    admit: Any,
) -> None:
    """Admit valid inline envelopes and retain conflicts with calibration fields."""
    raw_input_envelopes = welfare_params.get("input_envelopes")
    if not isinstance(raw_input_envelopes, dict):
        return
    for name, value in raw_input_envelopes.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(value, dict) and {"artifact_id", "kind", "media_type"} <= set(value):
            ref = UncertaintyEnvelopeRef.model_validate(value)
            admit(
                name,
                load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), ref),
                source_role="inline_ref",
                origin_ref=ref,
                ref=ref,
            )
            continue
        try:
            admit(
                name,
                UncertaintyEnvelope.model_validate(value),
                source_role="inline",
            )
        except _WELFARE_VALIDATION_ERRORS:
            logger.debug("Invalid inline welfare input envelope for %s", name, exc_info=True)
            if name in calibration_fields:
                calibration_issues.add("calibration_envelope_conflict")


def _build_calibration_covariance_source(
    calibration_ref: ArtifactRefModel | None,
    report: CalibrationReport | None,
    *,
    fields: tuple[str, ...],
    projection_present: bool,
    projection_status: str,
    issues: set[str],
) -> _CalibrationCovarianceSource | None:
    """Build the report-bound covariance source only when it carries a relevant field."""
    if calibration_ref is None or report is None or not (fields or issues):
        return None
    coordinate_order = (
        tuple(report.uncertainties.params) if report.uncertainties is not None else ()
    )
    coordinate_covariance = (
        tuple(tuple(float(value) for value in row) for row in report.uncertainties.covariance)
        if report.uncertainties is not None
        else ()
    )
    return _CalibrationCovarianceSource(
        report_ref=calibration_ref,
        report_schema_version=report.schema_version,
        projection_status=projection_status,
        field_order=fields,
        projection_present=projection_present,
        coordinate_projection=report.coordinate_projection,
        coordinate_order=coordinate_order,
        coordinate_covariance=coordinate_covariance,
        issue_codes=tuple(sorted(issues)),
    )


def _collect_input_envelopes(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    welfare_params: Mapping[str, Any],
) -> _EnvelopeCollection:
    envelopes: dict[str, UncertaintyEnvelope] = {}
    refs: dict[str, UncertaintyEnvelopeRef] = {}
    origins: dict[str, _EnvelopeOrigin] = {}
    calibration_issues: set[str] = set()

    def admit(name: str, envelope: UncertaintyEnvelope, **kwargs: Any) -> None:
        _admit_input_envelope(
            name,
            envelope,
            envelopes=envelopes,
            refs=refs,
            origins=origins,
            calibration_issues=calibration_issues,
            **kwargs,
        )

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        snapshot = _load_model(ctx, data_snapshot_ref, DataSnapshot)
        if snapshot.uncertainty_envelope_ref is not None:
            envelope_ref = snapshot.uncertainty_envelope_ref
            envelope = load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), envelope_ref)
            raw_name = envelope.metadata.get("param_name")
            name = (
                str(raw_name) if isinstance(raw_name, str) and raw_name.strip() else "data_snapshot"
            )
            admit(
                name,
                envelope,
                source_role="data_snapshot",
                origin_ref=envelope_ref,
                ref=envelope_ref,
            )

    calibration_ref = state.inputs.get(INPUT_CALIBRATION_REPORT_REF)
    report = (
        _load_model(ctx, calibration_ref, CalibrationReport)
        if calibration_ref is not None
        else None
    )
    projection_present = report is not None and report.coordinate_projection is not None
    projection_status = (
        (report.coordinate_projection_status or "not_established")
        if report is not None
        else "not_established"
    )
    if projection_status == "incomplete":
        calibration_issues.add("calibration_projection_incomplete")
    elif projection_status == "unsupported":
        calibration_issues.add("calibration_projection_unsupported")

    calibration_fields: tuple[str, ...] = ()
    if report is not None and calibration_ref is not None:
        loaded_names = _load_calibration_report_envelopes(ctx, report, calibration_ref, admit=admit)
        calibration_fields = _calibration_fields_from_report(
            report,
            loaded_names=loaded_names,
            projection_present=projection_present,
            projection_status=projection_status,
            issues=calibration_issues,
        )

    _collect_inline_envelopes(
        ctx,
        welfare_params=welfare_params,
        calibration_fields=calibration_fields,
        calibration_issues=calibration_issues,
        admit=admit,
    )
    calibration_source = _build_calibration_covariance_source(
        calibration_ref,
        report,
        fields=calibration_fields,
        projection_present=projection_present,
        projection_status=projection_status,
        issues=calibration_issues,
    )
    return _EnvelopeCollection(
        envelopes=envelopes,
        refs=refs,
        calibration_source=calibration_source,
    )


def _resolve_welfare_context(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    numeric_metrics: Mapping[str, float],
    response_size_hint: int,
) -> _ResolvedWelfareContext:
    labels, base_response = _resolve_base_response(
        welfare_params=welfare_params,
        numeric_metrics=numeric_metrics,
    )
    weights, weights_ref = _resolve_weights(
        ctx,
        welfare_params=welfare_params,
        labels=labels,
    )
    social_weight_ref = ensure_social_weight_manifest_artifact(
        ctx,
        welfare_params=welfare_params,
    )
    policy_ref = _coerce_artifact_ref(welfare_params.get("policy_ref"))
    baseline_ref = _coerce_artifact_ref(welfare_params.get("baseline_ref"))
    pe_model_ref = _coerce_artifact_ref(welfare_params.get("pe_model_ref"))
    dependence_context = _resolve_dependence_context(ctx, welfare_params)
    dependence_structure_ref = dependence_context.ref
    pe_sensitivity = _resolve_pe_sensitivity(
        welfare_params=welfare_params,
        labels=labels,
    )
    ge_multiplier_semantics = _resolve_ge_multiplier_semantics(welfare_params)
    model_class = str(welfare_params.get("model_class") or "linearized_ge_io")
    _validate_model_class(model_class, ge_multiplier_semantics)
    ge_context = _resolve_ge_context(
        ctx,
        welfare_params=welfare_params,
        size=len(labels),
        ge_multiplier_semantics=ge_multiplier_semantics,
    )
    if ge_context.point_multiplier is not None and ge_context.point_multiplier.shape != (
        len(labels),
        len(labels),
    ):
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "GE multiplier dimensions do not match welfare response vector",
            details={
                "multiplier_shape": list(ge_context.point_multiplier.shape),
                "response_size": len(labels),
            },
        )
    warnings = list(ge_context.warnings)
    diagnostics = {
        "response_size": len(labels),
        "metric_labels": list(labels),
        "weights_norm": float(np.linalg.norm(weights)),
        "response_size_hint": response_size_hint,
        "dependence_structure": dependence_context.diagnostics,
        **ge_context.diagnostics,
    }
    return _ResolvedWelfareContext(
        welfare_measure=str(welfare_params.get("measure") or "net_social_welfare"),
        model_class=model_class,
        ge_multiplier_semantics=ge_multiplier_semantics,
        labels=labels,
        base_response=base_response,
        weights=weights,
        weights_ref=weights_ref,
        social_weight_ref=social_weight_ref,
        policy_ref=policy_ref,
        baseline_ref=baseline_ref,
        pe_model_ref=pe_model_ref,
        dependence_structure_ref=dependence_structure_ref,
        dependence_context=dependence_context,
        pe_sensitivity=pe_sensitivity,
        ge_context=ge_context,
        warnings=tuple(warnings),
        diagnostics=diagnostics,
    )


def _response_from_mapping(
    raw_response: Mapping[str, Any], metric_order: list[str] | None
) -> tuple[tuple[str, ...], np.ndarray]:
    if not raw_response:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response must contain at least one response component",
        )
    admitted_response = _admit_welfare_numeric_mapping(
        raw_response, field_name="welfare_pe_response"
    )
    labels = metric_order or list(admitted_response)
    missing = [label for label in labels if label not in admitted_response]
    if missing:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response is missing a requested metric_order label",
            details={"missing_labels": missing},
        )
    vector = np.asarray([admitted_response[label] for label in labels], dtype=np.float64)
    return tuple(labels), vector


def _response_from_sequence(
    raw_response: list[Any] | tuple[Any, ...], metric_order: list[str] | None
) -> tuple[tuple[str, ...], np.ndarray]:
    if not raw_response:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response must contain at least one response component",
        )
    vector = _admit_welfare_numeric_sequence(raw_response, field_name="welfare_pe_response")
    if metric_order is not None and len(metric_order) != vector.shape[0]:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_metric_order length must match welfare_pe_response length",
            details={"metric_order": len(metric_order), "pe_response": int(vector.shape[0])},
        )
    labels = (
        tuple(f"component_{idx}" for idx in range(vector.shape[0]))
        if metric_order is None
        else tuple(metric_order)
    )
    return labels, vector


def _response_from_metrics(
    labels: list[str], numeric_metrics: Mapping[str, float], *, error_message: str
) -> tuple[tuple[str, ...], np.ndarray]:
    missing = [label for label in labels if label not in numeric_metrics]
    if missing:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            error_message,
            details={"missing_metrics": missing},
        )
    vector = np.asarray(
        [
            _admit_welfare_numeric_scalar(numeric_metrics[label], field_name="simulation metrics")
            for label in labels
        ],
        dtype=np.float64,
    )
    return tuple(labels), vector


def _resolve_base_response(
    *,
    welfare_params: Mapping[str, Any],
    numeric_metrics: Mapping[str, float],
) -> tuple[tuple[str, ...], np.ndarray]:
    numeric_metrics = _admit_welfare_numeric_mapping(
        numeric_metrics, field_name="simulation metrics"
    )
    metric_order: list[str] | None = None
    if "metric_order" in welfare_params:
        raw_order = welfare_params["metric_order"]
        if (
            not isinstance(raw_order, (list, tuple))
            or not raw_order
            or any(not isinstance(label, str) or not label.strip() for label in raw_order)
            or len(set(raw_order)) != len(raw_order)
        ):
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_metric_order must contain unique non-empty labels",
            )
        metric_order = list(raw_order)
    if "pe_response" in welfare_params:
        raw_response = welfare_params["pe_response"]
        if isinstance(raw_response, Mapping):
            return _response_from_mapping(raw_response, metric_order)
        if isinstance(raw_response, (list, tuple)):
            return _response_from_sequence(raw_response, metric_order)
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response must be a mapping or a sequence when provided",
            details={"received_type": type(raw_response).__name__},
        )
    if metric_order is not None:
        return _response_from_metrics(
            metric_order,
            numeric_metrics,
            error_message="Requested welfare_metric_order labels are missing from simulation metrics",
        )
    raw_weights = welfare_params.get("weights")
    if isinstance(raw_weights, Mapping):
        return _response_from_metrics(
            [str(key) for key in raw_weights],
            numeric_metrics,
            error_message=(
                "welfare_weights keys must align with numeric simulation metrics when pe_response is omitted"
            ),
        )
    for candidate in ("net_social_welfare", "welfare", "policy_value", "gdp_change"):
        if candidate in numeric_metrics:
            return (candidate,), np.asarray(
                [
                    _admit_welfare_numeric_scalar(
                        numeric_metrics[candidate], field_name="simulation metrics"
                    )
                ],
                dtype=np.float64,
            )
    if len(numeric_metrics) == 1:
        label, value = next(iter(numeric_metrics.items()))
        return (label,), np.asarray(
            [_admit_welfare_numeric_scalar(value, field_name="simulation metrics")],
            dtype=np.float64,
        )
    raise _fail_error(
        _ERROR_WELFARE_DIMENSION_MISMATCH,
        "No welfare target could be resolved from metrics or welfare_pe_response",
        details={"available_metrics": sorted(numeric_metrics)},
    )


def _resolve_weights(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
) -> tuple[np.ndarray, ArtifactRefModel | None]:
    if not labels:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "Welfare aggregation requires at least one response label",
        )
    if "weights" not in welfare_params:
        if len(labels) != 1:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights must be provided when aggregating more than one response component",
                details={"labels": list(labels)},
            )
        return np.asarray([1.0], dtype=np.float64), None
    raw_weights = welfare_params["weights"]

    if isinstance(raw_weights, Mapping):
        admitted_weights = _admit_welfare_numeric_mapping(raw_weights, field_name="welfare_weights")
        missing = [label for label in labels if label not in raw_weights]
        if missing:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights is missing one or more response labels",
                details={"missing_labels": missing},
            )
        vector = np.asarray([admitted_weights[label] for label in labels], dtype=np.float64)
    elif isinstance(raw_weights, (list, tuple)):
        vector = _admit_welfare_numeric_sequence(raw_weights, field_name="welfare_weights")
        if vector.shape[0] != len(labels):
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights length must match response vector length",
                details={"weights": int(vector.shape[0]), "response": len(labels)},
            )
    else:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_weights must be a dict keyed by labels or a dense list",
        )
    if not np.all(np.isfinite(vector)):
        raise _fail_error(
            _ERROR_WELFARE_OUTPUT_NONFINITE,
            "welfare_weights must be finite",
        )

    weights_ref = _persist_json_payload(
        ctx,
        payload={"labels": list(labels), "weights": vector.tolist()},
        kind="ir.welfare_weights",
        schema_name="ir.welfare_weights",
    )
    return vector, weights_ref


def _source_social_weight_handle(welfare_params: Mapping[str, Any]) -> str | None:
    for key in (
        "welfare_social_weight_ref",
        "social_weight_ref",
    ):
        value = welfare_params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_dependence_context(
    ctx: ExecutionContext,
    welfare_params: Mapping[str, Any],
) -> _ResolvedDependenceContext:
    raw = welfare_params.get("dependence_structure_ref")
    if raw is None:
        return _ResolvedDependenceContext(
            ref=None,
            structure=None,
            correlation_matrix=None,
            parameter_order=(),
            strategy="independent",
            warnings=(),
            diagnostics={"present": False, "strategy": "independent"},
        )
    try:
        ref = DependenceStructureRef.model_validate(raw)
        structure = load_dependence_structure(_ensure_ir_artifact_store(ctx.store), ref)
    except _WELFARE_VALIDATION_ERRORS as exc:
        raise _fail_error(
            _ERROR_DEPENDENCE_SPEC_INVALID,
            "Invalid welfare dependence_structure_ref",
            details={"error": str(exc)},
        ) from exc
    warnings = list(structure.warnings)
    if structure.blocking_reasons:
        warnings.extend(f"blocking:{item}" for item in structure.blocking_reasons)

    metadata = dict(structure.metadata)
    parameter_order = (
        _coerce_str_list(metadata.get("parameter_order"))
        or _coerce_str_list(metadata.get("parameter_names"))
        or _coerce_str_list(metadata.get("order"))
        or []
    )
    correlation_matrix = _coerce_dependence_matrix(
        metadata.get("correlation_matrix")
        or metadata.get("gaussian_copula_correlation")
        or metadata.get("gaussian_copula_corr")
    )
    covariance_matrix = _coerce_dependence_matrix(
        metadata.get("covariance_matrix") or metadata.get("gaussian_copula_covariance")
    )
    strategy = "descriptive_only"
    if correlation_matrix is None and covariance_matrix is not None:
        correlation_matrix = _correlation_from_covariance(covariance_matrix)
        strategy = "gaussian_copula_from_covariance"
    elif correlation_matrix is not None:
        strategy = "gaussian_copula"

    if correlation_matrix is not None:
        if not parameter_order or len(parameter_order) != correlation_matrix.shape[0]:
            warnings.append("dependence_parameter_order_mismatch")
            correlation_matrix = None
            strategy = "descriptive_only"
        else:
            correlation_matrix = _stabilize_correlation_matrix(correlation_matrix)

    diagnostics = {
        "present": True,
        "regime": structure.regime,
        "class_label": structure.class_label,
        "recommended_covariance": structure.recommended_covariance,
        "calibrated": bool(structure.calibrated),
        "source_method": structure.source_method,
        "strategy": strategy,
        "parameter_order": list(parameter_order),
        "warnings": list(warnings),
        "blocking_reasons": list(structure.blocking_reasons),
    }
    if correlation_matrix is not None:
        diagnostics["matrix_shape"] = list(correlation_matrix.shape)
    return _ResolvedDependenceContext(
        ref=ref,
        structure=structure,
        correlation_matrix=correlation_matrix,
        parameter_order=tuple(parameter_order),
        strategy=strategy,
        warnings=tuple(warnings),
        diagnostics=diagnostics,
    )


def _resolve_pe_sensitivity(
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
) -> dict[str, dict[str, float]]:
    if "pe_sensitivity" not in welfare_params:
        return {label: {label: 1.0} for label in labels}
    raw = welfare_params["pe_sensitivity"]
    resolved: dict[str, dict[str, float]] = {}
    if not isinstance(raw, Mapping) or not raw:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_sensitivity must be a non-empty mapping when provided",
            details={"received_type": type(raw).__name__},
        )

    unknown_labels = [label for label in raw if not isinstance(label, str) or label not in labels]
    if unknown_labels:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_sensitivity contains labels outside welfare_metric_order",
            details={"unknown_labels": [str(label) for label in unknown_labels]},
        )
    for label, per_label in raw.items():
        if not isinstance(per_label, Mapping) or not per_label:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_pe_sensitivity entries must be non-empty parameter mappings",
                details={"label": label, "received_type": type(per_label).__name__},
            )
        label_map: dict[str, float] = {}
        for param_name, coef in per_label.items():
            if not isinstance(param_name, str) or not param_name.strip():
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_pe_sensitivity parameter names must be non-empty strings",
                    details={"label": label, "parameter": str(param_name)},
                )
            try:
                numeric_coef = _coerce_welfare_numeric_scalar(coef)
            except (TypeError, ValueError, OverflowError) as exc:
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_pe_sensitivity coefficients must be finite numbers",
                    details={"label": label, "parameter": param_name},
                ) from exc
            if not math.isfinite(numeric_coef):
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_pe_sensitivity coefficients must be finite numbers",
                    details={"label": label, "parameter": param_name},
                )
            label_map[param_name] = numeric_coef
        resolved[label] = label_map
    return resolved


def _resolve_ge_multiplier_semantics(welfare_params: Mapping[str, Any]) -> str:
    explicit = welfare_params.get("ge_multiplier_semantics")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if welfare_params.get("ge_technical_coefficients") is not None:
        return "leontief_inverse"
    if welfare_params.get("ge_model_ref") is not None:
        return "leontief_inverse"
    return "reduced_form_ge_multiplier"


def _validate_model_class(model_class: str, ge_multiplier_semantics: str) -> None:
    if model_class == "linearized_ge_io" and ge_multiplier_semantics not in {
        "leontief_inverse",
        "reduced_form_ge_multiplier",
    }:
        raise _fail_error(
            _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
            "linearized_ge_io requires leontief or reduced-form GE semantics",
            details={"ge_multiplier_semantics": ge_multiplier_semantics},
        )
    if model_class == "linearized_cge" and ge_multiplier_semantics not in {
        "jacobian_inverse",
        "reduced_form_ge_multiplier",
    }:
        raise _fail_error(
            _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
            "linearized_cge requires jacobian or reduced-form GE semantics",
            details={"ge_multiplier_semantics": ge_multiplier_semantics},
        )
