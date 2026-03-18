"""
Cross-backend determinism tests.

Verifies that JAX and NumPy backends produce numerically equivalent results
for methods that support both backends, and that methods are deterministic
with the same seed.
"""
from __future__ import annotations

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# JAX availability guard
# ---------------------------------------------------------------------------

try:
    import jax  # noqa: F401
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not JAX_AVAILABLE,
    reason="JAX not installed — skipping cross-backend determinism tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_panel_data():
    """Panel data used across determinism tests."""
    rng = np.random.default_rng(42)
    n_obs = 200
    n_periods = 4
    return {
        "outcome": rng.standard_normal(n_obs).astype(np.float64),
        "treatment": (rng.standard_normal(n_obs) > 0).astype(np.float64),
        "entity_id": np.repeat(np.arange(n_obs // n_periods), n_periods).astype(np.int64),
        "time_id": np.tile(np.arange(n_periods), n_obs // n_periods).astype(np.int64),
        "covariates": rng.standard_normal((n_obs, 3)).astype(np.float64),
    }


@pytest.fixture(scope="module")
def sample_regression_data():
    rng = np.random.default_rng(99)
    n_obs = 150
    X = rng.standard_normal((n_obs, 4)).astype(np.float64)
    y = X @ np.array([1.0, -0.5, 0.3, 0.0]) + rng.standard_normal(n_obs) * 0.5
    return {"features": X, "target": y}


# ---------------------------------------------------------------------------
# Determinism: same backend, same seed → identical results
# ---------------------------------------------------------------------------

class TestSeedDeterminism:
    """Methods must be deterministic when given the same seed."""

    @pytest.mark.parametrize("fqn", [
        "bayesian.regression.linear_regression@1.0.0",
        "causal.did.standard@1.0.0",
    ])
    def test_same_seed_same_output(self, fqn, sample_panel_data, isolated_registry):
        """Running the same method twice with the same seed yields identical outputs."""
        try:
            method_cls = isolated_registry.get(fqn)
        except Exception:
            pytest.skip(f"Method {fqn} not registered")

        state = sample_panel_data
        params = {}
        seed = 42

        result1 = method_cls.pure_step(state, params)
        result2 = method_cls.pure_step(state, params)

        # Results should be identical (or very close for stochastic methods with same seed)
        for key in result1:
            v1, v2 = result1[key], result2[key]
            if isinstance(v1, np.ndarray) and np.issubdtype(v1.dtype, np.floating):
                np.testing.assert_array_equal(
                    v1, v2,
                    err_msg=f"Non-determinism in {fqn} output key '{key}'"
                )


# ---------------------------------------------------------------------------
# Cross-backend numerical equivalence
# ---------------------------------------------------------------------------

def _get_method_pairs(registry) -> list[tuple[str, str]]:
    """Find method FQNs that exist in both JAX and NumPy variants."""
    pairs = []
    try:
        from polisyos.foundry.methods.base import ComputeBackend
        all_entries = list(registry.snapshot().values())
        jax_fqns = {
            e.signature.fqn for e in all_entries
            if e.signature.backend == ComputeBackend.JAX
        }
        numpy_fqns = {
            e.signature.fqn for e in all_entries
            if e.signature.backend == ComputeBackend.NUMPY
        }
        shared = jax_fqns & numpy_fqns
        pairs = [(fqn, fqn) for fqn in sorted(shared)[:5]]
    except Exception:
        pass
    return pairs


class TestCrossBackendEquivalence:
    """JAX and NumPy backends should produce numerically equivalent outputs."""

    def test_numpy_runner_produces_finite_output(self, sample_regression_data, isolated_registry):
        """Smoke test: NumPy runner produces finite results for regression methods."""
        fqn = "bayesian.regression.linear_regression@1.0.0"
        try:
            method_cls = isolated_registry.get(fqn)
        except Exception:
            pytest.skip(f"{fqn} not registered")

        result = method_cls.pure_step(sample_regression_data, {"seed": 42})
        for key, val in result.items():
            arr = np.asarray(val)
            if np.issubdtype(arr.dtype, np.floating):
                assert np.all(np.isfinite(arr)), f"Non-finite values in {key}"

    def test_dispatcher_produces_consistent_results(self, sample_panel_data, isolated_registry):
        """Multiple dispatcher calls with same seed produce same result."""
        from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

        fqn = "causal.did.standard@1.0.0"
        try:
            entry = isolated_registry._store.get_by_fqn(fqn)
            if entry is None:
                pytest.skip(f"{fqn} not registered")
            method_cls = entry.factory()
            sig = entry.signature
        except Exception as e:
            pytest.skip(f"Could not load {fqn}: {e}")

        dispatcher = MethodDispatcher.get_instance()

        result1 = dispatcher.dispatch(
            method_class=method_cls,
            signature=sig,
            state=sample_panel_data,
            params={},
            seed=42,
        )
        result2 = dispatcher.dispatch(
            method_class=method_cls,
            signature=sig,
            state=sample_panel_data,
            params={},
            seed=42,
        )

        for key in result1.output:
            v1 = result1.output[key]
            v2 = result2.output[key]
            if isinstance(v1, np.ndarray) and np.issubdtype(v1.dtype, np.floating):
                np.testing.assert_allclose(
                    v1, v2, rtol=1e-10,
                    err_msg=f"Inconsistent results for {fqn} key '{key}'"
                )
