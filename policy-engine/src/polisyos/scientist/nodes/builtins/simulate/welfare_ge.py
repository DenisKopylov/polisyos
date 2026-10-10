"""Internal welfare ge implementation helpers."""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping
from typing import Any, Literal

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.ir import ArtifactRefModel, LeontiefIOBundle
from polisyos.ir.analytics import GEUncertaintyBundleRef
from polisyos.ir.analytics.welfare import (
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    load_ge_uncertainty_bundle,
    persist_ge_uncertainty_bundle,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext

from .welfare_types import (
    _DEFAULT_CONDITION_THRESHOLD,
    _DEFAULT_MAX_VERTEX_ENUMERATION,
    _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
    _ERROR_DEPENDENCE_SPEC_INVALID,
    _ERROR_GE_OPERATOR_SINGULAR,
    _ERROR_GE_UNCERTAINTY_REF_KIND,
    _ERROR_INTERVAL_SEMANTICS_INVALID,
    _ERROR_WELFARE_DIMENSION_MISMATCH,
    _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
    _WELFARE_LOAD_ERRORS,
    _WELFARE_VALIDATION_ERRORS,
    _fail_error,
    _load_artifact_json,
    _persist_json_payload,
    _ResolvedGEContext,
)


def _load_ge_uncertainty_inputs(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    size: int,
    ge_entry_map: dict[str, tuple[int, int]],
    diagnostics: dict[str, Any],
) -> tuple[GEUncertaintyBundleRef | None, GEUncertaintyBundle | None, dict[str, tuple[int, int]]]:
    bundle_ref = _coerce_ge_uncertainty_ref(welfare_params.get("ge_uncertainty_ref"))
    if bundle_ref is None:
        return None, None, ge_entry_map
    try:
        bundle = load_ge_uncertainty_bundle(_ensure_ir_artifact_store(ctx.store), bundle_ref)
    except _WELFARE_LOAD_ERRORS as exc:
        raise _fail_error(
            _ERROR_GE_UNCERTAINTY_REF_KIND,
            "Unable to load welfare GE uncertainty bundle",
            details={"error": str(exc)},
        ) from exc
    diagnostics["loaded_ge_uncertainty_representation"] = bundle.representation.value
    if tuple(bundle.multiplier_shape) != (size, size):
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "GE uncertainty bundle dimensions do not match welfare response size",
            details={"multiplier_shape": list(bundle.multiplier_shape), "response_size": size},
        )
    if not ge_entry_map and isinstance(bundle.metadata.get("entry_map"), dict):
        ge_entry_map = _coerce_entry_map(bundle.metadata["entry_map"])
    return bundle_ref, bundle, ge_entry_map


def _resolve_ge_point_source(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    size: int,
    semantics: str,
    bundle: GEUncertaintyBundle | None,
    diagnostics: dict[str, Any],
) -> tuple[np.ndarray | None, np.ndarray | None, str, ArtifactRefModel | None]:
    raw_ge_model_ref = _coerce_artifact_ref(welfare_params.get("ge_model_ref"))
    ge_model_ref = raw_ge_model_ref
    direct_multiplier = _coerce_matrix(welfare_params.get("ge_matrix"))
    direct_coefficients = _coerce_matrix(welfare_params.get("ge_technical_coefficients"))
    if direct_multiplier is not None:
        point = _validate_square_matrix(
            direct_multiplier, expected_size=size, field_name="welfare_ge_matrix"
        )
        source = point
        source_kind = "multiplier"
        if ge_model_ref is None:
            ge_model_ref = _persist_json_payload(
                ctx,
                payload={"matrix": point.tolist()},
                kind="ir.welfare_ge_multiplier_matrix",
                schema_name="ir.welfare_ge_multiplier_matrix",
            )
        return point, source, source_kind, ge_model_ref
    if direct_coefficients is not None:
        source = _validate_square_matrix(
            direct_coefficients,
            expected_size=size,
            field_name="welfare_ge_technical_coefficients",
        )
        point, condition_number = _invert_linear_operator(
            source,
            semantics=semantics,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
        )
        diagnostics["ge_condition_number"] = condition_number
        if ge_model_ref is None:
            ge_model_ref = _persist_json_payload(
                ctx,
                payload={"technical_coefficients": source.tolist()},
                kind="ir.welfare_ge_technical_coefficients",
                schema_name="ir.welfare_ge_technical_coefficients",
            )
        return point, source, "technical_coefficients", ge_model_ref
    if raw_ge_model_ref is not None:
        point, source, source_kind = _load_ge_model_from_ref(
            ctx,
            raw_ge_model_ref,
            semantics=semantics,
            size=size,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
            diagnostics=diagnostics,
        )
        return point, source, source_kind, raw_ge_model_ref
    if bundle is not None and bundle.point_multiplier_ref is not None:
        point = _load_matrix_artifact(
            ctx, bundle.point_multiplier_ref, expected_size=size, field_name="point_multiplier_ref"
        )
        return point, point, "multiplier", bundle.point_multiplier_ref
    return None, None, "none", ge_model_ref


