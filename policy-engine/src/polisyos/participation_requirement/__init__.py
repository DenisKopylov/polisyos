"""Participation provenance requirement compiler and consumer enforcement.

The compiler implements ADR-0167's participation matrix as a deterministic
claim-use ceiling. It produces requirements; it does not make participation
facts authoritative. Consumers must evaluate real participation records against
the compiled requirement before preference, legitimacy, prevalence, or public
projection surfaces may use them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PARTICIPATION_REQUIREMENT_SPEC_SCHEMA_VERSION = (
    "policyos.participation_requirement.spec.v1"
)
PARTICIPATION_REQUIREMENT_BUNDLE_SCHEMA_VERSION = (
    "policyos.participation_requirement.bundle.v1"
)
PARTICIPATION_EVALUATION_SCHEMA_VERSION = (
    "policyos.participation_requirement.evaluation.v1"
)
PARTICIPATION_RULE_VERSION = "adr-0167.participation-legitimacy-matrix.v1"


class ParticipationClaimUse(StrEnum):
    """ADR-0167 claim-use ceiling values."""

    PREVALENCE = "prevalence"
    EXISTENCE = "existence"
    QUALITATIVE = "qualitative"
    ROLE_FEASIBILITY = "role-feasibility"
    DISSENT = "dissent"
    CONTEXT_ONLY = "context-only"


class ParticipationClaimPurpose(StrEnum):
    """Broader C34 participation purpose for the source claim."""

    PREFERENCE = "preference"
    LIVED_EXPERIENCE = "lived_experience"
    ACCEPTABILITY = "acceptability"
    LEGITIMACY = "legitimacy"
    PROCEDURAL_FAIRNESS = "procedural_fairness"
    IMPLEMENTATION_FEASIBILITY = "implementation_feasibility"
    OBJECTION_DISSENT = "objection_dissent"
    CONTEXT = "context"


class ParticipationAuthorityLevel(StrEnum):
    """Authority level used by the participation matrix."""

    RESEARCH = "research"
    GOVERNED = "governed"
    PRODUCTION = "production"


class ParticipationPopulationScope(StrEnum):
    """Population scope used by ADR-0167."""

    INDIVIDUAL_OR_CASE = "individual_or_case"
    AFFECTED_SUBGROUP = "affected_subgroup"
    AFFECTED_POPULATION = "affected_population"
    GENERAL_POPULATION = "general_population"


class ParticipationSourceKind(StrEnum):
    """Participation source kinds recognised by C19/C34."""

    SURVEY = "survey"
    DELIBERATIVE_PANEL = "deliberative_panel"
    HEARING = "hearing"
    COMPLAINT = "complaint"
    ADMINISTRATIVE_COMPLAINT = "administrative_complaint"
    CIVIL_SOCIETY_SUBMISSION = "civil_society_submission"
    TESTIMONY = "testimony"
    EXPERT_INTERVIEW = "expert_interview"
    CONSULTATION = "consultation"
    ANALYST_SUMMARY = "analyst_summary"
    LLM_SPECULATION = "llm_speculation"


class ParticipationProvenanceClass(StrEnum):
    """ADR-0167 provenance classes."""

    A_REPRESENTATIVE_POPULATION = "A_representative_population"
    B_STRUCTURED_DELIBERATIVE_OR_PROCESS = "B_structured_deliberative_or_process"
    C_ATTRIBUTABLE_NONREPRESENTATIVE = "C_attributable_nonrepresentative"
    D_UNVERIFIABLE_OR_SPECULATIVE = "D_unverifiable_or_speculative"


class ParticipationRepresentativenessClass(StrEnum):
    """Representativeness classes used as governed threshold outcomes."""

    REPRESENTATIVE = "representative"
    MODELED_REPRESENTATIVE = "modeled_representative"
    STRUCTURED_SUBGROUP_OR_ROLE = "structured_subgroup_or_role"
    ATTRIBUTABLE_NONREPRESENTATIVE = "attributable_nonrepresentative"
    NONREPRESENTATIVE = "nonrepresentative"
    UNKNOWN = "unknown"


class ParticipationAuthorityBoundary(BaseModel):
    """Purpose-scoped authority boundary for requirements and evaluations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authoritative_for: tuple[str, ...] = ("participation_requirement",)
    may_not_use_for: tuple[str, ...] = (
        "participation_evidence_authority",
        "participation_authority",
        "claim_support_authority",
        "closeout_authority",
        "projection_authority",
    )

    @field_validator("authoritative_for", "may_not_use_for")
    @classmethod
    def _clean_text_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(value)


