"""Finite stress samples cannot quantify model uncertainty or source authority."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.ir import UncertaintyType
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
    _level5_uncertainty_envelope,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelStageResult
from polisyos.scientist.methods.search.objective import ObjectiveScoreStatus
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
)


def _scope_shaped_report(score: float | None = 1.0) -> StressTestReport:
    return StressTestReport(
        report_id="scope-shaped-without-source",
        total_scenarios_evaluated=2,
        robustness_score=score,
        score_status="available",
        score_profile="finite_binary_scenario_v1",
        score_predicate_status="recomputed",
        set_adequacy_status="complete",
        metadata={
            "attempted": 2,
            "finite_evaluated": 2,
            "violated_scenarios": 0,
            "unknown_or_nonfinite": 0,
            "planned_scenarios": 2,
            "completeness": True,
            "score_scope": "observed_finite_scenarios",
            "score_formula": "(finite_evaluated-violated_scenarios)/finite_evaluated",
        },
    )


@pytest.mark.parametrize("score", [None, 0.0, 0.25, 1.0, float("nan")])
def test_stress_score_does_not_establish_model_uncertainty(score: float | None) -> None:
    envelope = _level5_uncertainty_envelope(
        prior_result=None,
        holdout_delta=None,
        stress_report=_scope_shaped_report(score),
        platform_meta=None,
    )
    model = envelope.uncertainties[UncertaintyType.MODEL]
    assert model == UncertaintyEnvelope.unknown().uncertainties[UncertaintyType.MODEL]


def test_stress_sample_preserves_prior_model_estimate_and_its_provenance() -> None:
    prior_model = UncertaintyEstimate(
        level=0.37,
        source="prior candidate assessment",
        quantification_method="consumer_declared",
        is_reducible=False,
        recommended_action="Review the prior assessment's declared basis.",
    )
    prior = FunnelStageResult(
        policy_candidate={},
        objective_value=None,
        is_promising=True,
        stage_name="prior",
        uncertainty_envelope=UncertaintyEnvelope.unknown().with_update(
            UncertaintyType.MODEL, prior_model
        ),
    )
    envelope = _level5_uncertainty_envelope(
        prior_result=prior,
        holdout_delta=None,
        stress_report=_scope_shaped_report(),
        platform_meta=None,
    )
    assert envelope.uncertainties[UncertaintyType.MODEL] == prior_model


@pytest.mark.parametrize(
    "context",
    [
        {},
        {"stress_test_report": _scope_shaped_report()},
        {"stress_test_report_ref": {"not_an_artifact_ref": True}},
    ],
)
def test_level5_keeps_objective_status_separate_from_stress_status(context: dict) -> None:
    result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate({}, context)
    assert result.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert result.objective_value is None
    assert result.feedback["stress_observed_sample_assessment"]["status"] == "unassessed"
    assert result.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1.0


@pytest.mark.parametrize(
    "metadata_change",
    [{}, {"finite_evaluated": True}, {"completeness": "true"}, {"violated_scenarios": 3}],
)
def test_scope_shaped_metadata_does_not_replace_resolved_source(metadata_change: dict) -> None:
    report = _scope_shaped_report()
    report.metadata.update(metadata_change)
    result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {}, {"stress_test_report": report}
    )
    assessment = result.feedback["stress_observed_sample_assessment"]
    assert assessment["status"] == "unassessed"
    assert assessment["population_probability"] == "not_established"
    assert assessment["model_uncertainty"] == "not_established"
    assert "observed_fraction" not in assessment
    assert result.feedback["stress_robust"] is None
    assert result.terminal_action == "defer_to_human"


def test_fresh_consumer_rejects_persisted_same_shape_score_without_source(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report_ref = store.put_json(
        _scope_shaped_report(),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert isinstance(report_ref, ArtifactRef)
    result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {}, {"store": FileSystemCAS(store.root), "stress_test_report_ref": report_ref}
    )
    assert result.feedback["stress_score_status"] == "invalid"
    assert result.feedback["stress_observed_sample_assessment"]["status"] == "unassessed"
    assert result.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1.0
    assert any(card.failure_type == "stress_score_invalid" for card in result.failure_cards)


def test_partial_report_keeps_completeness_separate_from_unavailable_fraction(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report_ref = store.put_json(
        StressTestReport(
            report_id="incomplete-without-resolved-counts",
            score_profile="finite_binary_scenario_v1",
            score_status="partial",
        ),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {}, {"store": store, "stress_test_report_ref": report_ref}
    )
    assessment = result.feedback["stress_observed_sample_assessment"]
    assert assessment["status"] == "partial"
    assert assessment["completeness"] is False
    assert assessment["score_scope"] == "not_established"
    assert "observed_fraction" not in assessment
    assert result.feedback["stress_score_value"] is None
    assert result.feedback["stress_robust"] is None
    assert result.terminal_action == "defer_to_human"


def test_funnel_aggregate_does_not_promote_sample_fraction_to_model_certainty() -> None:
    funnel = FunnelOrchestrator([Level5RefutationGovernanceStage(require_hidden_holdout=False)])
    ticket = funnel.submit({}, {"stress_test_report": _scope_shaped_report()})
    outcome = funnel.advance(ticket, policy="full")
    assert outcome.final_result is not None
    assert outcome.final_result.feedback["stress_observed_sample_assessment"]["status"] == (
        "unassessed"
    )
    assert outcome.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1.0
    historical = outcome.final_result.feedback["uncertainty_historical_max"]
    assert historical["uncertainties"]["model"]["level"] == 1.0
