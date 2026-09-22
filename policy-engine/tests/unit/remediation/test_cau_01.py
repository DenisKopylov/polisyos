"""Regression witnesses for the bounded CAU-01 causal-method repair."""

from __future__ import annotations

import numpy as np
import pytest
from statsmodels.api import OLS
from statsmodels.stats.sandwich_covariance import cov_cluster

from polisyos.foundry.methods.catalog.causal.did import (
    DifferenceInDifferences,
    StandardDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    PanelObservationalData,
    RDDObservationalData,
)
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.ir.analytics.causal import EstimationStatus


def _panel(*, duplicated_periods: bool = False) -> PanelObservationalData:
    outcome = np.array(
        [
            [1.0, 2.5, 7.0, 8.5],
            [2.0, 1.0, 5.5, 7.5],
            [0.0, 1.5, 2.0, 3.0],
            [1.0, 0.5, 3.5, 4.0],
        ]
    )
    if duplicated_periods:
        outcome = np.repeat(outcome, 2, axis=1)
    return PanelObservationalData(
        outcome=outcome,
        treatment=np.array([1, 1, 0, 0]),
        time_treatment=4 if duplicated_periods else 2,
        unit_ids=np.array(["treated-a", "treated-b", "control-a", "control-b"]),
    )


def _rdd() -> RDDObservationalData:
    running = np.linspace(-1.0, 1.0, 80)
    outcome = 1.0 + 0.35 * running + 2.0 * (running >= 0.0) + 0.1 * np.sin(
        np.arange(running.size)
    )
    return RDDObservationalData(outcome=outcome, running_variable=running, cutoff=0.0)


def _report(output: dict[str, object]):
    return output["report"]


def test_cau_01_standard_did_rejects_zero_pre_period() -> None:
    """A standard DiD cannot certify a contrast without a pre-treatment period."""

    data = _panel()
    invalid = PanelObservationalData(
        outcome=data.outcome,
        treatment=data.treatment,
        time_treatment=0,
        unit_ids=data.unit_ids,
    )

    report = _report(StandardDifferenceInDifferences.pure_step(invalid, {}))

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "standard DiD requires at least one pre-treatment period"
    assert report.point_estimate is None


def test_cau_01_confidence_level_changes_did_interval() -> None:
    """Normal critical values must follow the requested DiD confidence level."""

    data = _panel()
    intervals = {
        level: _report(
            StandardDifferenceInDifferences.pure_step(data, {"confidence_level": level})
        ).confidence_interval
        for level in (0.80, 0.95, 0.99)
    }

    assert intervals[0.80] != intervals[0.95]
    assert intervals[0.95] != intervals[0.99]
    assert (intervals[0.99][1] - intervals[0.99][0]) > (
        intervals[0.80][1] - intervals[0.80][0]
    )


def test_cau_01_confidence_level_changes_rdd_interval() -> None:
    """Normal critical values must follow the requested RDD confidence level."""

    data = _rdd()
    params = {"bandwidth": 0.8, "kernel": "triangular", "manipulation_test": False}
    intervals = {
        level: _report(
            RegressionDiscontinuity.pure_step(data, {**params, "confidence_level": level})
        ).confidence_interval
        for level in (0.80, 0.95, 0.99)
    }

    assert intervals[0.80] != intervals[0.95]
    assert intervals[0.95] != intervals[0.99]
    assert (intervals[0.99][1] - intervals[0.99][0]) > (
        intervals[0.80][1] - intervals[0.80][0]
    )


def test_cau_01_cluster_covariance_uses_unit_ids() -> None:
    """The declared unit-cluster profile must differ from row-wise HC1 when IDs repeat."""

    data = _panel()
    hc1 = _report(StandardDifferenceInDifferences.pure_step(data, {"cov_type": "HC1"}))
    clustered = _report(
        StandardDifferenceInDifferences.pure_step(
            data,
            {"cov_type": "cluster", "cluster_var": "unit_ids"},
        )
    )

    assert clustered.method_params["cov_type"] == "cluster"
    assert clustered.method_params["covariance_procedure"] == "unit_cluster_cr0"
    assert clustered.standard_error != pytest.approx(hc1.standard_error)


