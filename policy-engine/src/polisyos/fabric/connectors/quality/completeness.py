"""
Completeness analysis for data quality validation.

Checks:
1. Null percentage vs schema.expected_completeness
2. Gap detection in time series
3. Coverage metrics (actual rows vs expected rows)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.fabric.quality.finite import ensure_non_negative_finite, ensure_probability

from .report import CompletenessResult, RuleViolation

logger = get_logger(__name__)

SEVERITY_WEIGHTS = {"error": 1.0, "warning": 0.6, "info": 0.3}


@dataclass
class DateGap:
    """Detected gap in time series."""

    start: datetime
    end: datetime
    expected_count: int
    actual_count: int

    @property
    def missing_count(self) -> int:
        return self.expected_count - self.actual_count


class CompletenessAnalyzer:
    """
    Detects missing values and data gaps.

    Uses vectorized pandas operations for efficiency.
    """

    def __init__(self, *, confidence: float = 1.0) -> None:
        self.confidence = ensure_probability(confidence, what="completeness confidence")

    def analyze(
        self,
        data: pd.DataFrame,
        schema: Any,
        expected_row_count: int | None = None,
        *,
        time_series: pd.Series | None = None,
    ) -> CompletenessResult:
        violations: list[RuleViolation] = []
        penalty = 0.0
        hard_fail = False

        field_completeness: dict[str, float] = {}
        schema_fields = tuple(getattr(schema, "fields", ()) or ())
        if not schema_fields:
            return CompletenessResult(
                score=1.0,
                field_completeness={},
                violations=[],
                gaps_detected=0,
                penalty=0.0,
                hard_fail=False,
                applicable=False,
                confidence=0.0,
                not_applicable_reason="schema has no fields",
            )

        null_violations, null_penalty, null_hard_fail = self._check_null_percentage(
            data, schema, field_completeness
        )
        violations.extend(null_violations)
        penalty += null_penalty
        hard_fail = hard_fail or null_hard_fail

        gaps_detected = 0
        if self._has_time_dimension(schema):
            time_field = self._get_time_field(schema)
            if time_field and time_field in data.columns:
                gaps = self._detect_gaps(data, time_field, schema, time_series)
                gaps_detected = len(gaps)
                for gap in gaps:
                    missing_ratio = 0.0
                    if gap.expected_count > 0:
                        missing_ratio = gap.missing_count / gap.expected_count
                    severity = "warning" if missing_ratio <= 0.2 else "error"
                    violations.append(
                        RuleViolation(
                            rule_type="completeness",
                            field_name=time_field,
                            severity=severity,
                            message=(
                                f"Time series gap detected: {gap.missing_count} missing points"
                            ),
                            expected=gap.expected_count,
                            actual=gap.actual_count,
                        )
                    )
                    penalty += missing_ratio * SEVERITY_WEIGHTS[severity]

        if expected_row_count is not None:
            expected_rows = ensure_non_negative_finite(
                expected_row_count,
                what="expected_row_count",
            )
            if expected_rows <= 0:
                expected_rows = 0.0
        else:
            expected_rows = 0.0

        if expected_rows > 0:
            coverage = len(data) / expected_rows
            if coverage < 0.9:
                severity = "warning" if coverage > 0.7 else "error"
                violations.append(
                    RuleViolation(
                        rule_type="completeness",
                        field_name=None,
                        severity=severity,
                        message=(
                            f"Low coverage: {len(data)} / {expected_row_count} rows ({coverage:.1%})"
                        ),
                        expected=expected_row_count,
                        actual=len(data),
                    )
                )
                penalty += (1.0 - coverage) * SEVERITY_WEIGHTS[severity]

        if field_completeness:
            avg_completeness = sum(field_completeness.values()) / len(field_completeness)
        else:
            avg_completeness = 0.0

        required_completeness = getattr(schema, "required_completeness", None)
        if required_completeness is not None:
            if avg_completeness < required_completeness:
                gap = required_completeness - avg_completeness
                severity = "warning" if gap <= 0.1 else "error"
                violations.append(
                    RuleViolation(
                        rule_type="completeness",
                        field_name=None,
                        severity=severity,
                        message=(
                            f"Overall completeness {avg_completeness:.1%} < required {required_completeness:.1%}"
                        ),
                        expected=required_completeness,
                        actual=avg_completeness,
                    )
                )
                penalty += gap * SEVERITY_WEIGHTS[severity]

        score = ensure_probability(
            avg_completeness - penalty, what="completeness score", clamp=True
        )
        if hard_fail:
            score = 0.0

        return CompletenessResult(
            score=score,
            field_completeness=field_completeness,
            violations=violations,
            gaps_detected=gaps_detected,
            penalty=penalty,
            hard_fail=hard_fail,
            applicable=True,
            confidence=self.confidence,
        )

    def _check_null_percentage(
        self,
        data: pd.DataFrame,
        schema: Any,
        field_completeness: dict[str, float],
    ) -> tuple[list[RuleViolation], float, bool]:
        violations: list[RuleViolation] = []
        penalty = 0.0
        hard_fail = False

        allowed_null_fields = set(getattr(schema, "allowed_null_fields", ()) or ())

        for field in schema.fields:
            if field.name not in data.columns:
                field_completeness[field.name] = 0.0
                violations.append(
                    RuleViolation(
                        rule_type="completeness",
                        field_name=field.name,
                        severity="error",
                        message=f"Missing required field: {field.name}",
                        expected="field present",
                        actual="field missing",
                    )
                )
                penalty += SEVERITY_WEIGHTS["error"]
                hard_fail = True
                continue

            actual_completeness = (
                0.0 if len(data[field.name]) == 0 else 1.0 - data[field.name].isna().mean()
            )
            actual_completeness = ensure_probability(
                actual_completeness,
                what=f"actual completeness {field.name}",
            )
            field_completeness[field.name] = actual_completeness

            if field.name in allowed_null_fields:
                continue

            expected_completeness = getattr(field, "expected_completeness", 1.0)
            expected_completeness = ensure_probability(
                expected_completeness,
                what=f"expected completeness {field.name}",
            )
            if actual_completeness < expected_completeness:
                gap = expected_completeness - actual_completeness
                if (
                    not getattr(field, "nullable", True) and actual_completeness < 1.0
                ) or gap > 0.2:
                    severity = "error"
                elif gap > 0.1:
                    severity = "warning"
                else:
                    severity = "info"

                violations.append(
                    RuleViolation(
                        rule_type="completeness",
                        field_name=field.name,
                        severity=severity,
                        message=(
                            f"Completeness {actual_completeness:.1%} < expected {expected_completeness:.1%}"
                        ),
                        expected=expected_completeness,
                        actual=actual_completeness,
                    )
                )
                penalty += gap * SEVERITY_WEIGHTS[severity]

        return violations, penalty, hard_fail

    def _detect_gaps(
        self,
        data: pd.DataFrame,
        time_field: str,
        schema: Any,
        time_series: pd.Series | None,
    ) -> list[DateGap]:
        gaps: list[DateGap] = []

        series = time_series if time_series is not None else data[time_field]
        time_values = pd.to_datetime(series, errors="coerce").dropna()

        if len(time_values) < 2:
            return gaps

        time_values = time_values.sort_values()

        freq = self._get_frequency(schema, time_values)
        if freq is None:
            return gaps

        expected_range = pd.date_range(
            start=time_values.min(),
            end=time_values.max(),
            freq=freq,
        )

        existing_values = pd.DatetimeIndex(time_values.unique())
        missing_dates = expected_range.difference(existing_values)

        if len(missing_dates) > 0:
            gaps.append(
                DateGap(
                    start=missing_dates.min(),
                    end=missing_dates.max(),
                    expected_count=len(expected_range),
                    actual_count=len(existing_values),
                )
            )

        return gaps

    @staticmethod
    def _get_frequency(schema: Any, time_values: pd.Series) -> str | None:
        granularity = getattr(schema, "time_granularity", None)
        if granularity is not None:
            try:
                return granularity.to_pandas_freq()
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)
        return CompletenessAnalyzer._infer_frequency(time_values)

    @staticmethod
    def _infer_frequency(time_series: pd.Series) -> str | None:
        if len(time_series) < 3:
            return None

        diffs = time_series.diff().dropna()
        median_diff = diffs.median()
        if not isinstance(median_diff, timedelta):
            return None

        seconds = median_diff.total_seconds()

        if seconds <= 1:
            return "S"
        if seconds <= 60:
            return "min"
        if seconds <= 3600:
            return "H"
        if seconds <= 86400:
            return "D"
        days = median_diff.days
        if days <= 7:
            return "W"
        if days <= 31:
            return "MS"
        if days <= 92:
            return "QS"
        return "YS"

    @staticmethod
    def _has_time_dimension(schema: Any) -> bool:
        if getattr(schema, "time_dimension", None):
            return True
        for field in schema.fields:
            from polisyos.fabric.connectors.contracts.schema import SemanticType

            if field.semantic_type == SemanticType.TEMPORAL:
                return True
            if hasattr(field, "data_type") and field.data_type.is_temporal():
                return True
        return False

    @staticmethod
    def _get_time_field(schema: Any) -> str | None:
        time_dimension = getattr(schema, "time_dimension", None)
        if time_dimension:
            return time_dimension
        for field in schema.fields:
            from polisyos.fabric.connectors.contracts.schema import SemanticType

            if field.semantic_type == SemanticType.TEMPORAL:
                return field.name
            if hasattr(field, "data_type") and field.data_type.is_temporal():
                return field.name
        return None


@dataclass
class SamplingConfig:
    """Configuration for data sampling."""

    threshold: int = 100_000
    strategy: str = "random"
    confidence: float = 0.95
    margin: float = 0.01


class SamplingStrategy:
    """
    Sampling strategies for large datasets.

    Tradeoff: Validation speed vs accuracy.
    """

    @staticmethod
    def should_sample(row_count: int, threshold: int = 100_000) -> bool:
        return row_count > threshold

    @staticmethod
    def compute_sample_size(
        row_count: int,
        confidence: float = 0.95,
        margin: float = 0.01,
    ) -> int:
        z = 1.96
        p = 0.5
        n = (z**2 * p * (1 - p)) / (margin**2)
        return min(int(n), row_count)

    @staticmethod
    def sample_data(
        data: pd.DataFrame,
        strategy: str = "random",
        sample_size: int | None = None,
    ) -> tuple[pd.DataFrame, bool]:
        if sample_size is None or sample_size >= len(data):
            return data, False

        if strategy == "random":
            return data.sample(n=sample_size, random_state=42), True
        if strategy == "systematic":
            step = len(data) // sample_size
            return data.iloc[::step][:sample_size], True
        raise ValueError(f"Unknown strategy: {strategy}")
