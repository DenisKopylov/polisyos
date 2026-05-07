"""
Missing value imputation transformations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from polisyos.fabric.connectors.transform._common import (
    build_lineage,
    copy_if_needed,
    stage_started_at,
)
from polisyos.fabric.connectors.transform.pipeline import (
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
)
from polisyos.fabric.quality.finite import ensure_probability, is_finite_number

__all__ = [
    "ImputationStrategy",
    "ImputationTransform",
    "detect_missing_pattern",
    "recommend_imputation_strategy",
    "validate_imputation_quality",
]


class ImputationStrategy:
    """Supported imputation strategies."""

    FORWARD_FILL = "ffill"
    BACKWARD_FILL = "bfill"
    LINEAR = "linear"
    SPLINE = "spline"
    MEAN = "mean"
    MEDIAN = "median"
    ZERO = "zero"
    CONSTANT = "constant"

    @classmethod
    def all_strategies(cls) -> list[str]:
        return [
            cls.FORWARD_FILL,
            cls.BACKWARD_FILL,
            cls.LINEAR,
            cls.SPLINE,
            cls.MEAN,
            cls.MEDIAN,
            cls.ZERO,
            cls.CONSTANT,
        ]


@dataclass
class ImputationTransform(DataTransform):
    """Fill missing values using statistical methods."""

    strategy: str = "linear"
    target_fields: list[str] | None = None
    max_missing_pct: float = 0.3
    strict: bool = False
    fill_value: float | None = None

    def __post_init__(self) -> None:
        if self.strategy not in ImputationStrategy.all_strategies():
            raise ValueError(
                f"Invalid strategy '{self.strategy}'. "
                f"Must be one of: {ImputationStrategy.all_strategies()}"
            )
        if self.strategy == ImputationStrategy.ZERO:
            self.fill_value = 0.0
        if self.strategy == ImputationStrategy.CONSTANT and self.fill_value is None:
            raise ValueError("fill_value must be set for constant strategy")
        self.max_missing_pct = ensure_probability(
            self.max_missing_pct,
            what="max_missing_pct",
        )

    @property
    def name(self) -> str:
        return f"impute_{self.strategy}"

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        start_time = stage_started_at()
        result, _ = copy_if_needed(data, context)

        if self.target_fields is not None:
            fields_to_impute = self.target_fields
        else:
            fields_to_impute = [
                col
                for col in result.columns
                if pd.api.types.is_numeric_dtype(result[col]) and result[col].isna().any()
            ]

        imputation_stats: dict[str, Any] = {}
        warnings: list[str] = []

        for field in fields_to_impute:
            if field not in result.columns:
                continue
            missing_pct = result[field].isna().mean()
            missing_count = int(result[field].isna().sum())

            if missing_pct > self.max_missing_pct:
                msg = (
                    f"Field '{field}' is {missing_pct:.1%} missing "
                    f"(>{self.max_missing_pct:.1%} threshold). "
                    "Imputation may introduce significant bias."
                )
                if self.strict:
                    raise TransformError(msg)
                warnings.append(msg)

            try:
                imputed = self._impute_field(result[field])
                remaining_missing = int(imputed.isna().sum())
                if missing_count > 0 and remaining_missing > 0:
                    msg = (
                        f"Field '{field}' still has {remaining_missing} missing "
                        "values after imputation"
                    )
                    if self.strict:
                        raise TransformError(msg)
                    warnings.append(msg)
                result[field] = imputed
                imputation_stats[field] = {
                    "missing_count": missing_count,
                    "missing_pct": float(missing_pct),
                    "imputed": missing_count,
                    "remaining_missing": remaining_missing,
                }
            except Exception as exc:
                raise TransformError(f"Imputation failed for field '{field}': {exc}") from exc

        lineage = build_lineage(
            stage_name=self.name,
            started_at=start_time,
            input_data=data,
            output_data=result,
            parameters={
                "strategy": self.strategy,
                "fields_imputed": list(imputation_stats.keys()),
                "imputation_stats": imputation_stats,
                "max_missing_pct": self.max_missing_pct,
            },
            context=context,
        )

        return result, lineage, warnings

    def validate_input(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        errors: list[str] = []
        if self.target_fields:
            for field in self.target_fields:
                if field not in data.columns:
                    errors.append(f"Target field '{field}' not found")
        return errors

    def validate_output(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        warnings: list[str] = []
        if self.target_fields:
            for field in self.target_fields:
                if field in data.columns:
                    remaining_missing = int(data[field].isna().sum())
                    if remaining_missing > 0:
                        warnings.append(
                            f"Field '{field}' still has {remaining_missing} "
                            "missing values after imputation"
                        )
        return warnings

    def _impute_field(self, series: pd.Series) -> pd.Series:
        if self.strategy == ImputationStrategy.FORWARD_FILL:
            return series.ffill()
        if self.strategy == ImputationStrategy.BACKWARD_FILL:
            return series.bfill()
        if self.strategy == ImputationStrategy.LINEAR:
            return series.interpolate(method="linear", limit_direction="both")
        if self.strategy == ImputationStrategy.SPLINE:
            if series.notna().sum() >= 4:
                return series.interpolate(
                    method="spline",
                    order=3,
                    limit_direction="both",
                )
            return series.interpolate(method="linear", limit_direction="both")
        if self.strategy == ImputationStrategy.MEAN:
            clean = _finite_numeric_series(series)
            if clean.empty:
                raise TransformError("mean imputation requires at least one finite value")
            return series.fillna(float(clean.mean()))
        if self.strategy == ImputationStrategy.MEDIAN:
            clean = _finite_numeric_series(series)
            if clean.empty:
                raise TransformError("median imputation requires at least one finite value")
            return series.fillna(float(clean.median()))
        if self.strategy in (ImputationStrategy.ZERO, ImputationStrategy.CONSTANT):
            return series.fillna(self.fill_value)
        raise TransformError(f"Unknown strategy: {self.strategy}")


# =============================================================================
# Utility Functions
# =============================================================================


def detect_missing_pattern(series: pd.Series) -> dict[str, Any]:
    """Summarize whether missing values are sparse or clustered before imputation runs."""
    is_missing = series.isna()

    total_missing = int(is_missing.sum())
    missing_pct = float(is_missing.mean())

    missing_runs: list[int] = []
    current_run = 0
    for is_na in is_missing:
        if is_na:
            current_run += 1
        else:
            if current_run > 0:
                missing_runs.append(current_run)
            current_run = 0
    if current_run > 0:
        missing_runs.append(current_run)

    max_consecutive = max(missing_runs) if missing_runs else 0
    is_clustered = max_consecutive > 3 if missing_runs else False

    return {
        "total_missing": total_missing,
        "missing_pct": missing_pct,
        "max_consecutive_missing": int(max_consecutive),
        "num_missing_runs": len(missing_runs),
        "is_clustered": is_clustered,
        "pattern_type": "clustered" if is_clustered else "random",
    }


def recommend_imputation_strategy(series: pd.Series) -> str:
    """Choose a default imputation strategy from the series' missingness pattern."""
    pattern = detect_missing_pattern(series)

    if pattern["missing_pct"] < 0.05:
        return ImputationStrategy.LINEAR
    if pattern["missing_pct"] > 0.3:
        return ImputationStrategy.MEAN
    if pattern["is_clustered"]:
        return ImputationStrategy.FORWARD_FILL
    return ImputationStrategy.LINEAR