def _resolve_ge_bounds(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    size: int,
    semantics: str,
    bundle: GEUncertaintyBundle | None,
    point_multiplier: np.ndarray | None,
    source_matrix: np.ndarray | None,
    source_kind: str,
    diagnostics: dict[str, Any],
    warnings: list[str],
) -> tuple[
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    np.ndarray | None,
    str,
]:
    lower_multiplier = _coerce_matrix(welfare_params.get("ge_lower_matrix"))
    upper_multiplier = _coerce_matrix(welfare_params.get("ge_upper_matrix"))
    if lower_multiplier is not None or upper_multiplier is not None:
        _validate_matrix_interval(
            lower_multiplier,
            upper_multiplier,
            expected_size=size,
            field_name="welfare_ge_matrix_interval",
        )
    lower_coefficients = _coerce_matrix(welfare_params.get("ge_lower_technical_coefficients"))
    upper_coefficients = _coerce_matrix(welfare_params.get("ge_upper_technical_coefficients"))
    if lower_coefficients is not None or upper_coefficients is not None:
        _validate_matrix_interval(
            lower_coefficients,
            upper_coefficients,
            expected_size=size,
            field_name="welfare_ge_technical_coefficients_interval",
        )
    if bundle is not None and bundle.lower_multiplier_ref is not None:
        lower_multiplier = _load_matrix_artifact(
            ctx, bundle.lower_multiplier_ref, expected_size=size, field_name="lower_multiplier_ref"
        )
        upper_multiplier = _load_matrix_artifact(
            ctx, bundle.upper_multiplier_ref, expected_size=size, field_name="upper_multiplier_ref"
        )
        _validate_matrix_interval(
            lower_multiplier,
            upper_multiplier,
            expected_size=size,
            field_name="ge_uncertainty_bundle.multiplier_interval",
        )
    if lower_coefficients is not None and upper_coefficients is not None:
        derived_lower, derived_upper, vertex_meta = _derive_multiplier_interval_from_coefficients(
            lower_coefficients,
            upper_coefficients,
            semantics=semantics,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
            max_varying_entries=int(
                welfare_params.get("robust_max_vertex_enumeration", _DEFAULT_MAX_VERTEX_ENUMERATION)
            ),
        )
        diagnostics["coefficient_interval_vertex_enumeration"] = vertex_meta
        if derived_lower is not None and derived_upper is not None:
            lower_multiplier = derived_lower
            upper_multiplier = derived_upper
        else:
            warnings.append("ge_coefficient_interval_not_materialized_to_multiplier_bounds")
    if point_multiplier is None and lower_multiplier is not None and upper_multiplier is not None:
        point_multiplier = 0.5 * (lower_multiplier + upper_multiplier)
        source_matrix = point_multiplier
        source_kind = "multiplier"
    if source_matrix is None and lower_coefficients is not None and upper_coefficients is not None:
        source_matrix = 0.5 * (lower_coefficients + upper_coefficients)
        point_multiplier, condition_number = _invert_linear_operator(
            source_matrix,
            semantics=semantics,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
        )
        diagnostics["ge_condition_number"] = condition_number
        source_kind = "technical_coefficients"
    return (
        point_multiplier,
        source_matrix,
        lower_multiplier,
        upper_multiplier,
        lower_coefficients,
        upper_coefficients,
        source_kind,
    )


