"""Define the Trinity intervention/governance artifact and its action vocabulary.

``PolicySpec`` is the policy-side boundary object in the Trinity contract: it
declares interventions, mechanism bindings, tunable parameters, and execution
schedules that should be evaluated against a fixed ``ProblemFrame`` and one or
more ``ModelSpec`` world models. Use this module when authoring the "what
should be changed" layer, not the "how the world evolves" layer.
"""
from __future__ import annotations

from typing import Annotated, Any, Sequence

from pydantic import Field, model_validator

# Import selector types from surface.py (to be moved later or re-exported)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.observation.contracts import IdentificationMode, StrategicResponseChannel
from polisyos.ir.governance.selector_expr import (
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
)
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.kernel.values import ParamValue
from polisyos.ir.types import TranslatableString

# Constants
ID_PATTERN = r"^[a-z][a-z0-9_]*$"
ARTIFACT_ID_PATTERN = r"^sha256:[a-f0-9]{64}$"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
MAX_INTERVENTIONS = 100
MAX_MECHANISM_BINDINGS = 100
MAX_SELECTOR_DEPTH = 10
MAX_SELECTOR_NODES = 50


class MechanismBinding(KernelModel):
    """Bind one or more interventions to an executable mechanism registry entry.

    This is the handshake between authored interventions and runtime mechanism
    implementations: search, compilation, and execution layers can override
    mechanism configuration without mutating the intervention payload itself.
    """

    binding_id: str = Field(..., pattern=ID_PATTERN)
    mechanism_id: str = Field(
        ..., pattern=ID_PATTERN, description="Reference to mechanism registry"
    )
    intervention_ids: list[str] = Field(
        ..., min_length=1, description="Interventions using this mechanism"
    )
    config_overrides: dict[str, Any] = Field(
        default_factory=dict, description="Mechanism-specific config overrides"
    )


class InterventionSpec(KernelModel):
    """Declare one policy action, its target selector, timing, and mechanism inputs.

    In Trinity terms this is an intervention/governance object, not a causal
    query intervention. It is used by policy compilation and schedule execution,
    while observation routing reads ``identification_mode`` and
    ``transmission_channels`` to decide which readiness checks and governance
    passes must run before evaluation.
    """

    intervention_id: str = Field(..., pattern=ID_PATTERN)
    kind: str = Field(..., pattern=ID_PATTERN, description="Mechanism type")
    target: SelectorExpr = Field(..., description="Agent/entity selector expression")
    schedule: ScheduleSpec = Field(..., description="Timing of intervention")
    params: dict[str, ParamValue] = Field(
        default_factory=dict, description="Mechanism parameters"
    )
    priority: Annotated[int, Field(ge=0)] | None = Field(
        None, description="Execution priority (lower = earlier)"
    )
    enabled: bool = Field(True, description="Whether intervention is active")
    lex_provision_ref: str | None = Field(
        None,
        max_length=200,
        description="Reference to the legal provision or lex artifact driving the intervention.",
    )
    target_population_type: str | None = Field(
        None,
        max_length=120,
        description="Population semantics used for policy targeting and evaluation.",
    )
    target_sector_ids: list[str] = Field(default_factory=list)
    target_region_ids: list[str] = Field(default_factory=list)
    measurement_expectations: dict[str, Any] = Field(default_factory=dict)
    identification_mode: IdentificationMode | None = None
    strategic_response_expected: bool = False
    transmission_channels: list[StrategicResponseChannel] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, max_length=10)


class TemporalInterventionStep(KernelModel):
    """Declare one activation point in a sequential intervention program.

    Steps are sorted by ``effective_date`` inside
    ``TemporalInterventionSequence`` and may override mechanism parameters for a
    dynamic treatment regime run.
    """

    step_id: str = Field(..., pattern=ID_PATTERN)
    effective_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}(-\d{2})?$",
        description="ISO-like YYYY-MM or YYYY-MM-DD activation marker for the step.",
    )
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    parameter_overrides: dict[str, ParamValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list, max_length=20)


