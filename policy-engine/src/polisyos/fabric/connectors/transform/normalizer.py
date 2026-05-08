"""
Normalization transformations for data standardization.

Handles:
1. Field renaming (source columns → target schema names)
2. Unit conversion (kUSD → USD, km → m)
3. Type casting (string → int, with safety checks)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from polisyos.fabric.connectors.transform._common import (
    build_lineage,
    copy_if_needed,
    stage_started_at,
)
from polisyos.fabric.connectors.transform.pipeline import (
    CopyPolicy,
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
)
from polisyos.fabric.numerics.finite import is_finite_number

__all__ = ["NormalizationTransform"]


@dataclass
class NormalizationTransform(DataTransform):
    """
    Standardize field names, units, and data types.

    Field mapping is applied first, then unit conversions operate on
    the renamed fields, finally type casting ensures schema compliance.
    """

    field_mappings: dict[str, str] = field(default_factory=dict)
    unit_conversions: dict[str, tuple[str, str]] = field(default_factory=dict)
    type_casts: dict[str, str] = field(default_factory=dict)
    drop_unmapped: bool = False
    cast_to_schema: bool = True

    @property
    def name(self) -> str:
        return "normalize"

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        start_time = stage_started_at()
        result, copy_policy = copy_if_needed(data, context)

        # Step 1: Rename columns
        if self.field_mappings:
            if copy_policy == CopyPolicy.COPY:
                result = result.rename(columns=self.field_mappings)
            else:
                result.rename(columns=self.field_mappings, inplace=True)

            if self.drop_unmapped:
                ordered_columns = tuple(
                    dict.fromkeys(
                        self.field_mappings[source_col]
                        for source_col in data.columns
                        if source_col in self.field_mappings
                    )
                )
                result = result.loc[:, list(ordered_columns)]

        # Step 2: Convert units
        conversion_log: dict[str, dict[str, str | bool]] = {}
        for field_name, (from_unit, to_unit) in self.unit_conversions.items():
            if field_name not in result.columns:
                continue
            try:
                conversion_log[field_name] = self._unit_conversion_evidence(
                    from_unit,
                    to_unit,
                )
                result[field_name] = self._convert_units(
                    result[field_name],
                    from_unit,
                    to_unit,
                )
            except Exception as exc:
                raise TransformError(
                    f"Unit conversion failed for field '{field_name}': {exc}"
                ) from exc

        # Step 3: Type casting (explicit)
        cast_log: dict[str, str] = {}
        for field_name, target_dtype in self.type_casts.items():
            if field_name not in result.columns:
                continue
            try:
                result[field_name] = self._safe_cast(result[field_name], target_dtype)
                cast_log[field_name] = target_dtype
            except Exception as exc:
                raise TransformError(f"Type cast failed for field '{field_name}': {exc}") from exc

        # Step 4: Type casting based on target schema (optional)
        if self.cast_to_schema and context.target_schema:
            for field_spec in context.target_schema.fields:
                if field_spec.name not in result.columns:
                    continue
                target_dtype = field_spec.data_type.value
                try:
                    result[field_spec.name] = self._safe_cast(
                        result[field_spec.name],
                        target_dtype,
                    )
                    cast_log.setdefault(field_spec.name, target_dtype)
                except Exception as exc:
                    raise TransformError(
                        f"Schema cast failed for field '{field_spec.name}': {exc}"
                    ) from exc

        lineage = build_lineage(
            stage_name=self.name,
            started_at=start_time,
            input_data=data,
            output_data=result,
            parameters={
                "field_mappings": self.field_mappings,
                "unit_conversions": conversion_log,
                "type_casts": cast_log,
                "drop_unmapped": self.drop_unmapped,
                "cast_to_schema": self.cast_to_schema,
            },
            context=context,
        )

        return result, lineage, []

    def validate_input(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        errors: list[str] = []
        for source_col in self.field_mappings:
            if source_col not in data.columns:
                errors.append(f"Source column '{source_col}' not found")
        if context.target_schema:
            expected_fields = set(context.target_schema.field_names())
            for target_field in self.field_mappings.values():
                if target_field not in expected_fields:
                    errors.append(f"Mapped target field '{target_field}' not found in target schema")
            for field_name, (_from_unit, to_unit) in self.unit_conversions.items():
                field = context.target_schema.get_field(field_name)
                if field is not None and field.unit is not None and field.unit.unit_id != to_unit:
                    errors.append(
                        f"Unit conversion for '{field_name}' targets {to_unit!r}, "
                        f"but target schema expects {field.unit.unit_id!r}"
                    )
        return errors

    def validate_output(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        warnings: list[str] = []
        if context.target_schema and hasattr(context.target_schema, "fields"):
            expected_fields = {f.name for f in context.target_schema.fields}
            actual_fields = set(data.columns)
            missing = expected_fields - actual_fields
            if missing:
                warnings.append(f"Missing expected fields: {missing}")
        return warnings

    def _convert_units(
        self,
        series: pd.Series,
        from_unit: str,
        to_unit: str,
    ) -> pd.Series:
        """
        Convert values from one unit to another.

        Attempts to use Phase 2.4 Unit system if available,
        otherwise falls back to simple metric prefix conversion.
        """
        try:
            from polisyos.fabric.connectors.types.units import Unit

            from_u = Unit.parse(from_unit)
            to_u = Unit.parse(to_unit)
            non_null = series[series.notna()]
            non_finite = non_null.map(lambda value: not is_finite_number(value))
            if non_finite.any():
                raise TransformError(
                    f"unit conversion input contains {int(non_finite.sum())} non-finite values"
                )
            return series.apply(lambda x: from_u.convert_to(to_u, x) if pd.notna(x) else x)
        except ImportError:
            return self._simple_unit_conversion(series, from_unit, to_unit)

    def _unit_conversion_evidence(
        self,
        from_unit: str,
        to_unit: str,
    ) -> dict[str, str | bool]:
        """Return replayable metadata for a declared unit conversion."""
        try:
            from polisyos.fabric.connectors.types.units import Unit

            from_u = Unit.parse(from_unit)
            to_u = Unit.parse(to_unit)
            factor = from_u.get_conversion_factor(to_u)
            return {
                "from_unit": from_u.to_string(),
                "to_unit": to_u.to_string(),
                "multiplier": str(factor.multiplier),
                "offset": str(factor.offset),
                "requires_rate": factor.requires_rate,
            }
        except ImportError:
            factor = Decimal(str(self._simple_unit_factor(from_unit, to_unit)))
            return {
                "from_unit": from_unit,
                "to_unit": to_unit,
                "multiplier": str(factor),
                "offset": "0",
                "requires_rate": False,
            }

    def _simple_unit_conversion(
        self,
        series: pd.Series,
        from_unit: str,
        to_unit: str,
    ) -> pd.Series:
        """Fallback conversion for common metric prefixes."""
        prefix_scale = {
            "k": 1_000,
            "M": 1_000_000,
            "G": 1_000_000_000,
        }

        from_prefix = from_unit[0] if from_unit[0] in prefix_scale else ""
        to_prefix = to_unit[0] if to_unit[0] in prefix_scale else ""

        from_base = from_unit[len(from_prefix) :]
        to_base = to_unit[len(to_prefix) :]

        if from_base != to_base:
            raise TransformError(f"Cannot convert between different units: {from_unit} → {to_unit}")

        from_scale = prefix_scale.get(from_prefix, 1)
        to_scale = prefix_scale.get(to_prefix, 1)
        factor = from_scale / to_scale

        non_null = series[series.notna()]
        non_finite = non_null.map(lambda value: not is_finite_number(value))
        if non_finite.any():
            raise TransformError(
                f"unit conversion input contains {int(non_finite.sum())} non-finite values"
            )

        return series * factor

    def _simple_unit_factor(self, from_unit: str, to_unit: str) -> float:
        prefix_scale = {
            "k": 1_000,
            "M": 1_000_000,
            "G": 1_000_000_000,
        }

        from_prefix = from_unit[0] if from_unit[0] in prefix_scale else ""
        to_prefix = to_unit[0] if to_unit[0] in prefix_scale else ""

        from_base = from_unit[len(from_prefix) :]
        to_base = to_unit[len(to_prefix) :]

        if from_base != to_base:
            raise TransformError(f"Cannot convert between different units: {from_unit} → {to_unit}")

        return prefix_scale.get(from_prefix, 1) / prefix_scale.get(to_prefix, 1)

    def _safe_cast(
        self,
        series: pd.Series,
        target_dtype: str,
    ) -> pd.Series:
        """Safely cast series to target dtype."""
        try:
            from polisyos.fabric.connectors.types.coercion import safe_cast

            return series.apply(lambda x: safe_cast(x, target_dtype) if pd.notna(x) else x)
        except ImportError:
            return self._pandas_safe_cast(series, target_dtype)

    def _pandas_safe_cast(
        self,
        series: pd.Series,
        target_dtype: str,
    ) -> pd.Series:
        if target_dtype in ("int", "int64", "int32"):
            numeric = pd.to_numeric(series, errors="coerce")
            non_finite = numeric.notna() & ~numeric.map(is_finite_number)
            if non_finite.any():
                raise TransformError(
                    f"Cannot safely cast {series.name} to int: non-finite values present"
                )
            if series.dtype in ("float", "float64"):
                if not (numeric.dropna() % 1 == 0).all():
                    raise TransformError(
                        f"Cannot safely cast {series.name} to int: would lose decimal places"
                    )
            return numeric.astype("Int64")
        if target_dtype in ("float", "float64"):
            numeric = pd.to_numeric(series, errors="coerce")
            non_finite = numeric.notna() & ~numeric.map(is_finite_number)
            if non_finite.any():
                raise TransformError(
                    f"Cannot safely cast {series.name} to float: non-finite values present"
                )
            return numeric
        if target_dtype in ("str", "string", "object"):
            return series.astype(str)
        if target_dtype in ("datetime", "datetime64"):
            return pd.to_datetime(series, errors="coerce")
        return series.astype(target_dtype)
