"""Define the Trinity ``what`` artifact and its objective/constraint vocabulary.

``ProblemFrame`` is the stable problem statement in the Trinity contract: it
captures the decision objective, KPI semantics, feasibility boundaries, and
stakeholder scope that policy proposals must respect. ``PolicySpec`` and
``ModelSpec`` may iterate around this artifact, but downstream governance and
optimization should treat ``ProblemFrame`` as the fixed reference for "what
success means" and "what cannot be violated".
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BeforeValidator, Field, model_validator

from polisyos.ir._validation import ensure_unique_ids
from polisyos.ir.kernel.base import SLOT_ID_PATTERN, KernelModel, reject_float

if TYPE_CHECKING:
    from polisyos.ir.kernel.numbers import DecimalValue, NonNegativeDecimal
    from polisyos.ir.kernel.values import (
        CountValue,
        DurationValue,
        MoneyValue,
        RateValue,
    )
    from polisyos.ir.types import EntityType, OptimizationDirection, TranslatableString
else:
    from polisyos.ir.kernel.numbers import DecimalValue, NonNegativeDecimal
    from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
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
    """Classify the domain vocabulary used to route metrics and templates.

    The domain label is consumed by authoring tools and reporting layers to
    choose problem-specific defaults; ``CUSTOM`` is the escape hatch when no
    built-in domain taxonomy applies.
    """

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
    """Declare whether a constraint is a hard feasibility gate or a soft penalty.

    ``ProblemFrame`` validators keep hard and soft constraints in separate
    collections, while portfolio/search routines can use ``SOFT`` entries with
    ``ConstraintSpec.penalty_weight`` as a scalarized penalty term.
    """

    HARD = "hard"  # Must be satisfied
    SOFT = "soft"  # Preferred but not required


class NormativeArbitrationPolicy(str, Enum):
    """Supported formal arbitration policies."""

    LEXICOGRAPHIC_RIGHTS = "lexicographic_rights"
    WEIGHTED_WELFARE = "weighted_welfare"
    MAX_MIN_HARM = "max_min_harm"
    PARETO_FILTER = "pareto_filter"


class NormativeComparisonMode(str, Enum):
    """Supported comparison modes for arbitration."""

    PROPOSAL_VS_BASELINE = "proposal_vs_baseline"


class NormativeOutcomeChannel(str, Enum):
    """Canonical channels that can feed normative utilities/rights."""

    SIMULATION_METRIC = "simulation_metric"
    DISTRIBUTIONAL_NET_IMPACT = "distributional_net_impact"
    DISTRIBUTIONAL_LOSERS_SHARE = "distributional_losers_share"
    DISTRIBUTIONAL_WINNERS_SHARE = "distributional_winners_share"
    DISTRIBUTIONAL_OVERALL_GINI_DELTA = "distributional_overall_gini_delta"
    UNCERTAINTY_CI_WIDTH_RATIO = "uncertainty_ci_width_ratio"
    SYNTHESIZED = "synthesized"


class NormativeComparisonTarget(str, Enum):
    """Which quantity a right condition evaluates."""

    PROPOSAL = "proposal"
    BASELINE = "baseline"
    DELTA = "delta"


class UtilityDirection(str, Enum):
    """Utility aggregation direction for a stakeholder term."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class KPISpec(KernelModel):
    """Describe one measurable success signal anchored to the metric registry.

    A KPI is the user-facing metric vocabulary for the ``what`` artifact: it
    links narrative objectives to a concrete ``metric_id``, optional
    baseline/target values, and an optimization direction that downstream
    scoring and reporting stages can interpret consistently.
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
    """Specify one feasibility boundary or soft penalty attached to a metric slot.

    Hard constraints are expected to fail governance or search admission when
    violated, whereas soft constraints may be traded off using
    ``penalty_weight``. Use ``slot_id`` and ``operator`` when the constraint is
    tied to a concrete metric channel.
    """

    constraint_id: str = Field(..., pattern=ID_PATTERN)
    constraint_type: ConstraintType = Field(
        default=ConstraintType.HARD, description="Hard (must satisfy) or soft (preferred)"
    )
    value: MoneyValue | RateValue | CountValue | DurationValue | DecimalValue | int | str | bool = (
        Field(..., description="Constraint value or threshold")
    )
    slot_id: str | None = Field(None, pattern=SLOT_ID_PATTERN, description="Slot this constrains")
    operator: Literal["<", "<=", "==", "!=", ">=", ">"] | None = Field(
        None, description="Comparison operator (if applicable)"
    )
    penalty_weight: NonNegativeDecimal | None = Field(
        None, description="Penalty weight for soft constraint violation"
    )
    notes: list[str] = Field(default_factory=list, max_length=5)


class StakeholderSpec(KernelModel):
    """Capture the affected actor set used by equity and arbitration passes.

    Stakeholders define whose outcomes must be tracked in ``ProblemFrame`` and
    optionally prioritized in ``NormativeFrame``. Downstream fairness,
    distributional, and policy communication layers read this contract to align
    metric impacts with stakeholder semantics.
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


