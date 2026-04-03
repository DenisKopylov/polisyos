"""Typed policy-design schema layered on top of TrinityBundle."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, fingerprint, from_canonical_bytes
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import KPISpec, ObjectiveSpec, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec, schedule_range
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.values import MoneyValue, ParamValue
from polisyos.ir.model_spec import AssumptionSpec, ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent.constraint_context import extract_budget_envelope

POLICY_CANDIDATE_SCHEMA_VERSION = "1.0"
POLICY_CANDIDATE_SCHEMA_NAME = "polisyos.scientist.policy_design.PolicyCandidateSchema"


class RolloutStep(KernelModel):
    """Single staged rollout action for one intervention."""

    step_id: str = Field(..., pattern=ID_PATTERN)
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    order: int = Field(..., ge=0)
    schedule: ScheduleSpec | None = None
    success_metric_ids: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=10)


class TargetPopulationSpec(KernelModel):
    """Target-population annotation not expressed directly by Trinity."""

    population_id: str = Field(..., pattern=ID_PATTERN)
    description: str = Field(..., min_length=1, max_length=500)
    geography: str | None = Field(None, max_length=200)
    eligibility_tags: list[str] = Field(default_factory=list, max_length=20)
    compatible_transport_tags: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=10)


class ParameterScheduleEntry(KernelModel):
    """Per-parameter staged value schedule."""

    entry_id: str = Field(..., pattern=ID_PATTERN)
    param_id: str = Field(..., pattern=ID_PATTERN)
    scheduled_value: ParamValue
    schedule: ScheduleSpec | None = None
    notes: list[str] = Field(default_factory=list, max_length=10)


class BudgetAllocationEntry(KernelModel):
    """Candidate-level policy-budget allocation."""

    allocation_id: str = Field(..., pattern=ID_PATTERN)
    intervention_id: str | None = Field(None, pattern=ID_PATTERN)
    constraint_id: str | None = Field(None, pattern=ID_PATTERN)
    amount: MoneyValue
    notes: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _validate_non_negative(self) -> "BudgetAllocationEntry":
        if self.amount.amount < Decimal("0"):
            raise ValueError("budget allocation amount must be non-negative")
        return self


class MonitoringSignalSpec(KernelModel):
    """Operational monitoring signal for post-rollout evaluation."""

    monitoring_id: str = Field(..., pattern=ID_PATTERN)
    metric_id: str = Field(..., pattern=ID_PATTERN)
    intervention_id: str | None = Field(None, pattern=ID_PATTERN)
    schedule: ScheduleSpec | None = None
    threshold_hint: str | None = Field(None, max_length=200)
    notes: list[str] = Field(default_factory=list, max_length=10)


class PolicyAssumptionSpec(KernelModel):
    """Surfaceable assumption attached to policy interpretation."""

    assumption_id: str = Field(..., pattern=ID_PATTERN)
    description: str = Field(..., min_length=1, max_length=500)
    source_assumption_id: str | None = Field(None, pattern=ID_PATTERN)
    source_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list, max_length=10)


class TransportAssumptionSpec(KernelModel):
    """Explicit transport/external-validity assumption."""

    transport_id: str = Field(..., pattern=ID_PATTERN)
    description: str = Field(..., min_length=1, max_length=500)
    source_context: str | None = Field(None, max_length=200)
    target_context: str | None = Field(None, max_length=200)
    compatible_population_tags: list[str] = Field(default_factory=list, max_length=20)
    caveats: list[str] = Field(default_factory=list, max_length=20)


class HarmEnvelope(KernelModel):
    """Expected harm summary for rollout planning."""

    max_expected_harm_score: float = Field(default=0.0, ge=0.0, le=1.0)
    at_risk_groups: list[str] = Field(default_factory=list, max_length=20)
    rollback_triggers: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=10)


class FallbackVariant(KernelModel):
    """Fallback candidate that keeps the same problem-frame identity."""

    variant_id: str = Field(..., pattern=ID_PATTERN)
    trinity_bundle: TrinityBundle
    notes: list[str] = Field(default_factory=list, max_length=10)


class PolicyCandidateSchema(KernelModel):
    """Rich Layer-B policy candidate wrapped around TrinityBundle."""

    schema_version: str = Field(POLICY_CANDIDATE_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(..., pattern=ID_PATTERN)
    trinity_bundle: TrinityBundle
    rollout_plan: list[RolloutStep] = Field(default_factory=list)
    target_population: TargetPopulationSpec
    parameter_schedule: list[ParameterScheduleEntry] = Field(default_factory=list)
    budget_allocation: list[BudgetAllocationEntry] = Field(default_factory=list)
    fallback_variants: list[FallbackVariant] = Field(default_factory=list)
    monitoring_plan: list[MonitoringSignalSpec] = Field(default_factory=list)
    evidence_assumptions: list[PolicyAssumptionSpec] = Field(default_factory=list)
    transport_assumptions: list[TransportAssumptionSpec] = Field(default_factory=list)
    expected_harm_envelope: HarmEnvelope = Field(default_factory=HarmEnvelope)
    implementation_notes: list[str] = Field(default_factory=list, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_policy_candidate(self) -> "PolicyCandidateSchema":
        bundle = self.trinity_bundle
        policy_spec = bundle.policy_spec
        problem_frame = bundle.problem_frame

        _validate_unique_ids(self.rollout_plan, "step_id")
        _validate_unique_ids(self.parameter_schedule, "entry_id")
        _validate_unique_ids(self.budget_allocation, "allocation_id")
        _validate_unique_ids(self.fallback_variants, "variant_id")
        _validate_unique_ids(self.monitoring_plan, "monitoring_id")
        _validate_unique_ids(self.evidence_assumptions, "assumption_id")
        _validate_unique_ids(self.transport_assumptions, "transport_id")

        intervention_map = {
            intervention.intervention_id: intervention for intervention in policy_spec.interventions
        }
        parameter_map = {parameter.param_id: parameter for parameter in policy_spec.parameters}
        constraint_ids = {
            constraint.constraint_id for constraint in problem_frame.hard_constraints
        } | {
            constraint.constraint_id for constraint in problem_frame.soft_constraints
        }
        metric_ids = _known_metric_ids(problem_frame)

        for step in self.rollout_plan:
            intervention = intervention_map.get(step.intervention_id)
            if intervention is None:
                raise ValueError(
                    f"rollout step '{step.step_id}' references unknown intervention "
                    f"'{step.intervention_id}'"
                )
            effective_schedule = step.schedule or intervention.schedule
            intervention_range = schedule_range(intervention.schedule)
            if effective_schedule is not None:
                rollout_range = schedule_range(effective_schedule)
                if (
                    rollout_range[0] < intervention_range[0]
                    or rollout_range[1] > intervention_range[1]
                ):
                    raise ValueError(
                        f"rollout step '{step.step_id}' schedule contradicts intervention "
                        f"schedule for '{step.intervention_id}'"
                    )
            for metric_id in step.success_metric_ids:
                if metric_id not in metric_ids:
                    raise ValueError(
                        f"rollout step '{step.step_id}' references unknown metric '{metric_id}'"
                    )

        self._validate_rollout_order(intervention_map)

        for entry in self.parameter_schedule:
            parameter = parameter_map.get(entry.param_id)
            if parameter is None:
                raise ValueError(
                    f"parameter schedule '{entry.entry_id}' references unknown param "
                    f"'{entry.param_id}'"
                )
            if entry.schedule is not None:
                intervention = intervention_map[parameter.intervention_id]
                scheduled_range = schedule_range(entry.schedule)
                intervention_range = schedule_range(intervention.schedule)
                if (
                    scheduled_range[0] < intervention_range[0]
                    or scheduled_range[1] > intervention_range[1]
                ):
                    raise ValueError(
                        f"parameter schedule '{entry.entry_id}' contradicts intervention "
                        f"schedule for '{parameter.intervention_id}'"
                    )

        total_allocated = Decimal("0")
        for entry in self.budget_allocation:
            total_allocated += entry.amount.amount
            if entry.intervention_id is not None and entry.intervention_id not in intervention_map:
                raise ValueError(
                    f"budget allocation '{entry.allocation_id}' references unknown "
                    f"intervention '{entry.intervention_id}'"
                )
            if entry.constraint_id is not None and entry.constraint_id not in constraint_ids:
                raise ValueError(
                    f"budget allocation '{entry.allocation_id}' references unknown "
                    f"constraint '{entry.constraint_id}'"
                )

        budget_envelope = extract_budget_envelope(problem_frame)
        if budget_envelope is not None and total_allocated > budget_envelope:
            raise ValueError(
                "budget allocation exceeds ProblemFrame budget envelope: "
                f"{total_allocated} > {budget_envelope}"
            )

        for item in self.monitoring_plan:
            if item.metric_id not in metric_ids:
                raise ValueError(
                    f"monitoring signal '{item.monitoring_id}' references unknown metric "
                    f"'{item.metric_id}'"
                )
            if item.intervention_id is not None and item.intervention_id not in intervention_map:
                raise ValueError(
                    f"monitoring signal '{item.monitoring_id}' references unknown "
                    f"intervention '{item.intervention_id}'"
                )

        if self.transport_assumptions:
            eligibility = set(self.target_population.eligibility_tags)
            for assumption in self.transport_assumptions:
                compatible = set(assumption.compatible_population_tags)
                if compatible and eligibility and compatible.isdisjoint(eligibility):
                    raise ValueError(
                        f"transport assumption '{assumption.transport_id}' is incompatible "
                        "with target population eligibility tags"
                    )
                if (
                    self.target_population.geography
                    and assumption.target_context
                    and self.target_population.geography != assumption.target_context
                ):
                    raise ValueError(
                        f"transport assumption '{assumption.transport_id}' target_context "
                        "conflicts with target population geography"
                    )

        for variant in self.fallback_variants:
            if (
                variant.trinity_bundle.problem_frame.problem_id
                != bundle.problem_frame.problem_id
            ):
                raise ValueError(
                    f"fallback variant '{variant.variant_id}' changes ProblemFrame identity"
                )

        return self

    def _validate_rollout_order(
        self,
        intervention_map: dict[str, Any],
    ) -> None:
        ordered = sorted(self.rollout_plan, key=lambda item: (item.order, item.step_id))
        previous_start: int | None = None
        previous_order: int | None = None
        for step in ordered:
            intervention = intervention_map[step.intervention_id]
            effective_schedule = step.schedule or intervention.schedule
            start_step, _ = schedule_range(effective_schedule)
            if previous_order is not None and step.order == previous_order and previous_start is None:
                previous_start = start_step
            if previous_start is not None and start_step < previous_start:
                raise ValueError(
                    f"rollout order contradicts schedule ordering at step '{step.step_id}'"
                )
            previous_start = start_step
            previous_order = step.order

    @classmethod
    def from_trinity_bundle(
        cls,
        bundle: TrinityBundle,
        *,
        candidate_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PolicyCandidateSchema":
        rollout_plan = [
            RolloutStep(
                step_id=f"rollout_{index + 1}",
                intervention_id=intervention.intervention_id,
                order=index,
                schedule=intervention.schedule,
            )
            for index, intervention in enumerate(bundle.policy_spec.interventions)
        ]
        parameter_schedule = [
            ParameterScheduleEntry(
                entry_id=f"param_schedule_{index + 1}",
                param_id=parameter.param_id,
                scheduled_value=parameter.default_value,
            )
            for index, parameter in enumerate(bundle.policy_spec.parameters)
        ]
        evidence_assumptions = [
            PolicyAssumptionSpec(
                assumption_id=assumption.assumption_id,
                description=assumption.description,
                source_assumption_id=assumption.assumption_id,
            )
            for assumption in bundle.model_spec.assumptions
        ]
        return cls(
            candidate_id=candidate_id or bundle.policy_spec.policy_id,
            trinity_bundle=bundle,
            rollout_plan=rollout_plan,
            target_population=TargetPopulationSpec(
                population_id=f"{bundle.policy_spec.policy_id}_population",
                description=(
                    f"Default target population for policy '{bundle.policy_spec.policy_id}'"
                ),
            ),
            parameter_schedule=parameter_schedule,
            evidence_assumptions=evidence_assumptions,
            metadata=dict(metadata or {}),
        )

    def to_trinity_bundle(self) -> TrinityBundle:
        return self.trinity_bundle

    def candidate_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude_none=True)
        return fingerprint(payload, prefix=True, canon_spec=CanonSpec(forbid_floats=False))

    def as_search_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude_none=True)
        payload["candidate_hash"] = self.candidate_hash()
        return payload


def persist_policy_candidate_schema(
    store: FileSystemCAS,
    candidate: PolicyCandidateSchema,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist policy candidate schema helper."""
    return store.put_json(
        candidate,
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(
                name=POLICY_CANDIDATE_SCHEMA_NAME,
                version=candidate.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_policy_candidate_schema(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> PolicyCandidateSchema:
    """Load policy candidate schema."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return PolicyCandidateSchema.model_validate(payload)


def _known_metric_ids(problem_frame: ProblemFrame) -> set[str]:
    metrics = {objective.metric_id for objective in problem_frame.objectives}
    metrics.update(kpi.metric_id for kpi in problem_frame.kpis if isinstance(kpi, KPISpec))
    return metrics


def _validate_unique_ids(items: list[Any], attr: str) -> None:
    seen: set[str] = set()
    for item in items:
        value = getattr(item, attr)
        if value in seen:
            raise ValueError(f"duplicate {attr}: {value}")
        seen.add(value)


__all__ = [
    "BudgetAllocationEntry",
    "FallbackVariant",
    "HarmEnvelope",
    "MonitoringSignalSpec",
    "POLICY_CANDIDATE_SCHEMA_NAME",
    "POLICY_CANDIDATE_SCHEMA_VERSION",
    "ParameterScheduleEntry",
    "PolicyAssumptionSpec",
    "PolicyCandidateSchema",
    "RolloutStep",
    "TargetPopulationSpec",
    "TransportAssumptionSpec",
    "load_policy_candidate_schema",
    "persist_policy_candidate_schema",
]
