"""
Automatic schema inference from data samples.

Used when connectors don't provide explicit schemas,
or to validate provided schemas against actual data.

Inference Pipeline:
1. Sample data (if large)
2. Infer data types per column
3. Detect units from naming patterns
4. Identify semantic types
5. Detect time/geo dimensions
6. Generate schema with confidence scores
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    GeoGranularity,
    SchemaType,
    SchemaVersion,
    SemanticType,
    TimeGranularity,
)

logger = get_logger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class InferenceConfig(BaseModel):
    """Configuration for schema inference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Sampling
    sample_rows: int = Field(default=1000, ge=100, le=100000)

    # Type inference thresholds
    null_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Above this null ratio, field is considered nullable",
    )
    category_threshold: int = Field(
        default=50,
        ge=2,
        le=1000,
        description="Below this unique count, infer CATEGORY",
    )
    category_ratio_threshold: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="Max ratio of unique values to total for CATEGORY",
    )

    # Float handling
    prefer_float32: bool = Field(
        default=True,
        description="Prefer FLOAT32 when inference detects floating-point data",
    )

    # Pattern detection
    datetime_patterns: tuple[str, ...] = (
        r"\d{4}-\d{2}-\d{2}",  # ISO date
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO datetime
        r"\d{2}/\d{2}/\d{4}",  # US date
        r"\d{2}\.\d{2}\.\d{4}",  # European date
    )

    # Confidence thresholds
    min_pattern_confidence: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Minimum match rate for pattern-based inference",
    )


class SchemaHints(BaseModel):
    """User-provided hints to guide inference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Explicit type overrides
    field_types: dict[str, SchemaType] = Field(default_factory=dict)
    field_units: dict[str, str] = Field(default_factory=dict)
    field_semantic_types: dict[str, SemanticType] = Field(default_factory=dict)

    # Structure hints
    primary_key: tuple[str, ...] = ()
    time_dimension: str | None = None
    geo_dimension: str | None = None

    # Granularity hints
    time_granularity: TimeGranularity | None = None
    geo_granularity: GeoGranularity | None = None

    # Fields to exclude
    exclude_fields: frozenset[str] = frozenset()


class InferenceResult(BaseModel):
    """Result of schema inference with confidence scores."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema: DataSchema

    # Confidence scores per field
    field_confidences: dict[str, float] = Field(default_factory=dict)

    # Warnings and suggestions
    warnings: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()

    # Inference metadata
    sample_size: int = 0
    inference_time_ms: float = 0.0

    @property
    def overall_confidence(self) -> float:
        """Average confidence across all fields."""
        if not self.field_confidences:
            return 0.0
        return sum(self.field_confidences.values()) / len(self.field_confidences)


# =============================================================================
# Inference Patterns
# =============================================================================


# Unit inference patterns (field name -> unit id)
UNIT_PATTERNS: dict[str, str] = {
    r".*_usd$": "usd",
    r".*_eur$": "eur",
    r".*_uah$": "uah",
    r".*_gbp$": "gbp",
    r".*_jpy$": "jpy",
    r".*_pct$": "percent",
    r".*_percent$": "percent",
    r".*_rate$": "ratio",
    r".*_ratio$": "ratio",
    r".*_count$": "count",
    r".*_num$": "count",
    r".*_population$": "persons",
    r".*_pop$": "persons",
    r"^population$": "persons",
    r"^pop$": "persons",
    r".*_area_km2$": "km2",
    r".*_area_sqkm$": "km2",
    r".*_distance_km$": "km",
    r".*_km$": "km",
    r".*_meters?$": "m",
    r".*_kg$": "kg",
    r".*_tonnes?$": "tonnes",
    r".*_gdp$": "usd",
    r".*_revenue$": "usd",
    r".*_income$": "usd",
    r".*_salary$": "usd",
}

