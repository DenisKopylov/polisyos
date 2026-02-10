from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.run.manifest import RunManifest as CoreRunManifest
from polisyos.core.trace.record import TraceRecord


@dataclass(frozen=True)
class CoreRunAdapterResult:
    run_id: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    tenant_id: str | None
    cell_id: str | None
    manifest_ref: ArtifactRef | None
    trace_ref: ArtifactRef | None
    root_artifacts: tuple[ArtifactRef, ...]
    workflow_report_ref: ArtifactRef | None
    experiment_state_ref: ArtifactRef | None
    decision_packet_ref: ArtifactRef | None
    trace_path: Path
    warnings: tuple[str, ...] = ()
    errors: tuple[dict[str, Any], ...] = ()


def load_core_run(
    *,
    store: FileSystemCAS,
    run_dir: Path,
) -> CoreRunAdapterResult | None:
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.exists():
        return None

    run_id = run_dir.name
    warnings: list[str] = []
    manifest_ref: ArtifactRef | None = None
    manifest: CoreRunManifest | None = None

    for line in _iter_trace_lines(trace_path):
        try:
            record = TraceRecord.model_validate_json(line)
        except Exception:
            continue
        if record.event != "RUN_FINALIZED":
            continue
        for ref in record.refs.outputs:
            if ref.kind == "core.run_manifest":
                manifest_ref = ref

    if manifest_ref is None:
        warnings.append("core_run_manifest_ref_not_found_in_trace")
        return CoreRunAdapterResult(
            run_id=run_id,
            status="unknown",
            started_at=None,
            finished_at=None,
            duration_ms=None,
            tenant_id=None,
            cell_id=None,
            manifest_ref=None,
            trace_ref=None,
            root_artifacts=(),
            workflow_report_ref=None,
            experiment_state_ref=None,
            decision_packet_ref=None,
            trace_path=trace_path,
            warnings=tuple(warnings),
            errors=(),
        )

    try:
        payload = from_canonical_bytes(store.get_bytes(manifest_ref.artifact_id))
        manifest = CoreRunManifest.model_validate(payload)
    except Exception as exc:
        warnings.append(f"core_run_manifest_load_failed:{type(exc).__name__}")
        return CoreRunAdapterResult(
            run_id=run_id,
            status="unknown",
            started_at=None,
            finished_at=None,
            duration_ms=None,
            tenant_id=None,
            cell_id=None,
            manifest_ref=manifest_ref,
            trace_ref=None,
            root_artifacts=(),
            workflow_report_ref=None,
            experiment_state_ref=None,
            decision_packet_ref=None,
            trace_path=trace_path,
            warnings=tuple(warnings),
            errors=(),
        )

    duration_ms = _duration_ms(manifest.started_at, manifest.finished_at)
    workflow_report_ref = _first_ref_by_kind(manifest.outputs, "scientist.workflow_report")
    experiment_state_ref = _first_ref_by_kind(manifest.outputs, "scientist.experiment_state")
    decision_packet_ref = _first_ref_by_kind(manifest.outputs, "scientist.decision_packet")

    return CoreRunAdapterResult(
        run_id=manifest.run_id,
        status=manifest.status,
        started_at=manifest.started_at,
        finished_at=manifest.finished_at,
        duration_ms=duration_ms,
        tenant_id=manifest.tenant_id,
        cell_id=manifest.cell_id,
        manifest_ref=manifest_ref,
        trace_ref=manifest.trace_ref,
        root_artifacts=tuple(manifest.outputs),
        workflow_report_ref=workflow_report_ref,
        experiment_state_ref=experiment_state_ref,
        decision_packet_ref=decision_packet_ref,
        trace_path=trace_path,
        warnings=tuple(warnings),
        errors=tuple(manifest.errors),
    )


def _first_ref_by_kind(refs: list[ArtifactRef], kind: str) -> ArtifactRef | None:
    for ref in refs:
        if ref.kind == kind:
            return ref
    return None


def _duration_ms(started_at: datetime | None, finished_at: datetime | None) -> int | None:
    if started_at is None or finished_at is None:
        return None
    delta = finished_at - started_at
    return max(int(delta.total_seconds() * 1000), 0)


def _iter_trace_lines(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield stripped

