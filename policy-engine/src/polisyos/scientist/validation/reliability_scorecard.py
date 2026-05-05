"""Scientist reliability scorecard helpers."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

REQUIRED_SCENARIOS = (
    "happy_path",
    "tool_failure_with_retry",
    "checkpoint_resume",
    "governance_rejection",
    "fairness_calibration_regression",
)
REQUIRED_BENCHMARKS = (
    "node_latency",
    "checkpoint_io",
    "state_serialization",
    "state_copy",
    "fan_out_merge",
    "failure_index_search",
    "search_pareto",
)
REQUIRED_OPERATIONAL_SIGNALS = (
    "metrics_exporter",
    "trace_correlation",
    "dlq_replay",
    "bounded_retention",
    "monitoring_alerts",
)

SCENARIO_EVIDENCE_CASES: dict[str, tuple[str, ...]] = {
    "happy_path": ("test_linear_scientist_workflow_happy_path",),
    "tool_failure_with_retry": (
        "test_linear_scientist_workflow_tool_failure_retries_and_succeeds",
    ),
    "checkpoint_resume": (
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes",
    ),
    "governance_rejection": (
        "test_linear_scientist_workflow_governance_rejection_stops_decision_publication",
    ),
    "fairness_calibration_regression": (
        "test_linear_scientist_workflow_post_deploy_regression_triggers_alerts_and_reissue",
    ),
}

BENCHMARK_EVIDENCE_CASES: dict[str, tuple[str, ...]] = {
    "node_latency": ("test_scientist_node_chain_latency",),
    "checkpoint_io": (
        "test_scientist_checkpoint_io_hot_path",
        "test_scientist_async_checkpoint_io_hot_path",
    ),
    "state_serialization": ("test_scientist_state_serialization_hot_path",),
    "state_copy": ("test_scientist_state_branch_hot_path",),
    "fan_out_merge": ("test_scientist_fan_out_merge_hot_path",),
    "failure_index_search": ("test_scientist_failure_index_search_hot_path",),
    "search_pareto": ("test_scientist_search_pareto_hot_path",),
}

OPERATIONAL_EVIDENCE_CASES: dict[str, tuple[str, ...]] = {
    "metrics_exporter": ("test_metrics_exporter_operational_signal",),
    "trace_correlation": ("test_trace_correlation_operational_signal",),
    "dlq_replay": ("test_dlq_replay_operational_signal",),
    "bounded_retention": ("test_bounded_retention_operational_signal",),
    "monitoring_alerts": ("test_monitoring_alerts_operational_signal",),
}


@dataclass(frozen=True)
class ScientistReliabilityScorecard:
    scenario_pass_rate: float
    benchmark_coverage_rate: float
    operational_readiness_rate: float
    weighted_score: float
    scenario_results: dict[str, bool]
    benchmark_results: dict[str, bool]
    operational_results: dict[str, bool]
    passes_all: bool
    notes: list[str]
    scenario_evidence: dict[str, tuple[str, ...]] = field(default_factory=dict)
    benchmark_evidence: dict[str, tuple[str, ...]] = field(default_factory=dict)
    operational_evidence: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_pass_rate": self.scenario_pass_rate,
            "benchmark_coverage_rate": self.benchmark_coverage_rate,
            "operational_readiness_rate": self.operational_readiness_rate,
            "weighted_score": self.weighted_score,
            "scenario_results": dict(self.scenario_results),
            "benchmark_results": dict(self.benchmark_results),
            "operational_results": dict(self.operational_results),
            "passes_all": self.passes_all,
            "notes": list(self.notes),
            "scenario_evidence": {
                name: list(values) for name, values in self.scenario_evidence.items()
            },
            "benchmark_evidence": {
                name: list(values) for name, values in self.benchmark_evidence.items()
            },
            "operational_evidence": {
                name: list(values) for name, values in self.operational_evidence.items()
            },
        }


def build_scientist_reliability_scorecard(
    *,
    scenario_results: Mapping[str, bool],
    benchmark_results: Mapping[str, bool],
    operational_results: Mapping[str, bool],
    scenario_evidence: Mapping[str, Sequence[str]] | None = None,
    benchmark_evidence: Mapping[str, Sequence[str]] | None = None,
    operational_evidence: Mapping[str, Sequence[str]] | None = None,
) -> ScientistReliabilityScorecard:
    normalized_scenarios = _normalize_results(REQUIRED_SCENARIOS, scenario_results)
    normalized_benchmarks = _normalize_results(REQUIRED_BENCHMARKS, benchmark_results)
    normalized_operational = _normalize_results(
        REQUIRED_OPERATIONAL_SIGNALS,
        operational_results,
    )
    normalized_scenario_evidence = _normalize_evidence(
        REQUIRED_SCENARIOS,
        scenario_evidence,
    )
    normalized_benchmark_evidence = _normalize_evidence(
        REQUIRED_BENCHMARKS,
        benchmark_evidence,
    )
    normalized_operational_evidence = _normalize_evidence(
        REQUIRED_OPERATIONAL_SIGNALS,
        operational_evidence,
    )

    scenario_pass_rate = _pass_rate(normalized_scenarios)
    benchmark_coverage_rate = _pass_rate(normalized_benchmarks)
    operational_readiness_rate = _pass_rate(normalized_operational)
    weighted_score = round(
        scenario_pass_rate * 0.5 + benchmark_coverage_rate * 0.3 + operational_readiness_rate * 0.2,
        4,
    )

    notes = [
        *[
            f"scenario_missing:{name}"
            for name, passed in normalized_scenarios.items()
            if not passed
        ],
        *[
            f"benchmark_missing:{name}"
            for name, passed in normalized_benchmarks.items()
            if not passed
        ],
        *[
            f"operational_gap:{name}"
            for name, passed in normalized_operational.items()
            if not passed
        ],
    ]
    return ScientistReliabilityScorecard(
        scenario_pass_rate=scenario_pass_rate,
        benchmark_coverage_rate=benchmark_coverage_rate,
        operational_readiness_rate=operational_readiness_rate,
        weighted_score=weighted_score,
        scenario_results=normalized_scenarios,
        benchmark_results=normalized_benchmarks,
        operational_results=normalized_operational,
        passes_all=not notes,
        notes=notes,
        scenario_evidence=normalized_scenario_evidence,
        benchmark_evidence=normalized_benchmark_evidence,
        operational_evidence=normalized_operational_evidence,
    )


def build_scientist_reliability_scorecard_from_evidence(
    *,
    passed_test_cases: Collection[str],
    benchmark_names: Collection[str],
) -> ScientistReliabilityScorecard:
    observed_tests = {
        str(item).strip() for item in passed_test_cases if isinstance(item, str) and item.strip()
    }
    observed_benchmarks = {
        str(item).strip() for item in benchmark_names if isinstance(item, str) and item.strip()
    }
    scenario_results = _presence_results(SCENARIO_EVIDENCE_CASES, observed_tests)
    benchmark_results = _presence_results(
        BENCHMARK_EVIDENCE_CASES,
        observed_benchmarks,
    )
    operational_results = _presence_results(
        OPERATIONAL_EVIDENCE_CASES,
        observed_tests,
    )
    return build_scientist_reliability_scorecard(
        scenario_results=scenario_results,
        benchmark_results=benchmark_results,
        operational_results=operational_results,
        scenario_evidence=SCENARIO_EVIDENCE_CASES,
        benchmark_evidence=BENCHMARK_EVIDENCE_CASES,
        operational_evidence=OPERATIONAL_EVIDENCE_CASES,
    )


def _normalize_results(required: tuple[str, ...], raw: Mapping[str, bool]) -> dict[str, bool]:
    return {name: bool(raw.get(name, False)) for name in required}


def _normalize_evidence(
    required: tuple[str, ...],
    raw: Mapping[str, Sequence[str]] | None,
) -> dict[str, tuple[str, ...]]:
    if raw is None:
        return dict.fromkeys(required, ())
    normalized: dict[str, tuple[str, ...]] = {}
    for name in required:
        values = raw.get(name, ())
        normalized[name] = tuple(
            str(item) for item in values if isinstance(item, str) and item.strip()
        )
    return normalized


def _presence_results(
    required: Mapping[str, tuple[str, ...]],
    observed: Collection[str],
) -> dict[str, bool]:
    return {name: any(case in observed for case in cases) for name, cases in required.items()}


def _pass_rate(results: Mapping[str, bool]) -> float:
    if not results:
        return 0.0
    passed = sum(1 for value in results.values() if value)
    return round(passed / len(results), 4)


__all__ = [
    "BENCHMARK_EVIDENCE_CASES",
    "OPERATIONAL_EVIDENCE_CASES",
    "REQUIRED_BENCHMARKS",
    "REQUIRED_OPERATIONAL_SIGNALS",
    "REQUIRED_SCENARIOS",
    "SCENARIO_EVIDENCE_CASES",
    "ScientistReliabilityScorecard",
    "build_scientist_reliability_scorecard",
    "build_scientist_reliability_scorecard_from_evidence",
]
