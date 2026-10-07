"""Independent raw fiscal-value and real consumer checks; no unit contract inferred."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import MetricDirection
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchEvaluatorPorts,
)
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.strategies import bayesian


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        pytest.param({}, None, id="absent-all"),
        pytest.param(
            {
                "gov_balance": None,
                "government_balance": None,
                "budget_deficit": None,
                "deficit": None,
            },
            None,
            id="null-all",
        ),
        pytest.param({"budget_deficit": 17.25}, 17.25, id="absent-primary-valid-deficit"),
        pytest.param(
            {"gov_balance": None, "budget_deficit": 17.25},
            17.25,
            id="null-primary-valid-deficit",
        ),
        pytest.param(
            {"gov_balance": None, "government_balance": -12.5},
            12.5,
            id="null-primary-valid-balance-alias",
        ),
        pytest.param({"gov_balance": 0.0, "budget_deficit": 99.0}, 0.0, id="zero-primary-wins"),
        pytest.param(
            {"government_balance": 0.0, "deficit": 99.0},
            0.0,
            id="zero-balance-alias-wins",
        ),
        pytest.param({"gov_balance": -12.5}, 12.5, id="negative-balance-deficit"),
        pytest.param({"gov_balance": 12.5}, 0.0, id="positive-balance-surplus"),
        pytest.param({"deficit": -12.5}, 12.5, id="negative-deficit-absolute"),
        pytest.param(
            {"gov_balance": -12.5, "government_balance": -12.5},
            12.5,
            id="equal-balance-aliases",
        ),
        pytest.param(
            {"gov_balance": -12.5, "government_balance": 12.5},
            None,
            id="conflicting-balance-aliases",
        ),
        pytest.param({"budget_deficit": 12.5, "deficit": 12.5}, 12.5, id="equal-deficit-aliases"),
        pytest.param(
            {"budget_deficit": 12.5, "deficit": 15.0}, None, id="conflicting-deficit-aliases"
        ),
        pytest.param(
            {"gov_balance": "bad", "budget_deficit": 99.0},
            None,
            id="present-malformed-primary-no-fallback",
        ),
        pytest.param(
            {"budget_deficit": "bad", "deficit": 99.0},
            None,
            id="present-malformed-deficit-no-fallback",
        ),
        pytest.param(
            {"gov_balance": math.nan, "budget_deficit": 99.0},
            None,
            id="present-nan-primary-no-fallback",
        ),
        pytest.param(
            {"gov_balance": math.inf, "budget_deficit": 99.0},
            None,
            id="present-inf-primary-no-fallback",
        ),
        pytest.param(
            {"gov_balance": False, "budget_deficit": 99.0},
            None,
            id="bool-false-primary-no-favorable-zero",
        ),
        pytest.param({"gov_balance": True}, None, id="bool-true-primary-no-favorable-zero"),
        pytest.param({"government_balance": False}, None, id="bool-false-alias-no-favorable-zero"),
        pytest.param({"budget_deficit": False}, None, id="bool-false-deficit-no-favorable-zero"),
        pytest.param({"deficit": True}, None, id="bool-true-deficit-not-measurement"),
        pytest.param(
            {"gov_balance": 10**400, "deficit": 99.0},
            None,
            id="overflow-integer-primary-unavailable",
        ),
    ],
)
def test_raw_deficit_presence_sign_and_unavailable_values(metrics, expected):
    value = BudgetDeficitObjective().evaluate(metrics)
    assert value.direction is OptimizationDirection.MINIMIZE
    if expected is None:
        assert math.isnan(value.raw_value)
        assert value.is_satisfied is False
    else:
        assert value.raw_value == expected
        assert value.normalized_value == expected
        assert value.weighted_value == expected
        assert value.is_satisfied is True


class _Generator:
    def generate(self, history, current_best, context):
        del history, current_best, context
        return {"candidate_id": "challenger"}


@pytest.mark.parametrize(
    "challenger",
    [
        pytest.param({"gov_balance": False, "budget_deficit": 99.0}, id="bool-false"),
        pytest.param({}, id="missing"),
        pytest.param({"gov_balance": 10**400}, id="overflow-int"),
    ],
)
def test_public_native_controller_keeps_valid_seed_for_unusable_challenger(challenger):
    calls = []

    def stage_b(candidate, context):
        del context
        calls.append(candidate["candidate_id"])
        metrics = {"gov_balance": -10.0} if candidate["candidate_id"] == "seed" else challenger
        return {"simulation_results": metrics, "feedback": {"verdict": "APPROVE"}}

    controller = SearchController(
        SearchConfig(
            stopping=MaxIterations(2),
            objective=CompositeObjective([BudgetDeficitObjective()]),
            max_iterations_hard_limit=2,
        ),
        candidate_generator=_Generator(),
        evaluators=SearchEvaluatorPorts(
            stage_a=lambda candidate, context: (0.0, True), stage_b=stage_b
        ),
    )
    result = controller.run({}, {"candidate_id": "seed"})
    assert calls == ["seed", "challenger"]
    assert result.best_candidate == {"candidate_id": "seed"}
    assert result.best_objective == 10.0
    assert len(result.history) == 2
    assert math.isnan(result.history[-1].objective_value)
    assert result.history[-1].objective_details[0].is_satisfied is False


@pytest.mark.parametrize(
    "raw_bad",
    [
        pytest.param(False, id="bool-false"),
        pytest.param(True, id="bool-true"),
        pytest.param(10**400, id="overflow-int"),
    ],
)
def test_public_bayesian_generator_excludes_unmeasured_score_before_actual_gp_fit(
    raw_bad, monkeypatch
):
    generator = BayesianCandidateGenerator(
        search_space=SearchSpace([{"name": "x", "lower": 0.0, "upper": 1.0}]),
        primary_metric="budget_deficit",
        direction=MetricDirection.MINIMIZE,
        n_initial=100,
        seed=31,
    )
    if not generator.botorch_available:
        pytest.skip("UNRUN: actual optional Bayesian receiver backend unavailable")
    optimizer = generator._optimizer
    assert optimizer is not None
    assert optimizer._model is None
    consumed_corpora = []
    real_corpus = optimizer._effective_training_corpus

    def actual_corpus(evaluations):
        corpus = real_corpus(evaluations)
        consumed_corpora.append([row.candidate_id for row in corpus])
        return corpus

    def forbidden_fit(*args, **kwargs):
        pytest.fail("Declared cold-start receiver must not fit a GP on these two history rows")

    monkeypatch.setattr(optimizer, "_effective_training_corpus", actual_corpus)
    monkeypatch.setattr(bayesian, "fit_gpytorch_mll", forbidden_fit)
    history = [
        {
            "candidate": {"candidate_id": "measured", "params": {"x": 0.2}},
            "stage_b_result": {"simulation_results": {"budget_deficit": 5.0}},
        },
        {
            "candidate": {"candidate_id": "unmeasured", "params": {"x": 0.8}},
            "stage_b_result": {"simulation_results": {"budget_deficit": raw_bad}},
        },
    ]
    candidate = generator.generate(history, None, {})
    assert consumed_corpora == [["measured"]]
    assert optimizer._model is None
    assert candidate["_strategy_metadata"]["source"] == "sobol_init"
    assert 0.0 <= candidate["x"] <= 1.0
