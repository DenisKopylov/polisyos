from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import (
    CostBudgetStopping,
    MaxIterations,
)


class SimpleObjective:
    @property
    def name(self) -> str:
        return "x_abs"

    @property
    def direction(self):
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results):
        value = abs(float(results.get("x", 0.0)))
        return ObjectiveValue(name="x_abs", raw_value=value, direction=self.direction)


class BatchGenerator:
    def __init__(self):
        self._counter = 0
        self.batch_calls = 0
        self.single_calls = 0

    def generate(self, history, current_best, context):
        del history, current_best, context
        self.single_calls += 1
        value = float(self._counter)
        self._counter += 1
        return {"x": value, "semantic": {"interventions": []}}

    def generate_batch(self, history, current_best, context, batch_size):
        del history, current_best, context
        self.batch_calls += 1
        output = []
        for _ in range(batch_size):
            value = float(self._counter)
            self._counter += 1
            output.append({"x": value, "semantic": {"interventions": []}})
        return output


class DummyArbiter:
    def __init__(self):
        self.owners: list[str] = []

    @contextmanager
    def acquire(self, owner: str):
        self.owners.append(owner)
        yield


def test_controller_uses_batch_generator() -> None:
    generator = BatchGenerator()
    objective = CompositeObjective([SimpleObjective()])
    stage_b_calls = {"count": 0}

    def stage_a(candidate: dict[str, Any], context: dict[str, Any]):
        del candidate, context
        return 0.0, True

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]):
        del context
        stage_b_calls["count"] += 1
        return {"simulation_results": {"x": candidate["x"]}, "feedback": {"verdict": "APPROVE"}}

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(5),
            objective=objective,
            batch_size=3,
        ),
        candidate_generator=generator,
        stage_a_evaluator=stage_a,
        stage_b_evaluator=stage_b,
    )
    result = controller.run({"user_request": "batch"})
    assert result.iterations_completed == 5
    assert stage_b_calls["count"] == 5
    assert generator.batch_calls >= 1
    assert generator.single_calls == 0


def test_controller_falls_back_to_single_generation() -> None:
    objective = CompositeObjective([SimpleObjective()])

    class SingleOnlyGenerator:
        def __init__(self):
            self.calls = 0

        def generate(self, history, current_best, context):
            del history, current_best, context
            self.calls += 1
            return {"x": 1.0, "semantic": {"interventions": []}}

    generator = SingleOnlyGenerator()

    controller = SearchController(
        config=SearchConfig(stopping=MaxIterations(3), objective=objective, batch_size=4),
        candidate_generator=generator,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"x": candidate["x"]},
            "feedback": {"verdict": "APPROVE"},
        },
    )
    result = controller.run({"user_request": "single"})
    assert result.iterations_completed == 3
    assert generator.calls == 3


def test_controller_uses_resource_arbiter_for_stage_b() -> None:
    generator = BatchGenerator()
    arbiter = DummyArbiter()
    objective = CompositeObjective([SimpleObjective()])

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(2),
            objective=objective,
            resource_arbiter=arbiter,
        ),
        candidate_generator=generator,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"x": candidate["x"]},
            "feedback": {"verdict": "APPROVE"},
        },
    )
    _ = controller.run({"user_request": "arbiter"})
    assert arbiter.owners == ["jax", "jax"]


