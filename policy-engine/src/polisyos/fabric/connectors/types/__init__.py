"""
Type system for connector data operations.

This package provides dimensional analysis, unit algebra, temporal semantics,
and safe type coercion for the PolicyOS data fabric connector system.

The type system ensures:
- Physical dimension compatibility (prevents adding GDP to Population)
- Unit conversion safety (km -> m, USD -> EUR with rates)
- Temporal aggregation correctness (Stock vs Flow handling)
- Precision-safe type coercion (no silent data loss)

Integration Points:
- ir/kernel/units.py: Kernel unit definitions (semantic types)
- fabric/connectors/contracts/schema.py: DataSchema with FieldSpec
- fabric/connectors/transform/: Transformation pipeline

Example:
    >>> from polisyos.fabric.connectors.types import (
    ...     Unit, Dimension, TemporalType, safe_cast
    ... )
    >>>
    >>> # Unit algebra
    >>> speed = Unit.parse("km/h")
    >>> assert speed.is_compatible_with(Unit.parse("m/s"))
    >>>
    >>> # Dimensional analysis
    >>> velocity_dim = Dimension(length=1, time=-1)
    >>> assert speed.dimension == velocity_dim
    >>>
    >>> # Temporal semantics
    >>> assert TemporalType.FLOW.can_sum_over_time
    >>> assert not TemporalType.STOCK.can_sum_over_time
    >>>
    >>> # Safe coercion
    >>> result = safe_cast(42, target_type="float64")
"""
from __future__ import annotations

# =============================================================================
# Connector Core Types (from legacy module)
# =============================================================================
from polisyos.fabric.connectors.types.connector_types import (
    CapabilityError,
    ConfigurationError,
    ConnectionError,
    ConnectorError,
    DataChunk,
    DatasetDescriptor,
    FetchError,
    FreshnessResult,
    FreshnessStatus,
    RateLimitError,
    RateLimitStatus,
    SchemaError,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

# =============================================================================
# Dimensions Module
# =============================================================================
from polisyos.fabric.connectors.types.dimensions import (
    Dimension,
    DimensionRegistry,
    BaseDimension,
    DimensionError,
    IncompatibleDimensionsError,
    get_dimension_registry,
)

# =============================================================================
# Units Module
# =============================================================================
from polisyos.fabric.connectors.types.units import (
    Unit,
    UnitRegistry,
    BaseUnit,
    ConversionFactor,
    MetricPrefix,
    UnitParseError,
    UnitConversionError,
    get_unit_registry,
    parse_unit,
)

# =============================================================================
# Temporal Module
# =============================================================================
from polisyos.fabric.connectors.types.temporal import (
    TemporalType,
    TimeGrain,
    AggregationMethod,
    TemporalVariable,
    TimeInterval,
    TemporalSemantics,
    StockFlowCombination,
    TemporalAggregationError,
    validate_temporal_aggregation,
    infer_temporal_type,
)

# =============================================================================
# Coercion Module
# =============================================================================
from polisyos.fabric.connectors.types.coercion import (
    TypeCoercion,
    CoercionPolicy,
    CoercionResult,
    CoercionRule,
    CoercionError,
    PrecisionLossWarning,
    safe_cast,
    can_safely_cast,
    get_coercion_path,
)


# =============================================================================
# Public API
# =============================================================================
__all__ = [
    # Connector core types
    "ConnectorError",
    "CapabilityError",
    "ConfigurationError",
    "ConnectionError",
    "FetchError",
    "RateLimitError",
    "SchemaError",
    "DataChunk",
    "DatasetDescriptor",
    "FreshnessResult",
    "FreshnessStatus",
    "RateLimitStatus",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    # Dimensions
    "Dimension",
    "DimensionRegistry",
    "BaseDimension",
    "DimensionError",
    "IncompatibleDimensionsError",
    "get_dimension_registry",
    # Units
    "Unit",
    "UnitRegistry",
    "BaseUnit",
    "ConversionFactor",
    "MetricPrefix",
    "UnitParseError",
    "UnitConversionError",
    "get_unit_registry",
    "parse_unit",
    # Temporal
    "TemporalType",
    "TimeGrain",
    "AggregationMethod",
    "TemporalVariable",
    "TimeInterval",
    "TemporalSemantics",
    "StockFlowCombination",
    "TemporalAggregationError",
    "validate_temporal_aggregation",
    "infer_temporal_type",
    # Coercion
    "TypeCoercion",
    "CoercionPolicy",
    "CoercionResult",
    "CoercionRule",
    "CoercionError",
    "PrecisionLossWarning",
    "safe_cast",
    "can_safely_cast",
    "get_coercion_path",
]


# =============================================================================
# Version Information
# =============================================================================
__version__ = "0.1.0"
