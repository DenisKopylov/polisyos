"""Public policy verified models module API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    CoreArtifactOwnerProfile,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
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


class PolicyRequestFrame(BaseModel):
    """Policy request frame public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    policy_question: str
    jurisdiction: str = "UA"
    as_of: str | None = None
    policy_domain: str | None = None
    target_context: dict[str, Any] = Field(default_factory=dict)
    evaluation_criteria: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


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
    unresolved_critical_gaps: list[SourceCoverageGap] = Field(default_factory=list)
    verifier_calls_total: int = 0
    adjudicator_calls_total: int = 0
    verifier_disagreement_rate: float = 0.0
    verified_claim_citation_coverage_pct: float = 0.0
    verification_cycles_completed: int = 0
    needs_expert_review: bool = False
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


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


class VerifiedPolicyReport(BaseModel):
    """Delivery-ready policy report combining verified legal basis, options, implications, and gaps."""

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
_SOURCE_VERIFICATION_REPORT_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.source_verification_report",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name="polisyos.scientist.SourceVerificationReport", version="1.0"),
    ),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.SourceVerificationReport", "1.0"), "1.0"),
    ),
)
_VERIFIED_POLICY_REPORT_OWNER = CoreArtifactOwnerProfile(
    kind="scientist.verified_policy_report",
    media_type="application/json",
    schema_variants=(SchemaInfo(name="polisyos.scientist.VerifiedPolicyReport", version="1.0"),),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.VerifiedPolicyReport", "1.0"), "1.0"),
    ),
)


def _persist_model(
    store: FileSystemCAS,
    model: BaseModel,
    *,
    kind: str,
    schema_name: str,
    inputs: list[InputRef] | None = None,
    owner_profile: CoreArtifactOwnerProfile | None = None,
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
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=return_selected_profile,
    )
    return artifact.model_dump()


def _load_owned_model[ModelT: BaseModel](
    model: type[ModelT],
    store: FileSystemCAS,
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
    store: FileSystemCAS,
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
        )
    )


def load_policy_request_frame(
    store: FileSystemCAS, ref: PolicyRequestFrameRef
) -> PolicyRequestFrame:
    """Load policy request frame."""
    from polisyos.core.artifacts import load_core_json_artifact

    return PolicyRequestFrame.model_validate(load_core_json_artifact(store, ref))


def persist_legal_candidate_pack(
    store: FileSystemCAS,
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
    store: FileSystemCAS, ref: LegalCandidatePackRef
) -> LegalCandidatePack:
    """Load legal candidate pack."""
    return _load_owned_model(
        LegalCandidatePack,
        store,
        ref,
        owner_profile=_LEGAL_CANDIDATE_PACK_OWNER,
    )


def persist_legal_source_pack(
    store: FileSystemCAS,
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
        )
    )


def load_legal_source_pack(store: FileSystemCAS, ref: LegalSourcePackRef) -> LegalSourcePack:
    """Load legal source pack."""
    from polisyos.core.artifacts import load_core_json_artifact

    return LegalSourcePack.model_validate(load_core_json_artifact(store, ref))


def persist_source_verification_report(
    store: FileSystemCAS,
    report: SourceVerificationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> SourceVerificationReportRef:
    """Persist the source-verification audit report and return its typed artifact reference."""
    return SourceVerificationReportRef.model_validate(
        _persist_model(
            store,
            report,
            kind="scientist.source_verification_report",
            schema_name="polisyos.scientist.SourceVerificationReport",
            inputs=inputs,
            owner_profile=_SOURCE_VERIFICATION_REPORT_OWNER,
        )
    )


def load_source_verification_report(
    store: FileSystemCAS,
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
    store: FileSystemCAS,
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
        )
    )


def load_policy_option_set(store: FileSystemCAS, ref: PolicyOptionSetRef) -> PolicyOptionSet:
    """Load policy option set."""
    from polisyos.core.artifacts import load_core_json_artifact

    return PolicyOptionSet.model_validate(load_core_json_artifact(store, ref))


def persist_verified_policy_report(
    store: FileSystemCAS,
    report: VerifiedPolicyReport,
    *,
    inputs: list[InputRef] | None = None,
) -> VerifiedPolicyReportRef:
    """Persist the final verified policy report assembled for delivery or governance review."""
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
    store: FileSystemCAS,
    ref: VerifiedPolicyReportRef,
) -> VerifiedPolicyReport:
    """Load verified policy report."""
    return _load_owned_model(
        VerifiedPolicyReport,
        store,
        ref,
        owner_profile=_VERIFIED_POLICY_REPORT_OWNER,
    )


__all__ = [
    "LegalCandidatePack",
    "LegalSourcePack",
    "PolicyEvidenceLink",
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
    "load_verified_policy_report",
    "persist_legal_candidate_pack",
    "persist_legal_source_pack",
    "persist_policy_option_set",
    "persist_policy_request_frame",
    "persist_source_verification_report",
    "persist_verified_policy_report",
]
