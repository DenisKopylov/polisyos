from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
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


class LegalCandidatePack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    queries: list[str] = Field(default_factory=list)
    fact_hits: list[LegalFactResult] = Field(default_factory=list)
    provision_hits: list[LegalProvisionResult] = Field(default_factory=list)
    hit_reasons: dict[str, str] = Field(default_factory=dict)
    source_family_hints: dict[str, str] = Field(default_factory=dict)
    anchor_coverage_hints: dict[str, list[str]] = Field(default_factory=dict)
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class LegalSourcePack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    source_bundles: list[LegalSourceBundle] = Field(default_factory=list)
    unresolved_anchor_hints: list[str] = Field(default_factory=list)
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class VerifiedLegalClaim(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    gap_id: str
    category: str
    description: str
    severity: Literal["info", "warning", "critical"] = "warning"
    related_bundle_ids: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    resolved: bool = False


class SourceVerificationReport(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    option_id: str
    claim_id: str
    relation: Literal["supports", "limits", "threshold", "timing", "exception"] = "supports"


class PolicyOption(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    verified_options: list[PolicyOption] = Field(default_factory=list)
    hypothesis_options: list[PolicyOption] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VerifiedPolicyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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


def _persist_model(
    store: FileSystemCAS,
    model: BaseModel,
    *,
    kind: str,
    schema_name: str,
    inputs: list[InputRef] | None = None,
) -> dict[str, Any]:
    artifact = store.put_json(
        model,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=str(getattr(model, "schema_version", "1.0"))),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return artifact.model_dump()


def persist_policy_request_frame(
    store: FileSystemCAS,
    frame: PolicyRequestFrame,
    *,
    inputs: list[InputRef] | None = None,
) -> PolicyRequestFrameRef:
    return PolicyRequestFrameRef.model_validate(
        _persist_model(
            store,
            frame,
            kind="scientist.policy_request_frame",
            schema_name="polisyos.scientist.PolicyRequestFrame",
            inputs=inputs,
        )
    )


def load_policy_request_frame(store: FileSystemCAS, ref: PolicyRequestFrameRef) -> PolicyRequestFrame:
    return PolicyRequestFrame.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def persist_legal_candidate_pack(
    store: FileSystemCAS,
    pack: LegalCandidatePack,
    *,
    inputs: list[InputRef] | None = None,
) -> LegalCandidatePackRef:
    return LegalCandidatePackRef.model_validate(
        _persist_model(
            store,
            pack,
            kind="scientist.legal_candidate_pack",
            schema_name="polisyos.scientist.LegalCandidatePack",
            inputs=inputs,
        )
    )


def load_legal_candidate_pack(store: FileSystemCAS, ref: LegalCandidatePackRef) -> LegalCandidatePack:
    return LegalCandidatePack.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def persist_legal_source_pack(
    store: FileSystemCAS,
    pack: LegalSourcePack,
    *,
    inputs: list[InputRef] | None = None,
) -> LegalSourcePackRef:
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
    return LegalSourcePack.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def persist_source_verification_report(
    store: FileSystemCAS,
    report: SourceVerificationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> SourceVerificationReportRef:
    return SourceVerificationReportRef.model_validate(
        _persist_model(
            store,
            report,
            kind="scientist.source_verification_report",
            schema_name="polisyos.scientist.SourceVerificationReport",
            inputs=inputs,
        )
    )


def load_source_verification_report(
    store: FileSystemCAS,
    ref: SourceVerificationReportRef,
) -> SourceVerificationReport:
    return SourceVerificationReport.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def persist_policy_option_set(
    store: FileSystemCAS,
    option_set: PolicyOptionSet,
    *,
    inputs: list[InputRef] | None = None,
) -> PolicyOptionSetRef:
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
    return PolicyOptionSet.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def persist_verified_policy_report(
    store: FileSystemCAS,
    report: VerifiedPolicyReport,
    *,
    inputs: list[InputRef] | None = None,
) -> VerifiedPolicyReportRef:
    return VerifiedPolicyReportRef.model_validate(
        _persist_model(
            store,
            report,
            kind="scientist.verified_policy_report",
            schema_name="polisyos.scientist.VerifiedPolicyReport",
            inputs=inputs,
        )
    )


def load_verified_policy_report(
    store: FileSystemCAS,
    ref: VerifiedPolicyReportRef,
) -> VerifiedPolicyReport:
    return VerifiedPolicyReport.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


__all__ = [
    "PolicyRequestFrame",
    "LegalCandidatePack",
    "LegalSourcePack",
    "VerifiedLegalClaim",
    "SourceCoverageGap",
    "SourceVerificationReport",
    "PolicyEvidenceLink",
    "PolicyOption",
    "PolicyOptionSet",
    "VerifiedPolicyReport",
    "persist_policy_request_frame",
    "load_policy_request_frame",
    "persist_legal_candidate_pack",
    "load_legal_candidate_pack",
    "persist_legal_source_pack",
    "load_legal_source_pack",
    "persist_source_verification_report",
    "load_source_verification_report",
    "persist_policy_option_set",
    "load_policy_option_set",
    "persist_verified_policy_report",
    "load_verified_policy_report",
]
