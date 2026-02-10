from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.runtime import (
    GovernanceDebugView,
    NodeDebugView,
    RunErrorView,
    RunNodeRecord,
)
from polisyos.core.trace.record import TraceRecord

from .run_index import IndexedRunRecord
from .timeline import TimelineService

_GOVERNANCE_REPORT_KEY = "governance_report_ref"
_DEFAULT_SENSITIVE_KEYS = (
    "authorization",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "cookie",
)


class DebugService:
    def __init__(
        self,
        *,
        store: FileSystemCAS,
        timeline_service: TimelineService,
        sensitive_keys: tuple[str, ...] = _DEFAULT_SENSITIVE_KEYS,
    ) -> None:
        self._store = store
        self._timeline_service = timeline_service
        self._sensitive_keys = tuple(key.lower() for key in sensitive_keys)

    def list_run_nodes(self, run: IndexedRunRecord) -> list[RunNodeRecord]:
        timeline_events = self._timeline_service.build_for_run(run).timeline.events
        workflow_nodes = self._load_workflow_nodes(run.workflow_report_ref)
        if not workflow_nodes:
            return _nodes_from_timeline(timeline_events)
        return _merge_workflow_nodes_with_timeline(workflow_nodes, timeline_events)

    def get_node_debug(self, run: IndexedRunRecord, *, alias: str) -> NodeDebugView:
        nodes = self.list_run_nodes(run)
        by_alias = {node.alias: node for node in nodes}
        record = by_alias.get(alias)
        if record is None:
            raise KeyError(alias)

        node_phase = f"scientist.node.{alias}"
        timeline = self._timeline_service.build_for_run(run).timeline.events
        node_events = [event for event in timeline if event.phase == node_phase]

        cache_hits = sum(int(event.metrics.get("cache_hit", 0)) for event in node_events)
        cache_stores = sum(int(event.metrics.get("cache_store", 0)) for event in node_events)
        cache_bypasses = sum(int(event.metrics.get("cache_bypass", 0)) for event in node_events)

        input_ids = sorted({aid for event in node_events for aid in event.input_artifact_ids})
        output_ids = sorted({aid for event in node_events for aid in event.output_artifact_ids})

        enriched_record = record.model_copy(
            update={
                "input_artifact_ids": (
                    record.input_artifact_ids if record.input_artifact_ids else input_ids
                ),
                "output_artifact_ids": (
                    record.output_artifact_ids if record.output_artifact_ids else output_ids
                ),
            }
        )

        return NodeDebugView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            alias=alias,
            record=enriched_record,
            timeline_events=node_events,
            cache_hits=cache_hits,
            cache_stores=cache_stores,
            cache_bypasses=cache_bypasses,
            notes=[],
        )

    def get_governance_debug(self, run: IndexedRunRecord) -> GovernanceDebugView:
        report_ref = None
        validation_trace = None
        fallback = False

        state_payload = self._load_experiment_state_payload(run.experiment_state_ref)
        if state_payload:
            validation_trace = _extract_validation_trace(state_payload)
            report_ref = _extract_report_ref(state_payload, _GOVERNANCE_REPORT_KEY)

        if report_ref is not None:
            report_payload = self._load_json_artifact(report_ref)
            verdict = _as_str(report_payload.get("verdict"))
            issues = _as_list_of_dicts(report_payload.get("issues"))
            notes = _as_list_of_strings(report_payload.get("notes"))
            return GovernanceDebugView(
                run_id=run.run_id,
                source_kind=run.source_kind,
                verdict=verdict,
                issues=issues,
                notes=notes,
                report_ref=report_ref,
                validation_trace=validation_trace,
                fallback_from_decision_packet=False,
            )

        packet_payload = self._load_json_artifact(run.decision_packet_ref)
        governance_block = packet_payload.get("governance")
        if isinstance(governance_block, dict):
            fallback = True
            verdict = _as_str(governance_block.get("verdict"))
            issues = _as_list_of_dicts(governance_block.get("issues"))
            notes = _as_list_of_strings(governance_block.get("notes"))
        else:
            verdict = None
            issues = []
            notes = []

        return GovernanceDebugView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            verdict=verdict,
            issues=issues,
            notes=notes,
            report_ref=None,
            validation_trace=validation_trace,
            fallback_from_decision_packet=fallback,
        )

    def get_run_errors(self, run: IndexedRunRecord) -> list[RunErrorView]:
        errors: list[RunErrorView] = []

        for item in run.manifest_errors:
            errors.append(
                RunErrorView(
                    source="manifest",
                    code=_as_str(item.get("code")) or "manifest.error",
                    message=_sanitize_string(_as_str(item.get("message")) or "Run manifest error"),
                    details=_sanitize_payload(dict(item), sensitive_keys=self._sensitive_keys),
                )
            )

        for node in self.list_run_nodes(run):
            if node.status != "fail":
                continue
            errors.append(
                RunErrorView(
                    source="workflow_report",
                    code=node.error_code or "node.failure",
                    message=_sanitize_string(node.error_message or "Node execution failed"),
                    node_alias=node.alias,
                    details=_sanitize_payload(
                        dict(node.error_details),
                        sensitive_keys=self._sensitive_keys,
                    ),
                )
            )

        if run.trace_path is not None and run.trace_path.exists():
            for record in _iter_trace_records(run.trace_path):
                for payload in record.errors:
                    errors.append(
                        RunErrorView(
                            source="trace",
                            code=_as_str(payload.get("code")) or "trace.error",
                            message=_sanitize_string(_as_str(payload.get("msg")) or "Trace error"),
                            timestamp=record.ts,
                            details=_sanitize_payload(
                                dict(payload),
                                sensitive_keys=self._sensitive_keys,
                            ),
                        )
                    )

        errors.sort(key=_error_sort_key)
        return errors

    def _load_workflow_nodes(self, workflow_report_ref: ArtifactRef | None) -> list[RunNodeRecord]:
        payload = self._load_json_artifact(workflow_report_ref)
        rows = payload.get("nodes")
        if not isinstance(rows, list):
            return []

        result: list[RunNodeRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            artifacts = row.get("artifacts")
            artifact_ids: list[str] = []
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if not isinstance(artifact, dict):
                        continue
                    artifact_id = _as_str(artifact.get("artifact_id"))
                    if artifact_id:
                        artifact_ids.append(artifact_id)

            raw_error = row.get("error")
            error_payload = raw_error if isinstance(raw_error, dict) else {}
            record = RunNodeRecord(
                alias=_as_str(row.get("alias")) or "",
                node_id=_as_str(row.get("node_id")),
                status=_normalize_status(_as_str(row.get("status"))),
                duration_ms=_as_int(row.get("duration_ms")),
                error_code=_as_str(error_payload.get("code")),
                error_message=_sanitize_string(_as_str(error_payload.get("message"))),
                error_details=_sanitize_payload(
                    error_payload.get("details")
                    if isinstance(error_payload.get("details"), dict)
                    else {},
                    sensitive_keys=self._sensitive_keys,
                ),
                skip_reason=_as_str(row.get("skip_reason")),
                artifact_ids=sorted(set(artifact_ids)),
            )
            if record.alias:
                result.append(record)
        result.sort(key=lambda item: item.alias)
        return result

    def _load_experiment_state_payload(self, ref: ArtifactRef | None) -> dict[str, Any]:
        return self._load_json_artifact(ref)

    def _load_json_artifact(self, ref: ArtifactRef | None) -> dict[str, Any]:
        if ref is None:
            return {}
        try:
            payload = from_canonical_bytes(self._store.get_bytes(ref.artifact_id))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}


