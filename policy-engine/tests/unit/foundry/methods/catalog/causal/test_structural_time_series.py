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


def test_structural_time_series_runs_without_effect():
    pytest.importorskip("statsmodels")
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.inference.structural_time_series@1.0.0")
    rng = np.random.default_rng(17)
    n_donors, n_periods, t0 = 6, 30, 20
    donors = np.cumsum(rng.normal(0.0, 0.5, size=(n_donors, n_periods)), axis=1)
    treated = donors.mean(axis=0) + rng.normal(0.0, 0.2, size=n_periods)
    outcome = np.vstack([treated, donors])
    treatment = np.array([1] + [0] * n_donors, dtype=int)
    data = PanelObservationalData(outcome=outcome, treatment=treatment, time_treatment=t0)

    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"max_donors": 4},
        seed=9,
    )
    report = result.output["report"]
    assert report.status == EstimationStatus.SUCCESS
    assert report.inference_method == "state_space_simulation"
    assert abs(report.point_estimate) < 2.0
