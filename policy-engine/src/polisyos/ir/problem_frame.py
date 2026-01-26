"""
ProblemFrame: The "Why" artifact - goals, KPIs, success criteria, constraints.

This artifact captures the formal problem statement that remains constant
across policy iterations and sensitivity analyses.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal, Sequence

from pydantic import BeforeValidator, Field, model_validator

from polisyos.ir.kernel.base import KernelModel, reject_float
from polisyos.ir.kernel.numbers import DecimalValue, NonNegativeDecimal
from polisyos.ir.kernel.values import (
    CountValue,
    DurationValue,
    MoneyValue,
    RateValue,
)
from polisyos.ir.types import EntityType, OptimizationDirection, TranslatableString

# Constants
ID_PATTERN = r"^[a-z][a-z0-9_]*$"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
MAX_OBJECTIVES = 20
MAX_CONSTRAINTS = 50
MAX_STAKEHOLDERS = 100
MAX_KPIS = 30
MAX_SUCCESS_CRITERIA = 20

PercentValue = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0, le=100)]
UnitIntervalValue = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0, le=1)]


class ProblemDomain(str, Enum):
    """Classification of policy problem domains."""

    FISCAL = "fiscal"
    MONETARY = "monetary"
    SOCIAL = "social"
    ENVIRONMENTAL = "environmental"
    LABOR = "labor"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    INFRASTRUCTURE = "infrastructure"
    REGULATORY = "regulatory"
    TRADE = "trade"
    CUSTOM = "custom"


class ConstraintType(str, Enum):
    """Types of constraints on policy outcomes."""

    HARD = "hard"  # Must be satisfied
    SOFT = "soft"  # Preferred but not required


class KPISpec(KernelModel):
    """
    Key Performance Indicator specification.

    Defines a measurable metric that indicates progress toward objectives.
    """

    kpi_id: str = Field(..., pattern=ID_PATTERN, description="Unique KPI identifier")
    metric_id: str = Field(..., pattern=ID_PATTERN, description="Reference to metric registry")
    name: TranslatableString | None = Field(None, description="Human-readable KPI name")
    unit_id: str | None = Field(None, pattern=ID_PATTERN, description="Unit of measurement")
    baseline_value: DecimalValue | None = Field(None, description="Current/starting value")
    target_value: DecimalValue | None = Field(None, description="Desired target value")
    direction: OptimizationDirection = Field(
        ..., description="Optimization direction: maximize, minimize, or maintain_range"
    )
    weight: PercentValue = Field(
        default=Decimal("1"), description="Relative importance weight (0-100)"
    )
    notes: list[str] = Field(default_factory=list, max_length=10)


class ObjectiveSpec(KernelModel):
    """
    Formal objective specification linking to metrics.

    Preserves compatibility with existing ObjectiveSpec in surface.py.
    """

    objective_id: str = Field(..., pattern=ID_PATTERN)
    metric_id: str = Field(..., pattern=ID_PATTERN)
    direction: OptimizationDirection
    target: DecimalValue | None = None
    weight: NonNegativeDecimal = Decimal("1")
    kpi_refs: list[str] = Field(
        default_factory=list,
        description="References to KPIs this objective relates to",
    )


class SuccessCriterion(KernelModel):
    """
    Formal success criterion with threshold and operator.

    Defines when an objective/KPI is considered achieved.
    """

    criterion_id: str = Field(..., pattern=ID_PATTERN)
    kpi_id: str = Field(..., pattern=ID_PATTERN, description="KPI this criterion evaluates")
    operator: Literal["<", "<=", "==", "!=", ">=", ">"] = Field(
        ..., description="Comparison operator"
    )
    threshold: DecimalValue | MoneyValue | RateValue | CountValue = Field(
        ..., description="Success threshold value"
    )
    confidence_level: UnitIntervalValue | None = Field(
        None, description="Required confidence level (0-1)"
    )
    notes: list[str] = Field(default_factory=list, max_length=5)


class ConstraintSpec(KernelModel):
    """
    Constraint specification on policy outcomes.

    Defines hard or soft boundaries that must/should be respected.
    """

    constraint_id: str = Field(..., pattern=ID_PATTERN)
    constraint_type: ConstraintType = Field(
        default=ConstraintType.HARD, description="Hard (must satisfy) or soft (preferred)"
    )
    value: MoneyValue | RateValue | CountValue | DurationValue | DecimalValue | int | str | bool = (
        Field(..., description="Constraint value or threshold")
    )
    slot_id: str | None = Field(None, pattern=ID_PATTERN, description="Slot this constrains")
    operator: Literal["<", "<=", "==", "!=", ">=", ">"] | None = Field(
        None, description="Comparison operator (if applicable)"
    )
    penalty_weight: NonNegativeDecimal | None = Field(
        None, description="Penalty weight for soft constraint violation"
    )
    notes: list[str] = Field(default_factory=list, max_length=5)


class StakeholderSpec(KernelModel):
    """
    Stakeholder affected by the policy problem.

    Captures who is impacted and how.
    """

    stakeholder_id: str = Field(..., pattern=ID_PATTERN)
    entity_type: EntityType
    name: TranslatableString | None = None
    role: str | None = Field(None, max_length=100, description="Role in the problem space")
    impact_direction: Literal["positive", "negative", "mixed", "neutral"] | None = Field(
        None, description="Expected policy impact direction"
    )
    priority: Annotated[int, Field(ge=1, le=10)] = Field(
        default=5, description="Stakeholder priority (1-10)"
    )
    attributes: dict[str, str | int | bool] = Field(default_factory=dict)


class ProblemFrame(KernelModel):
    """
    ProblemFrame: The "Why" artifact.

    Formalizes the policy problem being addressed, including goals, KPIs,
    success criteria, constraints, and stakeholders. This artifact remains
    constant during policy optimization and sensitivity analysis.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)

    # Identity
    problem_id: str = Field(..., pattern=ID_PATTERN, description="Unique problem identifier")
    domain: ProblemDomain = Field(..., description="Policy domain classification")

    # Goals and Metrics
    objectives: list[ObjectiveSpec] = Field(
        default_factory=list,
        max_length=MAX_OBJECTIVES,
        description="Formal optimization objectives",
    )
    kpis: list[KPISpec] = Field(
        default_factory=list,
        max_length=MAX_KPIS,
        description="Key Performance Indicators",
    )
    success_criteria: list[SuccessCriterion] = Field(
        default_factory=list,
        max_length=MAX_SUCCESS_CRITERIA,
        description="Formal success thresholds",
    )

    # Constraints
    hard_constraints: list[ConstraintSpec] = Field(
        default_factory=list,
        max_length=MAX_CONSTRAINTS,
        description="Inviolable constraints",
    )
    soft_constraints: list[ConstraintSpec] = Field(
        default_factory=list,
        max_length=MAX_CONSTRAINTS,
        description="Preferred but flexible constraints",
    )

    # Stakeholders
    stakeholders: list[StakeholderSpec] = Field(
        default_factory=list,
        max_length=MAX_STAKEHOLDERS,
        description="Entities affected by the problem",
    )

    # Metadata
    narrative: str | None = Field(
        None,
        max_length=5000,
        description="Human-readable problem description",
    )
    labels: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_problem_frame(self) -> "ProblemFrame":
        """Validate internal consistency of the problem frame."""

        _validate_unique_ids(self.objectives, "objective_id")
        _validate_unique_ids(self.kpis, "kpi_id")
        _validate_unique_ids(self.success_criteria, "criterion_id")
        _validate_unique_ids(self.hard_constraints + self.soft_constraints, "constraint_id")
        _validate_unique_ids(self.stakeholders, "stakeholder_id")

        kpi_ids = {kpi.kpi_id for kpi in self.kpis}
        for criterion in self.success_criteria:
            if criterion.kpi_id not in kpi_ids:
                raise ValueError(
                    f"Success criterion '{criterion.criterion_id}' references "
                    f"unknown KPI '{criterion.kpi_id}'"
                )

        for constraint in self.hard_constraints:
            if constraint.constraint_type != ConstraintType.HARD:
                raise ValueError(
                    f"Constraint '{constraint.constraint_id}' in hard_constraints "
                    f"must have constraint_type=HARD"
                )
        for constraint in self.soft_constraints:
            if constraint.constraint_type != ConstraintType.SOFT:
                raise ValueError(
                    f"Constraint '{constraint.constraint_id}' in soft_constraints "
                    f"must have constraint_type=SOFT"
                )

        return self


def _validate_unique_ids(items: Sequence[KernelModel], attr: str) -> None:
    """Validate that all items have unique values for the given attribute."""

    seen: set[str] = set()
    for item in items:
        value = getattr(item, attr)
        if value in seen:
            raise ValueError(f"duplicate {attr}: {value}")
        seen.add(value)
