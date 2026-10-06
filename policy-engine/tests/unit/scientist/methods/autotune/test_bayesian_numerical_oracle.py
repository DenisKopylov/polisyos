"""Independent physical arithmetic and actual public adapter numerical consumers."""

from unittest.mock import patch

import pytest
import torch

from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import BenchmarkSplit, MetricDirection
from polisyos.scientist.methods.search.strategies import bayesian as module
from polisyos.scientist.methods.search.strategies.types import StrategyState


def test_mixed_public_space_matches_independent_physical_encoding():
    space = SearchSpace(
        [
            {"name": "x", "lower": 0, "upper": 10},
            {"name": "n", "lower": 0.2, "upper": 1.8, "dtype": "integer"},
            {"name": "scale", "lower": 1, "upper": 100, "log_scale": True},
            {"name": "regime", "dtype": "categorical", "categories": ["A", "B"]},
        ]
    )
    physical = {"x": 3.0, "n": 1, "scale": 10.0, "regime": "B"}
    expected = (0.3, 0.5, 0.5, 0.0, 1.0)
    assert space.normalize(physical) == pytest.approx(expected)
    executed = space.candidate_from_vector((0.3, 0.12, 0.5, 0.25, 0.75))
    assert executed.params == pytest.approx(physical)
    assert executed.params_normalized == pytest.approx(expected)
    assert space.normalize(space.denormalize(expected)) == pytest.approx(expected)


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
def test_default_public_suggestion_consumes_real_seeded_torch_design():
    generator = BayesianCandidateGenerator(SearchSpace([{"name": "x", "lower": 0, "upper": 10}]))
    assert generator.botorch_available
    # This locked profile selects Torch's scramble, whose seed is not a
    # portable SciPy scramble.  Compute its expected draw without the adapter.
    independent = float(torch.quasirandom.SobolEngine(1, scramble=True, seed=42).draw(1)[0, 0])
    candidate = generator.generate([], {"x": 7}, {"sentinel": 1})
    assert candidate["x"] == pytest.approx(10 * independent)
    assert candidate["_strategy_metadata"]["source"] == "sobol_init"
    assert "sentinel" not in candidate


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
@pytest.mark.parametrize("direction", [MetricDirection.MINIMIZE, MetricDirection.MAXIMIZE])
def test_full_history_identity_reaches_actual_directional_training_and_json(direction):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
        primary_metric="cost",
        direction=direction,
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=4,
        seed=31,
    )
    history = []
    for i, (x, cost) in enumerate([(2, 20.0), (4, 8.0), (6, 4.0), (8, 8.0)], start=1):
        identity = {
            "candidate_id": f"sha256:{i:064x}",
            "evaluation_id": f"sha256:{i + 100:064x}",
            "origin": "declared-numerical-fixture",
            "split": "selection",
        }
        history.append(
            {
                "candidate": {"x": x, "_strategy_metadata": identity},
                "stage_a_passed": True,
                "stage_b_result": {**identity, "params": {"x": x}, "cost": cost},
            }
        )
    # A result-free fifth record must never become a fifth zero-valued observation.
    history.append({"candidate": {"x": 1}, "stage_a_passed": True})
    evaluations = generator._history_to_evaluations(history)
    assert len([row for row in evaluations if row.is_valid]) == 4
    for i, row in enumerate(evaluations[:4], start=1):
        assert row.candidate_id == f"sha256:{i:064x}"
        assert row.metadata["evaluation_id"] == f"sha256:{i + 100:064x}"
        assert row.metadata["origin"] == "declared-numerical-fixture"
        assert row.metadata["split"] == "selection"
    expected_x = [[0.2], [0.4], [0.6], [0.8]]
    sign = -1 if direction == MetricDirection.MINIMIZE else 1
    expected_y = [[sign * cost] for cost in (20.0, 8.0, 4.0, 8.0)]
    strategy = generator._optimizer
    train_x, train_y = strategy._prepare_training_data(evaluations)
    assert train_x.tolist() == expected_x
    assert train_y.tolist() == expected_y
    with patch.object(module, "fit_gpytorch_mll", wraps=module.fit_gpytorch_mll) as fit:
        strategy._fit_gp(train_x, train_y)
        state = StrategyState.from_artifact(strategy.get_state().to_artifact())
        restored = BayesianCandidateGenerator(
            generator._search_space,
            primary_metric="cost",
            direction=direction,
            compare_split=BenchmarkSplit.SELECTION,
            n_initial=4,
            seed=31,
        )._optimizer
        restored.set_state(state)
    assert fit.call_count == 1
    assert restored._fitted_train_X.tolist() == expected_x
    assert restored._fitted_train_y_bo.tolist() == expected_y
    assert len(restored._fitted_record_ids) == 4


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
@pytest.mark.parametrize("malformed", [False, True, 10**400])
def test_unmeasured_scalar_does_not_launder_through_history_into_training(malformed):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
        primary_metric="cost",
        direction=MetricDirection.MINIMIZE,
    )
    evaluations = generator._history_to_evaluations(
        [
            {"candidate": {"x": 2}, "stage_b_result": {"cost": 10.0}},
            {"candidate": {"x": 4}, "stage_b_result": {"cost": malformed}},
        ]
    )
    assert [row.is_valid for row in evaluations] == [True, False]
    train_x, train_y = generator._optimizer._prepare_training_data(evaluations)
    assert train_x.tolist() == [[0.2]]
    assert train_y.tolist() == [[-10.0]]


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
@pytest.mark.parametrize("malformed", ["false", "true", 0, 1, None, [], {}])
def test_present_untyped_stage_admission_is_rejected_without_scalar_fallback(malformed):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
        primary_metric="cost",
        direction=MetricDirection.MINIMIZE,
    )
    with patch.object(generator, "_history_score", side_effect=AssertionError("scalar fallback")):
        evaluations = generator._history_to_evaluations(
            [
                {
                    "candidate": {"x": 4},
                    "stage_a_passed": malformed,
                    "stage_b_result": {"cost": 0.0},
                    "objective_value": 0.0,
                }
            ]
        )
    assert len(evaluations) == 1
    assert evaluations[0].is_valid is False
    assert evaluations[0].metadata["invalid_reason"] == "malformed_stage_a_passed"
    assert generator._optimizer._effective_training_corpus(evaluations) == []


@pytest.mark.skipif(module.fit_gpytorch_mll is None, reason="optional GP stack unavailable")
@pytest.mark.parametrize(
    ("present", "value", "valid"), [(False, None, True), (True, True, True), (True, False, False)]
)
def test_absent_and_declared_boolean_stage_contract_is_preserved(present, value, valid):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]), primary_metric="cost"
    )
    entry = {"candidate": {"x": 4}, "stage_b_result": {"cost": 2.0}}
    if present:
        entry["stage_a_passed"] = value
    assert generator._history_to_evaluations([entry])[0].is_valid is valid
