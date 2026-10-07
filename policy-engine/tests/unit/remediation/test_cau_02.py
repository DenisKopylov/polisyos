"""Regression witnesses for staggered DiD unit, null, and anticipation semantics."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import (
    PanelObservationalData,
    ensure_causal_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import (
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _run_staggered(
    data: PanelObservationalData,
    *,
    seed: int = 11,
    n_bootstrap: int = 200,
    anticipation: object = 0,
    control_group: str = "never_treated",
):
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.inference.did.staggered@1.0.0")
    return (
        MethodDispatcher.get_instance()
        .dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=data,
            params={
                "control_group": control_group,
                "n_bootstrap": n_bootstrap,
                "anticipation": anticipation,
            },
            seed=seed,
        )
        .output["report"]
    )


def _single_cell_panel(
    effects: np.ndarray | None = None,
) -> PanelObservationalData:
    timing = np.array([4, 4, 4, 4, -1, -1, -1, -1], dtype=int)
    baseline = np.tile(np.arange(5, dtype=float), (timing.size, 1))
    outcome = baseline.copy()
    outcome[:4, -1] += np.array([2.0, 4.0, 6.0, 8.0]) if effects is None else effects
    return PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=4,
        treatment_timing=timing,
        unit_ids=np.arange(timing.size),
    )


def test_staggered_bootstrap_resamples_panel_units_not_att_cells():
    report = _run_staggered(_single_cell_panel())

    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(5.0)
    assert report.confidence_level == 0.95
    lower, upper = report.confidence_interval
    assert lower < report.point_estimate < upper
    envelope = report.to_uncertainty_envelope()
    assert envelope is not None
    assert report.method_params["parallel_trends_identified"] is False


def test_staggered_p_value_uses_centered_scalar_null_distribution():
    report = _run_staggered(_single_cell_panel(), seed=19)

    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(5.0)
    assert report.p_value < 0.05
    assert report.method_params["null_statistic"] == "centered_studentized_scalar"


def test_staggered_anticipation_excludes_already_affected_not_yet_controls():
    timing = np.array([2, 2, 3, 3, -1, -1], dtype=int)
    outcome = np.zeros((timing.size, 5), dtype=float)
    outcome[:2, 2:] = 2.0
    outcome[2:4, 2:] = 10.0
    data = PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(timing.size),
    )

    report = _run_staggered(
        data,
        anticipation=1,
        control_group="not_yet_treated",
        n_bootstrap=400,
    )

    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(6.0)


def test_staggered_zero_anticipation_preserves_not_yet_treated_characterization():
    timing = np.array([2, 2, 3, 3, -1, -1], dtype=int)
    outcome = np.zeros((timing.size, 5), dtype=float)
    outcome[:2, 2:] = 2.0
    outcome[2:4, 3:] = 10.0
    data = PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(timing.size),
    )

    report = _run_staggered(
        data,
        anticipation=0,
        control_group="not_yet_treated",
        n_bootstrap=400,
    )

    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(6.0)


def test_staggered_partial_no_control_cells_fail_closed():
    timing = np.array([2, 3, 4], dtype=int)
    data = PanelObservationalData(
        outcome=np.zeros((3, 5), dtype=float),
        treatment=np.ones(3, dtype=int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(3),
    )

    report = _run_staggered(
        data,
        anticipation=1,
        control_group="not_yet_treated",
        n_bootstrap=50,
    )

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert report.status_reason == "no admissible controls for one or more staggered ATT(g,t) cells"


def test_staggered_missing_baseline_cells_fail_closed():
    timing = np.array([1, 2, -1], dtype=int)
    data = PanelObservationalData(
        outcome=np.zeros((3, 4), dtype=float),
        treatment=(timing >= 0).astype(int),
        time_treatment=1,
        treatment_timing=timing,
        unit_ids=np.arange(3),
    )

    report = _run_staggered(data, anticipation=1, n_bootstrap=50)

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert report.status_reason == "no valid baseline for one or more staggered cohorts"


def test_staggered_duplicate_unit_ids_fail_closed_for_unit_bootstrap():
    data = _single_cell_panel()
    data.unit_ids = np.array([0, 0, 1, 2, 3, 4, 5, 6])

    report = _run_staggered(data, n_bootstrap=50)

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert report.status_reason == "staggered bootstrap requires unique unit_ids"


def test_staggered_no_admissible_controls_is_bounded_failure():
    timing = np.array([2, 3], dtype=int)
    data = PanelObservationalData(
        outcome=np.zeros((2, 4), dtype=float),
        treatment=np.ones(2, dtype=int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(2),
    )

    report = _run_staggered(
        data,
        anticipation=1,
        control_group="not_yet_treated",
        n_bootstrap=50,
    )

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert report.status_reason == "no admissible controls for one or more staggered ATT(g,t) cells"


@pytest.mark.parametrize("has_supported_cohort", [False, True])
def test_staggered_zero_start_cohort_is_not_silently_omitted(has_supported_cohort):
    """An observed cohort at t=0 has no pre-baseline, even beside a valid cohort."""
    timing = np.array([0, 0, 2, 2, -1, -1] if has_supported_cohort else [0, 0, -1, -1])
    outcome = np.zeros((timing.size, 4))
    outcome[:2, :] = 20.0
    if has_supported_cohort:
        outcome[2:4, 2:] = 3.0
    data = PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=0,
        treatment_timing=timing,
        unit_ids=np.arange(timing.size),
    )

    report = _run_staggered(data, n_bootstrap=40)

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert report.status_reason == "no valid baseline for one or more staggered cohorts"
    assert report.method_params["missing_baseline_groups"] == [0]


@pytest.mark.parametrize("anticipation", [-1, 0.5, True, "1", None, np.nan, np.inf])
def test_staggered_anticipation_requires_declared_nonnegative_period_count(anticipation):
    """An ambiguous anticipation window cannot be coerced into another control rule."""
    report = _run_staggered(_single_cell_panel(), anticipation=anticipation, n_bootstrap=40)

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.status_reason == "anticipation must be a nonnegative integer"
    assert report.point_estimate is None


@pytest.mark.parametrize("anticipation", [0, 1, np.int64(1)])
def test_staggered_supported_anticipation_preserves_known_contrast(anticipation):
    """Validated anticipation leaves ATT=5 on a panel with a sufficient baseline."""
    report = _run_staggered(_single_cell_panel(), anticipation=anticipation, n_bootstrap=40)

    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(5.0)
    assert report.method_params["anticipation"] == int(anticipation)
    assert report.p_value is not None
    assert report.confidence_interval is not None


def test_staggered_missing_baseline_refusal_survives_persisted_consumer_readback(tmp_path):
    """The typed refusal remains point-free and non-gate-eligible after CAS readback."""
    timing = np.array([0, 0, 2, 2, -1, -1])
    outcome = np.zeros((timing.size, 4))
    outcome[2:4, 2:] = 3.0
    data = PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=0,
        treatment_timing=timing,
        unit_ids=np.arange(timing.size),
    )
    report = _run_staggered(data, n_bootstrap=40)
    store = FileSystemCAS(tmp_path)

    report_ref = persist_causal_effect_report(store, report)
    loaded = load_causal_effect_report(store, report_ref)
    envelope = loaded.to_uncertainty_envelope()

    assert loaded.status is EstimationStatus.ASSUMPTION_FAILED
    assert loaded.point_estimate is None
    assert loaded.method_params["missing_baseline_groups"] == [0]
    assert envelope is not None
    assert envelope.gate_eligible is False
    assert envelope.metadata["failure_envelope"] is True
