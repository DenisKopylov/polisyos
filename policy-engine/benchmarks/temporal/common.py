"""Shared helpers for temporal benchmark entrypoints."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from benchmarks.harness import BenchmarkCase, BenchmarkCircuit, BenchmarkReport, CaseResult
from polisyos.scientist.methods.backtesting.temporal import (
    TemporalEvaluationResult,
    build_temporal_backtest_report,
    summarize_temporal_evaluations,
)

TEMPORAL_BENCHMARK_FAMILY = "temporal_causal_dynamics"
TEMPORAL_LITERATURE_ANCHOR = [
    "Brodersen et al. (2015). Inferring causal impact using Bayesian structural time-series models.",
    "Hernan and Robins (2020). Causal Inference: What If.",
]


@dataclass(frozen=True)
class TemporalBenchmarkFixture:
    case_id: str
    scenario_label: str
    runner: Callable[[], TemporalEvaluationResult]
    tags: tuple[str, ...] = ()
    timeout_s: float = 20.0


def benchmark_case_from_fixture(
    fixture: TemporalBenchmarkFixture,
    *,
    circuit: BenchmarkCircuit = BenchmarkCircuit.ESTIMATION,
) -> BenchmarkCase:
    return BenchmarkCase(
        name=fixture.case_id,
        circuit=circuit,
        runner=fixture.runner,
        checker=_check_temporal_result,
        tags=fixture.tags,
        timeout_s=fixture.timeout_s,
    )


def _check_temporal_result(result: TemporalEvaluationResult) -> bool:
    if not result.matches_expected_outcome:
        raise AssertionError(
            f"expected temporal outcome {result.expected_outcome!r}, got {result.actual_outcome!r}"
        )
    return True


def build_gold_scorecard(evaluations: Sequence[TemporalEvaluationResult]) -> dict[str, Any]:
    summary = summarize_temporal_evaluations(evaluations)
    engine_route_coverage_rate = _acceptance_rate(evaluations, "engine_route_used")
    bundle_presence_rate = _acceptance_rate(evaluations, "bundle_present")
    artifact_loadability_rate = _acceptance_rate(evaluations, "artifact_loadability")
    diagnostics_artifact_presence_rate = _acceptance_rate(
        evaluations,
        "diagnostics_artifact_present",
    )
    policy_cases = [
        item for item in evaluations if bool(item.metadata.get("requires_policy_lineage"))
    ]
    policy_lineage_rate = _acceptance_rate(
        policy_cases or evaluations,
        "policy_lineage_complete",
        default=1.0,
    )
    fallback_cases = [
        item for item in evaluations if bool(item.gating_checks.get("fallback_required"))
    ]
    truthful_fallback_disclosure_rate = _acceptance_rate(
        fallback_cases or evaluations,
        "truthful_fallback_disclosure",
        default=1.0,
    )
    return {
        **summary,
        "engine_route_coverage_rate": engine_route_coverage_rate,
        "bundle_presence_rate": bundle_presence_rate,
        "artifact_loadability_rate": artifact_loadability_rate,
        "policy_lineage_rate": policy_lineage_rate,
        "diagnostics_artifact_presence_rate": diagnostics_artifact_presence_rate,
        "truthful_fallback_disclosure_rate": truthful_fallback_disclosure_rate,
        "checks": {
            "n_total_nonzero": summary["n_total"] > 0,
            "all_cases_green": summary["n_total"] == summary["n_passed"],
            "engine_route_coverage_rate": engine_route_coverage_rate == 1.0,
            "bundle_presence_rate": bundle_presence_rate == 1.0,
            "artifact_loadability_rate": artifact_loadability_rate == 1.0,
            "policy_lineage_rate": policy_lineage_rate == 1.0,
            "diagnostics_artifact_presence_rate": diagnostics_artifact_presence_rate == 1.0,
            "truthful_fallback_disclosure_rate": truthful_fallback_disclosure_rate == 1.0,
            "diagnostics_presence_rate": summary["diagnostics_presence_rate"] == 1.0,
            "fallback_success_rate": summary["fallback_success_rate"] == 1.0,
        },
        "passes_all": (
            summary["n_total"] > 0
            and summary["n_total"] == summary["n_passed"]
            and engine_route_coverage_rate == 1.0
            and bundle_presence_rate == 1.0
            and artifact_loadability_rate == 1.0
            and policy_lineage_rate == 1.0
            and diagnostics_artifact_presence_rate == 1.0
            and truthful_fallback_disclosure_rate == 1.0
            and summary["diagnostics_presence_rate"] == 1.0
            and summary["fallback_success_rate"] == 1.0
        ),
    }


def build_hidden_summary(evaluations: Sequence[TemporalEvaluationResult]) -> dict[str, Any]:
    summary = summarize_temporal_evaluations(evaluations)
    artifact_loadability_rate = _acceptance_rate(
        evaluations,
        "artifact_loadability",
        default=1.0,
    )
    return {
        **summary,
        "artifact_reload_failure_rate": 1.0 - artifact_loadability_rate,
        "passes_all": (
            summary["n_total"] > 0
            and summary["n_total"] == summary["n_passed"]
            and summary["safe_rejection_rate"] == 1.0
            and summary["diagnostics_presence_rate"] == 1.0
            and summary["fallback_success_rate"] == 1.0
            and artifact_loadability_rate == 1.0
        ),
    }


def _acceptance_rate(
    evaluations: Sequence[TemporalEvaluationResult],
    key: str,
    *,
    default: float = 0.0,
) -> float:
    keyed = [item for item in evaluations if key in item.acceptance_checks]
    if not keyed:
        return float(default)
    values = [1.0 if bool(item.acceptance_checks.get(key)) else 0.0 for item in keyed]
    return float(sum(values) / len(values))


def build_temporal_suite_backtest(
    *,
    report_id: str,
    evaluations: Sequence[TemporalEvaluationResult],
    suite_id: str,
) -> dict[str, Any]:
    report = build_temporal_backtest_report(
        report_id=report_id,
        evaluations=evaluations,
        metadata={"suite_id": suite_id},
    )
    return _json_safe(report.model_dump(mode="python"))


def extract_temporal_evaluations(report: BenchmarkReport) -> list[TemporalEvaluationResult]:
    evaluations: list[TemporalEvaluationResult] = []
    for case in report.cases:
        if isinstance(case.result_payload, TemporalEvaluationResult):
            evaluations.append(case.result_payload)
    return evaluations


def temporal_case_details(
    case: CaseResult,
    *,
    include_scenario_metadata: bool,
) -> dict[str, Any]:
    result = case.result_payload
    if not isinstance(result, TemporalEvaluationResult):
        return {}
    payload = {
        "acceptance": {
            "passed": result.matches_expected_outcome,
            "expected_outcome": result.expected_outcome,
            "actual_outcome": result.actual_outcome,
            "checks": result.acceptance_checks,
        },
        "metrics": {
            **result.pointwise_metrics,
            **result.functional_metrics,
            **result.uncertainty_metrics,
        },
        "diagnostics_checks": result.diagnostics_checks,
        "gating_checks": result.gating_checks,
        "thresholds": result.thresholds,
        "reason_code": result.reason_code,
    }
    if include_scenario_metadata:
        payload["scenario_metadata"] = result.scenario.metadata
    return payload


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    return value


__all__ = [
    "TEMPORAL_BENCHMARK_FAMILY",
    "TEMPORAL_LITERATURE_ANCHOR",
    "TemporalBenchmarkFixture",
    "benchmark_case_from_fixture",
    "build_gold_scorecard",
    "build_hidden_summary",
    "build_temporal_suite_backtest",
    "extract_temporal_evaluations",
    "temporal_case_details",
]
