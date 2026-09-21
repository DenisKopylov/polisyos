"""FUN-03 regression witnesses for calibration and promotion boundaries."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from polisyos.ir import UncertaintyType
from polisyos.scientist.methods.search.funnel.level6_promotion import (
    Level6PromotionStage,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    UncertaintyEnvelope,
    UncertaintyEstimate,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker


def _stage(
    level: int,
    result: FunnelStageResult,
) -> MagicMock:
    stage = MagicMock(spec=FunnelStage)
    stage.fidelity_level = level
    stage.stage_name = result.stage_name
    stage.estimated_cost_usd = 0.1
    stage.evaluate.return_value = result
    return stage


def _envelope(*, statistical: float, model: float) -> UncertaintyEnvelope:
    envelope = UncertaintyEnvelope.unknown(source="FUN-03 witness")
    return envelope.with_update(
        UncertaintyType.STATISTICAL,
        UncertaintyEstimate(
            level=statistical,
            source="same-scope statistical witness",
            quantification_method="test_measurement",
            is_reducible=True,
        ),
    ).with_update(
        UncertaintyType.MODEL,
        UncertaintyEstimate(
            level=model,
            source="independent model-risk witness",
            quantification_method="test_measurement",
            is_reducible=True,
        ),
    )


def _stage_result(level: int, envelope: UncertaintyEnvelope) -> FunnelStageResult:
    return FunnelStageResult(
        policy_candidate={"candidate_id": "fun-03"},
        objective_value=0.5,
        is_promising=True,
        stage_name=f"L{level}",
        uncertainty_envelope=envelope,
        fidelity_level=level,
    )


def _uncertainty_level(payload: dict[str, Any], uncertainty_type: UncertaintyType) -> float:
    return float(payload[uncertainty_type.value]["level"])


def test_same_scope_refinement_is_current_while_history_keeps_unknown_risk() -> None:
    historical_unknown = UncertaintyEnvelope.unknown(source="deterministic gate")
    refined = _envelope(statistical=0.1, model=0.8)

    outcome = FunnelOrchestrator(
        [
            _stage(0, _stage_result(0, historical_unknown)),
            _stage(4, _stage_result(4, refined)),
        ]
    ).evaluate({"candidate_id": "fun-03"}, {"domain": "same-scope"})

    assert outcome.uncertainty_envelope.uncertainties[UncertaintyType.STATISTICAL].level == 1.0
    current = outcome.final_result
    assert current is not None
    assert current.uncertainty_envelope.uncertainties[
        UncertaintyType.STATISTICAL
    ].level == pytest.approx(0.1)
    assert current.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == pytest.approx(
        0.8
    )
    assert _uncertainty_level(
        current.feedback["uncertainty_historical_max"], UncertaintyType.STATISTICAL
    ) == 1.0
    assert _uncertainty_level(
        current.feedback["uncertainty_current"], UncertaintyType.STATISTICAL
    ) == pytest.approx(0.1)
    assert _uncertainty_level(
        outcome.stage_results[4].feedback["uncertainty_current"], UncertaintyType.STATISTICAL
    ) == pytest.approx(0.1)


def test_empty_tracker_has_one_explicit_not_established_routing_state() -> None:
    tracker = CorrelationTracker()

    metrics = tracker.compute_metrics()

    assert metrics["sample_count"] == 0
    assert metrics["calibration_state"] == "not_established"
    assert metrics["routing_mode"] == tracker.routing_mode()
    assert metrics["routing_mode"] == "no_promotion"
    assert metrics["promotion_ban_active"] is False
    assert tracker.drift_alerts() == []


def test_statistically_bad_tracker_is_observed_drift_not_empty_state() -> None:
    tracker = CorrelationTracker(drift_window_size=5)
    for index in range(5):
        tracker.record(
            MagicMock(
                predicted_score=float(index), objective_value=float(index), is_promising=True
            ),
            MagicMock(
                actual_score=float(5 - index),
                objective_value=float(5 - index),
                is_promising=True,
            ),
            f"fun-03-{index}",
        )

    metrics = tracker.compute_metrics()

    assert metrics["calibration_state"] == "observed"
    assert metrics["sample_count"] == 5
    assert metrics["routing_mode"] == "no_promotion"
    assert tracker.promotion_ban_active() is True


def test_level6_degradation_preflight_reads_existing_payload_without_runner() -> None:
    calls: list[str] = []
    payload = {"decision": "complete", "reason": "already calculated"}

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    result = Level6PromotionStage(promotion_runner=runner).evaluate(
        {"candidate_id": "fun-03"},
        {
            "funnel_degradation_mode": "no_promotion",
            "promotion_result": payload,
        },
    )

    assert calls == []
    assert result.terminal_action == "defer_to_human"
    assert result.feedback["promotion_result"] == payload
    assert result.feedback["promotion_result_read_only"] is True


def test_level6_owner_recheck_happens_before_effectful_runner() -> None:
    calls: list[str] = []

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    result = Level6PromotionStage(
        promotion_runner=runner,
        promotion_owner_recheck=lambda _candidate, _context: False,
    ).evaluate({"candidate_id": "fun-03"}, {"funnel_degradation_mode": "normal"})

    assert calls == []
    assert result.terminal_action == "defer_to_human"
    assert any(
        card.failure_type == "promotion_owner_recheck_failed" for card in result.failure_cards
    )


def test_level6_normal_path_calls_runner_after_owner_recheck() -> None:
    calls: list[str] = []

    def recheck(_candidate: dict[str, Any], _context: dict[str, Any]) -> bool:
        calls.append("recheck")
        return True

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    result = Level6PromotionStage(
        promotion_runner=runner,
        promotion_owner_recheck=recheck,
    ).evaluate({"candidate_id": "fun-03"}, {"funnel_degradation_mode": "normal"})

    assert calls == ["recheck", "runner"]
    assert result.terminal_action == "complete"


def test_orchestrator_honors_persisted_no_promotion_projection_without_tracker() -> None:
    calls: list[str] = []

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    outcome = FunnelOrchestrator(
        [Level6PromotionStage(promotion_runner=runner)]
    ).evaluate(
        {"candidate_id": "fun-03"},
        {
            "funnel_degradation_mode": "no_promotion",
            "correlation_metrics": {
                "sample_count": 0,
                "calibration_state": "not_established",
                "routing_mode": "no_promotion",
            },
        },
    )

    assert calls == []
    assert outcome.degradation_mode == "no_promotion"
    assert outcome.final_action == "defer_to_human"
