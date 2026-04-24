from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip(
    "pytest_benchmark",
    reason="pytest-benchmark not installed; skipping perf tests",
)

pytestmark = pytest.mark.benchmark


def _run_method(registry, fqn: str, state: dict, params: dict) -> None:
    method = registry.get(fqn)
    method.pure_step(state, params)


@pytest.fixture(scope="module")
def sparse_demography_state():
    rng = np.random.default_rng(42)
    n_records = 1500
    n_states = 12
    n_origin = 12
    transition = rng.uniform(0.01, 1.0, size=(n_origin, n_states))
    transition /= transition.sum(axis=1, keepdims=True)
    return {
        "base_weights": rng.uniform(0.5, 3.0, size=n_records),
        "origin_state_index": rng.integers(0, n_origin, size=n_records, dtype=np.int64),
        "target_state_totals": rng.uniform(150.0, 350.0, size=n_states),
        "transition_prior_matrix": transition,
    }


class BenchmarkDemographicConsistency:
    def test_survey_demographic_consistency(
        self, benchmark, sparse_demography_state, module_registry
    ):
        state = dict(sparse_demography_state)
        total_mass = float(np.sum(state["base_weights"]))
        state["target_state_totals"] = state["target_state_totals"] * (
            total_mass / float(np.sum(state["target_state_totals"]))
        )

        benchmark.pedantic(
            _run_method,
            args=(
                module_registry,
                "simulation.demography.static_aging@1.0.0",
                state,
                {
                    "mode": "deterministic",
                    "top_k_destinations": 3,
                    "tolerance": 1e-8,
                },
            ),
            iterations=2,
            rounds=4,
        )
        assert benchmark.stats["mean"] < 2.0
