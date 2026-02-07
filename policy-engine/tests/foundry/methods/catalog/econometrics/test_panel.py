from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.econometrics import (
    PanelData,
    ensure_econometric_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_panel_data() -> PanelData:
    rng = np.random.default_rng(123)
    n_entities = 6
    n_periods = 6
    n_obs = n_entities * n_periods

    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)

    x_var = rng.normal(size=n_obs)
    entity_constant = entity_ids.astype(float)
    entity_effect = entity_ids.astype(float) * 0.8
    epsilon = rng.normal(scale=0.1, size=n_obs)

    y = 1.5 * x_var + entity_effect + epsilon
    exog = np.column_stack([x_var, entity_constant])

    return PanelData(
        dependent=y,
        exog=exog,
        entity_ids=entity_ids,
        time_ids=time_ids,
        feature_names=["x_var", "x_entity_constant"],
    )


def test_panel_fixed_effects_drops_time_invariant_feature() -> None:
    pytest.importorskip("linearmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.panel.panel_data@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    data = _make_panel_data()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"model": "fixed_effects", "cov_type": "robust"},
        seed=42,
    )

    result = dispatched.output["result"]
    warnings = result.metadata.get("warnings", [])

    assert result.method_name == "fixed_effects"
    assert "x_var" in result.params
    assert any("x_entity_constant" in warning for warning in warnings)
    assert dispatched.output["envelope"] is not None


def test_panel_random_effects_runs() -> None:
    pytest.importorskip("linearmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.panel.panel_data@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_panel_data(),
        params={"model": "random_effects", "cov_type": "robust"},
        seed=7,
    )

    result = dispatched.output["result"]
    assert result.method_name == "random_effects"
    assert result.n_obs > 0
