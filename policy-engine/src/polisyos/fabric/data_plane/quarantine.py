"""CAS-backed dead-letter quarantine storage, reporting, and deterministic replay."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.observability import get_metrics
from polisyos.fabric.io.atomic import append_text_locked, file_lock
from polisyos.fabric.temporal import utc_now

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from polisyos.core.artifacts.manifest import ArtifactManifest
    from polisyos.core.observability import MetricsRegistry

_QUARANTINE_SCHEMA = SchemaInfo(
    name="polisyos.fabric.QuarantineRecord",
    version="1.0",
)
_QUARANTINE_PAYLOAD_SCHEMA = SchemaInfo(
    name="polisyos.fabric.QuarantinePayload",
    version="1.0",
)
_QUARANTINE_REPROCESS_SCHEMA = SchemaInfo(
    name="polisyos.fabric.QuarantineReprocessResult",
    version="1.0",
)
_INDEX_NAME = "quarantine_records.jsonl"
_INDEX_LOCK_NAME = "quarantine_records.lock"
_DEFAULT_RETRY_POLICY = {"mode": "deterministic_reprocess", "max_attempts": 1}
_REPROCESSORS: dict[str, Callable[[Any, QuarantineRecord], Any]] = {}


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


@runtime_checkable
class IndexedArtifactStore(Protocol):
    """Artifact store protocol that also exposes a mutable local root path."""

    root: Path

    def has(self, artifact_id: ArtifactID) -> bool: ...

    def get_bytes(self, artifact_id: ArtifactID) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest: ...

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef: ...


@dataclass(frozen=True)
class QuarantineRecord:
    """One poisoned record/message/claim isolated from the happy-path batch."""

    record_id: str
    created_at: str
    reason: str
    severity: str
    source: str
    raw_payload_ref: str | None = None
    schema_version: str | None = None
    traceback_class: str | None = None
    trace_id: str | None = None
    retry_policy: dict[str, Any] = field(default_factory=dict)
    downstream_impacts: tuple[str, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        reason: str,
        severity: str,
        source: str,
        raw_payload_ref: str | None = None,
        schema_version: str | None = None,
        traceback_class: str | None = None,
        trace_id: str | None = None,
        retry_policy: Mapping[str, Any] | None = None,
        downstream_impacts: Sequence[str] = (),
        context: Mapping[str, Any] | None = None,
    ) -> QuarantineRecord:
        return cls(
            record_id=f"quarantine.{uuid.uuid4().hex}",
            created_at=utc_now(drop_microseconds=True).isoformat().replace("+00:00", "Z"),
            reason=str(reason),
            severity=str(severity),
            source=str(source),
            raw_payload_ref=str(raw_payload_ref) if raw_payload_ref else None,
            schema_version=str(schema_version) if schema_version else None,
            traceback_class=str(traceback_class) if traceback_class else None,
            trace_id=str(trace_id) if trace_id else None,
            retry_policy=dict(retry_policy or _DEFAULT_RETRY_POLICY),
            downstream_impacts=tuple(
                dict.fromkeys(str(item) for item in downstream_impacts if str(item).strip())
            ),
            context=dict(context or {}),
        )


@dataclass(frozen=True)
class QuarantineReport:
    """Aggregated DLQ summary for metrics, lineage, and operator review."""

    total_records: int
    by_reason: dict[str, int]
    by_severity: dict[str, int]
    by_source: dict[str, int]
    downstream_impacts: dict[str, int]
    affected_sources: tuple[str, ...]


@dataclass(frozen=True)
class QuarantineReprocessResult:
    """Outcome of deterministic replay over quarantined records."""

    attempted: int
    succeeded: int
    failed: int
    result_refs: tuple[str, ...] = ()
    failed_record_ids: tuple[str, ...] = ()


def quarantine_index_path(store: IndexedArtifactStore) -> Path:
    """Mutable JSONL index tracking persisted quarantine record artifact refs."""
    return Path(store.root) / "quarantine" / _INDEX_NAME


def _quarantine_index_lock_path(store: IndexedArtifactStore) -> Path:
    return Path(store.root) / "quarantine" / _INDEX_LOCK_NAME


def _record_dlq_metric(
    store: IndexedArtifactStore,
    *,
    metrics: MetricsRegistry | None = None,
) -> None:
    resolved_metrics = metrics if metrics is not None else _default_metrics()
    if resolved_metrics is None or getattr(resolved_metrics, "set_fabric_dlq_count", None) is None:
        return
    index_path = quarantine_index_path(store)
    if not index_path.exists():
        resolved_metrics.set_fabric_dlq_count(0.0, queue_name="fabric.quarantine")
        return
    with (
        file_lock(_quarantine_index_lock_path(store)),
        index_path.open("r", encoding="utf-8") as handle,
    ):
        count = sum(1 for line in handle if line.strip())
    resolved_metrics.set_fabric_dlq_count(float(count), queue_name="fabric.quarantine")


def _artifact_ref_from_str(value: str) -> ArtifactID:
    return ArtifactID.model_validate(value)


def _json_payload(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict(orient="records")
        except TypeError:
            return value.to_dict()
    return value


def _put_payload_artifact(
    store: IndexedArtifactStore,
    *,
    payload: Any,
    kind: str = "fabric.quarantine_payload",
    media_type: str = "application/json",
    schema_version: str = "1.0",
    inputs: Sequence[str] = (),
) -> ArtifactRef:
    payload_obj = _json_payload(payload)
    input_refs = [
        InputRef(artifact_id=_artifact_ref_from_str(artifact_id), role="quarantine_input")
        for artifact_id in inputs
    ]
    ref = store.put_json(
        payload_obj,
        ArtifactWriteOptions(
            kind=kind,
            media_type=media_type,
            schema=SchemaInfo(name=_QUARANTINE_PAYLOAD_SCHEMA.name, version=schema_version),
            inputs=input_refs or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )
    return ArtifactRef.model_validate(ref.model_dump())


def persist_quarantine_record(
    store: IndexedArtifactStore,
    *,
    record: QuarantineRecord,
    raw_payload: Any | None = None,
    input_artifact_ids: Sequence[str] = (),
    metrics: MetricsRegistry | None = None,
) -> ArtifactRef:
    """Persist one quarantine record and append its immutable ref to the JSONL index."""

    raw_payload_ref = record.raw_payload_ref
    if raw_payload is not None and raw_payload_ref is None:
        payload_ref = _put_payload_artifact(
            store,
            payload=raw_payload,
            inputs=input_artifact_ids,
            schema_version=record.schema_version or "1.0",
        )
        raw_payload_ref = str(payload_ref.artifact_id)
        record = QuarantineRecord(
            record_id=record.record_id,
            created_at=record.created_at,
            reason=record.reason,
            severity=record.severity,
            source=record.source,
            raw_payload_ref=raw_payload_ref,
            schema_version=record.schema_version,
            traceback_class=record.traceback_class,
            trace_id=record.trace_id,
            retry_policy=dict(record.retry_policy),
            downstream_impacts=tuple(record.downstream_impacts),
            context=dict(record.context),
        )

    input_refs = [
        InputRef(artifact_id=_artifact_ref_from_str(artifact_id), role="quarantine_input")
        for artifact_id in input_artifact_ids
    ]
    if raw_payload_ref:
        input_refs.append(
            InputRef(
                artifact_id=_artifact_ref_from_str(raw_payload_ref),
                role="raw_payload",
            )
        )

    ref = store.put_json(
        asdict(record),
        ArtifactWriteOptions(
            kind="fabric.quarantine_record",
            media_type="application/json",
            schema=_QUARANTINE_SCHEMA,
            inputs=input_refs or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
    )
    artifact_ref = ArtifactRef.model_validate(ref.model_dump())
    append_text_locked(
        quarantine_index_path(store),
        json.dumps(
            {
                "artifact_id": str(artifact_ref.artifact_id),
                "record_id": record.record_id,
                "created_at": record.created_at,
                "reason": record.reason,
                "severity": record.severity,
                "source": record.source,
            },
            sort_keys=True,
        )
        + "\n",
        lock_path=_quarantine_index_lock_path(store),
    )
    _record_dlq_metric(store, metrics=metrics)
    return artifact_ref


def load_quarantine_record(
    store: IndexedArtifactStore,
    artifact_id: str | ArtifactID,
) -> QuarantineRecord:
    """Load one quarantine record from CAS."""

    aid = (
        artifact_id
        if isinstance(artifact_id, ArtifactID)
        else _artifact_ref_from_str(str(artifact_id))
    )
    payload = from_canonical_bytes(store.get_bytes(aid))
    if not isinstance(payload, dict):
        raise TypeError("quarantine record payload must be a JSON object")
    return QuarantineRecord(
        record_id=str(payload["record_id"]),
        created_at=str(payload["created_at"]),
        reason=str(payload["reason"]),
        severity=str(payload["severity"]),
        source=str(payload["source"]),
        raw_payload_ref=str(payload["raw_payload_ref"]) if payload.get("raw_payload_ref") else None,
        schema_version=str(payload["schema_version"]) if payload.get("schema_version") else None,
        traceback_class=(
            str(payload["traceback_class"]) if payload.get("traceback_class") else None
        ),
        trace_id=str(payload["trace_id"]) if payload.get("trace_id") else None,
        retry_policy=dict(payload.get("retry_policy", {})),
        downstream_impacts=tuple(payload.get("downstream_impacts", ())),
        context=dict(payload.get("context", {})),
    )


def load_quarantine_payload(
    store: IndexedArtifactStore,
    raw_payload_ref: str | None,
) -> Any | None:
    """Load the raw payload artifact referenced by one quarantine record."""

    if not raw_payload_ref:
        return None
    aid = _artifact_ref_from_str(raw_payload_ref)
    manifest = store.get_manifest(aid)
    raw = store.get_bytes(aid)
    if manifest.media_type == "application/json":
        return from_canonical_bytes(raw)
    return raw


def list_quarantine_records(
    store: IndexedArtifactStore,
    *,
    source: str | None = None,
    reason: str | None = None,
    severity: str | None = None,
) -> list[tuple[str, QuarantineRecord]]:
    """List quarantine records in deterministic creation order."""

    index_path = quarantine_index_path(store)
    if not index_path.exists():
        return []
    rows: list[tuple[str, QuarantineRecord]] = []
    with (
        file_lock(_quarantine_index_lock_path(store)),
        index_path.open("r", encoding="utf-8") as handle,
    ):
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            artifact_id = str(row["artifact_id"])
            record = load_quarantine_record(store, artifact_id)
            if source is not None and record.source != source:
                continue
            if reason is not None and record.reason != reason:
                continue
            if severity is not None and record.severity != severity:
                continue
            rows.append((artifact_id, record))
    rows.sort(key=lambda item: (item[1].created_at, item[0]))
    return rows


def build_quarantine_report(
    records: Sequence[tuple[str, QuarantineRecord]] | Sequence[QuarantineRecord],
) -> QuarantineReport:
    """Aggregate quarantine records into operator-friendly DLQ counters."""

    normalized: list[QuarantineRecord] = []
    for record in records:
        if isinstance(record, tuple):
            normalized.append(record[1])
        else:
            normalized.append(record)

    by_reason: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_source: dict[str, int] = {}
    downstream_impacts: dict[str, int] = {}
    for record in normalized:
        by_reason[record.reason] = by_reason.get(record.reason, 0) + 1
        by_severity[record.severity] = by_severity.get(record.severity, 0) + 1
        by_source[record.source] = by_source.get(record.source, 0) + 1
        for impact in record.downstream_impacts:
            downstream_impacts[impact] = downstream_impacts.get(impact, 0) + 1

    return QuarantineReport(
        total_records=len(normalized),
        by_reason=dict(sorted(by_reason.items())),
        by_severity=dict(sorted(by_severity.items())),
        by_source=dict(sorted(by_source.items())),
        downstream_impacts=dict(sorted(downstream_impacts.items())),
        affected_sources=tuple(sorted(by_source)),
    )


def register_quarantine_reprocessor(
    source: str,
    handler: Callable[[Any, QuarantineRecord], Any],
) -> None:
    """Register a deterministic replay handler for one quarantine source prefix."""

    key = str(source).strip()
    if not key:
        raise ValueError("quarantine reprocessor source must not be empty")
    _REPROCESSORS[key] = handler


def _resolve_reprocessor(
    source: str,
    handler: Callable[[Any, QuarantineRecord], Any] | None = None,
) -> Callable[[Any, QuarantineRecord], Any]:
    if handler is not None:
        return handler
    for prefix in sorted(_REPROCESSORS, key=len, reverse=True):
        if source == prefix or source.startswith(prefix):
            return _REPROCESSORS[prefix]
    raise KeyError(f"no quarantine reprocessor registered for source {source!r}")


def reprocess_quarantine_records(
    store: IndexedArtifactStore,
    *,
    artifact_ids: Sequence[str] | None = None,
    source: str | None = None,
    handler: Callable[[Any, QuarantineRecord], Any] | None = None,
) -> QuarantineReprocessResult:
    """Replay quarantined raw payloads in deterministic order after a fix is deployed."""

    candidates = list_quarantine_records(store, source=source)
    if artifact_ids is not None:
        allowed = {str(artifact_id) for artifact_id in artifact_ids}
        candidates = [item for item in candidates if item[0] in allowed]
    result_refs: list[str] = []
    failed_record_ids: list[str] = []

    for artifact_id, record in candidates:
        payload = load_quarantine_payload(store, record.raw_payload_ref)
        try:
            resolved_handler = _resolve_reprocessor(record.source, handler=handler)
            replay_result = resolved_handler(payload, record)
            replay_ref = store.put_json(
                {
                    "quarantine_artifact_id": artifact_id,
                    "record_id": record.record_id,
                    "source": record.source,
                    "reason": record.reason,
                    "replayed_at": utc_now(drop_microseconds=True)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "result": replay_result,
                },
                ArtifactWriteOptions(
                    kind="fabric.quarantine_reprocess_result",
                    media_type="application/json",
                    schema=_QUARANTINE_REPROCESS_SCHEMA,
                    inputs=[
                        InputRef(
                            artifact_id=_artifact_ref_from_str(artifact_id),
                            role="quarantine_record",
                        ),
                        *(
                            [
                                InputRef(
                                    artifact_id=_artifact_ref_from_str(record.raw_payload_ref),
                                    role="raw_payload",
                                )
                            ]
                            if record.raw_payload_ref
                            else []
                        ),
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
            )
            result_refs.append(str(replay_ref.artifact_id))
        except Exception:
            failed_record_ids.append(record.record_id)

    return QuarantineReprocessResult(
        attempted=len(candidates),
        succeeded=len(result_refs),
        failed=len(failed_record_ids),
        result_refs=tuple(result_refs),
        failed_record_ids=tuple(failed_record_ids),
    )


__all__ = [
    "QuarantineRecord",
    "QuarantineReport",
    "QuarantineReprocessResult",
    "build_quarantine_report",
    "list_quarantine_records",
    "load_quarantine_payload",
    "load_quarantine_record",
    "persist_quarantine_record",
    "quarantine_index_path",
    "register_quarantine_reprocessor",
    "reprocess_quarantine_records",
]
