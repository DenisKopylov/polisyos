"""FUN-03 regression witnesses for calibration and promotion boundaries."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir import UncertaintyType
from polisyos.scientist.methods.search.calibration_report import (
    FunnelCalibrationReport,
    load_funnel_calibration_report,
    persist_funnel_calibration_report,
)
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
from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
from polisyos.scientist.orchestration.engine.state import ExperimentState


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
    return float(payload["uncertainties"][uncertainty_type.value]["level"])


def _artifact_ref(hex_digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{hex_digit * 64}",
        kind="test",
        media_type="application/json",
    )


def test_same_scope_refinement_is_current_while_history_keeps_unknown_risk() -> None:
    historical_unknown = UncertaintyEnvelope.unknown(source="deterministic gate")
    refined = _envelope(statistical=0.1, model=0.8)

    orchestrator = FunnelOrchestrator(
        [
            _stage(0, _stage_result(0, historical_unknown)),
            _stage(4, _stage_result(4, refined)),
        ]
    )
    ticket = orchestrator.submit({"candidate_id": "fun-03"}, {"domain": "same-scope"})
    outcome = orchestrator.advance(ticket, policy="full")

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


@pytest.mark.parametrize(
    "scope_key",
    ["subject_id", "value_slot", "input_signature", "procedure_id", "population_scope"],
)
def test_scope_identity_prevents_cross_scope_continuation(scope_key: str) -> None:
    historical_unknown = UncertaintyEnvelope.unknown(source="scope A not assessed")
    refined = _envelope(statistical=0.1, model=0.8)
    stage = _stage(4, _stage_result(4, historical_unknown))
    stage.evaluate.side_effect = [
        _stage_result(4, historical_unknown),
        _stage_result(4, refined),
    ]
    orchestrator = FunnelOrchestrator([stage])
    candidate = {"candidate_id": "fun-03"}
    scope_a = {
        "subject_id": "subject-a",
        "value_slot": "value-a",
        "input_signature": "inputs-a",
        "procedure_id": "procedure-a",
        "population_scope": "population-a",
    }
    scope_b = {**scope_a, scope_key: f"{scope_a[scope_key]}-other"}

    ticket_a = orchestrator.submit(candidate, scope_a)
    outcome_a = orchestrator.advance(ticket_a, policy="full")
    ticket_b = orchestrator.submit(candidate, scope_b)

    assert ticket_b is not ticket_a
    assert ticket_b.stage_results == {}
    outcome_b = orchestrator.advance(ticket_b, policy="full")
    assert stage.evaluate.call_count == 2
    assert outcome_a.uncertainty_envelope.uncertainties[
        UncertaintyType.STATISTICAL
    ].level == 1.0
    assert outcome_b.final_result is not None
    assert outcome_b.final_result.uncertainty_envelope.uncertainties[
        UncertaintyType.STATISTICAL
    ].level == pytest.approx(0.1)


def test_empty_tracker_has_one_explicit_not_established_routing_state() -> None:
    tracker = CorrelationTracker()

    metrics = tracker.compute_metrics()

    assert metrics["sample_count"] == 0
    assert metrics["calibration_state"] == "not_established"
    assert metrics["routing_mode"] == tracker.routing_mode()
    assert metrics["routing_mode"] == "no_promotion"
    assert metrics["promotion_ban_active"] is False
    assert tracker.drift_alerts() == []


def test_persisted_empty_report_fails_closed_over_stale_normal_mode(tmp_path) -> None:
    state = ExperimentState(run_id="fun-03-report-run")
    store = FileSystemCAS(tmp_path / ".polisyos")
    report = FunnelCalibrationReport(
        current_mode="normal",
        routing_health={"sample_count": 0, "promotion_ban_active": False},
    )
    report_ref = persist_funnel_calibration_report(store, report)
    loaded_report = load_funnel_calibration_report(store, report_ref)

    metrics = runtime._resolve_runtime_correlation_metrics(state, loaded_report)

    assert metrics["sample_count"] == 0
    assert metrics["calibration_state"] == "not_established"
    assert metrics["routing_mode"] == "no_promotion"
    assert runtime._resolve_degradation_mode(
        state,
        calibration_report=loaded_report,
    ) == "no_promotion"


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


def test_production_owner_recheck_requires_explicit_write_permission(monkeypatch) -> None:
    candidate_ref = _artifact_ref("a")
    evidence_ref = _artifact_ref("b")
    state = ExperimentState(run_id="fun-03-owner-run")
    class _EvidenceBundle:
        def __init__(self, bound_candidate_ref: ArtifactRef) -> None:
            self.candidate_ref = bound_candidate_ref
            self.compatible_runs: list[str] = []

        def assert_compatible_with_run(self, run_id: str) -> None:
            self.compatible_runs.append(run_id)

    bundle = _EvidenceBundle(candidate_ref)
    monkeypatch.setattr(runtime, "load_promotion_evidence_bundle", lambda _store, _ref: bundle)
    context = {
        "funnel_degradation_mode": "normal",
        "policy_candidate_ref": candidate_ref,
        "promotion_evidence_bundle_ref": evidence_ref,
    }
    ctx = MagicMock(store=MagicMock())

    assert runtime._policy_promotion_owner_recheck(ctx, state, candidate_ref, context) is False
    assert runtime._policy_promotion_owner_recheck(
        ctx,
        state,
        candidate_ref,
        {**context, "promotion_write_allowed": False},
    ) is False
    assert runtime._policy_promotion_owner_recheck(
        ctx,
        state,
        candidate_ref,
        {**context, "promotion_write_allowed": True},
    ) is True
    assert bundle.compatible_runs == [state.run_id]


def test_orchestrator_honors_persisted_no_promotion_projection_without_tracker() -> None:
    calls: list[str] = []

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    orchestrator = FunnelOrchestrator(
        [Level6PromotionStage(promotion_runner=runner)]
    )
    ticket = orchestrator.submit(
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
    outcome = orchestrator.advance(ticket, policy="full")

    assert calls == []
    assert outcome.degradation_mode == "no_promotion"
    assert outcome.final_action == "defer_to_human"
