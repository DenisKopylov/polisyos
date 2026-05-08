"""Data quality validation transform and rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from polisyos.fabric.connectors.transform._common import (
    build_lineage,
    resolve_copy_policy,
    stage_started_at,
)
from polisyos.fabric.connectors.transform.pipeline import (
    CopyPolicy,
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
)
from polisyos.fabric.numerics.finite import ensure_finite_float, ensure_probability, is_finite_number

__all__ = [
    "CompletenessRule",
    "RangeRule",
    "ValidationRule",
    "ValidationTransform",
]


class ValidationRule(Protocol):
    """Protocol for validation rules."""

    name: str

    def validate(self, data: pd.DataFrame, context: TransformContext) -> list[str]: ...

    def required_fields(self) -> set[str]: ...


@dataclass
class CompletenessRule:
    """Require a minimum non-null ratio for a field."""

    field: str
    threshold: float = 0.95

    def __post_init__(self) -> None:
        self.threshold = ensure_probability(self.threshold, what=f"{self.name} threshold")

    @property
    def name(self) -> str:
        return f"completeness:{self.field}"

    def required_fields(self) -> set[str]:
        return {self.field}

    def validate(self, data: pd.DataFrame, context: TransformContext) -> list[str]:
        if self.field not in data.columns:
            return [f"Field '{self.field}' not found"]
        completeness = 1.0 - data[self.field].isna().mean()
        if completeness < self.threshold:
            return [
                f"Field '{self.field}' completeness {completeness:.1%} below "
                f"threshold {self.threshold:.1%}"
            ]
        return []


@dataclass
class RangeRule:
    """Require values to be within an inclusive range."""

    field: str
    min_value: float | None = None
    max_value: float | None = None

    def __post_init__(self) -> None:
        if self.min_value is not None:
            self.min_value = ensure_finite_float(self.min_value, what=f"{self.name} min_value")
        if self.max_value is not None:
            self.max_value = ensure_finite_float(self.max_value, what=f"{self.name} max_value")
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError(f"{self.name} min_value must be <= max_value")

    @property
    def name(self) -> str:
        return f"range:{self.field}"

    def required_fields(self) -> set[str]:
        return {self.field}

    def validate(self, data: pd.DataFrame, context: TransformContext) -> list[str]:
        if self.field not in data.columns:
            return [f"Field '{self.field}' not found"]
        series = pd.to_numeric(data[self.field], errors="coerce")
        violations = []
        non_finite = series.notna() & ~series.map(is_finite_number)
        if non_finite.any():
            violations.append(
                f"Field '{self.field}' has {int(non_finite.sum())} non-finite values"
            )
        series = series[~non_finite]
        if self.min_value is not None:
            below = (series < self.min_value).sum()
            if below > 0:
                violations.append(f"Field '{self.field}' has {below} values below {self.min_value}")
        if self.max_value is not None:
            above = (series > self.max_value).sum()
            if above > 0:
                violations.append(f"Field '{self.field}' has {above} values above {self.max_value}")
        return violations


@dataclass
class ValidationTransform(DataTransform):
    """Run validation rules and emit warnings or errors."""

    rules: list[ValidationRule]
    strict: bool = False

    def __post_init__(self) -> None:
        if self.strict and not self.rules:
            raise ValueError("strict validation requires at least one rule")

    @property
    def name(self) -> str:
        return "validate"

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        start_time = stage_started_at()
        copy_policy = resolve_copy_policy(context)

        if not self.rules:
            result = data.copy() if copy_policy == CopyPolicy.COPY else data
            lineage = build_lineage(
                stage_name=self.name,
                started_at=start_time,
                input_data=data,
                output_data=result,
                parameters={
                    "rules": [],
                    "rule_count": 0,
                    "strict": self.strict,
                    "skipped": True,
                },
                context=context,
            )
            return result, lineage, ["No validation rules configured; validation skipped"]

        warnings: list[str] = []
        for rule in self.rules:
            warnings.extend(rule.validate(data, context))

        if warnings and self.strict:
            raise TransformError("Validation failed: " + "; ".join(warnings))

        result = data.copy() if copy_policy == CopyPolicy.COPY else data

        lineage = build_lineage(
            stage_name=self.name,
            started_at=start_time,
            input_data=data,
            output_data=result,
            parameters={
                "rules": [rule.name for rule in self.rules],
                "rule_count": len(self.rules),
                "strict": self.strict,
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
        required: set[str] = set()
        for rule in self.rules:
            required |= rule.required_fields()
        missing = required - set(data.columns)
        if missing:
            errors.append(f"Validation fields missing: {sorted(missing)}")
        return errors
