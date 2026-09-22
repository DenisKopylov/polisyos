"""Regression witnesses for staggered DiD unit, null, and anticipation semantics."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import (
    PanelObservationalData,
    ensure_causal_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus


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
    anticipation: int = 0,
    control_group: str = "never_treated",
):
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.inference.did.staggered@1.0.0")
    return MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={
            "control_group": control_group,
            "n_bootstrap": n_bootstrap,
            "anticipation": anticipation,
        },
        seed=seed,
    ).output["report"]


def _single_cell_panel() -> PanelObservationalData:
    timing = np.array([4, 4, 4, 4, -1, -1, -1, -1], dtype=int)
    baseline = np.tile(np.arange(5, dtype=float), (timing.size, 1))
    outcome = baseline.copy()
    outcome[:4, -1] += np.array([2.0, 4.0, 6.0, 8.0])
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
    assert report.confidence_interval is not None
    lower, upper = report.confidence_interval
    assert lower < report.point_estimate < upper
    assert report.method_params["bootstrap_independence"] == "panel_unit"


def test_staggered_p_value_uses_a_null_centered_statistic():
    report = _run_staggered(_single_cell_panel(), seed=19)

    assert report.status is EstimationStatus.SUCCESS
    assert report.p_value is not None
    assert report.p_value < 0.2
    assert report.method_params["p_value_null"] == "centered_unit_bootstrap"


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
        n_bootstrap=100,
    )

    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(5.2)
    assert report.method_params["control_eligibility"] == (
        "timing > t + anticipation or never-treated"
    )


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
