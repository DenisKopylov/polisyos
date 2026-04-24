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
# Coercion Module
# =============================================================================
from polisyos.fabric.connectors.types.coercion import (
    CoercionError,
    CoercionPolicy,
    CoercionResult,
    CoercionRule,
    PrecisionLossWarning,
    TypeCoercion,
    can_safely_cast,
    get_coercion_path,
    safe_cast,
)

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
    BaseDimension,
    Dimension,
    DimensionError,
    DimensionRegistry,
    IncompatibleDimensionsError,
    get_dimension_registry,
)

# =============================================================================
# Temporal Module
# =============================================================================
from polisyos.fabric.connectors.types.temporal import (
    AggregationMethod,
    StockFlowCombination,
    TemporalAggregationError,
    TemporalSemantics,
    TemporalType,
    TemporalVariable,
    TimeGrain,
    TimeInterval,
    infer_temporal_type,
    validate_temporal_aggregation,
)

# =============================================================================
# Units Module
# =============================================================================
from polisyos.fabric.connectors.types.units import (
    BaseUnit,
    ConversionFactor,
    MetricPrefix,
    Unit,
    UnitConversionError,
    UnitParseError,
    UnitRegistry,
    get_unit_registry,
    parse_unit,
)

# =============================================================================
# Public API
# =============================================================================
__all__ = [
    "AggregationMethod",
    "BaseDimension",
    "BaseUnit",
    "CapabilityError",
    "CoercionError",
    "CoercionPolicy",
    "CoercionResult",
    "CoercionRule",
    "ConfigurationError",
    "ConnectionError",
    # Connector core types
    "ConnectorError",
    "ConversionFactor",
    "DataChunk",
    "DatasetDescriptor",
    # Dimensions
    "Dimension",
    "DimensionError",
    "DimensionRegistry",
    "FetchError",
    "FreshnessResult",
    "FreshnessStatus",
    "IncompatibleDimensionsError",
    "MetricPrefix",
    "PrecisionLossWarning",
    "RateLimitError",
    "RateLimitStatus",
    "SchemaError",
    "StockFlowCombination",
    "TemporalAggregationError",
    "TemporalSemantics",
    # Temporal
    "TemporalType",
    "TemporalVariable",
    "TimeGrain",
    "TimeInterval",
    # Coercion
    "TypeCoercion",
    # Units
    "Unit",
    "UnitConversionError",
    "UnitParseError",
    "UnitRegistry",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "can_safely_cast",
    "get_coercion_path",
    "get_dimension_registry",
    "get_unit_registry",
    "infer_temporal_type",
    "parse_unit",
    "safe_cast",
    "validate_temporal_aggregation",
]


# =============================================================================
# Version Information
# =============================================================================
__version__ = "0.1.0"
