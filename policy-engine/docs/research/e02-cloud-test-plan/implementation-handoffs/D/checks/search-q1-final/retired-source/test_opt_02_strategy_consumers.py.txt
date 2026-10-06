"""Executed coordinate consumers of the existing MO and neural algorithms."""

from unittest.mock import patch

import pytest

from polisyos.scientist.methods.autotune.bayesian_generator import SearchSpace as PublicSpace
from polisyos.scientist.methods.search.objective import OptimizationDirection
from polisyos.scientist.methods.search.strategies import _deps
from polisyos.scientist.methods.search.strategies.multi_objective import MOBayesianOptimizer
from polisyos.scientist.methods.search.strategies.neural import (
    NeuralSearchConfig,
    NeuralSearchStrategy,
)
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    ParameterType,
)


@pytest.mark.parametrize("consumer", ["random", "public"])
def test_unrepresentable_affine_domain_refuses_at_admission(consumer):
    def invoke():
        if consumer == "random":
            RandomSearchStrategy(
                SearchSpace([ParameterBounds("x", -1e308, 1e308)]), seed=31
            ).suggest([])
        else:
            PublicSpace([{"name": "x", "lower": -1e308, "upper": 1e308}])

    with pytest.raises(ValueError, match="representable span"):
        invoke()


def test_supported_logarithmic_endpoints_are_actual_in_bound_actions():
    space = SearchSpace([ParameterBounds("x", 1e-308, 1e308, dtype=ParameterType.LOG_CONTINUOUS)])
    for point in (0, 0.5, 1):
        candidate = space.candidate_from_vector((point,))
        assert 1e-308 <= candidate.params["x"] <= 1e308
        assert candidate.params_normalized == pytest.approx((point,))


@pytest.mark.skipif(_deps.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_multiobjective_native_tensor_converter_emits_executed_coordinate():
    space = SearchSpace([ParameterBounds("n", 0, 1, dtype=ParameterType.INTEGER)])
    optimizer = MOBayesianOptimizer(space, ["a", "b"], [OptimizationDirection.MINIMIZE] * 2)
    candidate = optimizer._tensor_to_candidate(_deps.require_torch().tensor([0.24]), "fixture", 0.8)
    assert candidate.params == {"n": 0}
    assert candidate.params_normalized == space.normalize(candidate.params)
    assert candidate.metadata["relaxed_proposal"] == pytest.approx([0.24])
    assert candidate.predicted_mean is None
    assert candidate.metadata["prediction_basis"] == "not_established_no_scalar_predictor"


@pytest.mark.skipif(_deps.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_neural_actual_fit_and_acquisition_emits_attainable_action():
    space = SearchSpace([ParameterBounds("n", 0.2, 1.8, dtype=ParameterType.INTEGER)])
    strategy = NeuralSearchStrategy(space, NeuralSearchConfig(n_initial=3, seed=41))
    evaluations = [
        Evaluation(
            str(i),
            {"n": 1},
            space.normalize({"n": 1}),
            [],
            float(i),
            True,
            metadata={"replica_id": str(i)},
        )
        for i in range(4)
    ]
    real_fit = _deps.fit_gpytorch_mll
    with patch.object(_deps, "fit_gpytorch_mll", wraps=real_fit) as fit:
        candidate = strategy._suggest_from_surrogate(evaluations, None)
    assert fit.call_count == 1
    assert candidate.source_strategy == "neural_gp"
    assert candidate.params == {"n": 1}
    assert candidate.params_normalized == (0.5,)
    assert candidate.predicted_mean is not None and candidate.predicted_std is not None
    assert candidate.metadata["prediction_basis"] == "executed_action"
