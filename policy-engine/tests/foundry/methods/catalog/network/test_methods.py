from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.network import (
    MultiplexNetworkData,
    NetworkData,
    ensure_network_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _network_state() -> NetworkData:
    return NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.2, 0.0],
                [1.0, 0.0, 0.5, 0.3],
                [0.2, 0.5, 0.0, 0.6],
                [0.0, 0.3, 0.6, 0.0],
            ]
        ),
        node_features=np.array([[1.0, 0.1], [0.2, 0.5], [0.7, 0.4], [0.3, 0.9]]),
        node_states=np.array([1.0, 0.0, 0.0, 1.0]),
    )


def test_network_registration_and_methods_run() -> None:
    pytest.importorskip("sklearn")

    ensure_network_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    signatures = [sig for sig in registry.query() if sig.namespace.startswith("network.")]
    assert {sig.name for sig in signatures} == {
        "community_detection",
        "input_output_network",
        "network_diffusion",
        "contagion_model",
        "multiplex_network",
    }

    state = _network_state()
    for fqn in (
        "network.community.community_detection@1.0.0",
        "network.io.input_output_network@1.0.0",
        "network.diffusion.network_diffusion@1.0.0",
        "network.contagion.contagion_model@1.0.0",
    ):
        method_cls = registry.get(fqn)
        result = dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=state,
            params={},
            seed=163,
        )
        assert result.output["result"].method_name


def test_multiplex_network_runs() -> None:
    ensure_network_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    multiplex_cls = registry.get("network.multiplex.multiplex_network@1.0.0")
    result = dispatcher.dispatch(
        method_class=multiplex_cls,
        signature=multiplex_cls.signature,
        state=MultiplexNetworkData(
            adjacency_layers=np.stack(
                [
                    np.array(
                        [
                            [0.0, 1.0, 0.2, 0.0],
                            [1.0, 0.0, 0.5, 0.3],
                            [0.2, 0.5, 0.0, 0.6],
                            [0.0, 0.3, 0.6, 0.0],
                        ]
                    ),
                    np.array(
                        [
                            [0.0, 0.7, 0.4, 0.1],
                            [0.7, 0.0, 0.2, 0.5],
                            [0.4, 0.2, 0.0, 0.8],
                            [0.1, 0.5, 0.8, 0.0],
                        ]
                    ),
                ]
            ),
            node_features=np.array([[1.0, 0.1], [0.2, 0.5], [0.7, 0.4], [0.3, 0.9]]),
        ),
        params={},
        seed=167,
    )
    assert result.output["result"].method_name == "multiplex_network"
