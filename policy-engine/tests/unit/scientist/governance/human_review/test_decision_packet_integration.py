from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

import polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment as decision_packet_enrichment
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.governance.human_review.admission import (
    HumanReviewAdmissionStatus,
    resolve_human_review_admission,
)
from polisyos.scientist.governance.human_review.audit import signature_for_decision
from polisyos.scientist.governance.human_review.decisions import persist_review_decision
from polisyos.scientist.governance.human_review.models import (
    HumanReviewDecision,
    ReviewAction,
    ReviewAssignment,
    ReviewAssignmentStatus,
    ReviewRiskTier,
)
from polisyos.scientist.governance.human_review.packets import (
    build_review_packet,
    persist_review_packet,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
    BuildDecisionPacketNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_HUMAN_REVIEW_DECISION_REF,
    ARTIFACT_HUMAN_REVIEW_PACKET_REF,
    ARTIFACT_METRICS_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

if TYPE_CHECKING:
    from pathlib import Path


def _ctx_and_state(
    tmp_path,
    *,
    params: dict[str, object] | None = None,
    governance_report: GovernanceReport | None = None,
):
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_human_review")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.hr.packet"))
    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "status": "ok"}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    governance_ref = store.put_json(
        governance_report or GovernanceReport(verdict="approve", issues=[]),
        PutOptions(
            kind="scientist.governance_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.GovernanceReport", version="1.0"),
        ),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="R_human_review",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_METRICS_REF: metrics_ref},
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
        params={"random_seed": 123, **(params or {})},
    )
    return store, ctx, state


def test_decision_packet_requires_review_refs_when_publication_gate_is_on(tmp_path) -> None:
    _store, ctx, state = _ctx_and_state(
        tmp_path,
        params={"require_human_review_for_publication": True},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "human_review_validation_failed"
    assert "missing_human_review_packet_ref" in outcome.error.details["violations"]
    assert "missing_human_review_decision_ref" in outcome.error.details["violations"]


def test_decision_packet_requires_review_refs_when_governance_is_human_gate(
    tmp_path,
) -> None:
    _store, ctx, state = _ctx_and_state(
        tmp_path,
        governance_report=GovernanceReport(
            verdict="human_gate",
            issues=[
                {
                    "code": "HUMAN_REVIEW_REQUESTED",
                    "message": "Manual release review is required.",
                }
            ],
        ),
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "human_review_validation_failed"
    assert "missing_human_review_packet_ref" in outcome.error.details["violations"]
    assert outcome.error.details["metadata"]["requirement"]["reasons"] == [
        "governance_human_gate",
        "governance_human_gate_issue",
    ]


def test_decision_packet_does_not_admit_unsigned_unassigned_human_review(tmp_path) -> None:
    store, ctx, state = _ctx_and_state(
        tmp_path,
        params={"require_human_review_for_publication": True, "risk_tier": "high"},
    )
    packet = build_review_packet(
        run_id=state.run_id,
        decision_payload={"policy_summary": {"title": "Policy"}},
        risk_tier="high",
    )
    packet_ref = persist_review_packet(store, packet)
    decision = HumanReviewDecision(
        decision_id="decision_1",
        packet_id=packet.packet_id,
        run_id=state.run_id,
        reviewer_id="reviewer_a",
        action=ReviewAction.APPROVE,
        rationale="Reviewed and approved.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the packet.",
        ),
        packet_ref=packet_ref,
    )
    decision_ref = persist_review_decision(store, decision)
    state.artifacts_index[ARTIFACT_HUMAN_REVIEW_PACKET_REF] = packet_ref
    state.artifacts_index[ARTIFACT_HUMAN_REVIEW_DECISION_REF] = decision_ref

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "human_review_validation_failed"
    assert "human_review_admission_not_established" in outcome.error.details["violations"]


@pytest.mark.parametrize(
    ("runtime_risk_tier", "risk_tier_mismatch"),
    [("high", False), ("low", True), (None, True)],
)
def test_fully_bound_signed_candidate_still_requires_institutional_review_custody(
    tmp_path: Path,
    runtime_risk_tier: str | None,
    risk_tier_mismatch: bool,
) -> None:
    params: dict[str, object] = {"require_human_review_for_publication": True}
    if runtime_risk_tier is not None:
        params["risk_tier"] = runtime_risk_tier
    store, ctx, state = _ctx_and_state(
        tmp_path,
        params=params,
    )
    state.execution_profile = "profile_human_review"
    decision_packet_ref = store.put_json(
        {
            "schema_version": "3.4",
            "run_id": state.run_id,
            "runtime_contracts": {"execution_profile": state.execution_profile},
        },
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.DecisionPacket", version="3.4"),
        ),
        return_selected_profile=True,
    )
    packet = build_review_packet(
        run_id=state.run_id,
        risk_tier="high",
        decision_packet_ref=decision_packet_ref,
    )
    assignment = ReviewAssignment(
        assignment_id="assignment_1",
        packet_id=packet.packet_id,
        reviewer_id="reviewer_a",
        status=ReviewAssignmentStatus.COMPLETED,
    )
    packet = packet.model_copy(update={"assignments": [assignment]})
    packet_ref = persist_review_packet(store, packet)
    decision_ref = persist_review_decision(
        store,
        HumanReviewDecision(
            decision_id="decision_1",
            packet_id=packet.packet_id,
            run_id=state.run_id,
            reviewer_id="reviewer_a",
            action=ReviewAction.APPROVE,
            rationale="Candidate reviewer approved the selected policy run.",
            signature=signature_for_decision(
                reviewer_id="reviewer_a",
                attestation="I reviewed the selected decision packet.",
            ),
            packet_ref=packet_ref,
        ),
    )
    key_pair = KeyPair.generate()
    store.sign_artifact(
        decision_ref,
        Ed25519Signer(key_pair.private_key),
        signer_identity="reviewer_a",
    )
    state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = decision_packet_ref
    state.artifacts_index[ARTIFACT_HUMAN_REVIEW_PACKET_REF] = packet_ref
    state.artifacts_index[ARTIFACT_HUMAN_REVIEW_DECISION_REF] = decision_ref

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "human_review_validation_failed"
    violations = outcome.error.details["violations"]
    assert "reviewer_appointment_authority_not_established" in violations
    assert "review_decision_currentness_not_established" in violations
    assert ("review_duration_evidence_not_established" in violations) is (
        runtime_risk_tier == "high"
    )
    assert ("human_review_risk_tier_binding_mismatch" in violations) is risk_tier_mismatch
    assert outcome.error.details["human_review_status"] != "approved"
    assert not outcome.artifacts
    assert "human_review_admission_not_established" in violations
    assert "human_review_subject_ref_mismatch" not in violations
    assert "reviewed_decision_execution_profile_mismatch" not in violations


