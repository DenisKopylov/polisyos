"""
PolicySpec: The "What" artifact - interventions, parameters, schedule.

This artifact captures the policy actions to be taken, which can be
iterated and optimized while the ProblemFrame remains constant.
"""
from __future__ import annotations

from typing import Annotated, Any, Sequence

from pydantic import Field, model_validator

# Import selector types from surface.py (to be moved later or re-exported)
from polisyos.ir.governance.schedule import ScheduleSpec
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
    """
    Binding between an intervention and a mechanism from the registry.

    Links policy interventions to executable mechanisms.
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
    """
    Policy intervention specification.

    Defines a single policy action with targeting, timing, and parameters.
    Compatible with existing InterventionSpec in surface.py.
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
    notes: list[str] = Field(default_factory=list, max_length=10)


class ParameterSpec(KernelModel):
    """
    Tunable parameter specification with bounds and metadata.

    Supports calibration and sensitivity analysis.
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
    """
    PolicySpec: The "What" artifact.

    Specifies the policy interventions, mechanism bindings, and parameters.
    This artifact is iterated during policy optimization while the ProblemFrame
    remains constant.
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
