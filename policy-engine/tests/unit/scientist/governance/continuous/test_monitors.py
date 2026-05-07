from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.governance.continuous.monitors import (
    DecisionValidityStatus,
    aggregate_validity_status,
    build_drift_monitor_event,
    recommend_validity_action,
)


def _ref(seed: str, *, kind: str = "scientist.decision_packet") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def test_drift_warning_triggers_human_review() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1"),
        event_type="fairness_drift",
        severity="warning",
        reason="Subgroup false-block rate exceeded warning threshold.",
        affected_claim_ids=["claim_fairness"],
        metric_name="false_block_rate",
        observed_value=0.17,
        threshold=0.1,
    )

    recommendation = recommend_validity_action(event)

    assert recommendation.status is DecisionValidityStatus.REVIEW_REQUIRED
    assert recommendation.recommended_action == "human_review"
    assert recommendation.human_review_required is True


def test_drift_block_triggers_reissue_assessment() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1"),
        event_type="calibration_drift",
        severity="block",
        reason="Calibration drift exceeded release envelope.",
        affected_claim_ids=["claim_calibration"],
    )

    recommendation = recommend_validity_action(event)

    assert recommendation.reissue_recommended is True
    assert recommendation.human_review_required is True
    assert aggregate_validity_status([recommendation]) is DecisionValidityStatus.REVIEW_REQUIRED


def test_info_monitor_event_keeps_artifact_monitoring() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1"),
        event_type="policy_context_drift",
        severity="info",
        reason="Related statute is being watched but did not change.",
    )

    recommendation = recommend_validity_action(event)

    assert recommendation.status is DecisionValidityStatus.MONITORING
    assert recommendation.recommended_action == "continue_monitoring"
