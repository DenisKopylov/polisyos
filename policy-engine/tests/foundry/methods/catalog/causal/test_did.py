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


def test_did_standard_known_att():
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.inference.did.standard@1.0.0")
    t0 = 5
    att_true = 3.0
    control = np.tile(np.arange(10, dtype=float), (5, 1))
    treated = control[:3].copy()
    treated[:, t0:] += att_true
    outcome = np.vstack([treated, control])
    treatment = np.array([1, 1, 1, 0, 0, 0, 0, 0], dtype=int)
    data = PanelObservationalData(outcome=outcome, treatment=treatment, time_treatment=t0)

    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={},
        seed=7,
    )
    report = result.output["report"]
    assert report.status == EstimationStatus.SUCCESS
    assert abs(report.point_estimate - att_true) < 0.5


def test_did_staggered_bootstrap_runs():
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.inference.did.staggered@1.0.0")
    n_units, n_periods = 12, 10
    base = np.tile(np.linspace(0, 9, n_periods, dtype=float), (n_units, 1))
    timing = np.array([5, 5, 6, 6, 7, 7, -1, -1, -1, -1, -1, -1], dtype=int)
    outcome = base.copy()
    for idx, g in enumerate(timing):
        if g >= 0:
            outcome[idx, g:] += 2.0
    treatment = (timing >= 0).astype(int)
    data = PanelObservationalData(
        outcome=outcome,
        treatment=treatment,
        time_treatment=5,
        treatment_timing=timing,
    )
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"n_bootstrap": 200},
        seed=11,
    )
    report = result.output["report"]
    assert report.status == EstimationStatus.SUCCESS
    assert report.inference_method == "bootstrap"
    assert report.n_bootstrap_samples == 200
