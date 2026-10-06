"""Canonical numeric intake refuses unrepresentable coordinates before native consumers."""

from fractions import Fraction

import pytest

from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, ParameterType

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "invalid",
    [10**400, -(10**400), True, False, "0.5", None, float("nan"), float("inf"), Fraction(1, 2)],
)
def test_coordinate_intake_refuses_invalid_numeric_domain(invalid):
    space = SearchSpace([ParameterBounds("x")])
    with pytest.raises(ValueError, match="Finite physical"):
        space.normalize({"x": invalid})
    with pytest.raises(ValueError, match="Normalized coordinates"):
        space.denormalize((invalid,))
    assert not space.same_execution({"x": invalid}, {"x": 0.5})


@pytest.mark.parametrize(
    "invalid", [10**400, -(10**400), True, False, "broken", None, float("nan"), float("inf")]
)
@pytest.mark.parametrize("endpoint", ["lower", "upper"])
def test_numeric_bounds_refuse_invalid_endpoint_with_controlled_error(invalid, endpoint):
    bounds = {"lower": 0.0, "upper": 1.0, endpoint: invalid}
    with pytest.raises(ValueError):
        ParameterBounds("x", **bounds)
    with pytest.raises(ValueError):
        ParameterBounds.explicit(name="x", **bounds)


def test_supported_mixed_actions_keep_typed_projection_and_zero():
    space = SearchSpace(
        [
            ParameterBounds("continuous", -2.0, 2.0),
            ParameterBounds("integer", -1.8, -0.2, dtype=ParameterType.INTEGER),
            ParameterBounds("log", 0.01, 100.0, dtype=ParameterType.LOG_CONTINUOUS),
            ParameterBounds("category", dtype=ParameterType.CATEGORICAL, categories=(True, 1, "1")),
        ]
    )
    for category in (True, 1, "1"):
        physical = {"continuous": 0.0, "integer": -1, "log": 1.0, "category": category}
        restored = space.denormalize(space.normalize(physical))
        assert restored["continuous"] == 0.0
        assert restored["integer"] == -1
        assert restored["log"] == pytest.approx(1.0)
        assert type(restored["category"]) is type(category)
        assert restored["category"] == category
    for point in (0.0, 0.5, 1.0):
        projected = space.candidate_from_vector((point, point, point, 0.1, 0.8, 0.1))
        assert projected.params["integer"] == -1
        assert projected.params_normalized == space.normalize(projected.params)
    with pytest.raises(ValueError, match="Unsupported representable span"):
        ParameterBounds("too_wide", -1e308, 1e308)
    with pytest.raises(ValueError, match="no attainable"):
        ParameterBounds("empty", 0.2, 0.8, dtype=ParameterType.INTEGER)


@pytest.mark.integration
@pytest.mark.parametrize("invalid", [10**400, -(10**400), True, float("inf")])
def test_native_receiver_refuses_invalid_physical_row_and_retains_valid_batch(invalid):
    pytest.importorskip("torch", reason="UNRUN: optional numerical backend", exc_type=ImportError)
    pytest.importorskip("botorch", reason="UNRUN: optional numerical backend", exc_type=ImportError)
    pytest.importorskip(
        "gpytorch", reason="UNRUN: optional numerical backend", exc_type=ImportError
    )
    from polisyos.scientist.methods.search.strategies.bayesian import (
        BayesianConfig,
        BayesianOptimizer,
    )
    from polisyos.scientist.methods.search.strategies.types import Evaluation

    strategy = BayesianOptimizer(
        SearchSpace([ParameterBounds("x")]), BayesianConfig(n_initial=6, seed=31)
    )
    rows = [
        Evaluation(name, {"x": x}, (normalized,), [], score, True)
        for name, x, normalized, score in [
            ("measured-a", 0.2, 0.2, 2.0),
            ("invalid", invalid, 0.4, 0.0),
            ("measured-b", 0.6, 0.6, 1.0),
        ]
    ]
    assert not strategy._has_compatible_params(rows[1])
    candidate = strategy.suggest(rows)
    assert candidate.source_strategy == "sobol_init"
    assert strategy._model is None
    assert [row.candidate_id for row in strategy._effective_training_corpus(rows)] == [
        "measured-a",
        "measured-b",
    ]
    assert candidate.params_normalized == strategy._space.normalize(candidate.params)
