"""Full-stream physical-objective, conditional-fraction and payload witnesses."""

from __future__ import annotations

import gc
from pathlib import Path

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


def _plan(**updates: object) -> AdversarialPlan:
    return AdversarialPlan(
        parameter_specs=[ParameterSpec(name="p", lower_bound=-1.0, upper_bound=1.0)],
        strategy=AdversarialStrategy.GRID_EXTREME,
        max_iterations=2,
        stop_on_first_vulnerability=False,
        **updates,
    )


@pytest.mark.parametrize("kind", ["gdp", "cost"])
@pytest.mark.parametrize("threshold", [-0.5, 0.0, 0.5])
def test_physical_direction_fraction_and_exact_cas_readback(
    tmp_path: Path, kind: str, threshold: float
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    objective = CompositeObjective(
        [GDPGrowthObjective()] if kind == "gdp" else [BudgetDeficitObjective()]
    )
    seen = []

    def evaluator(candidate: dict, context: dict) -> dict:
        physical = candidate["p"] if kind == "gdp" else candidate["p"] + 2.0
        seen.append(physical)
        return {
            "simulation_results": {"gdp_change" if kind == "gdp" else "budget_deficit": physical}
        }

    # GDP is normalized to -GDP; cost already has minimization coordinates.
    selected_threshold = threshold if kind == "gdp" else threshold + 2.0
    report = run_stress_test(
        adversarial_plan=_plan(vulnerability_threshold=selected_threshold),
        base_objective=objective,
        stage_b_evaluator=evaluator,
        cas=store,
    )
    bad = (
        [x <= -selected_threshold for x in seen]
        if kind == "gdp"
        else [x >= selected_threshold for x in seen]
    )
    assert report.worst_case_parameters == {"p": -1.0 if kind == "gdp" else 1.0}
    assert report.worst_case_objective == (1.0 if kind == "gdp" else 3.0)
    assert report.total_scenarios_evaluated == len(seen) == 2
    assert report.metadata["attempted"] == 2
    assert report.metadata["finite_evaluated"] == 2
    assert report.metadata["violated_scenarios"] == sum(bad)
    assert report.robustness_score == (len(seen) - sum(bad)) / len(seen)
    assert report.metadata["completeness"] is True
    assert report.metadata["score_scope"] == "observed_finite_scenarios"
    reopened = FileSystemCAS(tmp_path / "cas")
    payload = from_canonical_bytes(reopened.get_bytes(report.cas_artifact_id))
    restored = StressTestReport.model_validate(payload)
    assert restored.metadata == report.metadata
    assert restored.robustness_score == report.robustness_score
    assert restored.worst_case_parameters == report.worst_case_parameters


@pytest.mark.parametrize("invalid_count", [1, 2])
def test_unknown_outcomes_are_separate_from_finite_fraction(invalid_count: int) -> None:
    outcomes = iter([None] * invalid_count + [1.0] * (2 - invalid_count))

    def evaluator(candidate: dict, context: dict) -> object:
        value = next(outcomes)
        return None if value is None else {"simulation_results": {"budget_deficit": value}}

    report = run_stress_test(
        adversarial_plan=_plan(vulnerability_threshold=2.0),
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=evaluator,
    )
    assert report.metadata["attempted"] == 2
    assert report.metadata["finite_evaluated"] == 2 - invalid_count
    assert report.metadata["unknown_or_nonfinite"] == invalid_count
    assert report.metadata["violated_scenarios"] == 0
    assert report.total_scenarios_evaluated == 2 - invalid_count
    assert report.robustness_score == (1.0 if invalid_count == 1 else None)
    assert report.set_adequacy_status == "partial"
    assert report.metadata["completeness"] is False


def test_first_violation_does_not_claim_complete_observed_stream() -> None:
    plan = _plan(vulnerability_threshold=0.0).model_copy(
        update={"stop_on_first_vulnerability": True}
    )
    report = run_stress_test(
        adversarial_plan=plan,
        base_objective=CompositeObjective([GDPGrowthObjective()]),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"gdp_change": candidate["p"]}
        },
    )
    assert report.metadata["attempted"] == report.metadata["finite_evaluated"] == 1
    assert report.metadata["violated_scenarios"] == 1
    assert report.robustness_score == 0.0
    assert report.set_adequacy_status == "partial"
    assert report.metadata["completeness"] is False


class RepeatingProposal:
    """Produce the same executed action; retain the actual observed best."""

    def __init__(self, p: float = 0.0) -> None:
        self.p = p
        self.current_bests = []

    def generate(self, history: list, current_best: dict | None, context: dict) -> dict:
        self.current_bests.append(current_best)
        return {"p": self.p}


