"""Selected-score status must survive the funnel terminal boundary."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelStage, FunnelStageResult
from polisyos.scientist.methods.search.objective import (
    GDPGrowthObjective,
    ObjectiveScoreStatus,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
    _serialize_funnel_outcome,
)


@pytest.mark.parametrize(
    ("score_status", "source", "reported_source", "expected_action", "expected_replayed_status"),
    [
        (
            ObjectiveScoreStatus.AVAILABLE,
            {"gdp_change": 0.0, "metric_units": {"gdp_change": "fixture-unit"}},
            None,
            "complete",
            ObjectiveScoreStatus.AVAILABLE,
        ),
        (
            ObjectiveScoreStatus.UNAVAILABLE,
            {"gdp_change": 0.0, "metric_units": {}},
            None,
            "defer",
            ObjectiveScoreStatus.UNAVAILABLE,
        ),
        (
            ObjectiveScoreStatus.INVALID,
            {"gdp_change": "malformed", "metric_units": {"gdp_change": "fixture-unit"}},
            None,
            "reject",
            ObjectiveScoreStatus.INVALID,
        ),
        (
            ObjectiveScoreStatus.NOT_ESTABLISHED,
            {},
            None,
            "defer",
            ObjectiveScoreStatus.NOT_ESTABLISHED,
        ),
        (
            ObjectiveScoreStatus.INVALID,
            {"gdp_change": "malformed", "metric_units": {}},
            {"gdp_change": 0.0, "metric_units": {}},
            "reject",
            ObjectiveScoreStatus.INVALID,
        ),
    ],
    ids=[
        "available-zero",
        "unavailable",
        "invalid-present",
        "not-established",
        "unavailable-basis-mutated-to-invalid",
    ],
)
@pytest.mark.parametrize(
    "explicit_complete", [False, True], ids=["implicit-finalizer", "explicit-complete"]
)
def test_terminal_completion_uses_source_recomputed_score_state(
    score_status: ObjectiveScoreStatus,
    source: dict[str, object],
    reported_source: dict[str, object] | None,
    expected_action: str,
    expected_replayed_status: ObjectiveScoreStatus,
    explicit_complete: bool,
) -> None:
    """Exercise status transitions at both terminalization routes and preserve zero."""
    assessment = None
    if score_status is not ObjectiveScoreStatus.NOT_ESTABLISHED:
        assessment_source = reported_source if reported_source is not None else source
        assessment = (
            GDPGrowthObjective(expected_unit="fixture-unit")
            .evaluate(assessment_source)
            .score_assessment
        )
        assert assessment is not None
        assert assessment.status is score_status or (
            score_status is ObjectiveScoreStatus.INVALID
            and reported_source is not None
            and assessment.status is ObjectiveScoreStatus.UNAVAILABLE
        )

    stage = MagicMock(spec=FunnelStage)
    stage.fidelity_level = 6
    stage.stage_name = "selected-score-terminal-control"
    stage.estimated_cost_usd = 0.0
    stage.evaluate.return_value = FunnelStageResult(
        policy_candidate={"candidate": "fixture"},
        objective_value=(
            assessment.value
            if assessment is not None and assessment.status is ObjectiveScoreStatus.AVAILABLE
            else None
        ),
        is_promising=True,
        stage_name="selected-score-terminal-control",
        score_status=score_status,
        score_assessment=assessment,
        simulation_results=source,
        fidelity_level=6,
        terminal_action="complete" if explicit_complete else None,
    )
    orchestrator = FunnelOrchestrator([stage])

    outcome = orchestrator.advance(orchestrator.submit({"candidate": "fixture"}, {}))

    assert outcome.completed is True
    assert outcome.final_action == expected_action
    assert outcome.final_result is not None
    assert outcome.final_result.score_status is expected_replayed_status
    assert outcome.trace[-1].score_status is expected_replayed_status
    surface = _serialize_funnel_outcome(outcome)
    assert surface["final_action"] == expected_action
    assert surface["trace"][-1]["score_admission"]["status"] == expected_replayed_status.value
    assert "source_values" not in surface["trace"][-1]["score_admission"]
    if expected_replayed_status is ObjectiveScoreStatus.AVAILABLE:
        assert outcome.final_result.objective_value == 0.0
        assert outcome.final_result.score_admission is not None
        assert outcome.final_result.score_admission.status is ObjectiveScoreStatus.AVAILABLE
    elif expected_replayed_status is ObjectiveScoreStatus.INVALID:
        assert outcome.final_result.objective_value is None
        assert outcome.final_result.score_admission is not None
        assert outcome.final_result.score_admission.status is ObjectiveScoreStatus.INVALID
        if reported_source is not None:
            assert outcome.final_result.score_admission.reported_assessment is assessment
            assert outcome.final_result.score_admission.recomputed_assessment is not None
            assert (
                outcome.final_result.score_admission.recomputed_assessment.status
                is ObjectiveScoreStatus.INVALID
            )
    else:
        assert outcome.final_result.objective_value is None
