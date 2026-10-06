"""Adversarial scenario generation for robustness backtesting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.abm_bridge import ABMAlignmentReport, load_abm_alignment_report
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    load_abstraction_certificate,
)
from polisyos.ir.analytics.strategic import (
    load_equilibrium_selection_summary,
    load_equilibrium_set_summary,
    load_performative_shift_summary,
    load_post_adaptation_policy_value_summary,
    load_strategic_closure_summary,
    load_strategic_response_bundle,
)
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.doe.stress_report import (
    StressScenarioEvidence,
    StressTestReport,
    Vulnerability,
    VulnerabilityType,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
)

PHASE_D4_ROTATION_GROUP = "phase_d4_v1"
STRATEGIC_GAMING_SUITE_ID = "strategic_gaming_v1"
MULTIPLICITY_DISCLOSURE_SUITE_ID = "multiplicity_disclosure_v1"
ABSTRACTION_LEAKAGE_SUITE_ID = "abstraction_leakage_v1"
_PHASE_D4_METRIC_NAMES = (
    "challenge_pass_rate",
    "undisclosed_multiplicity_rate",
    "silent_static_fallback_rate",
    "abstraction_leakage_rate",
)


@dataclass(frozen=True)
class AdversarialScenario:
    """A synthetically perturbed scenario for robustness testing."""

    scenario_id: str
    perturbation_type: str
    perturbation_magnitude: float
    original_metrics: dict[str, list[float]]
    perturbed_metrics: dict[str, list[float]]


@dataclass(frozen=True)
class ChallengeCase:
    """Typed challenge-case contract for Phase D.4 challenge suites."""

    case_id: str
    challenge_family: str
    expected_outcome: str
    severity: str = "high"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChallengeCaseResult:
    """Evaluation outcome for one challenge case."""

    case: ChallengeCase
    status: str
    passed: bool
    summary: str
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChallengeSuiteResult:
    """Canonical D.4 suite output backed by benchmark/stress artifacts."""

    suite_id: str
    suite_version: str
    runtime_split_type: BenchmarkSplit
    benchmark_evaluation: BenchmarkEvaluation
    stress_test_report: StressTestReport | None = None
    warnings: tuple[str, ...] = ()


class AdversarialGenerator:
    """Generate adversarial perturbations of backtest scenarios.

    Creates worst-case/stress scenarios by applying systematic
    perturbations to input data to test model robustness.
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)

    def generate_shift(
        self,
        data: dict[str, list[float]],
        *,
        scenario_id: str = "shift",
        shift_fraction: float = 0.1,
    ) -> AdversarialScenario:
        """Apply a systematic level shift to all metrics."""
        perturbed: dict[str, list[float]] = {}
        for metric, values in data.items():
            arr = np.asarray(values, dtype=float)
            magnitude = float(np.std(arr)) * shift_fraction if arr.size > 1 else shift_fraction
            perturbed[metric] = (arr + magnitude).tolist()

        return AdversarialScenario(
            scenario_id=f"adv_{scenario_id}_shift",
            perturbation_type="level_shift",
            perturbation_magnitude=shift_fraction,
            original_metrics=data,
            perturbed_metrics=perturbed,
        )

    def generate_noise(
        self,
        data: dict[str, list[float]],
        *,
        scenario_id: str = "noise",
        noise_scale: float = 0.1,
    ) -> AdversarialScenario:
        """Add Gaussian noise to all metrics."""
        perturbed: dict[str, list[float]] = {}
        for metric, values in data.items():
            arr = np.asarray(values, dtype=float)
            std = float(np.std(arr)) if arr.size > 1 else 1.0
            noise = self._rng.normal(0, std * noise_scale, size=arr.size)
            perturbed[metric] = (arr + noise).tolist()

        return AdversarialScenario(
            scenario_id=f"adv_{scenario_id}_noise",
            perturbation_type="gaussian_noise",
            perturbation_magnitude=noise_scale,
            original_metrics=data,
            perturbed_metrics=perturbed,
        )

    def generate_outliers(
        self,
        data: dict[str, list[float]],
        *,
        scenario_id: str = "outlier",
        outlier_fraction: float = 0.1,
        outlier_magnitude: float = 5.0,
    ) -> AdversarialScenario:
        """Inject outliers into a fraction of data points."""
        perturbed: dict[str, list[float]] = {}
        for metric, values in data.items():
            arr = np.asarray(values, dtype=float).copy()
            n_outliers = max(1, int(len(arr) * outlier_fraction))
            indices = self._rng.choice(len(arr), size=n_outliers, replace=False)
            std = float(np.std(arr)) if arr.size > 1 else 1.0
            for idx in indices:
                arr[idx] += self._rng.choice([-1, 1]) * outlier_magnitude * std
            perturbed[metric] = arr.tolist()

        return AdversarialScenario(
            scenario_id=f"adv_{scenario_id}_outlier",
            perturbation_type="outlier_injection",
            perturbation_magnitude=outlier_magnitude,
            original_metrics=data,
            perturbed_metrics=perturbed,
        )

    def generate_missing(
        self,
        data: dict[str, list[float]],
        *,
        scenario_id: str = "missing",
        missing_fraction: float = 0.1,
    ) -> AdversarialScenario:
        """Replace a fraction of values with NaN."""
        perturbed: dict[str, list[float]] = {}
        for metric, values in data.items():
            arr = np.asarray(values, dtype=float).copy()
            n_missing = max(1, int(len(arr) * missing_fraction))
            indices = self._rng.choice(len(arr), size=n_missing, replace=False)
            arr[indices] = np.nan
            perturbed[metric] = arr.tolist()

        return AdversarialScenario(
            scenario_id=f"adv_{scenario_id}_missing",
            perturbation_type="missing_data",
            perturbation_magnitude=missing_fraction,
            original_metrics=data,
            perturbed_metrics=perturbed,
        )


