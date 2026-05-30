"""Layer 2 S1 graded-outcome routing over existing status primitives."""

from __future__ import annotations

import re
from collections.abc import Sequence  # noqa: TC003 - pydantic resolves annotations at runtime.
from datetime import datetime  # noqa: TC003 - pydantic resolves annotations at runtime.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.runtime.quality.status_deficits import (
    DeficitRecord,
    build_status_envelope,
    status_envelope_payload,
)

S1_GRADED_OUTCOME_SCHEMA_VERSION = "policyos.runtime.layer2.graded_outcome.v1"
S1_GRADED_OUTCOME_CLOSEOUT_RECORD_SCHEMA_VERSION = "policyos.runtime.status_envelope.v1"

_PRODUCER = "polisyos.runtime.quality.graded_outcomes"
_RUNTIME_EVENT_REF = "event://layer2/s1/graded-outcomes"
_AUTHORITY_BOUNDARY_MAY_NOT_USE_FOR = (
    "claim_authority",
    "producer_domain_truth",
    "production_closeout_authority",
    "publication_authority_without_closeout",
    "b_side_design_generation",
)


class GradedOutcomeInputError(ValueError):
    """Raised when S1 graded-outcome evidence cannot be composed safely."""


class GradedOutcomeEvidenceInput(BaseModel):
    """Evidence and authority posture consumed by the S1 composition policy.

    Attributes:
        schema_version: Schema version for S1 graded-outcome inputs.
        case_id: Stable corpus or runtime case id.
        claim_id: Claim id whose evidence profile is being routed.
        authority_level: Authority posture requested by the caller.
        requested_outcome: Local requested routing outcome.
        evidence_profile: Whether the evidence is exact, partial/proxy, or unsupported.
        proxy_evidence_refs: References to proxy evidence.
        partial_evidence_refs: References to partial evidence.
        limitation_reason_codes: Reason codes supporting a limitation route.
        mandatory_gate_state: Mandatory gate state that may dominate the request.
        owner: Accountable owner for the routed status.
        decision_owner_ref: Governance decision owner reference, when required.
        authority_profile_ref: Authority profile reference used for the route.
        review_refs: Review references supporting governed or research limitation routing.
        ttl_expires_at: Expiration time for the owned limitation or blocker.
        public_limitation_note: Public-facing limitation note.
        rule_version_ref: Semantic rule version for replay.
        source_authority: Deterministic or governed source class for the decision.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.layer2.graded_outcome.v1"]
    case_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    authority_level: Literal[
        "research",
        "governed",
        "governed_pilot",
        "governed-pilot",
        "production",
    ]
    requested_outcome: Literal[
        "pass",
        "publish_with_limitation",
        "accepted_deficit",
        "typed_blocker",
    ]
    evidence_profile: Literal["exact", "partial_or_proxy", "unsupported"]
    proxy_evidence_refs: tuple[str, ...] = Field(default=())
    partial_evidence_refs: tuple[str, ...] = Field(default=())
    limitation_reason_codes: tuple[str, ...] = Field(default=())
    mandatory_gate_state: Literal[
        "none",
        "overridable_by_governed_commit",
        "non_overridable",
    ]
    owner: str = Field(min_length=1)
    decision_owner_ref: str | None
    authority_profile_ref: str = Field(min_length=1)
    review_refs: tuple[str, ...] = Field(default=())
    ttl_expires_at: datetime
    public_limitation_note: str | None
    rule_version_ref: str = Field(min_length=1)
    source_authority: Literal[
        "deterministic_producer",
        "governed_config",
        "human_governance",
    ] = "deterministic_producer"


class GradedOutcomeDecision(BaseModel):
    """Composed S1 routing decision and closeout-visible status artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.layer2.graded_outcome.v1"]
    decision_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    authority_level: Literal["research", "governed", "production"]
    outcome: Literal["pass", "publish_with_limitation", "accepted_deficit", "typed_blocker"]
    publication_effect: str = Field(min_length=1)
    closeout_effect: str = Field(min_length=1)
    authority_profile_ref: str = Field(min_length=1)
    decision_owner_ref: str | None
    review_refs: tuple[str, ...] = Field(default=())
    deficit_records: tuple[dict[str, Any], ...] = Field(default=())
    limitations: tuple[dict[str, Any], ...] = Field(default=())
    blockers: tuple[dict[str, Any], ...] = Field(default=())
    authority_boundary: dict[str, Any]
    rule_version_ref: str = Field(min_length=1)


