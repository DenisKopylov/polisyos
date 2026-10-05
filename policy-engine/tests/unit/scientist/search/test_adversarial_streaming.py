"""Behavioral witnesses for bounded stress payloads and complete occurrence counts."""

from __future__ import annotations

import gc
import math
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport, Vulnerability
from polisyos.scientist.methods.search.adversarial import run_stress_test
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    GDPGrowthObjective,
)
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds


@pytest.mark.parametrize("collect_top_k", [1, 3])
def test_stress_keeps_full_vulnerability_payloads_bounded_during_sweep(
    collect_top_k: int,
) -> None:
    """Keeping the uncapped payload list must fail even if final output is capped."""
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="stress_payload_probe", lower_bound=0, upper_bound=1)],
        strategy=AdversarialStrategy.RANDOM_TAIL,
        seed=71,
        max_iterations=24,
        vulnerability_threshold=0,
        stop_on_first_vulnerability=False,
        collect_top_k=collect_top_k,
    )
    retained_counts: list[int] = []

    def evaluate(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del candidate, context
        retained_counts.append(
            sum(
                type(item) is Vulnerability and "stress_payload_probe" in item.parameter_values
                for item in gc.get_objects()
            )
        )
        return {"simulation_results": {"budget_deficit": 10.0}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=evaluate,
    )

    # One additional payload may be the current loop's temporary; it is not retained history.
    assert max(retained_counts) <= collect_top_k + 1
    assert len(report.vulnerabilities) == collect_top_k
    assert report.total_scenarios_evaluated == report.high_count == 24
    assert report.metadata["observed_vulnerability_count"] == 24
    assert report.metadata["unique_vulnerability_count"] == 24
    assert report.robustness_score == 0.0


class RepeatedCandidateGenerator:
    """Revisit one physical scenario through the supported generator protocol."""

    def generate(self, history: list[Any], current_best: Any, context: Any) -> dict[str, Any]:
        del history, current_best, context
        return {"x": 0.0}


def test_stress_repeated_scenario_counts_occurrences_before_presentation_dedupe() -> None:
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="x", lower_bound=-1, upper_bound=1)],
        strategy=AdversarialStrategy.SEARCH_LOOP,
        seed=71,
        max_iterations=40,
        vulnerability_threshold=2,
        stop_on_first_vulnerability=False,
        collect_top_k=1,
    )

    def evaluate(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        return {"simulation_results": {"budget_deficit": 2.0 if candidate["x"] == 0 else 1.0}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=evaluate,
        candidate_generator=RepeatedCandidateGenerator(),
    )

    assert report.total_scenarios_evaluated == 40
    assert report.high_count == report.metadata["observed_vulnerability_count"] == 8
    assert report.metadata["unique_vulnerability_count"] == 1
    assert len(report.vulnerabilities) == 1
    assert report.robustness_score == 0.8


@pytest.mark.parametrize("metric", ["gdp_change", "gov_balance"])
@pytest.mark.parametrize("threshold", [-0.5, 0.5])
def test_stress_real_adaptive_objectives_persist_analytical_worst_case(
    metric: str,
    threshold: float,
    store: FileSystemCAS,
) -> None:
    """Real objective normalization, adapter feedback and CAS readback agree with the DGP."""
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="x", lower_bound=-1, upper_bound=1)],
        strategy=AdversarialStrategy.SEARCH_LOOP,
        seed=37,
        max_iterations=36,
        vulnerability_threshold=threshold,
        stop_on_first_vulnerability=False,
        collect_top_k=2,
    )
    coordinates: list[float] = []

    def evaluate(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        coordinates.append(candidate["x"])
        return {"simulation_results": {metric: candidate["x"]}}

    space = SearchSpace([ParameterBounds(name="x", lower=-1, upper=1)])
    adapter = StrategyAdapter(strategy=RandomSearchStrategy(space=space, seed=5), space=space)
    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective(
            [GDPGrowthObjective() if metric == "gdp_change" else BudgetDeficitObjective()]
        ),
        stage_b_evaluator=evaluate,
        candidate_generator=adapter,
        cas=store,
    )
    expected_values = [-x if metric == "gdp_change" else max(-x, 0) for x in coordinates]
    expected_worst_index = max(range(len(expected_values)), key=expected_values.__getitem__)
    expected_violations = sum(value >= threshold for value in expected_values)

    assert len(coordinates) == 36  # Initial sampler contributes 32, adapter another four.
    assert report.worst_case_objective == expected_values[expected_worst_index]
    assert report.worst_case_parameters == {"x": coordinates[expected_worst_index]}
    assert report.high_count == expected_violations
    assert report.robustness_score == 1 - expected_violations / len(coordinates)
    assert report.cas_artifact_id is not None
    reopened = StressTestReport.model_validate(
        from_canonical_bytes(store.get_bytes(report.cas_artifact_id))
    )
    assert reopened.worst_case_objective == report.worst_case_objective
    assert reopened.high_count == report.high_count
    assert reopened.metadata == report.metadata
    assert len(reopened.vulnerabilities) == 2
    assert math.isfinite(reopened.worst_case_objective)


@pytest.mark.parametrize(
    "invalid_result",
    [None, {"simulation_results": {}}, {"simulation_results": {"budget_deficit": "bad"}}],
)
def test_stress_invalid_attempts_keep_full_counts_when_examples_are_capped(
    invalid_result: object,
) -> None:
    plan = AdversarialPlan(
        parameter_specs=[ParameterSpec(name="x", lower_bound=-1, upper_bound=1)],
        strategy=AdversarialStrategy.RANDOM_TAIL,
        seed=37,
        max_iterations=24,
        vulnerability_threshold=0,
        stop_on_first_vulnerability=False,
        collect_top_k=1,
    )
    calls = 0

    def evaluate(candidate: dict[str, Any], context: dict[str, Any]) -> Any:
        nonlocal calls
        del candidate, context
        calls += 1
        if calls > 10:
            return invalid_result
        return {"simulation_results": {"budget_deficit": 4.0}}

    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=evaluate,
    )

    assert report.total_scenarios_evaluated == calls == 24
    assert report.high_count == report.metadata["valid_evaluation_count"] == 10
    assert report.critical_count == report.metadata["invalid_evaluation_count"] == 14
    assert report.metadata["observed_vulnerability_count"] == 24
    assert len(report.vulnerabilities) == 1
    assert report.set_adequacy_status == "unverified"
    assert report.robustness_score == 0.0
    assert not report.is_robust
