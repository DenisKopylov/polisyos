"""
WS-5 performance regression benchmarks for JAX-sensitive runtime paths.

Run with:
    pytest tests/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-only

Benchmark JSON output can be persisted over time with:
    pytest tests/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-json=ws5-bench.json
"""
from __future__ import annotations

import jax
import jax.numpy as jnp
import pytest

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from polisyos.foundry.agent_sim.analysis import BehaviorAnalyzer
from polisyos.foundry.agent_sim.population import PopulationConfig, batch_create_agents
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator

pytest.importorskip(
    "pytest_benchmark",
    reason="pytest-benchmark not installed; skipping perf tests",
)

pytestmark = pytest.mark.benchmark


def _normal_env(point: float, std: float, level: float = 0.95) -> UncertaintyEnvelope:
    from statistics import NormalDist

    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z * std, point + z * std),
        confidence_level=level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


def test_monte_carlo_propagation_is_bounded(benchmark):
    propagator = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=512,
            mc_batch_size=128,
            mc_seed=7,
            mc_sampling_method="sobol",
            compute_sensitivity=False,
        )
    )
    envelopes = {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 0.5)}

    def _run():
        return propagator.propagate(
            lambda x=0.0, z=0.0: {"y": 2.0 * x + 3.0 * z},
            {"x": 1.0, "z": 2.0},
            envelopes,
            ["y"],
        )

    result = benchmark(_run)
    assert result[0].diagnostics["n_samples"] == 512
    mean_ms = benchmark.stats.get("mean", 0) * 1e3
    assert mean_ms < 500, f"Monte Carlo propagation too slow: {mean_ms:.1f} ms"


def test_quantile_mapping_is_bounded(benchmark):
    initial = GlobalState.empty(n_agents=512, seed=0, max_agents=512)
    final = initial.replace(
        agents=initial.agents.replace(
            wealth=initial.agents.wealth + jnp.linspace(0.0, 1.0, 512, dtype=jnp.float32)
        )
    )

    matrix = benchmark(
        lambda: BehaviorAnalyzer.compute_mobility_matrix(initial, final, n_quantiles=10)
    )

    assert matrix.shape == (10, 10)
    mean_ms = benchmark.stats.get("mean", 0) * 1e3
    assert mean_ms < 100, f"Mobility quantile mapping too slow: {mean_ms:.1f} ms"


def test_population_step_is_bounded(benchmark):
    state = GlobalState.empty(n_agents=256, max_agents=512, seed=0)
    parent_indices = jnp.full((64,), -1, dtype=jnp.int32)
    compiled = jax.jit(
        lambda current_state, key: batch_create_agents(
            current_state,
            n_new=64,
            parent_indices=parent_indices,
            rng_key=key,
            config=PopulationConfig(),
            n_requested=jnp.array(64, dtype=jnp.int32),
        )
    )

    warmup = compiled(state, jax.random.PRNGKey(0))
    jax.block_until_ready(warmup.agents.wealth)

    counter = {"value": 0}

    def _run():
        key = jax.random.PRNGKey(counter["value"])
        counter["value"] += 1
        result = compiled(state, key)
        jax.block_until_ready(result.agents.wealth)
        return result

    result = benchmark(_run)
    assert int(result.population_manager.n_active) >= 256
    mean_ms = benchmark.stats.get("mean", 0) * 1e3
    assert mean_ms < 100, f"Population birth step too slow: {mean_ms:.1f} ms"
