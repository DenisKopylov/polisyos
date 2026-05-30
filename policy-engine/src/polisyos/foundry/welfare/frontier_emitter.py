"""Pareto frontier and welfare value-choice emission for Policy Design Cases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon
from polisyos.foundry.welfare.social_weight_provenance import (
    SocialWeightProvenance,
    assert_social_weight_provenance_usable_for_value_choice,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

PARETO_FRONTIER_SCHEMA_VERSION = "policyos.foundry.welfare.pareto_frontier.v1"
VALUE_CHOICE_SCHEMA_VERSION = "policyos.foundry.welfare.value_choice.v1"
WELFARE_AUDIT_TRAIL_SCHEMA_VERSION = "policyos.foundry.welfare.audit_trail.v1"
WELFARE_FRONTIER_EMISSION_SCHEMA_VERSION = (
    "policyos.foundry.welfare.frontier_emission.v1"
)
WELFARE_FRONTIER_SURFACE_SCHEMA_VERSION = "policyos.foundry.welfare.frontier_surface.v1"

ObjectiveDirection = Literal["maximize", "minimize"]
ValueChoiceDecisionStatus = Literal["approved", "review_required", "contested"]
WelfareSurfaceAudience = Literal["public", "reviewer", "expert", "machine"]

_CANON_SPEC = canon.CanonSpec(forbid_floats=False)
_SCALAR_WELFARE_KEYS = frozenset(
    {
        "aggregate_welfare",
        "bcr",
        "net_benefit",
        "npv",
        "scalar_aggregate",
        "scalar_welfare",
        "welfare_aggregate",
        "welfare_delta",
        "welfare_score",
    }
)


class WelfareFrontierError(ValueError):
    """Raised when W8.D welfare frontier semantics would be violated."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class ObjectiveSpec(BaseModel):
    """One objective used in a multi-objective policy tradeoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    direction: ObjectiveDirection
    unit: str | None = None

    @field_validator("objective_id", "label", "unit")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class AlternativeOutcome(BaseModel):
    """Foundry outcome vector for one policy alternative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alternative_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    objective_values: dict[str, float] = Field(min_length=1)
    claim_refs: tuple[str, ...] = Field(min_length=1)
    welfare_bound_refs: tuple[str, ...] = Field(default_factory=tuple)
    social_weight_ref: str | None = None
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    method_refs: tuple[str, ...] = Field(default_factory=tuple)
    uncertainty_refs: tuple[str, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("alternative_id", "label", "social_weight_ref")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator(
        "claim_refs",
        "welfare_bound_refs",
        "evidence_refs",
        "method_refs",
        "uncertainty_refs",
        "notes",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)


class DominanceRecord(BaseModel):
    """Dominance relationship for one non-frontier alternative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alternative_id: str = Field(min_length=1)
    dominated_by: tuple[str, ...] = Field(min_length=1)
    objective_directions: dict[str, ObjectiveDirection]

    @field_validator("alternative_id")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("dominated_by")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)


class ParetoFrontierRecord(BaseModel):
    """Typed Pareto frontier facts over multi-objective tradeoffs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PARETO_FRONTIER_SCHEMA_VERSION
    frontier_id: str = Field(min_length=1)
    claim_refs: tuple[str, ...] = Field(min_length=1)
    objective_specs: tuple[ObjectiveSpec, ...] = Field(min_length=2)
    outcomes: tuple[AlternativeOutcome, ...] = Field(min_length=1)
    frontier_alternative_ids: tuple[str, ...]
    dominated_alternative_ids: tuple[str, ...]
    dominance: dict[str, DominanceRecord] = Field(default_factory=dict)
    welfare_bound_refs: tuple[str, ...] = Field(default_factory=tuple)
    generated_at: datetime
    producer_component: str = "polisyos.foundry.welfare.frontier_emitter"
    producer_version: str = "1.0"
    authority_role: Literal["producer_authority"] = "producer_authority"
    authoritative_for: tuple[str, ...] = ("pareto_frontier_fact",)
    may_not_use_for: tuple[str, ...] = (
        "value_choice_authority",
        "scalar_welfare_authority",
        "claim_authority",
        "projection_authority",
    )

    @field_validator(
        "schema_version",
        "frontier_id",
        "producer_component",
        "producer_version",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "claim_refs",
        "frontier_alternative_ids",
        "dominated_alternative_ids",
        "welfare_bound_refs",
        "authoritative_for",
        "may_not_use_for",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)

    @model_validator(mode="after")
    def _validate_frontier(self) -> ParetoFrontierRecord:
        objective_ids = tuple(objective.objective_id for objective in self.objective_specs)
        if len(set(objective_ids)) != len(objective_ids):
            raise ValueError("objective_ids must be unique")
        alternative_ids = tuple(outcome.alternative_id for outcome in self.outcomes)
        if len(set(alternative_ids)) != len(alternative_ids):
            raise ValueError("alternative_ids must be unique")
        for outcome in self.outcomes:
            missing = set(objective_ids) - set(outcome.objective_values)
            if missing:
                raise ValueError(
                    f"alternative {outcome.alternative_id!r} missing objective values: "
                    f"{sorted(missing)!r}"
                )
        known_ids = set(alternative_ids)
        frontier_ids = set(self.frontier_alternative_ids)
        dominated_ids = set(self.dominated_alternative_ids)
        if frontier_ids | dominated_ids != known_ids:
            raise ValueError("frontier and dominated alternatives must partition outcomes")
        if frontier_ids & dominated_ids:
            raise ValueError("frontier and dominated alternatives must not overlap")
        if set(self.dominance) != dominated_ids:
            raise ValueError("dominance records must match dominated alternatives")
        return self


class ValueChoiceDecisionPoint(BaseModel):
    """Governance/value decision selecting one frontier point."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = VALUE_CHOICE_SCHEMA_VERSION
    decision_id: str = Field(min_length=1)
    frontier_id: str = Field(min_length=1)
    selected_alternative_id: str = Field(min_length=1)
    social_weight_ref: str = Field(min_length=1)
    social_weight_provenance_id: str = Field(min_length=1)
    decision_status: ValueChoiceDecisionStatus
    rejected_nondominated_alternative_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_refs: tuple[str, ...] = Field(min_length=1)
    rationale_refs: tuple[str, ...] = Field(default_factory=tuple)
    dissent_refs: tuple[str, ...] = Field(default_factory=tuple)
    authority_role: Literal["producer_authority"] = "producer_authority"
    authoritative_for: tuple[str, ...] = ("value_choice_record",)
    may_not_use_for: tuple[str, ...] = (
        "pareto_frontier_fact",
        "scalar_welfare_authority",
        "claim_authority",
        "projection_authority",
    )

    @field_validator(
        "schema_version",
        "decision_id",
        "frontier_id",
        "selected_alternative_id",
        "social_weight_ref",
        "social_weight_provenance_id",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "rejected_nondominated_alternative_ids",
        "claim_refs",
        "rationale_refs",
        "dissent_refs",
        "authoritative_for",
        "may_not_use_for",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)


class WelfareAuditTrail(BaseModel):
    """Claim-bound welfare audit trail linking bounds, frontier, and value choice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = WELFARE_AUDIT_TRAIL_SCHEMA_VERSION
    audit_id: str = Field(min_length=1)
    claim_refs: tuple[str, ...] = Field(min_length=1)
    frontier_id: str = Field(min_length=1)
    value_choice_decision_id: str = Field(min_length=1)
    social_weight_provenance_refs: tuple[str, ...] = Field(min_length=1)
    welfare_bound_refs: tuple[str, ...] = Field(default_factory=tuple)
    generated_at: datetime
    audit_events: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    authority_role: Literal["producer_authority"] = "producer_authority"
    authoritative_for: tuple[str, ...] = ("welfare_tradeoff_audit",)
    may_not_use_for: tuple[str, ...] = (
        "scalar_welfare_authority",
        "claim_authority",
        "projection_authority",
    )

    @field_validator(
        "schema_version",
        "audit_id",
        "frontier_id",
        "value_choice_decision_id",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "claim_refs",
        "social_weight_provenance_refs",
        "welfare_bound_refs",
        "authoritative_for",
        "may_not_use_for",
    )
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)


