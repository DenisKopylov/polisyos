from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import (
    HTEObservationalData,
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


def _synthetic_hte_data(n: int = 400, seed: int = 42) -> HTEObservationalData:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    t = rng.binomial(1, 0.5, size=n)
    tau = 0.5 * x[:, 0] - 0.2 * x[:, 1]
    y = 1.0 + x[:, 2] + tau * t + rng.normal(0.0, 0.4, size=n)
    return HTEObservationalData(outcome=y, treatment=t, covariates=x)


def test_causal_forest_hte_smoke():
    pytest.importorskip("econml")
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.hte.causal_forest@1.0.0")
    data = _synthetic_hte_data()
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"n_estimators": 100, "confidence_level": 0.9},
        seed=7,
    )
    report = result.output["report"]
    hte_result = result.output["hte_result"]
    assert report.status == EstimationStatus.SUCCESS
    assert len(hte_result.cate_values) == data.n_obs


def test_policy_tree_smoke():
    pytest.importorskip("econml")
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.targeting.policy_tree@1.0.0")
    data = _synthetic_hte_data()
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"budget_fraction": 0.25, "max_depth": 2},
        seed=11,
    )
    report = result.output["report"]
    recommendation = result.output["policy_recommendation"]
    assert report.status == EstimationStatus.SUCCESS
    assert recommendation.n_total_units == data.n_obs