def _persist_resolved_ge_bundle(
    ctx: ExecutionContext,
    *,
    bundle_ref: GEUncertaintyBundleRef | None,
    point_multiplier: np.ndarray | None,
    lower_multiplier: np.ndarray | None,
    upper_multiplier: np.ndarray | None,
    lower_coefficients: np.ndarray | None,
    upper_coefficients: np.ndarray | None,
    size: int,
    welfare_params: Mapping[str, Any],
    ge_entry_map: dict[str, tuple[int, int]],
    diagnostics: dict[str, Any],
) -> GEUncertaintyBundleRef | None:
    if bundle_ref is not None or (lower_multiplier is None and upper_multiplier is None):
        return bundle_ref
    point_ref = _persist_json_payload(
        ctx,
        payload={"matrix": point_multiplier.tolist()},
        kind="ir.welfare_multiplier_matrix",
        schema_name="ir.welfare_multiplier_matrix",
    )
    lower_ref = _persist_json_payload(
        ctx,
        payload={"matrix": lower_multiplier.tolist()},
        kind="ir.welfare_multiplier_matrix",
        schema_name="ir.welfare_multiplier_matrix",
    )
    upper_ref = _persist_json_payload(
        ctx,
        payload={"matrix": upper_multiplier.tolist()},
        kind="ir.welfare_multiplier_matrix",
        schema_name="ir.welfare_multiplier_matrix",
    )
    return persist_ge_uncertainty_bundle(
        _ensure_ir_artifact_store(ctx.store),
        GEUncertaintyBundle(
            model_class=str(welfare_params.get("model_class") or "linearized_ge_io"),
            representation=(
                GEUncertaintyRepresentation.COEFFICIENT_INTERVALS
                if lower_coefficients is not None or upper_coefficients is not None
                else GEUncertaintyRepresentation.MULTIPLIER_INTERVALS
            ),
            multiplier_shape=(size, size),
            point_multiplier_ref=ArtifactRefModel.model_validate(
                point_ref.model_dump(mode="python")
            ),
            lower_multiplier_ref=ArtifactRefModel.model_validate(
                lower_ref.model_dump(mode="python")
            ),
            upper_multiplier_ref=ArtifactRefModel.model_validate(
                upper_ref.model_dump(mode="python")
            ),
            diagnostics=diagnostics,
            metadata={"entry_map": {key: list(value) for key, value in ge_entry_map.items()}},
        ),
    )


