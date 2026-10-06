"""Observed stress fractions do not establish model uncertainty."""

import pytest

from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.uncertainty import UncertaintyType


def report(*, finite, unknown, planned, violated=0):
    attempted = finite + unknown
    complete = planned > 0 and attempted == finite == planned
    return StressTestReport(
        report_id="stress-1",
        total_scenarios_evaluated=attempted,
        robustness_score=(finite - violated) / finite if finite else None,
        set_adequacy_status="complete" if complete else "partial",
        metadata={
            "attempted": attempted,
            "finite_evaluated": finite,
            "violated_scenarios": violated,
            "unknown_or_nonfinite": unknown,
            "planned_scenarios": planned,
            "completeness": complete,
            "score_scope": "observed_finite_scenarios",
            "score_formula": "(finite_evaluated-violated_scenarios)/finite_evaluated",
        },
    )


@pytest.mark.parametrize(
    ("finite", "unknown", "planned", "status"),
    [
        (2, 0, 2, "complete"),
        (1, 1, 2, "partial"),
        (1, 0, 2, "partial"),
        (0, 2, 2, "partial"),
        (0, 0, 0, "partial"),
    ],
)
def test_real_level5_consumes_adequacy_scope_without_probability_claim(
    finite, unknown, planned, status
):
    stress = report(finite=finite, unknown=unknown, planned=planned)
    stage = Level5RefutationGovernanceStage(require_hidden_holdout=False)
    result = stage.evaluate({"candidate_id": "candidate-1"}, {"stress_test_report": stress})
    assessment = result.feedback["stress_observed_sample_assessment"]
    assert assessment["status"] == status
    assert assessment["observed_fraction"] == stress.robustness_score
    assert assessment["population_probability"] == "not_established"
    model = result.uncertainty_envelope.uncertainties[UncertaintyType.MODEL]
    assert model.level == 1
    assert model.quantification_method == "stress_sample_does_not_establish_model_uncertainty"
    assert result.feedback["stress_robust"] is (True if status == "complete" else None)
    assert result.is_promising
    assert any(
        card.failure_type == "stress_observed_sample_incomplete" for card in result.failure_cards
    ) is (status != "complete")


@pytest.mark.parametrize(
    "corrupt",
    [
        {},
        {"finite_evaluated": True},
        {"completeness": "true"},
        {"violated_scenarios": 3},
        {"score_scope": "population_probability"},
    ],
)
def test_missing_or_malformed_scope_is_unassessed_even_with_score_one(corrupt):
    stress = report(finite=2, unknown=0, planned=2)
    stress.metadata = {} if not corrupt else {**stress.metadata, **corrupt}
    stage = Level5RefutationGovernanceStage(require_hidden_holdout=False)
    result = stage.evaluate({}, {"stress_test_report": stress})
    assert result.feedback["stress_observed_sample_assessment"]["status"] == "unassessed"
    assert result.feedback["stress_robust"] is None
    assert result.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1


def test_actual_stage_and_funnel_aggregate_keep_observed_complete_unknown_model_distinct():
    stress = report(finite=2, unknown=0, planned=2)
    funnel = FunnelOrchestrator([Level5RefutationGovernanceStage(require_hidden_holdout=False)])
    ticket = funnel.submit({}, {"stress_test_report": stress})
    outcome = funnel.advance(ticket, policy="full")
    assert (
        outcome.final_result.feedback["stress_observed_sample_assessment"]["status"] == "complete"
    )
    current = outcome.final_result.feedback["uncertainty_current"]["uncertainties"]["model"]
    historical = outcome.final_result.feedback["uncertainty_historical_max"]["uncertainties"][
        "model"
    ]
    assert current["level"] == historical["level"] == 1
    assert outcome.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1
    # Old complement transformation retains the score/status markers, but fails
    # the consumer invariant even on a complete observed sample.
    with pytest.raises(AssertionError):
        assert 1 - stress.robustness_score == 1
