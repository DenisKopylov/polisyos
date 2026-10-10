from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.ml import TabularData, ensure_ml_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_tabular() -> TabularData:
    rng = np.random.default_rng(211)
    x = rng.normal(size=(72, 5))
    y = 0.8 + 1.4 * x[:, 0] - 0.9 * x[:, 1] + 0.35 * x[:, 3] + rng.normal(scale=0.2, size=72)
    weights = 0.8 + rng.uniform(size=72)
    return TabularData(
        features=x,
        target=y,
        sample_weight=weights,
        feature_names=["x0", "x1", "x2", "x3", "x4"],
    )


def test_tabular_transformer_runs() -> None:
    pytest.importorskip("sklearn")

    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    tabular = _make_tabular()

    method_cls = registry.get("ml.deep.tabular_transformer@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=tabular,
        params={"d_model": 12, "ridge_alpha": 0.35},
        seed=223,
    )

    prediction = result.output["result"]
    assert prediction.method_name == "tabular_transformer"
    assert prediction.metrics["r_squared"] > 0.5
    assert "latent_0" in prediction.coefficients
    assert "x0" in prediction.feature_importances
    assert result.output["uncertainty_envelope"] is not None