def _resolve_ge_context(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    size: int,
    ge_multiplier_semantics: str,
) -> _ResolvedGEContext:
    warnings: list[str] = []
    diagnostics: dict[str, Any] = {}
    ge_entry_map = _coerce_entry_map(welfare_params.get("ge_entry_map"))
    _validate_entry_map(ge_entry_map, size=size)
    bundle_ref, ge_bundle, ge_entry_map = _load_ge_uncertainty_inputs(
        ctx,
        welfare_params=welfare_params,
        size=size,
        ge_entry_map=ge_entry_map,
        diagnostics=diagnostics,
    )
    point_multiplier, source_matrix, source_kind, ge_model_ref = _resolve_ge_point_source(
        ctx,
        welfare_params=welfare_params,
        size=size,
        semantics=ge_multiplier_semantics,
        bundle=ge_bundle,
        diagnostics=diagnostics,
    )
    (
        point_multiplier,
        source_matrix,
        lower_multiplier,
        upper_multiplier,
        lower_coefficients,
        upper_coefficients,
        source_kind,
    ) = _resolve_ge_bounds(
        ctx,
        welfare_params=welfare_params,
        size=size,
        semantics=ge_multiplier_semantics,
        bundle=ge_bundle,
        point_multiplier=point_multiplier,
        source_matrix=source_matrix,
        source_kind=source_kind,
        diagnostics=diagnostics,
        warnings=warnings,
    )
    if source_matrix is None and point_multiplier is None:
        return _ResolvedGEContext(
            source_kind="none",
            point_multiplier=None,
            source_matrix=None,
            lower_multiplier=None,
            upper_multiplier=None,
            ge_model_ref=None,
            ge_uncertainty_ref=None,
            ge_entry_map={},
            diagnostics=diagnostics,
            warnings=tuple(warnings),
        )
    if (
        lower_multiplier is None
        and upper_multiplier is None
        and source_kind == "multiplier"
        and ge_entry_map
    ):
        lower_multiplier = np.array(point_multiplier, copy=True)
        upper_multiplier = np.array(point_multiplier, copy=True)
    created_bundle_ref = _persist_resolved_ge_bundle(
        ctx,
        bundle_ref=bundle_ref,
        point_multiplier=point_multiplier,
        lower_multiplier=lower_multiplier,
        upper_multiplier=upper_multiplier,
        lower_coefficients=lower_coefficients,
        upper_coefficients=upper_coefficients,
        size=size,
        welfare_params=welfare_params,
        ge_entry_map=ge_entry_map,
        diagnostics=diagnostics,
    )
    if source_kind == "multiplier" and point_multiplier is not None:
        diagnostics["ge_point_multiplier_condition_number"] = float(
            np.linalg.cond(point_multiplier)
        )
    return _ResolvedGEContext(
        source_kind=source_kind,
        point_multiplier=point_multiplier,
        source_matrix=source_matrix,
        lower_multiplier=lower_multiplier,
        upper_multiplier=upper_multiplier,
        ge_model_ref=ge_model_ref,
        ge_uncertainty_ref=created_bundle_ref,
        ge_entry_map=ge_entry_map,
        diagnostics=diagnostics,
        warnings=tuple(warnings),
    )


def _coerce_artifact_ref(value: Any) -> ArtifactRefModel | None:
    if value is None:
        return None
    if isinstance(value, ArtifactRefModel):
        return value
    if isinstance(value, dict):
        return ArtifactRefModel.model_validate(value)
    return None


def _coerce_ge_uncertainty_ref(value: Any) -> GEUncertaintyBundleRef | None:
    if value is None:
        return None
    try:
        return GEUncertaintyBundleRef.model_validate(value)
    except _WELFARE_VALIDATION_ERRORS as exc:
        raise _fail_error(
            _ERROR_GE_UNCERTAINTY_REF_KIND,
            "Invalid welfare ge_uncertainty_ref",
            details={"error": str(exc)},
        ) from exc


def _coerce_str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        return None
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        out.append(item)
    return out or None


def _coerce_numeric_sequence(value: Any, *, field_name: str) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"{field_name} must be a list of finite numbers",
        )
    try:
        numeric = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"{field_name} must be a list of finite numbers",
            details={"error": str(exc)},
        ) from exc
    if not all(math.isfinite(item) for item in numeric):
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"{field_name} must contain only finite numbers",
        )
    return numeric


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "ok", "pass"}:
            return True
        if normalized in {"false", "0", "no", "n", "fail"}:
            return False
    return bool(value)


def _coerce_matrix(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "Expected a 2D matrix payload",
        )
    return matrix


def _coerce_dependence_matrix(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise _fail_error(
            _ERROR_DEPENDENCE_SPEC_INVALID,
            "Dependence structure matrix must be square",
        )
    if not np.all(np.isfinite(matrix)):
        raise _fail_error(
            _ERROR_DEPENDENCE_SPEC_INVALID,
            "Dependence structure matrix must be finite",
        )
    return matrix


def _correlation_from_covariance(covariance: np.ndarray) -> np.ndarray:
    scale = np.sqrt(np.clip(np.diag(covariance), a_min=1e-12, a_max=None))
    correlation = covariance / np.outer(scale, scale)
    return _stabilize_correlation_matrix(correlation)


def _stabilize_correlation_matrix(matrix: np.ndarray) -> np.ndarray:
    symmetric = 0.5 * (matrix + matrix.T)
    np.fill_diagonal(symmetric, 1.0)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    clipped = np.clip(eigenvalues, a_min=1e-8, a_max=None)
    repaired = (eigenvectors * clipped) @ eigenvectors.T
    scale = np.sqrt(np.clip(np.diag(repaired), a_min=1e-12, a_max=None))
    correlation = repaired / np.outer(scale, scale)
    correlation = np.clip(correlation, -1.0, 1.0)
    np.fill_diagonal(correlation, 1.0)
    return correlation


def _coerce_entry_map(value: Any) -> dict[str, tuple[int, int]]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, tuple[int, int]] = {}
    for param_name, coords in value.items():
        if not isinstance(param_name, str) or not param_name.strip():
            continue
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            continue
        try:
            row_idx = int(coords[0])
            col_idx = int(coords[1])
        except (TypeError, ValueError):
            continue
        out[param_name] = (row_idx, col_idx)
    return out


