from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from functools import total_ordering
from typing import Any

import pandas as pd


@total_ordering
class QualityLevel(Enum):
    """
    Quality classification levels for data fitness.

    Ordered from best to worst for comparison operations.
    """

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNUSABLE = "unusable"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, QualityLevel):
            return NotImplemented
        order = ["unusable", "poor", "acceptable", "good", "excellent"]
        return order.index(self.value) < order.index(other.value)

    def is_passing(self) -> bool:
        """Return True if level is acceptable or better."""
        return self in {
            QualityLevel.EXCELLENT,
            QualityLevel.GOOD,
            QualityLevel.ACCEPTABLE,
        }


@dataclass(frozen=True)
class QualityThresholds:
    """
    Configurable thresholds for quality level determination.

    Each profile (FAST/MVP/STRICT) provides different thresholds.
    Thresholds define boundaries between quality levels.
    """

    missingness_excellent: float = 0.01
    missingness_good: float = 0.05
    missingness_acceptable: float = 0.10
    missingness_poor: float = 0.20

    staleness_excellent: int = 7
    staleness_good: int = 30
    staleness_acceptable: int = 60
    staleness_poor: int = 90

    coverage_excellent: float = 0.99
    coverage_good: float = 0.95
    coverage_acceptable: float = 0.85
    coverage_poor: float = 0.70

    min_row_count: int = 10
    schema_drift_penalty: int = 2
    outlier_ratio_warning: float = 0.05

    @classmethod
    def for_profile(cls, profile_level: str | Enum | None) -> "QualityThresholds":
        """
        Return thresholds appropriate for profile.

        FAST: Loose thresholds for rapid iteration
        MVP: Balanced thresholds for standard validation
        STRICT: Tight thresholds for production/compliance
        """
        level_value = getattr(profile_level, "value", profile_level)
        level = str(level_value or "mvp").lower()
        if level == "fast":
            return cls(
                missingness_excellent=0.05,
                missingness_good=0.10,
                missingness_acceptable=0.20,
                missingness_poor=0.30,
                staleness_excellent=30,
                staleness_good=60,
                staleness_acceptable=120,
                staleness_poor=180,
                coverage_excellent=0.95,
                coverage_good=0.85,
                coverage_acceptable=0.70,
                coverage_poor=0.50,
                min_row_count=5,
            )
        if level == "strict":
            return cls(
                missingness_excellent=0.005,
                missingness_good=0.01,
                missingness_acceptable=0.05,
                missingness_poor=0.10,
                staleness_excellent=3,
                staleness_good=7,
                staleness_acceptable=14,
                staleness_poor=30,
                coverage_excellent=0.999,
                coverage_good=0.99,
                coverage_acceptable=0.95,
                coverage_poor=0.90,
                min_row_count=100,
            )
        return cls()

    def with_overrides(self, overrides: dict[str, Any]) -> "QualityThresholds":
        """Return a new thresholds instance with overrides applied."""
        return replace(self, **overrides)


