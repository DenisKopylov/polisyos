"""Stable registry facade for kernel slots, units, metrics, constraints, and mechanism specs."""
from .base import ID_PATTERN, SLOT_ID_PATTERN, KernelModel
from .constraints import DEFAULT_CONSTRAINT_REGISTRY, ConstraintRegistry, ConstraintSpec
from .mechanisms import (
    DEFAULT_MECHANISM_REGISTRY,
    MechanismTypeRegistry,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
)
from .merge_rules import (
    DEFAULT_MERGE_RULE_REGISTRY,
    ConflictResolution,
    MergeRuleKind,
    MergeRuleRef,
    MergeRuleRegistry,
    MergeRuleSpec,
)
from .metrics import DEFAULT_METRIC_REGISTRY, MetricRegistry, MetricSpec
from .numbers import DecimalValue, NonNegativeDecimal, PositiveDecimal
from .selector_fields import (
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    SelectorFieldRegistry,
    SelectorFieldSpec,
)
from .slots import (
    DEFAULT_SLOT_REGISTRY,
    MergeOverride,
    SlotKind,
    SlotRegistry,
    SlotScope,
    SlotSpec,
    SlotValueType,
)
from .time_semantics import TimeSemantics
from .trust import DEFAULT_TRUST_REGISTRY, TrustPolicySpec, TrustRegistry
from .units import (
    DEFAULT_UNITS_REGISTRY,
    CountUnit,
    DimensionlessUnit,
    DurationUnit,
    GenericUnit,
    MoneyUnit,
    RateUnit,
    UnitKind,
    UnitRef,
    UnitSpecType,
    UnitsRegistry,
)
from .values import CountValue, DurationValue, MoneyValue, RateValue

__all__ = [
    "ID_PATTERN",
    "SLOT_ID_PATTERN",
    "KernelModel",
    "ConflictResolution",
    "MergeRuleKind",
    "MergeRuleRef",
    "MergeRuleRegistry",
    "MergeRuleSpec",
    "DEFAULT_MERGE_RULE_REGISTRY",
    "ConstraintSpec",
    "ConstraintRegistry",
    "DEFAULT_CONSTRAINT_REGISTRY",
    "MetricSpec",
    "MetricRegistry",
    "DEFAULT_METRIC_REGISTRY",
    "SelectorFieldSpec",
    "SelectorFieldRegistry",
    "DEFAULT_SELECTOR_FIELD_REGISTRY",
    "TrustPolicySpec",
    "TrustRegistry",
    "DEFAULT_TRUST_REGISTRY",
    "ParamSpec",
    "ParamType",
    "MechanismTypeSpec",
    "MechanismTypeRegistry",
    "DEFAULT_MECHANISM_REGISTRY",
    "DecimalValue",
    "NonNegativeDecimal",
    "PositiveDecimal",
    "SlotKind",
    "SlotRegistry",
    "SlotScope",
    "SlotSpec",
    "SlotValueType",
    "MergeOverride",
    "DEFAULT_SLOT_REGISTRY",
    "TimeSemantics",
    "CountUnit",
    "DimensionlessUnit",
    "DurationUnit",
    "GenericUnit",
    "MoneyUnit",
    "RateUnit",
    "UnitKind",
    "UnitRef",
    "UnitSpecType",
    "UnitsRegistry",
    "DEFAULT_UNITS_REGISTRY",
    "CountValue",
    "DurationValue",
    "MoneyValue",
    "RateValue",
]