def test_controller_bounds_transient_empty_generation_and_separates_budget_from_iterations() -> (
    None
):
    class ScriptedBatchGenerator:
        def __init__(self):
            self.calls = 0

        def generate_batch(self, history, current_best, context, batch_size):
            del history, current_best, context, batch_size
            self.calls += 1
            if self.calls == 1:
                return []
            if self.calls == 2:
                return [{"x": 1.0, "semantic": {"interventions": []}}]
            return [{"x": 2.0, "semantic": {"interventions": []}}]

    generator = ScriptedBatchGenerator()
    objective = CompositeObjective([SimpleObjective()])
    context = {"cumulative_cost_usd": 0.0}
    stage_b_calls = {"count": 0}

    def stage_b(candidate, stage_context):
        stage_b_calls["count"] += 1
        stage_context["cumulative_cost_usd"] += 1.0
        return {
            "simulation_results": {"x": candidate["x"]},
            "feedback": {"verdict": "APPROVE"},
        }

    controller = SearchController(
        config=SearchConfig(
            stopping=CostBudgetStopping(max_cost_usd=1.0),
            objective=objective,
            batch_size=2,
            max_iterations_hard_limit=2,
        ),
        candidate_generator=generator,
        stage_a_evaluator=lambda candidate, stage_context: (0.0, True),
        stage_b_evaluator=stage_b,
    )

    result = controller.run(context)

    assert generator.calls == 2
    assert result.iterations_completed == 1
    assert result.stage_b_evaluations == 1
    assert stage_b_calls["count"] == 1
    transition = result.telemetry["generation_transition"]
    assert transition["kind"] == "transient_empty"
    assert transition["generation_attempts"] == 2
    assert transition["evaluation_iterations"] == 1
    assert transition["budget_spent"] == 1.0


def test_controller_limits_persistent_empty_without_claiming_source_exhaustion() -> None:
    class PersistentEmptyGenerator:
        def __init__(self):
            self.calls = 0

        def generate_batch(self, history, current_best, context, batch_size):
            del history, current_best, context, batch_size
            self.calls += 1
            if self.calls > 3:
                raise AssertionError(
                    "persistent-empty watchdog: controller requested a fourth batch"
                )
            return []

    generator = PersistentEmptyGenerator()

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([SimpleObjective()]),
            batch_size=2,
            max_iterations_hard_limit=1,
            max_empty_generation_attempts=3,
        ),
        candidate_generator=generator,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"x": candidate["x"]},
            "feedback": {"verdict": "APPROVE"},
        },
    )

    result = controller.run({"user_request": "persistent-empty"})

    assert generator.calls == 3
    assert result.iterations_completed == 0
    assert result.stage_b_evaluations == 0
    transition = result.telemetry["generation_transition"]
    assert result.stopping_reason == "generation_empty_attempt_limit"
    assert transition["kind"] == "attempt_limit"
    assert transition["generation_attempts"] == 3
    assert transition["evaluation_iterations"] == 0


@pytest.mark.parametrize("max_candidates", [2, 1])
def test_finite_grid_returns_last_short_batch_before_reporting_exhaustion(
    max_candidates: int,
) -> None:
    from polisyos.scientist.methods.search.objective import BudgetDeficitObjective
    from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
    from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
    from polisyos.scientist.methods.search.strategies.space import SearchSpace
    from polisyos.scientist.methods.search.strategies.types import ParameterBounds

    space = SearchSpace([ParameterBounds(name="x", lower=1.0, upper=2.0)])
    grid = GridSearchStrategy(space, points_per_dim=2, max_candidates=max_candidates)
    evaluated: list[float] = []

    def stage_b(candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        evaluated.append(candidate["x"])
        return {
            "simulation_results": {
                "budget_deficit": candidate["x"],
                "metric_units": {"budget_deficit": "EUR"},
            },
            "feedback": {"verdict": "APPROVE"},
        }

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(5),
            objective=CompositeObjective([BudgetDeficitObjective(expected_unit="EUR")]),
            batch_size=3,
        ),
        candidate_generator=StrategyAdapter(grid, space),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=stage_b,
    )

    result = controller.run({})

    assert evaluated == [1.0, 2.0][:max_candidates]
    assert result.iterations_completed == max_candidates
    assert result.best_objective == 1.0
    transition = result.telemetry["generation_transition"]
    if max_candidates == 2:
        assert result.stopping_reason == "generation_source_exhausted"
        assert transition["kind"] == "exhausted"
        assert transition["source_reason"] == "Grid exhausted after 2 candidates"
    else:
        assert result.stopping_reason == "generation_source_attempt_limit"
        assert transition["kind"] == "attempt_limit"
        assert transition["source_reason"] == "grid_candidate_limit_reached"
    assert transition["generation_attempts"] == 2


