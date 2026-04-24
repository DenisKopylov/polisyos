from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from polisyos.scientist.search.controller import SearchConfig, SearchController
from polisyos.scientist.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.search.stopping import MaxIterations


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
