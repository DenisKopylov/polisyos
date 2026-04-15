from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip(
    "pytest_benchmark",
    reason="pytest-benchmark not installed; skipping release-gate benchmarks",
)

from polisyos.foundry.methods.catalog.ml.protocols import TabularData
from polisyos.foundry.methods.catalog.bayesian.regression import BayesianLinearRegressionEstimator
from polisyos.foundry.methods.catalog.optimization.lp import ResourceLP
from polisyos.foundry.methods.catalog.survey.estimation import FayHerriotEstimator
from polisyos.foundry.methods.optimization import (
    AllocationItem,
    OptimizationProblem,
    ResourceConstraint,
)
from polisyos.foundry.methods.testing.golden_yaml import GoldenRegistry

pytestmark = [pytest.mark.benchmark, pytest.mark.performance]


@pytest.fixture(scope="module")
def release_gate_golden_registry() -> GoldenRegistry:
    return GoldenRegistry(
        Path("/Users/deniskopylov/polisyos/policy-engine/tests/foundry/golden")
    )


@pytest.fixture(scope="module")
def bayesian_state() -> TabularData:
    rng = np.random.default_rng(301)
    features = rng.normal(size=(48, 3))
    target = 1.1 + 1.8 * features[:, 0] - 0.6 * features[:, 1] + rng.normal(
        scale=0.3,
        size=48,
    )
    return TabularData(
        features=features,
        target=target,
        feature_names=["x0", "x1", "x2"],
    )


@pytest.fixture(scope="module")
def optimization_problem() -> OptimizationProblem:
    return OptimizationProblem(
        problem_id="release_gate_lp",
        items=(
            AllocationItem(item_id="x", cost=0.0, benefit=3.0, max_units=10, is_integer=False),
            AllocationItem(item_id="y", cost=0.0, benefit=2.0, max_units=10, is_integer=False),
        ),
        constraints=(
            ResourceConstraint(
                constraint_id="capacity",
                coefficients={"x": 2.0, "y": 1.0},
                bound=10.0,
                sense="<=",
            ),
        ),
    )


@pytest.fixture(scope="module")
def survey_state() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(42)
    n_areas = 12
    return {
        "y_direct": rng.normal(50, 5, size=n_areas),
        "X": rng.normal(0, 1, size=(n_areas, 2)),
        "sampling_var": np.abs(rng.normal(1, 0.3, size=n_areas)) + 0.1,
    }


def test_release_gate_domains_have_executable_golden_fixtures(
    release_gate_golden_registry: GoldenRegistry,
) -> None:
    for domain in ("bayesian", "optimization", "survey"):
        cases = release_gate_golden_registry.cases_by_domain(domain)
        assert cases
        assert any(case.skip_reason is None for case in cases)


def test_bayesian_accuracy_benchmark(
    benchmark,
    bayesian_state: TabularData,
) -> None:
    def _run():
        result = BayesianLinearRegressionEstimator.pure_step(
            bayesian_state,
            {"num_warmup": 12, "num_samples": 16, "num_chains": 1, "proposal_scale": 0.03},
        )
        assert result["result"].method_name == "bayesian_linear_regression"
        return result

    result = benchmark(_run)

    assert result["result"].method_name == "bayesian_linear_regression"
    assert benchmark.stats["mean"] * 1e3 < 25.0


def test_optimization_accuracy_benchmark(
    benchmark,
    optimization_problem: OptimizationProblem,
) -> None:
    def _run():
        payload, solver_info = ResourceLP.pure_step(
            optimization_problem,
            {"prefer_ortools": False},
        )
        if payload["status"] == "error":
            assert "error" in solver_info
        return payload, solver_info

    payload, solver_info = benchmark(_run)

    assert payload["status"] in {"optimal", "feasible", "error"}
    if payload["status"] != "error":
        assert float(payload["objective_value"]) >= 14.9
    else:
        assert "error" in solver_info
    assert benchmark.stats["mean"] * 1e3 < 50.0


def test_survey_accuracy_benchmark(
    benchmark,
    survey_state: dict[str, np.ndarray],
) -> None:
    def _run():
        result = FayHerriotEstimator.pure_step(survey_state, {"max_iter": 40})
        estimates = np.asarray(result["result"]["eblup_estimates"], dtype=float)
        assert np.all(np.isfinite(estimates))
        return result

    result = benchmark(_run)

    estimates = np.asarray(result["result"]["eblup_estimates"], dtype=float)
    assert estimates.shape[0] == survey_state["y_direct"].shape[0]
    assert benchmark.stats["mean"] * 1e3 < 5.0
