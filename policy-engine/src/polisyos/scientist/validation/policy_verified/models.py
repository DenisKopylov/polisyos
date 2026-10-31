"""Public policy verified models module API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from polisyos.core.artifacts import (
    ArtifactStore,
    CoreArtifactOwnerProfile,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.scientist import (
    LegalCandidatePackRef,
    LegalSourcePackRef,
    PolicyOptionSetRef,
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
    VerifiedPolicyReportRef,
)
from polisyos.ir.analytics.cross_graph import EvidenceSourceStatus
from polisyos.lex.knowledge.types import LegalFactResult, LegalProvisionResult, LegalSourceBundle
from polisyos.scientist.evidence.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSourceClass,
    ClaimSupportStatus,
    ClaimType,
    ClaimUse,
)
from polisyos.scientist.evidence.decision_readiness import DecisionReadiness


class PolicyRequestFrame(BaseModel):
    """Policy request frame public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    policy_question: str
    jurisdiction: str = ""
    jurisdiction_source: Literal["policy_request_jurisdiction", "jurisdiction"] | None = None
    as_of: str | None = None
    policy_domain: str | None = None
    target_context: dict[str, Any] = Field(default_factory=dict)
    evaluation_criteria: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _serialize_legacy_request(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.schema_version == "1.0":
            payload.pop("jurisdiction_source", None)
        return payload


class LegalRetrievalStatus(BaseModel):
    """One route's observed legal retrieval outcome for one query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=1)
    route: Literal["hybrid_facts", "constraints", "provisions"]
    search_mode: Literal["text", "vector", "structured"] | None = None
    vector_refusal_code: str | None = None
    limitation_code: str | None = None

    @model_validator(mode="after")
    def _validate_retrieval_outcome(self) -> LegalRetrievalStatus:
        """Keep vector admission, fallback, and unavailable outcomes distinct."""
        if self.search_mode in {"vector", "structured"} and (
            self.vector_refusal_code is not None or self.limitation_code is not None
        ):
            raise ValueError("vector_legal_search_cannot_carry_refusal")
        if self.search_mode == "text" and (
            not self.vector_refusal_code or self.limitation_code is not None
        ):
            raise ValueError("text_legal_search_requires_vector_refusal")
        if self.search_mode is None and (
            not self.limitation_code or self.vector_refusal_code is not None
        ):
            raise ValueError("unavailable_legal_search_requires_limitation")
        allowed_modes = {
            "hybrid_facts": {"text", "vector", None},
            "constraints": {"structured", None},
            "provisions": {"vector", None},
        }
        if self.search_mode not in allowed_modes[self.route]:
            raise ValueError("legal_retrieval_mode_invalid_for_route")
        return self


class LegalCandidatePack(BaseModel):
    """Legal candidate pack public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    request_id: str
    queries: list[str] = Field(default_factory=list)
    fact_hits: list[LegalFactResult] = Field(default_factory=list)
    provision_hits: list[LegalProvisionResult] = Field(default_factory=list)
    hit_reasons: dict[str, str] = Field(default_factory=dict)
    source_family_hints: dict[str, str] = Field(default_factory=dict)
    anchor_coverage_hints: dict[str, list[str]] = Field(default_factory=dict)
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    legal_retrieval_status: list[LegalRetrievalStatus] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class LegalSourcePack(BaseModel):
    """Legal source pack public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    source_bundles: list[LegalSourceBundle] = Field(default_factory=list)
    unresolved_anchor_hints: list[str] = Field(default_factory=list)
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class VerifiedLegalClaim(BaseModel):
    """Verified legal claim public type."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    bundle_id: str
    doc_id: str
    version_id: str = ""
    anchor: str
    citation_label: str = ""
    claim_type: str
    claim_text: str
    quote: str
    quote_offsets: dict[str, int] | None = None
    supports_policy_option_ids: list[str] = Field(default_factory=list)
    limits_policy_option_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_additional_sources: bool = False


class SourceCoverageGap(BaseModel):
    """Source coverage gap public type."""

    model_config = ConfigDict(extra="forbid")

    gap_id: str
    category: str
    description: str
    severity: Literal["info", "warning", "critical"] = "warning"
    related_bundle_ids: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    resolved: bool = False


class SourceVerificationReport(BaseModel):
    """Audit report capturing verified claims, unresolved evidence gaps, and escalation status."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    verified_claims: list[VerifiedLegalClaim] = Field(default_factory=list)
    legal_claim_candidates: list[ClaimRecord] = Field(default_factory=list)
    legal_verification_status: Literal["not_established"] = "not_established"
    unresolved_critical_gaps: list[SourceCoverageGap] = Field(default_factory=list)
    verifier_calls_total: int = 0
    adjudicator_calls_total: int = 0
    verifier_disagreement_rate: float = 0.0
    verified_claim_citation_coverage_pct: float = 0.0
    verification_cycles_completed: int = 0
    needs_expert_review: bool = False
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _preserve_candidate_authority_boundary(self) -> SourceVerificationReport:
        if self.schema_version == "1.0" and self.legal_claim_candidates:
            raise ValueError("legacy_source_report_cannot_store_candidate_claims")
        if self.schema_version == "1.1" and self.verified_claims:
            raise ValueError("legal_claim_verification_not_established")
        for claim in self.legal_claim_candidates:
            source = claim.metadata.get("legal_source_candidate")
            if (
                claim.claim_type is not ClaimType.LEGAL
                or claim.claim_use is not ClaimUse.CONTEXT_ONLY
                or claim.support_status is not ClaimSupportStatus.NOT_EVALUABLE
                or claim.publishability is not ClaimPublishability.INTERNAL_ONLY
                or claim.readiness_level is not DecisionReadiness.RESEARCH_ARTIFACT
                or "legal_claim_verification_not_established" not in claim.blocked_reasons
                or not isinstance(source, dict)
                or source.get("source") not in {"retrieved_fact", "llm_candidate", "legacy_unbound"}
                or (claim.decomposition_source_class is ClaimSourceClass.LLM_CANDIDATE)
                != (source.get("source") == "llm_candidate")
                or claim.decomposition_source_class not in {None, ClaimSourceClass.LLM_CANDIDATE}
            ):
                raise ValueError("legal_claim_candidate_authority_invalid")
        return self

    @model_serializer(mode="wrap")
    def _serialize_legacy_report(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        if self.schema_version == "1.0" and self.legal_claim_candidates:
            raise ValueError("legacy_source_report_cannot_store_candidate_claims")
        payload: dict[str, Any] = handler(self)
        if self.schema_version == "1.0":
            payload.pop("legal_claim_candidates", None)
            payload.pop("legal_verification_status", None)
        return payload


class PolicyEvidenceLink(BaseModel):
    """Policy evidence link public type."""

    model_config = ConfigDict(extra="forbid")

    option_id: str
    claim_id: str
    relation: Literal["supports", "limits", "threshold", "timing", "exception"] = "supports"


class PolicyOption(BaseModel):
    """Policy option public type."""

    model_config = ConfigDict(extra="forbid")

    option_id: str
    title: str
    summary: str
    intervention_outline: dict[str, Any] = Field(default_factory=dict)
    legal_basis_refs: list[str] = Field(default_factory=list)
    evidence_links: list[PolicyEvidenceLink] = Field(default_factory=list)
    hypothesis_basis: bool = False
    constraints: list[str] = Field(default_factory=list)
    thresholds: list[str] = Field(default_factory=list)
    timing: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PolicyOptionSet(BaseModel):
    """Policy option set public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    verified_options: list[PolicyOption] = Field(default_factory=list)
    hypothesis_options: list[PolicyOption] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PolicyReportCompositionBinding(BaseModel):
    """Declared inputs for a limited policy composition, pending owner admission.

    These typed references do not establish a completed Engine attempt or grant
    publication authority. A consumer must revalidate the selected occurrences.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    purpose: Literal["limited_policy_composition"] = "limited_policy_composition"
    result_status: Literal["limited"] = "limited"
    requirement_authority: Literal["not_established"] = "not_established"
    publishable: Literal[False] = False
    legal_verification_status: Literal["not_established"] = "not_established"
    option_program_correspondence: Literal["not_established"] = "not_established"
    run_id: str = Field(min_length=1)
    body_ref: ArtifactRef
    candidate_ref: ArtifactRef
    phase5_assessment_ref: ArtifactRef
    initial_governance_ref: ArtifactRef
    final_governance_ref: ArtifactRef
    selected_input_ref: ArtifactRef
    selected_attempt_ref: ArtifactRef

    @field_validator("publishable", mode="before")
    @classmethod
    def _require_false_bool(cls, value: object) -> object:
        if value is not False:
            raise ValueError("policy_composition_publishability_invalid")
        return value

    @field_validator(
        "body_ref",
        "candidate_ref",
        "phase5_assessment_ref",
        "initial_governance_ref",
        "final_governance_ref",
        "selected_input_ref",
        "selected_attempt_ref",
        mode="before",
    )
    @classmethod
    def _normalize_reference_model(cls, value: object) -> object:
        if isinstance(value, ArtifactRef):
            return value.model_dump(mode="python")
        return value

    @model_validator(mode="after")
    def _require_selected_role_profiles(self) -> PolicyReportCompositionBinding:
        expected_kinds = (
            (self.body_ref, "scientist.verified_policy_body"),
            (self.candidate_ref, "scientist.policy_design.candidate"),
            (self.phase5_assessment_ref, "scientist.policy_phase5_candidate_assessment"),
            (self.initial_governance_ref, "scientist.governance_report"),
            (self.final_governance_ref, "scientist.governance_report"),
            (self.selected_input_ref, "scientist.experiment_state"),
            (self.selected_attempt_ref, "core.run_invocation_attempt"),
        )
        if any(
            ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref, kind in expected_kinds
        ):
            raise ValueError("policy_composition_selected_role_profile_invalid")
        if artifact_ref_identity_key(self.initial_governance_ref) == artifact_ref_identity_key(
            self.final_governance_ref
        ):
            raise ValueError("policy_composition_governance_occurrences_not_distinct")
        return self


class VerifiedPolicyReport(BaseModel):
    """Policy report content, with an optional limited-composition declaration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executive_summary: str
    verified_legal_basis: list[VerifiedLegalClaim] = Field(default_factory=list)
    policy_options: list[PolicyOption] = Field(default_factory=list)
    constraints_and_timing: list[str] = Field(default_factory=list)
    simulation_and_causal_implications: list[str] = Field(default_factory=list)
    verified_findings: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    unresolved_critical_gaps: list[SourceCoverageGap] = Field(default_factory=list)
    citation_appendix: list[str] = Field(default_factory=list)
    intervention_legal_basis_map: dict[str, list[str]] = Field(default_factory=dict)
    needs_expert_review: bool = False
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    composition: PolicyReportCompositionBinding | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _validate_composition_version(self) -> VerifiedPolicyReport:
        if (self.schema_version, self.composition is None) not in {
            ("1.0", True),
            ("1.1", False),
        }:
            raise ValueError("policy_report_composition_schema_mismatch")
        if self.composition is not None and (
            self.verified_legal_basis
            or self.intervention_legal_basis_map
            or not self.needs_expert_review
        ):
            raise ValueError("limited_policy_report_legal_authority_not_established")
        return self


_POLICY_REQUEST_FRAME_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.policy_request_frame",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name="polisyos.scientist.PolicyRequestFrame", version="1.0"),
        SchemaInfo(name="polisyos.scientist.PolicyRequestFrame", version="1.1"),
    ),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.PolicyRequestFrame", "1.0"), "1.0"),
        (("polisyos.scientist.PolicyRequestFrame", "1.1"), "1.1"),
    ),
)
_POLICY_OPTION_SET_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.policy_option_set",
    media_type="application/json",
    schema_variants=(SchemaInfo(name="polisyos.scientist.PolicyOptionSet", version="1.0"),),
    payload_schema_version_by_manifest=((("polisyos.scientist.PolicyOptionSet", "1.0"), "1.0"),),
)
_LEGAL_CANDIDATE_PACK_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.legal_candidate_pack",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name="polisyos.scientist.LegalCandidatePack", version="1.0"),
        SchemaInfo(name="polisyos.scientist.LegalCandidatePack", version="1.1"),
    ),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.LegalCandidatePack", "1.0"), "1.0"),
        (("polisyos.scientist.LegalCandidatePack", "1.1"), "1.1"),
    ),
)
_LEGAL_SOURCE_PACK_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.legal_source_pack",
    media_type="application/json",
    schema_variants=(SchemaInfo(name="polisyos.scientist.LegalSourcePack", version="1.0"),),
    payload_schema_version_by_manifest=((("polisyos.scientist.LegalSourcePack", "1.0"), "1.0"),),
)
_SOURCE_VERIFICATION_REPORT_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.source_verification_report",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name="polisyos.scientist.SourceVerificationReport", version="1.0"),
        SchemaInfo(name="polisyos.scientist.SourceVerificationReport", version="1.1"),
    ),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.SourceVerificationReport", "1.0"), "1.0"),
        (("polisyos.scientist.SourceVerificationReport", "1.1"), "1.1"),
    ),
)
_VERIFIED_POLICY_BODY_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.verified_policy_body",
    media_type="application/json",
    schema_variants=(SchemaInfo(name="polisyos.scientist.VerifiedPolicyReport", version="1.0"),),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.VerifiedPolicyReport", "1.0"), "1.0"),
    ),
)
_VERIFIED_POLICY_REPORT_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.verified_policy_report",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name="polisyos.scientist.VerifiedPolicyReport", version="1.0"),
        SchemaInfo(name="polisyos.scientist.VerifiedPolicyReport", version="1.1"),
    ),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.VerifiedPolicyReport", "1.0"), "1.0"),
        (("polisyos.scientist.VerifiedPolicyReport", "1.1"), "1.1"),
    ),
)


