"""Layer 2 S9 canonical projection faithfulness and governed lowering contracts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.pdc import (
    AuthorityBoundary,
    CanonicalDesignRecord,
    DesignRecordV0,
    Layer2ReadinessModel,
)

LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s9_projection_lowering.v1"
)
LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION = "policyos.layer2.s9.projection_lowering.v1"
S9_PROJECTION_FLOOR_ID = "s9_projection_faithfulness"

Audience = Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]
ProjectionOperation = Literal["projection", "lowering"]
ProjectionAspect = Literal[
    "tradeoff_brief",
    "evidence_view",
    "legal_diff",
    "budget_package",
    "procedure",
    "machine_contract",
]
ProjectionDepth = Literal[
    "problem_frame",
    "design_sketch",
    "design_candidate",
    "policy_program",
    "legal_budget_procedure",
]
ProjectionRedaction = Literal["none", "public_redacted", "reviewer_private", "machine_full"]
ProjectionFormat = Literal["json", "markdown", "public_brief", "machine_contract"]
RevisionPolicy = Literal["same_revision", "reissue_required", "reopen_required"]
FaithfulnessStatus = Literal["pass", "fail"]
TradeoffDirectionStatus = Literal["preserved", "inverted", "unknown"]
ShadowApprovalStatus = Literal["not_approved", "rendered_as_approved"]
LoweringKind = Literal[
    "legal_diff",
    "budget_package",
    "implementation_procedure",
    "monitoring_protocol",
    "machine_contract",
]
LoweringGateStatus = Literal[
    "projection_allowed",
    "lowering_allowed_existing_scope",
    "lowering_blocked_missing_grounding",
    "lowering_blocked_requires_reissue",
    "lowering_blocked_projection_only",
]

_CREATED_AT = datetime(2026, 6, 2, tzinfo=UTC)
_S9_MAY_NOT_USE_FOR = [
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "approval_authority",
    "runtime_closeout_authority",
    "scorecard_authority",
    "s10_forecast_support",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
]
_AUTHORITY_SLOTS = {
    "claim_authority",
    "scorecard_authority",
    "runtime_closeout_authority",
    "closeout_authority",
    "approval_authority",
    "publication_authority",
    "production_recommendation",
    "production_claim_authority",
}
_LEGAL_BUDGET_PROCEDURE_ASPECTS = {
    "legal_diff",
    "budget_package",
    "procedure",
}
_BLOCKED_GATE_STATUSES = {
    "lowering_blocked_missing_grounding",
    "lowering_blocked_requires_reissue",
    "lowering_blocked_projection_only",
}


class ProjectionAlgebraRequest(Layer2ReadinessModel):
    """Typed S9 request over audience, aspect, depth, redaction, format, and revision."""

    request_id: str = Field(..., min_length=1, max_length=160)
    request_ref: str = Field(..., min_length=1, max_length=300)
    source_design_record_ref: str = Field(..., min_length=1, max_length=300)
    source_design_record_digest: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_digest: str = Field(..., min_length=1, max_length=300)
    operation: ProjectionOperation
    audience: Audience
    aspect: ProjectionAspect
    depth: ProjectionDepth
    redaction: ProjectionRedaction
    format: ProjectionFormat
    revision_policy: RevisionPolicy
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    reissue_ref: str | None = Field(default=None, max_length=300)
    requested_field_refs: list[str] = Field(default_factory=list, max_length=120)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    @model_validator(mode="after")
    def _validate_projection_request(self) -> ProjectionAlgebraRequest:
        if self.audience == "PUBLIC" and self.redaction == "machine_full":
            raise ValueError("PUBLIC projection cannot use machine_full redaction")
        if (
            self.operation == "projection"
            and (
                self.aspect in _LEGAL_BUDGET_PROCEDURE_ASPECTS
                or self.depth == "legal_budget_procedure"
            )
        ):
            raise ValueError(
                "projection requests cannot mint legal/budget/procedure lowering content"
            )
        return self


class ProjectionRenderRecord(Layer2ReadinessModel):
    """Rendered projection record before faithfulness verification."""

    render_id: str = Field(..., min_length=1, max_length=160)
    render_ref: str = Field(..., min_length=1, max_length=300)
    request_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_digest: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    audience: Audience
    aspect: ProjectionAspect
    depth: ProjectionDepth
    redaction: ProjectionRedaction
    format: ProjectionFormat
    rendered_claim_refs: list[str] = Field(default_factory=list, max_length=160)
    omission_manifest: list[dict[str, object]] = Field(default_factory=list, max_length=120)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S9_MAY_NOT_USE_FOR))
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class ProjectionFaithfulnessRecord(Layer2ReadinessModel):
    """S9 semantic faithfulness proof for a rendered projection."""

    faithfulness_id: str = Field(..., min_length=1, max_length=160)
    faithfulness_ref: str = Field(..., min_length=1, max_length=300)
    render_ref: str = Field(..., min_length=1, max_length=300)
    request_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_digest: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    faithfulness_status: FaithfulnessStatus
    issue_codes: list[str] = Field(default_factory=list, max_length=80)
    added_claim_refs: list[str] = Field(default_factory=list, max_length=80)
    hidden_blocker_refs: list[str] = Field(default_factory=list, max_length=80)
    hidden_limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    tradeoff_direction_status: TradeoffDirectionStatus
    shadow_approval_status: ShadowApprovalStatus
    consumer_contract_ref: str = Field(..., min_length=1, max_length=300)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class LoweringRequestRecord(Layer2ReadinessModel):
    """Governed lowering request that must pass an authority gate before append."""

    request_id: str = Field(..., min_length=1, max_length=160)
    request_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_digest: str = Field(..., min_length=1, max_length=300)
    source_design_record_ref: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    lowering_kind: LoweringKind
    requested_depth: ProjectionDepth
    grounding_refs: list[str] = Field(default_factory=list, max_length=80)
    post_closeout_state: str = Field(..., min_length=1, max_length=80)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class LoweringAuthorityGateRecord(Layer2ReadinessModel):
    """Fail-closed authority gate for S9 lowering requests."""

    gate_id: str = Field(..., min_length=1, max_length=160)
    gate_ref: str = Field(..., min_length=1, max_length=300)
    request_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_ref: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    status: LoweringGateStatus
    missing_grounding_refs: list[str] = Field(default_factory=list, max_length=80)
    inspected_grounding_refs: list[str] = Field(default_factory=list, max_length=80)
    action_route: str = Field(default="none", min_length=1, max_length=120)
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S9_MAY_NOT_USE_FOR))
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    @model_validator(mode="after")
    def _validate_gate_authority(self) -> LoweringAuthorityGateRecord:
        forbidden = _AUTHORITY_SLOTS & set(self.authority_boundary.authoritative_for)
        if forbidden:
            raise ValueError(f"lowering gate cannot grant authority slots: {sorted(forbidden)}")
        return self


class LoweringArtifactRecord(Layer2ReadinessModel):
    """Verified lowering artifact that remains bounded by projection authority."""

    artifact_id: str = Field(..., min_length=1, max_length=160)
    artifact_ref: str = Field(..., min_length=1, max_length=300)
    lowering_kind: LoweringKind
    source_canonical_design_record_ref: str = Field(..., min_length=1, max_length=300)
    verification_ref: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S9_MAY_NOT_USE_FOR))
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class LoweringAppendReceipt(Layer2ReadinessModel):
    """Immutable append receipt for verified lowering artifacts."""

    append_id: str = Field(..., min_length=1, max_length=160)
    append_ref: str = Field(..., min_length=1, max_length=300)
    artifact_ref: str = Field(..., min_length=1, max_length=300)
    request_ref: str = Field(..., min_length=1, max_length=300)
    gate_ref: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    verification_status: Literal["verified"]
    verification_ref: str = Field(..., min_length=1, max_length=300)
    reissue_ref: str | None = Field(default=None, max_length=300)
    reopen_ref: str | None = Field(default=None, max_length=300)
    replay_refs: list[str] = Field(..., min_length=1, max_length=80)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class DesignRecordMaturityReport(Layer2ReadinessModel):
    """Completeness report for maturing `DesignRecordV0` into the S9 canonical record."""

    schema_version: str = LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION
    design_record_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_ref: str = Field(..., min_length=1, max_length=300)
    design_record_schema_version: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_schema_version: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    axis_position_refs: list[str] = Field(..., min_length=1, max_length=80)
    firewall_status_refs: list[str] = Field(..., min_length=1, max_length=80)
    ledger_refs: list[str] = Field(..., min_length=1, max_length=120)
    assurance_case_refs: list[str] = Field(..., min_length=1, max_length=80)
    limitation_refs: list[str] = Field(..., min_length=1, max_length=80)
    abstention_refs: list[str] = Field(default_factory=list, max_length=80)
    lowering_artifact_refs: list[str] = Field(default_factory=list, max_length=80)
    projection_audiences: list[Audience] = Field(..., min_length=1, max_length=4)
    missing_maturity_fields: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    @model_validator(mode="after")
    def _validate_maturity_refs(self) -> DesignRecordMaturityReport:
        ledger_text = "\n".join(self.ledger_refs)
        missing: list[str] = []
        for label in ("s2", "s5", "s8"):
            if f"/{label}/" not in ledger_text and f"layer2/{label}" not in ledger_text:
                missing.append(label)
        if missing or self.missing_maturity_fields:
            raise ValueError(
                "S9 maturity report requires S2, S5, and S8 refs with no missing fields"
            )
        return self


class ProjectionLoweringIntegrityReport(Layer2ReadinessModel):
    """Integrity and false-clear report for the S9 projection faithfulness floor."""

    schema_version: str = LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=160)
    report_ref: str = Field(..., min_length=1, max_length=300)
    projection_faithfulness_denominator: int = Field(ge=0)
    projection_faithfulness_numerator: int = Field(ge=0)
    projection_faithfulness_pass_rate: float = Field(ge=0.0, le=1.0)
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    issue_counts: dict[str, int] = Field(default_factory=dict)
    negative_control_results: dict[str, object] = Field(default_factory=dict)
    lowering_gate_count: int = Field(ge=0)
    case_count: int = Field(ge=0)
    floor_id: Literal["s9_projection_faithfulness"] = S9_PROJECTION_FLOOR_ID
    metric_name: Literal["projection_faithfulness_pass_rate"] = (
        "projection_faithfulness_pass_rate"
    )
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


def build_projection_algebra_request(**payload: object) -> ProjectionAlgebraRequest:
    """Build and validate an S9 projection/lowering algebra request."""

    return ProjectionAlgebraRequest.model_validate(payload)


def build_projection_render_record(**payload: object) -> ProjectionRenderRecord:
    """Build and validate an S9 projection render record."""

    return ProjectionRenderRecord.model_validate(payload)


def build_canonical_design_record(
    design_record: DesignRecordV0 | Mapping[str, object],
    *,
    record_ref: str | None = None,
    source_design_record_ref: str | None = None,
    source_design_record_digest: str | None = None,
    source_revision_ref: str,
    canonical_design_record_revision_ref: str | None = None,
    recursive_design_graph_refs: Sequence[str] = (),
    claim_bound_evidence_portfolio_refs: Sequence[str] = (),
    pareto_tradeoff_value_choice_refs: Sequence[str] = (),
    counterexample_refinement_refs: Sequence[str] = (),
    assurance_case_refs: Sequence[str] = (),
    limitation_refs: Sequence[str] = (),
    abstention_refs: Sequence[str] = (),
    lowering_artifact_refs: Sequence[str] = (),
    rule_version_ref: str = LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
) -> CanonicalDesignRecord:
    """Mature a `DesignRecordV0` into a neutral S9 canonical record."""

    source = (
        design_record
        if isinstance(design_record, DesignRecordV0)
        else DesignRecordV0.model_validate(design_record)
    )
    slug = _slug(source.record_id)
    source_ref = source_design_record_ref or f"pdc://layer2/s2/{slug}/design-record-v0"
    resolved_record_ref = record_ref or f"pdc://layer2/s9/{slug}/canonical-design-record"
    digest = source_design_record_digest or _digest_mapping(source.model_dump(mode="json"))
    return CanonicalDesignRecord(
        record_id=f"layer2.s9.canonical.{slug}",
        record_ref=resolved_record_ref,
        source_design_record_ref=source_ref,
        source_design_record_digest=digest,
        source_revision_ref=source_revision_ref,
        canonical_design_record_revision_ref=(
            canonical_design_record_revision_ref or f"{resolved_record_ref}/revision/001"
        ),
        recursive_design_graph_refs=list(recursive_design_graph_refs)
        or _refs_matching(source.ledger_refs, "s5")
        or [f"pdc://layer2/s9/{slug}/missing-recursive-design-graph"],
        claim_bound_evidence_portfolio_refs=list(claim_bound_evidence_portfolio_refs)
        or [f"pdc://layer2/s9/{slug}/claim-bound-evidence-portfolio"],
        pareto_tradeoff_value_choice_refs=list(pareto_tradeoff_value_choice_refs)
        or _refs_matching(source.ledger_refs, "s8")
        or [f"pdc://layer2/s9/{slug}/missing-value-choice-ref"],
        axis_position_refs=[position.cell_ref for position in source.axis_positions],
        firewall_status_refs=[status.cell_ref for status in source.firewall_status],
        certified_envelope_ref=source.envelope.envelope_id,
        search_ledger_refs=list(source.ledger_refs)
        or [f"pdc://layer2/s2/{slug}/missing-search-ledger"],
        counterexample_refinement_refs=[str(ref) for ref in counterexample_refinement_refs],
        assurance_case_refs=list(assurance_case_refs)
        or [f"pdc://layer2/s9/{slug}/assurance/projection"],
        limitation_refs=list(limitation_refs) or [f"pdc://layer2/s9/{slug}/limitation"],
        abstention_refs=[str(ref) for ref in abstention_refs],
        lowering_artifact_refs=[str(ref) for ref in lowering_artifact_refs],
        projection_audiences=list(source.projection_audiences),
        projection_status=source.projection_status,
        authority_boundary=source.authority_boundary,
        rule_version_ref=rule_version_ref,
    )


def build_design_record_maturity_report(
    canonical_design_record: CanonicalDesignRecord | Mapping[str, object],
    *,
    design_record_schema_version: str,
    rule_version_ref: str = LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
) -> DesignRecordMaturityReport:
    """Build an S9 maturity report over a canonical design record."""

    canonical_record = (
        canonical_design_record
        if isinstance(canonical_design_record, CanonicalDesignRecord)
        else CanonicalDesignRecord.model_validate(canonical_design_record)
    )
    return DesignRecordMaturityReport(
        design_record_ref=canonical_record.source_design_record_ref,
        canonical_design_record_ref=canonical_record.record_ref,
        design_record_schema_version=design_record_schema_version,
        canonical_design_record_schema_version=canonical_record.schema_version,
        source_revision_ref=canonical_record.source_revision_ref,
        axis_position_refs=canonical_record.axis_position_refs,
        firewall_status_refs=canonical_record.firewall_status_refs,
        ledger_refs=canonical_record.search_ledger_refs,
        assurance_case_refs=canonical_record.assurance_case_refs,
        limitation_refs=canonical_record.limitation_refs,
        abstention_refs=canonical_record.abstention_refs,
        lowering_artifact_refs=canonical_record.lowering_artifact_refs,
        projection_audiences=canonical_record.projection_audiences,
        missing_maturity_fields=[],
        authority_boundary=canonical_record.authority_boundary,
        rule_version_ref=rule_version_ref,
    )


def verify_projection_faithfulness(
    *,
    canonical_design_record: CanonicalDesignRecord | Mapping[str, object],
    projection_request: ProjectionAlgebraRequest | Mapping[str, object],
    projection_render: ProjectionRenderRecord | Mapping[str, object],
) -> ProjectionFaithfulnessRecord:
    """Verify S9 projection faithfulness against canonical record truth."""

    canonical_record = (
        canonical_design_record
        if isinstance(canonical_design_record, CanonicalDesignRecord)
        else CanonicalDesignRecord.model_validate(canonical_design_record)
    )
    request = (
        projection_request
        if isinstance(projection_request, ProjectionAlgebraRequest)
        else ProjectionAlgebraRequest.model_validate(projection_request)
    )
    render = (
        projection_render
        if isinstance(projection_render, ProjectionRenderRecord)
        else ProjectionRenderRecord.model_validate(projection_render)
    )

    issue_codes: list[str] = []
    rendered_refs = set(render.rendered_claim_refs)
    manifest_refs = _omission_manifest_refs(render.omission_manifest)
    allowed_refs = _canonical_allowed_refs(canonical_record)

    hidden_limitation_refs = [
        ref
        for ref in canonical_record.limitation_refs
        if ref not in rendered_refs and ref not in manifest_refs
    ]
    if render.audience == "PUBLIC" and hidden_limitation_refs:
        issue_codes.append("s9_public_projection_missing_limitation")

    added_claim_refs = [
        ref
        for ref in render.rendered_claim_refs
        if _is_claim_ref(ref) and ref not in allowed_refs and "shadow-design" not in ref
    ]
    if added_claim_refs:
        issue_codes.append("s9_projection_added_claim")

    tradeoff_direction_status: TradeoffDirectionStatus = "preserved"
    if any("inverted" in ref or "tradeoff_inversion" in ref for ref in render.rendered_claim_refs):
        tradeoff_direction_status = "inverted"
        issue_codes.append("s9_tradeoff_inversion")

    shadow_approval_status: ShadowApprovalStatus = "not_approved"
    if canonical_record.projection_status == "shadow" and any(
        "approved" in ref or "approval" in ref for ref in render.rendered_claim_refs
    ):
        shadow_approval_status = "rendered_as_approved"
        issue_codes.append("s9_shadow_candidate_rendered_as_approved")

    if _projection_mints_authority(render):
        issue_codes.append("s9_projection_mints_authority")

    if any("universal" in ref for ref in render.rendered_claim_refs) and not any(
        "s14" in ref or "universality" in ref for ref in canonical_record.assurance_case_refs
    ):
        issue_codes.append("s9_universal_self_claim_without_s14_refs")

    issue_codes = _dedupe(issue_codes)
    return ProjectionFaithfulnessRecord(
        faithfulness_id=f"layer2.s9.faithfulness.{_slug(render.render_id)}",
        faithfulness_ref=f"{render.render_ref}/faithfulness",
        render_ref=render.render_ref,
        request_ref=request.request_ref,
        canonical_design_record_ref=canonical_record.record_ref,
        canonical_design_record_digest=request.canonical_design_record_digest,
        source_revision_ref=render.source_revision_ref,
        faithfulness_status="fail" if issue_codes else "pass",
        issue_codes=issue_codes,
        added_claim_refs=added_claim_refs,
        hidden_blocker_refs=[],
        hidden_limitation_refs=hidden_limitation_refs,
        tradeoff_direction_status=tradeoff_direction_status,
        shadow_approval_status=shadow_approval_status,
        consumer_contract_ref=(
            "policyos.runtime.policy_design_case.projection_contract_verification.v1"
        ),
        authority_boundary=_authority_boundary(["projection_faithfulness"]),
        rule_version_ref=LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
    )


def gate_lowering_request(
    *,
    canonical_design_record: CanonicalDesignRecord | Mapping[str, object],
    lowering_request: LoweringRequestRecord | Mapping[str, object],
) -> LoweringAuthorityGateRecord:
    """Gate a governed lowering request without granting production authority."""

    canonical_record = (
        canonical_design_record
        if isinstance(canonical_design_record, CanonicalDesignRecord)
        else CanonicalDesignRecord.model_validate(canonical_design_record)
    )
    request = (
        lowering_request
        if isinstance(lowering_request, LoweringRequestRecord)
        else LoweringRequestRecord.model_validate(lowering_request)
    )
    slug = _case_slug(canonical_record.record_ref)
    if (
        request.post_closeout_state.startswith("closed")
        and request.source_revision_ref != canonical_record.source_revision_ref
    ):
        status: LoweringGateStatus = "lowering_blocked_requires_reissue"
        missing_grounding_refs: list[str] = []
        action_route = "reissue_required"
    elif _requires_grounding(request) and not request.grounding_refs:
        status = "lowering_blocked_missing_grounding"
        missing_grounding_refs = [f"legal://{slug}/grounding"]
        action_route = "provide_grounding"
    elif canonical_record.projection_status == "shadow" and request.requested_depth in {
        "policy_program",
        "legal_budget_procedure",
    }:
        status = "lowering_blocked_projection_only"
        missing_grounding_refs = []
        action_route = "reopen_required"
    else:
        status = "lowering_allowed_existing_scope"
        missing_grounding_refs = []
        action_route = "append_verified_lowering_artifact"

    return LoweringAuthorityGateRecord(
        gate_id=f"layer2.s9.lowering_gate.{_slug(request.request_id)}",
        gate_ref=f"{request.request_ref}/gate",
        request_ref=request.request_ref,
        canonical_design_record_ref=canonical_record.record_ref,
        source_revision_ref=request.source_revision_ref,
        status=status,
        missing_grounding_refs=missing_grounding_refs,
        inspected_grounding_refs=list(request.grounding_refs),
        action_route=action_route,
        may_not_use_for=list(_S9_MAY_NOT_USE_FOR),
        authority_boundary=_authority_boundary(["lowering_gate"]),
        rule_version_ref=LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
    )


def append_verified_lowering_artifact(
    *,
    lowering_request: LoweringRequestRecord | Mapping[str, object],
    gate_record: LoweringAuthorityGateRecord | Mapping[str, object],
    artifact_ref: str,
    verification_ref: str,
) -> dict[str, object]:
    """Append a verified lowering artifact and immutable receipt."""

    request = (
        lowering_request
        if isinstance(lowering_request, LoweringRequestRecord)
        else LoweringRequestRecord.model_validate(lowering_request)
    )
    gate = (
        gate_record
        if isinstance(gate_record, LoweringAuthorityGateRecord)
        else LoweringAuthorityGateRecord.model_validate(gate_record)
    )
    if gate.status in _BLOCKED_GATE_STATUSES:
        raise ValueError(f"cannot append lowering artifact when gate status is {gate.status}")
    artifact_record = LoweringArtifactRecord(
        artifact_id=f"layer2.s9.lowering_artifact.{_slug(request.request_id)}",
        artifact_ref=artifact_ref,
        lowering_kind=request.lowering_kind,
        source_canonical_design_record_ref=request.canonical_design_record_ref,
        verification_ref=verification_ref,
        source_revision_ref=request.source_revision_ref,
        authority_boundary=_authority_boundary(["lowering_artifact_append"]),
        may_not_use_for=list(_S9_MAY_NOT_USE_FOR),
        rule_version_ref=LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
    )
    receipt = LoweringAppendReceipt(
        append_id=f"layer2.s9.lowering_append.{_slug(request.request_id)}",
        append_ref=f"{artifact_ref}/append-receipt",
        artifact_ref=artifact_ref,
        request_ref=request.request_ref,
        gate_ref=gate.gate_ref,
        source_revision_ref=request.source_revision_ref,
        verification_status="verified",
        verification_ref=verification_ref,
        replay_refs=[
            request.request_ref,
            gate.gate_ref,
            artifact_ref,
            verification_ref,
        ],
        authority_boundary=_authority_boundary(["lowering_append_receipt"]),
        rule_version_ref=LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
    )
    return {
        "artifact": artifact_record.model_dump(mode="json"),
        "append_receipt": receipt.model_dump(mode="json"),
    }


def s9_projection_lowering_integrity(
    *,
    projection_faithfulness_records: Sequence[
        ProjectionFaithfulnessRecord | Mapping[str, object]
    ],
    lowering_gate_records: Sequence[LoweringAuthorityGateRecord | Mapping[str, object]] = (),
    negative_control_results: Mapping[str, object] | None = None,
) -> ProjectionLoweringIntegrityReport:
    """Compute S9 faithfulness and false-clear metrics."""

    faithfulness_records = [
        record
        if isinstance(record, ProjectionFaithfulnessRecord)
        else ProjectionFaithfulnessRecord.model_validate(record)
        for record in projection_faithfulness_records
    ]
    gates = [
        record
        if isinstance(record, LoweringAuthorityGateRecord)
        else LoweringAuthorityGateRecord.model_validate(record)
        for record in lowering_gate_records
    ]
    denominator = len(faithfulness_records)
    numerator = sum(1 for record in faithfulness_records if record.faithfulness_status == "pass")
    issue_counts = Counter(
        issue
        for record in faithfulness_records
        for issue in record.issue_codes
    )
    negative_controls = dict(negative_control_results or {})
    false_clear_counts = {
        str(name): _negative_control_false_clear_count(result)
        for name, result in negative_controls.items()
    }
    return ProjectionLoweringIntegrityReport(
        report_id="layer2.s9.projection_lowering_integrity",
        report_ref="pdc://layer2/s9/projection-lowering-integrity",
        projection_faithfulness_denominator=denominator,
        projection_faithfulness_numerator=numerator,
        projection_faithfulness_pass_rate=(
            1.0 if denominator == 0 else numerator / denominator
        ),
        false_clear_counts=false_clear_counts,
        issue_counts=dict(issue_counts),
        negative_control_results=negative_controls,
        lowering_gate_count=len(gates),
        case_count=denominator,
        floor_id=S9_PROJECTION_FLOOR_ID,
        authority_boundary=_authority_boundary(["projection_lowering_integrity_report"]),
        rule_version_ref=LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
    )


def persist_projection_lowering_bundle(
    bundle: Mapping[str, object],
    *,
    store: artifacts.FileSystemCAS | None = None,
    rule_version_ref: str = LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION,
) -> dict[str, object]:
    """Persist an S9 projection/lowering bundle through CAS or deterministic refs."""

    payload = dict(bundle)
    if store is None:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "bundle_ref": f"pdc://layer2/s9/projection-lowering-bundle/sha256:{digest}",
            "artifact_ref": f"sha256:{digest}",
            "rule_version_ref": rule_version_ref,
        }
    ref = store.put_json(
        payload,
        artifacts.PutOptions(
            kind="policyos.layer2_s9.projection_lowering_bundle",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s9.projection_lowering_bundle",
                version=LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION,
            ),
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.quality.design_axes.projection_lowering",
                version=rule_version_ref,
            ),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    return {
        "bundle_ref": ref,
        "artifact_ref": ref.artifact_id,
        "rule_version_ref": rule_version_ref,
    }


def _authority_boundary(authoritative_for: Sequence[str]) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=[str(item) for item in authoritative_for],
        may_not_use_for=list(_S9_MAY_NOT_USE_FOR),
        source_authority="deterministic_producer",
        posture="shadow",
        rule_version_refs=[LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION],
    )


def _omission_manifest_refs(rows: Sequence[Mapping[str, object]]) -> set[str]:
    refs: set[str] = set()
    for row in rows:
        for key in ("omitted_field_ref", "source_ref", "claim_ref", "blocker_ref"):
            value = row.get(key)
            if isinstance(value, str) and value:
                refs.add(value)
    return refs


def _canonical_allowed_refs(record: CanonicalDesignRecord) -> set[str]:
    return {
        record.record_ref,
        record.source_design_record_ref,
        *record.recursive_design_graph_refs,
        *record.claim_bound_evidence_portfolio_refs,
        *record.pareto_tradeoff_value_choice_refs,
        *record.axis_position_refs,
        *record.firewall_status_refs,
        record.certified_envelope_ref,
        *record.search_ledger_refs,
        *record.counterexample_refinement_refs,
        *record.assurance_case_refs,
        *record.limitation_refs,
        *record.abstention_refs,
        *record.lowering_artifact_refs,
    }


def _is_claim_ref(ref: str) -> bool:
    return ref.startswith("claim://") or ref.startswith("hypothesis-candidate:")


def _projection_mints_authority(render: ProjectionRenderRecord) -> bool:
    if _AUTHORITY_SLOTS & set(render.authority_boundary.authoritative_for):
        return True
    may_not = set(render.may_not_use_for) | set(render.authority_boundary.may_not_use_for)
    required = {
        "claim_authority",
        "scorecard_authority",
        "runtime_closeout_authority",
    }
    return not required <= may_not


def _requires_grounding(request: LoweringRequestRecord) -> bool:
    return request.lowering_kind in {
        "legal_diff",
        "budget_package",
        "implementation_procedure",
    } or request.requested_depth == "legal_budget_procedure"


def _negative_control_false_clear_count(result: object) -> int:
    if not isinstance(result, Mapping):
        return 0
    expected_false_clear = result.get("expected_false_clear")
    actual_clear = result.get("actual_clear")
    if expected_false_clear is False and actual_clear is True:
        return 1
    return 0


def _refs_matching(refs: Sequence[str], label: str) -> list[str]:
    return [str(ref) for ref in refs if f"/{label}/" in str(ref) or f"layer2/{label}" in str(ref)]


def _digest_mapping(payload: Mapping[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"sha256:{digest}"


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace("://", ".")
        .replace("/", ".")
        .replace("_", "-")
        .replace(" ", "-")
    )[:120]


def _case_slug(ref: str) -> str:
    if "ua-msme" in ref:
        return "ua-msme"
    parts = [part for part in ref.split("/") if part]
    return _slug(parts[-2] if len(parts) > 1 else ref)


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
