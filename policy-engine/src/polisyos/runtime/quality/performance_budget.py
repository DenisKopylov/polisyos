"""Canary performance budget report construction."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec

SCHEMA_VERSION = "policyos.canary_performance_budget.v1"
_LOGGER = logging.getLogger(__name__)


_BUDGETS_MS: dict[str, float] = {
    "control.job_total": 900_000.0,
    "control.queue_latency": 30_000.0,
    "control.execution": 900_000.0,
    "cas.round_trip_p95": 250.0,
    "runtime.run_index_refresh": 500.0,
    "runtime.run_index_list": 100.0,
    "runtime.timeline_api": 500.0,
    "runtime.lineage_api": 750.0,
    "evidence.collection": 5_000.0,
    "dashboard.route_render": 3_000.0,
}

_RUNTIME_OBSERVATION_ALIASES: dict[str, tuple[str, ...]] = {
    "runtime.run_index_refresh": (
        "run_index_refresh_ms",
        "run_index_refresh_duration_ms",
        "run_index.refresh.duration_ms",
    ),
    "runtime.run_index_list": (
        "run_index_list_ms",
        "run_index_list_duration_ms",
        "run_index.list.duration_ms",
    ),
    "runtime.timeline_api": (
        "timeline_api_ms",
        "timeline_api_duration_ms",
        "timeline_build_ms",
        "timeline.build.duration_ms",
    ),
    "runtime.lineage_api": (
        "lineage_api_ms",
        "lineage_api_duration_ms",
        "lineage_build_ms",
        "lineage.build.duration_ms",
    ),
}

_ROW_META: dict[str, dict[str, Any]] = {
    "control.job_total": {
        "category": "control",
        "layer": "control_plane",
        "source": "control_timestamps",
        "retryable": True,
        "next_action": (
            "Inspect control job timing and worker saturation before production approval."
        ),
    },
    "control.queue_latency": {
        "category": "control",
        "layer": "control_plane",
        "source": "control_timestamps",
        "retryable": True,
        "next_action": (
            "Inspect control queue depth, lease ownership, and worker heartbeat latency."
        ),
    },
    "control.execution": {
        "category": "control",
        "layer": "control_plane",
        "source": "control_timestamps",
        "retryable": True,
        "next_action": "Inspect control worker execution trace and downstream dependency timings.",
    },
    "cas.round_trip_p95": {
        "category": "cas",
        "layer": "artifact_store",
        "source": "cas_samples",
        "retryable": True,
        "next_action": "Inspect CAS filesystem latency and artifact store contention.",
    },
    "runtime.run_index_refresh": {
        "category": "runtime_api",
        "layer": "runtime_api",
        "source": "runtime_hot_paths",
        "retryable": True,
        "next_action": "Profile run-index refresh and reduce filesystem scan work.",
    },
    "runtime.run_index_list": {
        "category": "runtime_api",
        "layer": "runtime_api",
        "source": "runtime_hot_paths",
        "retryable": True,
        "next_action": "Profile run-index listing and tenant filtering latency.",
    },
    "runtime.timeline_api": {
        "category": "runtime_api",
        "layer": "runtime_api",
        "source": "runtime_hot_paths",
        "retryable": True,
        "next_action": "Profile timeline assembly and trace-event normalization.",
    },
    "runtime.lineage_api": {
        "category": "runtime_api",
        "layer": "runtime_api",
        "source": "runtime_hot_paths",
        "retryable": True,
        "next_action": "Profile lineage graph expansion and artifact edge resolution.",
    },
    "evidence.collection": {
        "category": "evidence",
        "layer": "canary_evidence",
        "source": "evidence_collection",
        "retryable": True,
        "next_action": "Inspect evidence bundle assembly and filesystem write latency.",
    },
    "dashboard.route_render": {
        "category": "dashboard",
        "layer": "dashboard",
        "source": "dashboard_evidence",
        "retryable": True,
        "next_action": (
            "Inspect dashboard smoke trace and optimize the route before production approval."
        ),
    },
}


def build_canary_performance_budget(
    *,
    canary_kind: str,
    job_payload: Mapping[str, Any] | None = None,
    run_payload: Mapping[str, Any] | None = None,
    agents_payload: Mapping[str, Any] | None = None,
    timeline_payload: Mapping[str, Any] | None = None,
    lineage_payload: Mapping[str, Any] | None = None,
    dashboard_evidence: Mapping[str, Any] | None = None,
    runtime_observations: Mapping[str, Any] | None = None,
    cas_samples: Sequence[Any] | None = None,
    evidence_collection_duration_ms: float | int | None = None,
    budget_overrides_ms: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the stable canary performance budget evidence payload."""

    rows: list[dict[str, Any]] = []
    rows.extend(_control_rows(job_payload))
    rows.extend(_cas_rows(cas_samples))

    runtime_sources = [
        runtime_observations,
        _nested_get(job_payload, "runtime_hot_paths"),
        _nested_get(run_payload, "runtime_hot_paths"),
        _nested_get(agents_payload, "runtime_hot_paths"),
        _nested_get(timeline_payload, "performance"),
        _nested_get(lineage_payload, "performance"),
    ]
    rows.extend(_runtime_rows(runtime_sources))

    evidence_ms = _number(evidence_collection_duration_ms)
    if evidence_ms is not None:
        rows.append(_row("evidence.collection", evidence_ms))

    rows.extend(_dashboard_rows(dashboard_evidence))
    rows = [_with_budget(row, budget_overrides_ms=budget_overrides_ms) for row in rows]

    summary = _summary(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc(now).isoformat(),
        "canary_kind": canary_kind,
        "status": summary["status"],
        "phase_budgets": rows,
        "budget_summary": summary,
    }


