"""
Consistency checking for data quality validation.

Checks:
1. Bounds validation (min/max)
2. Categorical value validation
3. Pattern matching (regex)
4. Data type consistency
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .report import ConsistencyResult, RuleViolation

SEVERITY_WEIGHTS = {"error": 1.0, "warning": 0.6, "info": 0.3}


class ConsistencyChecker:
    """
    Cross-column and constraint validation.

    Uses vectorized pandas operations for performance.
    """

    def check_consistency(
        self,
        data: pd.DataFrame,
        schema: Any,
        *,
        full_data: pd.DataFrame | None = None,
    ) -> ConsistencyResult:
        violations: list[RuleViolation] = []
        penalty = 0.0

        data_for_set_checks = full_data if full_data is not None else data

        bounds_violations, bounds_penalty = self._check_bounds(data, schema)
        violations.extend(bounds_violations)
        penalty += bounds_penalty

        categorical_violations, categorical_penalty = self._check_categorical(
            data_for_set_checks, schema
        )
        violations.extend(categorical_violations)
        penalty += categorical_penalty

        pattern_violations, pattern_penalty = self._check_patterns(
            data_for_set_checks, schema
        )
        violations.extend(pattern_violations)
        penalty += pattern_penalty

        type_violations, type_penalty = self._check_data_types(data, schema)
        violations.extend(type_violations)
        penalty += type_penalty

        score = max(0.0, 1.0 - penalty)

        return ConsistencyResult(score=score, violations=violations, penalty=penalty)

    def _check_bounds(
        self,
        data: pd.DataFrame,
        schema: Any,
    ) -> tuple[list[RuleViolation], float]:
        violations: list[RuleViolation] = []
        penalty = 0.0

        for field in schema.fields:
            if field.name not in data.columns:
                continue

            if field.bounds == (None, None):
                continue

            min_val, max_val = field.bounds
            series = data[field.name]
            numeric_series = pd.to_numeric(series, errors="coerce").dropna()

            if len(numeric_series) == 0:
                continue

            total = len(numeric_series)

            if min_val is not None:
                out_of_bounds = numeric_series < min_val
                if out_of_bounds.any():
                    count = int(out_of_bounds.sum())
                    invalid_ratio = count / total
                    severity = _severity_from_ratio(invalid_ratio)
                    violations.append(
                        RuleViolation(
                            rule_type="consistency",
                            field_name=field.name,
                            severity=severity,
                            message=f"{count} values below minimum {min_val}",
                            expected=f">= {min_val}",
                            actual=f"min = {numeric_series.min()}",
                            sample_values=numeric_series[out_of_bounds]
                            .head(5)
                            .tolist(),
                        )
                    )
                    penalty += invalid_ratio * SEVERITY_WEIGHTS[severity]

            if max_val is not None:
                out_of_bounds = numeric_series > max_val
                if out_of_bounds.any():
                    count = int(out_of_bounds.sum())
                    invalid_ratio = count / total
                    severity = _severity_from_ratio(invalid_ratio)
                    violations.append(
                        RuleViolation(
                            rule_type="consistency",
                            field_name=field.name,
                            severity=severity,
                            message=f"{count} values above maximum {max_val}",
                            expected=f"<= {max_val}",
                            actual=f"max = {numeric_series.max()}",
                            sample_values=numeric_series[out_of_bounds]
                            .head(5)
                            .tolist(),
                        )
                    )
                    penalty += invalid_ratio * SEVERITY_WEIGHTS[severity]

        return violations, penalty

    def _check_categorical(
        self,
        data: pd.DataFrame,
        schema: Any,
    ) -> tuple[list[RuleViolation], float]:
        violations: list[RuleViolation] = []
        penalty = 0.0

        for field in schema.fields:
            if field.name not in data.columns:
                continue
            if field.allowed_values is None:
                continue

            series = data[field.name].dropna()
            if len(series) == 0:
                continue

            invalid = ~series.isin(field.allowed_values)
            if invalid.any():
                invalid_count = int(invalid.sum())
                invalid_ratio = invalid_count / len(series)
                severity = _severity_from_ratio(invalid_ratio)
                invalid_values = series[invalid].unique()

                violations.append(
                    RuleViolation(
                        rule_type="consistency",
                        field_name=field.name,
                        severity=severity,
                        message=(
                            f"{invalid_count} values ({invalid_ratio:.1%}) not in allowed set"
                        ),
                        expected=f"one of {list(field.allowed_values)[:10]}",
                        actual=f"{len(invalid_values)} invalid values",
                        sample_values=invalid_values[:5].tolist(),
                    )
                )
                penalty += invalid_ratio * SEVERITY_WEIGHTS[severity]

        return violations, penalty

    def _check_patterns(
        self,
        data: pd.DataFrame,
        schema: Any,
    ) -> tuple[list[RuleViolation], float]:
        violations: list[RuleViolation] = []
        penalty = 0.0

        for field in schema.fields:
            if field.name not in data.columns:
                continue
            if field.pattern is None:
                continue

            series = data[field.name].dropna()
            if len(series) == 0:
                continue

            try:
                pattern = re.compile(field.pattern)
                matches = series.astype(str).str.match(pattern, na=False)
                invalid = ~matches

                if invalid.any():
                    invalid_count = int(invalid.sum())
                    invalid_ratio = invalid_count / len(series)
                    severity = _severity_from_ratio(invalid_ratio)
                    invalid_values = series[invalid].unique()

                    violations.append(
                        RuleViolation(
                            rule_type="consistency",
                            field_name=field.name,
                            severity=severity,
                            message=f"{invalid_count} values do not match pattern",
                            expected=f"pattern: {field.pattern}",
                            actual=f"{len(invalid_values)} non-matching values",
                            sample_values=invalid_values[:5].tolist(),
                        )
                    )
                    penalty += invalid_ratio * SEVERITY_WEIGHTS[severity]
            except re.error as exc:
                violations.append(
                    RuleViolation(
                        rule_type="consistency",
                        field_name=field.name,
                        severity="warning",
                        message=f"Invalid regex pattern in schema: {exc}",
                        expected="valid regex",
                        actual=field.pattern,
                    )
                )
                penalty += 0.1 * SEVERITY_WEIGHTS["warning"]

        return violations, penalty

    def _check_data_types(
        self,
        data: pd.DataFrame,
        schema: Any,
    ) -> tuple[list[RuleViolation], float]:
        violations: list[RuleViolation] = []
        penalty = 0.0

        from polisyos.fabric.connectors.contracts.schema import SchemaType

        for field in schema.fields:
            if field.name not in data.columns:
                continue

            series = data[field.name].dropna()
            if len(series) == 0:
                continue

            expected_type = field.data_type

            if expected_type in (
                SchemaType.INT32,
                SchemaType.INT64,
                SchemaType.FLOAT32,
                SchemaType.FLOAT64,
            ):
                numeric = pd.to_numeric(series, errors="coerce")
                non_numeric = numeric.isna() & series.notna()

                if non_numeric.any():
                    count = int(non_numeric.sum())
                    invalid_ratio = count / len(series)
                    severity = _severity_from_ratio(invalid_ratio)
                    violations.append(
                        RuleViolation(
                            rule_type="consistency",
                            field_name=field.name,
                            severity=severity,
                            message=f"{count} non-numeric values in numeric field",
                            expected=expected_type.value,
                            actual="mixed types",
                            sample_values=series[non_numeric].head(5).tolist(),
                        )
                    )
                    penalty += invalid_ratio * SEVERITY_WEIGHTS[severity]

            elif expected_type == SchemaType.BOOLEAN:
                boolean_values = {True, False, "true", "false", "True", "False", 1, 0}
                non_boolean = ~series.isin(boolean_values)

                if non_boolean.any():
                    count = int(non_boolean.sum())
                    invalid_ratio = count / len(series)
                    severity = _severity_from_ratio(invalid_ratio)
                    violations.append(
                        RuleViolation(
                            rule_type="consistency",
                            field_name=field.name,
                            severity=severity,
                            message=f"{count} non-boolean values in boolean field",
                            expected="boolean",
                            actual="mixed types",
                            sample_values=series[non_boolean].head(5).tolist(),
                        )
                    )
                    penalty += invalid_ratio * SEVERITY_WEIGHTS[severity]

        return violations, penalty


def _severity_from_ratio(ratio: float) -> str:
    if ratio > 0.1:
        return "error"
    if ratio > 0.05:
        return "warning"
    return "info"