@dataclass
class QualityIndicators:
    """
    Quality indicators for a dataset or metric.

    Captures objective measurements about data quality that can be
    compared against thresholds to determine fitness for simulation.
    """

    metric_id: str
    missingness: float
    staleness_days: int
    coverage: float
    row_count: int
    schema_drift: bool = False
    outlier_ratio: float = 0.0
    computed_at: datetime = field(default_factory=datetime.utcnow)
    computation_method: str = "pandas"

    def overall_level(
        self,
        thresholds: QualityThresholds | None = None,
    ) -> QualityLevel:
        """
        Compute overall quality level using weighted scoring.

        Algorithm:
        1. Score each dimension (missingness, staleness, coverage) from -1 to +3
        2. Apply penalties for schema drift and row count
        3. Map total score to QualityLevel
        """
        thresholds = thresholds or QualityThresholds()
        score = 0

        if self.row_count < thresholds.min_row_count:
            return QualityLevel.UNUSABLE

        if self.missingness <= thresholds.missingness_excellent:
            score += 3
        elif self.missingness <= thresholds.missingness_good:
            score += 2
        elif self.missingness <= thresholds.missingness_acceptable:
            score += 1
        elif self.missingness <= thresholds.missingness_poor:
            score += 0
        else:
            score -= 1

        if self.staleness_days <= thresholds.staleness_excellent:
            score += 3
        elif self.staleness_days <= thresholds.staleness_good:
            score += 2
        elif self.staleness_days <= thresholds.staleness_acceptable:
            score += 1
        elif self.staleness_days <= thresholds.staleness_poor:
            score += 0
        else:
            score -= 1

        if self.coverage >= thresholds.coverage_excellent:
            score += 3
        elif self.coverage >= thresholds.coverage_good:
            score += 2
        elif self.coverage >= thresholds.coverage_acceptable:
            score += 1
        elif self.coverage >= thresholds.coverage_poor:
            score += 0
        else:
            score -= 1

        if self.schema_drift:
            score -= thresholds.schema_drift_penalty

        if score >= 8:
            return QualityLevel.EXCELLENT
        if score >= 5:
            return QualityLevel.GOOD
        if score >= 2:
            return QualityLevel.ACCEPTABLE
        if score >= -1:
            return QualityLevel.POOR
        return QualityLevel.UNUSABLE

    def get_failure_reasons(
        self,
        thresholds: QualityThresholds | None = None,
    ) -> list[str]:
        """Generate a human-readable list of quality concerns."""
        thresholds = thresholds or QualityThresholds()
        reasons: list[str] = []

        if self.row_count < thresholds.min_row_count:
            reasons.append(
                f"Insufficient rows: {self.row_count} < {thresholds.min_row_count} minimum"
            )

        if self.missingness > thresholds.missingness_acceptable:
            pct = self.missingness * 100
            reasons.append(f"High missingness: {pct:.1f}% null values")

        if self.staleness_days > thresholds.staleness_acceptable:
            reasons.append(f"Stale data: {self.staleness_days} days since last update")

        if self.coverage < thresholds.coverage_acceptable:
            pct = self.coverage * 100
            reasons.append(f"Low coverage: only {pct:.1f}% of expected records")

        if self.schema_drift:
            reasons.append("Schema drift detected: columns changed since baseline")

        if self.outlier_ratio > thresholds.outlier_ratio_warning:
            pct = self.outlier_ratio * 100
            reasons.append(f"High outlier ratio: {pct:.1f}% of values are outliers")

        return reasons

    @classmethod
    def from_quality_report(
        cls,
        report: "DataQualityReport",
    ) -> "QualityIndicators":
        """
        Create QualityIndicators from a DataQualityReport.

        This enables connector-specific quality metrics to flow
        into the existing governance system.
        """
        staleness_days = 0
        if report.freshness_status.data_age_seconds is not None:
            staleness_days = report.freshness_status.data_age_seconds // 86400
        elif report.freshness_status.cache_age_seconds:
            staleness_days = report.freshness_status.cache_age_seconds // 86400

        missingness = max(0.0, min(1.0, 1.0 - report.completeness_score))

        coverage = 1.0
        schema_drift = False

        outlier_ratio = 0.0
        if report.violations:
            bounds_violations = [
                v
                for v in report.violations
                if "minimum" in v.message.lower() or "maximum" in v.message.lower()
            ]
            if bounds_violations:
                outlier_ratio = min(0.2, len(bounds_violations) * 0.02)

        return cls(
            metric_id=report.dataset_id,
            missingness=missingness,
            staleness_days=int(staleness_days),
            coverage=coverage,
            row_count=report.row_count,
            schema_drift=schema_drift,
            outlier_ratio=outlier_ratio,
            computed_at=report.validated_at,
            computation_method="connector_quality_validator",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        return {
            "metric_id": self.metric_id,
            "missingness": self.missingness,
            "staleness_days": self.staleness_days,
            "coverage": self.coverage,
            "row_count": self.row_count,
            "schema_drift": self.schema_drift,
            "outlier_ratio": self.outlier_ratio,
            "computed_at": self.computed_at.isoformat(),
            "computation_method": self.computation_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityIndicators":
        """Deserialize from JSON storage."""
        computed_at = data.get("computed_at")
        if computed_at:
            parsed_time = datetime.fromisoformat(computed_at)
        else:
            parsed_time = datetime.utcnow()
        return cls(
            metric_id=data["metric_id"],
            missingness=float(data["missingness"]),
            staleness_days=int(data["staleness_days"]),
            coverage=float(data["coverage"]),
            row_count=int(data["row_count"]),
            schema_drift=bool(data.get("schema_drift", False)),
            outlier_ratio=float(data.get("outlier_ratio", 0.0)),
            computed_at=parsed_time,
            computation_method=str(data.get("computation_method", "pandas")),
        )


def compute_quality_indicators(
    df: pd.DataFrame,
    metric_id: str,
    *,
    last_updated: datetime | None = None,
    expected_row_count: int | None = None,
    baseline_columns: set[str] | None = None,
) -> QualityIndicators:
    """
    Compute quality indicators from a pandas DataFrame.

    This is the primary computation function for Phase 13.
    For large datasets, use `compute_quality_from_duckdb` instead.
    """
    row_count = len(df)

    total_cells = row_count * len(df.columns)
    if total_cells > 0:
        null_cells = df.isnull().sum().sum()
        missingness = float(null_cells) / float(total_cells)
    else:
        missingness = 1.0

    if last_updated is None:
        staleness_days = 0
    else:
        staleness_days = (datetime.utcnow() - last_updated).days

    if expected_row_count is not None and expected_row_count > 0:
        coverage = min(1.0, row_count / expected_row_count)
    else:
        coverage = 1.0

    schema_drift = False
    if baseline_columns is not None:
        schema_drift = set(df.columns) != baseline_columns

    outlier_ratio = 0.0
    numeric_cols = df.select_dtypes(include=["number"]).columns
    if len(numeric_cols) > 0 and row_count > 4:
        outlier_count = 0
        total_numeric_values = 0
        for col in numeric_cols:
            values = df[col].dropna()
            if len(values) > 4:
                q1 = values.quantile(0.25)
                q3 = values.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outlier_count += int(((values < lower) | (values > upper)).sum())
                total_numeric_values += len(values)
        if total_numeric_values > 0:
            outlier_ratio = outlier_count / total_numeric_values

    return QualityIndicators(
        metric_id=metric_id,
        missingness=missingness,
        staleness_days=staleness_days,
        coverage=float(coverage),
        row_count=row_count,
        schema_drift=schema_drift,
        outlier_ratio=outlier_ratio,
        computation_method="pandas",
    )


def compute_quality_from_duckdb(
    db_path: str,
    table_name: str,
    metric_id: str,
    *,
    last_updated: datetime | None = None,
    expected_row_count: int | None = None,
) -> QualityIndicators:
    """
    Compute quality indicators directly from DuckDB (for large datasets).
    """
    import duckdb

    conn = duckdb.connect(db_path, read_only=True)
    try:
        row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        columns_info = conn.execute(f"DESCRIBE {table_name}").fetchall()
        column_names = [col[0] for col in columns_info]

        if row_count > 0 and len(column_names) > 0:
            null_checks = " + ".join(
                [f"CASE WHEN {col} IS NULL THEN 1 ELSE 0 END" for col in column_names]
            )
            total_nulls = (
                conn.execute(f"SELECT SUM({null_checks}) FROM {table_name}")
                .fetchone()[0]
                or 0
            )
            total_cells = row_count * len(column_names)
            missingness = total_nulls / total_cells
        else:
            missingness = 1.0

        if last_updated is not None:
            staleness_days = (datetime.utcnow() - last_updated).days
        else:
            staleness_days = 0

        if expected_row_count is not None and expected_row_count > 0:
            coverage = min(1.0, row_count / expected_row_count)
        else:
            coverage = 1.0

        return QualityIndicators(
            metric_id=metric_id,
            missingness=float(missingness),
            staleness_days=staleness_days,
            coverage=float(coverage),
            row_count=row_count,
            schema_drift=False,
            outlier_ratio=0.0,
            computation_method="duckdb",
        )
    finally:
        conn.close()


def get_cached_quality_indicators(
    metric_id: str,
    catalog_registry: Any,
) -> QualityIndicators | None:
    """
    Retrieve pre-computed quality indicators from catalog metadata.

    Uses registry access if available. Returns None when missing.
    """
    if catalog_registry is None:
        return None

    contract = None
    if hasattr(catalog_registry, "get_contract"):
        try:
            contract = catalog_registry.get_contract(metric_id)
        except Exception:
            return None
    elif hasattr(catalog_registry, "get"):
        try:
            contract = catalog_registry.get(metric_id)
        except Exception:
            return None

    if contract is None:
        return None

    metadata = getattr(contract, "metadata", None)
    if not isinstance(metadata, dict):
        return None

    quality_stats = metadata.get("quality_indicators") or metadata.get("quality_stats")
    if quality_stats is None:
        return None

    try:
        return QualityIndicators.from_dict(quality_stats)
    except Exception:
        return None
