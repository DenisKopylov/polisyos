"""Independent functional and DGP oracles for the selected DiD scalar target."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import binom

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends import numpy_runner
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import did as did_module
from polisyos.foundry.methods.catalog.causal.did import StaggeredDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import (
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)


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
            * (
                _weighted_functional(data, upper, periods)
                - _weighted_functional(data, lower, periods)
            )
            / 2e-5
        )
    assert report.standard_error == pytest.approx(
        np.linalg.norm(influence) / data.n_units, rel=2e-9
    )
    # Independent seeded Mammen law checks the actual shared-unit score alignment.
    root_five = np.sqrt(5.0)
    draws = np.random.default_rng(19).choice(
        [(1 - root_five) / 2, (1 + root_five) / 2],
        size=(399, data.n_units),
        p=[(root_five + 1) / (2 * root_five), (root_five - 1) / (2 * root_five)],
    )
    score = np.asarray(influence)
    absolute = np.abs(draws @ score / np.linalg.norm(score))
    critical = np.sort(absolute)[int(np.floor(400 * 0.95))]
    assert report.confidence_interval == pytest.approx(
        (
            report.point_estimate - critical * report.standard_error,
            report.point_estimate + critical * report.standard_error,
        ),
        rel=2e-9,
    )
    assert (
        report.p_value
        == (1 + np.count_nonzero(absolute >= abs(report.point_estimate / report.standard_error)))
        / 400
    )
    assert report.method_params["cohort_share_influence"] is True
    assert report.method_params["target_contract"]["eligible_periods"] == {
        "2": [2, 3, 4, 5],
        "4": [4, 5],
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
        assert (
            null < tested.confidence_interval[0] or null > tested.confidence_interval[1]
        ) is outside
    assert report.method_params["multiplier_distribution"] == "iid_mammen"
    assert report.method_params["bootstrap_shared_draw"] is True
    assert report.method_params["null_statistic"] == "centered_studentized_scalar"


def test_registered_dispatch_injects_one_actual_unit_draw_stream(monkeypatch):
    """Observe the real selected backend RNG without substituting estimator or draw values."""

    data = _panel()
    factory = np.random.default_rng
    records = []

    class RecordedGenerator:
        def __init__(self, seed):
            self.seed = seed
            self.inner = factory(seed)
            self.shapes = []

        def choice(self, values, *, size, p):
            self.shapes.append(size)
            return self.inner.choice(values, size=size, p=p)

    def record_generator(seed=None):
        recorded = RecordedGenerator(seed)
        records.append(recorded)
        return recorded

    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    try:
        ensure_causal_methods_registered()
        method = MethodRegistry.get_instance().get("causal.inference.did.staggered@1.0.0")
        monkeypatch.setattr(numpy_runner.np.random, "default_rng", record_generator)
        result = MethodDispatcher.get_instance().dispatch(
            method_class=method,
            signature=method.signature,
            state=data,
            params={"n_bootstrap": 399, "confidence_level": 0.95},
            seed=19,
        )
        report = result.output["report"]
        used = [record for record in records if record.shapes]
        assert len(used) == 1
        assert used[0].seed == 19
        assert used[0].shapes == [(128, 12), (128, 12), (128, 12), (15, 12)]
        assert report.status is EstimationStatus.SUCCESS
        assert report.point_estimate == pytest.approx(41.0 / 6.0)
        assert report.n_bootstrap_samples == 399
        assert report.method_params["target_contract"]["sampling_unit"] == "independent_panel_unit"
        assert report.method_params["bootstrap_shared_draw"] is True
    finally:
        MethodRegistry.reset_instance()
        MethodDispatcher.reset_instance()


def test_cohort_share_removal_fails_the_independent_functional_oracle(monkeypatch):
    """The same target and markers cannot hide omission of estimated cohort-share influence."""

    data = _panel()
    periods = {2: [2, 3, 4, 5], 4: [4, 5]}
    derivatives = []
    for unit in range(data.n_units):
        upper, lower = np.ones(data.n_units), np.ones(data.n_units)
        upper[unit] += 1e-5
        lower[unit] -= 1e-5
        derivatives.append(
            data.n_units
            * (
                _weighted_functional(data, upper, periods)
                - _weighted_functional(data, lower, periods)
            )
            / 2e-5
        )
    expected_se = np.linalg.norm(derivatives) / data.n_units
    original = did_module._selected_participation_influence

    def without_share_uncertainty(panel, cells):
        point, influence, summaries = original(panel, cells)
        # This fixture's cohort means are independently known as 2.5 and9,
        # with6 of12 units selected and theta_sel=41/6. Remove only that ratio term.
        omitted = np.zeros(panel.n_units)
        omitted[:2] = 2.0 * (2.5 - 41.0 / 6.0)
        omitted[2:6] = 2.0 * (9.0 - 41.0 / 6.0)
        return point, influence - omitted, summaries

    positive = _run(data)
    with monkeypatch.context() as control:
        control.setattr(did_module, "_selected_participation_influence", without_share_uncertainty)
        removed = _run(data)
    restored = _run(data)
    assert positive.standard_error == pytest.approx(expected_se, rel=2e-9)
    assert removed.point_estimate == positive.point_estimate
    assert removed.method_params["target_binding"] == positive.method_params["target_binding"]
    assert removed.method_params["cohort_share_influence"] is True  # unchanged proxy
    # Hand-known centered within-cohort scores: (-2,2),(-3,-1,1,3),
    # and controls ±(1/3,1/5,1/15). Their norm/12 omits the ratio term.
    assert removed.standard_error == pytest.approx(
        np.sqrt(28.0 + 2.0 * (1.0 / 9 + 1.0 / 25 + 1.0 / 225)) / 12.0, rel=1e-8
    )
    assert removed.standard_error != pytest.approx(expected_se, rel=2e-9)
    assert restored.model_dump(mode="json") == positive.model_dump(mode="json")


@pytest.mark.parametrize("level, draws", [(0.95, 399), (0.99, 999), (0.8, 99)])
def test_closed_interval_endpoints_and_adjacent_nulls_share_integer_decision(
    tmp_path, level, draws
):
    data = _panel()
    reference = _run(data, seed=4, confidence_level=level, n_bootstrap=draws)
    lower, upper = reference.confidence_interval
    for null, outside in (
        (lower, False),
        (upper, False),
        (np.nextafter(lower, -np.inf), True),
        (np.nextafter(upper, np.inf), True),
    ):
        null = float(null)
        report = _run(data, seed=4, confidence_level=level, n_bootstrap=draws, null_effect=null)
        # Compare actual native closed endpoints, then fresh persisted decision fields.
        assert (
            null < report.confidence_interval[0] or null > report.confidence_interval[1]
        ) is outside
        assert report.method_params.get("null_rejected") is outside
        count = report.method_params["null_tail_count"]
        threshold = report.method_params["minimum_accepted_tail_count"]
        assert (count < threshold) is outside
        assert report.p_value == (1 + count) / (draws + 1)
        assert (report.p_value < report.method_params["significance_level"]) is outside
        ref = persist_causal_effect_report(
            _ensure_ir_artifact_store(FileSystemCAS(tmp_path)), report
        )
        fresh = load_causal_effect_report(_ensure_ir_artifact_store(FileSystemCAS(tmp_path)), ref)
        assert fresh.method_params["null_rejected"] is outside
        assert fresh.confidence_interval == (lower, upper)


@pytest.mark.parametrize(
    "timing", [[2.5] + [2] * 11, [True] * 12, [-2] + [-1] * 11, [6] + [-1] * 11]
)
def test_invalid_or_out_of_horizon_cohort_is_never_silently_dropped(timing):
    data = _panel().model_copy(update={"treatment_timing": np.asarray(timing)})
    report = _run(data)
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None


@pytest.mark.parametrize(
    "params",
    [
        {"eligible_periods": {"2": [2]}},
        {"eligible_periods": {"2": [2], "4": []}},
        {"eligible_periods": {"2": [2, 2], "4": [4]}},
        {"eligible_periods": {"2": [1], "4": [4]}},
        {"study_horizon": 4},
        {"n_bootstrap": 0},
        {"n_bootstrap": 2.5},
        {"confidence_level": float("nan")},
    ],
)
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
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(n),
    )


def test_seeded_serial_panel_null_coverage_and_alternative_binomial_bounds():
    """A bounded known-DGP check, not a nominal-coverage claim on admitted real data."""
    repetitions = 160
    rejected, covered, powered, alternative_covered = 0, 0, 0, 0
    for replication in range(repetitions):
        seed = 73000 + replication
        null = _run(_dgp(seed, shift=0.0), seed=seed + 1000)
        alternative = _run(_dgp(seed, shift=1.5), seed=seed + 1000)
        assert null.status is alternative.status is EstimationStatus.SUCCESS
        rejected += null.method_params["null_rejected"]
        covered += null.confidence_interval[0] <= 0.0 <= null.confidence_interval[1]
        powered += alternative.method_params["null_rejected"]
        alternative_covered += (
            alternative.confidence_interval[0] <= 1.5 <= alternative.confidence_interval[1]
        )
    lower, upper = binom.interval(0.995, repetitions, 0.05)
    assert lower <= rejected <= upper, (rejected, lower, upper)
    lower, upper = binom.interval(0.995, repetitions, 0.95)
    assert lower <= covered <= upper, (covered, lower, upper)
    assert lower <= alternative_covered <= upper, (alternative_covered, lower, upper)
    assert powered >= 0.95 * repetitions
    print(
        {
            "known_DGP_repetitions": repetitions,
            "null_rejected": rejected,
            "null_covered": covered,
            "alternative_rejected": powered,
            "alternative_covered": alternative_covered,
            "confidence": 0.995,
            "size": "pointwise iid-unit asymptotic only",
        }
    )
