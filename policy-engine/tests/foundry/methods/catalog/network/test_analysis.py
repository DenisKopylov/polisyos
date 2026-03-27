from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    ensure_all_methods_registered(registry)
    try:
        return registry.get(fqn)
    except Exception:
        pytest.skip(f"{fqn} not registered")


def _symmetric_adjacency(n, rng):
    A = rng.uniform(0, 1, size=(n, n))
    A = (A + A.T) / 2
    np.fill_diagonal(A, 0)
    return A


class TestCommunityDetection:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.community.community_detection@1.0.0")
        rng = np.random.default_rng(42)
        state = {"adjacency": _symmetric_adjacency(10, rng)}
        result = method.pure_step(state, {"n_clusters": 3, "__seed__": 42})
        assert isinstance(result, dict)


class TestInputOutputNetwork:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.io.input_output_network@1.0.0")
        rng = np.random.default_rng(42)
        state = {"adjacency": rng.uniform(0, 1, size=(5, 5))}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)


class TestNetworkDiffusion:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.diffusion.network_diffusion@1.0.0")
        rng = np.random.default_rng(42)
        n = 8
        state = {
            "adjacency": _symmetric_adjacency(n, rng),
            "node_states": rng.uniform(0, 1, size=n),
        }
        result = method.pure_step(state, {"diffusion_rate": 0.3, "n_steps": 5})
        assert isinstance(result, dict)


class TestContagionModel:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.contagion.contagion_model@1.0.0")
        rng = np.random.default_rng(42)
        n = 10
        node_states = np.zeros(n)
        node_states[:2] = 1.0  # 2 initially infected
        state = {
            "adjacency": _symmetric_adjacency(n, rng),
            "node_states": node_states,
        }
        result = method.pure_step(state, {"beta": 0.4, "gamma": 0.1, "n_steps": 5, "__seed__": 42})
        assert isinstance(result, dict)


class TestMultiplexNetwork:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "network.multiplex.multiplex_network@1.0.0")
        rng = np.random.default_rng(42)
        n = 6
        layers = np.stack([_symmetric_adjacency(n, rng) for _ in range(3)])
        state = {"adjacency_layers": layers}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
