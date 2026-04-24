"""Define the Trinity intervention/governance artifact and its action vocabulary.

``PolicySpec`` is the policy-side boundary object in the Trinity contract: it
declares interventions, mechanism bindings, tunable parameters, and execution
schedules that should be evaluated against a fixed ``ProblemFrame`` and one or
more ``ModelSpec`` world models. Use this module when authoring the "what
should be changed" layer, not the "how the world evolves" layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field, model_validator

from polisyos.ir._validation import (
    ensure_non_empty_dotted_path,
    ensure_unique_ids,
    validate_selector_expr,
)
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.contracts import IdentificationMode, StrategicResponseChannel

if TYPE_CHECKING:
    from polisyos.ir.governance.game_design import MechanismDesignSpec
    from polisyos.ir.governance.policy_composition import PolicyCompositionPlan
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorExpr
    from polisyos.ir.governance.temporal_logic import TemporalPolicyConstraint
    from polisyos.ir.kernel.values import ParamValue
    from polisyos.ir.types import TranslatableString
else:
    from polisyos.ir.governance.game_design import MechanismDesignSpec
    from polisyos.ir.governance.policy_composition import PolicyCompositionPlan
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorExpr
    from polisyos.ir.governance.temporal_logic import TemporalPolicyConstraint
    from polisyos.ir.kernel.values import ParamValue
    from polisyos.ir.types import TranslatableString

# Constants
ID_PATTERN = r"^[a-z][a-z0-9_]*$"
ARTIFACT_ID_PATTERN = r"^sha256:[a-f0-9]{64}$"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
MAX_INTERVENTIONS = 100
MAX_MECHANISM_BINDINGS = 100
MAX_TEMPORAL_CONSTRAINTS = 64
MAX_SELECTOR_DEPTH = 10
MAX_SELECTOR_NODES = 50
MAX_PARAM_PATH_DEPTH = 16


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
    params: dict[str, ParamValue] = Field(default_factory=dict, description="Mechanism parameters")
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
    def validate_temporal_sequence(self) -> TemporalInterventionSequence:
        ensure_unique_ids(
            self.steps,
            key_fn=lambda step: step.step_id,
            label="temporal intervention step_id",
        )
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

    @model_validator(mode="after")
    def validate_param_spec(self) -> ParameterSpec:
        ensure_non_empty_dotted_path(
            self.param_path,
            field_name="param_path",
            max_depth=MAX_PARAM_PATH_DEPTH,
        )
        return self


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
    temporal_constraints: list[TemporalPolicyConstraint] = Field(
        default_factory=list,
        max_length=MAX_TEMPORAL_CONSTRAINTS,
        description="Temporal compliance/consistency constraints for the policy",
    )
    composition: PolicyCompositionPlan | None = Field(
        None,
        description="Optional multi-level override/composition metadata",
    )
    mechanism_design: MechanismDesignSpec | None = Field(
        None,
        description="Optional strategic/mechanism-design contract for the policy",
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
    def validate_policy_spec(self) -> PolicySpec:
        """Validate internal consistency of the policy spec."""

        ensure_unique_ids(
            self.interventions,
            key_fn=lambda item: item.intervention_id,
            label="intervention_id",
        )
        ensure_unique_ids(
            self.mechanism_bindings,
            key_fn=lambda item: item.binding_id,
            label="binding_id",
        )
        ensure_unique_ids(self.parameters, key_fn=lambda item: item.param_id, label="param_id")
        ensure_unique_ids(
            self.temporal_constraints,
            key_fn=lambda item: item.constraint_id,
            label="temporal constraint_id",
        )

        intervention_ids = {intervention.intervention_id for intervention in self.interventions}
        mechanism_ids = {binding.mechanism_id for binding in self.mechanism_bindings}
        for intervention in self.interventions:
            validate_selector_expr(
                intervention.target,
                label=f"intervention '{intervention.intervention_id}'",
                max_depth=MAX_SELECTOR_DEPTH,
                max_nodes=MAX_SELECTOR_NODES,
            )
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

        if self.composition is not None:
            participating_policy_ids = {layer.policy_id for layer in self.composition.layers}
            if (
                self.policy_id not in participating_policy_ids
                and self.composition.base_policy_id != self.policy_id
            ):
                raise ValueError(
                    "composition must reference the current policy_id as base_policy_id "
                    "or as one of the composed layers"
                )

        if self.mechanism_design is not None:
            unknown_mechanisms = set(self.mechanism_design.mechanism_ids) - mechanism_ids
            if unknown_mechanisms:
                raise ValueError(
                    "mechanism_design references unknown mechanism_ids "
                    f"{sorted(unknown_mechanisms)}"
                )

        return self