def compose_graded_outcome(input: GradedOutcomeEvidenceInput) -> GradedOutcomeDecision:
    """Compose an S1 graded-outcome decision without minting claim authority.

    Args:
        input: Typed S1 evidence and authority posture.

    Returns:
        A typed decision containing validated deficit rows, blockers, and authority
        boundary metadata.

    Raises:
        GradedOutcomeInputError: If the requested limitation lacks evidence,
            owner/review metadata, or closeout-visible limitation text.
    """

    authority_level = _normalized_authority_level(input.authority_level)
    if input.mandatory_gate_state == "non_overridable":
        return _blocker_decision(
            input,
            authority_level=authority_level,
            blocker_code="graded_outcome_non_overridable_gate",
            message="A non-overridable mandatory gate blocks S1 limitation routing.",
        )

    if authority_level == "production" and input.evidence_profile != "exact":
        return _blocker_decision(
            input,
            authority_level=authority_level,
            blocker_code="graded_outcome_production_proxy_block",
            message="Production closeout requires exact production evidence.",
        )

    if input.requested_outcome == "publish_with_limitation":
        if not input.proxy_evidence_refs and not input.partial_evidence_refs:
            raise GradedOutcomeInputError(
                "publish_with_limitation requires proxy or partial evidence refs"
            )
        if authority_level in {"research", "governed"}:
            _require_limitation_commit(input)
            return _limitation_decision(input, authority_level=authority_level)

    if input.requested_outcome == "pass" and input.evidence_profile == "exact":
        return _pass_decision(input, authority_level=authority_level)

    return _blocker_decision(
        input,
        authority_level=authority_level,
        blocker_code="graded_outcome_unsupported_request",
        message="S1 graded-outcome input does not satisfy a publishable route.",
    )