class ParticipationRepresentativenessConfig(BaseModel):
    """Governed tuned participation-threshold configuration descriptor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_ref: str = "config://policyos/participation/representativeness/default-v1"
    version: str = "1.0"
    methodology_owner: str = "team-methodology"
    governance_owner: str = "team-governance"
    status: Literal["governed_config", "advisory"] = "governed_config"
    feature_flag: str = "universal_pdc_participation_matrix"
    threshold_names: tuple[str, ...] = (
        "sample_size",
        "response_rate",
        "coverage",
        "weighting",
        "subgroup_coverage",
    )

    @field_validator(
        "config_ref",
        "version",
        "methodology_owner",
        "governance_owner",
        "feature_flag",
    )
    @classmethod
    def _clean_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("threshold_names")
    @classmethod
    def _clean_thresholds(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(value)


class ParticipationProvenanceRequirementSpec(BaseModel):
    """Compiled participation requirement for one claim use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[PARTICIPATION_REQUIREMENT_SPEC_SCHEMA_VERSION] = (
        PARTICIPATION_REQUIREMENT_SPEC_SCHEMA_VERSION
    )
    requirement_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim_family: str = Field(min_length=1)
    claim_purpose: ParticipationClaimPurpose
    claim_use_requested: ParticipationClaimUse
    authority_level: ParticipationAuthorityLevel
    population_scope: ParticipationPopulationScope
    required_modes: tuple[ParticipationSourceKind, ...]
    required_sampling_frame: str = Field(min_length=1)
    minimum_provenance_class: ParticipationProvenanceClass
    minimum_representativeness_class: ParticipationRepresentativenessClass
    consent_redaction: str = Field(min_length=1)
    dissent_handling: str = Field(min_length=1)
    sponsor_disclosure: str = Field(min_length=1)
    process_evidence_requirements: tuple[str, ...] = Field(default=())
    public_projection_obligations: tuple[str, ...] = (
        "show_source_kind",
        "show_representativeness_class",
        "show_claim_use_allowed",
        "show_participation_gaps",
        "show_dissent_presence",
        "show_limitations",
    )
    privacy_constraints: tuple[str, ...] = (
        "raw_transcripts_must_be_redacted",
        "direct_identifiers_must_be_redacted",
        "safe_participant_band_required",
        "do_not_hide_dissent_or_gaps",
    )
    obligation_refs: tuple[str, ...] = Field(default=())
    facet_refs: tuple[str, ...] = Field(default=())
    concept_spine_refs: tuple[str, ...] = Field(default=())
    authority_profile_refs: tuple[str, ...] = Field(default=())
    rule_version: str = PARTICIPATION_RULE_VERSION
    representativeness_config: ParticipationRepresentativenessConfig = Field(
        default_factory=ParticipationRepresentativenessConfig
    )
    authority_boundary: ParticipationAuthorityBoundary = Field(
        default_factory=ParticipationAuthorityBoundary
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "requirement_id",
        "run_id",
        "claim_id",
        "claim_family",
        "required_sampling_frame",
        "consent_redaction",
        "dissent_handling",
        "sponsor_disclosure",
        "rule_version",
    )
    @classmethod
    def _clean_required(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "required_modes",
        "process_evidence_requirements",
        "public_projection_obligations",
        "privacy_constraints",
        "obligation_refs",
        "facet_refs",
        "concept_spine_refs",
        "authority_profile_refs",
    )
    @classmethod
    def _clean_tuple(cls, value: tuple[Any, ...]) -> tuple[Any, ...]:
        if value and isinstance(value[0], StrEnum):
            return tuple(dict.fromkeys(value))
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_modes(self) -> ParticipationProvenanceRequirementSpec:
        if not self.required_modes:
            raise ValueError("participation requirements need at least one required mode")
        if self.claim_use_requested is ParticipationClaimUse.PREVALENCE and (
            ParticipationSourceKind.SURVEY not in self.required_modes
        ):
            raise ValueError("prevalence participation requirements require survey mode")
        return self


class ParticipationRequirementBundle(BaseModel):
    """Bundle of compiled participation requirements for one run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[PARTICIPATION_REQUIREMENT_BUNDLE_SCHEMA_VERSION] = (
        PARTICIPATION_REQUIREMENT_BUNDLE_SCHEMA_VERSION
    )
    run_id: str = Field(min_length=1)
    requirements: tuple[ParticipationProvenanceRequirementSpec, ...] = Field(default=())
    rule_version: str = PARTICIPATION_RULE_VERSION
    runtime_event_ref: str | None = Field(default=None, min_length=1)
    authority_boundary: ParticipationAuthorityBoundary = Field(
        default_factory=lambda: ParticipationAuthorityBoundary(
            authoritative_for=(
                "participation_provenance_requirements",
                "participation_projection_preconditions",
                "participation_claim_use_downgrades",
            ),
            may_not_use_for=(
                "participation_evidence_authority",
                "claim_support_authority",
                "legal_authority",
                "method_validity",
                "closeout_pass",
            ),
        )
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_runtime_event_ref(self) -> ParticipationRequirementBundle:
        if self.runtime_event_ref is None:
            object.__setattr__(
                self,
                "runtime_event_ref",
                f"event://participation-requirement/{_slug(self.run_id)}",
            )
        return self


class ParticipationProvenanceRecord(BaseModel):
    """Real or candidate participation provenance consumed by W7.E enforcement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.participation_requirement.record.v1"] = (
        "policyos.participation_requirement.record.v1"
    )
    participation_ref: str = Field(min_length=1)
    claim_refs: tuple[str, ...] = Field(default=())
    source_kind: ParticipationSourceKind
    consultation_mode: str | None = None
    provenance_class: ParticipationProvenanceClass
    representativeness_class: ParticipationRepresentativenessClass
    sampling_or_recruitment_frame: str | None = None
    affected_group_map: dict[str, Any] = Field(default_factory=dict)
    instrument_or_briefing_ref: str | None = None
    facilitation_or_sponsor_ref: str | None = None
    event_time: str | None = None
    policy_lock_in_time: str | None = None
    geography_scope: str | None = None
    consent_redaction_state: str = Field(min_length=1)
    aggregation_method: str | None = None
    dissent_state: str = Field(min_length=1)
    response_to_comment_ref: str | None = None
    sponsor_disclosure: str | None = None
    limitations: tuple[str, ...] = Field(default=())
    evidence_ref: str | None = None
    raw_material_ref: str | None = None
    capability_ref: str | None = None
    construct_ref: str | None = None
    capability_index_ref: str | None = None
    construct_registry_ref: str | None = None
    authority_composition_rule_ref: str | None = None
    consent_envelope: dict[str, Any] = Field(default_factory=dict)
    source_limitations: tuple[str, ...] = Field(default=())
    source_class: str = "deterministic_producer"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "participation_ref",
        "consultation_mode",
        "sampling_or_recruitment_frame",
        "instrument_or_briefing_ref",
        "facilitation_or_sponsor_ref",
        "event_time",
        "policy_lock_in_time",
        "geography_scope",
        "consent_redaction_state",
        "aggregation_method",
        "dissent_state",
        "response_to_comment_ref",
        "sponsor_disclosure",
        "evidence_ref",
        "raw_material_ref",
        "capability_ref",
        "construct_ref",
        "capability_index_ref",
        "construct_registry_ref",
        "authority_composition_rule_ref",
        "source_class",
    )
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("claim_refs", "limitations", "source_limitations")
    @classmethod
    def _clean_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(value)


