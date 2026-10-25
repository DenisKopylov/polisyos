"""
Convenience functions for schema inference, validation, and coercion.

Contains the module-level helper functions and the CoercionResult
dataclass that wrap SchemaInference for common use cases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Protocol, cast

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    SchemaType,
    SemanticType,
)
from polisyos.fabric.numerics.finite import is_finite_number

if TYPE_CHECKING:
    from collections.abc import Callable

    from pandas._libs.missing import NAType

    from ._inference_config import InferenceConfig, SchemaHints

from ._inference_engine import SchemaInference

logger = get_logger(__name__)


__all__ = [
    "CoercionResult",
    "coerce_dataframe_to_schema",
    "infer_schema",
    "validate_dataframe_against_schema",
]


# =============================================================================
# Coercion Result
# =============================================================================


@dataclass(frozen=True)
class CoercionResult:
    """Result of coercing a DataFrame to a schema."""

    dataframe: pd.DataFrame
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    coerced_columns: tuple[str, ...]
    dropped_columns: tuple[str, ...]


# =============================================================================
# Convenience Functions
# =============================================================================


def infer_schema(
    df: pd.DataFrame,
    schema_id: str = "inferred",
    hints: SchemaHints | None = None,
    config: InferenceConfig | None = None,
) -> DataSchema:
    """
    Convenience function to infer schema from DataFrame.

    Args:
        df: DataFrame to analyze
        schema_id: ID for the generated schema
        hints: Optional inference hints
        config: Optional inference configuration

    Returns:
        Inferred DataSchema
    """
    inference = SchemaInference(config)
    result = inference.infer_from_sample(df, hints, schema_id)
    return result.schema


def validate_dataframe_against_schema(
    df: pd.DataFrame,
    schema: DataSchema,
    strict: bool = False,
) -> list[str]:
    """
    Validate a DataFrame against a schema.

    Args:
        df: DataFrame to validate
        schema: Schema to validate against
        strict: If True, fail on extra columns

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []

    schema_fields = {field.name for field in schema.fields}
    required_fields = set(schema.required_field_names())
    df_columns = set(df.columns)

    missing = required_fields - df_columns
    if missing:
        errors.append(f"Missing required columns: {missing}")

    if strict:
        extra = df_columns - schema_fields
        if extra:
            errors.append(f"Extra columns not in schema: {extra}")

    for field in schema.fields:
        if field.name not in df.columns:
            continue

        column_values = df[field.name]

        if (
            not field.nullable
            and field.name not in schema.allowed_null_fields
            and column_values.isna().any()
        ):
            null_count = column_values.isna().sum()
            errors.append(f"Field '{field.name}' has {null_count} null values but is not nullable")

        if field.data_type.is_numeric() or field.data_type == SchemaType.DECIMAL:
            numeric_col = pd.to_numeric(column_values, errors="coerce")
            finite_mask = numeric_col.map(is_finite_number)
            nonfinite = numeric_col.notna() & ~finite_mask
            if nonfinite.any():
                errors.append(f"Field '{field.name}' has {int(nonfinite.sum())} non-finite values")
            numeric_col = numeric_col[finite_mask]
        else:
            numeric_col = None

        if numeric_col is not None and field.bounds != (None, None):
            min_val, max_val = field.bounds
            if min_val is not None:
                below = (numeric_col < min_val).sum()
                if below > 0:
                    errors.append(
                        f"Field '{field.name}' has {below} values below min bound {min_val}"
                    )
            if max_val is not None:
                above = (numeric_col > max_val).sum()
                if above > 0:
                    errors.append(
                        f"Field '{field.name}' has {above} values above max bound {max_val}"
                    )

        if field.semantic_type is not None and numeric_col is not None:
            semantic_min, semantic_max = field.semantic_type.get_validation_bounds()
            if semantic_min is not None:
                below = (numeric_col < semantic_min).sum()
                if below > 0:
                    errors.append(
                        f"Field '{field.name}' has {below} values below semantic "
                        f"{field.semantic_type.value} min {semantic_min}"
                    )
            if semantic_max is not None:
                above = (numeric_col > semantic_max).sum()
                if above > 0:
                    errors.append(
                        f"Field '{field.name}' has {above} values above semantic "
                        f"{field.semantic_type.value} max {semantic_max}"
                    )

        if field.semantic_type in {SemanticType.IDENTIFIER, SemanticType.CODE}:
            values = column_values.dropna().astype(str).str.strip()
            empty_count = int((values == "").sum())
            if empty_count:
                errors.append(
                    f"Field '{field.name}' has {empty_count} empty "
                    f"{field.semantic_type.value} values"
                )

        if field.allowed_values is not None:
            invalid_allowed_values = set(column_values.dropna().astype(str)) - field.allowed_values
            if invalid_allowed_values:
                errors.append(f"Field '{field.name}' has invalid values: {invalid_allowed_values}")

        if field.pattern and field.data_type in (SchemaType.STRING, SchemaType.CATEGORY):
            pattern = re.compile(field.pattern)
            pattern_mismatches = [
                value
                for value in column_values.dropna().astype(str).unique()
                if not pattern.match(value)
            ]
            if pattern_mismatches:
                errors.append(
                    f"Field '{field.name}' has values not matching pattern: {pattern_mismatches}"
                )

        if field.max_length and field.data_type in (
            SchemaType.STRING,
            SchemaType.CATEGORY,
            SchemaType.BINARY,
        ):
            too_long = column_values.dropna().astype(str).str.len() > field.max_length
            if too_long.any():
                count = int(too_long.sum())
                errors.append(
                    f"Field '{field.name}' has {count} values exceeding max_length "
                    f"{field.max_length}"
                )

        completeness = 1.0 - column_values.isna().mean()
        if (
            field.name not in schema.allowed_null_fields
            and completeness < schema.required_completeness
        ):
            errors.append(
                f"Field '{field.name}' completeness {completeness:.1%} below required "
                f"{schema.required_completeness:.1%}"
            )

    return errors


