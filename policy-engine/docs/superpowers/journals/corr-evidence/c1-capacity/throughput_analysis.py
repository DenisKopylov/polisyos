"""Recompute descriptive throughput and memory trends from complete observations.

No output is a correctness or calibration bound. Partial levels cannot establish
a throughput knee; their complete declared denominator remains visible.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable


def _number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _slope(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None
    mx = sum(x for x, _ in points) / len(points)
    my = sum(y for _, y in points) / len(points)
    denominator = sum((x - mx) ** 2 for x, _ in points)
    return sum((x - mx) * (y - my) for x, y in points) / denominator if denominator > 0 else None


def _latencies(values: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(values)

    def percentile(q: float) -> float | None:
        if not ordered:
            return None
        index = (len(ordered) - 1) * q
        lower, upper = math.floor(index), math.ceil(index)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    return {
        "count": len(ordered),
        "median": percentile(0.5),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
    }


def analyse_level(
    rows: Iterable[dict[str, Any]],
    samples: Iterable[dict[str, Any]],
    *,
    declared_count: int,
    synthetic: bool,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Consume scalar metadata only, retaining every error and missing case."""
    metadata = list(rows)
    if len({row["work_id"] for row in metadata}) != len(metadata) or len(metadata) > declared_count:
        raise ValueError("throughput_result_identity_denominator_mismatch")
    terminal = [r for r in metadata if r["status"] in {"succeeded", "failed"}]
    success = [r for r in terminal if r["status"] == "succeeded"]
    errors = [r for r in terminal if r["status"] == "failed"]
    starts = [r["started_at"] for r in metadata if _number(r.get("started_at"))]
    ends = [r["finished_at"] for r in terminal if _number(r.get("finished_at"))]
    # Timestamps are relative to the profiler's common monotonic clock origin.
    first = min(starts) if starts else None
    last = max(ends) if ends else None
    elapsed = last - first if last is not None and first is not None else None
    if elapsed is not None and elapsed <= 0:
        elapsed = None
    points_time: list[tuple[float, float]] = []
    points_completed: list[tuple[float, float]] = []
    sample_count = ambiguous_samples = 0
    active_cpu: list[tuple[float, float]] = []
    for sample in samples:
        sample_count += 1
        time = sample.get("elapsed_seconds")
        rss = sample.get("summed_rss_bytes")
        completed = sample.get("completed_work_count")
        measured = sample.get("measurement_status") == "measured"
        if not measured:
            ambiguous_samples += 1
        # Report steady-state trends separately from import/startup growth.
        if (
            measured
            and _number(time)
            and _number(rss)
            and first is not None
            and last is not None
            and first <= time <= last
        ):
            points_time.append((time, rss))
            if type(completed) is int and completed >= 0:
                points_completed.append((float(completed), rss))
            user, system = sample.get("cpu_user_seconds"), sample.get("cpu_system_seconds")
            if _number(user) and _number(system):
                active_cpu.append((time, user + system))
    cpu_delta = active_cpu[-1][1] - active_cpu[0][1] if len(active_cpu) >= 2 else None
    cpu_span = active_cpu[-1][0] - active_cpu[0][0] if len(active_cpu) >= 2 else None
    all_latencies = [r["latency_seconds"] for r in terminal if _number(r.get("latency_seconds"))]
    valid_latencies = [r["latency_seconds"] for r in success if _number(r.get("latency_seconds"))]
    complete = len(terminal) == declared_count and len(metadata) == declared_count
    if profile is not None and (
        profile.get("status") != "completed" or profile.get("returncode") != 0
    ):
        complete = False
    known_usage = [
        r
        for r in terminal
        if type(r.get("prompt_tokens")) is int and type(r.get("completion_tokens")) is int
    ]
    return {
        "schema_version": "corr.direct_extraction_level_analysis.v1",
        "synthetic": synthetic,
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "status": "measured" if complete else "not_established",
        "declared_count": declared_count,
        "observed_identity_count": len(metadata),
        "terminal_count": len(terminal),
        "typed_success_count": len(success),
        "error_count": len(errors),
        "missing_terminal_count": declared_count - len(terminal),
        "complete_rate": len(terminal) / declared_count,
        "typed_success_rate": len(success) / declared_count,
        "error_rate": len(errors) / declared_count,
        "error_kinds": dict(
            sorted(Counter(r.get("error_kind") or "ambiguous" for r in errors).items())
        ),
        "latency_seconds_all_terminal": _latencies(all_latencies),
        "latency_seconds_typed_success": _latencies(valid_latencies),
        "latency_scope": (
            "persisted work admission before client/owner creation through typed owner outcome; "
            "source resolution precedes admission; provider-only duration retained separately"
        ),
        "startup_seconds_before_first_dispatch": first,
        "startup_boundary": "first work admission, preceding actual SDK dispatch",
        "warm_active_wall_seconds": elapsed,
        "terminal_per_second": len(terminal) / elapsed if elapsed else None,
        "typed_success_per_second": len(success) / elapsed if elapsed else None,
        "known_usage_count": len(known_usage),
        "unknown_usage_count": len(terminal) - len(known_usage),
        "observed_prompt_tokens": sum(r["prompt_tokens"] for r in known_usage),
        "observed_completion_tokens": sum(r["completion_tokens"] for r in known_usage),
        "memory": {
            "scope": "observed_warm_active_interval_only; OLS descriptive not causal",
            "sample_count": sample_count,
            "ambiguous_sample_count": ambiguous_samples,
            "warm_time_sample_count": len(points_time),
            "warm_completed_sample_count": len(points_completed),
            "rss_slope_bytes_per_second": _slope(points_time),
            "rss_slope_bytes_per_completed": _slope(points_completed),
            "warm_first_rss_bytes": points_time[0][1] if points_time else None,
            "warm_last_rss_bytes": points_time[-1][1] if points_time else None,
        },
        "warm_observed_cpu_seconds": cpu_delta,
        "warm_observed_cpu_per_wall": cpu_delta / cpu_span
        if cpu_span and cpu_delta is not None
        else None,
        "profile": profile,
        "scope_limitation": (
            "direct extraction only; excludes screening, self-verification and acquisition"
        ),
        "correctness_claim": None,
    }


def stop_decision(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """Apply the predeclared rule to complete levels without omitting failures."""
    gain = None
    if current["status"] != "measured":
        reason = "incomplete_level"
    elif current["error_rate"] > 0.10:
        reason = "error_rate_above_10_percent"
    elif previous is not None:
        before, after = (
            previous.get("typed_success_per_second"),
            current.get("typed_success_per_second"),
        )
        if not _number(before) or not _number(after) or before <= 0:
            reason = "throughput_comparison_not_established"
        else:
            gain = after / before - 1
            reason = "throughput_plateau" if gain < 0.20 else None
    else:
        reason = None
    return {
        "stop_higher_levels": reason is not None,
        "reason": reason,
        "typed_success_throughput_relative_gain": gain,
        "knee_established": reason in {"throughput_plateau", "error_rate_above_10_percent"},
    }
