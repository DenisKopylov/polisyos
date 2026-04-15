"""Shared helper utilities for Scientist feedback workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from polisyos.core.contracts.feedback import (
    DecisionCompareReport,
    MonitoringMetricResult,
    MonitoringRange,
    MonitoringVerdict,
)

__all__ = [
    "_aggregate_monitoring_verdict",
    "_as_bool_or_none",
    "_as_float",
    "_as_str",
    "_extract_artifact_id",
    "_extract_feedback_ref",
    "_extract_metric_observation",
    "_extract_numeric_value",
    "_extract_revised_metric_ids",
    "_extract_rows",
    "_outside_range",
    "_path_get",
    "_within_range",
]


def _aggregate_monitoring_verdict(
    metrics: Sequence[MonitoringMetricResult],
    *,
    degraded: bool,
) -> MonitoringVerdict:
    verdicts = {item.verdict for item in metrics}
    if MonitoringVerdict.REFUTED in verdicts:
        return MonitoringVerdict.REFUTED
    if degraded:
        return MonitoringVerdict.DEGRADED
    if verdicts == {MonitoringVerdict.CONFIRMED} and verdicts:
        return MonitoringVerdict.CONFIRMED
    if verdicts == {MonitoringVerdict.INSUFFICIENT_DATA} and verdicts:
        return MonitoringVerdict.INSUFFICIENT_DATA
    if MonitoringVerdict.INCONCLUSIVE in verdicts:
        return MonitoringVerdict.INCONCLUSIVE
    return MonitoringVerdict.PENDING


def _extract_metric_observation(payload: object, metric_name: str) -> tuple[float | None, int]:
    if isinstance(payload, Mapping):
        direct = payload.get(metric_name)
        numeric = _extract_numeric_value(direct)
        if numeric is not None:
            return numeric
        values = payload.get("values")
        if isinstance(values, Mapping):
            numeric = _extract_numeric_value(values.get(metric_name))
            if numeric is not None:
                return numeric
        rows = payload.get("rows")
        if isinstance(rows, Sequence):
            return _extract_metric_observation(rows, metric_name)
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        numeric_values: list[float] = []
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            value = _as_float(item.get(metric_name))
            if value is not None:
                numeric_values.append(value)
        if numeric_values:
            return numeric_values[-1], len(numeric_values)
    return None, 0


def _extract_numeric_value(value: object) -> tuple[float | None, int] | None:
    scalar = _as_float(value)
    if scalar is not None:
        return scalar, 1
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        numeric_values = [_as_float(item) for item in value]
        finite_values = [item for item in numeric_values if item is not None]
        if finite_values:
            return finite_values[-1], len(finite_values)
    return None


def _extract_feedback_ref(packet_payload: Mapping[str, object], key: str) -> str | None:
    feedback_loop = packet_payload.get("feedback_loop")
    if not isinstance(feedback_loop, Mapping):
        return None
    return _extract_artifact_id(feedback_loop.get(key))


def _extract_artifact_id(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, Mapping):
        artifact_id = value.get("artifact_id")
        if isinstance(artifact_id, str) and artifact_id.strip():
            return artifact_id
    return None


def _extract_rows(payload: object) -> list[Mapping[str, object]]:
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return [item for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        rows = payload.get("rows")
        if isinstance(rows, Sequence):
            return [item for item in rows if isinstance(item, Mapping)]
    return []


def _extract_revised_metric_ids(compare_report: DecisionCompareReport) -> list[str]:
    data_delta = compare_report.deltas.get("data")
    if data_delta is None:
        return []
    semantic_diff = data_delta.details.get("semantic_diff")
    if not isinstance(semantic_diff, Mapping):
        return []
    changes = semantic_diff.get("changes")
    if not isinstance(changes, list):
        return []
    metric_ids: list[str] = []
    for change in changes:
        if not isinstance(change, Mapping):
            continue
        field_deltas = change.get("field_deltas")
        if not isinstance(field_deltas, Mapping):
            continue
        for field_name in field_deltas:
            metric_id = str(field_name)
            if metric_id not in metric_ids:
                metric_ids.append(metric_id)
    return metric_ids


def _within_range(value: float, range_: MonitoringRange) -> bool:
    if range_.lower is not None and value < range_.lower:
        return False
    if range_.upper is not None and value > range_.upper:
        return False
    return True


def _outside_range(value: float, range_: MonitoringRange) -> bool:
    if range_.lower is not None and value < range_.lower:
        return True
    if range_.upper is not None and value > range_.upper:
        return True
    return False


def _path_get(payload: Mapping[str, object], path: Sequence[str]) -> object | None:
    current: object = payload
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None
