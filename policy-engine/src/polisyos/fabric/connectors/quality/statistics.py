"""Statistical profiling, anomaly detection, drift detection, and quality contracts."""

from __future__ import annotations

import importlib.util
import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from polisyos.fabric.quality.finite import (
    ensure_finite_float,
    ensure_non_negative_finite,
    ensure_probability,
    is_finite_number,
)
from polisyos.fabric.tabular import require_dataframe
from polisyos.fabric.temporal import parse_datetime_utc, utc_now


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    return str(value)


def _finite_numeric_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric[numeric.notna() & numeric.map(is_finite_number)]


def _series_type_stability(series: pd.Series, expected_kind: str | None = None) -> float:
    non_null = series.dropna()
    if non_null.empty:
        return 1.0

    if expected_kind == "numeric":
        numeric = pd.to_numeric(non_null, errors="coerce")
        return float(numeric.notna().mean())
    if expected_kind == "temporal":
        temporal = pd.to_datetime(non_null, errors="coerce", utc=True)
        return float(temporal.notna().mean())
    if expected_kind == "string":
        matches = sum(isinstance(value, str) for value in non_null)
        return matches / len(non_null)
    if expected_kind == "boolean":
        matches = sum(isinstance(value, bool) for value in non_null)
        return matches / len(non_null)

    type_counts = Counter(type(value).__name__ for value in non_null)
    dominant = max(type_counts.values(), default=0)
    return dominant / len(non_null)


def _schema_expected_kind(schema: Any, column_name: str) -> str | None:
    get_field = getattr(schema, "get_field", None)
    if get_field is None:
        return None
    field = get_field(column_name)
    if field is None:
        return None
    data_type = getattr(field, "data_type", None)
    if data_type is None:
        return None
    if data_type.is_numeric():
        return "numeric"
    if data_type.is_temporal():
        return "temporal"
    type_name = str(getattr(data_type, "value", data_type)).lower()
    if "bool" in type_name:
        return "boolean"
    if "string" in type_name or "text" in type_name or "category" in type_name:
        return "string"
    return None


def _top_values(series: pd.Series, *, limit: int) -> tuple[TopValue, ...]:
    non_null = series.dropna().astype(str)
    value_counts = non_null.value_counts().head(limit)
    total = int(non_null.shape[0])
    if total <= 0:
        return ()
    return tuple(
        TopValue(
            value=str(value),
            count=int(count),
            ratio=ensure_probability(count / total, what=f"top value ratio {value}", clamp=True),
        )
        for value, count in value_counts.items()
    )


def _numeric_histogram(series: pd.Series, *, bins: int) -> tuple[HistogramBin, ...]:
    numeric = _finite_numeric_series(series)
    if numeric.empty or len(numeric.unique()) <= 1:
        return ()
    try:
        categories = pd.cut(numeric, bins=min(max(bins, 1), 20), include_lowest=True)
    except ValueError:
        return ()
    counts = categories.value_counts(sort=False)
    histogram: list[HistogramBin] = []
    for interval, count in counts.items():
        histogram.append(
            HistogramBin(
                lower=float(interval.left),
                upper=float(interval.right),
                count=int(count),
            )
        )
    return tuple(histogram)


