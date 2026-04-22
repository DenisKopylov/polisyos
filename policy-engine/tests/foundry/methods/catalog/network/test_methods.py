from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.network import (
    MultiplexNetworkData,
    NetworkData,
    StrategicNetworkFormationData,
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
        "network_missingness_assessment",
        "peer_effect_decomposition",
        "contagion_model",
        "multiplex_network",
        "sbm_stratification",
        "ergm_null",
        "diffusion_null_test",
        "strategic_formation",
    }

    state = _network_state()
    for fqn in (
        "network.community.community_detection@1.0.0",
        "network.io.input_output_network@1.0.0",
        "network.diffusion.network_diffusion@1.0.0",
        "network.missingness.network_missingness_assessment@0.1.0",
        "network.peer_effects.peer_effect_decomposition@1.0.0",
        "network.contagion.contagion_model@1.0.0",
        "network.community.sbm_stratification@0.1.0",
        "network.generative.ergm_null@0.1.0",
        "network.generative.diffusion_null_test@0.1.0",
    ):
        method_cls = registry.get(fqn)
        result = dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=state,
            params=(
                {
                    "mode": "bounds_only",
                    "frame_observed": True,
                    "estimands": ("edge_count",),
                }
                if fqn == "network.missingness.network_missingness_assessment@0.1.0"
                else {}
            ),
            seed=163,
        )
        assert result.output["result"].method_name
        if fqn == "network.peer_effects.peer_effect_decomposition@1.0.0":
            assert result.output["result"].peer_effect_decomposition is not None
        if fqn == "network.missingness.network_missingness_assessment@0.1.0":
            assert result.output["result"].missingness_assessment is not None
        if fqn == "network.community.sbm_stratification@0.1.0":
            assert result.output["result"].metadata["embedding_fidelity_certificate"]["status"] == "red"

    strategic_cls = registry.get("network.formation.strategic_formation@0.1.0")
    strategic_result = dispatcher.dispatch(
        method_class=strategic_cls,
        signature=strategic_cls.signature,
        state=StrategicNetworkFormationData(
            adjacency=np.array(
                [
                    [0.0, 1.0, 0.0, 0.0],
                    [1.0, 0.0, 1.0, 0.0],
                    [0.0, 1.0, 0.0, 1.0],
                    [0.0, 0.0, 1.0, 0.0],
                ]
            ),
            dyad_features=np.ones((4, 4, 1), dtype=float),
        ),
        params={},
        seed=173,
    )
    assert strategic_result.output["result"].formation_diagnostic is not None


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


def test_multiplex_network_threads_missingness_assessment_from_params() -> None:
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
        ),
        params={
            "missingness": {
                "mode": "bounds_only",
                "frame_observed": True,
                "estimands": ("edge_count",),
            }
        },
        seed=171,
    )
    assessment = result.output["result"].missingness_assessment
    assert assessment is not None
    assert assessment.estimands["edge_count"].identification_status.value == "set_identified"


def test_network_result_attaches_embedding_fidelity_certificate_from_state_metadata() -> None:
    ensure_network_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("network.io.input_output_network@1.0.0")
    state = NetworkData(
        adjacency=np.array(
            [
                [0.0, 1.0, 0.2, 0.0],
                [1.0, 0.0, 0.5, 0.3],
                [0.2, 0.5, 0.0, 0.6],
                [0.0, 0.3, 0.6, 0.0],
            ]
        ),
        node_features=np.array([[1.0, 0.1], [0.2, 0.5], [0.7, 0.4], [0.3, 0.9]]),
        metadata={
            "embedding_matrix": np.ones((4, 2), dtype=float),
            "embedding_family": "node2vec",
        },
    )

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params={},
        seed=211,
    )

    certificate = result.output["result"].embedding_fidelity_certificate
    assert certificate is not None
    assert certificate.family == "node2vec"
    assert certificate.status.value == "red"
    assert result.output["result"].metadata["embedding_fidelity_certificate"]["status"] == "red"