class WelfareFrontierEmission(BaseModel):
    """Atomic W8.D emission bundle for frontier, value choice, and audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = WELFARE_FRONTIER_EMISSION_SCHEMA_VERSION
    frontier: ParetoFrontierRecord
    value_choice: ValueChoiceDecisionPoint
    social_weight_provenance: SocialWeightProvenance
    audit_trail: WelfareAuditTrail
    capability_reality_state: Literal["implemented"] = "implemented"
    pattern_closures: tuple[str, ...] = ("P05", "P15")

    @field_validator("pattern_closures")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)


class WelfareFrontierSurface(BaseModel):
    """Projection-only public/reviewer surface for welfare tradeoffs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = WELFARE_FRONTIER_SURFACE_SCHEMA_VERSION
    surface_id: str = Field(min_length=1)
    audience: WelfareSurfaceAudience
    frontier: ParetoFrontierRecord
    value_choice: ValueChoiceDecisionPoint
    social_weight_provenance: SocialWeightProvenance
    audit_trail: WelfareAuditTrail
    scalar_aggregate: None = None
    authority_role: Literal["projection_only"] = "projection_only"
    authoritative_for: tuple[str, ...] = Field(default_factory=tuple)
    may_be_used_for: tuple[str, ...] = (
        "public_audit",
        "reviewer_inspection",
        "operator_triage",
    )
    may_not_use_for: tuple[str, ...] = (
        "scalar_welfare_authority",
        "claim_authority",
        "runtime_closeout_authority",
        "approval_authority",
    )
    projection_policy: Literal["exposes_frontier_and_value_choice_only"] = (
        "exposes_frontier_and_value_choice_only"
    )

    @field_validator("surface_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("authoritative_for", "may_be_used_for", "may_not_use_for")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)


def emit_welfare_frontier(
    *,
    claim_refs: Sequence[str],
    objectives: Sequence[ObjectiveSpec | Mapping[str, Any]],
    outcomes: Sequence[AlternativeOutcome | Mapping[str, Any]],
    social_weight_provenance: SocialWeightProvenance | Mapping[str, Any] | None,
    selected_alternative_id: str,
    generated_at: datetime | None = None,
    rationale_refs: Sequence[str] = (),
) -> WelfareFrontierEmission:
    """Emit Pareto frontier facts plus a separate social-weighted value choice."""

    if social_weight_provenance is None:
        raise WelfareFrontierError(
            "social_weight_provenance_required",
            "Welfare frontier emission requires social-weight provenance.",
        )
    provenance = assert_social_weight_provenance_usable_for_value_choice(
        social_weight_provenance
    )
    claim_ref_tuple = _clean_tuple(tuple(str(ref) for ref in claim_refs))
    if not claim_ref_tuple:
        raise WelfareFrontierError("claim_refs_required", "Welfare emission must be claim-bound.")
    objective_tuple = tuple(
        objective
        if isinstance(objective, ObjectiveSpec)
        else ObjectiveSpec.model_validate(objective)
        for objective in objectives
    )
    outcome_tuple = tuple(
        outcome
        if isinstance(outcome, AlternativeOutcome)
        else AlternativeOutcome.model_validate(outcome)
        for outcome in outcomes
    )
    if not objective_tuple:
        raise WelfareFrontierError("objectives_required", "At least two objectives are required.")
    if len(objective_tuple) < 2:
        raise WelfareFrontierError(
            "multi_objective_frontier_required",
            "W8.D frontiers must not force aggregation into one objective.",
        )
    if not outcome_tuple:
        raise WelfareFrontierError("outcomes_required", "At least one outcome is required.")
    selected_id = _required_text(selected_alternative_id)
    _assert_social_weight_refs_match(outcome_tuple, provenance.social_weight_ref)

    generated = _utc(generated_at)
    frontier_ids, dominance = _compute_frontier(objective_tuple, outcome_tuple)
    dominated_ids = tuple(
        outcome.alternative_id
        for outcome in outcome_tuple
        if outcome.alternative_id not in frontier_ids
    )
    if selected_id not in {outcome.alternative_id for outcome in outcome_tuple}:
        raise WelfareFrontierError(
            "selected_alternative_unknown",
            "Selected alternative must be present in outcome records.",
        )
    if selected_id not in frontier_ids:
        raise WelfareFrontierError(
            "selected_alternative_not_on_frontier",
            "Value-choice decision must select a nondominated frontier point.",
        )
    welfare_bound_refs = _collect_refs(outcome.welfare_bound_refs for outcome in outcome_tuple)
    frontier_id = _stable_id(
        "pareto-frontier",
        {
            "claim_refs": claim_ref_tuple,
            "objectives": [objective.model_dump(mode="json") for objective in objective_tuple],
            "outcomes": [outcome.model_dump(mode="json") for outcome in outcome_tuple],
            "frontier_ids": frontier_ids,
        },
    )
    frontier = ParetoFrontierRecord(
        frontier_id=frontier_id,
        claim_refs=claim_ref_tuple,
        objective_specs=objective_tuple,
        outcomes=outcome_tuple,
        frontier_alternative_ids=frontier_ids,
        dominated_alternative_ids=dominated_ids,
        dominance=dominance,
        welfare_bound_refs=welfare_bound_refs,
        generated_at=generated,
    )
    decision_id = _stable_id(
        "value-choice",
        {
            "frontier_id": frontier.frontier_id,
            "selected_alternative_id": selected_id,
            "social_weight_provenance_id": provenance.provenance_id,
        },
    )
    value_choice = ValueChoiceDecisionPoint(
        decision_id=decision_id,
        frontier_id=frontier.frontier_id,
        selected_alternative_id=selected_id,
        social_weight_ref=provenance.social_weight_ref,
        social_weight_provenance_id=provenance.provenance_id,
        decision_status=_decision_status(provenance),
        rejected_nondominated_alternative_ids=tuple(
            alternative_id for alternative_id in frontier_ids if alternative_id != selected_id
        ),
        claim_refs=claim_ref_tuple,
        rationale_refs=tuple(rationale_refs),
        dissent_refs=tuple(dissent.dissent_id for dissent in provenance.dissent),
    )
    audit = WelfareAuditTrail(
        audit_id=_stable_id(
            "welfare-audit",
            {
                "frontier_id": frontier.frontier_id,
                "decision_id": value_choice.decision_id,
                "provenance_id": provenance.provenance_id,
            },
        ),
        claim_refs=claim_ref_tuple,
        frontier_id=frontier.frontier_id,
        value_choice_decision_id=value_choice.decision_id,
        social_weight_provenance_refs=(provenance.provenance_id,),
        welfare_bound_refs=welfare_bound_refs,
        generated_at=generated,
        audit_events=(
            {
                "event": "pareto_frontier_emitted",
                "frontier_id": frontier.frontier_id,
                "claim_refs": claim_ref_tuple,
            },
            {
                "event": "value_choice_recorded",
                "decision_id": value_choice.decision_id,
                "social_weight_provenance_id": provenance.provenance_id,
            },
        ),
    )
    return WelfareFrontierEmission(
        frontier=frontier,
        value_choice=value_choice,
        social_weight_provenance=provenance,
        audit_trail=audit,
    )


def build_welfare_frontier_surface(
    emission: WelfareFrontierEmission | Mapping[str, Any],
    *,
    audience: WelfareSurfaceAudience,
) -> WelfareFrontierSurface:
    """Build a projection-only surface that exposes frontier and value choice."""

    record = (
        emission
        if isinstance(emission, WelfareFrontierEmission)
        else WelfareFrontierEmission.model_validate(emission)
    )
    surface = WelfareFrontierSurface(
        surface_id=_stable_id(
            "welfare-frontier-surface",
            {
                "audience": audience,
                "frontier_id": record.frontier.frontier_id,
                "decision_id": record.value_choice.decision_id,
            },
        ),
        audience=audience,
        frontier=record.frontier,
        value_choice=record.value_choice,
        social_weight_provenance=record.social_weight_provenance,
        audit_trail=record.audit_trail,
    )
    assert_welfare_publication_not_scalar_only(surface.model_dump(mode="json"))
    return surface


def assert_welfare_publication_not_scalar_only(
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Block public/reviewer payloads that expose only scalar welfare aggregates."""

    scalar_keys = {
        key for key, value in payload.items() if key in _SCALAR_WELFARE_KEYS and value is not None
    }
    if not scalar_keys:
        return payload
    has_frontier = bool(payload.get("frontier") or payload.get("pareto_frontier"))
    has_value_choice = bool(payload.get("value_choice") or payload.get("value_choice_decision"))
    has_provenance = bool(
        payload.get("social_weight_provenance") or payload.get("social_weight_provenance_refs")
    )
    if has_frontier and has_value_choice and has_provenance:
        return payload
    raise WelfareFrontierError(
        "scalar_welfare_aggregate_without_frontier",
        "Scalar welfare aggregates cannot be published without Pareto frontier, "
        "value-choice, and social-weight provenance records.",
    )


def persist_welfare_frontier_emission(
    store: artifacts.FileSystemCAS,
    emission: WelfareFrontierEmission | Mapping[str, Any],
    *,
    inputs: list[artifacts.InputRef] | None = None,
) -> artifacts.ArtifactRef:
    """Persist a complete W8.D frontier emission bundle."""

    record = (
        emission
        if isinstance(emission, WelfareFrontierEmission)
        else WelfareFrontierEmission.model_validate(emission)
    )
    return store.put_json(
        record.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="foundry.welfare_frontier_emission",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.foundry.welfare.WelfareFrontierEmission",
                version=record.schema_version,
            ),
            inputs=inputs,
        ),
        canon_spec=_CANON_SPEC,
    )


def load_welfare_frontier_emission(
    store: artifacts.FileSystemCAS,
    ref: artifacts.ArtifactRef,
) -> WelfareFrontierEmission:
    """Load a persisted W8.D frontier emission bundle."""

    payload = canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return WelfareFrontierEmission.model_validate(payload)


def _compute_frontier(
    objectives: tuple[ObjectiveSpec, ...],
    outcomes: tuple[AlternativeOutcome, ...],
) -> tuple[tuple[str, ...], dict[str, DominanceRecord]]:
    directions = {objective.objective_id: objective.direction for objective in objectives}
    frontier_ids: list[str] = []
    dominance: dict[str, DominanceRecord] = {}
    for candidate in outcomes:
        dominators = tuple(
            challenger.alternative_id
            for challenger in outcomes
            if challenger.alternative_id != candidate.alternative_id
            and _dominates(challenger, candidate, objectives)
        )
        if dominators:
            dominance[candidate.alternative_id] = DominanceRecord(
                alternative_id=candidate.alternative_id,
                dominated_by=dominators,
                objective_directions=directions,
            )
        else:
            frontier_ids.append(candidate.alternative_id)
    return tuple(frontier_ids), dominance


def _dominates(
    challenger: AlternativeOutcome,
    candidate: AlternativeOutcome,
    objectives: tuple[ObjectiveSpec, ...],
) -> bool:
    at_least_as_good = True
    strictly_better = False
    for objective in objectives:
        challenger_value = float(challenger.objective_values[objective.objective_id])
        candidate_value = float(candidate.objective_values[objective.objective_id])
        if objective.direction == "maximize":
            if challenger_value + 1.0e-12 < candidate_value:
                at_least_as_good = False
                break
            if challenger_value > candidate_value + 1.0e-12:
                strictly_better = True
        else:
            if challenger_value > candidate_value + 1.0e-12:
                at_least_as_good = False
                break
            if challenger_value + 1.0e-12 < candidate_value:
                strictly_better = True
    return at_least_as_good and strictly_better


def _assert_social_weight_refs_match(
    outcomes: tuple[AlternativeOutcome, ...],
    social_weight_ref: str,
) -> None:
    mismatches = [
        outcome.alternative_id
        for outcome in outcomes
        if outcome.social_weight_ref is not None and outcome.social_weight_ref != social_weight_ref
    ]
    if mismatches:
        raise WelfareFrontierError(
            "social_weight_ref_mismatch",
            "Outcome social_weight_ref values must match the selected provenance record.",
        )


def _decision_status(provenance: SocialWeightProvenance) -> ValueChoiceDecisionStatus:
    if provenance.review_status == "contested":
        return "contested"
    if provenance.publication_readiness == "ready":
        return "approved"
    return "review_required"


def _collect_refs(ref_groups: Sequence[Sequence[str]]) -> tuple[str, ...]:
    collected: list[str] = []
    for group in ref_groups:
        collected.extend(group)
    return _clean_tuple(tuple(collected)) if collected else ()


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = canon.fingerprint(payload, canon_spec=_CANON_SPEC)[:16]
    return f"{prefix}:{digest}"


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).replace(microsecond=0)
    return value.astimezone(UTC).replace(microsecond=0)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _required_text(value: str) -> str:
    stripped = str(value).strip()
    if not stripped:
        raise ValueError("value must be non-empty")
    return stripped


def _clean_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if len(cleaned) != len(values):
        raise ValueError("tuple values must be non-empty and unique")
    return cleaned


__all__ = [
    "AlternativeOutcome",
    "DominanceRecord",
    "ObjectiveSpec",
    "ParetoFrontierRecord",
    "ValueChoiceDecisionPoint",
    "WelfareAuditTrail",
    "WelfareFrontierEmission",
    "WelfareFrontierError",
    "WelfareFrontierSurface",
    "assert_welfare_publication_not_scalar_only",
    "build_welfare_frontier_surface",
    "emit_welfare_frontier",
    "load_welfare_frontier_emission",
    "persist_welfare_frontier_emission",
]