def run_cost_budget_policy_from_performance_budget(
    performance_budget: Mapping[str, Any],
    *,
    policy_ref: str,
    authority_policy_ref: str,
    owner: str = "team-runtime-quality",
    ttl_seconds: int = 7 * 24 * 60 * 60,
    evidence_ref: str = "quality_evidence/canary_performance_budget.json",
) -> dict[str, Any]:
    """Project a governed wall-clock run-cost policy from performance budgets.

    Args:
        performance_budget: Canary performance budget payload.
        policy_ref: Governed run-cost policy/config ref.
        authority_policy_ref: Authority-level policy ref that permits blocking.
        owner: Budget owner for warning/blocker lifecycle.
        ttl_seconds: Warning/blocker lifecycle TTL.
        evidence_ref: Runtime-quality evidence ref for this budget input.

    Returns:
        A run-cost budget policy with a `wall_clock_seconds` limit, or an empty
        limits list when the performance payload has no duration budget.
    """

    budget_ms = _performance_budget_wall_clock_ms(performance_budget)
    limits: list[dict[str, Any]] = []
    if budget_ms is not None:
        limits.append(
            {
                "dimension": "wall_clock_seconds",
                "budget": round(budget_ms / 1000.0, 6),
                "unit": "second",
                "closeout_effect": "blocking",
                "authority_policy_ref": authority_policy_ref,
                "owner": owner,
                "ttl_seconds": int(ttl_seconds),
                "next_action": (
                    "Investigate canary performance budget wall-clock overrun before "
                    "production-authority closeout."
                ),
                "evidence_ref": evidence_ref,
            }
        )
    return {
        "policy_ref": policy_ref,
        "source": "canary_performance_budget",
        "owner": owner,
        "ttl_seconds": int(ttl_seconds),
        "limits": limits,
    }