def _persist_model(
    store: ArtifactStore,
    model: BaseModel,
    *,
    kind: str,
    schema_name: str,
    inputs: list[InputRef] | None = None,
    owner_profile: CoreArtifactOwnerProfile | None = None,
    canon_spec: CanonSpec | None = None,
) -> dict[str, Any]:
    payload_schema_version = getattr(model, "schema_version", "1.0")
    if owner_profile is None:
        schema_version = str(payload_schema_version)
        return_selected_profile = False
    else:
        if (
            kind != owner_profile.kind
            or owner_profile.media_type != "application/json"
            or type(payload_schema_version) is not str
        ):
            raise ValueError("core_artifact_owner_profile_writer_mismatch")
        schema = SchemaInfo(name=schema_name, version=payload_schema_version)
        schema_variants = owner_profile.schema_variants
        payload_version_rules = owner_profile.payload_schema_version_by_manifest
        if (
            type(schema_variants) is not tuple
            or schema not in schema_variants
            or type(payload_version_rules) is not tuple
            or dict(payload_version_rules).get((schema_name, payload_schema_version))
            != payload_schema_version
        ):
            raise ValueError("core_artifact_owner_payload_version_mismatch")
        schema_version = payload_schema_version
        return_selected_profile = True

    artifact = store.put_json(
        model,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs,
        ),
        canon_spec=canon_spec or CanonSpec(forbid_floats=False),
        return_selected_profile=return_selected_profile,
    )
    return artifact.model_dump()


