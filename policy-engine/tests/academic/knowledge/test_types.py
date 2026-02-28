"""Tests for academic knowledge types."""

from __future__ import annotations

import pytest

from polisyos.academic.knowledge.types import (
    EstimateCandidate,
    ParameterEstimateResult,
    ParameterPrior,
    WorkRecord,
    WorkSearchResult,
)


def test_work_search_result_frozen() -> None:
    result = WorkSearchResult(id="w-1", title="Test Work")
    with pytest.raises(Exception):
        result.title = "Changed"


def test_parameter_prior_as_calibration_prior() -> None:
    prior = ParameterPrior(
        variable="test_elasticity",
        prior_mean=0.35,
        prior_std=0.12,
        prior_low=0.1,
        prior_high=0.6,
        n_studies=10,
        best_design="rct",
        as_calibration_prior={"distribution": "normal", "mean": 0.35, "std": 0.12},
    )
    assert prior.as_calibration_prior["distribution"] == "normal"
    assert prior.as_calibration_prior["mean"] == 0.35
    assert prior.as_calibration_prior["std"] == 0.12


def test_estimate_candidate_defaults() -> None:
    est = EstimateCandidate(value=0.5, pattern_name="elasticity_of")
    assert est.ci_low is None
    assert est.ci_high is None
    assert est.std_error is None
    assert est.confidence == 0.5
    assert est.variable_hint == ""


def test_work_record_fields() -> None:
    record = WorkRecord(
        id="w-1",
        title="Minimum Wage Effects",
        abstract="We study the effect of minimum wage on employment.",
        study_design="did",
        trust_score=0.75,
    )
    assert record.title == "Minimum Wage Effects"
    assert record.study_design == "did"
    assert record.trust_score == 0.75
    assert record.estimates == []
    assert record.causal_claims == []


def test_parameter_estimate_result_extra_forbid() -> None:
    with pytest.raises(Exception):
        ParameterEstimateResult(
            variable_name="test",
            estimate=0.5,
            unknown_field="value",
        )