@pytest.mark.parametrize("kind", ["gdp", "cost"])
def test_typed_adaptive_extremum_and_best_feedback_survive_cas(tmp_path: Path, kind: str) -> None:
    class PhysicalProposal:
        def __init__(self) -> None:
            self.values = iter([-2.0, -3.0, 0.0] if kind == "gdp" else [2.0, 3.0, 0.0])
            self.bests = []

        def generate(self, history: list, current_best: dict | None, context: dict) -> dict:
            self.bests.append(current_best)
            return {"p": next(self.values)}

    proposal = PhysicalProposal()
    store = FileSystemCAS(tmp_path / "cas")
    report = run_stress_test(
        adversarial_plan=AdversarialPlan(
            parameter_specs=[ParameterSpec(name="p", lower_bound=-1.0, upper_bound=1.0)],
            strategy=AdversarialStrategy.SEARCH_LOOP,
            max_iterations=35,
            vulnerability_threshold=1.5 if kind == "gdp" else 3.5,
            stop_on_first_vulnerability=False,
            seed=7,
        ),
        base_objective=CompositeObjective(
            [GDPGrowthObjective()] if kind == "gdp" else [BudgetDeficitObjective()]
        ),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {
                "gdp_change" if kind == "gdp" else "budget_deficit": (
                    candidate["p"] if kind == "gdp" else candidate["p"] + 2.0
                )
            }
        },
        candidate_generator=proposal,
        cas=store,
    )
    sign = -1.0 if kind == "gdp" else 1.0
    assert proposal.bests == [None, {"p": 2.0 * sign}, {"p": 3.0 * sign}]
    assert report.worst_case_parameters == {"p": 3.0 * sign}
    assert report.worst_case_objective == (3.0 if kind == "gdp" else 5.0)
    assert report.metadata["finite_evaluated"] == 35
    assert report.metadata["violated_scenarios"] == 2
    assert report.robustness_score == pytest.approx(33 / 35)
    restored = StressTestReport.model_validate(
        from_canonical_bytes(FileSystemCAS(tmp_path / "cas").get_bytes(report.cas_artifact_id))
    )
    assert restored.worst_case_parameters == report.worst_case_parameters
    assert restored.robustness_score == report.robustness_score
    assert restored.metadata == report.metadata


@pytest.mark.parametrize("cap", [1, 10])
def test_repeated_scenarios_are_not_unique_issue_denominator(cap: int) -> None:
    proposal = RepeatingProposal()
    calls = 0

    def evaluator(candidate: dict, context: dict) -> dict:
        nonlocal calls
        calls += 1
        return {"simulation_results": {"budget_deficit": 1.0 if calls <= 32 else 3.0}}

    report = run_stress_test(
        adversarial_plan=AdversarialPlan(
            parameter_specs=[ParameterSpec(name="p", lower_bound=-1.0, upper_bound=1.0)],
            strategy=AdversarialStrategy.SEARCH_LOOP,
            max_iterations=42,
            vulnerability_threshold=2.0,
            stop_on_first_vulnerability=False,
            collect_top_k=cap,
            seed=7,
        ),
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=evaluator,
        candidate_generator=proposal,
    )
    assert len(proposal.current_bests) == 10
    assert report.metadata["attempted"] == report.metadata["finite_evaluated"] == 42
    assert report.metadata["violated_scenarios"] == 10
    assert report.metadata["unique_vulnerability_count"] == 1
    assert len(report.vulnerabilities) == 1
    assert report.robustness_score == pytest.approx(32 / 42)
    assert report.high_count == 10


def test_search_loop_without_adaptive_producer_remains_partial() -> None:
    report = run_stress_test(
        adversarial_plan=AdversarialPlan(
            parameter_specs=[ParameterSpec(name="p", lower_bound=-1.0, upper_bound=1.0)],
            strategy=AdversarialStrategy.SEARCH_LOOP,
            max_iterations=40,
            vulnerability_threshold=2.0,
            stop_on_first_vulnerability=False,
            seed=7,
        ),
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"budget_deficit": 1.0}
        },
    )
    assert report.total_scenarios_evaluated == 32
    assert report.robustness_score == 1.0
    assert report.metadata["completeness"] is False
    assert report.set_adequacy_status == "partial"


def test_full_vulnerability_payloads_are_bounded_during_real_run() -> None:
    gc.collect()
    before = sum(type(obj) is Vulnerability for obj in gc.get_objects())
    observed = []

    def evaluator(candidate: dict, context: dict) -> dict:
        gc.collect()
        observed.append(sum(type(obj) is Vulnerability for obj in gc.get_objects()) - before)
        return {"simulation_results": {"budget_deficit": 3.0}}

    report = run_stress_test(
        adversarial_plan=AdversarialPlan(
            parameter_specs=[ParameterSpec(name="p", lower_bound=-1.0, upper_bound=1.0)],
            strategy=AdversarialStrategy.RANDOM_TAIL,
            max_iterations=20,
            vulnerability_threshold=2.0,
            stop_on_first_vulnerability=False,
            collect_top_k=2,
            seed=7,
        ),
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=evaluator,
    )
    assert max(observed) <= 3
    assert len(report.vulnerabilities) == 2
    assert report.metadata["violated_scenarios"] == 20