def _load_owned_model[ModelT: BaseModel](
    model: type[ModelT],
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    owner_profile: CoreArtifactOwnerProfile,
) -> ModelT:
    """Load a strict model only from a selected Core view matching its owner ABI."""
    return validate_owned_core_model_json_artifact(
        model,
        store,
        ref,
        expected_owner=owner_profile,
    ).value


def persist_policy_request_frame(
    store: ArtifactStore,
    frame: PolicyRequestFrame,
    *,
    inputs: list[InputRef] | None = None,
) -> PolicyRequestFrameRef:
    """Persist the normalized policy request frame and return its typed artifact reference."""
    return PolicyRequestFrameRef.model_validate(
        _persist_model(
            store,
            frame,
            kind="scientist.policy_request_frame",
            schema_name="polisyos.scientist.PolicyRequestFrame",
            inputs=inputs,
            owner_profile=_POLICY_REQUEST_FRAME_OWNER,
        )
    )


def load_policy_request_frame(
    store: ArtifactStore, ref: PolicyRequestFrameRef
) -> PolicyRequestFrame:
    """Load policy request frame."""
    return _load_owned_model(
        PolicyRequestFrame,
        store,
        ref,
        owner_profile=_POLICY_REQUEST_FRAME_OWNER,
    )


def persist_legal_candidate_pack(
    store: ArtifactStore,
    pack: LegalCandidatePack,
    *,
    inputs: list[InputRef] | None = None,
) -> LegalCandidatePackRef:
    """Persist the candidate source-query pack produced during legal retrieval planning."""
    return LegalCandidatePackRef.model_validate(
        _persist_model(
            store,
            pack,
            kind="scientist.legal_candidate_pack",
            schema_name="polisyos.scientist.LegalCandidatePack",
            inputs=inputs,
            owner_profile=_LEGAL_CANDIDATE_PACK_OWNER,
        )
    )