# Semantic type patterns (field name -> SemanticType)
SEMANTIC_PATTERNS: dict[str, SemanticType] = {
    # Identifiers
    r".*_id$": SemanticType.IDENTIFIER,
    r"^id$": SemanticType.IDENTIFIER,
    r".*_code$": SemanticType.CODE,
    r".*_key$": SemanticType.IDENTIFIER,
    r".*_uuid$": SemanticType.IDENTIFIER,

    # Currency
    r".*_usd$|.*_eur$|.*_uah$|.*_gbp$|.*_jpy$": SemanticType.CURRENCY,
    r".*_price$|.*_cost$|.*_amount$": SemanticType.CURRENCY,
    r".*_revenue$|.*_income$|.*_salary$": SemanticType.CURRENCY,

    # Percentages and ratios
    r".*_pct$|.*_percent$": SemanticType.PERCENTAGE,
    r".*_rate$": SemanticType.RATE,
    r".*_ratio$": SemanticType.RATIO,

    # Counts
    r".*_count$|.*_num$|.*_qty$": SemanticType.COUNT,
    r".*_population$|.*_pop$|^population$|^pop$": SemanticType.POPULATION,

    # Spatial
    r".*_area$": SemanticType.AREA,
    r".*_distance$": SemanticType.DISTANCE,
    r"^lat$|^latitude$|.*_lat$": SemanticType.LATITUDE,
    r"^lon$|^lng$|^longitude$|.*_lon$|.*_lng$": SemanticType.LONGITUDE,

    # Temporal
    r"^year$|^month$|^date$|^period$|^time$": SemanticType.TEMPORAL,
    r".*_date$|.*_time$|.*_at$": SemanticType.TEMPORAL,

    # Geospatial
    r"^country$|^region$|^oblast$|^city$": SemanticType.GEOSPATIAL,
    r".*_country$|.*_region$|.*_oblast$": SemanticType.GEOSPATIAL,

    # Text
    r"^name$|.*_name$": SemanticType.NAME,
    r"^description$|.*_description$|.*_desc$": SemanticType.DESCRIPTION,
}

# Geographic code patterns for GeoGranularity detection
GEO_CODE_PATTERNS: dict[str, GeoGranularity] = {
    r"^[A-Z]{2}$": GeoGranularity.COUNTRY,  # ISO 3166-1 alpha-2
    r"^[A-Z]{3}$": GeoGranularity.COUNTRY,  # ISO 3166-1 alpha-3
    r"^UA-\d{2}$": GeoGranularity.OBLAST,  # Ukraine oblast codes
    r"^\d{5}$": GeoGranularity.POSTAL,  # 5-digit postal codes
}


# =============================================================================
# Schema Inference Class
# =============================================================================