def _validate_entry_map(entry_map: Mapping[str, tuple[int, int]], *, size: int) -> None:
    for param_name, (row_idx, col_idx) in entry_map.items():
        if row_idx < 0 or row_idx >= size or col_idx < 0 or col_idx >= size:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_ge_entry_map coordinates must lie within the GE matrix",
                details={"param_name": param_name, "row": row_idx, "col": col_idx, "size": size},
            )


def _validate_square_matrix(
    matrix: np.ndarray,
    *,
    expected_size: int,
    field_name: str,
) -> np.ndarray:
    if matrix.shape != (expected_size, expected_size):
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            f"{field_name} must be square and align with welfare response size",
            details={"shape": list(matrix.shape), "expected_size": expected_size},
        )
    return matrix


def _validate_matrix_interval(
    lower: np.ndarray | None,
    upper: np.ndarray | None,
    *,
    expected_size: int,
    field_name: str,
) -> None:
    if lower is None or upper is None:
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            f"{field_name} requires both lower and upper matrices",
        )
    _validate_square_matrix(lower, expected_size=expected_size, field_name=f"{field_name}.lower")
    _validate_square_matrix(upper, expected_size=expected_size, field_name=f"{field_name}.upper")
    if np.any(lower > upper):
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            f"{field_name} must satisfy elementwise lower <= upper",
        )


def _invert_linear_operator(
    matrix: np.ndarray,
    *,
    semantics: str,
    condition_threshold: float,
) -> tuple[np.ndarray, float]:
    if semantics == "leontief_inverse":
        operator = np.eye(matrix.shape[0], dtype=np.float64) - matrix
    elif semantics == "jacobian_inverse":
        operator = np.asarray(matrix, dtype=np.float64)
    else:
        return np.asarray(matrix, dtype=np.float64), float(np.linalg.cond(matrix))

    try:
        condition_number = float(np.linalg.cond(operator))
    except np.linalg.LinAlgError as exc:
        raise _fail_error(
            _ERROR_GE_OPERATOR_SINGULAR,
            "Unable to compute GE operator condition number",
            details={"error": str(exc)},
        ) from exc
    if not math.isfinite(condition_number) or condition_number > condition_threshold:
        raise _fail_error(
            _ERROR_GE_OPERATOR_SINGULAR,
            "GE operator is singular or ill-conditioned",
            details={"condition_number": condition_number, "threshold": condition_threshold},
        )
    try:
        inverse = np.linalg.inv(operator)
    except np.linalg.LinAlgError as exc:
        raise _fail_error(
            _ERROR_GE_OPERATOR_SINGULAR,
            "GE operator inversion failed",
            details={"error": str(exc)},
        ) from exc
    return np.asarray(inverse, dtype=np.float64), condition_number


def _invert_sampled_ge_operator(
    coefficients: np.ndarray,
    *,
    condition_threshold: float,
    sample_domain_error_factory: Any,
) -> np.ndarray:
    """Invert a sampled GE coefficient matrix or declare its configured domain limit."""
    operator = np.eye(coefficients.shape[0], dtype=np.float64) - coefficients
    condition_number = float(np.linalg.cond(operator))
    if not math.isfinite(condition_number) or condition_number > condition_threshold:
        raise sample_domain_error_factory(
            "Sampled GE operator exceeds its configured condition-number threshold",
            predicate_id="welfare.ge_operator.condition_number_within_threshold",
        )
    return np.asarray(np.linalg.inv(operator), dtype=np.float64)