class ParticipationPublicProjectionRow(BaseModel):
    """Privacy-safe participation row for public/API/dashboard projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    participation_ref: str | None = None
    claim_use_requested: ParticipationClaimUse
    claim_use_allowed: ParticipationClaimUse
    source_kind: str = Field(min_length=1)
    consultation_mode: str | None = None
    provenance_class: str = Field(min_length=1)
    representativeness_class: str = Field(min_length=1)
    public_projection_effect: str = Field(min_length=1)
    downgrade_reason: str | None = None
    blocker_code: str | None = None
    limitations: tuple[str, ...] = Field(default=())
    privacy_constraints: tuple[str, ...] = Field(default=())
    raw_materials_redacted: bool = True
    evidence_ref: str | None = None
    audience_visibility: tuple[str, ...] = ("public", "reviewer", "expert", "machine")

    @field_validator(
        "requirement_id",
        "claim_id",
        "participation_ref",
        "source_kind",
        "consultation_mode",
        "provenance_class",
        "representativeness_class",
        "public_projection_effect",
        "downgrade_reason",
        "blocker_code",
        "evidence_ref",
    )
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("limitations", "privacy_constraints", "audience_visibility")
    @classmethod
    def _clean_text_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(value)


class ParticipationDeficitRecord(BaseModel):
    """Projection/readiness deficit emitted from unmet participation requirements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deficit_id: str = Field(min_length=1)
    deficit_family: Literal["participation"] = "participation"
    deficit_code: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(default=())
    authority_level: str = Field(min_length=1)
    audience_scope: str = "public"
    disposition: str = Field(min_length=1)
    owner: str = "team-participation"
    runtime_event_ref: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    support_cap: str | None = None
    readiness_cap: str | None = None
    max_audience: str | None = None
    public_limitation_note: str | None = None
    review_refs: tuple[str, ...] = Field(default=())


