"""Run calibrated distribution-shift diagnostics for Phase-5 prediction readiness."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import erf, exp, sqrt
from types import SimpleNamespace
from typing import Any, ClassVar, Literal, cast

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.ir.analytics.shift_diagnostics import (
    CalibrationInfo,
    DetectorFamily,
    DetectorResult,
    FeatureShiftDiagnostic,
    LabelAvailability,
    OperatingCharacteristicKey,
    ReadinessBand,
    ReferenceComparisonType,
    SeverityBucket,
    ShiftComponent,
    ShiftDiagnosticReport,
    ShiftGlobalVerdict,
    ShiftModality,
    ShiftStatus,
    TaskType,
    build_readiness_impact,
    readiness_downgrade,
)

FeatureType = Literal["numeric", "categorical", "binary", "text", "embedding"]
ReportMode = Literal["single", "all_reference_comparisons"]

_REFERENCE_COMPARISONS: tuple[ReferenceComparisonType, ...] = (
    "training_vs_current",
    "validation_vs_current",
    "stable_recent_vs_current",
    "seasonal_historical_vs_current",
)
_COMPONENT_ORDER: tuple[SeverityBucket, ...] = (
    "none",
    "low",
    "moderate",
    "high",
    "severe",
    "unassessable",
)


class ShiftDiagnosticInput(BaseModel):
    """Reference/current windows consumed by the shift-diagnostic ensemble."""

    contract_id: ClassVar[str] = "foundry.ml.shift_diagnostic_input.v1"
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    reference_features: Any
    current_features: Any
    feature_names: tuple[str, ...] | None = None
    feature_types: tuple[FeatureType, ...] | None = None
    reference_predictions: Any | None = None
    current_predictions: Any | None = None
    reference_target: Any | None = None
    current_target: Any | None = None
    reference_sample_weight: Any | None = None
    current_sample_weight: Any | None = None
    reference_schema: dict[str, Any] | None = None
    current_schema: dict[str, Any] | None = None
    reference_subgroups: dict[str, Any] = Field(default_factory=dict)
    current_subgroups: dict[str, Any] = Field(default_factory=dict)
    reference_windows: dict[ReferenceComparisonType, dict[str, Any]] = Field(default_factory=dict)

    prediction_result_id: str | None = None
    model_id: str = "unknown-model"
    model_version: str = "unknown-version"
    task_type: TaskType = "classification"
    modality: ShiftModality = "tabular_administrative"
    training_reference_id: str = "training-reference"
    validation_reference_id: str | None = None
    current_window_id: str = "current-window"
    current_window_start: str = "unknown"
    current_window_end: str = "unknown"
    label_availability: LabelAvailability = "none"
    label_lag_days: int | None = Field(default=None, ge=0)
    base_readiness: ReadinessBand = "ready"
    decision_context: Literal["standard", "high_stakes"] = "standard"
    reference_comparison_type: ReferenceComparisonType = "training_vs_current"
    windowing_strategy: str = "calendar_window"
    null_regime: str = "historical_stable_window"
    calibration_version: str = "phase5_shift_diagnostic_v1"
    generated_at: str | None = None
    report_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "reference_features",
        "current_features",
        "reference_predictions",
        "current_predictions",
        "reference_target",
        "current_target",
        "reference_sample_weight",
        "current_sample_weight",
        mode="before",
    )
    @classmethod
    def _coerce_array(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value)

    @model_validator(mode="after")
    def _validate_shapes(self) -> ShiftDiagnosticInput:
        reference = _as_2d_object(self.reference_features, "reference_features")
        current = _as_2d_object(self.current_features, "current_features")
        if reference.shape[1] != current.shape[1]:
            raise ValueError("reference/current feature counts must match")
        if reference.shape[0] < 4 or current.shape[0] < 4:
            raise ValueError("shift diagnostics require at least 4 rows per window")
        if self.feature_names is not None and len(self.feature_names) != reference.shape[1]:
            raise ValueError("feature_names length must match feature columns")
        if self.feature_types is not None and len(self.feature_types) != reference.shape[1]:
            raise ValueError("feature_types length must match feature columns")
        for name, value, n_rows in (
            ("reference_predictions", self.reference_predictions, reference.shape[0]),
            ("current_predictions", self.current_predictions, current.shape[0]),
            ("reference_target", self.reference_target, reference.shape[0]),
            ("current_target", self.current_target, current.shape[0]),
            ("reference_sample_weight", self.reference_sample_weight, reference.shape[0]),
            ("current_sample_weight", self.current_sample_weight, current.shape[0]),
        ):
            if value is not None and np.asarray(value).shape[0] != n_rows:
                raise ValueError(f"{name} length must match its feature rows")
        _validate_group_lengths(self.reference_subgroups, reference.shape[0], "reference_subgroups")
        _validate_group_lengths(self.current_subgroups, current.shape[0], "current_subgroups")
        return self

    @field_serializer(
        "reference_features",
        "current_features",
        "reference_predictions",
        "current_predictions",
        "reference_target",
        "current_target",
        "reference_sample_weight",
        "current_sample_weight",
        mode="plain",
        when_used="json",
    )
    def _serialize_array(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


@dataclass(frozen=True)
class FeatureEvidence:
    name: str
    feature_type: FeatureType
    statistic: float
    p_value: float
    q_value: float
    effect_size: float
    severity_score: float
    direction_summary: str
    examples: tuple[str, ...]
    model_relevance: float | None = None


@dataclass(frozen=True)
class C2STEvidence:
    auc: float
    p_value: float
    severity_score: float
    feature_importance: dict[str, float]
    reference_density_ratio: np.ndarray | None


@dataclass(frozen=True)
class SupportEvidence:
    out_of_support_fraction: float
    rare_combination_rate: float
    effective_sample_size_ratio: float | None
    max_density_ratio: float | None
    severity_score: float


def _validate_group_lengths(groups: Mapping[str, Any], n_rows: int, field_name: str) -> None:
    for key, value in groups.items():
        if np.asarray(value).shape[0] != n_rows:
            raise ValueError(f"{field_name}.{key} length must match feature rows")


def _as_2d_object(value: Any, field_name: str) -> np.ndarray:
    array = np.asarray(value, dtype=object)
    if array.ndim != 2:
        raise ValueError(f"{field_name} must be a 2D array")
    return array


def _as_optional_vector(value: Any, field_name: str) -> np.ndarray | None:
    if value is None:
        return None
    array = np.asarray(value)
    if array.ndim != 1:
        raise ValueError(f"{field_name} must be a 1D array")
    return array


def _feature_names(data: ShiftDiagnosticInput) -> tuple[str, ...]:
    if data.feature_names is not None:
        return tuple(data.feature_names)
    n_features = _as_2d_object(data.reference_features, "reference_features").shape[1]
    return tuple(f"x{i}" for i in range(n_features))


def _infer_feature_types(data: ShiftDiagnosticInput) -> tuple[FeatureType, ...]:
    if data.feature_types is not None:
        return tuple(data.feature_types)
    reference = _as_2d_object(data.reference_features, "reference_features")
    inferred: list[FeatureType] = []
    for j in range(reference.shape[1]):
        numeric = _numeric_column(reference[:, j])
        finite = numeric[np.isfinite(numeric)]
        if finite.size == reference.shape[0]:
            unique = np.unique(finite)
            inferred.append("binary" if unique.size <= 2 else "numeric")
        else:
            inferred.append("categorical")
    return tuple(inferred)


def _numeric_column(values: Sequence[Any] | np.ndarray) -> np.ndarray:
    try:
        return np.asarray(values, dtype=float)
    except (TypeError, ValueError):
        result = np.full(np.asarray(values, dtype=object).shape[0], np.nan, dtype=float)
        for idx, value in enumerate(np.asarray(values, dtype=object)):
            if value is None:
                continue
            try:
                result[idx] = float(value)
            except (TypeError, ValueError):
                result[idx] = np.nan
        return result


def _missing_mask(values: np.ndarray) -> np.ndarray:
    mask = np.zeros(values.shape[0], dtype=bool)
    for idx, value in enumerate(values):
        if value is None:
            mask[idx] = True
            continue
        if isinstance(value, float) and np.isnan(value):
            mask[idx] = True
            continue
        if str(value).strip().lower() in {"", "nan", "none", "null"}:
            mask[idx] = True
    return mask


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(result):
        return default
    return result


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _normal_two_sided_p(z_value: float) -> float:
    cdf = 0.5 * (1.0 + erf(abs(z_value) / sqrt(2.0)))
    return _clip01(2.0 * (1.0 - cdf))


def _ks_test(reference: np.ndarray, current: np.ndarray) -> tuple[float, float]:
    ref = reference[np.isfinite(reference)]
    cur = current[np.isfinite(current)]
    if ref.size == 0 or cur.size == 0:
        return 0.0, 1.0
    try:
        from scipy.stats import ks_2samp

        result = ks_2samp(ref, cur, alternative="two-sided", mode="auto")
        return float(result.statistic), _clip01(float(result.pvalue))
    except Exception:
        combined = np.sort(np.unique(np.concatenate([ref, cur])))
        ref_cdf = np.searchsorted(np.sort(ref), combined, side="right") / ref.size
        cur_cdf = np.searchsorted(np.sort(cur), combined, side="right") / cur.size
        statistic = float(np.max(np.abs(ref_cdf - cur_cdf))) if combined.size else 0.0
        effective_n = ref.size * cur.size / (ref.size + cur.size)
        p_value = 2.0 * exp(-2.0 * effective_n * statistic * statistic)
        return statistic, _clip01(p_value)


def _categorical_test(reference: np.ndarray, current: np.ndarray) -> tuple[float, float, float]:
    ref_values = np.asarray([_category_key(value) for value in reference], dtype=object)
    cur_values = np.asarray([_category_key(value) for value in current], dtype=object)
    categories = tuple(dict.fromkeys([*ref_values.tolist(), *cur_values.tolist()]))
    if not categories:
        return 0.0, 1.0, 0.0
    ref_counts = np.asarray([np.sum(ref_values == cat) for cat in categories], dtype=float)
    cur_counts = np.asarray([np.sum(cur_values == cat) for cat in categories], dtype=float)
    ref_dist = ref_counts / max(float(np.sum(ref_counts)), 1.0)
    cur_dist = cur_counts / max(float(np.sum(cur_counts)), 1.0)
    total_variation = float(0.5 * np.sum(np.abs(ref_dist - cur_dist)))
    table = np.vstack([ref_counts, cur_counts])
    try:
        from scipy.stats import chi2_contingency

        statistic, p_value, _, _ = chi2_contingency(table, correction=False)
        return float(statistic), _clip01(float(p_value)), total_variation
    except Exception:
        grand = float(np.sum(table))
        row_totals = np.sum(table, axis=1, keepdims=True)
        col_totals = np.sum(table, axis=0, keepdims=True)
        expected = row_totals @ col_totals / max(grand, 1.0)
        valid = expected > 0.0
        statistic = float(np.sum(((table - expected) ** 2)[valid] / expected[valid]))
        p_value = exp(-0.5 * statistic)
        return statistic, _clip01(p_value), total_variation


def _category_key(value: Any) -> str:
    if value is None:
        return "<missing>"
    if isinstance(value, float) and np.isnan(value):
        return "<missing>"
    text = str(value).strip()
    return text if text else "<missing>"


def _benjamini_hochberg(p_values: Sequence[float]) -> tuple[float, ...]:
    if not p_values:
        return ()
    p = np.asarray([_clip01(float(value)) for value in p_values], dtype=float)
    order = np.argsort(p)
    ranks = np.arange(1, p.size + 1, dtype=float)
    sorted_q = np.minimum.accumulate((p[order] * p.size / ranks)[::-1])[::-1]
    q = np.empty_like(sorted_q)
    q[order] = np.clip(sorted_q, 0.0, 1.0)
    return tuple(float(value) for value in q)


def _severity_bucket(score: float | None) -> SeverityBucket:
    if score is None:
        return "unassessable"
    value = _clip01(score)
    if value < 0.10:
        return "none"
    if value < 0.30:
        return "low"
    if value < 0.55:
        return "moderate"
    if value < 0.80:
        return "high"
    return "severe"


def _detected_status(bucket: SeverityBucket) -> ShiftStatus:
    if bucket in {"high", "severe", "moderate"}:
        return "detected"
    return "not_detected"


def _score_from_p_effect(p_value: float, effect_size: float, effect_scale: float) -> float:
    p_signal = _clip01((0.05 - p_value) / 0.05) if p_value > 1e-6 else 1.0
    effect_signal = _clip01(abs(effect_size) / max(effect_scale, 1e-12))
    return _clip01(0.35 * p_signal + 0.65 * effect_signal)


def _weighted_effective_n(weights: np.ndarray | None, n_rows: int) -> float:
    if weights is None:
        return float(n_rows)
    finite = np.asarray(weights, dtype=float)
    finite = finite[np.isfinite(finite) & (finite > 0.0)]
    if finite.size == 0:
        return 0.0
    return float(np.sum(finite) ** 2 / max(float(np.sum(finite**2)), 1e-12))


def _schema_detector(
    data: ShiftDiagnosticInput,
    key: str,
) -> tuple[ShiftComponent, DetectorResult, tuple[str, ...]]:
    limitations: list[str] = []
    ref_schema = dict(data.reference_schema or {})
    cur_schema = dict(data.current_schema or {})
    ref_fields = tuple(ref_schema.get("fields") or _feature_names(data))
    cur_fields = tuple(cur_schema.get("fields") or _feature_names(data))
    missing = tuple(field for field in ref_fields if field not in cur_fields)
    new = tuple(field for field in cur_fields if field not in ref_fields)
    incompatible: list[str] = []
    for field in set(ref_schema.get("types", {})) & set(cur_schema.get("types", {})):
        if ref_schema["types"][field] != cur_schema["types"][field]:
            incompatible.append(field)
    for field in set(ref_schema.get("units", {})) & set(cur_schema.get("units", {})):
        if ref_schema["units"][field] != cur_schema["units"][field]:
            incompatible.append(field)

    score = 0.0
    if missing or incompatible:
        score = 0.95
    elif new:
        score = 0.45
        limitations.append("schema_has_new_fields_allowed_pending_contract_review")
    bucket = _severity_bucket(score)
    component = ShiftComponent(
        status=_detected_status(bucket),
        severity_score=score,
        severity_bucket=bucket,
        effect_size=float(len(missing) + len(new) + len(set(incompatible))),
        notes=tuple(
            note
            for note in (
                f"missing_fields={list(missing)}" if missing else "",
                f"new_fields={list(new)}" if new else "",
                f"incompatible_fields={sorted(set(incompatible))}" if incompatible else "",
            )
            if note
        ),
    )
    detector = DetectorResult(
        detector_name="schema_contract_check",
        detector_family="schema",
        data_view="input_schema",
        statistic=component.effect_size,
        effect_size=component.effect_size,
        null_percentile=score,
        calibrated_threshold=0.80,
        operating_characteristic_key=key,
        implicated_features=tuple(dict.fromkeys([*missing, *new, *incompatible])),
        limitations=tuple(limitations),
    )
    return component, detector, tuple(limitations)


def _univariate_detectors(
    data: ShiftDiagnosticInput,
    key: str,
    alpha: float,
    model_relevance: Mapping[str, float],
) -> tuple[ShiftComponent, tuple[DetectorResult, ...], tuple[FeatureShiftDiagnostic, ...]]:
    reference = _as_2d_object(data.reference_features, "reference_features")
    current = _as_2d_object(data.current_features, "current_features")
    names = _feature_names(data)
    types = _infer_feature_types(data)
    raw: list[tuple[str, FeatureType, float, float, float, str, tuple[str, ...]]] = []
    missing_raw: list[tuple[str, FeatureType, float, float, float, str, tuple[str, ...]]] = []

    for idx, (name, feature_type) in enumerate(zip(names, types, strict=True)):
        ref_col = reference[:, idx]
        cur_col = current[:, idx]
        if feature_type in {"numeric", "embedding"}:
            ref_numeric = _numeric_column(ref_col)
            cur_numeric = _numeric_column(cur_col)
            statistic, p_value = _ks_test(ref_numeric, cur_numeric)
            ref_mean = float(np.nanmean(ref_numeric)) if np.isfinite(ref_numeric).any() else 0.0
            cur_mean = float(np.nanmean(cur_numeric)) if np.isfinite(cur_numeric).any() else 0.0
            pooled = float(np.nanstd(np.concatenate([ref_numeric, cur_numeric])))
            effect = abs(cur_mean - ref_mean) / max(pooled, 1e-9)
            direction = f"mean {ref_mean:.4g} -> {cur_mean:.4g}"
            examples = ()
        else:
            statistic, p_value, effect = _categorical_test(ref_col, cur_col)
            ref_mode = _mode_label(ref_col)
            cur_mode = _mode_label(cur_col)
            direction = f"mode {ref_mode} -> {cur_mode}"
            examples = _top_category_changes(ref_col, cur_col)
        raw.append((name, feature_type, statistic, p_value, effect, direction, examples))

        ref_missing = _missing_mask(ref_col).astype(float)
        cur_missing = _missing_mask(cur_col).astype(float)
        missing_delta = abs(float(np.mean(cur_missing) - np.mean(ref_missing)))
        if missing_delta > 0.0:
            statistic, p_value, _ = _categorical_test(ref_missing, cur_missing)
            missing_raw.append(
                (
                    f"{name}__missingness",
                    "binary",
                    statistic,
                    p_value,
                    missing_delta,
                    f"missingness {np.mean(ref_missing):.3f} -> {np.mean(cur_missing):.3f}",
                    (),
                )
            )

    q_values = _benjamini_hochberg([item[3] for item in raw + missing_raw])
    evidence: list[FeatureEvidence] = []
    for item, q_value in zip(raw + missing_raw, q_values, strict=True):
        name, feature_type, statistic, p_value, effect, direction, examples = item
        relevance = model_relevance.get(name.replace("__missingness", ""))
        score = _score_from_p_effect(q_value, effect, 0.35 if feature_type == "binary" else 0.50)
        if relevance is not None:
            score = _clip01(score * (0.75 + 0.50 * _clip01(float(relevance))))
        evidence.append(
            FeatureEvidence(
                name=name,
                feature_type=feature_type,
                statistic=statistic,
                p_value=p_value,
                q_value=q_value,
                effect_size=effect,
                severity_score=score,
                direction_summary=direction,
                examples=examples,
                model_relevance=None if relevance is None else _clip01(float(relevance)),
            )
        )

    shifted = [item for item in evidence if item.q_value <= alpha or item.severity_score >= 0.30]
    feature_burden = len(shifted) / max(len(evidence), 1)
    top_score = max((item.severity_score for item in evidence), default=0.0)
    component_score = _clip01(0.70 * top_score + 0.30 * feature_burden)
    bucket = _severity_bucket(component_score)
    min_q = min((item.q_value for item in evidence), default=None)
    component = ShiftComponent(
        status=_detected_status(bucket),
        severity_score=component_score,
        severity_bucket=bucket,
        q_value=min_q,
        effect_size=feature_burden,
        power=0.80 if reference.shape[0] >= 100 and current.shape[0] >= 100 else 0.45,
        notes=(
            f"{len(shifted)} of {len(evidence)} feature or missingness diagnostics shifted",
            "feature-wise q-values use benjamini_hochberg",
        ),
    )
    detector = DetectorResult(
        detector_name="feature_wise_marginal_tests",
        detector_family="univariate",
        data_view="raw_features_and_missingness",
        statistic=float(len(shifted)),
        q_value=min_q,
        effect_size=feature_burden,
        null_percentile=component_score,
        calibrated_threshold=0.30,
        operating_characteristic_key=key,
        implicated_features=tuple(item.name for item in shifted[:12]),
        limitations=("misses_dependence_shift_without_multivariate_layers",),
    )
    features = tuple(
        FeatureShiftDiagnostic(
            feature_name=item.name,
            feature_type=cast(
                "Literal['numeric', 'categorical', 'binary', 'text', 'embedding', 'missingness_indicator']",
                "missingness_indicator" if item.name.endswith("__missingness") else item.feature_type,
            ),
            severity_score=item.severity_score,
            q_value=item.q_value,
            effect_size=item.effect_size,
            model_relevance=item.model_relevance,
            direction_summary=item.direction_summary,
            example_changes=item.examples,
        )
        for item in sorted(evidence, key=lambda value: value.severity_score, reverse=True)[:12]
        if item.severity_score >= 0.10
    )
    return component, (detector,), features


def _mode_label(values: np.ndarray) -> str:
    counts: dict[str, int] = {}
    for value in values:
        key = _category_key(value)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return "<none>"
    return max(counts.items(), key=lambda item: item[1])[0]


def _top_category_changes(reference: np.ndarray, current: np.ndarray) -> tuple[str, ...]:
    ref_keys = np.asarray([_category_key(value) for value in reference], dtype=object)
    cur_keys = np.asarray([_category_key(value) for value in current], dtype=object)
    categories = tuple(dict.fromkeys([*ref_keys.tolist(), *cur_keys.tolist()]))
    changes: list[tuple[float, str]] = []
    for category in categories:
        ref_share = float(np.mean(ref_keys == category))
        cur_share = float(np.mean(cur_keys == category))
        delta = cur_share - ref_share
        if abs(delta) >= 0.02:
            changes.append((abs(delta), f"{category}: {ref_share:.3f}->{cur_share:.3f}"))
    return tuple(item[1] for item in sorted(changes, reverse=True)[:4])


def _encoded_matrix(data: ShiftDiagnosticInput) -> tuple[np.ndarray, np.ndarray]:
    reference = _as_2d_object(data.reference_features, "reference_features")
    current = _as_2d_object(data.current_features, "current_features")
    types = _infer_feature_types(data)
    ref_cols: list[np.ndarray] = []
    cur_cols: list[np.ndarray] = []
    for idx, feature_type in enumerate(types):
        ref_col = reference[:, idx]
        cur_col = current[:, idx]
        if feature_type in {"numeric", "binary", "embedding"}:
            ref_num = _numeric_column(ref_col)
            cur_num = _numeric_column(cur_col)
            combined = np.concatenate([ref_num, cur_num])
            finite = combined[np.isfinite(combined)]
            fill = float(np.median(finite)) if finite.size else 0.0
            ref_filled = np.where(np.isfinite(ref_num), ref_num, fill)
            cur_filled = np.where(np.isfinite(cur_num), cur_num, fill)
            scale = float(np.std(np.concatenate([ref_filled, cur_filled])))
            if scale <= 1e-9:
                scale = 1.0
            center = float(np.mean(np.concatenate([ref_filled, cur_filled])))
            ref_cols.append(((ref_filled - center) / scale)[:, None])
            cur_cols.append(((cur_filled - center) / scale)[:, None])
        else:
            ref_keys = np.asarray([_category_key(value) for value in ref_col], dtype=object)
            cur_keys = np.asarray([_category_key(value) for value in cur_col], dtype=object)
            ref_counts = {key: int(np.sum(ref_keys == key)) for key in np.unique(ref_keys)}
            ref_total = max(float(ref_keys.size), 1.0)
            encoded_ref = np.asarray([ref_counts.get(key, 0) / ref_total for key in ref_keys])
            encoded_cur = np.asarray([ref_counts.get(key, 0) / ref_total for key in cur_keys])
            scale = float(np.std(np.concatenate([encoded_ref, encoded_cur])))
            if scale <= 1e-9:
                scale = 1.0
            center = float(np.mean(np.concatenate([encoded_ref, encoded_cur])))
            ref_cols.append(((encoded_ref - center) / scale)[:, None])
            cur_cols.append(((encoded_cur - center) / scale)[:, None])
        ref_cols.append(_missing_mask(ref_col).astype(float)[:, None])
        cur_cols.append(_missing_mask(cur_col).astype(float)[:, None])
    return np.hstack(ref_cols), np.hstack(cur_cols)


def _mmd_detector(
    data: ShiftDiagnosticInput,
    key: str,
    *,
    permutations: int,
    random_state: int,
) -> tuple[ShiftComponent, DetectorResult]:
    reference, current = _encoded_matrix(data)
    rng = np.random.default_rng(random_state)
    max_rows = 256
    if reference.shape[0] > max_rows:
        reference = reference[rng.choice(reference.shape[0], size=max_rows, replace=False)]
    if current.shape[0] > max_rows:
        current = current[rng.choice(current.shape[0], size=max_rows, replace=False)]
    statistic = _mmd2_biased(reference, current)
    p_value = 1.0
    if permutations > 0:
        combined = np.vstack([reference, current])
        n_reference = reference.shape[0]
        exceed = 1
        for _ in range(int(permutations)):
            order = rng.permutation(combined.shape[0])
            perm_ref = combined[order[:n_reference]]
            perm_cur = combined[order[n_reference:]]
            if _mmd2_biased(perm_ref, perm_cur) >= statistic:
                exceed += 1
        p_value = exceed / float(permutations + 1)
    score = _score_from_p_effect(p_value, statistic, 0.05)
    bucket = _severity_bucket(score)
    component = ShiftComponent(
        status=_detected_status(bucket),
        severity_score=score,
        severity_bucket=bucket,
        p_value=p_value,
        effect_size=statistic,
        power=0.75 if min(reference.shape[0], current.shape[0]) >= 100 else 0.40,
        notes=("rbf_mmd_on_mixed_type_encoded_features",),
    )
    detector = DetectorResult(
        detector_name="rbf_mmd_two_sample",
        detector_family="mmd",
        data_view="encoded_features",
        statistic=statistic,
        p_value=p_value,
        effect_size=statistic,
        null_percentile=score,
        calibrated_threshold=0.30,
        operating_characteristic_key=key,
        limitations=("kernel_bandwidth_uses_median_heuristic",),
    )
    return component, detector


def _mmd2_biased(reference: np.ndarray, current: np.ndarray) -> float:
    combined = np.vstack([reference, current])
    if combined.shape[0] < 2:
        return 0.0
    diffs = combined[:, None, :] - combined[None, :, :]
    distances = np.sum(diffs * diffs, axis=2)
    nonzero = distances[distances > 1e-12]
    bandwidth = float(np.median(nonzero)) if nonzero.size else 1.0
    if bandwidth <= 1e-12:
        bandwidth = 1.0
    gamma = 1.0 / (2.0 * bandwidth)
    kxx = np.exp(-gamma * _squared_distances(reference, reference))
    kyy = np.exp(-gamma * _squared_distances(current, current))
    kxy = np.exp(-gamma * _squared_distances(reference, current))
    return max(float(np.mean(kxx) + np.mean(kyy) - 2.0 * np.mean(kxy)), 0.0)


def _squared_distances(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    diff = left[:, None, :] - right[None, :, :]
    return np.sum(diff * diff, axis=2)


def _c2st_detector(
    data: ShiftDiagnosticInput,
    key: str,
    *,
    random_state: int,
) -> tuple[ShiftComponent, DetectorResult, C2STEvidence]:
    reference, current = _encoded_matrix(data)
    names = _feature_names(data)
    feature_columns = tuple(
        name for name in names for _ in (0, 1)
    )
    if reference.shape == current.shape and np.allclose(reference, current, equal_nan=True):
        evidence = C2STEvidence(
            auc=0.5,
            p_value=1.0,
            severity_score=0.0,
            feature_importance={},
            reference_density_ratio=np.ones(reference.shape[0], dtype=float),
        )
        component = ShiftComponent(
            status="not_detected",
            severity_score=0.0,
            severity_bucket="none",
            p_value=1.0,
            effect_size=0.0,
            power=0.45 if min(reference.shape[0], current.shape[0]) < 100 else 0.80,
            notes=("classifier_two_sample_skipped_for_identical_encoded_windows",),
        )
        detector = DetectorResult(
            detector_name="domain_classifier_two_sample",
            detector_family="classifier_two_sample",
            data_view="encoded_features",
            statistic=0.5,
            p_value=1.0,
            effect_size=0.0,
            null_percentile=0.0,
            calibrated_threshold=0.30,
            operating_characteristic_key=key,
            limitations=("identical_encoded_windows",),
        )
        return component, detector, evidence
    x = np.vstack([reference, current])
    y = np.concatenate([np.zeros(reference.shape[0]), np.ones(current.shape[0])])
    auc: float
    probabilities: np.ndarray | None = None
    importances: dict[str, float] = {}
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import StratifiedShuffleSplit

        split = StratifiedShuffleSplit(n_splits=1, test_size=0.35, random_state=random_state)
        train_idx, test_idx = next(split.split(x, y))
        model = LogisticRegression(max_iter=1000, solver="lbfgs")
        model.fit(x[train_idx], y[train_idx])
        probabilities = model.predict_proba(x)[:, 1]
        auc = float(roc_auc_score(y[test_idx], probabilities[test_idx]))
        coefs = np.abs(np.ravel(model.coef_))
        for name, coef in zip(feature_columns, coefs, strict=False):
            importances[name] = importances.get(name, 0.0) + float(coef)
        total = sum(importances.values())
        if total > 0.0:
            importances = {key_: value / total for key_, value in importances.items()}
    except Exception:
        mean_diff = np.mean(current, axis=0) - np.mean(reference, axis=0)
        norm = float(np.linalg.norm(mean_diff) / max(sqrt(reference.shape[1]), 1.0))
        auc = 0.5 + 0.5 * np.tanh(norm / 2.0)
        probabilities = None
        abs_diff = np.abs(mean_diff)
        total = float(np.sum(abs_diff))
        if total > 0.0:
            for name, value in zip(feature_columns, abs_diff, strict=False):
                importances[name] = importances.get(name, 0.0) + float(value / total)

    auc = max(auc, 1.0 - auc)
    se = sqrt((reference.shape[0] + current.shape[0] + 1.0) / (12.0 * reference.shape[0] * current.shape[0]))
    p_value = _normal_two_sided_p((auc - 0.5) / max(se, 1e-12))
    score = _score_from_p_effect(p_value, abs(auc - 0.5), 0.18)
    bucket = _severity_bucket(score)
    density_ratio: np.ndarray | None = None
    if probabilities is not None:
        ref_prob = np.clip(probabilities[: reference.shape[0]], 1e-4, 1.0 - 1e-4)
        density_ratio = (ref_prob / (1.0 - ref_prob)) * (reference.shape[0] / current.shape[0])
        density_ratio = np.clip(density_ratio, 1e-3, 100.0)
    evidence = C2STEvidence(
        auc=auc,
        p_value=p_value,
        severity_score=score,
        feature_importance=importances,
        reference_density_ratio=density_ratio,
    )
    detector = DetectorResult(
        detector_name="domain_classifier_two_sample",
        detector_family="classifier_two_sample",
        data_view="encoded_features",
        statistic=auc,
        p_value=p_value,
        effect_size=auc - 0.5,
        null_percentile=score,
        calibrated_threshold=0.30,
        operating_characteristic_key=key,
        implicated_features=tuple(
            name
            for name, _ in sorted(
                importances.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:8]
            if importances[name] > 0.0
        ),
        limitations=("domain_separability_can_be_benign_without_performance_degradation",),
    )
    component = ShiftComponent(
        status=_detected_status(bucket),
        severity_score=score,
        severity_bucket=bucket,
        p_value=p_value,
        effect_size=auc - 0.5,
        power=0.80 if min(reference.shape[0], current.shape[0]) >= 100 else 0.45,
        notes=("classifier_two_sample_auc_is_cross_validated_when_sklearn_available",),
    )
    return component, detector, evidence


def _support_detector(
    data: ShiftDiagnosticInput,
    c2st: C2STEvidence,
    key: str,
) -> tuple[ShiftComponent, DetectorResult, SupportEvidence]:
    reference = _as_2d_object(data.reference_features, "reference_features")
    current = _as_2d_object(data.current_features, "current_features")
    types = _infer_feature_types(data)
    row_out = np.zeros(current.shape[0], dtype=bool)
    cat_indices: list[int] = []
    for idx, feature_type in enumerate(types):
        ref_col = reference[:, idx]
        cur_col = current[:, idx]
        if feature_type in {"numeric", "binary", "embedding"}:
            ref_num = _numeric_column(ref_col)
            cur_num = _numeric_column(cur_col)
            finite = ref_num[np.isfinite(ref_num)]
            if finite.size:
                lower, upper = float(np.min(finite)), float(np.max(finite))
                row_out |= np.isfinite(cur_num) & ((cur_num < lower) | (cur_num > upper))
        else:
            ref_categories = {_category_key(value) for value in ref_col}
            row_out |= np.asarray([_category_key(value) not in ref_categories for value in cur_col])
            cat_indices.append(idx)

    rare_combination_rate = 0.0
    if cat_indices:
        selected = cat_indices[:5]
        ref_combos = {
            tuple(_category_key(row[idx]) for idx in selected)
            for row in reference
        }
        cur_combos = [
            tuple(_category_key(row[idx]) for idx in selected)
            for row in current
        ]
        rare_combination_rate = float(np.mean([combo not in ref_combos for combo in cur_combos]))

    ess_ratio: float | None = None
    max_ratio: float | None = None
    if c2st.reference_density_ratio is not None:
        weights = c2st.reference_density_ratio
        ess = _weighted_effective_n(weights, weights.shape[0])
        ess_ratio = ess / max(float(weights.shape[0]), 1.0)
        max_ratio = float(np.max(weights)) if weights.size else None

    out_fraction = float(np.mean(row_out))
    ess_signal = 0.0 if ess_ratio is None else _clip01(1.0 - ess_ratio)
    max_ratio_signal = 0.0 if max_ratio is None else _clip01((max_ratio - 5.0) / 20.0)
    score = _clip01(
        0.45 * _clip01(out_fraction / 0.10)
        + 0.25 * _clip01(rare_combination_rate / 0.20)
        + 0.20 * ess_signal
        + 0.10 * max_ratio_signal
    )
    bucket = _severity_bucket(score)
    evidence = SupportEvidence(
        out_of_support_fraction=out_fraction,
        rare_combination_rate=rare_combination_rate,
        effective_sample_size_ratio=ess_ratio,
        max_density_ratio=max_ratio,
        severity_score=score,
    )
    component = ShiftComponent(
        status=_detected_status(bucket),
        severity_score=score,
        severity_bucket=bucket,
        effect_size=out_fraction,
        power=0.75 if current.shape[0] >= 100 else 0.40,
        notes=(
            f"out_of_support_fraction={out_fraction:.4f}",
            f"rare_combination_rate={rare_combination_rate:.4f}",
        ),
    )
    detector = DetectorResult(
        detector_name="density_ratio_support_overlap",
        detector_family="density_ratio",
        data_view="raw_features",
        statistic=out_fraction,
        effect_size=out_fraction,
        null_percentile=score,
        calibrated_threshold=0.30,
        operating_characteristic_key=key,
        limitations=(
            "density_ratio_ess_uses_domain_classifier_weights_when_available",
            "support_uses_numeric_ranges_and_categorical_novelty",
        ),
    )
    return component, detector, evidence


def _prediction_output_detector(
    data: ShiftDiagnosticInput,
    key: str,
) -> tuple[ShiftComponent, DetectorResult | None]:
    reference = _as_optional_vector(data.reference_predictions, "reference_predictions")
    current = _as_optional_vector(data.current_predictions, "current_predictions")
    if reference is None or current is None:
        component = ShiftComponent(
            status="not_detected",
            severity_score=0.0,
            severity_bucket="none",
            notes=("prediction_outputs_not_provided",),
        )
        return component, None
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    statistic, p_value = _ks_test(ref, cur)
    effect = abs(float(np.nanmean(cur) - np.nanmean(ref)))
    score = _score_from_p_effect(p_value, max(statistic, effect), 0.20)
    bucket = _severity_bucket(score)
    component = ShiftComponent(
        status=_detected_status(bucket),
        severity_score=score,
        severity_bucket=bucket,
        p_value=p_value,
        effect_size=effect,
        power=0.80 if min(ref.size, cur.size) >= 100 else 0.45,
        notes=(f"prediction_mean {np.nanmean(ref):.4g} -> {np.nanmean(cur):.4g}",),
    )
    detector = DetectorResult(
        detector_name="prediction_output_distribution",
        detector_family="prediction_output",
        data_view="prediction_scores",
        statistic=statistic,
        p_value=p_value,
        effect_size=effect,
        null_percentile=score,
        calibrated_threshold=0.30,
        operating_characteristic_key=key,
        limitations=("proxy_for_harmful_shift_until_labels_arrive",),
    )
    return component, detector


def _label_prior_detector(
    data: ShiftDiagnosticInput,
    key: str,
) -> tuple[ShiftComponent, DetectorResult | None]:
    reference = _as_optional_vector(data.reference_target, "reference_target")
    current = _as_optional_vector(data.current_target, "current_target")
    if reference is None or current is None:
        component = ShiftComponent(
            status="unassessable_until_labels",
            severity_score=None,
            severity_bucket="unassessable",
            notes=("label_prior_shift_requires_labels_or_bbse_probabilities",),
        )
        return component, None
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref_mean = float(np.nanmean(ref))
    cur_mean = float(np.nanmean(cur))
    delta = cur_mean - ref_mean
    pooled = max(ref_mean * (1.0 - ref_mean), cur_mean * (1.0 - cur_mean), 1e-6)
    se = sqrt(pooled * (1.0 / max(ref.size, 1) + 1.0 / max(cur.size, 1)))
    p_value = _normal_two_sided_p(delta / max(se, 1e-12))
    score = _score_from_p_effect(p_value, abs(delta), 0.15)
    bucket = _severity_bucket(score)
    component = ShiftComponent(
        status=_detected_status(bucket),
        severity_score=score,
        severity_bucket=bucket,
        p_value=p_value,
        effect_size=abs(delta),
        power=0.80 if min(ref.size, cur.size) >= 100 else 0.45,
        notes=(f"label_prevalence {ref_mean:.4g} -> {cur_mean:.4g}",),
    )
    detector = DetectorResult(
        detector_name="label_prior_prevalence",
        detector_family="delayed_label_concept",
        data_view="labels",
        statistic=delta,
        p_value=p_value,
        effect_size=abs(delta),
        null_percentile=score,
        calibrated_threshold=0.30,
        operating_characteristic_key=key,
        limitations=("prevalence_shift_does_not_prove_conditional_concept_shift",),
    )
    return component, detector


def _concept_detector(
    data: ShiftDiagnosticInput,
    key: str,
    c2st: C2STEvidence,
) -> tuple[ShiftComponent, DetectorResult | None]:
    if data.label_availability == "none":
        return (
            ShiftComponent(
                status="unassessable_until_labels",
                severity_score=None,
                severity_bucket="unassessable",
                notes=("concept_shift_cannot_be_identified_from_unlabeled_X_only",),
            ),
            None,
        )
    ref_y = _as_optional_vector(data.reference_target, "reference_target")
    cur_y = _as_optional_vector(data.current_target, "current_target")
    ref_pred = _as_optional_vector(data.reference_predictions, "reference_predictions")
    cur_pred = _as_optional_vector(data.current_predictions, "current_predictions")
    if ref_y is None or cur_y is None or ref_pred is None or cur_pred is None:
        return (
            ShiftComponent(
                status="insufficient_power",
                severity_score=None,
                severity_bucket="unassessable",
                notes=("concept_shift_requires_predictions_and_current_or_delayed_labels",),
            ),
            None,
        )
    ref_loss = _loss_vector(data.task_type, np.asarray(ref_y, dtype=float), np.asarray(ref_pred, dtype=float))
    cur_loss = _loss_vector(data.task_type, np.asarray(cur_y, dtype=float), np.asarray(cur_pred, dtype=float))
    weights = c2st.reference_density_ratio
    if weights is None or weights.shape[0] != ref_loss.shape[0]:
        weights = np.ones_like(ref_loss)
    weights = np.asarray(weights, dtype=float)
    weights = np.where(np.isfinite(weights) & (weights > 0.0), weights, 1.0)
    expected_loss = float(np.sum(weights * ref_loss) / max(float(np.sum(weights)), 1e-12))
    observed_loss = float(np.mean(cur_loss))
    delta = observed_loss - expected_loss
    pooled = float(np.std(np.concatenate([ref_loss, cur_loss])))
    se = pooled * sqrt(1.0 / max(ref_loss.size, 1) + 1.0 / max(cur_loss.size, 1))
    p_value = _normal_two_sided_p(delta / max(se, 1e-12))
    score = _score_from_p_effect(p_value, max(delta, 0.0), 0.10)
    bucket = _severity_bucket(score)
    status: ShiftStatus = "confirmed" if bucket in {"high", "severe"} and delta > 0.0 else _detected_status(bucket)
    component = ShiftComponent(
        status=status,
        severity_score=score,
        severity_bucket=bucket,
        p_value=p_value,
        effect_size=max(delta, 0.0),
        power=0.80 if min(ref_loss.size, cur_loss.size) >= 100 else 0.45,
        notes=(
            f"reweighted_reference_loss={expected_loss:.4g}",
            f"current_loss={observed_loss:.4g}",
        ),
    )
    detector = DetectorResult(
        detector_name="delayed_label_reweighted_loss",
        detector_family="delayed_label_concept",
        data_view="loss_after_covariate_alignment",
        statistic=delta,
        p_value=p_value,
        effect_size=max(delta, 0.0),
        null_percentile=score,
        calibrated_threshold=0.55,
        operating_characteristic_key=key,
        limitations=("uses_density_ratio_reweighting_when_domain_classifier_weights_available",),
    )
    return component, detector


def _loss_vector(task_type: TaskType, target: np.ndarray, predictions: np.ndarray) -> np.ndarray:
    if task_type == "classification":
        pred = np.clip(predictions, 1e-6, 1.0 - 1e-6)
        binary_like = set(np.unique(target[np.isfinite(target)]).tolist()) <= {0.0, 1.0}
        if binary_like:
            return -(target * np.log(pred) + (1.0 - target) * np.log(1.0 - pred))
        return (target - predictions) ** 2
    return np.abs(target - predictions)


def _harmful_shift_component(
    *,
    prediction_shift: ShiftComponent,
    support_shift: ShiftComponent,
    concept_shift: ShiftComponent,
    marginal_shift: ShiftComponent,
) -> ShiftComponent:
    scores = [
        _safe_float(prediction_shift.severity_score),
        _safe_float(support_shift.severity_score),
        _safe_float(marginal_shift.severity_score) * 0.6,
    ]
    if concept_shift.status == "confirmed":
        scores.append(1.0)
    elif concept_shift.status == "suspected":
        scores.append(0.7)
    score = _clip01(max(scores) if scores else 0.0)
    bucket = _severity_bucket(score)
    status: ShiftStatus = "suspected" if bucket in {"high", "severe"} else _detected_status(bucket)
    return ShiftComponent(
        status=status,
        severity_score=score,
        severity_bucket=bucket,
        effect_size=score,
        notes=(
            "proxy_harmful_shift_risk_combines_prediction_output_support_and_concept_evidence",
        ),
    )


def _subgroup_diagnostics(
    data: ShiftDiagnosticInput,
    key: str,
) -> tuple[tuple[dict[str, Any], ...], tuple[DetectorResult, ...]]:
    diagnostics: list[dict[str, Any]] = []
    detectors: list[DetectorResult] = []
    for group_name, ref_values in data.reference_subgroups.items():
        if group_name not in data.current_subgroups:
            continue
        ref = np.asarray([_category_key(value) for value in np.asarray(ref_values, dtype=object)])
        cur = np.asarray(
            [_category_key(value) for value in np.asarray(data.current_subgroups[group_name], dtype=object)]
        )
        _, p_value, tv = _categorical_test(ref, cur)
        score = _score_from_p_effect(p_value, tv, 0.20)
        bucket = _severity_bucket(score)
        categories = tuple(dict.fromkeys([*ref.tolist(), *cur.tolist()]))
        top_changes = []
        for category in categories:
            ref_share = float(np.mean(ref == category))
            cur_share = float(np.mean(cur == category))
            delta = cur_share - ref_share
            if abs(delta) >= 0.03:
                top_changes.append(
                    {
                        "value": category,
                        "reference_share": ref_share,
                        "current_share": cur_share,
                        "delta": delta,
                    }
                )
        top_changes = sorted(top_changes, key=lambda item: abs(item["delta"]), reverse=True)[:5]
        diagnostics.append(
            {
                "subgroup_name": group_name,
                "severity_score": score,
                "severity_bucket": bucket,
                "p_value": p_value,
                "effect_size": tv,
                "top_changes": top_changes,
                "power": 0.80 if min(ref.size, cur.size) >= 100 else 0.40,
            }
        )
        if bucket in {"moderate", "high", "severe"}:
            detectors.append(
                DetectorResult(
                    detector_name=f"subgroup_distribution_{group_name}",
                    detector_family="subgroup",
                    data_view=f"subgroup:{group_name}",
                    statistic=tv,
                    p_value=p_value,
                    effect_size=tv,
                    null_percentile=score,
                    calibrated_threshold=0.30,
                    operating_characteristic_key=key,
                    implicated_subgroups=(group_name,),
                    limitations=("small_subgroup_power_is_reported_not_silently_green",),
                )
            )
    return tuple(diagnostics), tuple(detectors)


def _power_status(data: ShiftDiagnosticInput) -> Literal["sufficient", "insufficient", "unknown"]:
    n_reference = _as_2d_object(data.reference_features, "reference_features").shape[0]
    n_current = _as_2d_object(data.current_features, "current_features").shape[0]
    min_n = 80
    if data.modality == "sparse_survey":
        min_n = 150
    if data.modality == "longitudinal_panel":
        min_n = 100
    return "sufficient" if min(n_reference, n_current) >= min_n else "insufficient"


def _global_verdict(
    *,
    power_status: Literal["sufficient", "insufficient", "unknown"],
    schema_shift: ShiftComponent,
    marginal_shift: ShiftComponent,
    support_shift: ShiftComponent,
    label_prior_shift: ShiftComponent,
    concept_shift: ShiftComponent,
) -> ShiftGlobalVerdict:
    if schema_shift.severity_bucket in {"high", "severe"}:
        return "schema_shift"
    concept_material = concept_shift.status == "confirmed"
    marginal_material = marginal_shift.severity_bucket in {"moderate", "high", "severe"}
    support_material = support_shift.severity_bucket in {"moderate", "high", "severe"}
    if concept_material and (marginal_material or support_material):
        return "mixed_shift"
    if concept_material:
        return "concept_shift"
    if support_material and marginal_material:
        return "mixed_shift"
    if support_material:
        return "support_shift"
    if label_prior_shift.severity_bucket in {"high", "severe"}:
        return "label_prior_shift"
    if marginal_material:
        return "marginal_shift"
    if power_status == "insufficient":
        return "insufficient_power"
    return "no_shift_detected"


def _component_max(left: ShiftComponent, right: ShiftComponent) -> ShiftComponent:
    left_score = _safe_float(left.severity_score)
    right_score = _safe_float(right.severity_score)
    return left if left_score >= right_score else right


def _readiness_reasons_and_actions(report_like: Any, downgrade: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    reasons: list[str] = []
    actions: list[str] = []
    if report_like.schema_shift.severity_bucket in {"high", "severe"}:
        reasons.append("schema_shift_high_or_severe")
        actions.append("block_automated_recommendation")
        actions.append("repair_schema_contract_or_codebook")
    if report_like.concept_shift.status == "confirmed":
        reasons.append("concept_shift_confirmed")
        actions.append("revalidate_or_retrain_model")
    if report_like.support_shift.severity_bucket in {"high", "severe"}:
        reasons.append("support_shift_high_or_severe")
        actions.append("require_recent_validation_or_reweighting")
    if report_like.marginal_shift.severity_bucket in {"moderate", "high", "severe"}:
        reasons.append(f"marginal_shift_{report_like.marginal_shift.severity_bucket}")
        actions.append("review_top_shifted_features_and_cohorts")
    if report_like.label_prior_shift.severity_bucket in {"high", "severe"}:
        reasons.append("label_prior_shift_high_or_severe")
        actions.append("check_prevalence_and_threshold_policy")
    if report_like.power_status == "insufficient":
        reasons.append("insufficient_power_for_declared_mde")
        actions.append("collect_more_current_window_data_or_pool_windows")
    if not reasons:
        reasons.append("no_material_shift_detected_with_power_statement")
        actions.append("continue_normal_monitoring")
    if downgrade >= 3 and "block_automated_recommendation" not in actions:
        actions.append("block_automated_recommendation")
    elif downgrade == 2:
        actions.append("restrict_automated_use_pending_review")
    elif downgrade == 1:
        actions.append("schedule_monitoring_review")
    return tuple(dict.fromkeys(reasons)), tuple(dict.fromkeys(actions))


def _model_relevance(data: ShiftDiagnosticInput) -> dict[str, float]:
    raw = data.metadata.get("feature_importances") or data.metadata.get("coefficients") or {}
    if not isinstance(raw, Mapping):
        return {}
    values = {str(key): abs(_safe_float(value)) for key, value in raw.items()}
    max_value = max(values.values(), default=0.0)
    if max_value <= 0.0:
        return {}
    return {key: _clip01(value / max_value) for key, value in values.items()}


def _key(
    data: ShiftDiagnosticInput,
    family: DetectorFamily,
    *,
    reference_comparison_type: ReferenceComparisonType | None = None,
) -> str:
    reference = _as_2d_object(data.reference_features, "reference_features")
    current = _as_2d_object(data.current_features, "current_features")
    types = _infer_feature_types(data)
    cat_cardinality = 0
    missing_count = 0
    for idx, feature_type in enumerate(types):
        if feature_type in {"categorical", "text"}:
            categories = {
                _category_key(value)
                for value in np.concatenate([reference[:, idx], current[:, idx]])
            }
            cat_cardinality += len(categories)
        missing_count += int(np.sum(_missing_mask(reference[:, idx])))
        missing_count += int(np.sum(_missing_mask(current[:, idx])))
    total_cells = max(reference.size + current.size, 1)
    missing_rate = missing_count / total_cells
    return OperatingCharacteristicKey(
        modality=data.modality,
        task_type=data.task_type,
        n_reference_bucket=_n_bucket(reference.shape[0], "n_ref"),
        n_current_bucket=_n_bucket(current.shape[0], "n_cur"),
        feature_count_bucket=_feature_bucket(reference.shape[1]),
        categorical_cardinality_bucket=_cardinality_bucket(cat_cardinality),
        sparsity_missingness_bucket=_missing_bucket(missing_rate),
        label_lag_bucket=_label_lag_bucket(data),
        detector_family=family,
        reference_comparison_type=reference_comparison_type or data.reference_comparison_type,
        windowing_strategy=data.windowing_strategy,
        calibration_version=data.calibration_version,
    ).to_cache_key()


def _n_bucket(value: int, prefix: str) -> str:
    if value < 50:
        return f"{prefix}_lt_50"
    if value < 200:
        return f"{prefix}_50_199"
    if value < 1000:
        return f"{prefix}_200_999"
    if value < 10000:
        return f"{prefix}_1k_10k"
    return f"{prefix}_10k_plus"


def _feature_bucket(value: int) -> str:
    if value < 10:
        return "p_lt_10"
    if value < 100:
        return "p_10_100"
    return "p_100_plus"


def _cardinality_bucket(value: int) -> str:
    if value == 0:
        return "cat_none"
    if value < 50:
        return "cat_low"
    if value < 500:
        return "cat_medium"
    return "cat_high"


def _missing_bucket(value: float) -> str:
    if value < 0.01:
        return "missing_none_or_low"
    if value < 0.10:
        return "missing_moderate"
    return "missing_high"


def _label_lag_bucket(data: ShiftDiagnosticInput) -> str:
    if data.label_availability == "none":
        return "no_labels"
    if data.label_lag_days is None:
        return data.label_availability
    if data.label_lag_days <= 30:
        return "lag_0_30"
    if data.label_lag_days <= 180:
        return "lag_31_180"
    return "lag_181_plus"


def _calibration(data: ShiftDiagnosticInput, power_status: str) -> CalibrationInfo:
    n_reference = _as_2d_object(data.reference_features, "reference_features").shape[0]
    n_current = _as_2d_object(data.current_features, "current_features").shape[0]
    mde = 2.8 * sqrt(1.0 / max(n_reference, 1) + 1.0 / max(n_current, 1))
    return CalibrationInfo(
        operating_characteristic_library_version=data.calibration_version,
        calibration_id=f"{data.modality}:{data.reference_comparison_type}:{data.windowing_strategy}",
        reference_comparison_type=data.reference_comparison_type,
        target_report_fpr=0.05,
        multiplicity_method="benjamini_hochberg",
        null_regime=data.null_regime,
        min_detectable_effect_summary={
            "standardized_mean_difference": round(float(mde), 6),
            "feature_q_value_threshold": 0.05,
            "minimum_current_n_for_power": 150 if data.modality == "sparse_survey" else 80,
        },
        power_summary={
            "power_status": power_status,
            "n_reference": n_reference,
            "n_current": n_current,
            "declared_power_target": 0.80,
            "no_silent_green_state": True,
        },
    )


def _summary(
    verdict: ShiftGlobalVerdict,
    data: ShiftDiagnosticInput,
    features: Sequence[FeatureShiftDiagnostic],
) -> str:
    if verdict == "no_shift_detected":
        return (
            "No material observable distribution shift was detected with a declared power "
            "statement; concept shift remains unassessable until labels or a proxy arrive."
        )
    top = ", ".join(feature.feature_name for feature in features[:3]) or "no localized feature"
    return (
        f"{verdict.replace('_', ' ')} detected for {data.reference_comparison_type}; "
        f"top localized evidence: {top}."
    )


def _limitations(data: ShiftDiagnosticInput, power_status: str) -> tuple[str, ...]:
    limitations: list[str] = []
    if data.label_availability == "none":
        limitations.append("concept_shift_unassessable_without_labels_or_validated_proxy")
    if data.modality == "longitudinal_panel":
        limitations.append("panel_inference_requires_entity_blocked_calibration")
        if "entity_ids" not in data.reference_subgroups:
            limitations.append("entity_ids_not_supplied_for_panel_blocking")
    if data.modality == "sparse_survey":
        limitations.append("survey_design_weights_or_replicate_bootstrap_may_be_required")
    if power_status == "insufficient":
        limitations.append("insufficient_power_for_small_or_moderate_shift")
    return tuple(dict.fromkeys(limitations))


def _next_checks(report_like: Any, data: ShiftDiagnosticInput) -> tuple[str, ...]:
    checks: list[str] = ["persist_report_id_with_prediction_recommendation"]
    if data.label_availability == "none":
        checks.append("attach_delayed_outcomes_or_proxy_labels_when_available")
    if report_like.support_shift.severity_bucket in {"moderate", "high", "severe"}:
        checks.append("run_support_overlap_review_and_reweighting_feasibility")
    if report_like.marginal_shift.severity_bucket in {"moderate", "high", "severe"}:
        checks.append("review_top_shifted_features_cohorts_and_schema_lineage")
    if data.modality == "longitudinal_panel":
        checks.append("rerun_with_entity_blocked_permutation_or_bootstrap")
    if data.modality == "sparse_survey":
        checks.append("rerun_with_design_or_replicate_weights")
    return tuple(dict.fromkeys(checks))


def build_shift_diagnostic_report(
    data: ShiftDiagnosticInput | Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
) -> ShiftDiagnosticReport:
    """Build one calibrated shift report for a declared reference comparison."""

    merged = _merge_params(data, params)
    diagnostic_input = (
        merged if isinstance(merged, ShiftDiagnosticInput) else ShiftDiagnosticInput.model_validate(merged)
    )
    alpha = _safe_float((params or {}).get("feature_q_threshold", 0.05), 0.05)
    permutations = max(0, int((params or {}).get("mmd_permutations", 39)))
    random_state = int((params or {}).get("random_state", 0))
    model_relevance = _model_relevance(diagnostic_input)

    schema_component, schema_detector, schema_limitations = _schema_detector(
        diagnostic_input,
        _key(diagnostic_input, "schema"),
    )
    uni_component, uni_detectors, feature_diagnostics = _univariate_detectors(
        diagnostic_input,
        _key(diagnostic_input, "univariate"),
        alpha,
        model_relevance,
    )
    mmd_component, mmd_detector = _mmd_detector(
        diagnostic_input,
        _key(diagnostic_input, "mmd"),
        permutations=permutations,
        random_state=random_state,
    )
    c2st_component, c2st_detector, c2st_evidence = _c2st_detector(
        diagnostic_input,
        _key(diagnostic_input, "classifier_two_sample"),
        random_state=random_state,
    )
    marginal_component = _component_max(uni_component, _component_max(mmd_component, c2st_component))
    support_component, support_detector, support_evidence = _support_detector(
        diagnostic_input,
        c2st_evidence,
        _key(diagnostic_input, "density_ratio"),
    )
    prediction_component, prediction_detector = _prediction_output_detector(
        diagnostic_input,
        _key(diagnostic_input, "prediction_output"),
    )
    label_component, label_detector = _label_prior_detector(
        diagnostic_input,
        _key(diagnostic_input, "delayed_label_concept"),
    )
    concept_component, concept_detector = _concept_detector(
        diagnostic_input,
        _key(diagnostic_input, "delayed_label_concept"),
        c2st_evidence,
    )
    harmful_component = _harmful_shift_component(
        prediction_shift=prediction_component,
        support_shift=support_component,
        concept_shift=concept_component,
        marginal_shift=marginal_component,
    )
    subgroup_diagnostics, subgroup_detectors = _subgroup_diagnostics(
        diagnostic_input,
        _key(diagnostic_input, "subgroup"),
    )
    power_status = _power_status(diagnostic_input)
    verdict = _global_verdict(
        power_status=power_status,
        schema_shift=schema_component,
        marginal_shift=marginal_component,
        support_shift=support_component,
        label_prior_shift=label_component,
        concept_shift=concept_component,
    )
    if verdict == "no_shift_detected" and diagnostic_input.label_availability == "none":
        concept_component = ShiftComponent(
            status="unassessable_until_labels",
            severity_score=None,
            severity_bucket="unassessable",
            notes=("concept_shift_cannot_be_identified_from_unlabeled_X_only",),
        )

    report_like = SimpleNamespace(
        schema_shift=schema_component,
        concept_shift=concept_component,
        support_shift=support_component,
        harmful_shift_risk=harmful_component,
        marginal_shift=marginal_component,
        label_prior_shift=label_component,
        power_status=power_status,
        decision_context=diagnostic_input.decision_context,
    )
    downgrade = readiness_downgrade(report_like)
    reasons, actions = _readiness_reasons_and_actions(report_like, downgrade)
    detector_results = [
        schema_detector,
        *uni_detectors,
        mmd_detector,
        c2st_detector,
        support_detector,
        *([prediction_detector] if prediction_detector is not None else []),
        *([label_detector] if label_detector is not None else []),
        *([concept_detector] if concept_detector is not None else []),
        *subgroup_detectors,
    ]
    limitations = tuple(
        dict.fromkeys(
            [
                *schema_limitations,
                *_limitations(diagnostic_input, power_status),
            ]
        )
    )
    calibration = _calibration(diagnostic_input, power_status)
    generated_at = diagnostic_input.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    report_id = diagnostic_input.report_id or (
        f"shift:{diagnostic_input.model_id}:{diagnostic_input.current_window_id}:"
        f"{diagnostic_input.reference_comparison_type}"
    )
    return ShiftDiagnosticReport(
        report_id=report_id,
        generated_at=generated_at,
        prediction_result_id=diagnostic_input.prediction_result_id,
        model_id=diagnostic_input.model_id,
        model_version=diagnostic_input.model_version,
        task_type=diagnostic_input.task_type,
        modality=diagnostic_input.modality,
        training_reference_id=diagnostic_input.training_reference_id,
        validation_reference_id=diagnostic_input.validation_reference_id,
        current_window_id=diagnostic_input.current_window_id,
        current_window_start=diagnostic_input.current_window_start,
        current_window_end=diagnostic_input.current_window_end,
        n_reference=int(_as_2d_object(diagnostic_input.reference_features, "reference_features").shape[0]),
        n_current=int(_as_2d_object(diagnostic_input.current_features, "current_features").shape[0]),
        effective_n_reference=_weighted_effective_n(
            _as_optional_vector(diagnostic_input.reference_sample_weight, "reference_sample_weight"),
            _as_2d_object(diagnostic_input.reference_features, "reference_features").shape[0],
        ),
        effective_n_current=_weighted_effective_n(
            _as_optional_vector(diagnostic_input.current_sample_weight, "current_sample_weight"),
            _as_2d_object(diagnostic_input.current_features, "current_features").shape[0],
        ),
        label_availability=diagnostic_input.label_availability,
        label_lag_days=diagnostic_input.label_lag_days,
        decision_context=diagnostic_input.decision_context,
        power_status=power_status,
        calibration=calibration,
        schema_shift=schema_component,
        marginal_shift=marginal_component,
        support_shift=support_component,
        label_prior_shift=label_component,
        concept_shift=concept_component,
        prediction_output_shift=prediction_component,
        harmful_shift_risk=harmful_component,
        global_verdict=verdict,
        detector_results=tuple(detector_results),
        feature_diagnostics=feature_diagnostics,
        subgroup_diagnostics=subgroup_diagnostics,
        readiness_impact=build_readiness_impact(
            base_readiness=diagnostic_input.base_readiness,
            downgrade_level=downgrade,
            downgrade_reasons=reasons,
            required_actions=actions,
        ),
        human_summary=_summary(verdict, diagnostic_input, feature_diagnostics),
        machine_summary={
            "reference_comparison_type": diagnostic_input.reference_comparison_type,
            "support_overlap": {
                "out_of_support_fraction": support_evidence.out_of_support_fraction,
                "rare_combination_rate": support_evidence.rare_combination_rate,
                "effective_sample_size_ratio": support_evidence.effective_sample_size_ratio,
                "max_density_ratio": support_evidence.max_density_ratio,
            },
            "classifier_two_sample_auc": c2st_evidence.auc,
            "top_features": [feature.feature_name for feature in feature_diagnostics[:5]],
        },
        limitations=limitations,
        recommended_next_checks=_next_checks(report_like, diagnostic_input),
    )


def build_shift_reference_comparison_reports(
    data: ShiftDiagnosticInput | Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
) -> tuple[ShiftDiagnosticReport, ...]:
    """Run the four architecture reference comparisons when windows are supplied."""

    base = data.model_dump(mode="python") if isinstance(data, ShiftDiagnosticInput) else dict(data)
    windows = base.get("reference_windows") or {}
    reports: list[ShiftDiagnosticReport] = []
    for comparison in _REFERENCE_COMPARISONS:
        payload = dict(base)
        payload["reference_comparison_type"] = comparison
        window = windows.get(comparison)
        if isinstance(window, Mapping):
            payload.update(
                {
                    "reference_features": window.get("features", payload.get("reference_features")),
                    "reference_predictions": window.get(
                        "predictions", payload.get("reference_predictions")
                    ),
                    "reference_target": window.get("target", payload.get("reference_target")),
                    "reference_sample_weight": window.get(
                        "sample_weight", payload.get("reference_sample_weight")
                    ),
                    "reference_schema": window.get("schema", payload.get("reference_schema")),
                    "reference_subgroups": window.get(
                        "subgroups", payload.get("reference_subgroups", {})
                    ),
                    "training_reference_id": window.get(
                        "reference_id", payload.get("training_reference_id")
                    ),
                }
            )
        payload["report_id"] = f"{payload.get('report_id') or 'shift'}:{comparison}"
        reports.append(build_shift_diagnostic_report(payload, params=params))
    return tuple(reports)


def _merge_params(
    data: ShiftDiagnosticInput | Mapping[str, Any],
    params: Mapping[str, Any] | None,
) -> ShiftDiagnosticInput | dict[str, Any]:
    if not params:
        return data
    metadata_keys = {
        "model_id",
        "model_version",
        "task_type",
        "modality",
        "training_reference_id",
        "validation_reference_id",
        "current_window_id",
        "current_window_start",
        "current_window_end",
        "label_availability",
        "label_lag_days",
        "base_readiness",
        "decision_context",
        "reference_comparison_type",
        "windowing_strategy",
        "null_regime",
        "calibration_version",
        "generated_at",
        "report_id",
    }
    overrides = {key: params[key] for key in metadata_keys if key in params}
    if isinstance(data, ShiftDiagnosticInput):
        return data.model_copy(update=overrides)
    payload = dict(data)
    payload.update(overrides)
    return payload


@foundry_method(
    namespace="ml.diagnostics",
    version="1.0.0",
    tags={"ml", "diagnostics", "distribution-shift", "phase-5"},
)
class ShiftDiagnosticEstimator:
    """Build a calibrated shift report; do not use as a label-free proof of concept drift."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy?", "scikit-learn?")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="shift_diagnostic",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "shift_diagnostic_input",
                    SlotType.SCALAR,
                    Unit("shift_diagnostic", "json"),
                    contract_id=ShiftDiagnosticInput.contract_id,
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "shift_diagnostic_report",
                    SlotType.SCALAR,
                    Unit("shift_diagnostic", "json"),
                    contract_id=ShiftDiagnosticReport.contract_id,
                )
            }
        ),
        parameters=(
            ParameterSpec(name="report_mode", default="single", is_static=True),
            ParameterSpec(name="feature_q_threshold", default=0.05),
            ParameterSpec(name="mmd_permutations", default=39, is_static=True),
            ParameterSpec(name="random_state", default=0, is_static=True),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Calibrated distribution-shift diagnostic ensemble producing "
            "ShiftDiagnosticReport readiness evidence."
        ),
        tags=frozenset({"ml", "diagnostics", "distribution-shift", "phase-5"}),
        citations=(
            "Rabanser et al. (2019). Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift.",
            "Gretton et al. (2012). A Kernel Two-Sample Test.",
            "Lipton et al. (2018). Detecting and Correcting for Label Shift with Black Box Predictors.",
        ),
        assumptions={
            "concept_shift": (
                "Concept shift is unassessable from unlabeled covariates unless proxy "
                "or delayed labels are supplied."
            ),
            "calibration": (
                "Default thresholds are operating-characteristic placeholders and should "
                "be replaced by a versioned OCL for production datasets."
            ),
        },
        diagnostic_contract={
            "output_contract": ShiftDiagnosticReport.contract_id,
            "readiness_downgrade_levels": [0, 1, 2, 3],
            "reference_comparisons": list(_REFERENCE_COMPARISONS),
        },
        when_to_use=(
            "Before consuming PredictionResult outputs in high-stakes or deployed settings; "
            "to localize covariate/support/prediction-output drift and attach readiness impact."
        ),
        when_not_to_use=(
            "As a conclusive label-free test of P(Y|X) drift; attach delayed labels or proxies "
            "for concept-shift confirmation."
        ),
        typical_min_obs=80,
        output_interpretation=(
            "Read global_verdict together with subtype severities, power_status, top features, "
            "limitations, and readiness_impact."
        ),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> ShiftDiagnosticInput:
        if "shift_diagnostic_input" in bound_inputs:
            payload = bound_inputs["shift_diagnostic_input"]
        else:
            payload = fallback_state
        if isinstance(payload, ShiftDiagnosticInput):
            return payload
        if not isinstance(payload, Mapping):
            raise TypeError("ShiftDiagnosticEstimator state must be a mapping or ShiftDiagnosticInput")
        merged = dict(payload)
        merged.update({key: value for key, value in bound_inputs.items() if key != "shift_diagnostic_input"})
        return ShiftDiagnosticInput.model_validate(merged)

    @staticmethod
    def pure_step(state: ShiftDiagnosticInput | Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        report_mode = str(params.get("report_mode", "single"))
        if report_mode == "all_reference_comparisons":
            reports = build_shift_reference_comparison_reports(state, params=params)
            primary = max(
                reports,
                key=lambda report: report.readiness_impact.downgrade_level,
            )
            return {
                "shift_diagnostic_report": primary,
                "reference_comparison_reports": reports,
            }
        report = build_shift_diagnostic_report(state, params=params)
        return {"shift_diagnostic_report": report}


__all__ = [
    "ShiftDiagnosticEstimator",
    "ShiftDiagnosticInput",
    "build_shift_diagnostic_report",
    "build_shift_reference_comparison_reports",
]
