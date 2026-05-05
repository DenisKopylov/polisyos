from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.agent.supervisor_eval import (
    SupervisorEvalMetrics,
    evaluate_supervisor_promotion,
    supervisor_default_blockers,
)


def _ref(hex_char: str = "a") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{hex_char * 64}",
        kind="scientist.agent.supervisor_eval",
        media_type="application/json",
    )


def test_supervisor_promotion_requires_handoff_eval_ref() -> None:
    metrics = SupervisorEvalMetrics(
        case_count=5,
        delegation_success_rate=1.0,
        quorum_consistency_rate=0.95,
        citation_coverage=0.9,
        budget_violation_rate=0.0,
    )

    evaluation = evaluate_supervisor_promotion(metrics)

    assert evaluation.default_enable_ready is False
    assert "missing_supervisor_handoff_eval_ref" in evaluation.blockers


def test_supervisor_promotion_passes_with_handoff_and_thresholds() -> None:
    metrics = SupervisorEvalMetrics(
        handoff_eval_ref=_ref(),
        case_count=5,
        delegation_success_rate=1.0,
        quorum_consistency_rate=0.95,
        citation_coverage=0.9,
        budget_violation_rate=0.0,
    )

    assert supervisor_default_blockers(metrics) == []
    assert evaluate_supervisor_promotion(metrics).default_enable_ready is True