def build_challenge_case_result(
    *,
    case: ChallengeCase,
    passed: bool,
    summary: str,
    status: str | None = None,
    metrics: Mapping[str, float] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ChallengeCaseResult:
    """Build challenge case result."""
    if type(passed) is not bool:
        raise TypeError("passed must be a strict bool before challenge outcome admission")
    resolved_status = str(status or ("passed" if passed else "failed")).strip() or "failed"
    return ChallengeCaseResult(
        case=case,
        status=resolved_status,
        passed=passed,
        summary=str(summary).strip(),
        metrics={str(key): float(value) for key, value in (metrics or {}).items()},
        metadata=dict(metadata or {}),
    )


def build_challenge_suite_result(
    *,
    suite_id: str,
    suite_version: str,
    candidate_ref: ArtifactRef,
    loop_id: str,
    challenge_family: str,
    case_results: Sequence[ChallengeCaseResult],
    primary_failure_rate_name: str,
    vulnerability_type: VulnerabilityType,
    metadata: Mapping[str, Any] | None = None,
    warnings: Sequence[str] | None = None,
) -> ChallengeSuiteResult:
    """Project declared named case outcomes without inventing their scientific rule."""
    identities = [result.case.case_id for result in case_results]
    if any(type(identity) is not str or not identity.strip() for identity in identities) or len(
        set(identities)
    ) != len(identities):
        raise ValueError("challenge case identity must be nonempty and unique")
    skipped = [
        result
        for result in case_results
        if type(result.status) is str and result.status == "skipped"
    ]
    attempted = [
        result
        for result in case_results
        if not (type(result.status) is str and result.status == "skipped")
    ]
    finite = [
        result
        for result in attempted
        if type(result.passed) is bool
        and type(result.status) is str
        and type(result.case.expected_outcome) is str
        and bool(result.case.expected_outcome.strip())
        and result.status in {"passed", "failed"}
        and result.passed == (result.status == "passed")
    ]
    finite_ids = {result.case.case_id for result in finite}
    unknown = [result for result in attempted if result.case.case_id not in finite_ids]
    failed = [result for result in finite if not result.passed]
    vulnerabilities = [
        Vulnerability(
            vulnerability_id=f"{suite_id}:{result.case.case_id}",
            vulnerability_type=vulnerability_type,
            severity=result.case.severity,
            description=result.summary,
        )
        for result in failed
    ]
    evidence = StressScenarioEvidence(
        attempted=len(attempted),
        finite_evaluated=len(finite),
        violated_scenarios=len(failed),
        unknown_or_nonfinite=len(unknown),
        planned_scenarios=len(case_results),
        assessment_rule="challenge_case_pass",
        critical_occurrences=sum(item.severity == "critical" for item in vulnerabilities),
        high_occurrences=sum(item.severity == "high" for item in vulnerabilities),
        medium_occurrences=sum(item.severity == "medium" for item in vulnerabilities),
    )
    pass_rate = evidence.observed_fraction
    metrics = dict.fromkeys(_PHASE_D4_METRIC_NAMES, 0.0)
    if pass_rate is None:
        metrics.pop("challenge_pass_rate", None)
        metrics.pop(primary_failure_rate_name, None)
    else:
        metrics["challenge_pass_rate"] = pass_rate
        metrics[primary_failure_rate_name] = len(failed) / len(finite)
    disclosure_failures = [
        result.case.case_id
        for result in failed
        if bool(result.metadata.get("is_disclosure_failure"))
    ]
    aggregate_metadata = {
        **dict(metadata or {}),
        "challenge_suite_id": suite_id,
        "challenge_family": challenge_family,
        "challenge_case_ids": identities,
        "disclosure_failures": disclosure_failures,
        "suite_pass_rate": pass_rate,
        "assessment_profile": "challenge_case_pass@1.0",
        "assessment_unit": "declared_named_case_outcome_bool",
        "case_rule_basis": "consumer_asserted",
        "case_rule_scope": "Existing case producer declares expected_outcome/status/passed; this adapter does not recompute or authenticate its scientific predicate.",
        "skipped_case_count": len(skipped),
        "skipped_case_ids": [result.case.case_id for result in skipped],
        "unknown_or_inconsistent_case_ids": [result.case.case_id for result in unknown],
        **evidence.accounting_metadata(),
    }
    promotable = (
        evidence.complete
        and pass_rate == 1.0
        and all(
            float(metrics[name]) == 0.0
            for name in _PHASE_D4_METRIC_NAMES
            if name != "challenge_pass_rate"
        )
    )
    benchmark_evaluation = BenchmarkEvaluation(
        loop_id=str(loop_id),
        suite_id=suite_id,
        suite_version=suite_version,
        candidate_ref=candidate_ref,
        selection_metrics=dict(metrics),
        holdout_metrics=dict(metrics),
        sample_counts={BenchmarkSplit.ROTATING_CHALLENGE.value: len(finite)},
        promotable=promotable,
        status="ok" if promotable else "failed" if failed else "partial",
        notes=[result.summary for result in case_results if result.status != "passed"],
        runtime_split_type=BenchmarkSplit.ROTATING_CHALLENGE,
        metadata=aggregate_metadata,
    )
    stress_test_report = StressTestReport(
        schema_version="1.1",
        report_id=f"stress_{suite_id}_{loop_id}",
        total_scenarios_evaluated=len(finite),
        vulnerabilities=vulnerabilities,
        critical_count=evidence.critical_occurrences,
        high_count=evidence.high_occurrences,
        medium_count=evidence.medium_occurrences,
        robustness_score=pass_rate,
        scenario_evidence=evidence,
        set_adequacy_status="complete" if evidence.complete else "partial",
        metadata={
            **aggregate_metadata,
            "challenge_family_counts": {challenge_family: len(finite)},
            "blocking_failure_count": len(failed),
            "derived_from_phase_d4": True,
        },
    )
    return ChallengeSuiteResult(
        suite_id=suite_id,
        suite_version=suite_version,
        runtime_split_type=BenchmarkSplit.ROTATING_CHALLENGE,
        benchmark_evaluation=benchmark_evaluation,
        stress_test_report=stress_test_report,
        warnings=tuple(str(item) for item in (warnings or ()))
        + (() if evidence.complete else ("challenge_outcomes_partial",)),
    )


def run_phase_d4_challenge_suites(
    *,
    store,
    run_id: str,
    loop_id: str,
    candidate_ref: ArtifactRef,
    params: Mapping[str, Any],
    artifacts_index: Mapping[str, ArtifactRef],
    selection_metadata: Mapping[str, Any] | None = None,
) -> tuple[list[ChallengeSuiteResult], tuple[str, ...]]:
    """Run D.4 strategic and abstraction suites when supporting evidence exists."""

    from polisyos.scientist.methods.backtesting.abstraction_suite import (
        run_abstraction_challenge_suite,
    )
    from polisyos.scientist.methods.backtesting.strategic_suite import (
        run_strategic_challenge_suites,
    )

    strategic_summary = _resolve_strategic_summary(
        store,
        params,
        artifacts_index,
        selection_metadata,
    )
    abstraction_certificate = _load_abstraction_certificate_if_present(store, artifacts_index)
    abstraction_map_ref = artifacts_index.get(ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF)
    abm_alignment_report = _load_abm_alignment_report_if_present(store, artifacts_index)

    suite_results: list[ChallengeSuiteResult] = []
    warnings: list[str] = []

    strategic_results, strategic_warnings = run_strategic_challenge_suites(
        candidate_ref=candidate_ref,
        loop_id=loop_id,
        params=params,
        run_id=run_id,
        strategic_summary=strategic_summary,
        abstraction_certificate=abstraction_certificate,
    )
    suite_results.extend(strategic_results)
    warnings.extend(
        str(item)
        for item in strategic_warnings
        if strategic_results or not str(item).endswith("_skipped_no_inputs")
    )

    abstraction_result, abstraction_warnings = run_abstraction_challenge_suite(
        candidate_ref=candidate_ref,
        loop_id=loop_id,
        run_id=run_id,
        params=params,
        strategic_summary=strategic_summary,
        abstraction_certificate=abstraction_certificate,
        abstraction_map_ref=abstraction_map_ref,
        abm_alignment_report=abm_alignment_report,
    )
    if abstraction_result is not None:
        suite_results.append(abstraction_result)
    warnings.extend(
        str(item)
        for item in abstraction_warnings
        if abstraction_result is not None or not str(item).endswith("_skipped_no_inputs")
    )

    if not suite_results:
        return [], ("phase_d4_skipped_no_strategic_or_abstraction_evidence",)
    return suite_results, tuple(dict.fromkeys(warnings))


def _resolve_strategic_summary(
    store,
    params: Mapping[str, Any],
    artifacts_index: Mapping[str, ArtifactRef],
    selection_metadata: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    bundle_ref = artifacts_index.get(ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF)
    if bundle_ref is not None:
        try:
            bundle = load_strategic_response_bundle(store, bundle_ref)
            summary: dict[str, Any] = {
                "fallback_mode": bundle.fallback_mode.value,
                "equilibrium_selection_dependence": bundle.equilibrium_selection_dependence,
                "multiplicity_note": bundle.multiplicity_note,
                "blocked_reason": bundle.blocked_reason,
                "strategic_response_bundle_ref": bundle_ref.model_dump(mode="json"),
                "closure_summary": load_strategic_closure_summary(
                    store,
                    bundle.strategic_closure_ref,
                ).model_dump(mode="json"),
            }
            equilibrium_set = load_equilibrium_set_summary(store, bundle.equilibrium_set_ref)
            if equilibrium_set.equilibrium_profiles:
                summary["equilibrium_profiles"] = [
                    dict(profile) for profile in equilibrium_set.equilibrium_profiles
                ]
            if bundle.selected_equilibrium_ref is not None:
                selected = load_equilibrium_selection_summary(
                    store, bundle.selected_equilibrium_ref
                )
                summary["selected_equilibrium"] = dict(selected.selected_equilibrium)
            if bundle.performative_shift_ref is not None:
                performative_shift = load_performative_shift_summary(
                    store, bundle.performative_shift_ref
                )
                if performative_shift.performative_shift is not None:
                    summary["performative_shift"] = float(performative_shift.performative_shift)
            post_value = load_post_adaptation_policy_value_summary(
                store,
                bundle.post_adaptation_policy_value_ref,
            )
            if post_value.point_value is not None:
                summary["post_adaptation_policy_value"] = float(post_value.point_value)
            if post_value.lower_bound is not None and post_value.upper_bound is not None:
                summary["bounds"] = [
                    float(post_value.lower_bound),
                    float(post_value.upper_bound),
                ]
            return summary
        except Exception:
            pass
    for payload in (
        None if selection_metadata is None else selection_metadata.get("strategic_response"),
        params.get("strategic_response"),
        params.get("strategic_response_summary"),
    ):
        if isinstance(payload, Mapping):
            return dict(payload)
    return None


def _load_abstraction_certificate_if_present(
    store,
    artifacts_index: Mapping[str, ArtifactRef],
) -> AbstractionCertificate | None:
    ref = artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF)
    if ref is None:
        return None
    try:
        return load_abstraction_certificate(store, ref)
    except Exception:
        return None


def _load_abm_alignment_report_if_present(
    store,
    artifacts_index: Mapping[str, ArtifactRef],
) -> ABMAlignmentReport | None:
    ref = artifacts_index.get(ARTIFACT_ABM_ALIGNMENT_REPORT_REF)
    if ref is None:
        return None
    try:
        return load_abm_alignment_report(store, ref)
    except Exception:
        return None


__all__ = [
    "ABSTRACTION_LEAKAGE_SUITE_ID",
    "MULTIPLICITY_DISCLOSURE_SUITE_ID",
    "PHASE_D4_ROTATION_GROUP",
    "STRATEGIC_GAMING_SUITE_ID",
    "AdversarialGenerator",
    "AdversarialScenario",
    "ChallengeCase",
    "ChallengeCaseResult",
    "ChallengeSuiteResult",
    "build_challenge_case_result",
    "build_challenge_suite_result",
    "run_phase_d4_challenge_suites",
]
