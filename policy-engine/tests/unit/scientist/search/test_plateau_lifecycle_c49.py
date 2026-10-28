"""The configured preset consumes actual source-reconciled lifecycle scores."""

from __future__ import annotations

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