@dataclass(frozen=True)
class TopValue:
    value: str
    count: int
    ratio: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "ratio", ensure_probability(self.ratio, what="top value ratio"))
        if self.count < 0:
            raise ValueError("count must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "count": self.count, "ratio": self.ratio}


@dataclass(frozen=True)
class HistogramBin:
    lower: float
    upper: float
    count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "lower", ensure_finite_float(self.lower, what="histogram lower"))
        object.__setattr__(self, "upper", ensure_finite_float(self.upper, what="histogram upper"))
        if self.count < 0:
            raise ValueError("count must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {"lower": self.lower, "upper": self.upper, "count": self.count}


@dataclass(frozen=True)
class ColumnProfile:
    column_name: str
    pandas_dtype: str
    inferred_type: str
    null_rate: float
    non_null_count: int
    distinct_count: int
    cardinality_ratio: float
    type_stability: float
    min_value: Any = None
    max_value: Any = None
    quantiles: dict[str, float] = field(default_factory=dict)
    histogram: tuple[HistogramBin, ...] = ()
    top_values: tuple[TopValue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "null_rate",
            ensure_probability(self.null_rate, what=f"{self.column_name} null_rate"),
        )
        object.__setattr__(
            self,
            "cardinality_ratio",
            ensure_probability(
                self.cardinality_ratio,
                what=f"{self.column_name} cardinality_ratio",
                clamp=True,
            ),
        )
        object.__setattr__(
            self,
            "type_stability",
            ensure_probability(self.type_stability, what=f"{self.column_name} type_stability"),
        )
        if self.non_null_count < 0:
            raise ValueError("non_null_count must be >= 0")
        if self.distinct_count < 0:
            raise ValueError("distinct_count must be >= 0")
        object.__setattr__(
            self,
            "quantiles",
            {
                str(name): ensure_finite_float(value, what=f"{self.column_name} quantile {name}")
                for name, value in self.quantiles.items()
                if is_finite_number(value)
            },
        )

    @property
    def profile_score(self) -> float:
        return ensure_probability(
            ((1.0 - self.null_rate) + self.type_stability) / 2.0,
            what=f"{self.column_name} profile_score",
            clamp=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "column_name": self.column_name,
            "pandas_dtype": self.pandas_dtype,
            "inferred_type": self.inferred_type,
            "null_rate": self.null_rate,
            "non_null_count": self.non_null_count,
            "distinct_count": self.distinct_count,
            "cardinality_ratio": self.cardinality_ratio,
            "type_stability": self.type_stability,
            "min_value": _jsonable_value(self.min_value),
            "max_value": _jsonable_value(self.max_value),
            "quantiles": dict(self.quantiles),
            "histogram": [item.to_dict() for item in self.histogram],
            "top_values": [item.to_dict() for item in self.top_values],
            "profile_score": self.profile_score,
        }


@dataclass(frozen=True)
class DatasetProfile:
    row_count: int
    column_profiles: dict[str, ColumnProfile]
    profiled_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.row_count < 0:
            raise ValueError("row_count must be >= 0")

    @property
    def profile_score(self) -> float:
        if not self.column_profiles:
            return 1.0
        return ensure_probability(
            sum(profile.profile_score for profile in self.column_profiles.values())
            / len(self.column_profiles),
            what="dataset profile_score",
            clamp=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "profiled_at": self.profiled_at.isoformat(),
            "profile_score": self.profile_score,
            "column_profiles": {
                column: profile.to_dict() for column, profile in self.column_profiles.items()
            },
        }


@dataclass(frozen=True)
class AnomalyFinding:
    column_name: str
    detector: str
    anomaly_count: int
    anomaly_rate: float
    threshold: float | None = None
    sample_indices: tuple[int, ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        if self.anomaly_count < 0:
            raise ValueError("anomaly_count must be >= 0")
        object.__setattr__(
            self,
            "anomaly_rate",
            ensure_probability(self.anomaly_rate, what=f"{self.column_name} anomaly_rate"),
        )
        if self.threshold is not None:
            object.__setattr__(
                self,
                "threshold",
                ensure_non_negative_finite(
                    self.threshold,
                    what=f"{self.column_name} anomaly threshold",
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "column_name": self.column_name,
            "detector": self.detector,
            "anomaly_count": self.anomaly_count,
            "anomaly_rate": self.anomaly_rate,
            "threshold": self.threshold,
            "sample_indices": list(self.sample_indices),
            "message": self.message,
        }


@dataclass(frozen=True)
class AnomalyReport:
    findings: tuple[AnomalyFinding, ...] = ()
    detectors_used: tuple[str, ...] = ()

    @property
    def overall_anomaly_rate(self) -> float:
        if not self.findings:
            return 0.0
        return ensure_probability(
            max(finding.anomaly_rate for finding in self.findings),
            what="overall anomaly rate",
            clamp=True,
        )

    @property
    def score(self) -> float:
        return ensure_probability(
            1.0 - self.overall_anomaly_rate,
            what="anomaly score",
            clamp=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "detectors_used": list(self.detectors_used),
            "overall_anomaly_rate": self.overall_anomaly_rate,
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class DriftFinding:
    column_name: str
    test: str
    detected: bool
    statistic: float
    p_value: float | None
    drift_score: float
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "statistic",
            ensure_non_negative_finite(self.statistic, what=f"{self.column_name} drift statistic"),
        )
        object.__setattr__(
            self,
            "drift_score",
            ensure_probability(
                self.drift_score, what=f"{self.column_name} drift_score", clamp=True
            ),
        )
        if self.p_value is not None:
            object.__setattr__(
                self,
                "p_value",
                ensure_probability(self.p_value, what=f"{self.column_name} drift p_value"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "column_name": self.column_name,
            "test": self.test,
            "detected": self.detected,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "drift_score": self.drift_score,
            "message": self.message,
        }


@dataclass(frozen=True)
class DriftReport:
    baseline_dataset_id: str | None = None
    findings: tuple[DriftFinding, ...] = ()

    @property
    def score(self) -> float:
        if not self.findings:
            return 1.0
        return ensure_probability(
            1.0 - max(finding.drift_score for finding in self.findings),
            what="drift score",
            clamp=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_dataset_id": self.baseline_dataset_id,
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class QualityContractRule:
    rule_id: str
    scope: str
    metric: str
    field_name: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    severity: str = "error"
    message: str | None = None

    def __post_init__(self) -> None:
        if self.min_value is None and self.max_value is None:
            raise ValueError(
                f"Quality contract rule {self.rule_id} must declare min_value or max_value"
            )
        if self.min_value is not None:
            object.__setattr__(
                self,
                "min_value",
                ensure_finite_float(self.min_value, what=f"{self.rule_id} min_value"),
            )
        if self.max_value is not None:
            object.__setattr__(
                self,
                "max_value",
                ensure_finite_float(self.max_value, what=f"{self.rule_id} max_value"),
            )
        if self.severity not in {"warning", "error"}:
            raise ValueError(
                f"Unsupported severity for quality contract rule {self.rule_id}: {self.severity}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "scope": self.scope,
            "metric": self.metric,
            "field_name": self.field_name,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class QualityContract:
    contract_name: str
    rules: tuple[QualityContractRule, ...]
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_name": self.contract_name,
            "source": self.source,
            "rules": [rule.to_dict() for rule in self.rules],
        }


@dataclass(frozen=True)
class QualityContractFailure:
    rule_id: str
    scope: str
    metric: str
    field_name: str | None
    severity: str
    expected: dict[str, float]
    actual: float | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "scope": self.scope,
            "metric": self.metric,
            "field_name": self.field_name,
            "severity": self.severity,
            "expected": dict(self.expected),
            "actual": self.actual,
            "message": self.message,
        }


@dataclass(frozen=True)
class QualityContractResult:
    contract_name: str
    passed: bool
    evaluated_rules: int
    failed_rules: int
    blocking_rules: int
    failures: tuple[QualityContractFailure, ...] = ()
    source: str | None = None

    @property
    def score(self) -> float:
        if self.evaluated_rules <= 0:
            return 1.0
        return ensure_probability(
            1.0 - (self.failed_rules / self.evaluated_rules),
            what="quality contract score",
            clamp=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_name": self.contract_name,
            "source": self.source,
            "passed": self.passed,
            "evaluated_rules": self.evaluated_rules,
            "failed_rules": self.failed_rules,
            "blocking_rules": self.blocking_rules,
            "score": self.score,
            "failures": [failure.to_dict() for failure in self.failures],
        }


@dataclass(frozen=True)
class QualityTrendPoint:
    dataset_id: str
    schema_id: str
    source_id: str | None
    validated_at: datetime
    score: float
    row_count: int
    completeness_score: float | None = None
    consistency_score: float | None = None
    tier: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", ensure_probability(self.score, what="trend score"))
        if self.row_count < 0:
            raise ValueError("row_count must be >= 0")
        if self.completeness_score is not None:
            object.__setattr__(
                self,
                "completeness_score",
                ensure_probability(self.completeness_score, what="trend completeness_score"),
            )
        if self.consistency_score is not None:
            object.__setattr__(
                self,
                "consistency_score",
                ensure_probability(self.consistency_score, what="trend consistency_score"),
            )

    @classmethod
    def from_any(cls, payload: Any) -> QualityTrendPoint:
        if isinstance(payload, QualityTrendPoint):
            return payload
        if isinstance(payload, Mapping):
            return cls(
                dataset_id=str(payload["dataset_id"]),
                schema_id=str(payload["schema_id"]),
                source_id=payload.get("source_id"),
                validated_at=parse_datetime_utc(
                    payload["validated_at"], what="quality trend validated_at"
                ),
                score=float(payload["score"]),
                row_count=int(payload.get("row_count", 0)),
                completeness_score=payload.get("completeness_score"),
                consistency_score=payload.get("consistency_score"),
                tier=payload.get("tier"),
            )
        return cls(
            dataset_id=str(payload.dataset_id),
            schema_id=str(payload.schema_id),
            source_id=getattr(payload, "source_id", None),
            validated_at=parse_datetime_utc(
                payload.validated_at, what="quality trend validated_at"
            ),
            score=float(payload.score),
            row_count=int(getattr(payload, "row_count", 0)),
            completeness_score=getattr(payload, "completeness_score", None),
            consistency_score=getattr(payload, "consistency_score", None),
            tier=getattr(getattr(payload, "tier", None), "value", getattr(payload, "tier", None)),
        )

    def series_key(self) -> str:
        return build_quality_series_key(
            dataset_id=self.dataset_id,
            schema_id=self.schema_id,
            source_id=self.source_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "schema_id": self.schema_id,
            "source_id": self.source_id,
            "validated_at": self.validated_at.isoformat(),
            "score": self.score,
            "row_count": self.row_count,
            "completeness_score": self.completeness_score,
            "consistency_score": self.consistency_score,
            "tier": self.tier,
        }


@dataclass(frozen=True)
class QualityTrendReport:
    series_key: str
    history: tuple[QualityTrendPoint, ...]
    score_delta: float | None
    row_count_delta: int | None
    regression_detected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "series_key": self.series_key,
            "history": [point.to_dict() for point in self.history],
            "score_delta": self.score_delta,
            "row_count_delta": self.row_count_delta,
            "regression_detected": self.regression_detected,
        }


def build_quality_series_key(
    *, dataset_id: str, schema_id: str, source_id: str | None = None
) -> str:
    if source_id:
        return f"{dataset_id}|{schema_id}|{source_id}"
    return f"{dataset_id}|{schema_id}"


def profile_dataframe(
    data: Any,
    schema: Any | None = None,
    *,
    max_top_values: int = 5,
    histogram_bins: int = 10,
) -> DatasetProfile:
    df = require_dataframe(data, allow_dict=True, label="quality profiling data")
    profiles: dict[str, ColumnProfile] = {}
    row_count = len(df)

    for column_name in df.columns:
        series = df[column_name]
        non_null = series.dropna()
        non_null_count = int(non_null.shape[0])
        distinct_count = int(non_null.nunique(dropna=True))
        null_rate = 1.0 if row_count == 0 else (row_count - non_null_count) / row_count
        cardinality_ratio = 0.0 if non_null_count == 0 else distinct_count / non_null_count
        expected_kind = _schema_expected_kind(schema, str(column_name))
        numeric = _finite_numeric_series(series)

        inferred_type = expected_kind or (
            "numeric"
            if pd.api.types.is_numeric_dtype(series.dtype)
            else "temporal"
            if pd.api.types.is_datetime64_any_dtype(series.dtype)
            else "categorical"
            if distinct_count <= max(20, int(row_count * 0.05))
            else "string"
        )

        quantiles: dict[str, float] = {}
        min_value = None
        max_value = None
        histogram: tuple[HistogramBin, ...] = ()
        if not numeric.empty:
            min_value = float(numeric.min())
            max_value = float(numeric.max())
            quantile_pairs = {
                "p05": 0.05,
                "p25": 0.25,
                "p50": 0.50,
                "p75": 0.75,
                "p95": 0.95,
            }
            quantiles = {
                name: float(numeric.quantile(quantile)) for name, quantile in quantile_pairs.items()
            }
            histogram = _numeric_histogram(numeric, bins=histogram_bins)
        elif not non_null.empty:
            min_value = _jsonable_value(non_null.min())
            max_value = _jsonable_value(non_null.max())

        profiles[str(column_name)] = ColumnProfile(
            column_name=str(column_name),
            pandas_dtype=str(series.dtype),
            inferred_type=inferred_type,
            null_rate=float(null_rate),
            non_null_count=non_null_count,
            distinct_count=distinct_count,
            cardinality_ratio=float(cardinality_ratio),
            type_stability=_series_type_stability(series, expected_kind=expected_kind),
            min_value=min_value,
            max_value=max_value,
            quantiles=quantiles,
            histogram=histogram,
            top_values=_top_values(series, limit=max_top_values),
        )

    return DatasetProfile(row_count=row_count, column_profiles=profiles)


def detect_anomalies(
    data: Any,
    *,
    zscore_threshold: float = 3.0,
    mad_threshold: float = 3.5,
    iqr_multiplier: float = 1.5,
    enable_isolation_forest: bool = False,
    max_samples_per_finding: int = 10,
) -> AnomalyReport:
    df = require_dataframe(data, allow_dict=True, label="quality anomaly detection data")
    findings: list[AnomalyFinding] = []
    detectors_used = ["zscore", "iqr", "mad"]

    for column_name in df.select_dtypes(include=["number"]).columns:
        series = _finite_numeric_series(df[column_name])
        if len(series) < 5:
            continue

        mean = float(series.mean())
        std = float(series.std(ddof=0))
        if is_finite_number(std) and std > 0:
            zscores = ((series - mean).abs() / std).fillna(0.0)
            anomaly_mask = zscores > zscore_threshold
            anomaly_count = int(anomaly_mask.sum())
            if anomaly_count > 0:
                findings.append(
                    AnomalyFinding(
                        column_name=str(column_name),
                        detector="zscore",
                        anomaly_count=anomaly_count,
                        anomaly_rate=anomaly_count / len(series),
                        threshold=zscore_threshold,
                        sample_indices=tuple(
                            int(idx) for idx in series[anomaly_mask].index[:max_samples_per_finding]
                        ),
                        message=f"z-score detected {anomaly_count} anomalous values",
                    )
                )

        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        if is_finite_number(iqr) and iqr > 0:
            lower = q1 - iqr_multiplier * iqr
            upper = q3 + iqr_multiplier * iqr
            anomaly_mask = (series < lower) | (series > upper)
            anomaly_count = int(anomaly_mask.sum())
            if anomaly_count > 0:
                findings.append(
                    AnomalyFinding(
                        column_name=str(column_name),
                        detector="iqr",
                        anomaly_count=anomaly_count,
                        anomaly_rate=anomaly_count / len(series),
                        threshold=iqr_multiplier,
                        sample_indices=tuple(
                            int(idx) for idx in series[anomaly_mask].index[:max_samples_per_finding]
                        ),
                        message=f"IQR detected {anomaly_count} anomalous values",
                    )
                )

        median = float(series.median())
        mad = float((series - median).abs().median())
        if is_finite_number(mad) and mad > 0:
            modified_z = 0.6745 * (series - median).abs() / mad
            anomaly_mask = modified_z > mad_threshold
            anomaly_count = int(anomaly_mask.sum())
            if anomaly_count > 0:
                findings.append(
                    AnomalyFinding(
                        column_name=str(column_name),
                        detector="mad",
                        anomaly_count=anomaly_count,
                        anomaly_rate=anomaly_count / len(series),
                        threshold=mad_threshold,
                        sample_indices=tuple(
                            int(idx) for idx in series[anomaly_mask].index[:max_samples_per_finding]
                        ),
                        message=f"MAD detected {anomaly_count} anomalous values",
                    )
                )

        if enable_isolation_forest and importlib.util.find_spec("sklearn") is not None:
            from sklearn.ensemble import IsolationForest  # type: ignore[import]

            if len(series) >= 10:
                model = IsolationForest(
                    contamination="auto",
                    random_state=42,
                )
                predictions = model.fit_predict(series.to_frame())
                anomaly_mask = predictions == -1
                anomaly_count = int(anomaly_mask.sum())
                if anomaly_count > 0:
                    detectors_used.append("isolation_forest")
                    anomalous_index = series.index[anomaly_mask]
                    findings.append(
                        AnomalyFinding(
                            column_name=str(column_name),
                            detector="isolation_forest",
                            anomaly_count=anomaly_count,
                            anomaly_rate=anomaly_count / len(series),
                            sample_indices=tuple(
                                int(idx) for idx in anomalous_index[:max_samples_per_finding]
                            ),
                            message=f"Isolation Forest detected {anomaly_count} anomalous values",
                        )
                    )

    unique_detectors = tuple(dict.fromkeys(detectors_used))
    return AnomalyReport(findings=tuple(findings), detectors_used=unique_detectors)


def _ks_drift(current: pd.Series, baseline: pd.Series) -> tuple[float, float]:
    if importlib.util.find_spec("scipy") is not None:
        from scipy.stats import ks_2samp  # type: ignore[import]

        result = ks_2samp(current, baseline)
        return float(result.statistic), float(result.pvalue)

    current_sorted = sorted(float(value) for value in current)
    baseline_sorted = sorted(float(value) for value in baseline)
    all_values = sorted(set(current_sorted + baseline_sorted))
    current_n = len(current_sorted)
    baseline_n = len(baseline_sorted)
    statistic = 0.0
    current_seen = 0
    baseline_seen = 0
    for value in all_values:
        while current_seen < current_n and current_sorted[current_seen] <= value:
            current_seen += 1
        while baseline_seen < baseline_n and baseline_sorted[baseline_seen] <= value:
            baseline_seen += 1
        statistic = max(
            statistic,
            abs((current_seen / current_n) - (baseline_seen / baseline_n)),
        )
    return float(statistic), 1.0


def _psi(current: pd.Series, baseline: pd.Series, *, bins: int) -> float:
    quantiles = pd.concat([baseline, current]).quantile([index / bins for index in range(bins + 1)])
    edges = sorted({float(value) for value in quantiles if is_finite_number(value)})
    if len(edges) < 2:
        return 0.0
    baseline_bins = pd.cut(baseline, bins=edges, include_lowest=True, duplicates="drop")
    current_bins = pd.cut(current, bins=edges, include_lowest=True, duplicates="drop")
    baseline_dist = baseline_bins.value_counts(normalize=True, sort=False)
    current_dist = current_bins.value_counts(normalize=True, sort=False)
    psi = 0.0
    for bucket in set(baseline_dist.index) | set(current_dist.index):
        expected = float(baseline_dist.get(bucket, 0.0)) or 1e-6
        actual = float(current_dist.get(bucket, 0.0)) or 1e-6
        psi += (actual - expected) * math.log(actual / expected)
    return max(float(psi), 0.0)


def _categorical_drift(current: pd.Series, baseline: pd.Series) -> tuple[float, float, float]:
    current_counts = current.astype(str).value_counts()
    baseline_counts = baseline.astype(str).value_counts()
    all_labels = sorted(set(current_counts.index) | set(baseline_counts.index))
    observed = [int(current_counts.get(label, 0)) for label in all_labels]
    expected = [int(baseline_counts.get(label, 0)) for label in all_labels]
    observed_total = sum(observed)
    expected_total = sum(expected)
    if observed_total <= 0 or expected_total <= 0:
        return 0.0, 1.0, 0.0

    observed_dist = [count / observed_total for count in observed]
    expected_dist = [count / expected_total for count in expected]
    tv_distance = 0.5 * sum(
        abs(left - right) for left, right in zip(observed_dist, expected_dist, strict=False)
    )

    if importlib.util.find_spec("scipy") is not None:
        from scipy.stats import chisquare  # type: ignore[import]

        expected_scaled = [max(1e-6, value * observed_total) for value in expected_dist]
        expected_total_scaled = sum(expected_scaled)
        if expected_total_scaled > 0:
            scale = observed_total / expected_total_scaled
            expected_scaled = [value * scale for value in expected_scaled]
        result = chisquare(f_obs=observed, f_exp=expected_scaled)
        return float(result.statistic), float(result.pvalue), float(tv_distance)

    return float(tv_distance), 1.0, float(tv_distance)


def detect_drift(
    current_data: Any,
    baseline_data: Any,
    *,
    schema: Any | None = None,
    baseline_dataset_id: str | None = None,
    psi_bins: int = 10,
) -> DriftReport:
    current_df = require_dataframe(current_data, allow_dict=True, label="current drift data")
    baseline_df = require_dataframe(baseline_data, allow_dict=True, label="baseline drift data")
    findings: list[DriftFinding] = []

    shared_columns = [column for column in current_df.columns if column in baseline_df.columns]
    for column_name in shared_columns:
        expected_kind = _schema_expected_kind(schema, str(column_name))
        current_series = current_df[column_name].dropna()
        baseline_series = baseline_df[column_name].dropna()
        if current_series.empty or baseline_series.empty:
            continue
        if expected_kind == "temporal":
            continue

        if expected_kind == "numeric" or (
            pd.api.types.is_numeric_dtype(current_df[column_name].dtype)
            and pd.api.types.is_numeric_dtype(baseline_df[column_name].dtype)
        ):
            current_numeric = _finite_numeric_series(current_series)
            baseline_numeric = _finite_numeric_series(baseline_series)
            if len(current_numeric) < 5 or len(baseline_numeric) < 5:
                continue
            ks_statistic, ks_p_value = _ks_drift(current_numeric, baseline_numeric)
            ks_detected = ks_p_value < 0.05 and ks_statistic >= 0.1
            findings.append(
                DriftFinding(
                    column_name=str(column_name),
                    test="ks",
                    detected=ks_detected,
                    statistic=ks_statistic,
                    p_value=ks_p_value,
                    drift_score=min(1.0, ks_statistic),
                    message=f"KS statistic={ks_statistic:.4f}, p={ks_p_value:.4f}",
                )
            )
            psi = _psi(current_numeric, baseline_numeric, bins=psi_bins)
            psi_detected = psi >= 0.2
            findings.append(
                DriftFinding(
                    column_name=str(column_name),
                    test="psi",
                    detected=psi_detected,
                    statistic=psi,
                    p_value=None,
                    drift_score=min(1.0, psi),
                    message=f"PSI={psi:.4f}",
                )
            )
            continue

        chi_statistic, chi_p_value, tv_distance = _categorical_drift(
            current_series, baseline_series
        )
        detected = chi_p_value < 0.05 and tv_distance >= 0.1
        findings.append(
            DriftFinding(
                column_name=str(column_name),
                test="chi_squared",
                detected=detected,
                statistic=chi_statistic,
                p_value=chi_p_value,
                drift_score=min(1.0, tv_distance),
                message=f"chi_squared statistic={chi_statistic:.4f}, p={chi_p_value:.4f}, tv_distance={tv_distance:.4f}",
            )
        )

    return DriftReport(
        baseline_dataset_id=baseline_dataset_id,
        findings=tuple(findings),
    )


def load_quality_contract(
    spec: str | Path | Mapping[str, Any] | QualityContract,
) -> QualityContract:
    if isinstance(spec, QualityContract):
        return spec

    payload: Mapping[str, Any]
    source: str | None = None
    if isinstance(spec, Mapping):
        payload = spec
    else:
        text = None
        path_candidate: Path | None = None
        if isinstance(spec, Path):
            path_candidate = spec
        else:
            spec_text = str(spec)
            if "\n" not in spec_text and len(spec_text) < 240:
                path_candidate = Path(spec_text)
        if path_candidate is not None and path_candidate.exists():
            text = path_candidate.read_text(encoding="utf-8")
            source = str(path_candidate)
        else:
            text = str(spec)
            source = "<inline>"
        import yaml

        loaded = yaml.safe_load(text)
        if not isinstance(loaded, Mapping):
            raise ValueError("Quality contract YAML must define a mapping")
        payload = loaded

    contract_name = str(
        payload.get("name") or payload.get("contract_name") or "fabric_quality_contract"
    )
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("Quality contract must define at least one rule")

    rules: list[QualityContractRule] = []
    for index, entry in enumerate(raw_rules):
        if not isinstance(entry, Mapping) or len(entry) != 1:
            raise ValueError("Each quality contract rule must be a single-key mapping")
        expectation_name, params = next(iter(entry.items()))
        if not isinstance(params, Mapping):
            raise ValueError(
                f"Quality contract rule {expectation_name} must map to rule parameters"
            )
        rules.append(_parse_expectation_rule(expectation_name, params, index=index))

    return QualityContract(
        contract_name=contract_name,
        rules=tuple(rules),
        source=source or (str(payload.get("source")) if payload.get("source") else None),
    )


def _parse_expectation_rule(
    expectation_name: str, params: Mapping[str, Any], *, index: int
) -> QualityContractRule:
    severity = str(params.get("severity", "error")).lower()
    message = params.get("message")
    field_name = params.get("column") or params.get("field")
    rule_id = str(params.get("id", f"rule_{index + 1}"))

    mapping: dict[str, tuple[str, str]] = {
        "expect_column_null_rate_to_be_between": ("profile", "null_rate"),
        "expect_column_distinct_count_to_be_between": ("profile", "distinct_count"),
        "expect_column_cardinality_ratio_to_be_between": ("profile", "cardinality_ratio"),
        "expect_column_type_stability_to_be_at_least": ("profile", "type_stability"),
        "expect_column_anomaly_rate_to_be_below": ("anomaly", "anomaly_rate"),
        "expect_column_drift_score_to_be_below": ("drift", "drift_score"),
        "expect_dataset_score_to_be_at_least": ("dataset", "score"),
        "expect_dataset_completeness_to_be_at_least": ("dataset", "completeness_score"),
        "expect_dataset_consistency_to_be_at_least": ("dataset", "consistency_score"),
    }
    if expectation_name not in mapping:
        raise ValueError(f"Unsupported quality contract expectation: {expectation_name}")
    scope, metric = mapping[expectation_name]
    min_value = params.get("min")
    max_value = params.get("max")

    if expectation_name.endswith("_to_be_at_least") and min_value is None and max_value is None:
        min_value = params.get("value")
    if expectation_name.endswith("_to_be_below") and min_value is None and max_value is None:
        max_value = params.get("value")

    return QualityContractRule(
        rule_id=rule_id,
        scope=scope,
        metric=metric,
        field_name=str(field_name) if field_name is not None else None,
        min_value=min_value,
        max_value=max_value,
        severity=severity,
        message=str(message) if message is not None else None,
    )


def evaluate_quality_contract(
    contract: QualityContract,
    *,
    dataset_id: str,
    schema_id: str,
    source_id: str | None,
    score: float,
    completeness_score: float,
    consistency_score: float,
    row_count: int,
    dataset_profile: DatasetProfile | None,
    anomaly_report: AnomalyReport | None,
    drift_report: DriftReport | None,
) -> QualityContractResult:
    profile_map = dataset_profile.column_profiles if dataset_profile is not None else {}
    anomaly_by_column: dict[str, float] = {}
    if anomaly_report is not None:
        for finding in anomaly_report.findings:
            anomaly_by_column[finding.column_name] = max(
                anomaly_by_column.get(finding.column_name, 0.0),
                finding.anomaly_rate,
            )
    drift_by_column: dict[str, float] = {}
    if drift_report is not None:
        for finding in drift_report.findings:
            drift_by_column[finding.column_name] = max(
                drift_by_column.get(finding.column_name, 0.0),
                finding.drift_score,
            )

    failures: list[QualityContractFailure] = []
    blocking_rules = 0
    for rule in contract.rules:
        actual = _resolve_contract_metric(
            rule=rule,
            dataset_id=dataset_id,
            schema_id=schema_id,
            source_id=source_id,
            row_count=row_count,
            score=score,
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            profile_map=profile_map,
            anomaly_by_column=anomaly_by_column,
            drift_by_column=drift_by_column,
            dataset_profile=dataset_profile,
            anomaly_report=anomaly_report,
            drift_report=drift_report,
        )
        failure_message = _check_contract_bounds(rule, actual)
        if failure_message is None:
            continue
        if rule.severity == "error":
            blocking_rules += 1
        failures.append(
            QualityContractFailure(
                rule_id=rule.rule_id,
                scope=rule.scope,
                metric=rule.metric,
                field_name=rule.field_name,
                severity=rule.severity,
                expected={
                    name: value
                    for name, value in {
                        "min": rule.min_value,
                        "max": rule.max_value,
                    }.items()
                    if value is not None
                },
                actual=actual,
                message=rule.message or failure_message,
            )
        )

    return QualityContractResult(
        contract_name=contract.contract_name,
        passed=len(failures) == 0,
        evaluated_rules=len(contract.rules),
        failed_rules=len(failures),
        blocking_rules=blocking_rules,
        failures=tuple(failures),
        source=contract.source,
    )


def _resolve_contract_metric(
    *,
    rule: QualityContractRule,
    dataset_id: str,
    schema_id: str,
    source_id: str | None,
    row_count: int,
    score: float,
    completeness_score: float,
    consistency_score: float,
    profile_map: Mapping[str, ColumnProfile],
    anomaly_by_column: Mapping[str, float],
    drift_by_column: Mapping[str, float],
    dataset_profile: DatasetProfile | None,
    anomaly_report: AnomalyReport | None,
    drift_report: DriftReport | None,
) -> float | None:
    if rule.scope == "dataset":
        values = {
            "score": score,
            "completeness_score": completeness_score,
            "consistency_score": consistency_score,
            "row_count": float(row_count),
            "profile_score": dataset_profile.profile_score if dataset_profile else None,
            "anomaly_score": anomaly_report.score if anomaly_report else None,
            "drift_score": drift_report.score if drift_report else None,
        }
        value = values.get(rule.metric)
        return None if value is None else float(value)

    if rule.field_name is None:
        return None

    if rule.scope == "profile":
        profile = profile_map.get(rule.field_name)
        if profile is None:
            return None
        if rule.metric in {"null_rate", "cardinality_ratio", "type_stability"}:
            return float(getattr(profile, rule.metric))
        if rule.metric == "distinct_count":
            return float(profile.distinct_count)
        if rule.metric in profile.quantiles:
            return float(profile.quantiles[rule.metric])
        return None

    if rule.scope == "anomaly":
        return anomaly_by_column.get(rule.field_name)

    if rule.scope == "drift":
        return drift_by_column.get(rule.field_name)

    return None


def _check_contract_bounds(rule: QualityContractRule, actual: float | None) -> str | None:
    if actual is None:
        return (
            f"Quality contract rule {rule.rule_id} could not be evaluated for "
            f"{rule.scope}:{rule.metric}"
        )
    if rule.min_value is not None and actual < rule.min_value:
        return f"{rule.scope}:{rule.metric}={actual:.4f} is below minimum {rule.min_value:.4f}"
    if rule.max_value is not None and actual > rule.max_value:
        return f"{rule.scope}:{rule.metric}={actual:.4f} exceeds maximum {rule.max_value:.4f}"
    return None


def build_quality_trend_report(
    *,
    dataset_id: str,
    schema_id: str,
    source_id: str | None,
    current_point: QualityTrendPoint,
    history: Iterable[QualityTrendPoint | Mapping[str, Any] | Any] | None = None,
) -> QualityTrendReport | None:
    series_key = build_quality_series_key(
        dataset_id=dataset_id,
        schema_id=schema_id,
        source_id=source_id,
    )
    trend_points: list[QualityTrendPoint] = []
    if history is not None:
        for item in history:
            point = QualityTrendPoint.from_any(item)
            if point.series_key() == series_key:
                trend_points.append(point)
    trend_points.append(current_point)
    trend_points.sort(key=lambda item: item.validated_at)

    if len(trend_points) < 2:
        return QualityTrendReport(
            series_key=series_key,
            history=tuple(trend_points),
            score_delta=None,
            row_count_delta=None,
            regression_detected=False,
        )

    previous = trend_points[-2]
    current = trend_points[-1]
    score_delta = round(current.score - previous.score, 6)
    row_count_delta = current.row_count - previous.row_count
    regression_detected = score_delta < -0.05
    return QualityTrendReport(
        series_key=series_key,
        history=tuple(trend_points),
        score_delta=score_delta,
        row_count_delta=row_count_delta,
        regression_detected=regression_detected,
    )


__all__ = [
    "AnomalyFinding",
    "AnomalyReport",
    "ColumnProfile",
    "DatasetProfile",
    "DriftFinding",
    "DriftReport",
    "HistogramBin",
    "QualityContract",
    "QualityContractFailure",
    "QualityContractResult",
    "QualityContractRule",
    "QualityTrendPoint",
    "QualityTrendReport",
    "TopValue",
    "build_quality_series_key",
    "build_quality_trend_report",
    "detect_anomalies",
    "detect_drift",
    "evaluate_quality_contract",
    "load_quality_contract",
    "profile_dataframe",
]
