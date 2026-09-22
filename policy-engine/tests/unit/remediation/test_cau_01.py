"""Regression witnesses for the bounded CAU-01 causal-method repair."""

from __future__ import annotations

from dataclasses import replace
from statistics import NormalDist

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
    report_values = {
        level: _report(
            StandardDifferenceInDifferences.pure_step(data, {"confidence_level": level})
        )
        for level in (0.80, 0.95, 0.99)
    }
    intervals = {level: report.confidence_interval for level, report in report_values.items()}
    critical_values = {
        level: NormalDist().inv_cdf((1.0 + level) / 2.0)
        for level in (0.80, 0.95, 0.99)
    }
    point_estimate = report_values[0.95].point_estimate

    assert intervals[0.80] != intervals[0.95]
    assert intervals[0.95] != intervals[0.99]
    assert (intervals[0.99][1] - intervals[0.99][0]) > (
        intervals[0.80][1] - intervals[0.80][0]
    )
    for level, report in report_values.items():
        assert report.point_estimate == pytest.approx(point_estimate)
        assert report.confidence_interval == pytest.approx(
            (
                point_estimate - critical_values[level] * report.standard_error,
                point_estimate + critical_values[level] * report.standard_error,
            )
        )


def test_cau_01_confidence_level_changes_rdd_interval() -> None:
    """Normal critical values must follow the requested RDD confidence level."""

    data = _rdd()
    params = {"bandwidth": 0.8, "kernel": "triangular", "manipulation_test": False}
    reports = {
        level: _report(
            RegressionDiscontinuity.pure_step(data, {**params, "confidence_level": level})
        )
        for level in (0.80, 0.95, 0.99)
    }
    intervals = {level: report.confidence_interval for level, report in reports.items()}
    critical_values = {
        level: NormalDist().inv_cdf((1.0 + level) / 2.0)
        for level in (0.80, 0.95, 0.99)
    }
    point_estimate = reports[0.95].point_estimate

    assert intervals[0.80] != intervals[0.95]
    assert intervals[0.95] != intervals[0.99]
    assert (intervals[0.99][1] - intervals[0.99][0]) > (
        intervals[0.80][1] - intervals[0.80][0]
    )
    for level, report in reports.items():
        assert report.point_estimate == pytest.approx(point_estimate)
        assert report.confidence_interval == pytest.approx(
            (
                point_estimate - critical_values[level] * report.standard_error,
                point_estimate + critical_values[level] * report.standard_error,
            )
        )
    assert reports[0.95].method_params["confidence_procedure"] == "normal_two_sided"
    assert reports[0.95].method_params["critical_value"] == pytest.approx(
        critical_values[0.95]
    )


def test_cau_01_did_95_interval_matches_normal_critical_value_and_preserves_point() -> None:
    """The requested 95% level preserves the point estimate and uses z(.975)."""

    data = _panel()
    report_95 = _report(
        StandardDifferenceInDifferences.pure_step(data, {"confidence_level": 0.95})
    )
    report_80 = _report(
        StandardDifferenceInDifferences.pure_step(data, {"confidence_level": 0.80})
    )
    critical_value = NormalDist().inv_cdf((1.0 + 0.95) / 2.0)

    assert report_95.point_estimate == pytest.approx(report_80.point_estimate)
    assert report_95.confidence_interval == pytest.approx(
        (
            report_95.point_estimate - critical_value * report_95.standard_error,
            report_95.point_estimate + critical_value * report_95.standard_error,
        )
    )
    assert report_95.method_params["confidence_procedure"] == "normal_two_sided"
    assert report_95.method_params["critical_value"] == pytest.approx(critical_value)


def test_cau_01_invalid_did_confidence_level_fails_closed() -> None:
    """An invalid DiD confidence level is an input failure, not a default to 95%."""

    report = _report(
        StandardDifferenceInDifferences.pure_step(_panel(), {"confidence_level": 1.0})
    )

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "confidence_level must be in (0, 1)"
    assert report.point_estimate is None


def test_cau_01_invalid_rdd_confidence_level_fails_closed() -> None:
    """An invalid RDD confidence level is rejected before local fitting."""

    report = _report(
        RegressionDiscontinuity.pure_step(
            _rdd(),
            {"bandwidth": 0.8, "kernel": "triangular", "confidence_level": 0.0},
        )
    )

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "confidence_level must be in (0, 1)"
    assert report.point_estimate is None


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


def test_cau_01_cluster_covariance_requires_unit_identity() -> None:
    """A cluster request without panel identities cannot silently fall back to HC1."""

    data = PanelObservationalData(
        outcome=_panel().outcome,
        treatment=_panel().treatment,
        time_treatment=2,
    )
    report = _report(
        StandardDifferenceInDifferences.pure_step(data, {"cov_type": "cluster"})
    )

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "cluster covariance requires unit_ids"
    assert report.point_estimate is None


def test_cau_01_cluster_covariance_rejects_bad_identity_shape() -> None:
    """A cluster request with an unbound identity shape fails closed."""

    report = _report(
        StandardDifferenceInDifferences.pure_step(
            _panel(),
            {"cov_type": "cluster", "cluster_var": np.array(["only-one-label"])},
        )
    )

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "cluster_var must have one label per unit or observation"
    assert report.point_estimate is None


def test_cau_01_cluster_rejects_varying_observation_labels_within_unit() -> None:
    """A row-level cluster vector must remain constant over each panel unit."""

    cluster_var = np.repeat(np.arange(_panel().n_units), _panel().n_periods)
    cluster_var[1] = 99
    report = _report(
        StandardDifferenceInDifferences.pure_step(
            _panel(),
            {"cov_type": "cluster", "cluster_var": cluster_var},
        )
    )

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "cluster_var must be constant within each unit"
    assert report.point_estimate is None


def test_cau_01_cluster_rejects_duplicate_unit_ids() -> None:
    """Unit-cluster inference rejects duplicate IDs that collapse independent units."""

    data = _panel()
    duplicate_ids = PanelObservationalData(
        outcome=data.outcome,
        treatment=data.treatment,
        time_treatment=data.time_treatment,
        unit_ids=np.array(["duplicate", "duplicate", "control-a", "control-b"]),
    )
    report = _report(
        StandardDifferenceInDifferences.pure_step(
            duplicate_ids,
            {"cov_type": "cluster", "cluster_var": "unit_ids"},
        )
    )

    assert report.status == EstimationStatus.INPUT_INVALID
    assert report.status_reason == "unit_ids must be unique for unit-cluster covariance"
    assert report.point_estimate is None


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


def test_cau_01_dedicated_metadata_survives_deprecated_metadata_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing the deprecated owner's assumptions cannot rewrite the dedicated owner."""

    dedicated_assumptions = dict(StandardDifferenceInDifferences.metadata.assumptions)
    mutated_legacy_metadata = replace(
        DifferenceInDifferences.metadata,
        assumptions={"legacy_mutation": "not a dedicated contract"},
    )
    monkeypatch.setattr(
        DifferenceInDifferences,
        "metadata",
        mutated_legacy_metadata,
    )

    assert dict(StandardDifferenceInDifferences.metadata.assumptions) == dedicated_assumptions
    assert dict(DifferenceInDifferences.metadata.assumptions) != dedicated_assumptions


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