def graded_outcome_closeout_record(
    decisions: Sequence[GradedOutcomeDecision],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Persist S1 decisions through the existing status-envelope shape.

    Args:
        decisions: Composed S1 decisions.
        generated_at: Optional generation timestamp for replayable envelopes.

    Returns:
        JSON-compatible status envelope payload with closeout-reader metadata and
        closeout-visible issue summaries.
    """

    deficit_records = [
        row for decision in decisions for row in decision.deficit_records
    ]
    envelope = build_status_envelope(
        local_statuses=[],
        deficits=deficit_records,
        now=generated_at,
    )
    blocking_decisions = [
        decision for decision in decisions if decision.outcome == "typed_blocker"
    ]
    payload = status_envelope_payload(envelope)
    payload.update(
        {
            "status": "blocked" if blocking_decisions else "pass",
            "authority_role": "runtime_reader",
            "provenance_kind": "runtime_emitted",
            "producer": _PRODUCER,
            "runtime_event_ref": _RUNTIME_EVENT_REF,
            "issues": _issue_rows(decisions),
        }
    )
    return payload


def _normalized_authority_level(
    authority_level: Literal[
        "research",
        "governed",
        "governed_pilot",
        "governed-pilot",
        "production",
    ],
) -> Literal["research", "governed", "production"]:
    if authority_level in {"governed_pilot", "governed-pilot"}:
        return "governed"
    return authority_level


def _require_limitation_commit(input: GradedOutcomeEvidenceInput) -> None:
    if not input.decision_owner_ref or not input.review_refs:
        raise GradedOutcomeInputError(
            "publish_with_limitation requires decision_owner_ref and review_refs"
        )
    if not input.authority_profile_ref:
        raise GradedOutcomeInputError(
            "publish_with_limitation requires authority_profile_ref"
        )
    if not input.public_limitation_note:
        raise GradedOutcomeInputError(
            "publish_with_limitation requires public_limitation_note"
        )


def _limitation_decision(
    input: GradedOutcomeEvidenceInput,
    *,
    authority_level: Literal["research", "governed"],
) -> GradedOutcomeDecision:
    evidence_ref = _evidence_ref(input)
    deficit_record = _deficit_record(input, authority_level=authority_level)
    limitation = {
        "code": "graded_outcome_publish_with_limitation",
        "deficit_id": deficit_record["deficit_id"],
        "message": input.public_limitation_note,
        "publication_effect": "publish_with_limitation",
        "closeout_effect": "limited_closeout",
        "owner": input.owner,
        "decision_owner_ref": input.decision_owner_ref,
        "authority_profile_ref": input.authority_profile_ref,
        "review_refs": list(input.review_refs),
        "evidence_ref": evidence_ref,
        "claim_ids": [input.claim_id],
    }
    return GradedOutcomeDecision(
        schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
        decision_id=_decision_id(input, authority_level=authority_level),
        case_id=input.case_id,
        claim_id=input.claim_id,
        authority_level=authority_level,
        outcome="publish_with_limitation",
        publication_effect="publish_with_limitation",
        closeout_effect="limited_closeout",
        authority_profile_ref=input.authority_profile_ref,
        decision_owner_ref=input.decision_owner_ref,
        review_refs=input.review_refs,
        deficit_records=(deficit_record,),
        limitations=(limitation,),
        blockers=(),
        authority_boundary=_authority_boundary(input, authority_level=authority_level),
        rule_version_ref=input.rule_version_ref,
    )


def _pass_decision(
    input: GradedOutcomeEvidenceInput,
    *,
    authority_level: Literal["research", "governed", "production"],
) -> GradedOutcomeDecision:
    return GradedOutcomeDecision(
        schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
        decision_id=_decision_id(input, authority_level=authority_level),
        case_id=input.case_id,
        claim_id=input.claim_id,
        authority_level=authority_level,
        outcome="pass",
        publication_effect="unaffected",
        closeout_effect="closeout_allowed",
        authority_profile_ref=input.authority_profile_ref,
        decision_owner_ref=input.decision_owner_ref,
        review_refs=input.review_refs,
        deficit_records=(),
        limitations=(),
        blockers=(),
        authority_boundary=_authority_boundary(input, authority_level=authority_level),
        rule_version_ref=input.rule_version_ref,
    )


def _blocker_decision(
    input: GradedOutcomeEvidenceInput,
    *,
    authority_level: Literal["research", "governed", "production"],
    blocker_code: str,
    message: str,
) -> GradedOutcomeDecision:
    blocker = {
        "code": blocker_code,
        "message": message,
        "publication_effect": "publication_blocked",
        "closeout_effect": "closeout_blocked",
        "owner": input.owner,
        "claim_id": input.claim_id,
        "authority_level": authority_level,
        "evidence_profile": input.evidence_profile,
        "mandatory_gate_state": input.mandatory_gate_state,
    }
    return GradedOutcomeDecision(
        schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
        decision_id=_decision_id(input, authority_level=authority_level),
        case_id=input.case_id,
        claim_id=input.claim_id,
        authority_level=authority_level,
        outcome="typed_blocker",
        publication_effect="publication_blocked",
        closeout_effect="closeout_blocked",
        authority_profile_ref=input.authority_profile_ref,
        decision_owner_ref=input.decision_owner_ref,
        review_refs=input.review_refs,
        deficit_records=(),
        limitations=(),
        blockers=(blocker,),
        authority_boundary=_authority_boundary(input, authority_level=authority_level),
        rule_version_ref=input.rule_version_ref,
    )


def _deficit_record(
    input: GradedOutcomeEvidenceInput,
    *,
    authority_level: Literal["research", "governed"],
) -> dict[str, Any]:
    row = {
        "deficit_id": f"limitation:{input.case_id}:{_slug(input.claim_id)}",
        "deficit_family": "graded_outcome",
        "deficit_code": "graded_outcome_proxy_or_partial_evidence",
        "claim_ids": [input.claim_id],
        "authority_level": authority_level,
        "audience_scope": "public",
        "disposition": "publish_with_limitation",
        "support_cap": "weak",
        "readiness_cap": "external_briefing",
        "max_audience": "public_with_limitation",
        "owner": input.owner,
        "ttl_expires_at": input.ttl_expires_at,
        "runtime_event_ref": f"{_RUNTIME_EVENT_REF}/{input.case_id}",
        "evidence_ref": _evidence_ref(input),
        "public_limitation_note": input.public_limitation_note,
        "review_refs": input.review_refs,
    }
    return DeficitRecord.model_validate(row).model_dump(mode="json", exclude_none=True)


def _authority_boundary(
    input: GradedOutcomeEvidenceInput,
    *,
    authority_level: Literal["research", "governed", "production"],
) -> dict[str, Any]:
    return {
        "authoritative_for": ["graded_outcome_routing"],
        "may_not_use_for": list(_AUTHORITY_BOUNDARY_MAY_NOT_USE_FOR),
        "source_authority": input.source_authority,
        "posture": authority_level,
    }


def _issue_rows(decisions: Sequence[GradedOutcomeDecision]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        for limitation in decision.limitations:
            rows.append(
                {
                    "code": "graded_outcome_publish_with_limitation",
                    "severity": "limitation",
                    "deficit_id": limitation.get("deficit_id"),
                    "message": limitation.get("message"),
                    "module_id": "graded_outcomes",
                    "owner": limitation.get("owner"),
                    "decision_owner_ref": decision.decision_owner_ref,
                    "authority_profile_ref": decision.authority_profile_ref,
                    "review_refs": list(decision.review_refs),
                    "evidence_ref": limitation.get("evidence_ref"),
                    "claim_ids": [decision.claim_id],
                    "authority_level": decision.authority_level,
                    "audience_scope": "public",
                }
            )
        for blocker in decision.blockers:
            rows.append(
                {
                    "code": blocker["code"],
                    "severity": "fail",
                    "message": blocker["message"],
                    "module_id": "graded_outcomes",
                    "owner": blocker.get("owner"),
                    "claim_id": decision.claim_id,
                    "authority_level": decision.authority_level,
                }
            )
    return rows


def _evidence_ref(input: GradedOutcomeEvidenceInput) -> str:
    if input.proxy_evidence_refs:
        return input.proxy_evidence_refs[0]
    return input.partial_evidence_refs[0]


def _decision_id(
    input: GradedOutcomeEvidenceInput,
    *,
    authority_level: Literal["research", "governed", "production"],
) -> str:
    return f"graded-outcome:{input.case_id}:{_slug(input.claim_id)}:{authority_level}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").casefold()
    return slug or "claim"
