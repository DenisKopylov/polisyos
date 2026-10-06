"""Observed-scenario evidence survives real producer and blueprint publication."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.adversarial import run_stress_test
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _ensure_stress_test_report,
    _merge_stress_test_reports,
    _recompute_stress_test_report,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_STRESS_TEST_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.adversary import ScenarioAttackSurface
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


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


@pytest.mark.parametrize("legacy", [False, True])
def test_actual_blueprint_existing_report_path_requires_scenario_basis(
    tmp_path: Path, legacy: bool
) -> None:
    report = (
        StressTestReport(report_id="historical", total_scenarios_evaluated=32, robustness_score=1.0)
        if legacy
        else _run([1.0] * 31 + [3.0])
    )
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="blueprint-counts")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("blueprint-counts"))
    ref = store.put_json(
        report.model_dump(mode="json"),
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.StressTestReport", version=report.schema_version
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    original = store.get_bytes(ref.artifact_id)
    state = ExperimentState(
        run_id="blueprint-counts", artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: ref}
    )
    published_ref = _ensure_stress_test_report(
        ctx, state, evaluation_vector=PolicyEvaluationVector(candidate_id="c")
    )
    restored = StressTestReport.model_validate(
        from_canonical_bytes(FileSystemCAS(tmp_path / "cas").get_bytes(published_ref.artifact_id))
    )
    assert restored.robustness_score == (None if legacy else 31 / 32)
    assert restored.set_adequacy_status == ("partial" if legacy else "complete")
    assert store.get_bytes(ref.artifact_id) == original


@pytest.mark.parametrize("schema", ["2.0", "1.1-dev", "1.0"])
def test_typed_basis_requires_exact_supported_schema(schema: str) -> None:
    payload = _run([1.0, 3.0]).model_dump(mode="json")
    payload["schema_version"] = schema
    with pytest.raises(ValidationError):
        StressTestReport.model_validate(payload)


def test_new_schema_cannot_claim_score_without_typed_basis() -> None:
    with pytest.raises(ValidationError):
        StressTestReport(schema_version="1.1", report_id="unbound", robustness_score=1.0)


def test_anonymous_report_retry_is_counted_once_at_actual_cas_path(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="retry-counts")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("retry-counts"))
    base = _run([1.0, 3.0])
    child = _run([1.0, 1.0])
    ref = store.put_json(
        base.model_dump(mode="json"),
        PutOptions(kind="scientist.stress_test_report", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = ExperimentState(
        run_id="retry-counts", artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: ref}
    )
    first = _ensure_stress_test_report(
        ctx,
        state,
        evaluation_vector=PolicyEvaluationVector(candidate_id="c"),
        supplemental_reports=[child],
    )
    retried_state = state.model_copy(
        update={"artifacts_index": {ARTIFACT_STRESS_TEST_REPORT_REF: first}}
    )
    second = _ensure_stress_test_report(
        ctx,
        retried_state,
        evaluation_vector=PolicyEvaluationVector(candidate_id="c"),
        supplemental_reports=[child],
    )

    def read(reference):
        return StressTestReport.model_validate(
            from_canonical_bytes(store.get_bytes(reference.artifact_id))
        )

    assert read(first).scenario_evidence.attempted == 4
    assert read(second).scenario_evidence.attempted == 4
    assert read(second).robustness_score == 3 / 4
    assert second.artifact_id == first.artifact_id
    # Same report label with changed real content must refuse, rather than merge twice.
    changed = child.model_copy(deep=True)
    changed.metadata["changed_payload"] = True
    with pytest.raises(ValueError, match="content"):
        _ensure_stress_test_report(
            ctx,
            retried_state,
            evaluation_vector=PolicyEvaluationVector(candidate_id="c"),
            supplemental_reports=[changed],
        )


def test_same_anonymous_report_as_base_is_not_an_extra_attempt() -> None:
    base = _run([1.0, 3.0])
    merged = _recompute_stress_test_report(_merge_stress_test_reports(base, [base]))
    assert merged.scenario_evidence.attempted == 2
    assert merged.robustness_score == 1 / 2


def test_budget_port_uses_ordinary_typed_context_not_json_state(tmp_path: Path) -> None:
    from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
    from polisyos.scientist.orchestration.engine import BudgetMiddleware, BudgetState

    context_type = getattr(runtime, "PolicyBudgetExecutionContext", None)
    assert context_type is not None, "ordinary blueprint context port is missing"
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="typed-budget")
    owner = BudgetMiddleware(BudgetState())
    arguments = {"store": store, "run": run, "logger": logging.getLogger("typed-budget")}
    context = context_type(**arguments, budget_middleware=owner)
    assert context.budget_middleware is owner
    assert isinstance(context, ExecutionContext)
    assert context_type(**arguments).budget_middleware is None
    with pytest.raises(TypeError):
        context_type(**arguments, budget_middleware=object())
    with pytest.raises(ValidationError):
        ExperimentState(run_id="typed-budget", params={"_resource_budget_middleware": owner})