def _load_ge_model_from_ref(
    ctx: ExecutionContext,
    ref: ArtifactRefModel,
    *,
    semantics: str,
    size: int,
    condition_threshold: float,
    diagnostics: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, Literal["multiplier", "technical_coefficients"]]:
    payload = _load_artifact_json(ctx, ref)
    if isinstance(payload, dict):
        if "technical_coefficients" in payload:
            matrix = _validate_square_matrix(
                np.asarray(payload["technical_coefficients"], dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.technical_coefficients",
            )
            multiplier, condition_number = _invert_linear_operator(
                matrix,
                semantics=semantics,
                condition_threshold=condition_threshold,
            )
            diagnostics["ge_condition_number"] = condition_number
            return multiplier, matrix, "technical_coefficients"
        if "matrix" in payload:
            matrix = _validate_square_matrix(
                np.asarray(payload["matrix"], dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.matrix",
            )
            return matrix, matrix, "multiplier"
        if "leontief_inverse" in payload:
            matrix = _validate_square_matrix(
                np.asarray(payload["leontief_inverse"], dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.leontief_inverse",
            )
            return matrix, matrix, "multiplier"
        try:
            bundle = LeontiefIOBundle.model_validate(payload)
        except ValidationError:
            bundle = None
        if bundle is not None:
            coefficients = _validate_square_matrix(
                np.asarray(bundle.technical_coefficients, dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.leontief_io_bundle",
            )
            multiplier, condition_number = _invert_linear_operator(
                coefficients,
                semantics=semantics,
                condition_threshold=condition_threshold,
            )
            diagnostics["ge_condition_number"] = condition_number
            return multiplier, coefficients, "technical_coefficients"
    raise _fail_error(
        _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
        "Unsupported ge_model_ref payload for welfare propagation",
        details={"kind": ref.kind},
    )


def _load_matrix_artifact(
    ctx: ExecutionContext,
    ref: ArtifactRefModel,
    *,
    expected_size: int,
    field_name: str,
) -> np.ndarray:
    payload = _load_artifact_json(ctx, ref)
    if isinstance(payload, dict):
        if "matrix" in payload:
            return _validate_square_matrix(
                np.asarray(payload["matrix"], dtype=np.float64),
                expected_size=expected_size,
                field_name=field_name,
            )
        if "leontief_inverse" in payload:
            return _validate_square_matrix(
                np.asarray(payload["leontief_inverse"], dtype=np.float64),
                expected_size=expected_size,
                field_name=field_name,
            )
    return _validate_square_matrix(
        np.asarray(payload, dtype=np.float64),
        expected_size=expected_size,
        field_name=field_name,
    )


def _derive_multiplier_interval_from_coefficients(
    lower_coefficients: np.ndarray,
    upper_coefficients: np.ndarray,
    *,
    semantics: str,
    condition_threshold: float,
    max_varying_entries: int,
) -> tuple[np.ndarray | None, np.ndarray | None, dict[str, Any]]:
    varying = list(zip(*np.where(np.abs(lower_coefficients - upper_coefficients) > 0.0)))
    if len(varying) > max_varying_entries:
        return None, None, {"varying_entries": len(varying), "status": "skipped"}

    lower_bound: np.ndarray | None = None
    upper_bound: np.ndarray | None = None
    for selector in itertools.product((0, 1), repeat=len(varying)):
        candidate = np.array(lower_coefficients, copy=True)
        for choice, (row_idx, col_idx) in zip(selector, varying, strict=False):
            candidate[row_idx, col_idx] = (
                upper_coefficients[row_idx, col_idx]
                if choice
                else lower_coefficients[row_idx, col_idx]
            )
        multiplier, _ = _invert_linear_operator(
            candidate,
            semantics=semantics,
            condition_threshold=condition_threshold,
        )
        if lower_bound is None:
            lower_bound = multiplier
            upper_bound = multiplier
            continue
        lower_bound = np.minimum(lower_bound, multiplier)
        upper_bound = np.maximum(upper_bound, multiplier)
    return (
        lower_bound,
        upper_bound,
        {
            "varying_entries": len(varying),
            "status": "ok",
            "corner_count": 2 ** len(varying),
        },
    )
