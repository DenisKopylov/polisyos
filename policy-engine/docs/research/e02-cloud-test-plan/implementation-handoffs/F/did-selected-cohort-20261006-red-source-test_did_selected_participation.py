"""Independent functional and DGP oracles for the selected DiD scalar target."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import binom

from polisyos.foundry.methods.catalog.causal.did import StaggeredDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import EstimationStatus


def _panel() -> PanelObservationalData:
    timing = np.array([2, 2, 4, 4, 4, 4, -1, -1, -1, -1, -1, -1])
    outcome = np.tile(np.arange(6, dtype=float), (12, 1))
    outcome[:2, 2:] += np.array([1.0, 2.0, 3.0, 4.0])
    outcome[2:6, 4:] += np.array([8.0, 10.0])
    # Centered, unequal unit contributions leave the hand-calculated means unchanged.
    outcome[:2, 2:] += np.array([-1.0, 1.0])[:, None]
    outcome[2:6, 4:] += np.array([-1.5, -0.5, 0.5, 1.5])[:, None]
    outcome[6:, 2:] += np.arange(-2.5, 3.0)[:, None] * 0.2
    return PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(12),
    )


def _run(data, *, seed=19, **params):
    return StaggeredDifferenceInDifferences.pure_step(
        data,
        {"n_bootstrap": 399, **params, "__rng__": np.random.default_rng(seed)},
    )["report"]


def _weighted_functional(data, weights, periods):
    """Population functional under independently perturbed empirical sampling mass."""
    timing = data.treatment_timing
    selected_mass = weights[timing >= 0].sum()
    result = 0.0
    for group, eligible in periods.items():
        treated = timing == group
        control = timing == -1
        contrasts = []
        for t in eligible:
            changes = data.outcome[:, t] - data.outcome[:, group - 1]
            contrasts.append(
                np.average(changes[treated], weights=weights[treated])
                - np.average(changes[control], weights=weights[control])
            )
        result += weights[treated].sum() / selected_mass * np.mean(contrasts)
    return result


def test_unequal_followup_selected_target_and_ratio_influence():
    data = _panel()
    report = _run(data)
    assert report.status is EstimationStatus.SUCCESS
    # τ2=(1+2+3+4)/4, τ4=(8+10)/2; π=(2/6,4/6).
    assert report.point_estimate == pytest.approx(41.0 / 6.0)
    assert report.point_estimate != pytest.approx(5.75)  # old cell-size θ_W
    periods = {2: [2, 3, 4, 5], 4: [4, 5]}
    influence = []
    for unit in range(data.n_units):
        upper = np.ones(data.n_units)
        lower = upper.copy()
        upper[unit] += 1e-5
        lower[unit] -= 1e-5
        # A unit's mass is 1/n, so this derivative is ψ_i/n.
        influence.append(
            data.n_units
            * (_weighted_functional(data, upper, periods) - _weighted_functional(data, lower, periods))
            / 2e-5
        )
    assert report.standard_error == pytest.approx(
        np.linalg.norm(influence) / data.n_units, rel=2e-9
    )
    assert report.method_params["cohort_share_influence"] is True
    assert report.method_params["target_contract"]["eligible_periods"] == {
        "2": [2, 3, 4, 5], "4": [4, 5]
    }


def test_fixed_eligible_periods_change_target_and_binding():
    data = _panel()
    complete = _run(data)
    selected = _run(data, eligible_periods={"2": [5], "4": [4]})
    assert selected.status is EstimationStatus.SUCCESS
    assert selected.point_estimate == pytest.approx(20.0 / 3.0)
    assert selected.method_params["target_binding"] != complete.method_params["target_binding"]
    assert selected.method_params["n_cells"] == 2
    altered = data.model_copy(update={"unit_ids": data.unit_ids[::-1]})
    assert _run(altered).method_params["target_binding"] != complete.method_params["target_binding"]


def test_same_centered_studentized_law_drives_null_test_and_interval():
    data = _panel()
    report = _run(data, seed=4, confidence_level=0.95)
    null_at_point = _run(data, seed=4, confidence_level=0.95, null_effect=report.point_estimate)
    assert null_at_point.p_value == 1.0
    assert null_at_point.confidence_interval == report.confidence_interval
    for null, outside in ((0.0, True), (report.point_estimate, False)):
        tested = _run(data, seed=4, null_effect=null)
        assert (tested.p_value < 0.05) is outside
        assert (null < tested.confidence_interval[0] or null > tested.confidence_interval[1]) is outside
    assert report.method_params["multiplier_distribution"] == "iid_mammen"
    assert report.method_params["bootstrap_shared_draw"] is True
    assert report.method_params["null_statistic"] == "centered_studentized_scalar"


@pytest.mark.parametrize("timing", [[2.5] + [2] * 11, [True] * 12, [-2] + [-1] * 11, [6] + [-1] * 11])
def test_invalid_or_out_of_horizon_cohort_is_never_silently_dropped(timing):
    data = _panel().model_copy(update={"treatment_timing": np.asarray(timing)})
    report = _run(data)
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None


@pytest.mark.parametrize("params", [
    {"eligible_periods": {"2": [2]}},
    {"eligible_periods": {"2": [2], "4": []}},
    {"eligible_periods": {"2": [2, 2], "4": [4]}},
    {"eligible_periods": {"2": [1], "4": [4]}},
    {"study_horizon": 4},
    {"n_bootstrap": 0},
    {"n_bootstrap": 2.5},
    {"confidence_level": float("nan")},
])
def test_invalid_fixed_target_or_inference_request_refuses(params):
    report = _run(_panel(), **params)
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None


def test_degenerate_unit_influence_is_point_only():
    data = _panel()
    outcome = np.tile(np.arange(6, dtype=float), (12, 1))
    for unit, group in enumerate(data.treatment_timing):
        if group >= 0:
            outcome[unit, group:] += 2.0
    report = _run(data.model_copy(update={"outcome": outcome}))
    assert report.point_estimate == pytest.approx(2.0)
    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.p_value is None and report.confidence_interval is None
    assert report.method_params["inference_limitation"] == "degenerate_unit_influence"


def _dgp(seed, *, shift):
    rng = np.random.default_rng(seed)
    n, periods = 400, 6
    timing = rng.choice(np.array([2, 4, -1]), size=n, p=[0.2, 0.3, 0.5])
    innovations = rng.normal(size=(n, periods))
    errors = innovations.copy()
    for t in range(1, periods):
        errors[:, t] += 0.6 * errors[:, t - 1]
    outcome = rng.normal(size=n)[:, None] + np.arange(periods)[None, :] + errors
    for group, effect in ((2, -3.0 + shift), (4, 2.0 + shift)):
        outcome[np.ix_(timing == group, np.arange(periods) >= group)] += effect
    return PanelObservationalData(
        outcome=outcome, treatment=(timing >= 0).astype(int), time_treatment=2,
        treatment_timing=timing, unit_ids=np.arange(n),
    )


def test_seeded_serial_panel_null_coverage_and_alternative_binomial_bounds():
    """A bounded known-DGP check, not a nominal-coverage claim on admitted real data."""
    repetitions = 160
    rejected, covered, powered = 0, 0, 0
    for replication in range(repetitions):
        seed = 73000 + replication
        null = _run(_dgp(seed, shift=0.0), seed=seed + 1000)
        alternative = _run(_dgp(seed, shift=1.5), seed=seed + 1000)
        assert null.status is alternative.status is EstimationStatus.SUCCESS
        rejected += null.p_value < 0.05
        covered += null.confidence_interval[0] <= 0.0 <= null.confidence_interval[1]
        powered += alternative.p_value < 0.05
    lower, upper = binom.interval(0.995, repetitions, 0.05)
    assert lower <= rejected <= upper, (rejected, lower, upper)
    lower, upper = binom.interval(0.995, repetitions, 0.95)
    assert lower <= covered <= upper, (covered, lower, upper)
    assert powered >= 0.95 * repetitions
    print({"known_DGP_repetitions": repetitions, "null_rejected": rejected,
           "null_covered": covered, "alternative_rejected": powered,
           "confidence": 0.995, "size": "pointwise iid-unit asymptotic only"})