class TemporalInterventionSequence(KernelModel):
    """Group ordered intervention steps for sequential or DTR-style execution.

    The sequence is consumed by observation compilers and causal runners that
    require ``IdentificationMode.SEQUENTIAL`` semantics. Validators enforce
    unique ``step_id`` values and monotone ``effective_date`` ordering so the
    runtime can replay the intervention path deterministically.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    sequence_id: str = Field(..., pattern=ID_PATTERN)
    dynamic_intervention_id: str = Field(..., pattern=ID_PATTERN)
    identification_mode: IdentificationMode = IdentificationMode.SEQUENTIAL
    strategic_response_expected: bool = False
    transmission_channels: list[StrategicResponseChannel] = Field(default_factory=list)
    steps: list[TemporalInterventionStep] = Field(..., min_length=1, max_length=128)
    notes: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_temporal_sequence(self) -> "TemporalInterventionSequence":
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("duplicate temporal intervention step_id")
        effective_dates = [step.effective_date for step in self.steps]
        if effective_dates != sorted(effective_dates):
            raise ValueError("temporal intervention steps must be ordered by effective_date")
        return self


class ParameterSpec(KernelModel):
    """Expose one tunable intervention parameter to calibration and search.

    ``param_path`` points into ``InterventionSpec.params`` and optional bounds
    constrain feasible updates. Scientist calibration and sensitivity tooling
    should only mutate parameters marked ``tunable=True``.
    """

    param_id: str = Field(..., pattern=ID_PATTERN)
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    param_path: str = Field(
        ..., description="Dot-separated path to parameter within intervention.params"
    )
    default_value: ParamValue = Field(..., description="Default/initial value")
    min_value: ParamValue | None = Field(None, description="Minimum allowed value")
    max_value: ParamValue | None = Field(None, description="Maximum allowed value")
    tunable: bool = Field(True, description="Whether parameter can be optimized")
    sensitivity_priority: Annotated[int, Field(ge=1, le=10)] = Field(
        default=5, description="Priority for sensitivity analysis (1=highest)"
    )


class PolicySpec(KernelModel):
    """Define the Trinity intervention/governance contract for policy proposals.

    ``PolicySpec`` answers "which intervention is being proposed and under what
    execution semantics?" It should reference a stable ``ProblemFrame`` and can
    be iterated by search, optimization, or human authoring while ``ModelSpec``
    supplies alternative world-model assumptions. Use ``interventions`` for the
    authored action set, ``mechanism_bindings`` for runtime mechanism mapping,
    and ``parameters`` for calibration/search knobs.

    Attributes:
        policy_id: Stable identifier for the proposal candidate.
        problem_frame_ref: Optional content-addressed link to the ``ProblemFrame``
            this proposal is meant to satisfy.
        interventions: Concrete actions with selector, schedule, and mechanism
            parameters.
        mechanism_bindings: Explicit runtime mechanism bindings for one or more
            interventions.
        parameters: Tunable knobs exposed to calibration and sensitivity passes.
        global_schedule: Optional schedule override shared by all interventions.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)

    # Identity
    policy_id: str = Field(..., pattern=ID_PATTERN, description="Unique policy identifier")

    # Reference to ProblemFrame (links "What" to "Why")
    problem_frame_ref: str | None = Field(
        None,
        pattern=ARTIFACT_ID_PATTERN,
        description="Reference to ProblemFrame artifact this policy addresses",
    )

    # Interventions
    interventions: list[InterventionSpec] = Field(
        default_factory=list,
        max_length=MAX_INTERVENTIONS,
        description="Policy interventions/actions",
    )

    # Mechanism Bindings
    mechanism_bindings: list[MechanismBinding] = Field(
        default_factory=list,
        max_length=MAX_MECHANISM_BINDINGS,
        description="Explicit mechanism bindings",
    )

    # Parameters (for calibration/sensitivity)
    parameters: list[ParameterSpec] = Field(
        default_factory=list,
        description="Tunable parameter specifications",
    )

    # Global Schedule (optional, for policy-level timing)
    global_schedule: ScheduleSpec | None = Field(
        None, description="Global policy schedule (overrides individual if set)"
    )

    # Metadata
    name: TranslatableString | None = Field(None, description="Human-readable policy name")
    description: str | None = Field(None, max_length=2000)
    labels: list[str] = Field(default_factory=list, max_length=20)
    version_tag: str | None = Field(None, max_length=50, description="Semantic version tag")
    notes: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_policy_spec(self) -> "PolicySpec":
        """Validate internal consistency of the policy spec."""

        _validate_unique_ids(self.interventions, "intervention_id")
        _validate_unique_ids(self.mechanism_bindings, "binding_id")
        _validate_unique_ids(self.parameters, "param_id")

        _validate_selector_limits(self.interventions)

        intervention_ids = {intervention.intervention_id for intervention in self.interventions}
        for binding in self.mechanism_bindings:
            for intervention_id in binding.intervention_ids:
                if intervention_id not in intervention_ids:
                    raise ValueError(
                        f"MechanismBinding '{binding.binding_id}' references "
                        f"unknown intervention '{intervention_id}'"
                    )

        for param in self.parameters:
            if param.intervention_id not in intervention_ids:
                raise ValueError(
                    f"ParameterSpec '{param.param_id}' references "
                    f"unknown intervention '{param.intervention_id}'"
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


def _selector_stats(node: SelectorExpr) -> tuple[int, int]:
    """Calculate depth and node count of selector expression."""

    if isinstance(node, SelectorPredicate):
        return 1, 1
    if isinstance(node, SelectorNot):
        depth, nodes = _selector_stats(node.clause)
        return depth + 1, nodes + 1
    if isinstance(node, (SelectorAll, SelectorAny)):
        depths: list[int] = []
        total = 1
        for clause in node.clauses:
            depth, nodes = _selector_stats(clause)
            depths.append(depth)
            total += nodes
        return (max(depths) + 1 if depths else 1), total
    return 1, 1


def _validate_selector_limits(interventions: list[InterventionSpec]) -> None:
    """Validate selector complexity limits."""

    for intervention in interventions:
        depth, nodes = _selector_stats(intervention.target)
        if depth > MAX_SELECTOR_DEPTH:
            raise ValueError(
                f"Selector depth {depth} in intervention '{intervention.intervention_id}' "
                f"exceeds limit {MAX_SELECTOR_DEPTH}"
            )
        if nodes > MAX_SELECTOR_NODES:
            raise ValueError(
                f"Selector nodes {nodes} in intervention '{intervention.intervention_id}' "
                f"exceeds limit {MAX_SELECTOR_NODES}"
            )
