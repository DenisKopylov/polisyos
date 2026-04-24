"""
Stock/Flow-aware temporal aggregation transformations.

This is one of the MOST CRITICAL modules in Phase 2.5.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import pandas as pd

from polisyos.fabric.connectors.contracts.schema import (
    Additivity,
    DataSchema,
    TimeGranularity,
)
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
from polisyos.fabric.connectors.types.temporal import (
    AggregationMethod,
    TemporalType,
    infer_temporal_type,
)

__all__ = [
    "AggregationMethod",
    "AggregationTransform",
    "TemporalType",
    "validate_temporal_aggregation",
]


# =============================================================================
# Aggregation Transform
# =============================================================================


@dataclass(frozen=True)
class AggregationTransform(DataTransform):
    """
    Aggregate data with Stock/Flow awareness and additivity semantics.

    - Semi-additive (stocks): can sum across entities, not time.
    - Non-additive (rates/indices): never sum.
    """

    group_by: Sequence[str | Any]
    aggregations: Mapping[str, str | AggregationMethod]
    temporal_context: Mapping[str, TemporalType | str] = field(default_factory=dict)
    additivity_context: Mapping[str, Additivity | str] = field(default_factory=dict)
    strict: bool = False
    auto_infer_temporal: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_by", tuple(self.group_by))
        object.__setattr__(self, "aggregations", MappingProxyType(dict(self.aggregations)))
        object.__setattr__(
            self,
            "temporal_context",
            MappingProxyType(self._normalize_temporal_context(self.temporal_context)),
        )
        object.__setattr__(
            self,
            "additivity_context",
            MappingProxyType(self._normalize_additivity_context(self.additivity_context)),
        )

    @property
    def name(self) -> str:
        return "aggregate"

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        start_time = stage_started_at()
        result, _ = copy_if_needed(data, context)
        temporal_context = dict(self.temporal_context)

        if self.auto_infer_temporal:
            temporal_context = self._infer_missing_temporal_types(
                result,
                context,
                temporal_context=temporal_context,
            )

        time_collapsing, time_details = self._detect_time_collapsing(context)
        agg_dict, corrections, warnings = self._build_safe_aggregation_dict(
            time_collapsing=time_collapsing,
            context=context,
            temporal_context=temporal_context,
        )

        resolved_additivity: dict[str, str] = {}
        schema = context.target_schema or context.source_schema
        for field, ttype in temporal_context.items():
            resolved = self._resolve_additivity(field, ttype, schema)
            if resolved is not None:
                resolved_additivity[field] = resolved.value

        if self.group_by:
            result = result.groupby(list(self.group_by), as_index=False).agg(agg_dict)
        else:
            aggregated = result.agg(agg_dict)
            result = aggregated.to_frame().T if isinstance(aggregated, pd.Series) else aggregated

        lineage = build_lineage(
            stage_name=self.name,
            started_at=start_time,
            input_data=data,
            output_data=result,
            parameters={
                "group_by": [str(g) for g in self.group_by],
                "aggregations": agg_dict,
                "temporal_types": {k: v.value for k, v in temporal_context.items()},
                "additivity": resolved_additivity,
                "time_collapsing": time_collapsing,
                **time_details,
                "corrections_made": corrections,
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

        for col in self.group_by:
            if isinstance(col, str) and col not in data.columns:
                errors.append(f"Grouping column '{col}' not found")
            if isinstance(col, pd.Grouper) and col.key not in data.columns:
                errors.append(f"Grouping key '{col.key}' not found")

        for field in self.aggregations:
            if field not in data.columns:
                errors.append(f"Aggregation field '{field}' not found")

        return errors

    def validate_output(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        return []

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_temporal_context(
        context: dict[str, TemporalType | str],
    ) -> dict[str, TemporalType]:
        normalized: dict[str, TemporalType] = {}
        for field, ttype in context.items():
            if isinstance(ttype, TemporalType):
                normalized[field] = ttype
            elif isinstance(ttype, str):
                normalized[field] = TemporalType(ttype.lower())
            else:
                raise TransformError(f"Invalid temporal type for '{field}': {ttype}")
        return normalized

    @staticmethod
    def _normalize_additivity_context(
        context: dict[str, Additivity | str],
    ) -> dict[str, Additivity]:
        normalized: dict[str, Additivity] = {}
        for field, add in context.items():
            if isinstance(add, Additivity):
                normalized[field] = add
            elif isinstance(add, str):
                normalized[field] = Additivity(add.lower())
            else:
                raise TransformError(f"Invalid additivity for '{field}': {add}")
        return normalized

    def _infer_missing_temporal_types(
        self,
        data: pd.DataFrame,
        context: TransformContext,
        *,
        temporal_context: dict[str, TemporalType],
    ) -> dict[str, TemporalType]:
        for field in self.aggregations:
            if field in temporal_context:
                continue
            semantic_type = None
            schema = context.target_schema or context.source_schema
            if schema is not None:
                field_spec = schema.get_field(field)
                if field_spec is not None and field_spec.semantic_type is not None:
                    semantic_type = field_spec.semantic_type.value
            temporal_context[field] = infer_temporal_type(field, semantic_type)
        return temporal_context

    def _detect_time_collapsing(self, context: TransformContext) -> tuple[bool, dict[str, Any]]:
        schema = context.source_schema
        target_schema = context.target_schema
        if schema is None or schema.time_dimension is None:
            return False, {
                "time_dimension": None,
                "source_time_granularity": None,
                "target_time_granularity": None,
            }

        time_dim = schema.time_dimension
        source_grain = schema.time_granularity
        target_grain = target_schema.time_granularity if target_schema else None

        time_in_group = False
        grouper_grain: TimeGranularity | None = None

        for item in self.group_by:
            if isinstance(item, pd.Grouper):
                if item.key == time_dim:
                    time_in_group = True
                    grouper_grain = _freq_to_granularity(item.freq)
            elif isinstance(item, str) and item == time_dim:
                time_in_group = True

        if not time_in_group:
            return True, {
                "time_dimension": time_dim,
                "source_time_granularity": source_grain.value if source_grain else None,
                "target_time_granularity": target_grain.value if target_grain else None,
                "group_time_granularity": grouper_grain.value if grouper_grain else None,
            }

        time_collapsing = False
        if grouper_grain is not None:
            if source_grain is None or grouper_grain.is_coarser_than(source_grain):
                time_collapsing = True

        if not time_collapsing and source_grain and target_grain:
            if target_grain.is_coarser_than(source_grain):
                time_collapsing = True

        return time_collapsing, {
            "time_dimension": time_dim,
            "source_time_granularity": source_grain.value if source_grain else None,
            "target_time_granularity": target_grain.value if target_grain else None,
            "group_time_granularity": grouper_grain.value if grouper_grain else None,
        }

    def _build_safe_aggregation_dict(
        self,
        *,
        time_collapsing: bool,
        context: TransformContext,
        temporal_context: Mapping[str, TemporalType],
    ) -> tuple[dict[str, str], list[str], list[str]]:
        validated_agg: dict[str, str] = {}
        corrections: list[str] = []
        warnings: list[str] = []

        schema = context.target_schema or context.source_schema

        for field, agg_method in self.aggregations.items():
            method = (
                agg_method.value if isinstance(agg_method, AggregationMethod) else str(agg_method)
            )
            method = method.lower()

            temporal_type = temporal_context.get(field, TemporalType.DERIVED)
            additivity = self._resolve_additivity(field, temporal_type, schema)

            if method == AggregationMethod.SUM.value:
                if additivity == Additivity.NON_ADDITIVE:
                    msg = f"Cannot sum non-additive variable '{field}'. Using 'first' instead."
                    if self.strict:
                        raise TransformError(msg)
                    corrections.append(f"{field}: sum → first (non-additive)")
                    warnings.append(msg)
                    validated_agg[field] = AggregationMethod.FIRST.value
                    continue

                if additivity == Additivity.SEMI_ADDITIVE and time_collapsing:
                    safe_agg = temporal_type.get_default_aggregation().value
                    msg = (
                        f"Cannot sum semi-additive variable '{field}' across time. "
                        f"Using '{safe_agg}' instead."
                    )
                    if self.strict:
                        raise TransformError(msg)
                    corrections.append(f"{field}: sum → {safe_agg} (semi-additive)")
                    warnings.append(msg)
                    validated_agg[field] = safe_agg
                    continue

                if additivity is None and time_collapsing:
                    warnings.append(f"Additivity unknown for '{field}'. Verify SUM over time.")

            if temporal_type == TemporalType.PARAMETER and method not in ("first", "last"):
                warnings.append(
                    f"Parameter '{field}' should be constant; "
                    f"consider 'first' or 'last' aggregation."
                )

            validated_agg[field] = method

        return validated_agg, corrections, warnings

    def _resolve_additivity(
        self,
        field: str,
        temporal_type: TemporalType,
        schema: DataSchema | None,
    ) -> Additivity | None:
        if field in self.additivity_context:
            return self.additivity_context[field]

        if schema is not None:
            spec = schema.get_field(field)
            if spec is not None and spec.additivity is not None:
                return spec.additivity

        if temporal_type == TemporalType.FLOW:
            return Additivity.ADDITIVE
        if temporal_type == TemporalType.STOCK:
            return Additivity.SEMI_ADDITIVE
        if temporal_type == TemporalType.PARAMETER:
            return Additivity.NON_ADDITIVE
        return None


# =============================================================================
# Utility Functions
# =============================================================================


def _freq_to_granularity(freq: Any) -> TimeGranularity | None:
    if freq is None:
        return None
    rule_code = getattr(freq, "rule_code", None)
    freq_str = str(rule_code or freq).upper()

    if freq_str.startswith("W"):
        return TimeGranularity.WEEKLY
    if freq_str.startswith("Q"):
        return TimeGranularity.QUARTERLY
    if freq_str.startswith("A") or freq_str.startswith("Y"):
        return TimeGranularity.ANNUAL

    mapping = {
        "S": TimeGranularity.SECOND,
        "SEC": TimeGranularity.SECOND,
        "MIN": TimeGranularity.MINUTE,
        "T": TimeGranularity.MINUTE,
        "H": TimeGranularity.HOURLY,
        "D": TimeGranularity.DAILY,
        "M": TimeGranularity.MONTHLY,
        "ME": TimeGranularity.MONTHLY,
        "MS": TimeGranularity.MONTHLY,
    }
    return mapping.get(freq_str)


def validate_temporal_aggregation(
    field: str,
    temporal_type: TemporalType,
    agg_method: str,
) -> tuple[bool, str | None]:
    """Validate that an aggregation method is appropriate for a temporal type."""
    if temporal_type == TemporalType.STOCK and agg_method.lower() == "sum":
        return False, f"Cannot sum Stock variable '{field}' across time"
    if temporal_type == TemporalType.PARAMETER and agg_method not in ["first", "last"]:
        return False, f"Parameter '{field}' should use 'first' or 'last' aggregation"
    return True, None
