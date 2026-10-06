"""Real named challenge outcomes retain their scenario unit through blueprint CAS."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.methods.backtesting.adversarial import (
    STRATEGIC_GAMING_SUITE_ID,
    ChallengeCase,
    ChallengeCaseResult,
    build_challenge_case_result,
    build_challenge_suite_result,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport, VulnerabilityType
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _ensure_stress_test_report,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_STRESS_TEST_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


def _case(index: int, passed: bool, *, status: str | None = None, expected: str = "declared_check"):
    return build_challenge_case_result(
        case=ChallengeCase(
            case_id=f"case-{index}", challenge_family="strategic", expected_outcome=expected
        ),
        passed=passed,
        status=status,
        summary="same observed issue" if not passed else "declared check passed",
    )


def _suite(store: FileSystemCAS, cases: list[ChallengeCaseResult]):
    candidate = store.put_json(
        {"candidate": "actual-fixture"},
        PutOptions(kind="scientist.policy_candidate", media_type="application/json"),
    )
    return build_challenge_suite_result(
        suite_id=STRATEGIC_GAMING_SUITE_ID,
        suite_version="1.0",
        candidate_ref=candidate,
        loop_id="loop",
        challenge_family="strategic",
        case_results=cases,
        primary_failure_rate_name="silent_static_fallback_rate",
        vulnerability_type=VulnerabilityType.OBJECTIVE_COLLAPSE,
    )


@pytest.mark.parametrize("presentation_cap", [1, 20])
def test_real_32_case_producer_and_blueprint_fresh_reader_keep_fraction(
    tmp_path: Path, presentation_cap: int
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    cases = [_case(i, i < 31) for i in range(32)]
    suite = _suite(store, cases)
    report = suite.stress_test_report
    assert report is not None and report.scenario_evidence is not None
    assert report.scenario_evidence.assessment_rule == "challenge_case_pass"
    assert (
        report.scenario_evidence.attempted,
        report.scenario_evidence.finite_evaluated,
        report.scenario_evidence.violated_scenarios,
    ) == (32, 32, 1)
    assert report.robustness_score == 31 / 32
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="challenge-counts")
    context = ExecutionContext(store=store, run=run, logger=logging.getLogger("challenge-counts"))
    presentation = report.model_copy(
        update={"vulnerabilities": report.vulnerabilities[:presentation_cap]}
    )
    reference = store.put_json(
        presentation,
        PutOptions(kind="scientist.stress_test_report", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = ExperimentState(
        run_id="challenge-counts", artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: reference}
    )
    first = _ensure_stress_test_report(
        context, state, evaluation_vector=PolicyEvaluationVector(candidate_id="c")
    )
    restored = StressTestReport.model_validate(
        from_canonical_bytes(FileSystemCAS(tmp_path / "cas").get_bytes(first.artifact_id))
    )
    assert restored.robustness_score == 31 / 32
    assert restored.scenario_evidence == report.scenario_evidence
    assert restored.metadata["population_probability"] == "not_established"
    # A named suite replacement is the same declared case set, not 32 extra attempts.
    retry_state = state.model_copy(
        update={"artifacts_index": {ARTIFACT_STRESS_TEST_REPORT_REF: first}}
    )
    repeated = _ensure_stress_test_report(
        context,
        retry_state,
        evaluation_vector=PolicyEvaluationVector(candidate_id="c"),
        supplemental_reports=[report],
    )
    retried = StressTestReport.model_validate(
        from_canonical_bytes(store.get_bytes(repeated.artifact_id))
    )
    assert retried.scenario_evidence.attempted == 32
    assert retried.robustness_score == 31 / 32


@pytest.mark.parametrize(
    "cases,attempted,unknown,skipped",
    [
        ([], 0, 0, 0),
        ([_case(0, False, status="skipped")], 0, 0, 1),
        ([_case(0, False, status="error")], 1, 1, 0),
        ([_case(0, False, status="passed")], 1, 1, 0),
        ([_case(0, True, expected="")], 1, 1, 0),
    ],
)
def test_empty_unknown_skipped_or_inconsistent_case_basis_is_unavailable(
    tmp_path: Path, cases: list[ChallengeCaseResult], attempted: int, unknown: int, skipped: int
) -> None:
    result = _suite(FileSystemCAS(tmp_path / "cas"), cases)
    report = result.stress_test_report
    assert report is not None
    assert report.robustness_score is None and report.is_robust is False
    assert report.scenario_evidence.attempted == attempted
    assert report.scenario_evidence.unknown_or_nonfinite == unknown
    assert report.metadata["skipped_case_count"] == skipped
    assert report.set_adequacy_status == "partial"
    assert result.benchmark_evaluation.promotable is False
    assert "challenge_pass_rate" not in result.benchmark_evaluation.selection_metrics


def test_partial_named_cases_retain_only_observed_conditional_fraction(tmp_path: Path) -> None:
    result = _suite(
        FileSystemCAS(tmp_path / "cas"), [_case(0, True), _case(1, False, status="error")]
    )
    report = result.stress_test_report
    assert report is not None and report.scenario_evidence is not None
    assert (
        report.scenario_evidence.attempted,
        report.scenario_evidence.finite_evaluated,
        report.scenario_evidence.unknown_or_nonfinite,
    ) == (2, 1, 1)
    assert report.robustness_score == 1.0 and report.is_robust is False
    assert result.benchmark_evaluation.promotable is False
    assert report.metadata["score_status"] == "conditional"


def test_duplicate_case_ids_refuse_and_nonboolean_outcome_is_unknown(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match="case.*identity"):
        _suite(store, [_case(0, True), _case(0, False)])
    malformed = ChallengeCaseResult(
        case=ChallengeCase(
            case_id="raw", challenge_family="strategic", expected_outcome="declared_check"
        ),
        status="passed",
        passed=1,
        summary="malformed raw boolean",
    )
    result = _suite(store, [malformed])
    assert result.stress_test_report.robustness_score is None
    assert result.stress_test_report.scenario_evidence.unknown_or_nonfinite == 1
    assert result.benchmark_evaluation.promotable is False


@pytest.mark.parametrize("malformed", [1, "false", float("nan"), float("inf")])
def test_actual_case_intake_refuses_before_boolean_coercion(malformed: object) -> None:
    with pytest.raises(TypeError, match="passed.*bool"):
        build_challenge_case_result(
            case=ChallengeCase(
                case_id="raw", challenge_family="strategic", expected_outcome="declared_check"
            ),
            passed=malformed,
            summary="raw intake",
        )


@pytest.mark.parametrize("cap", [1, 10])
def test_ten_same_issue_case_occurrences_remain_ten_after_presentation(
    cap: int, tmp_path: Path
) -> None:
    from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
        _recompute_stress_test_report,
    )

    report = _suite(
        FileSystemCAS(tmp_path / "cas"), [_case(i, i < 22) for i in range(32)]
    ).stress_test_report
    assert report is not None and report.scenario_evidence is not None
    assert report.scenario_evidence.violated_scenarios == 10
    presentation = report.model_copy(update={"vulnerabilities": report.vulnerabilities[:cap]})
    observed = _recompute_stress_test_report(presentation)
    assert len(observed.vulnerabilities) == cap
    assert observed.robustness_score == 22 / 32
    assert observed.scenario_evidence.violated_scenarios == 10