def test_cau_01_cluster_covariance_stable_under_duplicate_periods() -> None:
    """Repeating the same periods must not manufacture independent clusters."""

    original = _report(
        StandardDifferenceInDifferences.pure_step(
            _panel(),
            {"cov_type": "cluster", "cluster_var": "unit_ids"},
        )
    )
    duplicated = _report(
        StandardDifferenceInDifferences.pure_step(
            _panel(duplicated_periods=True),
            {"cov_type": "cluster", "cluster_var": "unit_ids"},
        )
    )

    assert duplicated.point_estimate == pytest.approx(original.point_estimate)
    assert duplicated.standard_error == pytest.approx(original.standard_error, rel=1e-10)


def test_cau_01_rejects_unknown_covariance_profile() -> None:
    """An unsupported covariance name must fail closed instead of silently using HC1."""

    report = _report(
        StandardDifferenceInDifferences.pure_step(_panel(), {"cov_type": "made_up"})
    )

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "unsupported covariance profile: made_up"


def test_cau_01_old_and_dedicated_standard_equivalent() -> None:
    """The legacy slot adapter and dedicated method preserve one effective request."""

    data = _panel()
    legacy_data = DifferenceInDifferences.materialize_input(
        {
            "outcome_panel": data.outcome,
            "treatment_indicator": data.treatment,
            "time_treatment": data.time_treatment,
            "unit_ids": data.unit_ids,
        },
        {},
    )
    legacy_output = DifferenceInDifferences.pure_step(legacy_data, {"confidence_level": 0.95})
    dedicated_output = StandardDifferenceInDifferences.pure_step(
        data, {"confidence_level": 0.95}
    )
    legacy = _report(legacy_output)
    dedicated = _report(dedicated_output)

    assert legacy.status == dedicated.status == EstimationStatus.SUCCESS
    assert legacy.point_estimate == pytest.approx(dedicated.point_estimate)
    assert legacy.standard_error == pytest.approx(dedicated.standard_error)
    assert legacy.confidence_interval == pytest.approx(dedicated.confidence_interval)
    assert legacy_output["warnings"] == dedicated_output["warnings"]


def test_cau_01_dedicated_metadata_is_not_deprecated_owner() -> None:
    """Dedicated metadata remains valid if the deprecated wrapper metadata changes."""

    assert (
        StandardDifferenceInDifferences.metadata.assumptions
        == DifferenceInDifferences.metadata.assumptions
    )
    assert (
        StandardDifferenceInDifferences.metadata.assumptions
        is not DifferenceInDifferences.metadata.assumptions
    )
    assert (
        StandardDifferenceInDifferences.metadata.equations
        is not DifferenceInDifferences.metadata.equations
    )


def test_cau_01_statsmodels_cluster_reference() -> None:
    """The unit-cluster CR0 standard error agrees with the independent reference."""

    data = _panel()
    report = _report(
        StandardDifferenceInDifferences.pure_step(
            data,
            {"cov_type": "cluster", "cluster_var": "unit_ids"},
        )
    )
    post = np.tile(np.arange(data.n_periods) >= data.time_treatment, data.n_units).astype(float)
    treatment = np.repeat(data.treatment.astype(float), data.n_periods)
    x_mat = np.column_stack(
        [np.ones(data.n_units * data.n_periods), post, treatment, post * treatment]
    )
    fit = OLS(data.outcome.reshape(-1), x_mat).fit()
    covariance = cov_cluster(
        fit,
        np.repeat(data.unit_ids, data.n_periods),
        use_correction=False,
    )

    assert report.standard_error == pytest.approx(float(np.sqrt(covariance[3, 3])), rel=1e-10)