class ParticipationRequirementEvaluation(BaseModel):
    """Consumer-side enforcement result for one participation requirement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[PARTICIPATION_EVALUATION_SCHEMA_VERSION] = (
        PARTICIPATION_EVALUATION_SCHEMA_VERSION
    )
    requirement_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    participation_ref: str | None = None
    status: Literal["satisfied", "downgraded", "blocked", "missing"]
    claim_use_requested: ParticipationClaimUse
    claim_use_allowed: ParticipationClaimUse
    authority_level: ParticipationAuthorityLevel
    population_scope: ParticipationPopulationScope
    downgrade_reason: str | None = None
    blocker_code: str | None = None
    case_closeout_effect: str = Field(min_length=1)
    public_projection_rows: tuple[ParticipationPublicProjectionRow, ...] = Field(default=())
    deficit_records: tuple[ParticipationDeficitRecord, ...] = Field(default=())
    authority_boundary: ParticipationAuthorityBoundary = Field(
        default_factory=lambda: ParticipationAuthorityBoundary(
            authoritative_for=("participation_requirement_evaluation",),
            may_not_use_for=(
                "participation_authority",
                "claim_support_authority",
                "closeout_authority",
                "projection_authority",
            ),
        )
    )
    raw_material_ref: str | None = None
    capability_ref: str | None = None
    construct_ref: str | None = None
    capability_index_ref: str | None = None
    construct_registry_ref: str | None = None
    authority_composition_rule_ref: str | None = None
    consent_envelope: dict[str, Any] = Field(default_factory=dict)
    source_limitations: tuple[str, ...] = Field(default=())
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParticipationProvenanceCompiler:
    """Deterministic compiler from claim records to participation requirements."""

    def compile(self, payload: Mapping[str, Any]) -> ParticipationRequirementBundle:
        """Compile participation requirements from claim-like mappings."""

        run_id = _required_text(payload.get("run_id") or "run")
        claims = _claims_from_payload(payload)
        requirements = tuple(
            spec
            for claim in claims
            if (spec := self._requirement_for_claim(run_id, claim)) is not None
        )
        return ParticipationRequirementBundle(
            run_id=run_id,
            requirements=requirements,
            metadata={
                "producer": "participation_provenance_requirement_compiler",
                "capability_reality_label": "implemented",
                "pattern_guards": ["P05", "P10", "P14", "P15"],
                "requirement_count": len(requirements),
            },
        )

    def _requirement_for_claim(
        self,
        run_id: str,
        claim: Mapping[str, Any],
    ) -> ParticipationProvenanceRequirementSpec | None:
        claim_id = _optional_text(claim.get("claim_id") or claim.get("id"))
        if claim_id is None:
            return None
        purpose = _claim_purpose(claim)
        if purpose is None:
            return None
        requested = _requested_use(claim, purpose)
        authority_level = _authority_level(claim)
        population_scope = _population_scope(claim)
        matrix = _matrix_row(purpose=purpose, requested=requested)
        requirement_id = _stable_id(
            "participation_requirement",
            run_id,
            claim_id,
            requested.value,
            authority_level.value,
            population_scope.value,
        )
        return ParticipationProvenanceRequirementSpec(
            requirement_id=requirement_id,
            run_id=run_id,
            claim_id=claim_id,
            claim_family=_required_text(claim.get("claim_family") or purpose.value),
            claim_purpose=purpose,
            claim_use_requested=requested,
            authority_level=authority_level,
            population_scope=population_scope,
            required_modes=matrix["required_modes"],
            required_sampling_frame=matrix["required_sampling_frame"],
            minimum_provenance_class=matrix["minimum_provenance_class"],
            minimum_representativeness_class=matrix[
                "minimum_representativeness_class"
            ],
            consent_redaction=matrix["consent_redaction"],
            dissent_handling=matrix["dissent_handling"],
            sponsor_disclosure=matrix["sponsor_disclosure"],
            process_evidence_requirements=matrix["process_evidence_requirements"],
            obligation_refs=_text_tuple(claim.get("obligation_refs")),
            facet_refs=_text_tuple(claim.get("facet_refs")),
            concept_spine_refs=_text_tuple(claim.get("concept_spine_refs")),
            authority_profile_refs=_text_tuple(claim.get("authority_profile_refs")),
            metadata={
                "source": "claim_record",
                "claim_text_digest": _digest({"text": _optional_text(claim.get("text"))}),
            },
        )


def compile_participation_requirements(
    payload: Mapping[str, Any],
) -> ParticipationRequirementBundle:
    """Compile participation provenance requirements with the default compiler."""

    return ParticipationProvenanceCompiler().compile(payload)


def participation_requirement_bundle_audit_surface(
    bundle: ParticipationRequirementBundle | Mapping[str, Any],
) -> dict[str, Any]:
    """Return an audit/API projection of participation requirements."""

    model = (
        bundle
        if isinstance(bundle, ParticipationRequirementBundle)
        else ParticipationRequirementBundle.model_validate(dict(bundle))
    )
    payload = model.model_dump(mode="json")
    payload["surface"] = "participation_requirement.audit_surface"
    payload["summary"] = {
        "requirement_count": len(model.requirements),
        "claim_ids": [requirement.claim_id for requirement in model.requirements],
        "claim_uses": sorted(
            {requirement.claim_use_requested.value for requirement in model.requirements}
        ),
        "required_modes": sorted(
            {
                mode.value
                for requirement in model.requirements
                for mode in requirement.required_modes
            }
        ),
    }
    return payload


def write_participation_requirement_bundle(
    bundle: ParticipationRequirementBundle | Mapping[str, Any],
    output_dir: str | Path,
) -> Path:
    """Persist a participation requirement bundle as deterministic JSON."""

    model = (
        bundle
        if isinstance(bundle, ParticipationRequirementBundle)
        else ParticipationRequirementBundle.model_validate(dict(bundle))
    )
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slug(model.run_id)}-participation-requirements.json"
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def evaluate_participation_requirement(
    requirement: ParticipationProvenanceRequirementSpec | Mapping[str, Any],
    records: Sequence[ParticipationProvenanceRecord | Mapping[str, Any]],
    capability_bindings: Sequence[Mapping[str, Any] | object] = (),
) -> ParticipationRequirementEvaluation:
    """Evaluate participation records against one compiled requirement."""

    spec = (
        requirement
        if isinstance(requirement, ParticipationProvenanceRequirementSpec)
        else ParticipationProvenanceRequirementSpec.model_validate(requirement)
    )
    candidate_records = [
        record
        if isinstance(record, ParticipationProvenanceRecord)
        else ParticipationProvenanceRecord.model_validate(record)
        for record in records
    ]
    if not candidate_records:
        candidate_records = _records_from_capability_bindings(spec, capability_bindings)
    record = _select_record(spec, candidate_records)
    if record is None:
        return _evaluation(
            spec,
            record=None,
            status="missing",
            allowed=ParticipationClaimUse.CONTEXT_ONLY,
            downgrade_reason=None,
            blocker_code="participation_provenance_missing",
        )

    if record.source_kind in {
        ParticipationSourceKind.LLM_SPECULATION,
        ParticipationSourceKind.ANALYST_SUMMARY,
    } or record.provenance_class is ParticipationProvenanceClass.D_UNVERIFIABLE_OR_SPECULATIVE:
        return _evaluation(
            spec,
            record=record,
            status="blocked",
            allowed=ParticipationClaimUse.CONTEXT_ONLY,
            downgrade_reason=None,
            blocker_code="llm_speculation_not_participation"
            if record.source_kind
            in {ParticipationSourceKind.LLM_SPECULATION, ParticipationSourceKind.ANALYST_SUMMARY}
            else "summary_without_underlying_method",
        )

    allowed = _allowed_use_for_record(record, spec)
    if _use_rank(allowed) >= _use_rank(spec.claim_use_requested):
        return _evaluation(
            spec,
            record=record,
            status="satisfied",
            allowed=spec.claim_use_requested,
            downgrade_reason=None,
            blocker_code=None,
        )

    return _evaluation(
        spec,
        record=record,
        status="downgraded",
        allowed=allowed,
        downgrade_reason=_downgrade_reason(spec, record, allowed),
        blocker_code=None,
    )


def _evaluation(
    spec: ParticipationProvenanceRequirementSpec,
    *,
    record: ParticipationProvenanceRecord | None,
    status: Literal["satisfied", "downgraded", "blocked", "missing"],
    allowed: ParticipationClaimUse,
    downgrade_reason: str | None,
    blocker_code: str | None,
) -> ParticipationRequirementEvaluation:
    closeout_effect = _closeout_effect(status=status, blocker_code=blocker_code)
    participation_ref = record.participation_ref if record is not None else None
    limitations = tuple(record.limitations) if record is not None else ()
    source_limitations = tuple(record.source_limitations) if record is not None else ()
    evidence_ref = (
        record.evidence_ref
        if record is not None and record.evidence_ref is not None
        else f"participation_requirement:{spec.requirement_id}"
    )
    projection_effect = (
        "supports_claim"
        if status == "satisfied"
        else "show_limitation"
        if status == "downgraded"
        else "show_participation_gap"
    )
    row = ParticipationPublicProjectionRow(
        requirement_id=spec.requirement_id,
        claim_id=spec.claim_id,
        participation_ref=participation_ref,
        claim_use_requested=spec.claim_use_requested,
        claim_use_allowed=allowed,
        source_kind=record.source_kind.value if record is not None else "missing",
        consultation_mode=record.consultation_mode if record is not None else None,
        provenance_class=record.provenance_class.value if record is not None else "missing",
        representativeness_class=record.representativeness_class.value
        if record is not None
        else "unknown",
        public_projection_effect=projection_effect,
        downgrade_reason=downgrade_reason,
        blocker_code=blocker_code,
        limitations=tuple(dict.fromkeys([*limitations, *source_limitations])),
        privacy_constraints=spec.privacy_constraints,
        raw_materials_redacted=True,
        evidence_ref=evidence_ref,
    )
    deficits: tuple[ParticipationDeficitRecord, ...] = ()
    if status in {"downgraded", "blocked", "missing"}:
        code = blocker_code or downgrade_reason or "participation_requirement_unmet"
        disposition = (
            "publish_with_limitation" if status == "downgraded" else "affected_claim_blocked"
        )
        deficits = (
            ParticipationDeficitRecord(
                deficit_id=_stable_id("participation_deficit", spec.requirement_id, code),
                deficit_code=code,
                claim_ids=(spec.claim_id,),
                authority_level=spec.authority_level.value,
                disposition=disposition,
                runtime_event_ref=f"event://participation_requirement/{spec.requirement_id}",
                evidence_ref=evidence_ref,
                support_cap=allowed.value,
                readiness_cap="review_required" if status == "downgraded" else "blocked",
                max_audience="public",
                public_limitation_note=(
                    f"Participation use downgraded from {spec.claim_use_requested.value} "
                    f"to {allowed.value}: {code}."
                ),
            ),
        )
    return ParticipationRequirementEvaluation(
        requirement_id=spec.requirement_id,
        claim_id=spec.claim_id,
        participation_ref=participation_ref,
        status=status,
        claim_use_requested=spec.claim_use_requested,
        claim_use_allowed=allowed,
        authority_level=spec.authority_level,
        population_scope=spec.population_scope,
        downgrade_reason=downgrade_reason,
        blocker_code=blocker_code,
        case_closeout_effect=closeout_effect,
        public_projection_rows=(row,),
        deficit_records=deficits,
        raw_material_ref=record.raw_material_ref if record is not None else None,
        capability_ref=record.capability_ref if record is not None else None,
        construct_ref=record.construct_ref if record is not None else None,
        capability_index_ref=record.capability_index_ref if record is not None else None,
        construct_registry_ref=record.construct_registry_ref if record is not None else None,
        authority_composition_rule_ref=record.authority_composition_rule_ref
        if record is not None
        else None,
        consent_envelope=record.consent_envelope if record is not None else {},
        source_limitations=source_limitations,
        metadata={
            "rule_version": spec.rule_version,
            "pattern_guards": ["P05", "P10", "P14", "P15"],
            "typed_limitation": "participation_evidence_absent"
            if status == "missing"
            else None,
        },
    )


def _claims_from_payload(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = payload.get("claims") or payload.get("claim_records") or payload.get("family_assignments")
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, Sequence) and not isinstance(raw, str):
        return [item for item in raw if isinstance(item, Mapping)]
    claim = payload.get("claim")
    return [claim] if isinstance(claim, Mapping) else []


def _claim_purpose(claim: Mapping[str, Any]) -> ParticipationClaimPurpose | None:
    token = " ".join(
        _optional_text(value) or ""
        for value in (
            claim.get("claim_family"),
            claim.get("family"),
            claim.get("claim_use"),
            claim.get("text"),
            claim.get("normalized_subject"),
        )
    ).casefold()
    mapping = (
        (("preference", "preferred", "prefer"), ParticipationClaimPurpose.PREFERENCE),
        (
            ("lived_experience", "lived experience", "harm", "barrier"),
            ParticipationClaimPurpose.LIVED_EXPERIENCE,
        ),
        (
            ("acceptability", "acceptable", "participation_legitimacy"),
            ParticipationClaimPurpose.ACCEPTABILITY,
        ),
        (("legitimacy", "legitimate"), ParticipationClaimPurpose.LEGITIMACY),
        (
            ("procedural_fairness", "procedural", "fairness", "due process"),
            ParticipationClaimPurpose.PROCEDURAL_FAIRNESS,
        ),
        (
            ("implementation_feasibility", "implementation", "feasibility"),
            ParticipationClaimPurpose.IMPLEMENTATION_FEASIBILITY,
        ),
        (
            ("objection_dissent", "objection", "dissent", "contest"),
            ParticipationClaimPurpose.OBJECTION_DISSENT,
        ),
        (
            ("participation_context", "context-only", "context_only"),
            ParticipationClaimPurpose.CONTEXT,
        ),
    )
    for needles, purpose in mapping:
        if any(needle in token for needle in needles):
            return purpose
    return None


def _requested_use(
    claim: Mapping[str, Any],
    purpose: ParticipationClaimPurpose,
) -> ParticipationClaimUse:
    raw = _optional_text(
        claim.get("claim_use_requested")
        or claim.get("requested_claim_use")
        or claim.get("participation_claim_use")
    )
    if raw:
        normalized = raw.replace("_", "-")
        for value in ParticipationClaimUse:
            if value.value == normalized:
                return value
    if purpose is ParticipationClaimPurpose.PREFERENCE:
        return ParticipationClaimUse.PREVALENCE
    if purpose in {
        ParticipationClaimPurpose.ACCEPTABILITY,
        ParticipationClaimPurpose.LEGITIMACY,
        ParticipationClaimPurpose.PROCEDURAL_FAIRNESS,
    }:
        return ParticipationClaimUse.QUALITATIVE
    if purpose is ParticipationClaimPurpose.IMPLEMENTATION_FEASIBILITY:
        return ParticipationClaimUse.ROLE_FEASIBILITY
    if purpose is ParticipationClaimPurpose.OBJECTION_DISSENT:
        return ParticipationClaimUse.DISSENT
    if purpose is ParticipationClaimPurpose.LIVED_EXPERIENCE:
        return ParticipationClaimUse.EXISTENCE
    return ParticipationClaimUse.CONTEXT_ONLY


def _authority_level(claim: Mapping[str, Any]) -> ParticipationAuthorityLevel:
    raw = _optional_text(claim.get("authority_level") or claim.get("requested_authority_level"))
    try:
        return ParticipationAuthorityLevel((raw or "governed").casefold())
    except ValueError:
        return ParticipationAuthorityLevel.GOVERNED


def _population_scope(claim: Mapping[str, Any]) -> ParticipationPopulationScope:
    raw = _optional_text(claim.get("population_scope") or claim.get("audience_scope"))
    normalized = (raw or "affected_population").casefold().replace("-", "_")
    try:
        return ParticipationPopulationScope(normalized)
    except ValueError:
        return ParticipationPopulationScope.AFFECTED_POPULATION


def _matrix_row(
    *,
    purpose: ParticipationClaimPurpose,
    requested: ParticipationClaimUse,
) -> dict[str, Any]:
    if requested is ParticipationClaimUse.PREVALENCE:
        return {
            "required_modes": (ParticipationSourceKind.SURVEY,),
            "required_sampling_frame": "scope_matched_sampling_frame",
            "minimum_provenance_class": ParticipationProvenanceClass.A_REPRESENTATIVE_POPULATION,
            "minimum_representativeness_class": ParticipationRepresentativenessClass.REPRESENTATIVE,
            "consent_redaction": "public_aggregate_with_reidentification_controls",
            "dissent_handling": "report_distribution_and_unresolved_dissent",
            "sponsor_disclosure": "sponsor_required",
            "process_evidence_requirements": (
                "survey_population_scope",
                "sampling_or_recruitment_frame",
                "weighting_or_model_validation",
                "limitations",
            ),
        }
    if requested is ParticipationClaimUse.ROLE_FEASIBILITY:
        return {
            "required_modes": (
                ParticipationSourceKind.EXPERT_INTERVIEW,
                ParticipationSourceKind.HEARING,
                ParticipationSourceKind.TESTIMONY,
            ),
            "required_sampling_frame": "role_matched_source_context",
            "minimum_provenance_class": (
                ParticipationProvenanceClass.C_ATTRIBUTABLE_NONREPRESENTATIVE
            ),
            "minimum_representativeness_class": (
                ParticipationRepresentativenessClass.ATTRIBUTABLE_NONREPRESENTATIVE
            ),
            "consent_redaction": "role_safe_attribution_or_redaction",
            "dissent_handling": "record_if_present",
            "sponsor_disclosure": "sponsor_required",
            "process_evidence_requirements": ("role_mapping", "limitations"),
        }
    if requested is ParticipationClaimUse.DISSENT:
        return {
            "required_modes": (
                ParticipationSourceKind.HEARING,
                ParticipationSourceKind.COMPLAINT,
                ParticipationSourceKind.TESTIMONY,
            ),
            "required_sampling_frame": "attributable_source_context",
            "minimum_provenance_class": (
                ParticipationProvenanceClass.C_ATTRIBUTABLE_NONREPRESENTATIVE
            ),
            "minimum_representativeness_class": (
                ParticipationRepresentativenessClass.ATTRIBUTABLE_NONREPRESENTATIVE
            ),
            "consent_redaction": "safe_dissent_projection_required",
            "dissent_handling": "first_class_contestation",
            "sponsor_disclosure": "sponsor_required_if_process_hosted",
            "process_evidence_requirements": ("dissent_log", "response_trace"),
        }
    if purpose in {
        ParticipationClaimPurpose.LEGITIMACY,
        ParticipationClaimPurpose.PROCEDURAL_FAIRNESS,
        ParticipationClaimPurpose.ACCEPTABILITY,
    }:
        return {
            "required_modes": (
                ParticipationSourceKind.DELIBERATIVE_PANEL,
                ParticipationSourceKind.HEARING,
                ParticipationSourceKind.CONSULTATION,
            ),
            "required_sampling_frame": "affected_group_process_frame",
            "minimum_provenance_class": (
                ParticipationProvenanceClass.B_STRUCTURED_DELIBERATIVE_OR_PROCESS
            ),
            "minimum_representativeness_class": (
                ParticipationRepresentativenessClass.STRUCTURED_SUBGROUP_OR_ROLE
            ),
            "consent_redaction": "process_safe_public_summary",
            "dissent_handling": "preserve_unresolved_dissent",
            "sponsor_disclosure": "sponsor_and_facilitation_required",
            "process_evidence_requirements": (
                "affected_group_map",
                "invited_and_missing_groups",
                "timing_before_policy_lock_in",
                "response_to_comment",
                "dissent_log",
                "limitations",
            ),
        }
    return {
        "required_modes": (
            ParticipationSourceKind.TESTIMONY,
            ParticipationSourceKind.COMPLAINT,
            ParticipationSourceKind.CONSULTATION,
        ),
        "required_sampling_frame": "attributable_source_context",
        "minimum_provenance_class": (
            ParticipationProvenanceClass.C_ATTRIBUTABLE_NONREPRESENTATIVE
        ),
        "minimum_representativeness_class": (
            ParticipationRepresentativenessClass.ATTRIBUTABLE_NONREPRESENTATIVE
        ),
        "consent_redaction": "consent_or_public_safe_redaction_required",
        "dissent_handling": "record_if_present",
        "sponsor_disclosure": "sponsor_required_if_process_hosted",
        "process_evidence_requirements": ("attribution", "limitations"),
    }


def _select_record(
    spec: ParticipationProvenanceRequirementSpec,
    records: Sequence[ParticipationProvenanceRecord],
) -> ParticipationProvenanceRecord | None:
    for record in records:
        if spec.claim_id in record.claim_refs:
            return record
    return records[0] if records else None


def _records_from_capability_bindings(
    spec: ParticipationProvenanceRequirementSpec,
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> list[ParticipationProvenanceRecord]:
    records: list[ParticipationProvenanceRecord] = []
    for raw in capability_bindings:
        binding = _payload(raw)
        if not _participation_capability(binding):
            continue
        if not _capability_matches_requirement(spec, binding):
            continue
        metadata = _mapping(binding.get("metadata"))
        consent = _mapping(metadata.get("consent_envelope"))
        capability_ref = _optional_text(
            binding.get("selected_capability_ref") or binding.get("capability_ref")
        )
        source_limitations = _text_tuple(
            metadata.get("source_limitations") or consent.get("source_limitations")
        )
        records.append(
            ParticipationProvenanceRecord(
                participation_ref=capability_ref
                or _required_text(metadata.get("participation_ref") or spec.requirement_id),
                claim_refs=(spec.claim_id,),
                source_kind=_participation_source_kind(metadata.get("source_kind")),
                consultation_mode=_optional_text(metadata.get("consultation_mode")),
                provenance_class=_participation_provenance_class(
                    metadata.get("provenance_class")
                ),
                representativeness_class=_participation_representativeness_class(
                    metadata.get("representativeness_class")
                ),
                sampling_or_recruitment_frame=_optional_text(
                    metadata.get("sampling_or_recruitment_frame")
                ),
                affected_group_map=_mapping(metadata.get("affected_group_map")),
                consent_redaction_state=_required_text(
                    consent.get("consent_redaction_state")
                    or metadata.get("consent_redaction_state")
                    or spec.consent_redaction
                ),
                dissent_state=_required_text(
                    metadata.get("dissent_state") or "not_recorded"
                ),
                sponsor_disclosure=_optional_text(metadata.get("sponsor_disclosure")),
                limitations=tuple(
                    dict.fromkeys(
                        [
                            *_text_tuple(binding.get("limitations")),
                            *source_limitations,
                        ]
                    )
                ),
                evidence_ref=_optional_text(metadata.get("evidence_ref")) or capability_ref,
                raw_material_ref=_optional_text(metadata.get("raw_material_ref")),
                capability_ref=capability_ref,
                construct_ref=_optional_text(binding.get("construct_ref")),
                capability_index_ref=_optional_text(binding.get("capability_index_ref")),
                construct_registry_ref=_optional_text(binding.get("construct_registry_ref")),
                authority_composition_rule_ref=_optional_text(
                    binding.get("authority_composition_rule_ref")
                    or binding.get("rule_version_ref")
                ),
                consent_envelope=consent,
                source_limitations=source_limitations,
                metadata=metadata,
            )
        )
    return records


def _participation_capability(binding: Mapping[str, Any]) -> bool:
    modalities = {item.casefold() for item in _text_tuple(binding.get("modality"))}
    mode = _optional_text(binding.get("evidence_mode")) or ""
    if modalities.intersection(
        {"participation_provenance", "civic_legitimacy_signal", "value_choice_provenance"}
    ):
        return True
    return mode == "participation_attestation"


def _capability_matches_requirement(
    spec: ParticipationProvenanceRequirementSpec,
    binding: Mapping[str, Any],
) -> bool:
    requirement_id = _optional_text(binding.get("requirement_id"))
    if requirement_id == spec.requirement_id:
        return True
    target_claim_ids = set(_text_tuple(binding.get("target_claim_ids")))
    if spec.claim_id in target_claim_ids:
        return True
    construct = (_optional_text(binding.get("construct_ref")) or "").removeprefix(
        "construct:"
    )
    if not construct:
        return False
    return construct in {
        "participation_provenance",
        "civic_legitimacy_signal",
        "value_choice_provenance",
    }


def _participation_source_kind(value: object) -> ParticipationSourceKind:
    raw = (_optional_text(value) or "consultation").casefold().replace("-", "_")
    try:
        return ParticipationSourceKind(raw)
    except ValueError:
        return ParticipationSourceKind.CONSULTATION


def _participation_provenance_class(value: object) -> ParticipationProvenanceClass:
    raw = _optional_text(value) or ParticipationProvenanceClass.B_STRUCTURED_DELIBERATIVE_OR_PROCESS
    try:
        return ParticipationProvenanceClass(raw)
    except ValueError:
        return ParticipationProvenanceClass.B_STRUCTURED_DELIBERATIVE_OR_PROCESS


def _participation_representativeness_class(
    value: object,
) -> ParticipationRepresentativenessClass:
    raw = (
        _optional_text(value)
        or ParticipationRepresentativenessClass.STRUCTURED_SUBGROUP_OR_ROLE
    )
    try:
        return ParticipationRepresentativenessClass(raw)
    except ValueError:
        return ParticipationRepresentativenessClass.STRUCTURED_SUBGROUP_OR_ROLE


def _allowed_use_for_record(
    record: ParticipationProvenanceRecord,
    spec: ParticipationProvenanceRequirementSpec,
) -> ParticipationClaimUse:
    if record.source_kind is ParticipationSourceKind.SURVEY:
        if (
            record.provenance_class
            is ParticipationProvenanceClass.A_REPRESENTATIVE_POPULATION
            and record.representativeness_class
            in {
                ParticipationRepresentativenessClass.REPRESENTATIVE,
                ParticipationRepresentativenessClass.MODELED_REPRESENTATIVE,
            }
            and bool(record.sampling_or_recruitment_frame)
        ):
            return ParticipationClaimUse.PREVALENCE
        return ParticipationClaimUse.QUALITATIVE
    if record.source_kind is ParticipationSourceKind.EXPERT_INTERVIEW:
        return ParticipationClaimUse.ROLE_FEASIBILITY
    if record.source_kind in {
        ParticipationSourceKind.DELIBERATIVE_PANEL,
        ParticipationSourceKind.CONSULTATION,
        ParticipationSourceKind.HEARING,
    }:
        if spec.claim_use_requested is ParticipationClaimUse.PREVALENCE:
            return ParticipationClaimUse.QUALITATIVE
        if (
            record.provenance_class
            in {
                ParticipationProvenanceClass.B_STRUCTURED_DELIBERATIVE_OR_PROCESS,
                ParticipationProvenanceClass.C_ATTRIBUTABLE_NONREPRESENTATIVE,
            }
            and record.affected_group_map
        ):
            return ParticipationClaimUse.QUALITATIVE
        return ParticipationClaimUse.CONTEXT_ONLY
    if record.source_kind in {
        ParticipationSourceKind.COMPLAINT,
        ParticipationSourceKind.ADMINISTRATIVE_COMPLAINT,
        ParticipationSourceKind.CIVIL_SOCIETY_SUBMISSION,
        ParticipationSourceKind.TESTIMONY,
    }:
        if spec.claim_use_requested is ParticipationClaimUse.DISSENT:
            return ParticipationClaimUse.DISSENT
        return ParticipationClaimUse.EXISTENCE
    return ParticipationClaimUse.CONTEXT_ONLY


def _downgrade_reason(
    spec: ParticipationProvenanceRequirementSpec,
    record: ParticipationProvenanceRecord,
    allowed: ParticipationClaimUse,
) -> str:
    if spec.claim_use_requested is ParticipationClaimUse.PREVALENCE and (
        record.representativeness_class
        not in {
            ParticipationRepresentativenessClass.REPRESENTATIVE,
            ParticipationRepresentativenessClass.MODELED_REPRESENTATIVE,
        }
    ):
        return "nonrepresentative_for_claim_scope"
    if not record.sampling_or_recruitment_frame and spec.claim_use_requested is (
        ParticipationClaimUse.PREVALENCE
    ):
        return "summary_without_underlying_method"
    if allowed is ParticipationClaimUse.CONTEXT_ONLY:
        return "participation_provenance_insufficient"
    return "claim_use_ceiling_exceeded"


def _closeout_effect(
    *,
    status: str,
    blocker_code: str | None,
) -> str:
    if status == "satisfied":
        return "unaffected"
    if status == "downgraded":
        return "limited_closeout"
    if blocker_code in {"participation_provenance_missing", "llm_speculation_not_participation"}:
        return "affected_claim_blocked"
    return "limited_closeout"


def _use_rank(value: ParticipationClaimUse) -> int:
    return {
        ParticipationClaimUse.CONTEXT_ONLY: 0,
        ParticipationClaimUse.EXISTENCE: 1,
        ParticipationClaimUse.DISSENT: 1,
        ParticipationClaimUse.QUALITATIVE: 2,
        ParticipationClaimUse.ROLE_FEASIBILITY: 2,
        ParticipationClaimUse.PREVALENCE: 3,
    }[value]


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, Iterable):
        values = value
    else:
        values = (value,)
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _optional_text(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _payload(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("required text value is missing")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{_digest({'parts': parts})[:16]}"


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


__all__ = [
    "PARTICIPATION_EVALUATION_SCHEMA_VERSION",
    "PARTICIPATION_REQUIREMENT_BUNDLE_SCHEMA_VERSION",
    "PARTICIPATION_REQUIREMENT_SPEC_SCHEMA_VERSION",
    "ParticipationAuthorityBoundary",
    "ParticipationAuthorityLevel",
    "ParticipationClaimPurpose",
    "ParticipationClaimUse",
    "ParticipationDeficitRecord",
    "ParticipationPopulationScope",
    "ParticipationProvenanceClass",
    "ParticipationProvenanceCompiler",
    "ParticipationProvenanceRecord",
    "ParticipationProvenanceRequirementSpec",
    "ParticipationPublicProjectionRow",
    "ParticipationRepresentativenessClass",
    "ParticipationRepresentativenessConfig",
    "ParticipationRequirementBundle",
    "ParticipationRequirementEvaluation",
    "ParticipationSourceKind",
    "compile_participation_requirements",
    "evaluate_participation_requirement",
    "participation_requirement_bundle_audit_surface",
    "write_participation_requirement_bundle",
]