class StakeholderOutcomeBinding(KernelModel):
    """Map a stakeholder to a concrete outcome channel and key."""

    binding_id: str = Field(..., pattern=ID_PATTERN)
    stakeholder_id: str = Field(..., pattern=ID_PATTERN)
    channel: NormativeOutcomeChannel
    outcome_key: str = Field(..., min_length=1, max_length=200)
    weight: NonNegativeDecimal = Decimal("1")
    notes: list[str] = Field(default_factory=list, max_length=10)


class StakeholderUtilityTerm(KernelModel):
    """Explicit utility term for stakeholder welfare aggregation."""

    term_id: str = Field(..., pattern=ID_PATTERN)
    stakeholder_id: str = Field(..., pattern=ID_PATTERN)
    binding_refs: list[str] = Field(default_factory=list, max_length=10)
    direction: UtilityDirection = UtilityDirection.MAXIMIZE
    coefficient: DecimalValue = Decimal("1")
    welfare_weight: NonNegativeDecimal = Decimal("1")
    notes: list[str] = Field(default_factory=list, max_length=10)


class StakeholderRightSpec(KernelModel):
    """Explicit normative right attached to a stakeholder."""

    right_id: str = Field(..., pattern=ID_PATTERN)
    stakeholder_id: str = Field(..., pattern=ID_PATTERN)
    binding_ref: str | None = Field(None, pattern=ID_PATTERN)
    compare_to: NormativeComparisonTarget = NormativeComparisonTarget.DELTA
    operator: Literal["<", "<=", "==", "!=", ">=", ">"]
    threshold: DecimalValue | int | str | bool
    hard: bool = True
    notes: list[str] = Field(default_factory=list, max_length=10)


class NormativeFrame(KernelModel):
    """Formal value-conflict model used by normative arbitration."""

    comparison_mode: NormativeComparisonMode = NormativeComparisonMode.PROPOSAL_VS_BASELINE
    default_policy: NormativeArbitrationPolicy = NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS
    enabled_policies: list[NormativeArbitrationPolicy] = Field(
        default_factory=lambda: [NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS],
        max_length=4,
    )
    stakeholder_bindings: list[StakeholderOutcomeBinding] = Field(
        default_factory=list,
        max_length=MAX_STAKEHOLDERS * 5,
    )
    utility_terms: list[StakeholderUtilityTerm] = Field(
        default_factory=list,
        max_length=MAX_STAKEHOLDERS * 5,
    )
    rights_catalog: list[StakeholderRightSpec] = Field(
        default_factory=list,
        max_length=MAX_STAKEHOLDERS * 5,
    )
    hard_constraint_refs: list[str] = Field(default_factory=list, max_length=MAX_CONSTRAINTS)
    notes: list[str] = Field(default_factory=list, max_length=20)


