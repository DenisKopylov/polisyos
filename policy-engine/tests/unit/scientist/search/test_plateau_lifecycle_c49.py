"""The configured preset consumes actual source-reconciled lifecycle scores."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import TypeAdapter

from polisyos.scientist.methods.search.contracts import SearchResult, SearchStatus
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.stopping import PlateauToleranceProfile, StoppingPresets


def test_real_search_lifecycle_uses_optional_profile_without_replacing_grounding():
    class Candidates:
        def generate(self, history, current_best, context):
            return {"semantic": {"interventions": []}, "ordinal": len(history)}

    stage_b_calls = []

    def evaluate(candidate, context):
        stage_b_calls.append(candidate)
        return {
            "simulation_results": {
                "gdp_change": 0.2,
                "metric_units": {"gdp_change": "fixture-gdp-unit"},
            }
        }

    profile = PlateauToleranceProfile(
        direction="minimize",
        unit="configured-composite-normalized-score",
        abs_tol=0.01,
        rel_tol=0.01,
    )
    controller = SearchController(
        config=SearchConfig(
            objective=CompositeObjective([GDPGrowthObjective(expected_unit="fixture-gdp-unit")]),
            stopping=StoppingPresets.default(max_iter=8, patience=2, tolerance_profile=profile),
        ),
        candidate_generator=Candidates(),
        stage_a_evaluator=lambda *_: (0.0, True),
        stage_b_evaluator=evaluate,
    )
    result = controller.run({"user_request": "portable plateau lifecycle fixture"})
    assert result.best_candidate is not None
    assert len(stage_b_calls) == 3
    assert "Improvement plateau" in result.stopping_reason
    assert "configured-composite-normalized-score" in result.stopping_reason
    assert all(row.score_assessment is not None for row in result.history)


def test_missing_units_do_not_manufacture_a_profile_plateau():
    class Candidates:
        def generate(self, history, current_best, context):
            return {"semantic": {"interventions": []}, "ordinal": len(history)}

    controller = SearchController(
        config=SearchConfig(
            objective=CompositeObjective([GDPGrowthObjective(expected_unit="fixture-gdp-unit")]),
            stopping=StoppingPresets.default(
                max_iter=4,
                patience=2,
                tolerance_profile=PlateauToleranceProfile(
                    direction="minimize",
                    unit="configured-composite-normalized-score",
                    abs_tol=0.01,
                    rel_tol=0.01,
                ),
            ),
        ),
        candidate_generator=Candidates(),
        stage_a_evaluator=lambda *_: (0.0, True),
        stage_b_evaluator=lambda *_: {"simulation_results": {"gdp_change": 0.2}},
    )
    result = controller.run({"user_request": "unknown source-unit fixture"})
    assert result.best_candidate is None
    assert "Maximum iterations" in result.stopping_reason
    assert all(row.objective_value is None for row in result.history)


def test_declared_extreme_gain_keeps_the_actual_lifecycle_running_until_resource_cap() -> None:
    class Candidates:
        def generate(
            self,
            history: Sequence[Any],
            current_best: dict[str, Any] | None,
            context: dict[str, Any],
        ) -> dict[str, Any]:
            return {"semantic": {"interventions": []}, "ordinal": len(history)}

    observations = iter((-1e308, 1e308, 1e308, 1e308))
    emitted = []

    def evaluate(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        measurement = next(observations)
        emitted.append(measurement)
        return {
            "simulation_results": {
                "gdp_change": measurement,
                "metric_units": {"gdp_change": "fixture-gdp-unit"},
            }
        }

    controller = SearchController(
        config=SearchConfig(
            objective=CompositeObjective([GDPGrowthObjective(expected_unit="fixture-gdp-unit")]),
            stopping=StoppingPresets.default(
                max_iter=4,
                patience=2,
                tolerance_profile=PlateauToleranceProfile(
                    direction="minimize",
                    unit="fixture-gdp-unit",
                    abs_tol=0.0,
                    rel_tol=1.8,
                ),
            ),
        ),
        candidate_generator=Candidates(),
        stage_a_evaluator=lambda *_: (0.0, True),
        stage_b_evaluator=evaluate,
    )
    result = controller.run({"user_request": "finite range boundary of the declared GDP score"})
    assert emitted == [-1e308, 1e308, 1e308, 1e308]
    assert [row.objective_value for row in result.history] == [1e308, -1e308, -1e308, -1e308]
    assert result.best_objective == -1e308
    assert result.status is SearchStatus.STOPPED
    assert result.stopping_reason is not None and "Maximum iterations" in result.stopping_reason

    adapter = TypeAdapter(SearchResult)
    reopened = adapter.validate_json(adapter.dump_json(result))
    assert reopened.status is SearchStatus.STOPPED
    assert reopened.stopping_reason == result.stopping_reason
    assert [row.score_assessment for row in reopened.history] == [
        row.score_assessment for row in result.history
    ]
