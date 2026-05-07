from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.governance.human_review.audit import signature_for_decision
from polisyos.scientist.governance.human_review.decisions import persist_review_decision
from polisyos.scientist.governance.human_review.models import HumanReviewDecision, ReviewAction
from polisyos.scientist.governance.human_review.packets import (
    build_review_packet,
    persist_review_packet,
)
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
    BuildDecisionPacketNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_HUMAN_REVIEW_DECISION_REF,
    ARTIFACT_HUMAN_REVIEW_PACKET_REF,
    ARTIFACT_METRICS_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


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
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
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


def test_decision_packet_includes_approved_human_review_refs(tmp_path) -> None:
    store, ctx, state = _ctx_and_state(
        tmp_path,
        params={"require_human_review_for_publication": True},
    )
    packet = build_review_packet(
        run_id=state.run_id,
        decision_payload={"policy_summary": {"title": "Policy"}},
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

    assert outcome.status == "ok"
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    assert payload["human_review"]["required"] is True
    assert payload["human_review"]["status"] == "approved"
    assert payload["artifacts"][ARTIFACT_HUMAN_REVIEW_PACKET_REF] == str(packet_ref.artifact_id)
    assert payload["artifacts"][ARTIFACT_HUMAN_REVIEW_DECISION_REF] == str(decision_ref.artifact_id)
