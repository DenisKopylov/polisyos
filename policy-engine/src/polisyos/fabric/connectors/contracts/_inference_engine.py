"""
Schema inference engine.

Contains the SchemaInference class that performs automatic schema
inference from data samples, including type detection, unit inference,
semantic type detection, and time/geo dimension detection.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

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
from polisyos.fabric.numerics.finite import is_finite_number

from ._inference_config import InferenceConfig, SchemaHints
from ._inference_result import InferenceResult

logger = get_logger(__name__)

__all__ = [
    "GEO_CODE_PATTERNS",
    "SEMANTIC_PATTERNS",
    "UNIT_PATTERNS",
    "SchemaInference",
]


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
    r"^zip$|.*_zip$|^postal_code$|.*_postal_code$": SemanticType.CODE,
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
        self._semantic_patterns = {re.compile(p): sem for p, sem in SEMANTIC_PATTERNS.items()}
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
            warnings.append(f"Sampled {self._config.sample_rows} rows from {total_rows} total")

        # Infer fields
        fields: list[FieldSpec] = []
        for col in sample.columns:
            if col in hints.exclude_fields:
                continue

            field, confidence, field_warnings = self._infer_field(sample[col], col, hints)
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
            data_type = hints.field_types.get(name) or hints.field_types.get(normalized_name)
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
            numeric_series = self._finite_numeric_series(series)
            if not numeric_series.empty:
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
                        except Exception as exc:
                            logger.debug("Ignored exception: %s", exc)
                except Exception:
                    logger.debug(
                        "Failed to match datetime pattern %s on column sample",
                        pattern,
                        exc_info=True,
                    )
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
            sample = self._finite_numeric_series(series)
            if len(sample) > 0:
                min_val, max_val = sample.min(), sample.max()

                if min_val >= 0 and max_val <= 1 and (sample <= 1).all():
                    return SemanticType.RATIO

                if min_val >= 0 and max_val <= 100 and (sample <= 100).all():
                    return SemanticType.PERCENTAGE

                if (
                    data_type
                    in (
                        SchemaType.INT32,
                        SchemaType.INT64,
                        SchemaType.UINT32,
                        SchemaType.UINT64,
                    )
                    and min_val >= 0
                    and not self._is_count_excluded_name(name_lower)
                ):
                    return SemanticType.COUNT

        return None

    @staticmethod
    def _finite_numeric_series(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if numeric.empty:
            return numeric
        return numeric[numeric.map(is_finite_number)]

    @staticmethod
    def _is_count_excluded_name(name_lower: str) -> bool:
        protected_tokens = (
            "year",
            "date",
            "time",
            "period",
            "id",
            "key",
            "code",
            "zip",
            "postal",
        )
        return any(token in name_lower for token in protected_tokens)

    def _detect_time_dimension(
        self,
        df: pd.DataFrame,
        hints: SchemaHints,
        fields: list[FieldSpec],
    ) -> tuple[str | None, TimeGranularity | None]:
        """Detect time dimension and granularity."""
        if hints.time_dimension:
            time_col = hints.time_dimension
            granularity = hints.time_granularity or self._detect_time_granularity(df, time_col)
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
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

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
            if candidate in df.columns and df[candidate].is_unique:
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
                    f"Consider providing explicit type hint for '{name}' (confidence: {conf:.0%})"
                )

        if not schema.primary_key:
            suggestions.append("No primary key detected. Consider providing primary_key hint.")

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
        normalized = unicodedata.normalize("NFKC", name)
        normalized = re.sub(r"[\s\-]+", "_", normalized)
        normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", normalized)
        normalized = normalized.casefold()
        encoded_chars: list[str] = []
        for char in normalized:
            if char.isascii():
                encoded_chars.append(char if char.isalnum() or char == "_" else "_")
            elif unicodedata.category(char)[:1] in {"L", "N"}:
                encoded_chars.append(f"u{ord(char):04x}")
            else:
                encoded_chars.append("_")
        normalized = "".join(encoded_chars)
        normalized = re.sub(r"_+", "_", normalized)
        normalized = normalized.strip("_")

        if normalized and normalized[0].isdigit():
            normalized = "col_" + normalized

        return normalized or "unnamed"
