"""
Temporal semantics for time-series aggregation and analysis.

This module defines the behavior for time-series data based on whether
values represent Stocks (point-in-time) or Flows (period-based):

Stock Variables (Levels):
- Represent a quantity at a specific point in time
- Examples: Inventory, Population, Account Balance, GDP level
- Aggregation rules: AVERAGE, LAST, FIRST (never SUM)
- Summing stock values across time periods is meaningless

Flow Variables (Rates):
- Represent a quantity over a time period
- Examples: Revenue, Births, Expenses, Production
- Aggregation rules: SUM, AVERAGE
- Can be meaningfully summed across time periods

This distinction is critical for preventing logical errors in policy
analysis. For example:
- Revenue Q1 + Revenue Q2 = Revenue H1 (valid - flow)
- Balance Q1 + Balance Q2 != Balance H1 (invalid - stock)

Integration with ir/kernel/slots.py:
- Kernel slots have SlotKind (STOCK, FLOW, PARAMETER)
- This module provides the aggregation semantics for connector data
- The mapping enables automatic aggregation rule inference

Example:
    >>> from polisyos.fabric.connectors.types.temporal import (
    ...     TemporalType, TemporalVariable, AggregationMethod
    ... )
    >>> revenue = TemporalVariable(
    ...     name="quarterly_revenue",
    ...     temporal_type=TemporalType.FLOW,
    ...     time_grain=TimeGrain.QUARTERLY,
    ... )
    >>> assert revenue.can_sum_over_time
    >>> assert revenue.default_aggregation == AggregationMethod.SUM
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import ClassVar, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "TemporalType",
    "TimeGrain",
    "AggregationMethod",
    "TemporalVariable",
    "TemporalAggregationError",
    "TimeInterval",
    "TemporalSemantics",
    "StockFlowCombination",
    "validate_temporal_aggregation",
    "infer_temporal_type",
]


# =============================================================================
# Exceptions
# =============================================================================


class TemporalAggregationError(ValueError):
    """Raised when an invalid temporal aggregation is attempted."""

    def __init__(
        self,
        variable_name: str,
        temporal_type: "TemporalType",
        attempted_method: "AggregationMethod",
        reason: str,
    ):
        self.variable_name = variable_name
        self.temporal_type = temporal_type
        self.attempted_method = attempted_method
        self.reason = reason
        super().__init__(
            f"Invalid aggregation for '{variable_name}' ({temporal_type.value}): "
            f"cannot use {attempted_method.value} - {reason}"
        )


# =============================================================================
# Enums
# =============================================================================


class TemporalType(str, Enum):
    """
    Classification of time-series variables by their temporal semantics.

    This enum determines how values can be aggregated across time periods
    and what operations are mathematically meaningful.

    Attributes:
        STOCK: Point-in-time values (levels, balances, states)
        FLOW: Period-based values (rates, changes, movements)
        PARAMETER: Time-invariant configuration values
        DERIVED: Values computed from other variables (inherit semantics)
    """

    STOCK = "stock"
    FLOW = "flow"
    PARAMETER = "parameter"
    DERIVED = "derived"

    @property
    def can_sum_over_time(self) -> bool:
        """Whether values can be meaningfully summed across time periods."""
        return self == TemporalType.FLOW

    @property
    def can_average_over_time(self) -> bool:
        """Whether averaging across time periods is meaningful."""
        return self in (TemporalType.STOCK, TemporalType.FLOW)

    @property
    def is_time_varying(self) -> bool:
        """Whether the variable changes over time."""
        return self in (TemporalType.STOCK, TemporalType.FLOW, TemporalType.DERIVED)

    def get_allowed_aggregations(self) -> frozenset["AggregationMethod"]:
        """Get the set of valid aggregation methods for this temporal type."""
        if self == TemporalType.STOCK:
            return frozenset({
                AggregationMethod.FIRST,
                AggregationMethod.LAST,
                AggregationMethod.MEAN,
                AggregationMethod.MEDIAN,
                AggregationMethod.MIN,
                AggregationMethod.MAX,
            })
        elif self == TemporalType.FLOW:
            return frozenset({
                AggregationMethod.SUM,
                AggregationMethod.MEAN,
                AggregationMethod.MEDIAN,
                AggregationMethod.MIN,
                AggregationMethod.MAX,
            })
        elif self == TemporalType.PARAMETER:
            return frozenset({
                AggregationMethod.FIRST,  # Parameters should be constant
                AggregationMethod.LAST,
            })
        else:  # DERIVED
            return frozenset(AggregationMethod)  # Allow all (context-dependent)

    def get_default_aggregation(self) -> "AggregationMethod":
        """Get the default aggregation method for this temporal type."""
        defaults = {
            TemporalType.STOCK: AggregationMethod.LAST,
            TemporalType.FLOW: AggregationMethod.SUM,
            TemporalType.PARAMETER: AggregationMethod.FIRST,
            TemporalType.DERIVED: AggregationMethod.MEAN,
        }
        return defaults[self]

    @classmethod
    def from_kernel_slot_kind(cls, slot_kind: str) -> "TemporalType":
        """
        Map from ir/kernel/slots.SlotKind to TemporalType.

        This bridges the kernel slot system with the connector temporal semantics.

        Args:
            slot_kind: The SlotKind value from kernel (as string).

        Returns:
            The corresponding TemporalType.
        """
        mapping = {
            "stock": cls.STOCK,
            "flow": cls.FLOW,
            "parameter": cls.PARAMETER,
        }
        return mapping.get(slot_kind.lower(), cls.DERIVED)


class TimeGrain(str, Enum):
    """
    Temporal granularity of time-series data.

    Defines the resolution of time-series observations and
    enables proper aggregation/disaggregation logic.
    """

    INSTANT = "instant"      # Point-in-time (no duration)
    SECOND = "second"
    MINUTE = "minute"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    FISCAL_YEAR = "fiscal_year"
    CUSTOM = "custom"        # Custom period defined elsewhere

    @property
    def approximate_days(self) -> float | None:
        """Get approximate number of days in this time grain."""
        day_mapping = {
            TimeGrain.INSTANT: 0,
            TimeGrain.SECOND: 1 / 86400,
            TimeGrain.MINUTE: 1 / 1440,
            TimeGrain.HOURLY: 1 / 24,
            TimeGrain.DAILY: 1,
            TimeGrain.WEEKLY: 7,
            TimeGrain.MONTHLY: 30.44,  # Average month
            TimeGrain.QUARTERLY: 91.31,  # Average quarter
            TimeGrain.ANNUAL: 365.25,
            TimeGrain.FISCAL_YEAR: 365.25,
            TimeGrain.CUSTOM: None,
        }
        return day_mapping.get(self)

    def is_finer_than(self, other: "TimeGrain") -> bool:
        """Check if this grain is finer (higher frequency) than another."""
        if self == TimeGrain.CUSTOM or other == TimeGrain.CUSTOM:
            return False  # Can't compare custom

        self_days = self.approximate_days
        other_days = other.approximate_days

        if self_days is None or other_days is None:
            return False

        return self_days < other_days

    def is_coarser_than(self, other: "TimeGrain") -> bool:
        """Check if this grain is coarser (lower frequency) than another."""
        if self == TimeGrain.CUSTOM or other == TimeGrain.CUSTOM:
            return False

        self_days = self.approximate_days
        other_days = other.approximate_days

        if self_days is None or other_days is None:
            return False

        return self_days > other_days

    def to_pandas_freq(self) -> str | None:
        """Convert to pandas frequency string."""
        mapping = {
            TimeGrain.SECOND: "s",
            TimeGrain.MINUTE: "min",
            TimeGrain.HOURLY: "h",
            TimeGrain.DAILY: "D",
            TimeGrain.WEEKLY: "W",
            TimeGrain.MONTHLY: "MS",
            TimeGrain.QUARTERLY: "QS",
            TimeGrain.ANNUAL: "YS",
            TimeGrain.FISCAL_YEAR: "YS",
        }
        return mapping.get(self)


class AggregationMethod(str, Enum):
    """
    Methods for aggregating time-series data.

    Each method has specific semantic meaning and validity
    depending on whether the variable is a Stock or Flow.
    """

    SUM = "sum"              # Sum all values (valid for FLOW only)
    MEAN = "mean"            # Arithmetic mean
    MEDIAN = "median"        # Median value
    MIN = "min"              # Minimum value
    MAX = "max"              # Maximum value
    FIRST = "first"          # First value in period
    LAST = "last"            # Last value in period
    COUNT = "count"          # Number of observations
    STD = "std"              # Standard deviation
    VAR = "var"              # Variance
    WEIGHTED_MEAN = "weighted_mean"  # Weighted average (requires weights)
    CUMSUM = "cumsum"        # Cumulative sum
    DIFF = "diff"            # Period-over-period difference
    PCT_CHANGE = "pct_change"  # Percentage change

    @property
    def is_additive(self) -> bool:
        """Whether this method produces additive results."""
        return self in (AggregationMethod.SUM, AggregationMethod.COUNT)

    @property
    def is_position_sensitive(self) -> bool:
        """Whether this method depends on observation order."""
        return self in (
            AggregationMethod.FIRST,
            AggregationMethod.LAST,
            AggregationMethod.CUMSUM,
            AggregationMethod.DIFF,
            AggregationMethod.PCT_CHANGE,
        )


# =============================================================================
# Time Interval
# =============================================================================


@dataclass(frozen=True, slots=True)
class TimeInterval:
    """
    Represents a time interval for temporal operations.

    Supports both point-in-time (start == end) and period semantics
    (start < end with a specified grain).

    Attributes:
        start: Start of the interval (inclusive)
        end: End of the interval (inclusive)
        grain: The temporal granularity
        label: Optional human-readable label (e.g., "2024-Q1")
    """

    start: date
    end: date
    grain: TimeGrain = TimeGrain.DAILY
    label: str | None = None

    def __post_init__(self) -> None:
        """Validate the interval."""
        if self.start > self.end:
            raise ValueError(f"start ({self.start}) must be <= end ({self.end})")

    @property
    def is_point(self) -> bool:
        """Check if this is a point-in-time (zero duration)."""
        return self.start == self.end

    @property
    def duration_days(self) -> int:
        """Get the duration in days."""
        return (self.end - self.start).days

    def contains(self, point: date) -> bool:
        """Check if a date falls within this interval."""
        return self.start <= point <= self.end

    def overlaps(self, other: "TimeInterval") -> bool:
        """Check if two intervals overlap."""
        return self.start <= other.end and other.start <= self.end

    def __str__(self) -> str:
        """String representation."""
        if self.label:
            return self.label
        if self.is_point:
            return str(self.start)
        return f"{self.start}/{self.end}"

    @classmethod
    def from_year(cls, year: int) -> "TimeInterval":
        """Create an annual interval for a given year."""
        return cls(
            start=date(year, 1, 1),
            end=date(year, 12, 31),
            grain=TimeGrain.ANNUAL,
            label=str(year),
        )

    @classmethod
    def from_quarter(cls, year: int, quarter: int) -> "TimeInterval":
        """Create a quarterly interval."""
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f"quarter must be 1-4, got {quarter}")

        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2

        # Calculate last day of end month
        if end_month == 12:
            end_date = date(year, 12, 31)
        else:
            end_date = date(year, end_month + 1, 1) - timedelta(days=1)

        return cls(
            start=date(year, start_month, 1),
            end=end_date,
            grain=TimeGrain.QUARTERLY,
            label=f"{year}-Q{quarter}",
        )

    @classmethod
    def from_month(cls, year: int, month: int) -> "TimeInterval":
        """Create a monthly interval."""
        if month not in range(1, 13):
            raise ValueError(f"month must be 1-12, got {month}")

        # Calculate last day of month
        if month == 12:
            end_date = date(year, 12, 31)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        return cls(
            start=date(year, month, 1),
            end=end_date,
            grain=TimeGrain.MONTHLY,
            label=f"{year}-{month:02d}",
        )


# =============================================================================
# Temporal Variable
# =============================================================================


@dataclass
class TemporalVariable:
    """
    Metadata for a time-series variable with temporal semantics.

    Combines temporal type (Stock/Flow) with time grain information
    to enable correct aggregation and validation logic.

    Attributes:
        name: Variable identifier
        temporal_type: Stock, Flow, or Parameter classification
        time_grain: The native time granularity of the data
        default_aggregation: Override for default aggregation method
        description: Human-readable description
        unit_expression: Optional unit string (e.g., "USD", "km/h")
    """

    name: str
    temporal_type: TemporalType
    time_grain: TimeGrain = TimeGrain.DAILY
    default_aggregation: AggregationMethod | None = None
    description: str = ""
    unit_expression: str | None = None

    # Validation cache
    _allowed_aggregations: frozenset[AggregationMethod] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        """Initialize and validate."""
        self._allowed_aggregations = self.temporal_type.get_allowed_aggregations()

        # Validate default aggregation
        if self.default_aggregation is not None:
            if self.default_aggregation not in self._allowed_aggregations:
                raise ValueError(
                    f"Invalid default aggregation '{self.default_aggregation.value}' "
                    f"for temporal type '{self.temporal_type.value}'"
                )

    @property
    def can_sum_over_time(self) -> bool:
        """Whether this variable can be summed across time periods."""
        return self.temporal_type.can_sum_over_time

    @property
    def allowed_aggregations(self) -> frozenset[AggregationMethod]:
        """Get the set of valid aggregation methods for this variable."""
        if self._allowed_aggregations is None:
            self._allowed_aggregations = self.temporal_type.get_allowed_aggregations()
        return self._allowed_aggregations

    def get_aggregation_method(self) -> AggregationMethod:
        """Get the aggregation method (explicit or default)."""
        if self.default_aggregation is not None:
            return self.default_aggregation
        return self.temporal_type.get_default_aggregation()

    def validate_aggregation(self, method: AggregationMethod) -> None:
        """
        Validate that an aggregation method is allowed for this variable.

        Args:
            method: The aggregation method to validate.

        Raises:
            TemporalAggregationError: If the method is not allowed.
        """
        if method not in self.allowed_aggregations:
            raise TemporalAggregationError(
                variable_name=self.name,
                temporal_type=self.temporal_type,
                attempted_method=method,
                reason=f"only {[m.value for m in self.allowed_aggregations]} allowed",
            )

    def can_aggregate_to(self, target_grain: TimeGrain) -> bool:
        """
        Check if this variable can be aggregated to a coarser time grain.

        Aggregation from finer to coarser grain is allowed.
        Disaggregation (coarser to finer) requires special handling.

        Args:
            target_grain: The target time granularity.

        Returns:
            True if aggregation is possible, False otherwise.
        """
        if target_grain == self.time_grain:
            return True  # Same grain, no aggregation needed

        return self.time_grain.is_finer_than(target_grain)

    def get_disaggregation_warning(self, target_grain: TimeGrain) -> str | None:
        """
        Get a warning message if disaggregation would be needed.

        Args:
            target_grain: The target time granularity.

        Returns:
            Warning message if disaggregation needed, None otherwise.
        """
        if target_grain.is_finer_than(self.time_grain):
            return (
                f"Warning: Disaggregating '{self.name}' from "
                f"{self.time_grain.value} to {target_grain.value} "
                f"requires interpolation/distribution assumptions"
            )
        return None


# =============================================================================
# Pydantic Model for Schema Integration
# =============================================================================


class TemporalSemantics(BaseModel):
    """
    Pydantic model for temporal semantics in data schemas.

    This model is used in FieldSpec and DataSchema to capture
    temporal properties of data fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    temporal_type: TemporalType = Field(
        default=TemporalType.DERIVED,
        description="Whether this field represents a stock, flow, or parameter",
    )
    time_grain: TimeGrain = Field(
        default=TimeGrain.DAILY,
        description="Native temporal granularity of the data",
    )
    default_aggregation: AggregationMethod | None = Field(
        default=None,
        description="Override for default time aggregation method",
    )
    reference_point: Literal["start", "end", "middle"] | None = Field(
        default=None,
        description="For stocks: which point in the period the value represents",
    )

    def to_temporal_variable(self, name: str) -> TemporalVariable:
        """Convert to a TemporalVariable instance."""
        return TemporalVariable(
            name=name,
            temporal_type=self.temporal_type,
            time_grain=self.time_grain,
            default_aggregation=self.default_aggregation,
        )


