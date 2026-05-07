from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.human_review.audit import signature_for_decision
from polisyos.scientist.governance.human_review.decisions import (
    HUMAN_REVIEW_DECISION_KIND,
    load_review_decision,
    persist_review_decision,
)
from polisyos.scientist.governance.human_review.models import HumanReviewDecision, ReviewAction
from polisyos.scientist.governance.human_review.packets import (
    HUMAN_REVIEW_PACKET_KIND,
    build_review_packet,
    load_review_packet,
    persist_review_packet,
)


def _ref(ch: str, *, kind: str = "scientist.evidence") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + ch * 64,
        kind=kind,
        media_type="application/json",
    )


def test_review_packet_and_decision_persist_and_load_from_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    claims_ref = _ref("1", kind="scientist.claim_ledger")
    packet = build_review_packet(
        run_id="run_1",
        workflow_id="scientist_policy_design",
        decision_payload={
            "schema_version": "3.4",
            "run_id": "run_1",
            "claim_readiness_summary": {"blocked_claim_ids": ["claim_a"]},
            "policy_summary": {"title": "Policy"},
        },
        claims_ref=claims_ref,
    )

    packet_ref = persist_review_packet(store, packet)
    loaded_packet = load_review_packet(store, packet_ref)
    decision = HumanReviewDecision(
        decision_id="decision_1",
        packet_id=packet.packet_id,
        run_id="run_1",
        reviewer_id="reviewer_a",
        action=ReviewAction.APPROVE,
        rationale="Evidence and blocked-claim handling were reviewed.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the release packet.",
        ),
        packet_ref=packet_ref,
    )
    decision_ref = persist_review_decision(store, decision)
    loaded_decision = load_review_decision(store, decision_ref)

    assert packet_ref.kind == HUMAN_REVIEW_PACKET_KIND
    assert decision_ref.kind == HUMAN_REVIEW_DECISION_KIND
    assert loaded_packet.packet_id == packet.packet_id
    assert loaded_decision == decision
    packet_manifest = store.get_manifest(packet_ref.artifact_id)
    decision_manifest = store.get_manifest(decision_ref.artifact_id)
    assert "claims" in {item.role for item in packet_manifest.inputs}
    assert "review_packet" in {item.role for item in decision_manifest.inputs}


def test_review_packet_prefers_claim_ledger_v2_summary_and_blocked_details() -> None:
    packet = build_review_packet(
        run_id="run_1",
        workflow_id="scientist_policy_design",
        decision_payload={
            "schema_version": "3.4",
            "run_id": "run_1",
            "claim_readiness_summary": {"blocked_claim_ids": ["legacy_claim"]},
            "claim_ledger_summary": {
                "lifecycle_status": "available",
                "blocked_claim_ids": ["claim_a"],
            },
            "blocked_claim_summary": {
                "blocked_claims": [
                    {
                        "claim_id": "claim_a",
                        "blocked_reasons": ["counterevidence_found"],
                    }
                ]
            },
            "policy_summary": {"title": "Policy"},
        },
    )

    assert packet.claim_ledger_summary["lifecycle_status"] == "available"
    assert packet.blocked_claim_ids == ["claim_a"]
