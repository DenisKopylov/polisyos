"""Property-based tests for network analysis methods."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
    from hypothesis.extra.numpy import arrays

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from polisyos.foundry.methods.catalog.network.protocols import NetworkResult
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


@st.composite
def _adjacency_strategy(draw):
    n = draw(st.integers(min_value=5, max_value=30))
    adj = draw(
        arrays(
            np.float64, (n, n), elements=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False)
        )
    )
    # Symmetrize for undirected graph
    adj = (adj + adj.T) / 2
    np.fill_diagonal(adj, 0.0)
    return {"adjacency": adj, "n_nodes": n}


def _network_result(method_result, method_fqn: str) -> NetworkResult:
    assert isinstance(method_result.output, dict), f"{method_fqn} did not return an output mapping"
    assert set(method_result.output) == {"result"}
    result = method_result.output["result"]
    assert isinstance(result, NetworkResult)
    return result


class TestCommunityDetectionProperties:
    @given(data=_adjacency_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_community_output_dict(self, data, isolated_registry, property_method_dispatcher):
        fqn = "network.community.community_detection@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        state = {"adjacency": data["adjacency"]}
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={"n_clusters": 3},
            seed=0,
        )
        result = _network_result(invocation, fqn)
        assert result.method_name == "community_detection"
        assert set(result.metrics) == {"modularity", "n_clusters"}
        assert np.isfinite(np.asarray(list(result.metrics.values()), dtype=float)).all()
        assert result.metrics["n_clusters"] == 3.0

    @given(data=_adjacency_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_community_labels_cover_all_nodes(
        self, data, isolated_registry, property_method_dispatcher
    ):
        """Every node receives an in-range cluster label in the typed result."""
        fqn = "network.community.community_detection@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        state = {"adjacency": data["adjacency"]}
        result = _network_result(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params={"n_clusters": 3},
                seed=0,
            ),
            fqn,
        )
        labels = np.asarray(result.labels)
        assert labels.shape == (data["n_nodes"],)
        assert np.issubdtype(labels.dtype, np.integer)
        assert np.all(labels >= 0)
        assert np.all(labels < int(result.metrics["n_clusters"]))


class TestDiffusionProperties:
    @given(data=_adjacency_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_diffusion_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "network.diffusion.network_diffusion@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        initial_states = np.zeros(data["n_nodes"], dtype=float)
        initial_states[0] = 1.0
        state = {"adjacency": data["adjacency"], "node_states": initial_states}
        params = {"diffusion_rate": 0.3, "decay": 0.05, "n_steps": 10}
        result = _network_result(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params=params,
                seed=0,
            ),
            fqn,
        )
        trajectories = np.asarray(result.state_trajectories, dtype=float)
        assert trajectories.shape == (params["n_steps"] + 1, data["n_nodes"])
        assert np.isfinite(trajectories).all()
        assert np.all((trajectories >= 0.0) & (trajectories <= 1.0))
        np.testing.assert_array_equal(trajectories[0], initial_states)
        np.testing.assert_allclose(result.node_scores, trajectories[-1])
        assert result.metrics["final_mean_state"] == pytest.approx(float(np.mean(trajectories[-1])))

    @given(data=_adjacency_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_diffusion_consensus_and_isolate_decay_follow_update(
        self, data, isolated_registry, property_method_dispatcher
    ):
        """Uniform states stay fixed on positive-degree rows and decay at isolated rows."""
        fqn = "network.diffusion.network_diffusion@1.0.0"
        method = _method_or_skip(isolated_registry, fqn)
        adjacency = np.asarray(data["adjacency"], dtype=float)
        isolated = np.sum(adjacency, axis=1) == 0.0
        consensus = np.full(data["n_nodes"], 0.4, dtype=float)
        state = {"adjacency": adjacency, "node_states": consensus}
        diffusion_rate = 0.2
        decay = 0.2
        n_steps = 10
        params = {"diffusion_rate": diffusion_rate, "decay": decay, "n_steps": n_steps}
        result = _network_result(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params=params,
                seed=0,
            ),
            fqn,
        )
        trajectories = np.asarray(result.state_trajectories, dtype=float)
        expected = np.broadcast_to(consensus, trajectories.shape).copy()
        for step in range(1, n_steps + 1):
            expected[step, isolated] = consensus[isolated] * (1.0 - decay) ** step
        np.testing.assert_allclose(trajectories, expected, rtol=0.0, atol=1e-12)
