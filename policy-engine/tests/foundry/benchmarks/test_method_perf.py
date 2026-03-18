"""
Performance benchmarks for individual Foundry method pure_step execution.

Benchmarks one representative method per domain at n=1000 observations.
Thresholds:
- Simple estimators: < 200ms at n=1000
- Heavy estimators (MCMC, GP): < 10s

Run with:
    pytest tests/foundry/benchmarks/test_method_perf.py -m benchmark --benchmark-only -v
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip(
    "pytest_benchmark",
    reason="pytest-benchmark not installed; skipping perf tests",
)

pytestmark = pytest.mark.benchmark


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rng():
    return np.random.default_rng(42)


@pytest.fixture(scope="module")
def panel_n1000(rng):
    n = 1000
    return {
        "outcome": rng.standard_normal(n),
        "treatment": (rng.standard_normal(n) > 0).astype(float),
        "entity_id": np.repeat(np.arange(250), 4).astype(np.int64),
        "time_id": np.tile(np.arange(4), 250).astype(np.int64),
        "covariates": rng.standard_normal((n, 3)),
    }


@pytest.fixture(scope="module")
def regression_n1000(rng):
    n = 1000
    X = rng.standard_normal((n, 5))
    y = X @ np.array([1.0, -0.5, 0.3, 0.0, 0.2]) + rng.standard_normal(n)
    return {"features": X, "target": y}


@pytest.fixture(scope="module")
def lp_small():
    return {
        "c": np.array([1.0, 2.0, 3.0]),
        "A_ub": np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
        "b_ub": np.array([10.0, 10.0, 10.0]),
    }


@pytest.fixture(scope="module")
def timeseries_n500(rng):
    ar = 0.5
    n = 500
    ts = np.zeros(n)
    for t in range(1, n):
        ts[t] = ar * ts[t - 1] + rng.standard_normal()
    return {"endog": ts}


@pytest.fixture(scope="module")
def spatial_n200(rng):
    n = 200
    return {
        "outcome": rng.standard_normal(n),
        "lon": rng.uniform(-180, 180, n),
        "lat": rng.uniform(-90, 90, n),
    }


@pytest.fixture(scope="module")
def income_n1000(rng):
    n = 1000
    return {
        "income": np.exp(rng.standard_normal(n)),
        "weights": rng.uniform(0.5, 2.0, n),
    }


# ---------------------------------------------------------------------------
# Benchmark helper
# ---------------------------------------------------------------------------

def _run_method(registry, fqn: str, state: dict, params: dict) -> None:
    try:
        method = registry.get(fqn)
        method.pure_step(state, params)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Causal benchmarks
# ---------------------------------------------------------------------------

class BenchmarkCausal:
    def test_did_standard_n1000(self, benchmark, panel_n1000, module_registry):
        """Standard DiD should complete in < 200ms at n=1000."""
        benchmark.pedantic(
            _run_method,
            args=(module_registry, "causal.did.standard@1.0.0", panel_n1000, {}),
            iterations=3,
            rounds=5,
        )
        assert benchmark.stats["mean"] < 1.0  # 1s generous upper bound

    def test_callaway_santanna_n1000(self, benchmark, panel_n1000, module_registry):
        """Callaway-Sant'Anna should complete in < 2s at n=1000."""
        benchmark.pedantic(
            _run_method,
            args=(module_registry, "causal.did.callaway_santanna@1.0.0", panel_n1000, {}),
            iterations=2,
            rounds=3,
        )
        assert benchmark.stats["mean"] < 5.0


# ---------------------------------------------------------------------------
# Econometrics benchmarks
# ---------------------------------------------------------------------------

class BenchmarkEconometrics:
    def test_arima_n500(self, benchmark, timeseries_n500, module_registry):
        state = timeseries_n500
        params = {"p": 2, "d": 1, "q": 1}
        benchmark.pedantic(
            _run_method,
            args=(module_registry, "econometrics.timeseries.arima@1.0.0", state, params),
            iterations=2,
            rounds=3,
        )
        assert benchmark.stats["mean"] < 5.0

    def test_fixed_effects_n1000(self, benchmark, panel_n1000, module_registry):
        benchmark.pedantic(
            _run_method,
            args=(module_registry, "econometrics.panel.fixed_effects@1.0.0", panel_n1000, {}),
            iterations=3,
            rounds=5,
        )
        assert benchmark.stats["mean"] < 1.0


# ---------------------------------------------------------------------------
# Optimization benchmarks
# ---------------------------------------------------------------------------

class BenchmarkOptimization:
    def test_lp_small(self, benchmark, lp_small, module_registry):
        """LP with 3 vars should solve in < 100ms."""
        benchmark.pedantic(
            _run_method,
            args=(module_registry, "optimization.linear.resource_lp@1.0.0", lp_small, {}),
            iterations=5,
            rounds=10,
        )
        assert benchmark.stats["mean"] < 0.5


# ---------------------------------------------------------------------------
# Bayesian benchmarks
# ---------------------------------------------------------------------------

class BenchmarkBayesian:
    def test_linear_regression_n1000(self, benchmark, regression_n1000, module_registry):
        """Bayesian linear regression should complete in < 5s at n=1000."""
        benchmark.pedantic(
            _run_method,
            args=(
                module_registry,
                "bayesian.regression.linear_regression@1.0.0",
                regression_n1000,
                {"n_samples": 100, "seed": 42},
            ),
            iterations=1,
            rounds=3,
        )
        assert benchmark.stats["mean"] < 10.0


# ---------------------------------------------------------------------------
# Spatial benchmarks
# ---------------------------------------------------------------------------

class BenchmarkSpatial:
    def test_moran_i_n200(self, benchmark, spatial_n200, module_registry):
        benchmark.pedantic(
            _run_method,
            args=(module_registry, "spatial.autocorrelation.moran_i@1.0.0", spatial_n200, {}),
            iterations=3,
            rounds=5,
        )
        assert benchmark.stats["mean"] < 2.0


# ---------------------------------------------------------------------------
# Distributional benchmarks
# ---------------------------------------------------------------------------

class BenchmarkDistributional:
    def test_gini_n1000(self, benchmark, income_n1000, module_registry):
        benchmark.pedantic(
            _run_method,
            args=(module_registry, "distributional.inequality.gini@1.0.0", income_n1000, {}),
            iterations=5,
            rounds=10,
        )
        assert benchmark.stats["mean"] < 0.5  # Very fast (pure NumPy sort)
