from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.spatial import (
    AccessibilityData,
    GravityFlowData,
    SpatialData,
    ensure_spatial_methods_registered,
)


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _spatial_state() -> SpatialData:
    rng = np.random.default_rng(151)
    coords = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.2], [0.2, 0.8]])
    weights = np.array(
        [
            [0, 1, 1, 0, 1, 0],
            [1, 0, 0, 1, 0, 1],
            [1, 0, 0, 1, 1, 0],
            [0, 1, 1, 0, 0, 1],
            [1, 0, 1, 0, 0, 1],
            [0, 1, 0, 1, 1, 0],
        ],
        dtype=float,
    )
    features = np.column_stack([np.ones(6), rng.normal(size=6), rng.normal(size=6)])
    values = 0.5 + features @ np.array([0.2, 1.1, -0.7]) + rng.normal(scale=0.05, size=6)
    return SpatialData(coordinates=coords, values=values, features=features, weights_matrix=weights)


def test_spatial_registration_and_core_methods_run() -> None:
    pytest.importorskip("scipy")
    pytest.importorskip("statsmodels")

    ensure_spatial_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    signatures = [sig for sig in registry.query() if sig.namespace.startswith("spatial.")]
    assert {sig.name for sig in signatures} == {
        "moran_i",
        "gwr",
        "spatial_durbin",
        "gravity_model",
        "accessibility_index",
    }

    state = _spatial_state()
    for fqn in (
        "spatial.autocorrelation.moran_i@1.0.0",
        "spatial.regression.gwr@1.0.0",
        "spatial.regression.spatial_durbin@1.0.0",
    ):
        method_cls = registry.get(fqn)
        result = dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=state,
            params={},
            seed=153,
        )
        assert result.output["result"].method_name


def test_gravity_model_and_accessibility_index_run() -> None:
    pytest.importorskip("scipy")
    pytest.importorskip("statsmodels")

    ensure_spatial_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    gravity_cls = registry.get("spatial.flows.gravity_model@1.0.0")
    gravity_result = dispatcher.dispatch(
        method_class=gravity_cls,
        signature=gravity_cls.signature,
        state=GravityFlowData(
            origin_coords=np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]),
            destination_coords=np.array([[0.0, 0.5], [1.0, 0.5], [0.5, 0.0], [0.5, 1.0]]),
            origin_mass=np.array([10.0, 20.0, 15.0, 18.0]),
            destination_mass=np.array([12.0, 18.0, 17.0, 13.0]),
            observed_flows=np.array(
                [
                    [0.5, 5.0, 7.0, 4.0],
                    [4.0, 0.7, 6.0, 3.0],
                    [8.0, 5.0, 0.6, 2.0],
                    [3.0, 4.0, 5.0, 0.8],
                ]
            ),
        ),
        params={},
        seed=157,
    )
    assert "distance_decay" in gravity_result.output["result"].statistics

    access_cls = registry.get("spatial.accessibility.accessibility_index@1.0.0")
    access_result = dispatcher.dispatch(
        method_class=access_cls,
        signature=access_cls.signature,
        state=AccessibilityData(
            origin_coords=np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]),
            destination_coords=np.array([[0.0, 0.5], [1.0, 0.5], [0.5, 0.0], [0.5, 1.0]]),
            opportunity_mass=np.array([100.0, 120.0, 80.0, 95.0]),
            travel_cost_matrix=np.array(
                [
                    [5.0, 8.0, 12.0, 6.0],
                    [7.0, 4.0, 10.0, 5.0],
                    [11.0, 9.0, 3.0, 7.0],
                    [6.0, 5.0, 7.0, 4.0],
                ]
            ),
        ),
        params={"decay": 1.2},
        seed=159,
    )
    assert np.asarray(access_result.output["scores"], dtype=float).shape == (4,)