# =============================================================================
# Validation Functions
# =============================================================================


def validate_temporal_aggregation(
    variables: Sequence[TemporalVariable],
    method: AggregationMethod,
    *,
    raise_on_error: bool = True,
) -> list[TemporalAggregationError]:
    """
    Validate that an aggregation method is valid for all variables.

    Args:
        variables: The temporal variables to validate.
        method: The proposed aggregation method.
        raise_on_error: If True, raise on first error; otherwise collect all.

    Returns:
        List of validation errors (empty if all valid).

    Raises:
        TemporalAggregationError: If raise_on_error and validation fails.
    """
    errors = []

    for var in variables:
        if method not in var.allowed_aggregations:
            error = TemporalAggregationError(
                variable_name=var.name,
                temporal_type=var.temporal_type,
                attempted_method=method,
                reason=f"only {[m.value for m in var.allowed_aggregations]} allowed",
            )

            if raise_on_error:
                raise error

            errors.append(error)

    return errors


def infer_temporal_type(
    variable_name: str,
    semantic_type: str | None = None,
) -> TemporalType:
    """
    Infer the temporal type from variable name and semantic type.

    This heuristic helps classify variables when explicit type is not provided.

    Args:
        variable_name: The name of the variable.
        semantic_type: Optional semantic type hint.

    Returns:
        Inferred TemporalType.
    """
    name_lower = variable_name.lower()

    # Stock indicators
    stock_keywords = {
        "balance", "inventory", "stock", "level", "count", "population",
        "total", "outstanding", "position", "holdings", "assets", "liabilities",
        "capital", "reserves", "debt", "equity", "headcount", "quantity",
        "gdp", "cpi", "index", "price",  # Economic indicators
    }

    # Flow indicators
    flow_keywords = {
        "revenue", "income", "expense", "cost", "profit", "loss",
        "sales", "purchases", "transactions", "payments", "receipts",
        "production", "consumption", "births", "deaths", "migration",
        "inflow", "outflow", "change", "delta", "growth", "gain",
        "spending", "investment", "saving", "transfer", "volume",
    }

    # Parameter indicators
    parameter_keywords = {
        "rate", "coefficient", "factor", "threshold", "limit",
        "parameter", "config", "setting", "constant", "fixed",
    }

    # Check semantic type first
    if semantic_type:
        semantic_lower = semantic_type.lower()
        if semantic_lower in ("currency", "percentage", "ratio", "rate"):
            return TemporalType.FLOW  # Usually flows
        if semantic_lower in ("count", "population", "index"):
            return TemporalType.STOCK

    # Check parameter keywords before stock/flow keywords
    for keyword in parameter_keywords:
        if keyword in name_lower:
            return TemporalType.PARAMETER

    # Check keywords in name
    for keyword in stock_keywords:
        if keyword in name_lower:
            return TemporalType.STOCK

    for keyword in flow_keywords:
        if keyword in name_lower:
            return TemporalType.FLOW

    # Default to DERIVED (unknown)
    return TemporalType.DERIVED