def measure_cas_round_trip_samples(
    store: Any,
    *,
    sample_count: int = 3,
) -> list[dict[str, float]]:
    """Write and read tiny CAS samples, returning sanitized timing observations."""

    put_json = getattr(store, "put_json", None)
    get_bytes = getattr(store, "get_bytes", None)
    if not callable(put_json) or not callable(get_bytes):
        return []

    samples: list[dict[str, float]] = []
    for index in range(max(0, sample_count)):
        started = time.perf_counter()
        try:
            ref = put_json(
                {"sample": "canary_performance_budget", "index": index},
                ArtifactWriteOptions(
                    kind="runtime.canary_performance_budget_sample",
                    media_type="application/json",
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            get_bytes(ref.artifact_id)
        except Exception as exc:
            _LOGGER.debug("Skipping CAS round-trip sample after failed write/read: %s", exc)
            continue
        samples.append({"duration_ms": round((time.perf_counter() - started) * 1000.0, 3)})
    return samples


def _row(phase: str, observed_duration_ms: float, **overrides: Any) -> dict[str, Any]:
    meta = dict(_ROW_META[phase.split(":", 1)[0]])
    retryable = bool(meta["retryable"])
    row = {
        "phase": phase,
        "category": meta["category"],
        "layer": meta["layer"],
        "source": meta["source"],
        "observed_duration_ms": round(observed_duration_ms, 3),
        "duration_ms": round(observed_duration_ms, 3),
        "budget_ms": float(overrides.pop("budget_ms", _BUDGETS_MS[phase.split(":", 1)[0]])),
        "status": "pass",
        "retryable": retryable,
        "retryability": "retryable" if retryable else "not_retryable",
        "production_blocking": True,
        "next_action": meta["next_action"],
    }
    row.update(overrides)
    row.setdefault(
        "retryability",
        "retryable" if bool(row.get("retryable")) else "not_retryable",
    )
    return row


def _with_budget(
    row: dict[str, Any],
    *,
    budget_overrides_ms: Mapping[str, Any] | None,
) -> dict[str, Any]:
    phase = str(row["phase"])
    base_phase = phase.split(":", 1)[0]
    override = None
    if budget_overrides_ms:
        override = budget_overrides_ms.get(phase)
        if override is None:
            override = budget_overrides_ms.get(base_phase)
    budget_ms = _number(override) or _number(row.get("budget_ms")) or _BUDGETS_MS[base_phase]
    observed_ms = _number(row.get("observed_duration_ms")) or 0.0
    enriched = dict(row)
    enriched["budget_ms"] = round(budget_ms, 3)
    enriched["status"] = "pass" if observed_ms <= budget_ms else "over_budget"
    over_by_ms = round(max(0.0, observed_ms - budget_ms), 3)
    if over_by_ms > 0:
        enriched["over_by_ms"] = over_by_ms
    else:
        enriched.pop("over_by_ms", None)
    return enriched


def _control_rows(job_payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(job_payload, Mapping):
        return []
    submitted = _timestamp(
        job_payload.get("submitted_at")
        or job_payload.get("created_at")
        or job_payload.get("queued_at")
    )
    started = _timestamp(job_payload.get("started_at"))
    finished = _timestamp(
        job_payload.get("finished_at")
        or job_payload.get("completed_at")
        or job_payload.get("ended_at")
    )
    rows: list[dict[str, Any]] = []
    if submitted is not None and finished is not None:
        rows.append(_row("control.job_total", _duration_ms(submitted, finished)))
    if submitted is not None and started is not None:
        rows.append(_row("control.queue_latency", _duration_ms(submitted, started)))
    if started is not None and finished is not None:
        rows.append(_row("control.execution", _duration_ms(started, finished)))
    return rows


def _cas_rows(cas_samples: Sequence[Any] | None) -> list[dict[str, Any]]:
    durations = [_duration_from_value(sample) for sample in (cas_samples or [])]
    clean = sorted(duration for duration in durations if duration is not None)
    if not clean:
        return []
    index = max(0, math.ceil(len(clean) * 0.95) - 1)
    return [
        _row(
            "cas.round_trip_p95",
            clean[index],
            sample_count=len(clean),
        )
    ]


def _runtime_rows(sources: Sequence[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase, aliases in _RUNTIME_OBSERVATION_ALIASES.items():
        duration = None
        for source in sources:
            duration = _find_duration(source, aliases)
            if duration is not None:
                break
        if duration is not None:
            rows.append(_row(phase, duration))
    return rows


def _dashboard_rows(dashboard_evidence: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(dashboard_evidence, Mapping):
        return []
    raw_routes = dashboard_evidence.get("routes")
    if not isinstance(raw_routes, list):
        raw_routes = dashboard_evidence.get("route_timings")
    if not isinstance(raw_routes, list):
        raw_route = dashboard_evidence.get("route")
        raw_routes = [raw_route] if isinstance(raw_route, Mapping) else []

    rows: list[dict[str, Any]] = []
    for index, route in enumerate(raw_routes):
        if not isinstance(route, Mapping):
            continue
        duration = _find_duration(
            route,
            (
                "render_duration_ms",
                "route_render_ms",
                "duration_ms",
                "load_duration_ms",
            ),
        )
        if duration is None:
            continue
        path = str(route.get("path") or route.get("route") or route.get("url") or f"route-{index}")
        phase = f"dashboard.route_render:{path}"
        budget_ms = _number(route.get("budget_ms"))
        rows.append(
            _row(
                phase,
                duration,
                budget_ms=(
                    budget_ms
                    if budget_ms is not None
                    else _BUDGETS_MS["dashboard.route_render"]
                ),
                path=path,
            )
        )
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    over_budget = [row for row in rows if row.get("status") == "over_budget"]
    warnings = [row for row in rows if row.get("status") in {"warn", "warning"}]
    status = "fail" if over_budget else ("warn" if warnings else "pass")
    slowest = max(rows, key=lambda row: float(row.get("observed_duration_ms") or 0), default=None)
    return {
        "status": status,
        "phase_count": len(rows),
        "pass_count": sum(1 for row in rows if row.get("status") == "pass"),
        "warning_count": len(warnings),
        "over_budget_count": len(over_budget),
        "production_blocking_over_budget_count": sum(
            1 for row in over_budget if row.get("production_blocking") is True
        ),
        "approval_blocking": any(row.get("production_blocking") is True for row in over_budget),
        "slowest_phase": slowest.get("phase") if slowest else None,
        "slowest_duration_ms": slowest.get("observed_duration_ms") if slowest else None,
    }


def _performance_budget_wall_clock_ms(performance_budget: Mapping[str, Any]) -> float | None:
    rows = [
        row
        for row in performance_budget.get("phase_budgets") or ()
        if isinstance(row, Mapping)
    ]
    for row in rows:
        if row.get("phase") == "control.job_total":
            total_budget = _number(row.get("budget_ms") or row.get("max_duration_ms"))
            if total_budget is not None:
                return round(total_budget, 3)
    total = sum(_number(row.get("budget_ms") or row.get("max_duration_ms")) or 0.0 for row in rows)
    if total > 0:
        return round(total, 3)
    return _number(performance_budget.get("budget_ms") or performance_budget.get("max_duration_ms"))


def _nested_get(payload: Any, key: str) -> Any:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _nested_get(value, key)
            if found is not None:
                return found
    return None


def _find_duration(payload: Any, aliases: Sequence[str]) -> float | None:
    if not isinstance(payload, Mapping):
        return None
    for alias in aliases:
        value = _value_at_path(payload, alias)
        duration = _duration_from_value(value)
        if duration is not None:
            return duration
    for key, value in payload.items():
        if str(key) in aliases:
            duration = _duration_from_value(value)
            if duration is not None:
                return duration
        if isinstance(value, Mapping):
            duration = _find_duration(value, aliases)
            if duration is not None:
                return duration
    return None


def _value_at_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _duration_from_value(value: Any) -> float | None:
    if isinstance(value, Mapping):
        for key in (
            "observed_duration_ms",
            "duration_ms",
            "elapsed_ms",
            "latency_ms",
            "render_duration_ms",
        ):
            duration = _number(value.get(key))
            if duration is not None:
                return duration
        seconds = _number(value.get("duration_seconds") or value.get("elapsed_seconds"))
        if seconds is not None:
            return seconds * 1000.0
        return None
    return _number(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _duration_ms(started_at: datetime, finished_at: datetime) -> float:
    return round(max(0.0, (finished_at - started_at).total_seconds() * 1000.0), 3)


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "SCHEMA_VERSION",
    "build_canary_performance_budget",
    "measure_cas_round_trip_samples",
    "run_cost_budget_policy_from_performance_budget",
]
