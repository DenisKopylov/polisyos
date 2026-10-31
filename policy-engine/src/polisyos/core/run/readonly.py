"""Read terminal Core owner facts without acquiring or reconstructing a writer.

These facts establish persisted run ownership and exact artifact selections. They
do not appoint an implementation, authorize a consumer, or grant a new run lease.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from polisyos.core.artifacts import ArtifactRef, ArtifactStore, load_core_json_artifact
from polisyos.core.artifacts.manifest import artifact_ref_identity_key
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.run.context import (
    RunContext,
    _read_run_owner_records,
    _run_invocation_attempt_chain,
    _RunInvocationAttempt,
    _validate_terminal_run_manifest_ref,
    _validate_worker_receipt_history,
)
from polisyos.core.run.manifest import RunManifest
from polisyos.core.trace import RunTerminality, TraceRecord


class TerminalRunSourceError(ValueError):
    """The selected terminal run is not established by actual Core owner facts."""


@dataclass(frozen=True)
class _TerminalFacts:
    manifest: RunManifest
    records: tuple[TraceRecord, ...]
    outputs: tuple[ArtifactRef, ...]
    invocation_tail: ArtifactRef | None


def _validate_trace_prefix(
    store: ArtifactStore, manifest: RunManifest, records: list[TraceRecord]
) -> None:
    """Reconcile the terminal manifest's actual persisted pre-finalization trace."""
    trace_ref = manifest.trace_ref
    if (
        trace_ref is None
        or trace_ref.kind != "core.trace.jsonl"
        or trace_ref.media_type != "application/jsonl"
        or not store.verify(trace_ref).ok
    ):
        raise TerminalRunSourceError("terminal_run_source_trace_artifact_not_established")
    stored_records = [
        TraceRecord.model_validate_json(line)
        for line in store.get_bytes(trace_ref).decode("utf-8").splitlines()
        if line.strip()
    ]
    if to_canonical_bytes(stored_records, CanonSpec()) != to_canonical_bytes(
        records[:-1], CanonSpec()
    ):
        raise TerminalRunSourceError("terminal_run_source_trace_prefix_mismatch")