@pytest.mark.parametrize(
    ("case", "expected_calls", "expected_rows", "expected_kind", "expected_reason"),
    [
        ("recovered", 2, 1, "transient_empty", "Cost budget"),
        ("deadline", 1, 0, "attempt_limit", "generation_retry_deadline"),
        ("budget", 1, 0, "transient_empty", "Cost budget"),
        ("repair", 1, 0, "repair_required", "generation_repair_required"),
        ("bounded", 1, 0, "attempt_limit", "generation_source_attempt_limit"),
    ],
)
def test_explicit_generation_notice_controls_retry_and_precedes_evaluation(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_calls: int,
    expected_rows: int,
    expected_kind: str,
    expected_reason: str,
) -> None:
    from polisyos.scientist.methods.search import service
    from polisyos.scientist.methods.search.contracts import GenerationNotice, GenerationTransition
    from polisyos.scientist.methods.search.objective import BudgetDeficitObjective

    actual_context = {"cumulative_cost_usd": 0.0, "selected_resource": "missing"}
    pauses: list[float] = []
    monkeypatch.setattr(service, "sleep", pauses.append)

    class Source:
        calls = 0

        def generate(
            self, _history: list[Any], _best: dict[str, Any] | None, context: dict[str, Any]
        ) -> dict[str, Any]:
            self.calls += 1
            if case == "bounded":
                raise GenerationNotice(
                    GenerationTransition.ATTEMPT_LIMIT, "proposal_search_budget_exhausted"
                )
            if case == "repair" and context["selected_resource"] != "repaired":
                raise GenerationNotice(GenerationTransition.REPAIR_REQUIRED, "needs_resource")
            if self.calls == 1 and case != "repair":
                if case == "budget":
                    actual_context["cumulative_cost_usd"] = 1.0
                raise GenerationNotice(
                    GenerationTransition.TRANSIENT_EMPTY,
                    "source_unavailable",
                    retry_after_seconds=2.0 if case == "deadline" else 0.025,
                )
            return {"x": 1.0}

    def stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        context["cumulative_cost_usd"] += 1.0
        return {
            "simulation_results": {
                "budget_deficit": candidate["x"],
                "metric_units": {"budget_deficit": "EUR"},
            },
            "feedback": {"verdict": "APPROVE"},
        }

    source = Source()
    controller = SearchController(
        config=SearchConfig(
            stopping=CostBudgetStopping(max_cost_usd=1.0),
            objective=CompositeObjective([BudgetDeficitObjective(expected_unit="EUR")]),
        ),
        candidate_generator=source,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=stage_b,
    )

    result = controller.run(actual_context)

    assert source.calls == expected_calls
    assert result.iterations_completed == expected_rows
    assert result.telemetry["scientific_evaluations"] == expected_rows
    assert result.stopping_reason is not None and expected_reason in result.stopping_reason
    assert result.telemetry["generation_transition"]["kind"] == expected_kind
    expected_source_reason = {
        "repair": "needs_resource",
        "bounded": "proposal_search_budget_exhausted",
    }.get(case, "source_unavailable")
    assert result.telemetry["generation_transition"]["source_reason"] == expected_source_reason
    assert result.telemetry["generation_transition"]["generation_attempts"] == expected_calls
    assert result.telemetry["budget_spent"] == float(case in {"budget", "recovered"})
    assert pauses == ([0.025] if case == "recovered" else [])

    if case == "repair":
        actual_context["selected_resource"] = "repaired"
        repaired = controller.run(actual_context)
        assert repaired.iterations_completed == 1
        assert repaired.best_candidate == {"x": 1.0}
        assert repaired.best_objective == 1.0
