"""Shared scorecard helpers for research-grade benchmark reporting."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np

from benchmarks.harness import BenchmarkReport, CaseResult

MetricGetter = Callable[[Any], float]
CaseGroupGetter = Callable[[str], str]


def safe_effect_scale(value: float | int | None, *, floor: float = 0.25) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = float("nan")
    if not math.isfinite(numeric):
        return floor
    return max(abs(numeric), floor)


def summarize_method_metrics(
    report: BenchmarkReport,
    *,
    metric_getters: dict[str, MetricGetter],
    standardized_metrics: set[str] | None = None,
    scale_getter: MetricGetter | None = None,
    case_group_getter: CaseGroupGetter | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Aggregate raw and standardized metrics across report cases.

    Returns `(aggregate_metrics, standardized_metrics, case_groups)`.
    """
    standardized_metrics = standardized_metrics or set()
    raw_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    std_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    grouped_case_metrics: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )

    for case in report.cases:
        if not isinstance(case.result_payload, dict):
            continue
        case_group = case_group_getter(case.name) if case_group_getter else None
        for method_name, result in case.result_payload.items():
            scale = safe_effect_scale(scale_getter(result) if scale_getter else None)
            for metric_name, getter in metric_getters.items():
                value = _finite_float(getter(result))
                if value is None:
                    continue
                raw_values[method_name][metric_name].append(value)
                if case_group is not None:
                    grouped_case_metrics[case_group][method_name][metric_name].append(value)
                if metric_name in standardized_metrics:
                    std_values[method_name][metric_name].append(value / scale)

    aggregate = _mean_summary(raw_values)
    standardized = _mean_summary(std_values, suffix="_standardized_mean")
    grouped = {group: _mean_summary(methods) for group, methods in grouped_case_metrics.items()}
    return aggregate, standardized, grouped


def compute_ranking_summary(
    report: BenchmarkReport,
    *,
    primary_metric: str,
    metric_getter: MetricGetter,
    scale_getter: MetricGetter | None = None,
    standardized: bool = False,
) -> dict[str, Any]:
    """Compute rank/deviation summaries on a per-case primary metric."""
    per_case: dict[str, dict[str, float]] = {}
    rank_lists: dict[str, list[int]] = defaultdict(list)
    deviation_lists: dict[str, list[float]] = defaultdict(list)
    top_quartile_failures: dict[str, int] = defaultdict(int)

    for case in report.cases:
        if not isinstance(case.result_payload, dict):
            continue

        case_metrics: list[tuple[str, float, float | None]] = []
        case_scales: list[float] = []
        for method_name, result in case.result_payload.items():
            value = _finite_float(metric_getter(result))
            if value is None:
                continue
            scale = _finite_float(scale_getter(result)) if scale_getter else None
            if scale is not None:
                case_scales.append(scale)
            if standardized:
                value = value / safe_effect_scale(scale)
            case_metrics.append((method_name, value, scale))

        if not case_metrics:
            continue

        case_metrics.sort(key=lambda item: item[1])
        best_value = case_metrics[0][1]
        case_scale = safe_effect_scale(case_scales[0]) if case_scales else None
        per_case[case.name] = {name: metric for name, metric, _scale in case_metrics}
        top_quartile_cutoff = max(1, math.ceil(len(case_metrics) / 4))

        for rank, (method_name, metric_value, _scale) in enumerate(case_metrics, start=1):
            rank_lists[method_name].append(rank)
            deviation = metric_value - best_value
            if standardized:
                normalized_deviation = deviation
            elif case_scale is not None:
                normalized_deviation = deviation / case_scale
            else:
                normalized_deviation = deviation / safe_effect_scale(best_value, floor=1e-3)
            deviation_lists[method_name].append(float(normalized_deviation))
            if rank > top_quartile_cutoff:
                top_quartile_failures[method_name] += 1

    aggregate: dict[str, Any] = {}
    for method_name, ranks in rank_lists.items():
        aggregate[method_name] = {
            "primary_metric": primary_metric,
            "mean_rank": float(np.mean(ranks)),
            "max_rank": int(max(ranks)),
            "cases_ranked": int(len(ranks)),
            "max_deviation_from_best": float(max(deviation_lists.get(method_name, [0.0]))),
            "top_quartile_failures": int(top_quartile_failures.get(method_name, 0)),
        }

    return {
        "primary_metric": primary_metric,
        "standardized": standardized,
        "per_case": per_case,
        "aggregate": aggregate,
    }


def compute_grouped_ranking_summary(
    report: BenchmarkReport,
    *,
    primary_metric: str,
    metric_getter: MetricGetter,
    case_group_getter: CaseGroupGetter,
    scale_getter: MetricGetter | None = None,
    standardized: bool = False,
) -> dict[str, Any]:
    grouped_cases: dict[str, list[CaseResult]] = defaultdict(list)
    for case in report.cases:
        grouped_cases[case_group_getter(case.name)].append(case)

    out: dict[str, Any] = {}
    for group_name, cases in grouped_cases.items():
        out[group_name] = compute_ranking_summary(
            BenchmarkReport(
                circuits=report.circuits, cases=cases, circuit_scores=report.circuit_scores
            ),
            primary_metric=primary_metric,
            metric_getter=metric_getter,
            scale_getter=scale_getter,
            standardized=standardized,
        )
    return out