class SchemaInference:
    """
    Automatic schema inference from data samples.

    Usage:
        inference = SchemaInference()
        result = inference.infer_from_sample(df, hints=SchemaHints(...))
        schema = result.schema
    """

    def __init__(self, config: InferenceConfig | None = None) -> None:
        self._config = config or InferenceConfig()

        # Compile regex patterns once
        self._unit_patterns = {re.compile(p): unit for p, unit in UNIT_PATTERNS.items()}
        self._semantic_patterns = {
            re.compile(p): sem for p, sem in SEMANTIC_PATTERNS.items()
        }
        self._geo_patterns = {re.compile(p): geo for p, geo in GEO_CODE_PATTERNS.items()}

    def infer_from_sample(
        self,
        sample: pd.DataFrame,
        hints: SchemaHints | None = None,
        schema_id: str = "inferred",
    ) -> InferenceResult:
        """
        Infer schema from a data sample.

        Args:
            sample: DataFrame to analyze
            hints: Optional user-provided hints
            schema_id: ID for the generated schema

        Returns:
            InferenceResult with schema and confidence scores
        """
        import time

        start_time = time.perf_counter()

        hints = hints or SchemaHints()
        warnings: list[str] = []
        suggestions: list[str] = []
        field_confidences: dict[str, float] = {}

        # Sample if needed
        total_rows = len(sample)
        if total_rows > self._config.sample_rows:
            sample = sample.sample(n=self._config.sample_rows, random_state=42)
            warnings.append(
                f"Sampled {self._config.sample_rows} rows from {total_rows} total"
            )

        # Infer fields
        fields: list[FieldSpec] = []
        for col in sample.columns:
            if col in hints.exclude_fields:
                continue

            field, confidence, field_warnings = self._infer_field(
                sample[col], col, hints
            )
            fields.append(field)
            field_confidences[field.name] = confidence
            warnings.extend(field_warnings)

        if not fields:
            raise ValueError("No fields to infer after applying exclusions")

        # Detect dimensions
        time_dim, time_gran = self._detect_time_dimension(sample, hints, fields)
        geo_dim, geo_gran = self._detect_geo_dimension(sample, hints, fields)

        # Infer primary key
        primary_key = hints.primary_key or self._infer_primary_key(sample, fields)

        # Create schema
        schema = DataSchema(
            schema_id=schema_id,
            version=SchemaVersion(1, 0, 0),
            fields=tuple(fields),
            primary_key=primary_key,
            time_dimension=time_dim,
            time_granularity=time_gran,
            geo_dimension=geo_dim,
            geo_granularity=geo_gran,
        )

        # Generate suggestions
        suggestions.extend(self._generate_suggestions(schema, sample, field_confidences))

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return InferenceResult(
            schema=schema,
            field_confidences=field_confidences,
            warnings=tuple(warnings),
            suggestions=tuple(suggestions),
            sample_size=len(sample),
            inference_time_ms=elapsed_ms,
        )

    def _infer_field(
        self,
        series: pd.Series,
        name: str,
        hints: SchemaHints,
    ) -> tuple[FieldSpec, float, list[str]]:
        """
        Infer field specification from a pandas Series.

        Returns:
            Tuple of (FieldSpec, confidence score 0-1, warnings)
        """
        warnings: list[str] = []
        confidence = 1.0

        # Normalize name
        normalized_name = self._normalize_column_name(name)

        # Use hint if provided, otherwise infer
        if name in hints.field_types or normalized_name in hints.field_types:
            data_type = hints.field_types.get(name) or hints.field_types.get(
                normalized_name
            )
            confidence = 1.0
        else:
            data_type, type_confidence = self._infer_data_type(series)
            confidence *= type_confidence

        # Infer unit
        unit = (
            hints.field_units.get(name)
            or hints.field_units.get(normalized_name)
            or self._infer_unit(normalized_name)
        )

        # Infer semantic type
        semantic = (
            hints.field_semantic_types.get(name)
            or hints.field_semantic_types.get(normalized_name)
            or self._infer_semantic_type(normalized_name, series, data_type)
        )

        # Compute bounds for numeric types
        bounds: tuple[float | None, float | None] = (None, None)
        if data_type.is_numeric():
            numeric_series = pd.to_numeric(series, errors="coerce")
            if not numeric_series.isna().all():
                bounds = (
                    float(numeric_series.min()),
                    float(numeric_series.max()),
                )

        # Infer allowed values for category
        allowed_values: frozenset[str] | None = None
        if data_type == SchemaType.CATEGORY:
            unique = series.dropna().unique()
            if len(unique) <= self._config.category_threshold:
                allowed_values = frozenset(str(v) for v in unique)

        # Compute completeness
        null_ratio = series.isna().mean()
        completeness = 1.0 - null_ratio
        nullable = null_ratio > self._config.null_threshold
        if 0.0 < null_ratio <= self._config.null_threshold:
            warnings.append(
                f"Field '{normalized_name}' has rare nulls ({null_ratio:.1%}); "
                "consider marking nullable if expected."
            )

        field = FieldSpec(
            name=normalized_name,
            data_type=data_type,
            unit=unit,
            semantic_type=semantic,
            nullable=nullable,
            bounds=bounds,
            allowed_values=allowed_values,
            source_name=name if name != normalized_name else "",
            expected_completeness=completeness,
        )

        return field, confidence, warnings

    def _infer_data_type(self, series: pd.Series) -> tuple[SchemaType, float]:
        """
        Infer data type from pandas Series.

        Returns:
            Tuple of (SchemaType, confidence score)
        """
        dtype = series.dtype

        # Integer detection
        if pd.api.types.is_integer_dtype(dtype):
            if series.min() >= 0:
                if series.max() <= 255:
                    return SchemaType.UINT8, 0.95
                if series.max() <= 65535:
                    return SchemaType.UINT16, 0.95
                if series.max() <= 4294967295:
                    return SchemaType.UINT32, 0.95
                return SchemaType.UINT64, 0.95
            if series.min() >= -128 and series.max() <= 127:
                return SchemaType.INT8, 0.95
            if series.min() >= -32768 and series.max() <= 32767:
                return SchemaType.INT16, 0.95
            if series.min() >= -(2**31) and series.max() < 2**31:
                return SchemaType.INT32, 0.95
            return SchemaType.INT64, 0.95

        # Float detection
        if pd.api.types.is_float_dtype(dtype):
            if self._config.prefer_float32:
                return SchemaType.FLOAT32, 0.95
            return SchemaType.FLOAT64, 0.95

        # Boolean detection
        if pd.api.types.is_bool_dtype(dtype):
            return SchemaType.BOOLEAN, 1.0

        # Datetime detection
        if pd.api.types.is_datetime64_any_dtype(dtype):
            if hasattr(dtype, "tz") and dtype.tz is not None:
                return SchemaType.TIMESTAMP_TZ, 1.0
            return SchemaType.DATETIME, 1.0

        # Timedelta detection
        if pd.api.types.is_timedelta64_dtype(dtype):
            return SchemaType.DURATION, 1.0

        # Categorical detection
        if isinstance(dtype, pd.CategoricalDtype):
            return SchemaType.CATEGORY, 1.0

        # String/object detection with pattern matching
        if series.dtype == object:
            sample = series.dropna().head(100)

            if len(sample) == 0:
                return SchemaType.STRING, 0.5

            # Try datetime patterns
            for pattern in self._config.datetime_patterns:
                try:
                    match_rate = sample.astype(str).str.match(pattern).mean()
                    if match_rate >= self._config.min_pattern_confidence:
                        try:
                            pd.to_datetime(sample.head(10))
                            return SchemaType.DATETIME, match_rate
                        except Exception:
                            pass
                except Exception:
                    continue

            # Check for category (low cardinality)
            unique_count = series.nunique(dropna=True)
            total_count = len(series.dropna())
            unique_ratio = unique_count / total_count if total_count > 0 else 1.0

            if (
                unique_count <= self._config.category_threshold
                and unique_ratio <= self._config.category_ratio_threshold
            ):
                return SchemaType.CATEGORY, 0.85

            # Check for boolean-like strings
            lower_vals = set(sample.astype(str).str.lower().unique())
            bool_sets = [
                {"true", "false"},
                {"yes", "no"},
                {"y", "n"},
                {"1", "0"},
                {"t", "f"},
            ]
            for bool_set in bool_sets:
                if lower_vals.issubset(bool_set):
                    return SchemaType.BOOLEAN, 0.85

            return SchemaType.STRING, 0.8

        return SchemaType.STRING, 0.5

    def _infer_unit(self, name: str) -> str | None:
        """Infer unit from field name patterns."""
        name_lower = name.lower()
        for pattern, unit in self._unit_patterns.items():
            if pattern.match(name_lower):
                return unit
        return None

    def _infer_semantic_type(
        self,
        name: str,
        series: pd.Series,
        data_type: SchemaType,
    ) -> SemanticType | None:
        """Infer semantic type from name and content."""
        name_lower = name.lower()

        for pattern, semantic in self._semantic_patterns.items():
            if pattern.match(name_lower):
                return semantic

        if data_type.is_numeric():
            if data_type == SchemaType.BOOLEAN:
                return None
            sample = series.dropna()
            if len(sample) > 0:
                min_val, max_val = sample.min(), sample.max()

                if 0 <= min_val and max_val <= 100:
                    if (sample >= 0).all() and (sample <= 100).all():
                        return SemanticType.PERCENTAGE

                if 0 <= min_val and max_val <= 1:
                    if (sample >= 0).all() and (sample <= 1).all():
                        return SemanticType.RATIO

                if data_type in (
                    SchemaType.INT32,
                    SchemaType.INT64,
                    SchemaType.UINT32,
                    SchemaType.UINT64,
                ):
                    if min_val >= 0:
                        return SemanticType.COUNT

        return None

    def _detect_time_dimension(
        self,
        df: pd.DataFrame,
        hints: SchemaHints,
        fields: list[FieldSpec],
    ) -> tuple[str | None, TimeGranularity | None]:
        """Detect time dimension and granularity."""
        if hints.time_dimension:
            time_col = hints.time_dimension
            granularity = hints.time_granularity or self._detect_time_granularity(
                df, time_col
            )
            return time_col, granularity

        time_candidates = [
            "year",
            "date",
            "period",
            "time",
            "month",
            "quarter",
            "timestamp",
        ]

        for field in fields:
            name_lower = field.name.lower()

            if name_lower in time_candidates or any(tc in name_lower for tc in time_candidates):
                granularity = self._detect_time_granularity(df, field.name)
                return field.name, granularity

            if field.data_type in (
                SchemaType.DATETIME,
                SchemaType.TIMESTAMP_TZ,
                SchemaType.DATE,
            ):
                granularity = self._detect_time_granularity(df, field.name)
                return field.name, granularity

            if field.semantic_type == SemanticType.TEMPORAL:
                granularity = self._detect_time_granularity(df, field.name)
                return field.name, granularity

        return None, None

    def _detect_time_granularity(
        self,
        df: pd.DataFrame,
        time_col: str,
    ) -> TimeGranularity | None:
        """Detect temporal granularity from data."""
        if time_col not in df.columns:
            return None

        col = df[time_col]
        name_lower = time_col.lower()

        if "year" in name_lower:
            return TimeGranularity.ANNUAL
        if "quarter" in name_lower:
            return TimeGranularity.QUARTERLY
        if "month" in name_lower:
            return TimeGranularity.MONTHLY
        if "week" in name_lower:
            return TimeGranularity.WEEKLY
        if "day" in name_lower or "daily" in name_lower:
            return TimeGranularity.DAILY
        if "hour" in name_lower:
            return TimeGranularity.HOURLY

        try:
            if not pd.api.types.is_datetime64_any_dtype(col):
                col = pd.to_datetime(col, errors="coerce")

            sorted_vals = col.dropna().sort_values()
            if len(sorted_vals) > 1:
                diffs = sorted_vals.diff().dropna()
                median_days = diffs.dt.days.median()

                if median_days <= 1:
                    return TimeGranularity.DAILY
                if median_days <= 7:
                    return TimeGranularity.WEEKLY
                if median_days <= 31:
                    return TimeGranularity.MONTHLY
                if median_days <= 92:
                    return TimeGranularity.QUARTERLY
                return TimeGranularity.ANNUAL
        except Exception:
            pass

        return None

    def _detect_geo_dimension(
        self,
        df: pd.DataFrame,
        hints: SchemaHints,
        fields: list[FieldSpec],
    ) -> tuple[str | None, GeoGranularity | None]:
        """Detect geographic dimension and granularity."""
        if hints.geo_dimension:
            granularity = hints.geo_granularity or self._detect_geo_granularity(
                df, hints.geo_dimension
            )
            return hints.geo_dimension, granularity

        geo_candidates = [
            "country",
            "region",
            "oblast",
            "raion",
            "hromada",
            "city",
            "geo_code",
            "location",
        ]

        for field in fields:
            name_lower = field.name.lower()

            if name_lower in geo_candidates or any(gc in name_lower for gc in geo_candidates):
                granularity = self._detect_geo_granularity(df, field.name)
                return field.name, granularity

            if field.semantic_type == SemanticType.GEOSPATIAL:
                granularity = self._detect_geo_granularity(df, field.name)
                return field.name, granularity

        return None, None

    def _detect_geo_granularity(
        self,
        df: pd.DataFrame,
        geo_col: str,
    ) -> GeoGranularity | None:
        """Detect geographic granularity from data."""
        if geo_col not in df.columns:
            return None

        col = df[geo_col]
        name_lower = geo_col.lower()

        if "country" in name_lower:
            return GeoGranularity.COUNTRY
        if "oblast" in name_lower:
            return GeoGranularity.OBLAST
        if "raion" in name_lower:
            return GeoGranularity.RAION
        if "hromada" in name_lower:
            return GeoGranularity.HROMADA
        if "region" in name_lower:
            return GeoGranularity.REGION
        if "city" in name_lower:
            return GeoGranularity.CITY

        sample = col.dropna().head(100).astype(str)
        for pattern, granularity in self._geo_patterns.items():
            match_rate = sample.str.match(pattern).mean()
            if match_rate >= 0.9:
                return granularity

        return None

    def _infer_primary_key(
        self,
        df: pd.DataFrame,
        fields: list[FieldSpec],
    ) -> tuple[str, ...]:
        """
        Attempt to infer primary key from data.

        Heuristics:
        1. Look for _id or _key suffixes
        2. Check for uniqueness
        """
        candidates: list[str] = []

        for field in fields:
            if (
                field.name.endswith("_id")
                or field.name.endswith("_key")
                or field.name == "id"
                or field.semantic_type == SemanticType.IDENTIFIER
            ):
                candidates.append(field.name)

        for candidate in candidates:
            if candidate in df.columns:
                if df[candidate].is_unique:
                    return (candidate,)

        return ()

    def _generate_suggestions(
        self,
        schema: DataSchema,
        df: pd.DataFrame,
        confidences: dict[str, float],
    ) -> list[str]:
        """Generate improvement suggestions based on inference results."""
        suggestions: list[str] = []

        for name, conf in confidences.items():
            if conf < 0.7:
                suggestions.append(
                    f"Consider providing explicit type hint for '{name}' "
                    f"(confidence: {conf:.0%})"
                )

        if not schema.primary_key:
            suggestions.append(
                "No primary key detected. Consider providing primary_key hint."
            )

        if not schema.time_dimension:
            temporal_fields = [
                f.name
                for f in schema.fields
                if f.data_type.is_temporal() or f.semantic_type == SemanticType.TEMPORAL
            ]
            if temporal_fields:
                suggestions.append(
                    f"Temporal fields detected ({temporal_fields}) but no time_dimension set. "
                    "Consider providing time_dimension hint."
                )

        for field in schema.fields:
            if field.expected_completeness < 0.5:
                suggestions.append(
                    f"Field '{field.name}' has low completeness "
                    f"({field.expected_completeness:.0%}). Verify data quality."
                )

        return suggestions

    @staticmethod
    def _normalize_column_name(name: str) -> str:
        """
        Normalize column name to snake_case.

        Examples:
            "GDP Growth Rate" -> "gdp_growth_rate"
            "countryCode" -> "country_code"
            "UNEMPLOYMENT_RATE" -> "unemployment_rate"
        """
        normalized = re.sub(r"[\s\-]+", "_", name)
        normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", normalized)
        normalized = normalized.lower()
        normalized = re.sub(r"[^a-z0-9_]", "", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        normalized = normalized.strip("_")

        if normalized and normalized[0].isdigit():
            normalized = "col_" + normalized

        return normalized or "unnamed"


# =============================================================================
# Convenience Functions
# =============================================================================


@dataclass(frozen=True)
class CoercionResult:
    """Result of coercing a DataFrame to a schema."""

    dataframe: pd.DataFrame
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    coerced_columns: tuple[str, ...]
    dropped_columns: tuple[str, ...]


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

    schema_fields = {f.name for f in schema.fields}
    df_columns = set(df.columns)

    missing = schema_fields - df_columns
    if missing:
        errors.append(f"Missing required columns: {missing}")

    if strict:
        extra = df_columns - schema_fields
        if extra:
            errors.append(f"Extra columns not in schema: {extra}")

    for field in schema.fields:
        if field.name not in df.columns:
            continue

        col = df[field.name]

        if (
            not field.nullable
            and field.name not in schema.allowed_null_fields
            and col.isna().any()
        ):
            null_count = col.isna().sum()
            errors.append(
                f"Field '{field.name}' has {null_count} null values but is not nullable"
            )

        if field.data_type.is_numeric() and field.bounds != (None, None):
            numeric_col = pd.to_numeric(col, errors="coerce")
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

        if field.allowed_values:
            invalid = set(col.dropna().astype(str)) - field.allowed_values
            if invalid:
                errors.append(
                    f"Field '{field.name}' has invalid values: {invalid}"
                )

        if field.pattern and field.data_type in (SchemaType.STRING, SchemaType.CATEGORY):
            pattern = re.compile(field.pattern)
            invalid = [
                value
                for value in col.dropna().astype(str).unique()
                if not pattern.match(value)
            ]
            if invalid:
                errors.append(
                    f"Field '{field.name}' has values not matching pattern: {invalid}"
                )

        if field.max_length and field.data_type in (
            SchemaType.STRING,
            SchemaType.CATEGORY,
            SchemaType.BINARY,
        ):
            too_long = col.dropna().astype(str).str.len() > field.max_length
            if too_long.any():
                count = int(too_long.sum())
                errors.append(
                    f"Field '{field.name}' has {count} values exceeding max_length {field.max_length}"
                )

        completeness = 1.0 - col.isna().mean()
        if (
            field.name not in schema.allowed_null_fields
            and completeness < schema.required_completeness
        ):
            errors.append(
                f"Field '{field.name}' completeness {completeness:.1%} below required {schema.required_completeness:.1%}"
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
        for col in df_work.columns:
            normalized = SchemaInference._normalize_column_name(col)
            if normalized in normalized_map:
                warnings.append(
                    f"Column '{col}' normalized to '{normalized}' conflicts with '{normalized_map[normalized]}'"
                )
                continue
            normalized_map[normalized] = col

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
        extra = [col for col in df_work.columns if col not in schema_fields]
        if extra:
            df_work = df_work.drop(columns=extra)
            dropped_columns.extend(extra)
    elif strict:
        extra = [col for col in df_work.columns if col not in schema_fields]
        if extra:
            errors.append(f"Extra columns not in schema: {set(extra)}")

    for field in schema.fields:
        if field.name not in df_work.columns:
            errors.append(f"Missing required column '{field.name}'")
            continue

        col = df_work[field.name]
        try:
            if field.data_type == SchemaType.BOOLEAN:
                df_work[field.name] = _coerce_boolean(col)
                coerced_columns.append(field.name)
            elif field.data_type.is_numeric():
                df_work[field.name] = pd.to_numeric(col, errors="coerce")
                df_work[field.name] = df_work[field.name].astype(
                    field.data_type.to_pandas_dtype()
                )
                coerced_columns.append(field.name)
            elif field.data_type in (SchemaType.DATETIME, SchemaType.TIMESTAMP_TZ):
                df_work[field.name] = pd.to_datetime(col, errors="coerce", utc=True)
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.DATE:
                df_work[field.name] = pd.to_datetime(col, errors="coerce").dt.date
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.DURATION:
                df_work[field.name] = pd.to_timedelta(col, errors="coerce")
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.CATEGORY:
                df_work[field.name] = col.astype("category")
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.STRING:
                df_work[field.name] = col.astype("string")
                coerced_columns.append(field.name)
            elif field.data_type == SchemaType.DECIMAL:
                df_work[field.name] = col.apply(_coerce_decimal)
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

    def _to_bool(value: Any) -> Any:
        if pd.isna(value):
            return pd.NA
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(int(value))
        key = str(value).strip().lower()
        return mapping.get(key, pd.NA)

    return series.map(_to_bool).astype("boolean")


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None
