"""Observed-scenario evidence survives real producer and blueprint publication."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.adversarial import run_stress_test
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _merge_stress_test_reports,
    _recompute_stress_test_report,
)
from polisyos.scientist.policy_design.adversary import ScenarioAttackSurface


def _run(values: list[float | None], *, threshold: float | None = 2.0, top_k: int = 1):
    outcomes = iter(values)

    def evaluate(candidate: dict, context: dict) -> dict | None:
        value = next(outcomes)
        return None if value is None else {"simulation_results": {"budget_deficit": value}}

    return run_stress_test(
        adversarial_plan=AdversarialPlan(
            parameter_specs=[ParameterSpec(name="p", lower_bound=-1.0, upper_bound=1.0)],
            strategy=AdversarialStrategy.RANDOM_TAIL,
            max_iterations=len(values),
            vulnerability_threshold=threshold,
            stop_on_first_vulnerability=False,
            collect_top_k=top_k,
            seed=7,
        ),
        base_objective=CompositeObjective([BudgetDeficitObjective()]),
        stage_b_evaluator=evaluate,
    )


@pytest.mark.parametrize("top_k", [1, 20])
def test_blueprint_fraction_uses_32_scenarios_not_one_issue_example(
    tmp_path: Path, top_k: int
) -> None:
    producer = _run([1.0] * 31 + [3.0], top_k=top_k)
    assert producer.robustness_score == 31 / 32
    assert len(producer.vulnerabilities) == 1
    published = _recompute_stress_test_report(producer)
    assert published.robustness_score == 31 / 32
    evidence = published.scenario_evidence
    assert evidence is not None
    assert (evidence.attempted, evidence.finite_evaluated, evidence.violated_scenarios) == (
        32,
        32,
        1,
    )
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        published.model_dump(mode="json"),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.StressTestReport", version=published.schema_version
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    reopened = FileSystemCAS(tmp_path / "cas")
    restored = StressTestReport.model_validate(
        from_canonical_bytes(reopened.get_bytes(ref.artifact_id))
    )
    assert restored.scenario_evidence == evidence
    assert restored.robustness_score == 31 / 32
    assert restored.metadata["score_scope"] == "observed_finite_scenarios"
    assert restored.metadata.get("population_probability", "not_established") == "not_established"


def test_absent_threshold_does_not_assess_robustness() -> None:
    report = _run([1.0, 1.0], threshold=None)
    assert report.robustness_score is None
    assert report.is_robust is False
    assert report.set_adequacy_status == "partial"
    assert report.metadata["score_status"] == "unavailable"
    assert _recompute_stress_test_report(report).robustness_score is None


@pytest.mark.parametrize("invalid", [True, False, "0", float("nan"), float("inf"), 10**400])
@pytest.mark.parametrize("intake", ["plan", "surface"])
def test_threshold_intakes_refuse_values_before_float_coercion(
    invalid: object, intake: str
) -> None:
    model = AdversarialPlan if intake == "plan" else ScenarioAttackSurface
    arguments = (
        {"parameter_specs": [ParameterSpec(name="p", lower_bound=-1, upper_bound=1)]}
        if intake == "plan"
        else {"candidate_id": "c"}
    )
    with pytest.raises(ValidationError):
        model(**arguments, vulnerability_threshold=invalid)


@pytest.mark.parametrize("values, expected", [([None, 1.0], 1.0), ([None, None], None)])
def test_unknown_or_empty_finite_basis_remains_partial(
    values: list, expected: float | None
) -> None:
    report = _recompute_stress_test_report(_run(values))
    assert report.robustness_score == expected
    assert report.is_robust is False
    assert report.set_adequacy_status == "partial"
    assert report.scenario_evidence.unknown_or_nonfinite == values.count(None)


def test_suite_replacement_keeps_count_basis_separate_from_issue_groups() -> None:
    base = _run([1.0] * 31 + [3.0])
    failing_suite = _run([1.0] * 3 + [3.0])
    failing_suite.metadata["challenge_suite_id"] = "strategic_gaming_v1"
    failing_suite.vulnerabilities[0].vulnerability_id = "strategic_gaming_v1:issue"
    merged = _recompute_stress_test_report(_merge_stress_test_reports(base, [failing_suite]))
    assert merged.robustness_score == 34 / 36
    passing_suite = _run([1.0] * 4)
    passing_suite.metadata["challenge_suite_id"] = "strategic_gaming_v1"
    replaced = _recompute_stress_test_report(_merge_stress_test_reports(merged, [passing_suite]))
    assert replaced.robustness_score == 35 / 36
    assert replaced.scenario_evidence.violated_scenarios == 1
    assert len(replaced.vulnerabilities) == 1


def test_legacy_issue_counts_cannot_supply_missing_scenario_evidence() -> None:
    legacy = StressTestReport(
        report_id="legacy", total_scenarios_evaluated=32, robustness_score=1.0
    )
    assert legacy.is_robust is False
    assert _recompute_stress_test_report(legacy).robustness_score is None
    merged = _recompute_stress_test_report(_merge_stress_test_reports(_run([1.0, 3.0]), [legacy]))
    assert merged.robustness_score is None
    assert merged.set_adequacy_status == "partial"


def test_known_complete_nonviolating_stream_is_robust() -> None:
    report = _recompute_stress_test_report(_run([1.0, 1.0]))
    assert report.robustness_score == 1.0
    assert report.is_robust is True
    assert report.set_adequacy_status == "complete"


@pytest.mark.parametrize("field, value", [("attempted", True), ("violated_scenarios", 3)])
def test_fresh_report_reader_refuses_corrupted_count_basis(field: str, value: object) -> None:
    payload = _run([1.0, 3.0]).model_dump(mode="json")
    payload["scenario_evidence"][field] = value
    with pytest.raises(ValidationError):
        StressTestReport.model_validate(payload)


def test_fresh_reader_refuses_score_independent_of_retained_basis() -> None:
    payload = _run([1.0, 3.0]).model_dump(mode="json")
    payload["robustness_score"] = 1.0
    with pytest.raises(ValidationError):
        StressTestReport.model_validate(payload)
