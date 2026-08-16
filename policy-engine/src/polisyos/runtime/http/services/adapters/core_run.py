"""Adapts on-disk core run manifests and traces into runtime service records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.run.context import recover_pending_run_finalize
from polisyos.core.run.manifest import RunManifest as CoreRunManifest
from polisyos.core.trace.record import RunTerminality, TraceRecord

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime
    from pathlib import Path

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore

logger = get_logger(__name__)

_RUN_MANIFEST_KIND = "core.run_manifest"
_RUN_MANIFEST_MEDIA_TYPE = "application/json"
_RUN_MANIFEST_SCHEMA_NAME = "polisyos.core.RunManifest"
_RUN_MANIFEST_SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True)
class CoreRunAdapterResult:
    """Normalized view of one core run as exposed through runtime HTTP services."""

    run_id: str
    status: str
    run_terminality: RunTerminality
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    tenant_id: str | None
    cell_id: str | None
    execution_profile: str | None
    control_job_id: str | None
    capability_manifest_ref: ArtifactRef | None
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
    store: ArtifactStore,
    run_dir: Path,
) -> CoreRunAdapterResult | None:
    """Load core run."""
    recover_pending_run_finalize(store, run_dir)
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.exists():
        return None

    run_id: str | None = None
    warnings: list[str] = []
    run_terminality = RunTerminality.NOT_ESTABLISHED
    terminality_conflicted = False
    finalized_without_fact = False
    trace_started_at: datetime | None = None
    trace_tenant_id: str | None = None
    trace_cell_id: str | None = None
    latest_manifest_ref: ArtifactRef | None = None
    terminal_manifest_ref: ArtifactRef | None = None
    manifest: CoreRunManifest | None = None

    for line in _iter_trace_lines(trace_path):
        try:
            record = TraceRecord.model_validate_json(line)
        except (TypeError, ValueError) as exc:
            logger.debug("Failed to validate trace record from %s: %s", trace_path, exc)
            if "core_run_trace_record_invalid" not in warnings:
                warnings.append("core_run_trace_record_invalid")
            run_terminality = RunTerminality.NOT_ESTABLISHED
            terminality_conflicted = True
            continue
        if record.phase == "core" and record.event == "RUN_STARTED":
            if run_id is None:
                run_id = record.run_id
                trace_started_at = record.ts
                trace_tenant_id = record.tenant_id
                trace_cell_id = record.cell_id
            elif (
                record.run_id != run_id
                or record.tenant_id != trace_tenant_id
                or record.cell_id != trace_cell_id
            ):
                if "core_run_trace_owner_identity_ambiguous" not in warnings:
                    warnings.append("core_run_trace_owner_identity_ambiguous")
                if "core_run_terminality_fact_conflict" not in warnings:
                    warnings.append("core_run_terminality_fact_conflict")
                run_terminality = RunTerminality.NOT_ESTABLISHED
                terminality_conflicted = True
                continue
        if run_id is None:
            if "core_run_trace_event_before_run_started" not in warnings:
                warnings.append("core_run_trace_event_before_run_started")
            run_terminality = RunTerminality.NOT_ESTABLISHED
            terminality_conflicted = True
            continue
        if record.run_id != run_id:
            if "core_run_trace_run_id_mismatch" not in warnings:
                warnings.append("core_run_trace_run_id_mismatch")
            run_terminality = RunTerminality.NOT_ESTABLISHED
            terminality_conflicted = True
            continue
        if (
            record.run_terminality is not None
            and record.phase == "core"
            and record.event in {"RUN_STARTED", "RUN_FINALIZED"}
            and (record.tenant_id != trace_tenant_id or record.cell_id != trace_cell_id)
        ):
            if "core_run_terminality_owner_scope_mismatch" not in warnings:
                warnings.append("core_run_terminality_owner_scope_mismatch")
            if "core_run_terminality_fact_conflict" not in warnings:
                warnings.append("core_run_terminality_fact_conflict")
            run_terminality = RunTerminality.NOT_ESTABLISHED
            terminality_conflicted = True
            continue
        run_terminality, terminality_conflicted, finalized_without_fact = (
            _admit_run_terminality(
                record,
                current=run_terminality,
                conflicted=terminality_conflicted,
                finalized_without_fact=finalized_without_fact,
                warnings=warnings,
            )
        )
        if record.phase != "core" or record.event != "RUN_FINALIZED":
            continue
        manifest_refs = [ref for ref in record.refs.outputs if ref.kind == _RUN_MANIFEST_KIND]
        if len(manifest_refs) == 1:
            latest_manifest_ref = manifest_refs[0]
        if (
            record.run_terminality is RunTerminality.TERMINAL
            and not terminality_conflicted
        ):
            candidate = _terminal_manifest_ref(record)
            if candidate is None or (
                terminal_manifest_ref is not None and terminal_manifest_ref != candidate
            ):
                if "core_run_terminal_manifest_ref_invalid" not in warnings:
                    warnings.append("core_run_terminal_manifest_ref_invalid")
                run_terminality = RunTerminality.NOT_ESTABLISHED
                terminality_conflicted = True
                continue
            terminal_manifest_ref = candidate

    if run_id is None:
        logger.debug("No RUN_STARTED identity found in trace %s", trace_path)
        return None

    manifest_ref = (
        terminal_manifest_ref
        if run_terminality is RunTerminality.TERMINAL
        else latest_manifest_ref
    )
    if manifest_ref is None:
        if run_terminality is RunTerminality.TERMINAL:
            warnings.append("core_run_terminal_manifest_ref_not_established")
            run_terminality = RunTerminality.NOT_ESTABLISHED
        warnings.append("core_run_manifest_ref_not_found_in_trace")
        return CoreRunAdapterResult(
            run_id=run_id,
            status="unknown",
            run_terminality=run_terminality,
            started_at=trace_started_at,
            finished_at=None,
            duration_ms=None,
            tenant_id=trace_tenant_id,
            cell_id=trace_cell_id,
            execution_profile=None,
            control_job_id=None,
            capability_manifest_ref=None,
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
        if run_terminality is RunTerminality.TERMINAL:
            manifest = _load_bound_terminal_manifest(
                store=store,
                manifest_ref=manifest_ref,
                run_id=run_id,
                tenant_id=trace_tenant_id,
                cell_id=trace_cell_id,
            )
        else:
            payload = from_canonical_bytes(store.get_bytes(manifest_ref.artifact_id))
            manifest = CoreRunManifest.model_validate(payload)
    except Exception as exc:  # terminal authority fails closed on any store/validation failure
        logger.debug("Failed to load core run manifest %s: %s", manifest_ref, exc)
        warnings.append(f"core_run_manifest_load_failed:{type(exc).__name__}")
        run_terminality = RunTerminality.NOT_ESTABLISHED
        return CoreRunAdapterResult(
            run_id=run_id,
            status="unknown",
            run_terminality=run_terminality,
            started_at=trace_started_at,
            finished_at=None,
            duration_ms=None,
            tenant_id=trace_tenant_id,
            cell_id=trace_cell_id,
            execution_profile=None,
            control_job_id=None,
            capability_manifest_ref=None,
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

    if manifest.run_id != run_id:
        warnings.append("core_run_manifest_owner_identity_mismatch")
        run_terminality = RunTerminality.NOT_ESTABLISHED
        return CoreRunAdapterResult(
            run_id=run_id,
            status="unknown",
            run_terminality=run_terminality,
            started_at=trace_started_at,
            finished_at=None,
            duration_ms=None,
            tenant_id=trace_tenant_id,
            cell_id=trace_cell_id,
            execution_profile=None,
            control_job_id=None,
            capability_manifest_ref=None,
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
        run_terminality=run_terminality,
        started_at=manifest.started_at,
        finished_at=manifest.finished_at,
        duration_ms=duration_ms,
        tenant_id=manifest.tenant_id,
        cell_id=manifest.cell_id,
        execution_profile=manifest.execution_profile,
        control_job_id=manifest.control_job_id,
        capability_manifest_ref=manifest.capability_manifest_ref,
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


def _terminal_manifest_ref(record: TraceRecord) -> ArtifactRef | None:
    refs = [ref for ref in record.refs.outputs if ref.kind == _RUN_MANIFEST_KIND]
    if len(refs) != 1:
        return None
    ref = refs[0]
    if ref.media_type != _RUN_MANIFEST_MEDIA_TYPE:
        return None
    return ref


def _load_bound_terminal_manifest(
    *,
    store: ArtifactStore,
    manifest_ref: ArtifactRef,
    run_id: str,
    tenant_id: str | None,
    cell_id: str | None,
) -> CoreRunManifest:
    """Resolve and content-bind the manifest carried by an owner terminal event."""
    if (
        manifest_ref.kind != _RUN_MANIFEST_KIND
        or manifest_ref.media_type != _RUN_MANIFEST_MEDIA_TYPE
    ):
        raise ValueError("terminal run manifest ref metadata mismatch")
    verification = store.verify(manifest_ref.artifact_id)
    if not verification.ok:
        raise ValueError("terminal run manifest failed CAS verification")
    artifact_manifest = store.get_manifest(manifest_ref.artifact_id)
    if (
        artifact_manifest.kind != manifest_ref.kind
        or artifact_manifest.media_type != manifest_ref.media_type
    ):
        raise ValueError("terminal run manifest sidecar metadata mismatch")
    schema = artifact_manifest.artifact_schema
    if (
        schema is None
        or schema.name != _RUN_MANIFEST_SCHEMA_NAME
        or schema.version != _RUN_MANIFEST_SCHEMA_VERSION
    ):
        raise ValueError("terminal run manifest schema provenance mismatch")

    payload = from_canonical_bytes(store.get_bytes(manifest_ref.artifact_id))
    manifest = CoreRunManifest.model_validate(payload)
    if (
        manifest.run_id != run_id
        or manifest.tenant_id != tenant_id
        or manifest.cell_id != cell_id
    ):
        raise ValueError("terminal run manifest owner identity mismatch")
    if artifact_manifest.producer != manifest.producer or artifact_manifest.env != manifest.env:
        raise ValueError("terminal run manifest producer provenance mismatch")
    if len(artifact_manifest.inputs) != 1:
        raise ValueError("terminal run manifest lineage mismatch")
    registry_input = artifact_manifest.inputs[0]
    if (
        registry_input.role != "registry_bundle"
        or registry_input.artifact_id != manifest.registry_bundle.artifact_id
    ):
        raise ValueError("terminal run manifest registry binding mismatch")
    return manifest


def _admit_run_terminality(
    record: TraceRecord,
    *,
    current: RunTerminality,
    conflicted: bool,
    finalized_without_fact: bool,
    warnings: list[str],
) -> tuple[RunTerminality, bool, bool]:
    """Admit producer lifecycle facts without interpreting status or timestamps."""
    observed = record.run_terminality
    if observed is None:
        if (
            record.phase == "core"
            and record.event == "RUN_FINALIZED"
            and current is not RunTerminality.TERMINAL
        ):
            if not finalized_without_fact:
                warnings.append("core_run_finalized_without_terminality")
            return RunTerminality.NOT_ESTABLISHED, conflicted, True
        return current, conflicted, finalized_without_fact
    expected = (
        {
            "RUN_STARTED": RunTerminality.NON_TERMINAL,
            "RUN_FINALIZED": RunTerminality.TERMINAL,
        }.get(record.event)
        if record.phase == "core"
        else None
    )
    if conflicted or expected is not observed:
        if not conflicted:
            warnings.append("core_run_terminality_fact_conflict")
        return RunTerminality.NOT_ESTABLISHED, True, finalized_without_fact
    if observed is RunTerminality.NON_TERMINAL and (
        current is RunTerminality.TERMINAL or finalized_without_fact
    ):
        warnings.append("core_run_terminality_fact_regression")
        return RunTerminality.NOT_ESTABLISHED, True, finalized_without_fact
    return observed, False, False


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


def _iter_trace_lines(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield stripped
