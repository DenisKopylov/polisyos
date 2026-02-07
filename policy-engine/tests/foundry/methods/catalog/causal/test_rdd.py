from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import (
    RDDObservationalData,
    ensure_causal_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.causal import EstimationStatus


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_rdd_known_jump():
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get(
        "causal.inference.regression_discontinuity@1.0.0"
    )
    rng = np.random.default_rng(123)
    x = rng.uniform(-1.0, 1.0, 1200)
    tau = 4.0
    y = 2.0 + 0.5 * x + tau * (x >= 0).astype(float) + rng.normal(0.0, 0.3, x.shape[0])
    data = RDDObservationalData(outcome=y, running_variable=x, cutoff=0.0)
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"bandwidth": 0.4, "kernel": "triangular"},
        seed=0,
    )
    report = result.output["report"]
    assert report.status == EstimationStatus.SUCCESS
    assert abs(report.point_estimate - tau) < 1.0
