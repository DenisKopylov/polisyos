"""Internal welfare covariance implementation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from polisyos.core.artifacts.manifest import InputRef
from polisyos.foundry.uncertainty.covariance import (
    CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
    CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
    build_covariance_matrix,
    calibration_covariance_blocks_agree_v1,
    preserve_singular_covariance,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    PosteriorSamplesCarrier,
    UncertaintyEnvelope,
)
from polisyos.ir.analytics.welfare import WelfareMethod
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    DependenceStructureRef,
    UncertaintyEnvelopeRef,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext

from .welfare_draws import _posterior_sample_probabilities
from .welfare_ge import _stabilize_correlation_matrix
from .welfare_types import (
    _CALIBRATION_COORDINATE_PROJECTION_VERSION,
    _CalibrationCoordinateLaw,
    _CalibrationCoordinateSampler,
    _CalibrationCovarianceSource,
    _CovarianceResolution,
    _EmpiricalRowSampler,
    _extract_std,
    _input_envelope_refs,
    _input_ref,
    _persist_json_payload,
    _PropagationOutcome,
    _ResolvedDependenceContext,
)


def _covariance_limitation(code: str, note: Mapping[str, Any]) -> _CovarianceResolution:
    return _CovarianceResolution(
        matrix=None,
        dependence_applied=False,
        note=dict(note),
        limitation_code=code,
    )


def _calibration_projection_matrix(
    calibration_source: _CalibrationCovarianceSource,
    *,
    calibration_fields: list[str],
) -> np.ndarray | _CovarianceResolution:
    projection = calibration_source.coordinate_projection
    if projection is not None:
        if (
            projection.field_order != calibration_source.field_order
            or projection.coordinate_order != calibration_source.coordinate_order
            or calibration_source.projection_status != "complete"
        ):
            return _covariance_limitation(
                "calibration_projection_invalid",
                {
                    "strategy": "calibration_report_projection_invalid",
                    "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                    "calibration_fields": calibration_fields,
                },
            )
        return np.asarray(projection.matrix, dtype=np.float64)
    if calibration_source.report_schema_version == "1.0":
        coordinate_order = calibration_source.coordinate_order
        if (
            not coordinate_order
            or len(set(coordinate_order)) != len(coordinate_order)
            or set(coordinate_order) != set(calibration_source.field_order)
            or len(coordinate_order) != len(calibration_source.field_order)
        ):
            return _covariance_limitation(
                "calibration_projection_missing",
                {
                    "strategy": "calibration_report_legacy_identity_incomplete",
                    "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                    "coordinate_order": list(coordinate_order),
                    "calibration_field_order": list(calibration_source.field_order),
                },
            )
        return np.asarray(
            [
                [1.0 if field == coordinate else 0.0 for coordinate in coordinate_order]
                for field in calibration_source.field_order
            ],
            dtype=np.float64,
        )
    return _covariance_limitation(
        "calibration_projection_missing",
        {
            "strategy": "calibration_report_projection_missing",
            "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
            "calibration_fields": calibration_fields,
        },
    )


def _project_calibration_coordinate_covariance(
    calibration_source: _CalibrationCovarianceSource,
    *,
    calibration_fields: list[str],
    envelope_covariance: np.ndarray,
    full_projection: np.ndarray,
) -> tuple[np.ndarray, _CalibrationCoordinateLaw] | _CovarianceResolution:
    coordinate_order = calibration_source.coordinate_order
    try:
        coordinate_covariance = preserve_singular_covariance(
            np.asarray(calibration_source.coordinate_covariance, dtype=np.float64),
            symmetry_rtol=CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
            symmetry_atol=CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
        )
        if coordinate_covariance.shape != (len(coordinate_order), len(coordinate_order)):
            raise ValueError("coordinate covariance shape does not match coordinate order")
        if full_projection.shape != (
            len(calibration_source.field_order),
            len(coordinate_order),
        ):
            raise ValueError("coordinate projection shape does not match its declared orders")
        projection_rows = [
            calibration_source.field_order.index(name) for name in calibration_fields
        ]
        projection_matrix = full_projection[projection_rows, :]
        projected_covariance = preserve_singular_covariance(
            projection_matrix @ coordinate_covariance @ projection_matrix.T,
            symmetry_rtol=CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
            symmetry_atol=CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
        )
    except (TypeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        return _covariance_limitation(
            "calibration_covariance_invalid",
            {
                "strategy": "calibration_report_coordinate_covariance_invalid",
                "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                "coordinate_order": list(coordinate_order),
                "validation_error": str(exc),
            },
        )
    if not calibration_covariance_blocks_agree_v1(projected_covariance, envelope_covariance):
        return _covariance_limitation(
            "calibration_covariance_conflict",
            {
                "strategy": "calibration_report_projection_conflict",
                "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                "projection_schema_version": _CALIBRATION_COORDINATE_PROJECTION_VERSION,
                "coordinate_order": list(coordinate_order),
                "calibration_field_order": list(calibration_source.field_order),
                "calibration_fields": calibration_fields,
                "projected_covariance": projected_covariance.tolist(),
                "envelope_covariance": envelope_covariance.tolist(),
                "reconciliation_tolerance": {
                    "version": 1,
                    "rtol": CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
                    "atol": CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
                },
            },
        )
    law = _CalibrationCoordinateLaw(
        coordinate_order=coordinate_order,
        calibration_fields=tuple(calibration_fields),
        projection_matrix=projection_matrix,
        coordinate_covariance=coordinate_covariance,
    )
    return projected_covariance, law


def _non_normal_covariance_pairs(
    matrix: np.ndarray,
    *,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[set[str], set[str], list[dict[str, Any]]]:
    unsupported_fields: set[str] = set()
    correlated_fields: set[str] = set()
    pairs: list[dict[str, Any]] = []
    for left_index, left_name in enumerate(param_names):
        left_is_non_normal = (
            input_envelopes[left_name].distribution_family is not DistributionFamily.NORMAL
        )
        for right_index in range(left_index + 1, len(param_names)):
            covariance_value = float(matrix[left_index, right_index])
            if covariance_value == 0.0:
                continue
            right_name = param_names[right_index]
            right_is_non_normal = (
                input_envelopes[right_name].distribution_family is not DistributionFamily.NORMAL
            )
            if not left_is_non_normal and not right_is_non_normal:
                continue
            correlated_fields.update((left_name, right_name))
            if left_is_non_normal:
                unsupported_fields.add(left_name)
            if right_is_non_normal:
                unsupported_fields.add(right_name)
            pairs.append(
                {"left_field": left_name, "right_field": right_name, "covariance": covariance_value}
            )
    return unsupported_fields, correlated_fields, pairs


def _mixed_marginal_covariance_limitation(
    covariance: np.ndarray,
    *,
    dependence_context: _ResolvedDependenceContext,
    calibration_source: _CalibrationCovarianceSource,
    coordinate_order: tuple[str, ...],
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> _CovarianceResolution | None:
    matrix = np.asarray(covariance, dtype=np.float64)
    if matrix.shape != (len(param_names), len(param_names)) or not np.all(np.isfinite(matrix)):
        return _covariance_limitation(
            "calibration_covariance_invalid",
            {
                "strategy": "calibration_report_joint_matrix_invalid",
                "limitation_code": "calibration_covariance_invalid",
                "covariance_order": list(param_names),
            },
        )
    unsupported, correlated, pairs = _non_normal_covariance_pairs(
        matrix, param_names=param_names, input_envelopes=input_envelopes
    )
    if not unsupported:
        return None
    code = "calibration_mixed_marginal_covariance_unsupported"
    note = {
        "strategy": code,
        "limitation_code": code,
        "reason": (
            "the current Gaussian-copula marginal transform does not preserve the "
            "admitted Pearson covariance for non-Normal fields"
        ),
        "gate_predicate_class": "recomputed",
        "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
        "calibration_report_schema_version": calibration_source.report_schema_version,
        "calibration_field_order": list(calibration_source.field_order),
        "coordinate_order": list(coordinate_order),
        "projection_schema_version": (
            _CALIBRATION_COORDINATE_PROJECTION_VERSION
            if calibration_source.projection_present
            else None
        ),
        "dependence_structure_ref": (
            str(dependence_context.ref.artifact_id) if dependence_context.ref is not None else None
        ),
        "covariance_order": list(param_names),
        "unsupported_marginal_fields": [name for name in param_names if name in unsupported],
        "correlated_fields": [name for name in param_names if name in correlated],
        "nonzero_covariance_pairs": pairs,
        "covariance_predicate": "exact_nonzero_in_admitted_finite_matrix",
        "decision": "retain_candidate_point_withhold_interval_and_samples",
    }
    return _CovarianceResolution(
        matrix=None, dependence_applied=False, note=note, limitation_code=code
    )


def _calibration_external_overlap_reconciled(
    dependence_context: _ResolvedDependenceContext,
    *,
    calibration_source: _CalibrationCovarianceSource,
    calibration_fields: list[str],
    calibration_covariance: np.ndarray,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> bool | _CovarianceResolution:
    external_order = list(dependence_context.parameter_order)
    external_index = {name: idx for idx, name in enumerate(external_order)}
    external_is_calibrated = (
        dependence_context.correlation_matrix is not None
        and dependence_context.structure is not None
        and dependence_context.structure.calibrated
        and not dependence_context.structure.blocking_reasons
        and len(external_order) == len(external_index)
    )
    if not external_is_calibrated:
        return False
    overlap_fields = [name for name in calibration_fields if name in external_index]
    if not overlap_fields:
        return False
    try:
        overlap_indices = [external_index[name] for name in overlap_fields]
        overlap_stds = np.asarray(
            [_extract_std(input_envelopes[name]) for name in overlap_fields], dtype=np.float64
        )
        external_overlap = dependence_context.correlation_matrix[
            np.ix_(overlap_indices, overlap_indices)
        ] * np.outer(overlap_stds, overlap_stds)
        report_indices = [calibration_fields.index(name) for name in overlap_fields]
        report_overlap = calibration_covariance[np.ix_(report_indices, report_indices)]
    except (KeyError, TypeError, ValueError, FloatingPointError) as exc:
        return _covariance_limitation(
            "calibration_covariance_invalid",
            {
                "strategy": "calibration_report_overlap_invalid",
                "limitation_code": "calibration_covariance_invalid",
                "validation_error": str(exc),
            },
        )
    if not calibration_covariance_blocks_agree_v1(report_overlap, external_overlap):
        return _covariance_limitation(
            "calibration_covariance_conflict",
            {
                "strategy": "calibration_report_overlap_conflict",
                "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                "calibration_fields": overlap_fields,
                "reconciliation_tolerance": {
                    "version": 1,
                    "rtol": CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
                    "atol": CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
                },
            },
        )
    return True


def _resolved_calibration_field_matrix(
    *,
    dependence_context: _ResolvedDependenceContext,
    calibration_source: _CalibrationCovarianceSource,
    calibration_fields: list[str],
    calibration_covariance: np.ndarray,
    coordinate_law: _CalibrationCoordinateLaw,
    overlap_reconciled: bool,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> _CovarianceResolution:
    order = [calibration_fields.index(name) for name in param_names]
    covariance = calibration_covariance[np.ix_(order, order)]
    strategy = (
        "calibration_report_overlap_reconciled"
        if overlap_reconciled
        else "calibration_report_projected_covariance"
    )
    note = {
        "strategy": strategy,
        "covered_params": list(param_names),
        "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
        "covariance_order": list(param_names),
        "covariance_matrix": covariance.tolist(),
        "preserves_singular_ties": True,
        "independence_source_validated": False,
    }
    mixed = _mixed_marginal_covariance_limitation(
        covariance,
        dependence_context=dependence_context,
        calibration_source=calibration_source,
        coordinate_order=coordinate_law.coordinate_order,
        param_names=param_names,
        input_envelopes=input_envelopes,
    )
    if mixed is not None:
        return mixed
    return _CovarianceResolution(
        matrix=covariance,
        dependence_applied=True,
        note=note,
        coordinate_law=coordinate_law,
    )


def _resolve_cross_source_calibration_matrix(
    dependence_context: _ResolvedDependenceContext,
    *,
    calibration_source: _CalibrationCovarianceSource,
    calibration_fields: list[str],
    calibration_covariance: np.ndarray,
    coordinate_law: _CalibrationCoordinateLaw,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> _CovarianceResolution:
    external_order = list(dependence_context.parameter_order)
    external_index = {name: idx for idx, name in enumerate(external_order)}
    if (
        dependence_context.correlation_matrix is None
        or dependence_context.structure is None
        or not dependence_context.structure.calibrated
        or dependence_context.structure.blocking_reasons
        or len(external_order) != len(external_index)
        or not set(param_names) <= set(external_index)
    ):
        code = "calibration_cross_source_dependence_unknown"
        return _covariance_limitation(
            code,
            {
                "strategy": "calibration_report_plus_disjoint_sources",
                "calibration_fields": calibration_fields,
                "uncovered_fields": [
                    name for name in param_names if name not in calibration_fields
                ],
                "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                "reason": "no_complete_calibrated_joint_covariance",
                "independence_source_validated": False,
            },
        )
    dep_indices = [external_index[name] for name in param_names]
    correlation = dependence_context.correlation_matrix[np.ix_(dep_indices, dep_indices)]
    stds = np.asarray([_extract_std(input_envelopes[name]) for name in param_names])
    covariance = correlation * np.outer(stds, stds)
    calibration_indices = [param_names.index(name) for name in calibration_fields]
    external_block = covariance[np.ix_(calibration_indices, calibration_indices)]
    if not calibration_covariance_blocks_agree_v1(calibration_covariance, external_block):
        return _covariance_limitation(
            "calibration_covariance_conflict",
            {
                "strategy": "calibration_report_overlap_conflict",
                "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                "calibration_fields": calibration_fields,
                "reconciliation_tolerance": {
                    "version": 1,
                    "rtol": CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
                    "atol": CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
                },
            },
        )
    extra_indices = [idx for idx, name in enumerate(param_names) if name not in calibration_fields]
    cross_block = covariance[np.ix_(calibration_indices, extra_indices)]
    tolerance = max(
        CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
        CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1 * float(np.max(np.abs(np.diag(covariance)))),
    )
    if float(np.max(np.abs(cross_block))) <= tolerance:
        code = "calibration_cross_source_dependence_unknown"
        return _covariance_limitation(
            code,
            {
                "strategy": "calibration_report_plus_disjoint_sources",
                "calibration_fields": calibration_fields,
                "uncovered_fields": [param_names[index] for index in extra_indices],
                "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                "reason": "zero_cross_covariance_requires_verified_independence",
                "independence_source_validated": False,
            },
        )
    covariance[np.ix_(calibration_indices, calibration_indices)] = calibration_covariance
    covariance = 0.5 * (covariance + covariance.T)
    minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(covariance)))
    if minimum_eigenvalue < -1e-10:
        return _covariance_limitation(
            "calibration_covariance_conflict",
            {
                "strategy": "calibration_report_joint_matrix_not_psd",
                "minimum_eigenvalue": minimum_eigenvalue,
            },
        )
    mixed = _mixed_marginal_covariance_limitation(
        covariance,
        dependence_context=dependence_context,
        calibration_source=calibration_source,
        coordinate_order=coordinate_law.coordinate_order,
        param_names=param_names,
        input_envelopes=input_envelopes,
    )
    if mixed is not None:
        return mixed
    return _CovarianceResolution(
        matrix=covariance,
        dependence_applied=True,
        note={
            "strategy": "calibration_report_reconciled_dependence_structure",
            "covered_params": list(param_names),
            "calibration_fields": calibration_fields,
            "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
            "dependence_structure_ref": (
                str(dependence_context.ref.artifact_id)
                if dependence_context.ref is not None
                else None
            ),
            "reconciliation_tolerance": {
                "version": 1,
                "rtol": CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
                "atol": CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
            },
            "covariance_order": list(param_names),
            "covariance_matrix": covariance.tolist(),
            "preserves_singular_ties": True,
            "independence_source_validated": False,
        },
        coordinate_law=coordinate_law,
    )


def _resolve_calibration_covariance(
    dependence_context: _ResolvedDependenceContext,
    *,
    calibration_source: _CalibrationCovarianceSource,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    jitter: float,
) -> _CovarianceResolution:
    """Resolve one report-owned covariance law for Delta and Monte Carlo."""
    if calibration_source.issue_codes:
        code = calibration_source.issue_codes[0]
        return _covariance_limitation(
            code, {"strategy": "calibration_report", "limitation_code": code}
        )
    calibration_fields = [name for name in calibration_source.field_order if name in param_names]
    if not calibration_fields:
        code = "calibration_projection_missing"
        return _covariance_limitation(
            code, {"strategy": "calibration_report", "limitation_code": code}
        )
    try:
        envelope_covariance = _build_report_covariance(
            calibration_fields, input_envelopes=input_envelopes, jitter=jitter
        )
    except (KeyError, TypeError, ValueError, FloatingPointError) as exc:
        code = "calibration_covariance_invalid"
        return _covariance_limitation(
            code,
            {
                "strategy": "calibration_report",
                "limitation_code": code,
                "validation_error": str(exc),
            },
        )
    full_projection = _calibration_projection_matrix(
        calibration_source, calibration_fields=calibration_fields
    )
    if isinstance(full_projection, _CovarianceResolution):
        return full_projection
    projection = _project_calibration_coordinate_covariance(
        calibration_source,
        calibration_fields=calibration_fields,
        envelope_covariance=envelope_covariance,
        full_projection=full_projection,
    )
    if isinstance(projection, _CovarianceResolution):
        return projection
    calibration_covariance, coordinate_law = projection
    # The projected report law is authoritative; envelope rows independently reconcile it.
    overlap = _calibration_external_overlap_reconciled(
        dependence_context,
        calibration_source=calibration_source,
        calibration_fields=calibration_fields,
        calibration_covariance=calibration_covariance,
        param_names=param_names,
        input_envelopes=input_envelopes,
    )
    if isinstance(overlap, _CovarianceResolution):
        return overlap
    if len(calibration_fields) == len(param_names):
        return _resolved_calibration_field_matrix(
            dependence_context=dependence_context,
            calibration_source=calibration_source,
            calibration_fields=calibration_fields,
            calibration_covariance=calibration_covariance,
            coordinate_law=coordinate_law,
            overlap_reconciled=overlap,
            param_names=param_names,
            input_envelopes=input_envelopes,
        )
    return _resolve_cross_source_calibration_matrix(
        dependence_context,
        calibration_source=calibration_source,
        calibration_fields=calibration_fields,
        calibration_covariance=calibration_covariance,
        coordinate_law=coordinate_law,
        param_names=param_names,
        input_envelopes=input_envelopes,
    )


def _build_report_covariance(
    param_names: list[str],
    *,
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    jitter: float,
) -> np.ndarray:
    """Validate and select a report-owned projected covariance submatrix."""
    reduced_envelopes: dict[str, UncertaintyEnvelope] = {}
    for name in param_names:
        envelope = input_envelopes[name]
        metadata = dict(envelope.metadata)
        row = metadata.get("covariance_row")
        order = metadata.get("covariance_params")
        if (
            not isinstance(row, list)
            or not isinstance(order, list)
            or not all(isinstance(item, str) for item in order)
            or len(order) != len(row)
            or len(set(order)) != len(order)
            or not set(param_names) <= set(order)
        ):
            raise ValueError(f"calibration covariance metadata is incomplete for {name!r}")
        metadata["covariance_row"] = [row[order.index(item)] for item in param_names]
        metadata["covariance_params"] = list(param_names)
        reduced_envelopes[name] = envelope.model_copy(update={"metadata": metadata})
    matrix = build_covariance_matrix(
        param_names,
        reduced_envelopes,
        use_full_covariance=True,
        jitter=jitter,
        preserve_singular=True,
    )
    return np.asarray(matrix, dtype=np.float64)


def _calibration_sampler_indices(
    param_names: list[str], calibration_fields: tuple[str, ...]
) -> tuple[tuple[int, ...], tuple[str, ...], tuple[int, ...]] | None:
    parameter_index = {name: index for index, name in enumerate(param_names)}
    if not calibration_fields or any(name not in parameter_index for name in calibration_fields):
        return None
    calibration_indices = tuple(parameter_index[name] for name in calibration_fields)
    extra_fields = tuple(name for name in param_names if name not in set(calibration_fields))
    extra_indices = tuple(parameter_index[name] for name in extra_fields)
    return calibration_indices, extra_fields, extra_indices


def _calibration_sampler_joint_correlation(
    resolved_covariance: np.ndarray,
    *,
    param_names: list[str],
    calibration_indices: tuple[int, ...],
    extra_fields: tuple[str, ...],
    extra_indices: tuple[int, ...],
    projection_matrix: np.ndarray,
    coordinate_covariance: np.ndarray,
) -> tuple[np.ndarray | None, np.ndarray | None, tuple[float, ...], str | None]:
    if resolved_covariance.shape != (len(param_names), len(param_names)):
        return None, None, (), "calibration_covariance_invalid"
    projection_pseudoinverse = None
    if extra_fields:
        try:
            projection_pseudoinverse = np.linalg.pinv(projection_matrix, rcond=1e-12)
        except np.linalg.LinAlgError:
            return None, None, (), "calibration_cross_source_dependence_unknown"
        cross_block = resolved_covariance[np.ix_(calibration_indices, extra_indices)]
        represented_cross_block = projection_matrix @ projection_pseudoinverse @ cross_block
        if not np.allclose(
            represented_cross_block,
            cross_block,
            rtol=CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
            atol=CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
        ):
            return None, None, (), "calibration_cross_source_dependence_unknown"
    diagonal = np.diag(resolved_covariance)
    tolerance = 1e-10 * max(1.0, float(np.max(np.abs(coordinate_covariance))))
    if not np.all(np.isfinite(diagonal)) or np.any(diagonal < -tolerance):
        return None, None, (), "calibration_covariance_invalid"
    scales = np.sqrt(np.clip(diagonal, 0.0, None))
    denominator = np.outer(scales, scales)
    correlation = np.divide(
        resolved_covariance,
        denominator,
        out=np.zeros_like(resolved_covariance),
        where=denominator > 0.0,
    )
    correlation = 0.5 * (correlation + correlation.T)
    np.fill_diagonal(correlation, np.where(scales > 0.0, 1.0, 0.0))
    extra_stds = tuple(float(scales[index]) for index in extra_indices)
    if extra_fields and any(value <= 0.0 for value in extra_stds):
        zero_columns = [
            position for position, index in enumerate(extra_indices) if scales[index] <= 0.0
        ]
        extra_diagonal = diagonal[list(extra_indices)]
        extra_cross = resolved_covariance[np.ix_(calibration_indices, extra_indices)]
        if np.any(extra_diagonal < 0.0) or np.any(
            np.abs(extra_cross[:, zero_columns]) > CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1
        ):
            return None, None, (), "calibration_cross_source_dependence_unknown"
    return correlation, projection_pseudoinverse, extra_stds, None


def _calibration_dependence_sampler(
    resolution: _CovarianceResolution,
    *,
    calibration_source: _CalibrationCovarianceSource,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[dict[str, Any], _CalibrationCoordinateSampler | None, str | None]:
    """Build a sampler that materializes calibration fields through their persisted projection."""
    if resolution.matrix is None:
        raise ValueError("calibration covariance resolution is missing its matrix")

    def limited(code: str) -> tuple[dict[str, Any], None, str]:
        return (
            {
                "applied": False,
                "strategy": "calibration_report_coordinate_sampling",
                "covered_params": [],
                "uncovered_params": list(param_names),
                "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
                "preserves_singular_ties": False,
                "limitation_code": code,
            },
            None,
            code,
        )

    law = resolution.coordinate_law
    if law is None:
        return limited("calibration_projection_missing")
    indices = _calibration_sampler_indices(param_names, law.calibration_fields)
    if indices is None:
        return limited("calibration_projection_missing")
    calibration_indices, extra_fields, extra_indices = indices
    if any(
        input_envelopes[name].distribution_family != DistributionFamily.NORMAL
        for name in law.calibration_fields
    ):
        return limited("calibration_coordinate_distribution_unsupported")
    correlation, projection_pseudoinverse, extra_stds, limitation = (
        _calibration_sampler_joint_correlation(
            np.asarray(resolution.matrix, dtype=np.float64),
            param_names=param_names,
            calibration_indices=calibration_indices,
            extra_fields=extra_fields,
            extra_indices=extra_indices,
            projection_matrix=law.projection_matrix,
            coordinate_covariance=law.coordinate_covariance,
        )
    )
    if limitation is not None or correlation is None:
        return limited(limitation or "calibration_covariance_invalid")

    sampler = _CalibrationCoordinateSampler(
        coordinate_order=law.coordinate_order,
        calibration_fields=law.calibration_fields,
        extra_fields=extra_fields,
        projection_matrix=law.projection_matrix,
        coordinate_covariance=law.coordinate_covariance,
        joint_covariance=np.asarray(resolution.matrix, dtype=np.float64),
        calibration_indices=calibration_indices,
        extra_indices=extra_indices,
        projection_pseudoinverse=projection_pseudoinverse,
        extra_stds=extra_stds,
    )
    strategy = (
        "calibration_report_optimizer_coordinates"
        if not extra_fields
        else "calibration_report_joint_covariance_projection"
    )
    note = {
        "applied": True,
        "strategy": strategy,
        "covered_params": list(param_names),
        "uncovered_params": [],
        "correlation_matrix": correlation.tolist(),
        "preserves_singular_ties": True,
        "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
    }
    return note, sampler, None


def _calibration_projection_report_metadata(
    calibration_source: _CalibrationCovarianceSource | None,
    *,
    covariance_note: Mapping[str, Any],
    uncertainty_status: str,
) -> dict[str, Any]:
    """Describe the candidate covariance source and its explicit limitations."""
    if calibration_source is None:
        return {}
    return {
        "calibration_report_ref": str(calibration_source.report_ref.artifact_id),
        "calibration_report_schema_version": calibration_source.report_schema_version,
        "calibration_coordinate_projection_status": calibration_source.projection_status,
        "calibration_projection_schema_version": (
            _CALIBRATION_COORDINATE_PROJECTION_VERSION
            if calibration_source.projection_present
            else None
        ),
        "calibration_projection_present": calibration_source.projection_present,
        "calibration_field_order": list(calibration_source.field_order),
        "covariance_source_selection": covariance_note.get("strategy"),
        "independence_source_validated": False,
        "uncertainty_status": uncertainty_status,
    }


def _limited_covariance_outcome(
    ctx: ExecutionContext,
    *,
    config_ref: ArtifactRefModel,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    calibration_source: _CalibrationCovarianceSource | None,
    requested_method: str,
    method_used: WelfareMethod,
    limitation_code: str,
    dependence_note: Mapping[str, Any],
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef] | None = None,
) -> _PropagationOutcome:
    """Preserve the candidate point while withholding an unsupported joint interval."""
    point_value = float(simulation_fn(**nominal_params)["welfare"])
    report_payload = {
        "schema_version": "2.0" if calibration_source is not None else "1.0",
        "input_envelope_count": len(input_envelopes),
        "methods": [method_used.value],
        "requested_method": requested_method,
        "status": "partial",
        "limitation_code": limitation_code,
        "calibration_report_ref": (
            str(calibration_source.report_ref.artifact_id)
            if calibration_source is not None
            else None
        ),
        "dependence_resolution": dict(dependence_note),
        **_calibration_projection_report_metadata(
            calibration_source,
            covariance_note=dependence_note,
            uncertainty_status="partial",
        ),
    }
    report_ref = _persist_json_payload(
        ctx,
        payload=report_payload,
        kind="foundry.welfare_propagation_report",
        schema_name="polisyos.foundry.WelfarePropagationReport",
        inputs=_calibration_lineage_inputs(
            calibration_source,
            additional_refs=_input_envelope_refs(input_envelope_refs or {}),
        ),
    )
    return _PropagationOutcome(
        credible_interval=None,
        method_used=method_used,
        result_map={"welfare": {"point_estimate": point_value}},
        method_config_ref=config_ref,
        report_ref=report_ref,
        sample_bundle_ref=None,
        diagnostics={
            "dependence_applied": False,
            "limitation_codes": [limitation_code],
            "dependence_resolution": dict(dependence_note),
            "calibration_report_ref": (
                str(calibration_source.report_ref.artifact_id)
                if calibration_source is not None
                else None
            ),
            "requested_method": requested_method,
        },
    )


def _build_dependence_sampler(
    dependence_context: _ResolvedDependenceContext,
    *,
    param_names: list[str],
) -> dict[str, Any]:
    if dependence_context.correlation_matrix is None or len(param_names) < 2:
        return {
            "applied": False,
            "strategy": dependence_context.strategy,
            "covered_params": [],
            "uncovered_params": list(param_names),
            "reason": "no_dependence_matrix",
        }
    order_index = {name: idx for idx, name in enumerate(dependence_context.parameter_order)}
    covered = [name for name in param_names if name in order_index]
    if len(covered) < 2:
        return {
            "applied": False,
            "strategy": dependence_context.strategy,
            "covered_params": covered,
            "uncovered_params": [name for name in param_names if name not in covered],
            "reason": "insufficient_parameter_overlap",
        }
    indices = [order_index[name] for name in covered]
    correlation = dependence_context.correlation_matrix[np.ix_(indices, indices)]
    correlation = _stabilize_correlation_matrix(correlation)
    return {
        "applied": True,
        "strategy": dependence_context.strategy,
        "covered_params": covered,
        "uncovered_params": [name for name in param_names if name not in covered],
        "correlation_matrix": correlation.tolist(),
    }


def _resolve_empirical_row_sampler(
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    *,
    calibration_coordinates_active: bool,
) -> tuple[_EmpiricalRowSampler | None, str | None]:
    """Admit only a single empirical marginal or explicitly paired source rows."""
    payloads = {
        name: envelope.distribution_payload
        for name, envelope in input_envelopes.items()
        if isinstance(envelope.distribution_payload, PosteriorSamplesCarrier)
    }
    if not payloads:
        return None, None
    if calibration_coordinates_active:
        return None, "empirical_joint_law_missing"

    probabilities_by_name: dict[str, tuple[float, ...]] = {}
    for name, payload in payloads.items():
        assert isinstance(payload, PosteriorSamplesCarrier)
        probabilities = _posterior_sample_probabilities(payload)
        if probabilities is None:
            return None, "empirical_sample_weights_invalid"
        probabilities_by_name[name] = probabilities

    if len(param_names) == 1 and set(payloads) == set(param_names):
        name = param_names[0]
        payload = payloads[name]
        assert isinstance(payload, PosteriorSamplesCarrier)
        return (
            _EmpiricalRowSampler(
                param_names=(name,),
                samples_by_name={name: payload.samples},
                probabilities=probabilities_by_name[name],
                dependence_note={
                    "applied": False,
                    "strategy": "empirical_weighted_marginal",
                    "covered_params": [name],
                    "uncovered_params": [],
                    "source_weights_applied": payload.weights is not None,
                },
            ),
            None,
        )

    if set(payloads) != set(param_names) or len(payloads) < 2:
        return None, "empirical_joint_law_missing"

    joint_ids = [input_envelopes[name].metadata.get("joint_sample_id") for name in param_names]
    sample_axes = [
        payloads[name].sample_axis
        for name in param_names
        if isinstance(payloads[name], PosteriorSamplesCarrier)
    ]
    sample_counts = [
        len(payloads[name].samples)
        for name in param_names
        if isinstance(payloads[name], PosteriorSamplesCarrier)
    ]
    first_probabilities = probabilities_by_name[param_names[0]]
    if (
        not all(isinstance(value, str) and value.strip() for value in joint_ids)
        or len(set(joint_ids)) != 1
        or not sample_axes
        or not all(isinstance(value, str) and value.strip() for value in sample_axes)
        or len(set(sample_axes)) != 1
        or not sample_counts
        or len(set(sample_counts)) != 1
        or any(probabilities_by_name[name] != first_probabilities for name in param_names[1:])
    ):
        return None, "empirical_joint_law_missing"

    joint_id = str(joint_ids[0])
    sample_axis = sample_axes[0]
    source_weights_applied = any(
        isinstance(payloads[name], PosteriorSamplesCarrier) and payloads[name].weights is not None
        for name in param_names
    )
    return (
        _EmpiricalRowSampler(
            param_names=tuple(param_names),
            samples_by_name={
                name: payloads[name].samples
                for name in param_names
                if isinstance(payloads[name], PosteriorSamplesCarrier)
            },
            probabilities=first_probabilities,
            dependence_note={
                "applied": True,
                "strategy": "empirical_joint_rows",
                "covered_params": list(param_names),
                "uncovered_params": [],
                "joint_sample_id": joint_id,
                "sample_axis": sample_axis,
                "joint_identity_status": "declared_non_authoritative",
                "source_weights_applied": source_weights_applied,
            },
        ),
        None,
    )


def _build_parameter_covariance(
    dependence_context: _ResolvedDependenceContext,
    *,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[np.ndarray, bool, dict[str, Any]]:
    stds = np.asarray(
        [max(_extract_std(input_envelopes[name]), 1e-12) for name in param_names], dtype=np.float64
    )
    covariance = np.diag(stds**2)
    note: dict[str, Any] = {
        "strategy": "independent",
        "covered_params": [],
        "uncovered_params": list(param_names),
    }
    if dependence_context.correlation_matrix is None or len(param_names) < 2:
        return covariance, False, note

    order_index = {name: idx for idx, name in enumerate(dependence_context.parameter_order)}
    covered = [name for name in param_names if name in order_index]
    if len(covered) < 2:
        note["strategy"] = dependence_context.strategy
        note["covered_params"] = covered
        return covariance, False, note

    indices = [order_index[name] for name in covered]
    corr_sub = dependence_context.correlation_matrix[np.ix_(indices, indices)]
    corr_sub = _stabilize_correlation_matrix(corr_sub)
    local_indices = [param_names.index(name) for name in covered]
    for row_local, row_param in enumerate(local_indices):
        for col_local, col_param in enumerate(local_indices):
            covariance[row_param, col_param] = (
                corr_sub[row_local, col_local] * stds[row_param] * stds[col_param]
            )
    note = {
        "strategy": dependence_context.strategy,
        "covered_params": covered,
        "uncovered_params": [name for name in param_names if name not in covered],
        "correlation_matrix": corr_sub.tolist(),
    }
    return covariance, True, note


def _calibration_lineage_inputs(
    calibration_source: _CalibrationCovarianceSource | None,
    *,
    dependence_ref: DependenceStructureRef | None = None,
    additional_refs: tuple[InputRef, ...] = (),
) -> list[InputRef] | None:
    inputs = list(additional_refs)
    if calibration_source is not None:
        inputs.append(_input_ref(calibration_source.report_ref, role="calibration_report"))
    if dependence_ref is not None:
        inputs.append(_input_ref(dependence_ref, role="dependence_structure"))
    return inputs or None