@dataclass(frozen=True, slots=True)
class TerminalCoreRunSource:
    """An exact terminal selection, revalidated on each read and exposing no writer.

    Constructing this value does not appoint it: every operation independently
    replays the selected Core trace, snapshots, run manifest and output events.
    Expected scope values are equalities; ``None`` is never a wildcard.
    """

    _store: ArtifactStore
    _trace_path: Path
    _run_ref_parts: tuple[str, str, str, str]
    _expected_run_id: str
    _expected_tenant_id: str | None
    _expected_cell_id: str | None
    _expected_control_job_id: str | None

    @property
    def run_ref(self) -> ArtifactRef:
        """Return the selected terminal manifest identity as a detached value."""
        artifact_id, kind, media_type, profile = self._run_ref_parts
        return ArtifactRef(
            artifact_id=artifact_id,
            kind=kind,
            media_type=media_type,
            manifest_profile_sha256=profile,
        )

    @property
    def trace_path(self) -> Path:
        """Return the durable trace locator without creating an execution handle."""
        return self._trace_path

    @property
    def run_manifest(self) -> RunManifest:
        """Return terminal metadata only after fresh owner and scope reconciliation."""
        return self._read().manifest.model_copy(deep=True)

    def _read(self) -> _TerminalFacts:
        try:
            run_ref = self.run_ref
            manifest = RunManifest.model_validate(load_core_json_artifact(self._store, run_ref))
            if (
                manifest.run_id != self._expected_run_id
                or manifest.tenant_id != self._expected_tenant_id
                or manifest.cell_id != self._expected_cell_id
                or manifest.control_job_id != self._expected_control_job_id
            ):
                raise TerminalRunSourceError("terminal_run_source_scope_mismatch")
            if manifest.status == "running" or manifest.finished_at is None:
                raise TerminalRunSourceError("terminal_run_source_manifest_not_terminal")
            _validate_terminal_run_manifest_ref(
                self._store,
                run_manifest=manifest,
                run_ref=run_ref,
                require_selected_profile=True,
            )
            records, snapshot, _ = _read_run_owner_records(
                self._store, self._trace_path, run_id=manifest.run_id
            )
            _validate_worker_receipt_history(records)
            terminals = [
                record
                for record in records
                if record.phase == "core" and record.event == "RUN_FINALIZED"
            ]
            if (
                len(terminals) != 1
                or records[-1] is not terminals[0]
                or terminals[0].run_terminality is not RunTerminality.TERMINAL
                or any(record.run_terminality is RunTerminality.TERMINAL for record in records[:-1])
                or len(terminals[0].refs.outputs) != 1
                or artifact_ref_identity_key(terminals[0].refs.outputs[0])
                != artifact_ref_identity_key(run_ref)
            ):
                raise TerminalRunSourceError("terminal_run_source_terminal_fact_mismatch")
            _validate_trace_prefix(self._store, manifest, records)
            inputs, outputs = RunContext._owner_refs_from_records(records)
            terminal_inputs = terminals[0].refs.inputs
            if len(terminal_inputs) > 1 or (
                terminal_inputs
                and (
                    terminal_inputs[0].manifest_profile_sha256 is None
                    or artifact_ref_identity_key(terminal_inputs[0])
                    not in {artifact_ref_identity_key(ref) for ref in outputs}
                )
            ):
                raise TerminalRunSourceError(
                    "terminal_run_source_workflow_finalization_contract_invalid"
                )
            if tuple(map(artifact_ref_identity_key, inputs)) != tuple(
                map(artifact_ref_identity_key, manifest.inputs)
            ) or tuple(map(artifact_ref_identity_key, outputs)) != tuple(
                map(artifact_ref_identity_key, manifest.outputs)
            ):
                raise TerminalRunSourceError("terminal_run_source_owner_refs_mismatch")
            # Finalize changes these terminal fields and emits the manifest. All
            # remaining fields must still be the protected owner's actual facts.
            expected = snapshot.run_manifest.model_copy(
                update={
                    "status": manifest.status,
                    "errors": manifest.errors,
                    "finished_at": manifest.finished_at,
                    "trace_ref": manifest.trace_ref,
                    "inputs": list(inputs),
                    "outputs": list(outputs),
                },
                deep=True,
            )
            if to_canonical_bytes(expected, CanonSpec()) != to_canonical_bytes(
                manifest, CanonSpec()
            ):
                raise TerminalRunSourceError("terminal_run_source_manifest_owner_mismatch")
            return _TerminalFacts(
                manifest,
                tuple(records),
                outputs,
                getattr(snapshot, "runtime_invocation_tail_ref", None),
            )
        except TerminalRunSourceError:
            raise
        except (OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
            raise TerminalRunSourceError("terminal_run_source_not_established") from exc

    def read_runtime_owner_output_refs(self) -> tuple[ArtifactRef, ...]:
        """Read exactly the output events admitted by the terminal owner chain."""
        return tuple(ref.model_copy(deep=True) for ref in self._read().outputs)

    def read_runtime_invocation_attempts(self) -> list[_RunInvocationAttempt]:
        """Replay exact invocation bases and outcomes through the existing Core reader."""
        facts = self._read()
        return _run_invocation_attempt_chain(
            self._store, tail_ref=facts.invocation_tail, run_manifest=facts.manifest
        )

    def read_runtime_workflow_finalization_ref(self) -> ArtifactRef:
        """Read the single terminal workflow transition without interpreting its schema."""
        facts = self._read()
        terminal = facts.records[-1]
        if len(terminal.refs.inputs) != 1:
            raise TerminalRunSourceError("terminal_run_source_workflow_finalization_absent")
        selected = terminal.refs.inputs[0]
        if selected.manifest_profile_sha256 is None:
            raise TerminalRunSourceError(
                "terminal_run_source_workflow_finalization_profile_missing"
            )
        if artifact_ref_identity_key(selected) not in {
            artifact_ref_identity_key(ref) for ref in facts.outputs
        }:
            raise TerminalRunSourceError("terminal_run_source_workflow_finalization_unlinked")
        return selected.model_copy(deep=True)


def open_terminal_run_source(
    store: ArtifactStore,
    *,
    run_ref: ArtifactRef,
    trace_path: Path,
    expected_run_id: str,
    expected_tenant_id: str | None,
    expected_cell_id: str | None,
    expected_control_job_id: str | None,
) -> TerminalCoreRunSource:
    """Open an exact terminal run selected by an already authorized caller.

    Args:
        store: Existing CAS holding the selected owner and outcome artifacts.
        run_ref: Full-profile terminal manifest selected by the actual run owner.
        trace_path: Durable Core trace belonging to that selected run.
        expected_run_id: Actual current control record's run identity.
        expected_tenant_id: Authenticated expected tenant; ``None`` means unscoped.
        expected_cell_id: Authenticated expected cell; ``None`` means unscoped.
        expected_control_job_id: Actual current launching job, including explicit absence.

    Returns:
        A reader with no writer lease, lifecycle methods or mutation appointment.

    Raises:
        TerminalRunSourceError: Core does not establish the exact terminal selection.
    """
    if run_ref.manifest_profile_sha256 is None:
        raise TerminalRunSourceError("terminal_run_source_selected_profile_missing")
    source = TerminalCoreRunSource(
        store,
        Path(trace_path),
        (
            str(run_ref.artifact_id),
            run_ref.kind,
            run_ref.media_type,
            run_ref.manifest_profile_sha256,
        ),
        expected_run_id,
        expected_tenant_id,
        expected_cell_id,
        expected_control_job_id,
    )
    source._read()
    return source


__all__ = ["TerminalCoreRunSource", "TerminalRunSourceError", "open_terminal_run_source"]
