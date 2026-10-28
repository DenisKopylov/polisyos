"""Adapts on-disk core run manifests and traces into runtime service records."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.common.logger import get_logger
from polisyos.core.artifacts import read_core_json_artifact, read_core_manifest_profile
from polisyos.core.canon import content_hash
from polisyos.core.run.context import recover_pending_run_finalize
from polisyos.core.run.manifest import RunManifest as CoreRunManifest
from polisyos.core.trace import RunTerminality, TraceRecord

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord

logger = get_logger(__name__)

_RUN_MANIFEST_KIND = "core.run_manifest"
_RUN_MANIFEST_MEDIA_TYPE = "application/json"
_RUN_MANIFEST_SCHEMA_NAME = "polisyos.core.RunManifest"
_RUN_MANIFEST_SCHEMA_VERSION = "0.1.0"
BOUND_RUN_MANIFEST_SCHEMA_VERSION = _RUN_MANIFEST_SCHEMA_VERSION


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
    root_input_artifacts: tuple[ArtifactRef, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class TerminalCoreRunSource:
    """Strict terminal-trace resolution for one direct child of a trusted root."""

    run_id: str
    tenant_id: str | None
    cell_id: str | None
    run_dir: Path
    trace_path: Path
    manifest_ref: ArtifactRef
    manifest: CoreRunManifest
    workflow_finalization_ref: ArtifactRef | None = None


def derive_core_run_dir(core_runs_root: Path, run_id: str) -> Path:
    """Return the exact direct run child, rejecting traversal and normalization aliases."""

    _validate_direct_child_run_id(run_id)
    trusted_root = core_runs_root.resolve()
    candidate = (trusted_root / run_id).resolve()
    if candidate.parent != trusted_root or candidate.name != run_id:
        raise ValueError("run_id normalized outside the trusted Core-run root")
    return candidate


def derive_control_job_core_run_id(*, job_id: str, control_run_id: str, attempt: int) -> str:
    """Derive one collision-resistant Core identity for a leased control-job attempt.

    The control-plane run ID remains stable across retries. Core traces are
    append-only, so each lease attempt receives a distinct child identity and
    is selected only by that attempt's fenced completed-job progress.
    """
    if (
        not isinstance(job_id, str)
        or not job_id.strip()
        or not isinstance(control_run_id, str)
        or not control_run_id.strip()
        or isinstance(attempt, bool)
        or not isinstance(attempt, int)
        or attempt < 1
    ):
        raise ValueError("control_job_core_run_identity_invalid")
    identity = "\0".join((job_id, control_run_id, str(attempt))).encode("utf-8")
    return "control-" + hashlib.sha256(identity).hexdigest()


def load_completed_control_job_core_run_source(
    *,
    store: ArtifactStore,
    core_runs_root: Path,
    job: ControlJobRecord,
    expected_control_run_id: str,
    tenant_id: str,
    cell_id: str,
    read_attempts: list[str] | None = None,
) -> TerminalCoreRunSource:
    """Join one completed stable control run to its exact lease-attempt Core trace.

    The completed control row owns the attempt pointer. The Core manifest must
    independently bind back to that job and match the full persisted artifact
    reference, tenant, and cell before a consumer reads any Core output.
    """
    from collections.abc import Mapping

    from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key

    run_id = getattr(job, "run_id", None)
    job_id = getattr(job, "job_id", None)
    attempt = getattr(job, "attempt", None)
    progress = getattr(job, "progress", None)
    if (
        getattr(job, "state", None) != "completed"
        or getattr(job, "kind", None) != "natural_language_run"
        or not isinstance(job_id, str)
        or not isinstance(run_id, str)
        or run_id != expected_control_run_id
        or isinstance(attempt, bool)
        or not isinstance(attempt, int)
        or not isinstance(progress, Mapping)
        or progress.get("state") != "completed"
        or progress.get("phase") != "natural_language_run"
        or progress.get("run_id") != run_id
        or type(progress.get("core_run_attempt")) is not int
        or progress.get("core_run_attempt") != attempt
    ):
        raise ValueError("control_job_core_run_source_not_completed")
    core_run_id = derive_control_job_core_run_id(
        job_id=job_id,
        control_run_id=run_id,
        attempt=attempt,
    )
    if progress.get("core_run_id") != core_run_id:
        raise ValueError("control_job_core_run_attempt_pointer_mismatch")
    raw_manifest_ref = progress.get("core_manifest_artifact_ref")
    try:
        selected_manifest_ref = ArtifactRef.model_validate(raw_manifest_ref)
    except (TypeError, ValueError) as exc:
        raise ValueError("control_job_core_run_manifest_ref_not_established") from exc
    if progress.get("manifest_ref") != str(selected_manifest_ref.artifact_id):
        raise ValueError("control_job_core_run_manifest_pointer_mismatch")
    terminal = load_terminal_core_run_source(
        store=store,
        core_runs_root=core_runs_root,
        run_id=core_run_id,
        read_attempts=read_attempts,
    )
    if (
        terminal.run_id != core_run_id
        or terminal.manifest.run_id != core_run_id
        or terminal.manifest.status != "ok"
        or terminal.manifest.control_job_id != job_id
        or terminal.tenant_id != tenant_id
        or terminal.cell_id != cell_id
        or terminal.manifest.tenant_id != tenant_id
        or terminal.manifest.cell_id != cell_id
        or artifact_ref_identity_key(terminal.manifest_ref)
        != artifact_ref_identity_key(selected_manifest_ref)
    ):
        raise ValueError("control_job_core_run_terminal_binding_mismatch")
    return terminal


def _validate_direct_child_run_id(run_id: str) -> None:
    """Reject any run identifier that cannot be one descriptor-relative child."""

    if not isinstance(run_id, str) or not run_id or run_id != run_id.strip():
        raise ValueError("run_id must be a non-empty normalized direct-child name")
    if run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
        raise ValueError("run_id must not contain path separators or dot segments")
    run_path = Path(run_id)
    if run_path.is_absolute() or len(run_path.parts) != 1:
        raise ValueError("run_id must name one direct child of core_runs_root")


def load_terminal_core_run_source(
    *,
    store: ArtifactStore,
    core_runs_root: Path,
    run_id: str,
    read_attempts: list[str] | None = None,
) -> TerminalCoreRunSource:
    """Resolve one terminal Core source without recovery, scanning, or index facts."""

    _validate_direct_child_run_id(run_id)
    trusted_root = core_runs_root.absolute()
    run_dir = trusted_root / run_id
    trace_path = run_dir / "trace.jsonl"
    try:
        strict_lines = list(
            _iter_strict_terminal_trace_lines(trusted_root, run_id, read_attempts=read_attempts)
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("terminal Core run trace intake is invalid") from exc
    try:
        records = [_parse_trace_record(line) for line in strict_lines]
    except (TypeError, ValueError) as exc:
        raise ValueError("terminal Core run trace record is invalid") from exc
    if not records:
        raise ValueError("terminal Core run trace is empty")
    started = [
        record for record in records if record.phase == "core" and record.event == "RUN_STARTED"
    ]
    if len(started) != 1 or records[0] is not started[0]:
        raise ValueError("terminal Core run requires one leading RUN_STARTED owner fact")
    owner = started[0]
    if owner.run_terminality is not RunTerminality.NON_TERMINAL:
        raise ValueError("RUN_STARTED does not carry the non-terminal lifecycle fact")
    if owner.run_id != run_id:
        raise ValueError("RUN_STARTED owner does not match the requested run_id")
    for record in records:
        if (
            record.run_id != owner.run_id
            or record.tenant_id != owner.tenant_id
            or record.cell_id != owner.cell_id
        ):
            raise ValueError("terminal Core trace owner scope is ambiguous")
    finalized = [
        record for record in records if record.phase == "core" and record.event == "RUN_FINALIZED"
    ]
    if len(finalized) != 1 or records[-1] is not finalized[0]:
        raise ValueError("terminal Core run requires one final RUN_FINALIZED fact")
    if any(record.run_terminality is RunTerminality.TERMINAL for record in records[:-1]):
        raise ValueError("terminal Core trace has an intermediate terminal fact")
    terminal = finalized[0]
    if terminal.run_terminality is not RunTerminality.TERMINAL:
        raise ValueError("RUN_FINALIZED does not carry the terminal lifecycle fact")
    manifest_ref = _terminal_manifest_ref(terminal)
    if manifest_ref is None:
        raise ValueError("terminal Core run manifest reference is invalid")
    manifest = load_bound_terminal_manifest(
        store=store,
        manifest_ref=manifest_ref,
        run_id=owner.run_id,
        tenant_id=owner.tenant_id,
        cell_id=owner.cell_id,
    )
    workflow_finalization_ref: ArtifactRef | None = None
    if len(terminal.refs.inputs) == 1:
        candidate = terminal.refs.inputs[0]
        if (
            candidate.kind == "scientist.workflow_state_finalization"
            and candidate.media_type == "application/json"
            and candidate.manifest_profile_sha256 is not None
            and sum(ref == candidate for ref in manifest.outputs) == 1
        ):
            workflow_finalization_ref = candidate
    return TerminalCoreRunSource(
        run_id=owner.run_id,
        tenant_id=owner.tenant_id,
        cell_id=owner.cell_id,
        run_dir=run_dir,
        trace_path=trace_path,
        manifest_ref=manifest_ref,
        manifest=manifest,
        workflow_finalization_ref=workflow_finalization_ref,
    )


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
    terminal_has_inputs = False
    trace_started_at: datetime | None = None
    trace_tenant_id: str | None = None
    trace_cell_id: str | None = None
    latest_manifest_ref: ArtifactRef | None = None
    terminal_manifest_ref: ArtifactRef | None = None
    manifest: CoreRunManifest | None = None

    for line in _iter_trace_lines(trace_path):
        try:
            record = _parse_trace_record(line)
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
        run_terminality, terminality_conflicted, finalized_without_fact = _admit_run_terminality(
            record,
            current=run_terminality,
            conflicted=terminality_conflicted,
            finalized_without_fact=finalized_without_fact,
            warnings=warnings,
        )
        if record.phase != "core" or record.event != "RUN_FINALIZED":
            continue
        manifest_refs = [ref for ref in record.refs.outputs if ref.kind == _RUN_MANIFEST_KIND]
        if len(manifest_refs) == 1:
            latest_manifest_ref = manifest_refs[0]
        if record.run_terminality is RunTerminality.TERMINAL and not terminality_conflicted:
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
            terminal_has_inputs = bool(record.refs.inputs)

    if run_id is None:
        logger.debug("No RUN_STARTED identity found in trace %s", trace_path)
        return None

    manifest_ref = (
        terminal_manifest_ref if run_terminality is RunTerminality.TERMINAL else latest_manifest_ref
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
            manifest = load_bound_terminal_manifest(
                store=store,
                manifest_ref=manifest_ref,
                run_id=run_id,
                tenant_id=trace_tenant_id,
                cell_id=trace_cell_id,
            )
        else:
            payload = read_core_json_artifact(store, manifest_ref).value
            manifest = CoreRunManifest.model_validate(payload)
    except CanonicalProfileRefusalError:
        raise
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
    if run_terminality is RunTerminality.TERMINAL:
        has_finalization_output = any(
            ref.kind == "scientist.workflow_state_finalization" for ref in manifest.outputs
        )
        if terminal_has_inputs or has_finalization_output:
            try:
                (
                    experiment_state_ref,
                    workflow_report_ref,
                    tenant_manifest_scope_missing,
                ) = _terminal_workflow_output_refs(
                    store=store,
                    run_dir=run_dir,
                    run_id=run_id,
                    tenant_id=trace_tenant_id,
                    cell_id=trace_cell_id,
                    expected_manifest_ref=manifest_ref,
                )
                if tenant_manifest_scope_missing:
                    warnings.append("core_run_finalization_manifest_tenant_not_established")
            except (OSError, RuntimeError, TypeError, ValueError):
                # A recorded but unverifiable finalization must never fall back to
                # the earlier state merely because its kind appears first.
                experiment_state_ref = None
                workflow_report_ref = None
                warnings.append("core_run_workflow_finalization_unavailable")
        else:
            # Legacy runs remain inspectable as candidate history. They do not
            # establish that any same-kind output was the finalizer selection.
            warnings.append("core_run_workflow_finalization_not_established")
    else:
        warnings.append("core_run_workflow_finalization_not_established")
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
        root_input_artifacts=tuple(manifest.inputs),
        workflow_report_ref=workflow_report_ref,
        experiment_state_ref=experiment_state_ref,
        decision_packet_ref=decision_packet_ref,
        trace_path=trace_path,
        warnings=tuple(warnings),
        errors=tuple(manifest.errors),
    )


def _terminal_workflow_output_refs(
    *,
    store: ArtifactStore,
    run_dir: Path,
    run_id: str,
    tenant_id: str | None,
    cell_id: str | None,
    expected_manifest_ref: ArtifactRef,
) -> tuple[ArtifactRef, ArtifactRef, bool]:
    """Select workflow refs through the real terminal owner's bounded receipt.

    This is an output-selection check, not a source-currentness decision or an
    assertion that all upstream reads were observed. The exact finalization
    contract remains owned by ``WorkflowStateFinalization``.
    """
    from polisyos.core.artifacts import read_core_json_artifact_bounded
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
    from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, artifact_ref_identity_key
    from polisyos.core.artifacts.protocol import (
        CoreJSONArtifactBoundedMemberReader,
        matches_runtime_protocol,
    )
    from polisyos.scientist.orchestration.engine.finalization import (
        FINAL_WORKFLOW_REPORT_STATE_PATH,
        FINALIZATION_KIND,
        FINALIZATION_OUTPUT_KINDS,
        FINALIZATION_SCHEMA_NAME,
        FINALIZATION_SCHEMA_VERSION,
        WorkflowStateFinalization,
    )
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    if not matches_runtime_protocol(store, CoreJSONArtifactBoundedMemberReader):
        raise ValueError("workflow_finalization_bounded_reader_unavailable")
    terminal = load_terminal_core_run_source(
        store=store,
        core_runs_root=run_dir.parent,
        run_id=run_id,
    )
    if (
        terminal.tenant_id != tenant_id
        or terminal.cell_id != cell_id
        or terminal.manifest_ref != expected_manifest_ref
        or terminal.workflow_finalization_ref is None
    ):
        raise ValueError("workflow_finalization_terminal_owner_mismatch")

    # One shared aggregate budget over receipt, spec, final state and report.
    # Reserve two maximal manifest reads for each next payload to avoid an
    # over-budget read before the observer can account it.
    remaining = 8 * 1024 * 1024
    manifest_limit = 65_536
    tenant_manifest_scope_missing = False

    def read_view(ref: ArtifactRef, *, kind: str, schema_name: str, schema_version: str) -> object:
        nonlocal remaining, tenant_manifest_scope_missing
        if (
            type(ref) is not ArtifactRef
            or ref.manifest_profile_sha256 is None
            or ref.kind != kind
            or ref.media_type != "application/json"
            or remaining <= 2 * manifest_limit
        ):
            raise ValueError("workflow_finalization_selected_ref_invalid")
        limits = CoreJsonReadLimits(
            max_bytes=remaining - 2 * manifest_limit,
            max_depth=64,
            max_elements=200_000,
            max_manifest_bytes=manifest_limit,
        )
        bounded = read_core_json_artifact_bounded(store, ref, limits=limits)
        observed = bounded.observed_source_bytes
        if type(observed) is not int or observed < 0 or observed > remaining:
            raise ValueError("workflow_finalization_read_budget_invalid")
        remaining -= observed
        if (
            bounded.effective_ref != ref
            or bounded.manifest.kind != kind
            or bounded.manifest.media_type != "application/json"
            or bounded.manifest.artifact_schema
            != SchemaInfo(name=schema_name, version=schema_version)
        ):
            raise ValueError("workflow_finalization_selected_manifest_mismatch")
        context = bounded.manifest.tenant_context
        if context is not None and (context.tenant_id != tenant_id or context.cell_id != cell_id):
            raise ValueError("workflow_finalization_selected_tenant_mismatch")
        if context is None and tenant_id is not None:
            tenant_manifest_scope_missing = True
        value = bounded.value
        if not isinstance(value, dict) or value.get("schema_version") != schema_version:
            raise ValueError("workflow_finalization_payload_schema_mismatch")
        return value

    def require_one(ref: ArtifactRef, candidates: list[ArtifactRef], *, kind: str) -> None:
        if (
            ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            or sum(
                artifact_ref_identity_key(item) == artifact_ref_identity_key(ref)
                for item in candidates
            )
            != 1
        ):
            raise ValueError("workflow_finalization_selected_ref_not_owner_linked")

    receipt_ref = terminal.workflow_finalization_ref
    receipt = WorkflowStateFinalization.model_validate(
        read_view(
            receipt_ref,
            kind=FINALIZATION_KIND,
            schema_name=FINALIZATION_SCHEMA_NAME,
            schema_version=FINALIZATION_SCHEMA_VERSION,
        )
    )
    if receipt.run_id != run_id:
        raise ValueError("workflow_finalization_run_mismatch")
    require_one(receipt.workflow_spec_ref, terminal.manifest.inputs, kind="scientist.workflow_spec")
    spec = WorkflowSpec.model_validate(
        read_view(
            receipt.workflow_spec_ref,
            kind="scientist.workflow_spec",
            schema_name="polisyos.scientist.orchestration.engine.WorkflowSpec",
            schema_version="1.0",
        )
    )
    if spec.workflow_id != receipt.workflow_id:
        raise ValueError("workflow_finalization_spec_mismatch")
    require_one(
        receipt.prior_state_ref, terminal.manifest.outputs, kind="scientist.experiment_state"
    )
    require_one(
        receipt.final_state_ref, terminal.manifest.outputs, kind="scientist.experiment_state"
    )

    bindings = {item.state_path: item.artifact_ref for item in receipt.output_bindings}
    if (
        len(bindings) != len(receipt.output_bindings)
        or FINAL_WORKFLOW_REPORT_STATE_PATH not in bindings
        or set(bindings) - set(FINALIZATION_OUTPUT_KINDS)
    ):
        raise ValueError("workflow_finalization_output_bindings_invalid")
    for path, ref in bindings.items():
        require_one(ref, terminal.manifest.outputs, kind=FINALIZATION_OUTPUT_KINDS[path])

    prior_state = read_view(
        receipt.prior_state_ref,
        kind="scientist.experiment_state",
        schema_name="polisyos.scientist.orchestration.engine.ExperimentState",
        schema_version="1.3",
    )
    if not isinstance(prior_state, dict) or prior_state.get("run_id") != run_id:
        raise ValueError("workflow_finalization_prior_state_run_mismatch")

    # The index must read the final state's own recorded bindings, not infer them
    # from another same-kind artifact or from a receipt marker alone.
    final_state = read_view(
        receipt.final_state_ref,
        kind="scientist.experiment_state",
        schema_name="polisyos.scientist.orchestration.engine.ExperimentState",
        schema_version="1.3",
    )
    if not isinstance(final_state, dict) or final_state.get("run_id") != run_id:
        raise ValueError("workflow_finalization_state_run_mismatch")
    for path, ref in bindings.items():
        section, key = path.split(".", 1)
        mapping = final_state.get(section)
        if not isinstance(mapping, dict):
            raise ValueError("workflow_finalization_state_binding_missing")
        try:
            state_ref = ArtifactRef.model_validate(mapping[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("workflow_finalization_state_binding_invalid") from exc
        if artifact_ref_identity_key(state_ref) != artifact_ref_identity_key(ref):
            raise ValueError("workflow_finalization_state_binding_mismatch")

    report_ref = bindings[FINAL_WORKFLOW_REPORT_STATE_PATH]
    report = read_view(
        report_ref,
        kind="scientist.workflow_report",
        schema_name="polisyos.scientist.orchestration.engine.WorkflowReport",
        schema_version="1.0",
    )
    if (
        not isinstance(report, dict)
        or report.get("run_id") != run_id
        or report.get("workflow_id") != receipt.workflow_id
    ):
        raise ValueError("workflow_finalization_report_identity_mismatch")
    return receipt.final_state_ref, report_ref, tenant_manifest_scope_missing


def _terminal_manifest_ref(record: TraceRecord) -> ArtifactRef | None:
    refs = [ref for ref in record.refs.outputs if ref.kind == _RUN_MANIFEST_KIND]
    if len(refs) != 1:
        return None
    ref = refs[0]
    if ref.media_type != _RUN_MANIFEST_MEDIA_TYPE:
        return None
    return ref


def load_bound_terminal_manifest(
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
    verification = store.verify(manifest_ref)
    if not verification.ok:
        raise ValueError("terminal run manifest failed CAS verification")
    artifact_manifest = read_core_manifest_profile(store, manifest_ref)[0]
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

    manifest_bytes = store.get_bytes(manifest_ref)
    if content_hash(manifest_bytes, prefix=True) != str(manifest_ref.artifact_id):
        raise ValueError("terminal run manifest bytes do not match the bound artifact id")
    payload = read_core_json_artifact(store, manifest_ref, raw_payload_bytes=manifest_bytes).value
    manifest = CoreRunManifest.model_validate(payload)
    if manifest.run_id != run_id or manifest.tenant_id != tenant_id or manifest.cell_id != cell_id:
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


def _iter_strict_terminal_trace_lines(
    core_runs_root: Path,
    run_id: str,
    *,
    read_attempts: list[str] | None = None,
) -> Iterator[str]:
    """Open the exact run child and trace leaf relative to trusted descriptors."""

    no_follow = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(no_follow, int):
        raise ValueError("terminal Core run trace no-follow intake is unavailable")
    directory_only = getattr(os, "O_DIRECTORY", None)
    if not isinstance(directory_only, int):
        raise ValueError("terminal Core run directory-only intake is unavailable")
    directory_flags = os.O_RDONLY | directory_only | no_follow
    root_fd: int | None = None
    run_fd: int | None = None
    trace_fd: int | None = None
    try:
        root_fd = os.open(core_runs_root, directory_flags)
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise ValueError("trusted Core run root is not a directory")
        run_fd = os.open(run_id, directory_flags, dir_fd=root_fd)
        if not stat.S_ISDIR(os.fstat(run_fd).st_mode):
            raise ValueError("terminal Core run child is not a directory")
        trace_fd = os.open(
            "trace.jsonl",
            os.O_RDONLY | no_follow,
            dir_fd=run_fd,
        )
        if not stat.S_ISREG(os.fstat(trace_fd).st_mode):
            raise ValueError("terminal Core run trace leaf is not a regular file")
        with os.fdopen(trace_fd, "r", encoding="utf-8") as handle:
            trace_fd = None
            if read_attempts is not None:
                read_attempts.append(f"terminal_trace:{core_runs_root / run_id / 'trace.jsonl'}")
            for line in handle:
                stripped = line.strip()
                if stripped:
                    yield stripped
    finally:
        if trace_fd is not None:
            os.close(trace_fd)
        if run_fd is not None:
            os.close(run_fd)
        if root_fd is not None:
            os.close(root_fd)


def _parse_trace_record(line: str) -> TraceRecord:
    """Parse one trace record for both tolerant indexing and strict resolution."""

    return TraceRecord.model_validate_json(line)