def build_flagship_scorecard(
    *,
    flagship_method: str,
    aggregate_metrics: dict[str, Any],
    ranking_summary: dict[str, Any] | None = None,
    thresholds: dict[str, float | int] | None = None,
    gate_method_set: list[str] | tuple[str, ...] | None = None,
    method_presence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a suite-level scorecard for a flagship plus production challengers."""
    thresholds = thresholds or {}
    method_presence = method_presence or {}
    gate_methods = list(dict.fromkeys([flagship_method, *(gate_method_set or ())]))

    def _method_checks(method_name: str) -> dict[str, Any]:
        aggregate = aggregate_metrics.get(method_name, {})
        ranking = (ranking_summary or {}).get("aggregate", {}).get(method_name, {})
        presence = method_presence.get(
            method_name,
            {
                "cases_total": 0,
                "cases_present": 0,
                "missing_cases": [],
                "present": bool(aggregate or ranking),
            },
        )

        checks: dict[str, bool] = {}
        if "mean_rank_max" in thresholds and ranking:
            checks["mean_rank"] = ranking.get("mean_rank", float("inf")) <= float(
                thresholds["mean_rank_max"]
            )
        if "max_rank_max" in thresholds and ranking:
            checks["max_rank"] = ranking.get("max_rank", float("inf")) <= float(
                thresholds["max_rank_max"]
            )
        if "max_deviation_from_best_max" in thresholds and ranking:
            checks["max_deviation_from_best"] = ranking.get(
                "max_deviation_from_best", float("inf")
            ) <= float(thresholds["max_deviation_from_best_max"])
        if "top_quartile_failures_max" in thresholds and ranking:
            checks["top_quartile_failures"] = ranking.get(
                "top_quartile_failures", float("inf")
            ) <= float(thresholds["top_quartile_failures_max"])
        for threshold_name, metric_name in (
            ("ci_coverage_mean_min", "ci_coverage_mean"),
            ("failure_rate_mean_max", "failure_rate_mean"),
        ):
            if threshold_name in thresholds and metric_name in aggregate:
                threshold = float(thresholds[threshold_name])
                value = aggregate.get(metric_name, float("nan"))
                checks[metric_name] = (
                    value >= threshold if threshold_name.endswith("_min") else value <= threshold
                )
        passes_all = bool(presence.get("present")) and bool(checks) and all(checks.values())
        return {
            "aggregate_metrics": aggregate,
            "ranking_metrics": ranking,
            "checks": checks,
            "presence": presence,
            "passes_all": passes_all,
        }

    gate_results = {method_name: _method_checks(method_name) for method_name in gate_methods}
    flagship_result = gate_results.get(flagship_method, _method_checks(flagship_method))
    flagship_presence = flagship_result["presence"]

    selected_gate_method = next(
        (method_name for method_name in gate_methods if gate_results[method_name]["passes_all"]),
        None,
    )
    if not flagship_presence.get("present"):
        flagship_status = "flagship_missing"
    elif flagship_result["passes_all"]:
        flagship_status = "flagship_passed"
    else:
        flagship_status = "flagship_present_but_failed"

    return {
        "flagship_method": flagship_method,
        "flagship_status": flagship_status,
        "flagship_presence": flagship_presence,
        "gate_method_set": gate_methods,
        "selected_gate_method": selected_gate_method,
        "thresholds": thresholds,
        "aggregate_metrics": flagship_result["aggregate_metrics"],
        "ranking_metrics": flagship_result["ranking_metrics"],
        "checks": flagship_result["checks"],
        "gate_results": gate_results,
        "passes_all": selected_gate_method is not None and bool(flagship_presence.get("present")),
    }


def compute_method_presence(
    report: BenchmarkReport,
    method_names: list[str] | tuple[str, ...] | set[str],
) -> dict[str, Any]:
    tracked = list(dict.fromkeys(method_names))
    cases_total = len(report.cases)
    presence: dict[str, Any] = {}
    for method_name in tracked:
        missing_cases: list[str] = []
        cases_present = 0
        for case in report.cases:
            payload = case.result_payload if isinstance(case.result_payload, dict) else {}
            if method_name in payload:
                cases_present += 1
            else:
                missing_cases.append(case.name)
        presence[method_name] = {
            "cases_total": cases_total,
            "cases_present": cases_present,
            "missing_cases": missing_cases,
            "present": cases_present == cases_total and cases_total > 0,
        }
    return presence


def compute_grouped_method_presence(
    report: BenchmarkReport,
    method_names: list[str] | tuple[str, ...] | set[str],
    *,
    case_group_getter: CaseGroupGetter,
) -> dict[str, Any]:
    grouped_cases: dict[str, list[CaseResult]] = defaultdict(list)
    for case in report.cases:
        grouped_cases[case_group_getter(case.name)].append(case)

    out: dict[str, Any] = {}
    for group_name, cases in grouped_cases.items():
        out[group_name] = compute_method_presence(
            BenchmarkReport(
                circuits=report.circuits, cases=cases, circuit_scores=report.circuit_scores
            ),
            method_names,
        )
    return out


def _mean_summary(
    metric_map: dict[str, dict[str, list[float]]],
    *,
    suffix: str = "_mean",
) -> dict[str, Any]:
    return {
        method_name: {
            f"{metric_name}{suffix}": float(np.mean(values))
            for metric_name, values in metrics.items()
            if values
        }
        for method_name, metrics in metric_map.items()
    }


def _finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except Exception:
        return None
    return numeric if math.isfinite(numeric) else None