def test_copied_admitted_diagnostic_cannot_promote_real_decision_packet_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, ctx, state = _ctx_and_state(
        tmp_path,
        params={"require_human_review_for_publication": True, "risk_tier": "high"},
    )
    state.execution_profile = "profile_human_review"
    decision_packet_ref = store.put_json(
        {
            "schema_version": "3.4",
            "run_id": state.run_id,
            "runtime_contracts": {"execution_profile": state.execution_profile},
        },
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.DecisionPacket", version="3.4"),
        ),
        return_selected_profile=True,
    )
    packet = build_review_packet(
        run_id=state.run_id,
        risk_tier="high",
        decision_packet_ref=decision_packet_ref,
    )
    assignment = ReviewAssignment(
        assignment_id="assignment_1",
        packet_id=packet.packet_id,
        reviewer_id="reviewer_a",
        status=ReviewAssignmentStatus.COMPLETED,
    )
    packet = packet.model_copy(update={"assignments": [assignment]})
    packet_ref = persist_review_packet(store, packet)
    decision_ref = persist_review_decision(
        store,
        HumanReviewDecision(
            decision_id="decision_1",
            packet_id=packet.packet_id,
            run_id=state.run_id,
            reviewer_id="reviewer_a",
            action=ReviewAction.APPROVE,
            rationale="Signed candidate for copied-result control.",
            signature=signature_for_decision(
                reviewer_id="reviewer_a",
                attestation="I reviewed the selected decision packet.",
            ),
            packet_ref=packet_ref,
        ),
    )
    key_pair = KeyPair.generate()
    store.sign_artifact(
        decision_ref,
        Ed25519Signer(key_pair.private_key),
        signer_identity="reviewer_a",
    )
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(key_pair.public_key, identity="reviewer_a")
    state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = decision_packet_ref
    state.artifacts_index[ARTIFACT_HUMAN_REVIEW_PACKET_REF] = packet_ref
    state.artifacts_index[ARTIFACT_HUMAN_REVIEW_DECISION_REF] = decision_ref

    admission = resolve_human_review_admission(
        store,
        review_packet_ref=packet_ref,
        review_decision_ref=decision_ref,
        decision_packet_ref=decision_packet_ref,
        run_id=state.run_id,
        context_run_id=ctx.run.run_manifest.run_id,
        execution_profile=state.execution_profile,
        minimum_time_spent_seconds=300,
        expected_risk_tier=ReviewRiskTier.HIGH,
        verifier=verifier,
    )
    assert admission.signature_verification is not None
    assert admission.signature_verification.status.value == "valid"
    forged = replace(
        admission,
        status=HumanReviewAdmissionStatus.ADMITTED,
        violations=(),
    )
    monkeypatch.setattr(
        decision_packet_enrichment,
        "resolve_human_review_admission",
        lambda *_args, **_kwargs: forged,
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "human_review_validation_failed"
    assert outcome.error.details["human_review_status"] != "approved"
    assert "human_review_admission_not_established" in outcome.error.details["violations"]
    assert "reviewer_appointment_authority_not_established" in outcome.error.details["violations"]
    assert "review_decision_currentness_not_established" in outcome.error.details["violations"]
    assert "review_duration_source_not_established" in outcome.error.details["violations"]
    assert "review_duration_evidence_not_established" in outcome.error.details["violations"]
    assert not outcome.artifacts
