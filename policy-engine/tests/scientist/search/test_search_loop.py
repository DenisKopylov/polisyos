"""
Verification tests for Phase 17: Search Loop + Two-Stage + Engine Abstraction.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from polisyos.scientist.search.controller import (
    SearchConfig,
    SearchController,
    SearchStatus,
)
from polisyos.scientist.search.objective import (
    CompositeObjective,
    GDPGrowthObjective,
    ObjectivePresets,
)
from polisyos.scientist.search.stages import CheapStage, ExpensiveStage
from polisyos.scientist.search.stopping import (
    CompositeStoppingCriterion,
    ImprovementPlateau,
    MaxIterations,
    MaxWallTime,
)
from polisyos.scientist.workflows.engine_simple import SimpleLoopEngine


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_candidate_generator():
    """Generator that produces candidates converging to x=0."""

    class QuadraticGenerator:
        def __init__(self):
            self._iteration = 0

        def generate(
            self,
            history: List[Any],
            current_best: Dict[str, Any] | None,
            context: Dict[str, Any],
        ) -> Dict[str, Any]:
            if current_best:
                x = current_best.get("x", 1.0)
                x = x * 0.5
            else:
                x = 1.0

            self._iteration += 1
            return {"x": x, "semantic": {"interventions": []}}

    return QuadraticGenerator()


@pytest.fixture
def quadratic_objective():
    """Objective f(x) = x^2, minimum at x=0."""

    class QuadraticObjective:
        @property
        def name(self) -> str:
            return "quadratic"

        def evaluate(self, results: Dict[str, Any]) -> Any:
            from polisyos.scientist.search.objective import (
                ObjectiveValue,
                OptimizationDirection,
            )

            x = results.get("x", 0.0)
            return ObjectiveValue(
                name=self.name,
                raw_value=x**2,
                direction=OptimizationDirection.MINIMIZE,
            )

    return CompositeObjective([QuadraticObjective()])


# ─────────────────────────────────────────────────────────────────────────────
# Test: Optimization Flow
# ─────────────────────────────────────────────────────────────────────────────


class TestOptimizationFlow:
    """
    Test that search loop finds optimal solution for simple objective.

    Mock the ExpensiveStage with f(x) = x^2. Assert the search loop
    converges toward the minimum at x=0.
    """

    def test_search_finds_quadratic_minimum(
        self,
        mock_candidate_generator,
        quadratic_objective,
    ):
        """Search should converge toward x=0 for f(x)=x^2."""

        def stage_a_evaluator(candidate, context):
            return 0.0, True

        def stage_b_evaluator(candidate, context):
            x = candidate.get("x", 1.0)
            return {
                "simulation_results": {"x": x, "objective_value": x**2},
                "feedback": {"verdict": "APPROVE"},
            }

        config = SearchConfig(
            stopping=MaxIterations(10),
            objective=quadratic_objective,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run(
            initial_context={"user_request": "test"},
            initial_candidate={"x": 1.0, "semantic": {"interventions": []}},
        )

        assert result.best_candidate is not None
        assert result.best_candidate["x"] < 0.1
        assert result.best_objective < 0.01

    def test_search_respects_max_iterations(self, mock_candidate_generator, quadratic_objective):
        """Search must stop exactly at max_iterations."""

        def stage_a_evaluator(candidate, context):
            return 0.0, True

        def stage_b_evaluator(candidate, context):
            return {"simulation_results": {"x": 1.0}, "feedback": {"verdict": "APPROVE"}}

        config = SearchConfig(
            stopping=MaxIterations(5),
            objective=quadratic_objective,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run({"user_request": "test"})

        assert result.iterations_completed == 5
        assert "Maximum iterations" in result.stopping_reason


# ─────────────────────────────────────────────────────────────────────────────
# Test: Stopping Criteria
# ─────────────────────────────────────────────────────────────────────────────


class TestStoppingCriteria:
    """Test stopping criteria behavior."""

    def test_max_iterations_stops_exactly(self):
        """MaxIterations(5) should stop after exactly 5 iterations."""
        criterion = MaxIterations(5)

        history = []
        for i in range(10):
            result = criterion.check(history, {"iteration": i})
            if result.should_stop:
                assert i == 5
                break
            history.append({"iteration": i, "objective_value": 1.0})
        else:
            pytest.fail("Should have stopped")

    def test_improvement_plateau_triggers(self):
        """ImprovementPlateau should trigger when no improvement."""
        criterion = ImprovementPlateau(patience=3, min_improvement=0.01)

        history = [
            {"objective_value": 1.0},
            {"objective_value": 1.0},
            {"objective_value": 1.0},
            {"objective_value": 1.0},
        ]

        result = criterion.check(history, {})
        assert result.should_stop
        assert "plateau" in result.reason.lower()

    def test_composite_stops_on_first_trigger(self):
        """Composite should stop when ANY criterion triggers."""
        composite = CompositeStoppingCriterion(
            [
                MaxIterations(10),
                MaxWallTime(0.001),
            ]
        )

        import time

        time.sleep(0.01)

        result = composite.check([{"objective_value": 1.0}], {})
        assert result.should_stop
        assert "wall_time" in result.details.get("triggered_by", "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test: Two-Stage Filtering
# ─────────────────────────────────────────────────────────────────────────────


class TestTwoStageFiltering:
    """
    Test that Stage A filtering prevents Stage B execution.

    Critical: If CheapStage returns is_promising=False, ExpensiveStage
    should NEVER be called. This saves expensive simulation compute.
    """

    def test_stage_a_rejection_skips_stage_b(self, mock_candidate_generator, quadratic_objective):
        """ExpensiveStage should NOT be called if CheapStage rejects."""

        stage_b_called = [False]

        def stage_a_evaluator(candidate, context):
            return 1.0, False

        def stage_b_evaluator(candidate, context):
            stage_b_called[0] = True
            return {"simulation_results": {}, "feedback": {"verdict": "APPROVE"}}

        config = SearchConfig(
            stopping=MaxIterations(3),
            objective=quadratic_objective,
            enable_stage_a=True,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run({"user_request": "test"})

        assert not stage_b_called[0], "Stage B was called despite Stage A rejection!"
        assert result.stage_a_evaluations == 3
        assert result.stage_b_evaluations == 0

    def test_stage_a_approval_runs_stage_b(self, mock_candidate_generator, quadratic_objective):
        """ExpensiveStage SHOULD be called if CheapStage approves."""

        stage_b_count = [0]

        def stage_a_evaluator(candidate, context):
            return 0.0, True

        def stage_b_evaluator(candidate, context):
            stage_b_count[0] += 1
            return {"simulation_results": {"x": 1.0}, "feedback": {"verdict": "APPROVE"}}

        config = SearchConfig(
            stopping=MaxIterations(3),
            objective=quadratic_objective,
            enable_stage_a=True,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run({"user_request": "test"})

        assert stage_b_count[0] == 3
        assert result.stage_b_evaluations == 3

    def test_cheap_stage_rejects_invalid_params(self):
        """CheapStage should reject policies with invalid parameters."""
        stage = CheapStage(threshold=0.5)

        bad_candidate = {
            "semantic": {
                "interventions": [
                    {"mechanism": "income_tax", "parameters": {"rate": 1.5}}
                ],
            },
        }

        result = stage.evaluate(bad_candidate, {})

        assert not result.is_promising
        assert result.objective_value >= 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Test: Workflow Engine Abstraction
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkflowEngineAbstraction:
    """Test that WorkflowEngine protocol is properly implemented."""

    def test_simple_engine_runs_to_completion(self):
        """SimpleLoopEngine should execute all nodes."""
        execution_log = []

        def node_a(state):
            execution_log.append("a")
            return {**state, "a_done": True}

        def node_b(state):
            execution_log.append("b")
            return {**state, "b_done": True}

        engine = SimpleLoopEngine(
            [
                ("node_a", node_a),
                ("node_b", node_b),
            ]
        )

        result = engine.run({"initial": True})

        assert execution_log == ["a", "b"]
        assert result["a_done"]
        assert result["b_done"]

    def test_simple_engine_step_by_step(self):
        """SimpleLoopEngine.step() should execute one node at a time."""

        def node_a(state):
            return {**state, "step": 1}

        def node_b(state):
            return {**state, "step": 2}

        engine = SimpleLoopEngine(
            [
                ("node_a", node_a),
                ("node_b", node_b),
            ]
        )

        state = {"initial": True}

        state, done = engine.step(state)
        assert state["step"] == 1
        assert not done

        state, done = engine.step(state)
        assert state["step"] == 2
        assert done

    def test_engine_protocol_compliance(self):
        """Verify engines satisfy WorkflowEngine protocol."""
        from polisyos.scientist.workflows.engine_base import WorkflowEngine

        engine = SimpleLoopEngine([("test", lambda s: s)])

        assert hasattr(engine, "run")
        assert hasattr(engine, "step")
        assert hasattr(engine, "current_phase")
        assert hasattr(engine, "reset")

        assert isinstance(engine, WorkflowEngine)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Objectives
# ─────────────────────────────────────────────────────────────────────────────


class TestObjectives:
    """Test objective evaluation."""

    def test_gdp_objective_maximizes(self):
        """GDP objective should maximize (negative normalized value)."""
        obj = GDPGrowthObjective(weight=1.0)

        result = obj.evaluate({"gdp_change": 0.05})

        assert result.raw_value == 0.05
        assert result.normalized_value == -0.05

    def test_composite_combines_correctly(self):
        """Composite objective should combine weighted normalized values."""
        objective = ObjectivePresets.balanced_growth()

        results = {
            "gdp_change": 0.03,
            "gov_balance": -100.0,
            "gini_coefficient": 0.35,
        }

        value = objective.evaluate(results)

        assert isinstance(value.raw_value, float)
        assert value.is_satisfied


# ─────────────────────────────────────────────────────────────────────────────
# Integration Test
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegration:
    """Full integration tests for the search system."""

    def test_end_to_end_search_with_mock_workflow(self):
        """
        End-to-end test: SearchController -> CheapStage -> ExpensiveStage
        with mocked workflow engine.
        """
        mock_engine = MagicMock()
        mock_engine.run.return_value = {
            "simulation_results": {
                "gdp_change": 0.02,
                "gov_balance": 50.0,
                "gini_coefficient": 0.3,
            },
            "feedback": {"verdict": "APPROVE"},
        }

        cheap = CheapStage(threshold=0.5)
        expensive = ExpensiveStage(mock_engine)

        def stage_a_fn(candidate, context):
            result = cheap.evaluate(candidate, context)
            return result.objective_value, result.is_promising

        def stage_b_fn(candidate, context):
            result = expensive.evaluate(candidate, context)
            return {
                "simulation_results": result.simulation_results,
                "feedback": result.feedback,
            }

        class StaticGenerator:
            def generate(self, history, best, context):
                return {
                    "semantic": {
                        "interventions": [
                            {"mechanism": "tax", "parameters": {"rate": 0.2}}
                        ],
                        "objectives": ["growth"],
                    },
                }

        config = SearchConfig(
            stopping=MaxIterations(2),
            objective=ObjectivePresets.balanced_growth(),
        )

        controller = SearchController(
            config=config,
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=stage_a_fn,
            stage_b_evaluator=stage_b_fn,
        )

        result = controller.run({"user_request": "Optimize growth"})

        assert result.status == SearchStatus.STOPPED
        assert result.iterations_completed == 2
        assert result.best_candidate is not None
        assert mock_engine.run.call_count == 2
