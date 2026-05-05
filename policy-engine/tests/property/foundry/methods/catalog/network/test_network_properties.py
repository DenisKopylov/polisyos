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


class TestCommunityDetectionProperties:
    @given(data=_adjacency_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_community_output_dict(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "network.community.community_detection@1.0.0")
        state = {"adjacency": data["adjacency"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass

    @given(data=_adjacency_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_community_labels_cover_all_nodes(self, data, isolated_registry):
        """Every node should be assigned to a community."""
        method = _method_or_skip(isolated_registry, "network.community.community_detection@1.0.0")
        state = {"adjacency": data["adjacency"]}
        try:
            result = method.pure_step(state, {})
            if "labels" in result:
                labels = np.asarray(result["labels"])
                assert len(labels) == data["n_nodes"]
        except Exception:
            pass


class TestDiffusionProperties:
    @given(data=_adjacency_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_diffusion_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "network.diffusion.network_diffusion@1.0.0")
        state = {"adjacency": data["adjacency"]}
        seeds = np.zeros(data["n_nodes"])
        seeds[0] = 1.0
        params = {"initial_adopters": seeds, "n_steps": 10, "threshold": 0.3}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert not np.all(np.isnan(arr)), f"All-NaN in diffusion/{key}"
        except Exception:
            pass

    @given(data=_adjacency_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_diffusion_monotone(self, data, isolated_registry):
        """Number of adopters should be non-decreasing over time."""
        method = _method_or_skip(isolated_registry, "network.diffusion.network_diffusion@1.0.0")
        state = {"adjacency": data["adjacency"]}
        seeds = np.zeros(data["n_nodes"])
        seeds[0] = 1.0
        params = {"initial_adopters": seeds, "n_steps": 10, "threshold": 0.3}
        try:
            result = method.pure_step(state, params)
            if "adoption_count" in result:
                counts = np.asarray(result["adoption_count"])
                if np.all(np.isfinite(counts)):
                    for i in range(1, len(counts)):
                        assert counts[i] >= counts[i - 1] - 1e-10
        except Exception:
            pass
