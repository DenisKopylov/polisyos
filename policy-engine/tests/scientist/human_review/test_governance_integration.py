from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport, GovernanceReportLinks
from polisyos.scientist.human_review.audit import signature_for_decision
from polisyos.scientist.human_review.models import HumanReviewDecision, ReviewAction
from polisyos.scientist.human_review.oversight_policy import (
    apply_human_review_to_governance_report,
)
from polisyos.scientist.human_review.packets import build_review_packet
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_HUMAN_REVIEW_DECISION_REF,
    ARTIFACT_HUMAN_REVIEW_PACKET_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def _ref(ch: str, *, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + ch * 64,
        kind=kind,
        media_type="application/json",
    )


def test_governance_report_links_include_review_packet_and_decision_refs() -> None:
    packet_ref = _ref("1", kind="scientist.human_review_packet")
    decision_ref = _ref("2", kind="scientist.human_review_decision")
    report = GovernanceReport(
        verdict="human_gate",
        issues=[],
        links=GovernanceReportLinks(human_review_packet_ref=packet_ref),
    )

    assert report.links.human_review_packet_ref == packet_ref
    assert report.model_dump(mode="json")["links"]["human_review_packet_ref"][
        "artifact_id"
    ] == str(packet_ref.artifact_id)

    packet = build_review_packet(run_id="run_1")
    decision = HumanReviewDecision(
        decision_id="decision_1",
        packet_id=packet.packet_id,
        run_id="run_1",
        reviewer_id="reviewer_a",
        action=ReviewAction.APPROVE,
        rationale="Reviewed.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the packet.",
        ),
    )
    updated = apply_human_review_to_governance_report(
        report,
        review_packet_ref=packet_ref,
        review_decision_ref=decision_ref,
        decisions=[decision],
        packet=packet,
    )

    assert updated.links.human_review_decision_ref == decision_ref
    assert "human_review_status:approved" in updated.notes


def test_run_governance_includes_review_refs_from_state(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_review_refs")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.hr.gov"))
    packet_ref = _ref("3", kind="scientist.human_review_packet")
    decision_ref = _ref("4", kind="scientist.human_review_decision")
    state = ExperimentState(
        run_id="R_review_refs",
        artifacts_index={
            ARTIFACT_HUMAN_REVIEW_PACKET_REF: packet_ref,
            ARTIFACT_HUMAN_REVIEW_DECISION_REF: decision_ref,
        },
        params={"governance_profile": "fast"},
    )

    outcome = RunGovernanceNode().execute(ctx, state)
    report_ref = outcome.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))

    assert outcome.status == "ok"
    assert report["links"]["human_review_packet_ref"]["artifact_id"] == str(
        packet_ref.artifact_id
    )
    assert report["links"]["human_review_decision_ref"]["artifact_id"] == str(
        decision_ref.artifact_id
    )