def _nodes_from_timeline(events: list[Any]) -> list[RunNodeRecord]:
    grouped: dict[str, RunNodeRecord] = {}
    for event in events:
        if not event.phase.startswith("scientist.node."):
            continue
        alias = event.phase[len("scientist.node.") :]
        if not alias:
            continue
        existing = grouped.get(alias)
        if existing is None:
            existing = RunNodeRecord(alias=alias)
        status = existing.status
        if event.event == "NODE_OK":
            status = "ok"
        elif event.event == "NODE_SKIP":
            status = "skip"
        elif event.event == "NODE_FAIL":
            status = "fail"

        duration_ms = max(existing.duration_ms, _as_int(event.metrics.get("duration_ms")))
        grouped[alias] = existing.model_copy(
            update={
                "status": status,
                "duration_ms": duration_ms,
                "output_artifact_ids": sorted(
                    set(existing.output_artifact_ids).union(event.output_artifact_ids)
                ),
                "input_artifact_ids": sorted(
                    set(existing.input_artifact_ids).union(event.input_artifact_ids)
                ),
            }
        )
    return [grouped[key] for key in sorted(grouped)]


def _merge_workflow_nodes_with_timeline(
    nodes: list[RunNodeRecord], timeline_events: list[Any]
) -> list[RunNodeRecord]:
    from_timeline = {node.alias: node for node in _nodes_from_timeline(timeline_events)}
    merged: list[RunNodeRecord] = []
    for node in nodes:
        timeline_node = from_timeline.get(node.alias)
        if timeline_node is None:
            merged.append(node)
            continue
        merged.append(
            node.model_copy(
                update={
                    "input_artifact_ids": (
                        node.input_artifact_ids
                        if node.input_artifact_ids
                        else timeline_node.input_artifact_ids
                    ),
                    "output_artifact_ids": (
                        node.output_artifact_ids
                        if node.output_artifact_ids
                        else timeline_node.output_artifact_ids
                    ),
                    "artifact_ids": sorted(
                        set(node.artifact_ids).union(timeline_node.output_artifact_ids)
                    ),
                }
            )
        )
    merged.sort(key=lambda item: item.alias)
    return merged


def _extract_validation_trace(payload: dict[str, Any]) -> dict[str, Any] | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    trace = params.get("validation_trace")
    return trace if isinstance(trace, dict) else None


def _extract_report_ref(payload: dict[str, Any], key: str) -> ArtifactRef | None:
    reports_index = payload.get("reports_index")
    if not isinstance(reports_index, dict):
        return None
    raw_ref = reports_index.get(key)
    if not isinstance(raw_ref, dict):
        return None
    try:
        return ArtifactRef.model_validate(raw_ref)
    except Exception:
        return None


def _iter_trace_records(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield TraceRecord.model_validate_json(stripped)
            except Exception:
                continue


def _error_sort_key(error: RunErrorView) -> tuple[float, str, str]:
    if isinstance(error.timestamp, datetime):
        return (error.timestamp.timestamp(), error.source, error.code)
    return (float("inf"), error.source, error.code)


def _normalize_status(raw: str | None):
    if raw in {"ok", "skip", "fail", "unknown"}:
        return raw
    return "unknown"


def _as_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(item)
    return result


def _as_list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        result.append(str(item))
    return result


def _sanitize_payload(value: Any, *, sensitive_keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered_key = str(key).lower()
            if any(marker in lowered_key for marker in sensitive_keys):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_payload(item, sensitive_keys=sensitive_keys)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item, sensitive_keys=sensitive_keys) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def _sanitize_string(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if "bearer " in lowered:
        return "[REDACTED]"
    if lowered.startswith("eyj") and len(value) >= 32:
        return "[REDACTED]"
    return value