def load_legal_candidate_pack(
    store: ArtifactStore, ref: LegalCandidatePackRef
) -> LegalCandidatePack:
    """Load legal candidate pack."""
    return _load_owned_model(
        LegalCandidatePack,
        store,
        ref,
        owner_profile=_LEGAL_CANDIDATE_PACK_OWNER,
    )


def persist_legal_source_pack(
    store: ArtifactStore,
    pack: LegalSourcePack,
    *,
    inputs: list[InputRef] | None = None,
) -> LegalSourcePackRef:
    """Persist the expanded legal source bundle gathered for verification and drafting."""
    return LegalSourcePackRef.model_validate(
        _persist_model(
            store,
            pack,
            kind="scientist.legal_source_pack",
            schema_name="polisyos.scientist.LegalSourcePack",
            inputs=inputs,
            owner_profile=_LEGAL_SOURCE_PACK_OWNER,
        )
    )


def load_legal_source_pack(store: ArtifactStore, ref: LegalSourcePackRef) -> LegalSourcePack:
    """Load legal source pack."""
    return _load_owned_model(
        LegalSourcePack,
        store,
        ref,
        owner_profile=_LEGAL_SOURCE_PACK_OWNER,
    )


def persist_source_verification_report(
    store: ArtifactStore,
    report: SourceVerificationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> SourceVerificationReportRef:
    """Persist the source-verification audit report and return its typed artifact reference."""
    report = SourceVerificationReport.model_validate(
        {name: getattr(report, name) for name in SourceVerificationReport.model_fields}
    )
    return SourceVerificationReportRef.model_validate(
        _persist_model(
            store,
            report,
            kind="scientist.source_verification_report",
            schema_name="polisyos.scientist.SourceVerificationReport",
            inputs=inputs,
            owner_profile=_SOURCE_VERIFICATION_REPORT_OWNER,
            canon_spec=(
                CanonSpec(forbid_floats=False, exclude_none=False)
                if report.schema_version == "1.1"
                else None
            ),
        )
    )


def load_source_verification_report(
    store: ArtifactStore,
    ref: SourceVerificationReportRef,
) -> SourceVerificationReport:
    """Load source verification report."""
    return _load_owned_model(
        SourceVerificationReport,
        store,
        ref,
        owner_profile=_SOURCE_VERIFICATION_REPORT_OWNER,
    )


def persist_policy_option_set(
    store: ArtifactStore,
    option_set: PolicyOptionSet,
    *,
    inputs: list[InputRef] | None = None,
) -> PolicyOptionSetRef:
    """Persist the verified and hypothesis-backed policy option set for downstream stages."""
    return PolicyOptionSetRef.model_validate(
        _persist_model(
            store,
            option_set,
            kind="scientist.policy_option_set",
            schema_name="polisyos.scientist.PolicyOptionSet",
            inputs=inputs,
            owner_profile=_POLICY_OPTION_SET_OWNER,
        )
    )


def load_policy_option_set(store: ArtifactStore, ref: PolicyOptionSetRef) -> PolicyOptionSet:
    """Load policy option set."""
    return _load_owned_model(
        PolicyOptionSet,
        store,
        ref,
        owner_profile=_POLICY_OPTION_SET_OWNER,
    )


def persist_verified_policy_body(
    store: ArtifactStore,
    report: VerifiedPolicyReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist an internal candidate body without granting publication authority."""
    return ArtifactRef.model_validate(
        _persist_model(
            store,
            report,
            kind="scientist.verified_policy_body",
            schema_name="polisyos.scientist.VerifiedPolicyReport",
            inputs=inputs,
            owner_profile=_VERIFIED_POLICY_BODY_OWNER,
        )
    )


def load_verified_policy_body(store: ArtifactStore, ref: ArtifactRef) -> VerifiedPolicyReport:
    """Read the selected candidate-body owner profile; this does not admit authority."""
    return _load_owned_model(
        VerifiedPolicyReport,
        store,
        ref,
        owner_profile=_VERIFIED_POLICY_BODY_OWNER,
    )


def _policy_composition_inputs(binding: PolicyReportCompositionBinding) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("verified_body", binding.body_ref),
            ("policy_candidate", binding.candidate_ref),
            ("phase5_candidate_assessment", binding.phase5_assessment_ref),
            ("initial_governance_assessment", binding.initial_governance_ref),
            ("final_governance_report", binding.final_governance_ref),
            ("selected_input", binding.selected_input_ref),
            ("selected_attempt", binding.selected_attempt_ref),
        )
    ]


def _compose_limited_policy_report(
    body: VerifiedPolicyReport, binding: PolicyReportCompositionBinding
) -> VerifiedPolicyReport:
    """Copy candidate body content into the limited report wire format."""
    if body.schema_version != "1.0" or body.composition is not None:
        raise ValueError("policy_composition_body_version_invalid")
    payload = body.model_dump(mode="python")
    missing_evidence = list(body.missing_evidence)
    for limitation in (
        "Applicable requirement authority is not established.",
        "Independent legal claim verification is not established.",
        "The selected policy option has not been matched to the final program.",
    ):
        if limitation not in missing_evidence:
            missing_evidence.append(limitation)
    payload["missing_evidence"] = missing_evidence
    payload.update(schema_version="1.1", composition=binding.model_dump(mode="python"))
    return VerifiedPolicyReport.model_validate(payload)


def _require_composition_body_content(store: ArtifactStore, report: VerifiedPolicyReport) -> None:
    """Recompute report content from its selected body; this is not attempt admission."""
    binding = report.composition
    if binding is None:
        raise ValueError("policy_composition_binding_missing")
    body = load_verified_policy_body(store, binding.body_ref)
    expected = _compose_limited_policy_report(body, binding)
    canon = CanonSpec(forbid_floats=False, exclude_none=False)
    if to_canonical_bytes(expected.model_dump(mode="json"), canon) != to_canonical_bytes(
        report.model_dump(mode="json"), canon
    ):
        raise ValueError("policy_composition_body_content_mismatch")


def persist_verified_policy_report(
    store: ArtifactStore,
    report: VerifiedPolicyReport,
    *,
    inputs: list[InputRef] | None = None,
) -> VerifiedPolicyReportRef:
    """Persist report content; a composition declaration still requires owner admission."""
    if report.schema_version != "1.0" or report.composition is not None:
        # Revalidate mutable/model_copy callers before writing a new wire version.
        report = VerifiedPolicyReport.model_validate(report.model_dump(mode="python"))
        assert report.composition is not None
        expected_inputs = _policy_composition_inputs(report.composition)
        if inputs is not None and inputs != expected_inputs:
            raise ValueError("policy_composition_source_edges_mismatch")
        _require_composition_body_content(store, report)
        inputs = expected_inputs
    return VerifiedPolicyReportRef.model_validate(
        _persist_model(
            store,
            report,
            kind="scientist.verified_policy_report",
            schema_name="polisyos.scientist.VerifiedPolicyReport",
            inputs=inputs,
            owner_profile=_VERIFIED_POLICY_REPORT_OWNER,
        )
    )


def load_verified_policy_report(
    store: ArtifactStore,
    ref: VerifiedPolicyReportRef,
) -> VerifiedPolicyReport:
    """Read the owner profile and exact declared edges, without granting authority."""
    report = _load_owned_model(
        VerifiedPolicyReport,
        store,
        ref,
        owner_profile=_VERIFIED_POLICY_REPORT_OWNER,
    )
    if report.composition is not None:
        if ref.manifest_profile_sha256 is None:
            raise ValueError("policy_composition_selected_profile_not_established")
        if store.get_manifest(ref).inputs != _policy_composition_inputs(report.composition):
            raise ValueError("policy_composition_source_edges_mismatch")
        _require_composition_body_content(store, report)
    return report


__all__ = [
    "LegalCandidatePack",
    "LegalSourcePack",
    "PolicyEvidenceLink",
    "PolicyReportCompositionBinding",
    "PolicyOption",
    "PolicyOptionSet",
    "PolicyRequestFrame",
    "SourceCoverageGap",
    "SourceVerificationReport",
    "VerifiedLegalClaim",
    "VerifiedPolicyReport",
    "load_legal_candidate_pack",
    "load_legal_source_pack",
    "load_policy_option_set",
    "load_policy_request_frame",
    "load_source_verification_report",
    "load_verified_policy_body",
    "load_verified_policy_report",
    "persist_legal_candidate_pack",
    "persist_legal_source_pack",
    "persist_policy_option_set",
    "persist_policy_request_frame",
    "persist_source_verification_report",
    "persist_verified_policy_body",
    "persist_verified_policy_report",
]
