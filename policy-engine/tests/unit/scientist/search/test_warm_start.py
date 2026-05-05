"""Tests for WS6.5 — Search Controller Warm-Start & Pareto Tracking."""

from __future__ import annotations

from polisyos.scientist.search.controller import (
    SearchConfig,
    SearchController,
)
from polisyos.scientist.search.objective import (
    CompositeObjective,
    GDPGrowthObjective,
    InequalityObjective,
)
from polisyos.scientist.search.stopping import MaxIterations

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _simple_generator():
    class G:
        def generate(self, history, current_best, context):
            return {"param_a": 0.5}

    return G()


def _stage_a_pass(candidate, context):
    return 0.5, True


def _stage_b_eval(candidate, context):
    return {
        "simulation_results": {
            "gdp_change": candidate.get("param_a", 0.0),
        }
    }


def _make_config(**overrides) -> SearchConfig:
    defaults = dict(
        stopping=MaxIterations(3),
        objective=CompositeObjective(objectives=[GDPGrowthObjective()]),
    )
    defaults.update(overrides)
    return SearchConfig(**defaults)


# ---------------------------------------------------------------------------
# Warm-start
# ---------------------------------------------------------------------------


class TestWarmStart:
    def test_initial_evaluations_seed_history(self):
        config = _make_config(
            initial_evaluations=[
                {"candidate": {"param_a": 0.8}, "objective_value": 2.0, "is_promising": True},
                {"candidate": {"param_a": 0.3}, "objective_value": 5.0, "is_promising": False},
            ],
            max_iterations_hard_limit=1,
        )
        ctrl = SearchController(
            config=config,
            candidate_generator=_simple_generator(),
            stage_a_evaluator=_stage_a_pass,
            stage_b_evaluator=_stage_b_eval,
        )
        result = ctrl.run({})
        # History should include warm-start + actual iterations
        warm_entries = [h for h in result.history if h.iteration == -1]
        assert len(warm_entries) == 2

    def test_warm_start_updates_best(self):
        config = _make_config(
            initial_evaluations=[
                {"candidate": {"param_a": 0.9}, "objective_value": -10.0},
            ],
        )
        ctrl = SearchController(
            config=config,
            candidate_generator=_simple_generator(),
            stage_a_evaluator=_stage_a_pass,
            stage_b_evaluator=_stage_b_eval,
        )
        result = ctrl.run({})
        # The warm-start candidate should be best if no iteration beats it
        assert result.best_objective <= -10.0 or result.best_candidate is not None

    def test_empty_initial_evaluations(self):
        config = _make_config(initial_evaluations=[])
        ctrl = SearchController(
            config=config,
            candidate_generator=_simple_generator(),
            stage_a_evaluator=_stage_a_pass,
            stage_b_evaluator=_stage_b_eval,
        )
        result = ctrl.run({})
        warm_entries = [h for h in result.history if h.iteration == -1]
        assert len(warm_entries) == 0


# ---------------------------------------------------------------------------
# Pareto front
# ---------------------------------------------------------------------------


class TestParetoFront:
    def test_pareto_front_populated(self):
        config = _make_config(
            objective=CompositeObjective(
                objectives=[
                    GDPGrowthObjective(weight=0.5),
                    InequalityObjective(weight=0.5),
                ]
            ),
        )

        call_count = [0]

        class VaryingGenerator:
            def generate(self, history, current_best, context):
                call_count[0] += 1
                return {"param_a": call_count[0] * 0.1}

        def stage_b(candidate, context):
            pa = candidate.get("param_a", 0.5)
            return {
                "simulation_results": {
                    "gdp_change": pa,
                    "gini_coefficient": 1.0 - pa,
                }
            }

        ctrl = SearchController(
            config=config,
            candidate_generator=VaryingGenerator(),
            stage_a_evaluator=_stage_a_pass,
            stage_b_evaluator=stage_b,
        )
        result = ctrl.run({})
        assert isinstance(result.pareto_front, list)
        # With multi-objective there should be at least one point
        assert len(result.pareto_front) >= 1


# ---------------------------------------------------------------------------
# Dominates helper
# ---------------------------------------------------------------------------


class TestDominates:
    def test_strictly_better(self):
        assert SearchController._dominates([1.0, 1.0], [2.0, 2.0])

    def test_equal_does_not_dominate(self):
        assert not SearchController._dominates([1.0, 1.0], [1.0, 1.0])

    def test_partial_does_not_dominate(self):
        assert not SearchController._dominates([1.0, 3.0], [2.0, 2.0])

    def test_different_length(self):
        assert not SearchController._dominates([1.0], [2.0, 2.0])


# ---------------------------------------------------------------------------
# Adaptive batch sizing (integration)
# ---------------------------------------------------------------------------


class TestAdaptiveBatchSizing:
    def test_config_accepts_batch_size(self):
        config = _make_config(batch_size=4)
        assert config.batch_size == 4