# =============================================================================
# Stock/Flow Combination Rules
# =============================================================================


class StockFlowCombination:
    """
    Rules for combining Stock and Flow variables in operations.

    These rules ensure mathematically valid operations when
    working with mixed temporal types.
    """

    # Addition rules: what type results from adding two types
    ADDITION_RULES: ClassVar[dict[tuple[TemporalType, TemporalType], TemporalType | None]] = {
        (TemporalType.STOCK, TemporalType.STOCK): TemporalType.STOCK,
        (TemporalType.FLOW, TemporalType.FLOW): TemporalType.FLOW,
        (TemporalType.STOCK, TemporalType.FLOW): None,  # Invalid
        (TemporalType.FLOW, TemporalType.STOCK): None,  # Invalid
        (TemporalType.PARAMETER, TemporalType.PARAMETER): TemporalType.PARAMETER,
    }

    # Multiplication rules
    MULTIPLICATION_RULES: ClassVar[dict[tuple[TemporalType, TemporalType], TemporalType]] = {
        (TemporalType.STOCK, TemporalType.STOCK): TemporalType.DERIVED,
        (TemporalType.FLOW, TemporalType.FLOW): TemporalType.DERIVED,
        (TemporalType.STOCK, TemporalType.FLOW): TemporalType.DERIVED,
        (TemporalType.FLOW, TemporalType.STOCK): TemporalType.DERIVED,
        (TemporalType.PARAMETER, TemporalType.STOCK): TemporalType.STOCK,
        (TemporalType.PARAMETER, TemporalType.FLOW): TemporalType.FLOW,
        (TemporalType.STOCK, TemporalType.PARAMETER): TemporalType.STOCK,
        (TemporalType.FLOW, TemporalType.PARAMETER): TemporalType.FLOW,
    }

    @classmethod
    def can_add(cls, type1: TemporalType, type2: TemporalType) -> bool:
        """Check if two temporal types can be added."""
        key = (type1, type2)
        if key in cls.ADDITION_RULES:
            return cls.ADDITION_RULES[key] is not None
        # Check reverse
        key_rev = (type2, type1)
        if key_rev in cls.ADDITION_RULES:
            return cls.ADDITION_RULES[key_rev] is not None
        return False

    @classmethod
    def addition_result(cls, type1: TemporalType, type2: TemporalType) -> TemporalType:
        """Get the result type of adding two temporal types."""
        key = (type1, type2)
        result = cls.ADDITION_RULES.get(key)
        if result is None:
            key_rev = (type2, type1)
            result = cls.ADDITION_RULES.get(key_rev)

        if result is None:
            raise ValueError(
                f"Cannot add {type1.value} and {type2.value}: "
                "mixing stocks and flows in addition is invalid"
            )

        return result

    @classmethod
    def multiplication_result(
        cls,
        type1: TemporalType,
        type2: TemporalType,
    ) -> TemporalType:
        """Get the result type of multiplying two temporal types."""
        key = (type1, type2)
        result = cls.MULTIPLICATION_RULES.get(key)
        if result is None:
            key_rev = (type2, type1)
            result = cls.MULTIPLICATION_RULES.get(key_rev, TemporalType.DERIVED)

        return result