class ProblemFrame(KernelModel):
    """Define the Trinity ``what`` contract for objectives, metrics, and guardrails.

    ``ProblemFrame`` answers "what problem are we solving and under which
    boundaries?" and is expected to remain stable while ``PolicySpec`` explores
    interventions and ``ModelSpec`` explores simulation assumptions. Use this
    artifact as the canonical anchor for optimizer objectives, governance
    constraints, stakeholder interpretation, and human-facing summaries.

    Attributes:
        problem_id: Stable identifier for the policy problem within a project.
        domain: Domain taxonomy used for reporting and authoring defaults.
        objectives: Formal optimization objectives tied to registry metrics.
        kpis: Business-facing KPI definitions that quantify progress.
        success_criteria: Threshold tests that define when a KPI is considered met.
        hard_constraints: Non-negotiable feasibility boundaries.
        soft_constraints: Penalty-based preferences that search may trade off.
        stakeholders: Affected actor groups used by equity and arbitration logic.
        normative_frame: Optional welfare/rights model for normative arbitration.
        narrative: Human-readable problem statement preserved alongside the schema.
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
    normative_frame: NormativeFrame | None = Field(
        default=None,
        description="Optional formal normative arbitration model",
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
    def validate_problem_frame(self) -> ProblemFrame:
        """Validate internal consistency of the problem frame."""

        ensure_unique_ids(
            self.objectives,
            key_fn=lambda item: item.objective_id,
            label="objective_id",
        )
        ensure_unique_ids(self.kpis, key_fn=lambda item: item.kpi_id, label="kpi_id")
        ensure_unique_ids(
            self.success_criteria,
            key_fn=lambda item: item.criterion_id,
            label="criterion_id",
        )
        ensure_unique_ids(
            self.hard_constraints + self.soft_constraints,
            key_fn=lambda item: item.constraint_id,
            label="constraint_id",
        )
        ensure_unique_ids(
            self.stakeholders,
            key_fn=lambda item: item.stakeholder_id,
            label="stakeholder_id",
        )

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

        if self.normative_frame is not None:
            self._validate_normative_frame()

        return self

    def _validate_normative_frame(self) -> None:
        if self.normative_frame is None:
            raise ValueError("normative_frame must be present before validation")
        normative = self.normative_frame
        stakeholder_ids = {stakeholder.stakeholder_id for stakeholder in self.stakeholders}
        hard_constraint_ids = {constraint.constraint_id for constraint in self.hard_constraints}

        ensure_unique_ids(
            normative.stakeholder_bindings,
            key_fn=lambda item: item.binding_id,
            label="binding_id",
        )
        ensure_unique_ids(
            normative.utility_terms,
            key_fn=lambda item: item.term_id,
            label="term_id",
        )
        ensure_unique_ids(
            normative.rights_catalog,
            key_fn=lambda item: item.right_id,
            label="right_id",
        )

        if not normative.enabled_policies:
            raise ValueError("normative_frame.enabled_policies must not be empty")
        if normative.default_policy not in normative.enabled_policies:
            raise ValueError("normative_frame.default_policy must be present in enabled_policies")

        binding_ids = {binding.binding_id for binding in normative.stakeholder_bindings}
        for binding in normative.stakeholder_bindings:
            if binding.stakeholder_id not in stakeholder_ids:
                raise ValueError(
                    "normative_frame.stakeholder_bindings references unknown stakeholder "
                    f"'{binding.stakeholder_id}'"
                )

        for term in normative.utility_terms:
            if term.stakeholder_id not in stakeholder_ids:
                raise ValueError(
                    "normative_frame.utility_terms references unknown stakeholder "
                    f"'{term.stakeholder_id}'"
                )
            for binding_ref in term.binding_refs:
                if binding_ref not in binding_ids:
                    raise ValueError(
                        f"normative_frame.utility_terms references unknown binding '{binding_ref}'"
                    )

        for right in normative.rights_catalog:
            if right.stakeholder_id not in stakeholder_ids:
                raise ValueError(
                    "normative_frame.rights_catalog references unknown stakeholder "
                    f"'{right.stakeholder_id}'"
                )
            if right.binding_ref is not None and right.binding_ref not in binding_ids:
                raise ValueError(
                    "normative_frame.rights_catalog references unknown binding "
                    f"'{right.binding_ref}'"
                )

        for constraint_ref in normative.hard_constraint_refs:
            if constraint_ref not in hard_constraint_ids:
                raise ValueError(
                    "normative_frame.hard_constraint_refs references unknown hard constraint "
                    f"'{constraint_ref}'"
                )
