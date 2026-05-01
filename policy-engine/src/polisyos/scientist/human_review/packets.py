"""Review-packet builders and CAS persistence helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from hashlib import sha256
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.human_review.audit import make_audit_event
from polisyos.scientist.human_review.models import (
    FundamentalRightsChecklist,
    HumanReviewPacket,
    RecommendedReviewerAction,
    ReviewAssignment,
    ReviewControl,
    ReviewRiskTier,
)

HUMAN_REVIEW_PACKET_KIND = "scientist.human_review_packet"
HUMAN_REVIEW_PACKET_SCHEMA_NAME = "polisyos.scientist.human_review.HumanReviewPacket"
HUMAN_REVIEW_PACKET_SCHEMA_VERSION = "1.0"

__all__ = [
    "HUMAN_REVIEW_PACKET_KIND",
    "HUMAN_REVIEW_PACKET_SCHEMA_NAME",
    "HUMAN_REVIEW_PACKET_SCHEMA_VERSION",
    "build_review_packet",
    "human_review_packet_inputs",
    "load_review_packet",
    "persist_review_packet",
    "review_packet_summary",
]


def build_review_packet(
    *,
    run_id: str,
    decision_payload: Mapping[str, Any] | None = None,
    workflow_id: str | None = None,
    risk_tier: ReviewRiskTier | str = ReviewRiskTier.MEDIUM,
    decision_packet_ref: ArtifactRef | None = None,
    claims_ref: ArtifactRef | None = None,
    governance_report_ref: ArtifactRef | None = None,
    research_dag_ref: ArtifactRef | None = None,
    evidence_bundle_ref: ArtifactRef | None = None,
    assignments: list[ReviewAssignment] | None = None,
    required_reviewer_count: int = 1,
    fundamental_rights_checklist: FundamentalRightsChecklist | None = None,
    metadata: dict[str, Any] | None = None,
) -> HumanReviewPacket:
    """Build a high-signal human-review packet from an existing decision payload."""

    payload = dict(decision_payload or {})
    resolved_risk = ReviewRiskTier(risk_tier)
    packet_id = _packet_id(run_id=run_id, workflow_id=workflow_id, payload=payload)
    controls = _default_controls(resolved_risk)
    recommended_actions = _recommended_actions(payload, resolved_risk)
    checklist = fundamental_rights_checklist or FundamentalRightsChecklist(
        public_sector_use=resolved_risk is ReviewRiskTier.PUBLIC_SECTOR_HIGH,
        affects_fundamental_rights=bool(payload.get("affects_fundamental_rights")),
        automated_decision_support=True,
        legal_basis_documented=_has_section(payload, "legal_verification"),
        privacy_impact_considered=_section_has_no_issue(payload, "privacy"),
        fairness_impact_considered=_section_has_no_issue(payload, "fairness"),
        human_override_available=ReviewControl.OVERRIDE_RELEASE in controls,
        explanation_available=bool(payload.get("policy_answer") or payload.get("policy_summary")),
    )
    return HumanReviewPacket(
        packet_id=packet_id,
        run_id=run_id,
        workflow_id=workflow_id,
        risk_tier=resolved_risk,
        decision_summary=_decision_summary(payload),
        claim_ledger_summary=_claim_ledger_summary(payload),
        top_evidence_refs=_refs_from_payload(payload, "top_evidence_refs"),
        top_counterevidence_refs=_refs_from_payload(payload, "top_counterevidence_refs"),
        uncertainty_summary=_dict_section(payload, "uncertainty"),
        calibration_summary=_dict_section(payload, "calibration_validation"),
        source_freshness_summary=_source_freshness_summary(payload),
        legal_fairness_privacy_escalation_issues=_governance_issues(payload),
        blocked_claim_ids=_blocked_claim_ids(payload),
        unresolved_assumptions=_unresolved_assumptions(payload),
        recommended_reviewer_actions=recommended_actions,
        controls=controls,
        fundamental_rights_checklist=checklist,
        required_reviewer_count=required_reviewer_count,
        assignments=list(assignments or []),
        audit_trail=[
            make_audit_event(
                packet_id=packet_id,
                event_type="packet.created",
                message="Human review packet created.",
                actor_id="scientist.human_review.packets",
            )
        ],
        decision_packet_ref=decision_packet_ref,
        claims_ref=claims_ref,
        governance_report_ref=governance_report_ref,
        research_dag_ref=research_dag_ref,
        evidence_bundle_ref=evidence_bundle_ref,
        metadata=metadata or {},
    )


def human_review_packet_inputs(packet: HumanReviewPacket) -> list[InputRef]:
    """Build manifest lineage inputs for a review packet."""

    inputs: list[InputRef] = []
    seen: set[tuple[str, str]] = set()

    def add(ref: ArtifactRef | None, role: str) -> None:
        if ref is None:
            return
        key = (str(ref.artifact_id), role)
        if key in seen:
            return
        seen.add(key)
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=role))

    add(packet.decision_packet_ref, "decision_packet")
    add(packet.claims_ref, "claims")
    add(packet.governance_report_ref, "governance_report")
    add(packet.research_dag_ref, "research_dag")
    add(packet.evidence_bundle_ref, "evidence_bundle")
    for index, ref in enumerate(packet.top_evidence_refs):
        add(ref, f"top_evidence[{index}]")
    for index, ref in enumerate(packet.top_counterevidence_refs):
        add(ref, f"top_counterevidence[{index}]")
    return inputs


def persist_review_packet(
    store: FileSystemCAS,
    packet: HumanReviewPacket,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a human-review packet as a CAS artifact."""

    return store.put_json(
        packet,
        PutOptions(
            kind=HUMAN_REVIEW_PACKET_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=HUMAN_REVIEW_PACKET_SCHEMA_NAME,
                version=HUMAN_REVIEW_PACKET_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else human_review_packet_inputs(packet),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_review_packet(store: FileSystemCAS, ref: ArtifactRef) -> HumanReviewPacket:
    """Load a persisted human-review packet from CAS."""

    return HumanReviewPacket.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def review_packet_summary(packet: HumanReviewPacket) -> dict[str, Any]:
    """Return a compact packet summary for governance/decision artifacts."""

    return {
        "packet_id": packet.packet_id,
        "run_id": packet.run_id,
        "workflow_id": packet.workflow_id,
        "risk_tier": packet.risk_tier.value,
        "required_reviewer_count": packet.required_reviewer_count,
        "assignment_count": len(packet.assignments),
        "blocked_claim_count": len(packet.blocked_claim_ids),
        "unresolved_assumption_count": len(packet.unresolved_assumptions),
        "recommended_reviewer_actions": [
            item.value for item in packet.recommended_reviewer_actions
        ],
        "controls": [item.value for item in packet.controls],
        "fundamental_rights_unresolved": packet.fundamental_rights_checklist.unresolved_items,
    }


def _packet_id(
    *,
    run_id: str,
    workflow_id: str | None,
    payload: Mapping[str, Any],
) -> str:
    seed = f"{run_id}|{workflow_id or ''}|{payload.get('schema_version', '')}"
    return f"hrp_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _default_controls(risk_tier: ReviewRiskTier) -> list[ReviewControl]:
    controls = [
        ReviewControl.REQUEST_EXPLANATION,
        ReviewControl.REQUEST_RERUN,
        ReviewControl.REISSUE_WITH_CHANGES,
    ]
    if risk_tier in {ReviewRiskTier.HIGH, ReviewRiskTier.PUBLIC_SECTOR_HIGH}:
        controls.extend([ReviewControl.STOP_RELEASE, ReviewControl.OVERRIDE_RELEASE])
    return controls


def _recommended_actions(
    payload: Mapping[str, Any],
    risk_tier: ReviewRiskTier,
) -> list[RecommendedReviewerAction]:
    actions = [
        RecommendedReviewerAction.VERIFY_CLAIMS,
        RecommendedReviewerAction.APPROVE_OR_REJECT_RELEASE,
    ]
    if _blocked_claim_ids(payload):
        actions.append(RecommendedReviewerAction.CHECK_COUNTEREVIDENCE)
    if risk_tier is ReviewRiskTier.PUBLIC_SECTOR_HIGH:
        actions.append(RecommendedReviewerAction.REVIEW_RIGHTS_IMPACT)
    if payload.get("legal_verification") is not None:
        actions.append(RecommendedReviewerAction.REVIEW_LEGAL_BASIS)
    if payload.get("fairness") is not None or payload.get("calibration_validation") is not None:
        actions.append(RecommendedReviewerAction.REVIEW_FAIRNESS)
    if payload.get("privacy") is not None:
        actions.append(RecommendedReviewerAction.REVIEW_PRIVACY)
    return sorted(set(actions), key=lambda item: item.value)


def _decision_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "run_id": payload.get("run_id"),
        "policy_summary": payload.get("policy_summary"),
        "policy_answer": payload.get("policy_answer"),
        "governance_verdict": _dict_section(payload, "governance").get("verdict"),
        "research_dag_status": payload.get("research_dag_status"),
        "claim_ledger_status": payload.get("claim_ledger_status"),
    }


def _claim_ledger_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _dict_section(payload, "claim_ledger_summary")
    return summary or _dict_section(payload, "claim_readiness_summary")


def _source_freshness_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    web_evidence = _dict_section(payload, "web_evidence")
    return {
        "web_evidence_status": web_evidence.get("status"),
        "source_count": web_evidence.get("source_count"),
        "source_quality_signal_count": len(web_evidence.get("source_quality_signals", []) or []),
    }


def _governance_issues(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    governance = _dict_section(payload, "governance")
    issues = governance.get("issues", [])
    return [dict(item) for item in issues if isinstance(item, Mapping)]


def _blocked_claim_ids(payload: Mapping[str, Any]) -> list[str]:
    blocked_summary = _dict_section(payload, "blocked_claim_summary")
    blocked_claims = blocked_summary.get("blocked_claims", []) or []
    blocked_from_details = [
        str(item.get("claim_id"))
        for item in blocked_claims
        if isinstance(item, Mapping) and item.get("claim_id")
    ]
    if blocked_from_details:
        return sorted(set(blocked_from_details))
    ledger_summary = _dict_section(payload, "claim_ledger_summary")
    blocked_ids = ledger_summary.get("blocked_claim_ids", []) or []
    if blocked_ids:
        return sorted(str(item) for item in blocked_ids)
    readiness_summary = _dict_section(payload, "claim_readiness_summary")
    return sorted(str(item) for item in readiness_summary.get("blocked_claim_ids", []) or [])


def _unresolved_assumptions(payload: Mapping[str, Any]) -> list[str]:
    assumptions: list[str] = []
    for section_name in ("causal", "causal_validity", "uncertainty", "welfare"):
        section = _dict_section(payload, section_name)
        for key in ("unresolved_assumptions", "assumptions", "gaps"):
            value = section.get(key)
            if isinstance(value, list):
                assumptions.extend(str(item) for item in value)
    return sorted(set(assumptions))


def _refs_from_payload(payload: Mapping[str, Any], key: str) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    for item in payload.get(key, []) or []:
        try:
            refs.append(ArtifactRef.model_validate(item))
        except (TypeError, ValueError):
            continue
    return _dedupe_refs(refs)


def _dedupe_refs(refs: Iterable[ArtifactRef]) -> list[ArtifactRef]:
    output: list[ArtifactRef] = []
    seen: set[str] = set()
    for ref in refs:
        key = str(ref.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        output.append(ref)
    return output


def _dict_section(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _has_section(payload: Mapping[str, Any], key: str) -> bool:
    return bool(_dict_section(payload, key))


def _section_has_no_issue(payload: Mapping[str, Any], key: str) -> bool:
    section = _dict_section(payload, key)
    if not section:
        return False
    issues = section.get("issues", [])
    return not issues
