from __future__ import annotations

from datetime import datetime

from polisyos.scientist.methods.search.controller import SearchConfig, SearchController, SearchIteration
from polisyos.scientist.methods.search.diversity import ExclusionListBuilder, enrich_context_with_diversity
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.stopping import MaxIterations


def test_exclusion_list_builder_extracts_unique_mechanisms() -> None:
    history = [
        SearchIteration(
            iteration=0,
            candidate={"interventions": [{"mechanism_type": "tax_subsidy"}]},
            objective_value=1.0,
            objective_details=[],
            is_promising=True,
            stage_a_passed=True,
            stage_b_result=None,
            duration_seconds=0.01,
            timestamp=datetime.utcnow(),
        ),
        SearchIteration(
            iteration=1,
            candidate={"interventions": [{"kind": "income_tax"}, {"kind": "tax_subsidy"}]},
            objective_value=0.5,
            objective_details=[],
            is_promising=True,
            stage_a_passed=True,
            stage_b_result=None,
            duration_seconds=0.01,
            timestamp=datetime.utcnow(),
        ),
    ]
    exclusions = ExclusionListBuilder.build_from_history(history)
    assert exclusions == ["tax_subsidy", "income_tax"]
    enriched = enrich_context_with_diversity({"seed": 1}, history)
    assert enriched["excluded_mechanisms"] == exclusions
    assert "diversity_constraints" in enriched


def test_search_controller_injects_diversity_context(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_SEARCH_DIVERSITY_ENABLED", "true")

    class RecordingGenerator:
        def __init__(self) -> None:
            self.calls = 0
            self.contexts: list[dict[str, object]] = []

        def generate(self, history, current_best, context):
            del history, current_best
            self.contexts.append(dict(context))
            if self.calls == 0:
                candidate = {"interventions": [{"mechanism_type": "tax_subsidy"}]}
            else:
                candidate = {"interventions": [{"mechanism_type": "income_tax"}]}
            self.calls += 1
            return candidate

    generator = RecordingGenerator()
    objective = CompositeObjective([GDPGrowthObjective(weight=1.0)])

    def stage_a(candidate, context):
        del candidate, context
        return 0.0, True

    def stage_b(candidate, context):
        del context
        mechanism = candidate["interventions"][0]["mechanism_type"]
        score = 1.0 if mechanism == "tax_subsidy" else 0.5
        return {"simulation_results": {"gdp_change": score}, "feedback": {"verdict": "APPROVE"}}

    controller = SearchController(
        config=SearchConfig(stopping=MaxIterations(2), objective=objective),
        candidate_generator=generator,
        stage_a_evaluator=stage_a,
        stage_b_evaluator=stage_b,
    )
    result = controller.run(initial_context={"user_request": "test"})

    assert result.iterations_completed == 2
    assert len(generator.contexts) >= 2
    second_context = generator.contexts[1]
    assert "excluded_mechanisms" in second_context
    assert "tax_subsidy" in second_context["excluded_mechanisms"]