def validate_imputation_quality(
    original: pd.Series,
    imputed: pd.Series,
) -> dict[str, Any]:
    """Validate imputation quality."""
    orig_clean = _finite_numeric_series(original)
    imputed_clean = _finite_numeric_series(imputed)
    if orig_clean.empty or imputed_clean.empty:
        return {
            "mean_change_pct": 1.0,
            "std_change_pct": 1.0,
            "outliers_introduced": 0,
            "quality_score": 0.0,
            "valid": False,
            "diagnostic": "no finite values available for imputation quality check",
        }

    orig_mean = orig_clean.mean()
    imputed_mean = imputed_clean.mean()
    mean_change_pct = abs(imputed_mean - orig_mean) / orig_mean if orig_mean != 0 else 0

    orig_std = orig_clean.std()
    imputed_std = imputed_clean.std()
    if not is_finite_number(orig_std) or not is_finite_number(imputed_std) or orig_std == 0:
        std_change_pct = 0.0
    else:
        std_change_pct = abs(imputed_std - orig_std) / orig_std

    orig_min, orig_max = orig_clean.min(), orig_clean.max()
    imputed_values = imputed[original.isna()]
    outliers_introduced = int(((imputed_values < orig_min) | (imputed_values > orig_max)).sum())

    return {
        "mean_change_pct": float(mean_change_pct),
        "std_change_pct": float(std_change_pct),
        "outliers_introduced": outliers_introduced,
        "quality_score": ensure_probability(
            1.0 - min(float(mean_change_pct), 1.0),
            what="imputation quality_score",
            clamp=True,
        ),
        "valid": True,
    }


def _finite_numeric_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return numeric
    return numeric[numeric.map(is_finite_number)]