def coerce_dataframe_to_schema(
    df: pd.DataFrame,
    schema: DataSchema,
    *,
    strict: bool = False,
    normalize_columns: bool = True,
    drop_extra: bool = False,
) -> CoercionResult:
    """
    Coerce a DataFrame to the schema's expected types.

    Returns a new DataFrame plus coercion warnings/errors.
    """
    errors: list[str] = []
    warnings: list[str] = []
    coerced_columns: list[str] = []
    dropped_columns: list[str] = []

    df_work = df.copy()

    if normalize_columns:
        normalized_map: dict[str, str] = {}
        for column_name in df_work.columns:
            normalized = SchemaInference._normalize_column_name(column_name)
            if normalized in normalized_map:
                warnings.append(
                    f"Column '{column_name}' normalized to '{normalized}' conflicts with "
                    f"'{normalized_map[normalized]}'"
                )
                continue
            normalized_map[normalized] = column_name

        rename_map: dict[str, str] = {}
        for field in schema.fields:
            if field.name in df_work.columns:
                continue
            if field.name in normalized_map:
                rename_map[normalized_map[field.name]] = field.name

        if rename_map:
            df_work = df_work.rename(columns=rename_map)

    schema_fields = {f.name for f in schema.fields}

    if drop_extra:
        extra = [column_name for column_name in df_work.columns if column_name not in schema_fields]
        if extra:
            df_work = df_work.drop(columns=extra)
            dropped_columns.extend(extra)
    elif strict:
        extra = [column_name for column_name in df_work.columns if column_name not in schema_fields]
        if extra:
            errors.append(f"Extra columns not in schema: {set(extra)}")

    for field in schema.fields:
        if field.name not in df_work.columns:
            if field.presence == "optional":
                continue
            errors.append(f"Missing required column '{field.name}'")
            continue

        column_values = df_work[field.name]
        try:
            if field.data_type == SchemaType.BOOLEAN:
                df_work[field.name] = _coerce_boolean(column_values)
                coerced_columns.append(field.name)
            elif field.data_type.is_numeric():
                numeric = pd.to_numeric(column_values, errors="coerce")
                non_finite = numeric.notna() & ~numeric.map(is_finite_number)
                if non_finite.any():
                    count = int(non_finite.sum())
                    errors.append(
                        f"Column '{field.name}' has {count} non-finite values during coercion"
                    )
                    numeric = numeric.mask(non_finite, pd.NA)
                df_work[field.name] = numeric.astype(
                    pd.api.types.pandas_dtype(field.data_type.to_pandas_dtype())
                )
                coerced_columns.append(field.name)
            elif field.data_type in (SchemaType.DATETIME, SchemaType.TIMESTAMP_TZ):
                df_work[field.name] = pd.to_datetime(column_values, errors="coerce", utc=True)
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.DATE:
                df_work[field.name] = pd.to_datetime(column_values, errors="coerce").dt.date
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.DURATION:
                df_work[field.name] = pd.to_timedelta(column_values, errors="coerce")
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.CATEGORY:
                df_work[field.name] = column_values.astype("category")
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.STRING:
                df_work[field.name] = column_values.astype("string")
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.DECIMAL:
                # The apply stub's scalar alias omits Decimal; the runtime accepts it.
                apply_decimal = cast("_DecimalSeriesApply", column_values.apply)
                df_work[field.name] = apply_decimal(_coerce_decimal)
                coerced_columns.append(field.name)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Failed to coerce column '{field.name}': {exc}")

    return CoercionResult(
        dataframe=df_work,
        errors=tuple(errors),
        warnings=tuple(warnings),
        coerced_columns=tuple(coerced_columns),
        dropped_columns=tuple(dropped_columns),
    )


# =============================================================================
# Coercion Helpers
# =============================================================================


def _coerce_boolean(series: pd.Series) -> pd.Series:
    mapping = {
        "true": True,
        "false": False,
        "yes": True,
        "no": False,
        "y": True,
        "n": False,
        "1": True,
        "0": False,
        "t": True,
        "f": False,
    }

    def _to_bool(value: object) -> bool | NAType:
        if value is None or value is pd.NA or value is pd.NaT or not pd.api.types.is_scalar(value):
            return pd.NA
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(int(value))
        key = str(value).strip().lower()
        return mapping.get(key, pd.NA)

    return series.map(_to_bool).astype("boolean")


class _DecimalSeriesApply(Protocol):
    """Typed view of ``Series.apply`` for a scalar Decimal mapper."""

    # Decimal is outside the pandas-stubs SeriesDType bound; the result uses the
    # default generic at this narrowly scoped pandas object-dtype boundary.
    def __call__(
        self,
        func: Callable[[object], Decimal | None],
        /,
    ) -> pd.Series: ...


def _coerce_decimal(value: object) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, str):
        from polisyos.fabric._internal.numeric_parsing import parse_decimal_text

        return parse_decimal_text(value)
    try:
        parsed = Decimal(str(value))
        if not parsed.is_finite():
            return None
        return parsed
    except (InvalidOperation, TypeError, ValueError):
        logger.debug(
            "Failed to coerce value %r to Decimal",
            value,
            exc_info=True,
        )
        return None
