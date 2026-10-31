"""Typed policy-design schema layered on top of TrinityBundle."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from polisyos.core.artifacts import ArtifactStore, read_core_json_artifact_bytes
from polisyos.core.artifacts import (
    require_return_selected_profile_writer as _require_return_selected_profile_writer,
)
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, fingerprint, from_canonical_bytes, to_canonical_bytes
from polisyos.ir.governance.problem_frame import KPISpec, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec, schedule_range
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.values import MoneyValue, ParamValue
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
    def _validate_non_negative(self) -> BudgetAllocationEntry:
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

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = POLICY_CANDIDATE_SCHEMA_NAME
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = POLICY_CANDIDATE_SCHEMA_VERSION
    ARTIFACT_KIND: ClassVar[Literal["scientist.policy_design.candidate"]] = (
        "scientist.policy_design.candidate"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

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
    def _validate_policy_candidate(self) -> PolicyCandidateSchema:
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
        } | {constraint.constraint_id for constraint in problem_frame.soft_constraints}
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
        for budget_entry in self.budget_allocation:
            total_allocated += budget_entry.amount.amount
            if (
                budget_entry.intervention_id is not None
                and budget_entry.intervention_id not in intervention_map
            ):
                raise ValueError(
                    f"budget allocation '{budget_entry.allocation_id}' references unknown "
                    f"intervention '{budget_entry.intervention_id}'"
                )
            if (
                budget_entry.constraint_id is not None
                and budget_entry.constraint_id not in constraint_ids
            ):
                raise ValueError(
                    f"budget allocation '{budget_entry.allocation_id}' references unknown "
                    f"constraint '{budget_entry.constraint_id}'"
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
            if variant.trinity_bundle.problem_frame.problem_id != bundle.problem_frame.problem_id:
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
            if (
                previous_order is not None
                and step.order == previous_order
                and previous_start is None
            ):
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
    ) -> PolicyCandidateSchema:
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
    store: ArtifactStore,
    candidate: PolicyCandidateSchema,
    *,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist the canonical policy candidate schema used by search, runtime, and replay flows."""
    if type(return_selected_profile) is not bool:
        raise TypeError("return_selected_profile must be a bool")
    if return_selected_profile:
        _require_return_selected_profile_writer(store, "put_json")
    if candidate.schema_version != PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION:
        raise ValueError("policy candidate schema version is not supported by this producer")
    return store.put_json(
        candidate,
        PutOptions(
            kind=PolicyCandidateSchema.ARTIFACT_KIND,
            media_type=PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
                version=PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=return_selected_profile,
    )


def load_policy_candidate_schema(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> PolicyCandidateSchema:
    """Load policy candidate schema."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    return validate_core_model_json_artifact(PolicyCandidateSchema, store, ref)


def policy_candidate_trinity_contents_match(
    candidate_payload: Mapping[str, Any], trinity_payload: Mapping[str, Any]
) -> bool:
    """Compare both selected program trees through one typed decoding path.

    This compares content only. Callers must separately admit the selected
    source profiles and producer attempts.
    """
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    candidate_trinity = TrinityBundle.model_validate(
        from_canonical_bytes(to_canonical_bytes(candidate_payload["trinity_bundle"], spec=spec))
    )
    trinity = TrinityBundle.model_validate(
        from_canonical_bytes(to_canonical_bytes(trinity_payload, spec=spec))
    )
    return to_canonical_bytes(candidate_trinity.model_dump(mode="json"), spec=spec) == (
        to_canonical_bytes(trinity.model_dump(mode="json"), spec=spec)
    )


def policy_candidate_contents_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Compare candidate values without Python's boolean/numeric aliasing."""
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    left_value = validate_policy_candidate_payload(left).model_dump(mode="json")
    right_value = validate_policy_candidate_payload(right).model_dump(mode="json")
    return to_canonical_bytes(left_value, spec=spec) == to_canonical_bytes(right_value, spec=spec)


def validate_policy_candidate_payload(payload: Mapping[str, Any]) -> PolicyCandidateSchema:
    """Decode canonical tagged values before validating an inline candidate."""
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    decoded = from_canonical_bytes(to_canonical_bytes(payload, spec=spec))
    return PolicyCandidateSchema.model_validate(decoded)


def reissue_policy_candidate_schema(
    store: ArtifactStore, ref: ArtifactRef, *, inputs: list[InputRef]
) -> ArtifactRef:
    """Reissue one admitted selected candidate without changing its stored content.

    Raises:
        ValueError: If the selected candidate, writer, or reissued bytes cannot be verified.
    """
    if ref.manifest_profile_sha256 is None:
        raise ValueError("policy_candidate_source_not_established")
    load_policy_candidate_schema(store, ref)
    raw = read_core_json_artifact_bytes(store, ref)
    manifest = store.get_manifest(ref)
    _require_return_selected_profile_writer(store, "put_bytes")
    selected = store.put_bytes(
        raw,
        PutOptions(
            kind=PolicyCandidateSchema.ARTIFACT_KIND,
            media_type=PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    if (
        selected.manifest_profile_sha256 is None
        or selected.artifact_id != ref.artifact_id
        or read_core_json_artifact_bytes(store, selected) != raw
    ):
        raise ValueError("policy_candidate_reissue_not_established")
    load_policy_candidate_schema(store, selected)
    return selected


def persist_selected_policy_candidate_payload(
    store: ArtifactStore, payload: Mapping[str, Any], *, inputs: list[InputRef]
) -> ArtifactRef:
    """Persist a validated inline candidate without dropping its supplied fields.

    Raises:
        ValueError: If the candidate version or selected output is unsupported.
    """
    candidate = validate_policy_candidate_payload(payload)
    if candidate.schema_version != PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION:
        raise ValueError("policy_candidate_version_not_established")
    selected_payload = dict(payload)
    selected_payload.setdefault("schema_version", candidate.schema_version)
    _require_return_selected_profile_writer(store, "put_json")
    selected = store.put_json(
        selected_payload,
        PutOptions(
            kind=PolicyCandidateSchema.ARTIFACT_KIND,
            media_type=PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
                version=PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    if selected.manifest_profile_sha256 is None:
        raise ValueError("policy_candidate_reissue_not_established")
    load_policy_candidate_schema(store, selected)
    return selected


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
    "POLICY_CANDIDATE_SCHEMA_NAME",
    "POLICY_CANDIDATE_SCHEMA_VERSION",
    "BudgetAllocationEntry",
    "FallbackVariant",
    "HarmEnvelope",
    "MonitoringSignalSpec",
    "ParameterScheduleEntry",
    "PolicyAssumptionSpec",
    "PolicyCandidateSchema",
    "RolloutStep",
    "TargetPopulationSpec",
    "TransportAssumptionSpec",
    "load_policy_candidate_schema",
    "policy_candidate_contents_match",
    "policy_candidate_trinity_contents_match",
    "persist_selected_policy_candidate_payload",
    "persist_policy_candidate_schema",
    "reissue_policy_candidate_schema",
    "validate_policy_candidate_payload",
]
