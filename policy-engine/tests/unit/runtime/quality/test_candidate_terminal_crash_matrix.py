"""Durable candidate terminal intent controls using actual selected CAS views.

These tests cover the local intent boundary.  The terminal's parents are
component fixtures; they do not establish a protected candidate action, N5,
or the event/head transaction by themselves.
"""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.services.control.artifacts import (
    _recover_candidate_terminal_authority_artifact,
    write_authority_artifact,
)
from polisyos.runtime.http.services.control.run_lifecycle import AcquisitionRouteLoopAuthoritySink
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    _candidate_terminal_intent_for_publication,
    _read_candidate_terminal_intent,
    _write_candidate_terminal_intent,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from tests._helpers.candidate_terminal_recovery import candidate_terminal_writer_inputs


@pytest.fixture
def terminal(tmp_path: Path) -> AcquisitionCandidateRouteLoopReceipt:
    """Construct a blocked terminal with real selected but non-authoritative parents."""
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-intent", cell_id="cell-intent")

    def parent(kind: str, name: str):
        return cas.put_json(
            {"component_fixture": name},
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                producer=ProducerInfo(component="test.candidate-terminal-parent", version="1"),
            ),
            return_selected_profile=True,
        )

    action = parent("runtime_quality.acquisition_candidate_action_receipt", "action")
    decision = parent("runtime_quality.acquisition_evaluation_decision", "decision")
    basis = parent("runtime_quality.acquisition_evaluation_basis", "basis")
    reentry = parent("runtime_quality.candidate_source_reentry_receipt", "reentry")
    return AcquisitionCandidateRouteLoopReceipt(
        receipt_id="action-job.candidate-evaluation.terminal",
        tenant_id="tenant-intent",
        cell_id="cell-intent",
        run_id="run-intent",
        source_job_id="source-job",
        route_id="sha256:" + "a" * 64,
        action_generation=1,
        job_id="action-job",
        compiled_ref="sha256:" + "b" * 64,
        planner_report_hash="sha256:" + "c" * 64,
        cost_basis_hash="sha256:" + "d" * 64,
        decision_ref="sha256:" + "e" * 64,
        terminal_outcome="candidate_reentry_completed",
        predecessor_receipt_ref="sha256:" + "f" * 64,
        owner_receipt_refs=(str(action.artifact_id), str(decision.artifact_id)),
        candidate_action_ref=action,
        candidate_reentry_ref=reentry,
        evaluation_decision_ref=decision,
        selected_basis_ref=basis,
        selected_evaluation_witness_ref=reentry,
        generated_at=datetime(2026, 8, 28, 12, tzinfo=UTC),
    )


@pytest.fixture
def pending_terminal(
    tmp_path: Path, terminal: AcquisitionCandidateRouteLoopReceipt, monkeypatch: pytest.MonkeyPatch
):
    """Use real phase/event/head owners with only candidate selection adapted.

    The candidate-action parent is a test fixture, so the live route, lease,
    source and candidate frontier are not established by this fixture.
    """
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-intent", cell_id="cell-intent")
    db = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    events = RuntimeDiagnosticEventLog(store=db, artifact_store=cas)
    sink = AcquisitionRouteLoopAuthoritySink(artifact_store=cas, event_log=events, control_store=db)
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verified_current_action_outcome_ref",
        lambda _self, _executing, _ref, refs, **_kwargs: refs[0],
    )
    common = {
        name: getattr(terminal, name)
        for name in (
            "tenant_id",
            "cell_id",
            "run_id",
            "source_job_id",
            "route_id",
            "action_generation",
            "job_id",
            "compiled_ref",
            "planner_report_hash",
            "cost_basis_hash",
            "decision_ref",
        )
    }
    requested = AcquisitionRoutePhaseReceipt(
        **common,
        receipt_id="candidate.requested",
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        generated_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    first = sink.persist_phase(requested)
    executing = requested.model_copy(
        update={
            "receipt_id": "candidate.executing",
            "coarse_phase": "executing",
            "receipt_phase": "executing",
            "predecessor_receipt_ref": first.receipt_ref,
        }
    )
    second = sink.persist_phase(executing)
    selected = sink.persist_action_outcome_selection(
        second.receipt_ref,
        (str(terminal.candidate_action_ref.artifact_id),),
        candidate_receipt_ref=terminal.candidate_action_ref,
    )
    pending = AcquisitionRoutePhaseReceipt(
        **common,
        schema_version="AcquisitionRoutePhaseReceipt@1.2",
        receipt_id="candidate.pending",
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        predecessor_receipt_ref=selected.receipt_ref,
        owner_receipt_refs=(str(terminal.candidate_action_ref.artifact_id),),
        candidate_receipt_ref=terminal.candidate_action_ref,
        generated_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    head = sink.persist_phase(pending)
    actual = terminal.model_copy(
        update={
            "predecessor_receipt_ref": head.receipt_ref,
            "generated_at": pending.generated_at + timedelta(seconds=1),
        }
    )
    try:
        yield SimpleNamespace(cas=cas, db=db, events=events, sink=sink, head=head, terminal=actual)
    finally:
        db.close()


def _forbid_n5(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_n5(*_args: object, **_kwargs: object) -> object:
        pytest.fail("terminal intent recovery attempted to run N5")

    monkeypatch.setattr(JointSimulationPort, "__call__", no_n5)


def test_complete_terminal_intent_is_exclusive_and_retains_original_time(
    tmp_path: Path, terminal: AcquisitionCandidateRouteLoopReceipt
) -> None:
    marker = tmp_path / "terminal.started"
    assert _read_candidate_terminal_intent(marker) is None
    _write_candidate_terminal_intent(marker, terminal)
    first_bytes = marker.read_bytes()
    assert _read_candidate_terminal_intent(marker) == terminal

    replacement = terminal.model_copy(
        update={"generated_at": terminal.generated_at + timedelta(seconds=1)}
    )
    with pytest.raises(FileExistsError):
        _write_candidate_terminal_intent(marker, replacement)
    assert marker.read_bytes() == first_bytes
    assert _read_candidate_terminal_intent(marker).generated_at == terminal.generated_at


def test_marker_only_retry_reuses_original_terminal_without_running_n5(
    tmp_path: Path, terminal: AcquisitionCandidateRouteLoopReceipt, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete pre-event intent is selected without another numerical call."""
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-intent", cell_id="cell-intent")

    _forbid_n5(monkeypatch)
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    ) as db:
        events = RuntimeDiagnosticEventLog(store=db, artifact_store=cas)
        marker = tmp_path / "terminal.started"
        first = _candidate_terminal_intent_for_publication(
            marker=marker, expected=terminal, event_log=events, sink=object()
        )
        retry = terminal.model_copy(
            update={"generated_at": terminal.generated_at + timedelta(seconds=30)}
        )
        recovered = _candidate_terminal_intent_for_publication(
            marker=marker, expected=retry, event_log=events, sink=object()
        )
        assert first == recovered == terminal
        assert _read_candidate_terminal_intent(marker) == terminal
        assert events.list_events(run_id=terminal.run_id, job_id=terminal.job_id) == []


def test_marker_rejects_same_bytes_foreign_selected_profile(
    tmp_path: Path, terminal: AcquisitionCandidateRouteLoopReceipt
) -> None:
    """Equal CAS bytes do not substitute a different selected owner view."""
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-intent", cell_id="cell-intent")
    source = terminal.selected_basis_ref
    foreign = cas.put_bytes(
        cas.get_bytes(source),
        ArtifactWriteOptions(
            kind=source.kind,
            media_type=source.media_type,
            producer=ProducerInfo(component="test.foreign-candidate-owner", version="1"),
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == source.artifact_id
    assert foreign.manifest_profile_sha256 != source.manifest_profile_sha256
    marker = tmp_path / "terminal.started"
    _write_candidate_terminal_intent(marker, terminal)
    before = marker.read_bytes()
    altered = terminal.model_copy(update={"selected_basis_ref": foreign})
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    ) as db:
        events = RuntimeDiagnosticEventLog(store=db, artifact_store=cas)
        with pytest.raises(ValueError, match="candidate_evaluation_terminal_intent_changed"):
            _candidate_terminal_intent_for_publication(
                marker=marker, expected=altered, event_log=events, sink=object()
            )
        assert events.list_events(run_id=terminal.run_id, job_id=terminal.job_id) == []
    assert marker.read_bytes() == before


def test_event_only_and_both_recover_the_real_selected_terminal_without_n5(
    tmp_path: Path, pending_terminal: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recover the owner event's original bytes and time when the marker is absent."""
    case = pending_terminal
    _forbid_n5(monkeypatch)
    opts, fields = candidate_terminal_writer_inputs(case.terminal)
    written = _recover_candidate_terminal_authority_artifact(
        case.cas, case.events, case.terminal, opts, **fields
    )
    marker = tmp_path / "terminal.started"
    retry = case.terminal.model_copy(
        update={"generated_at": case.terminal.generated_at + timedelta(minutes=1)}
    )
    selected = _candidate_terminal_intent_for_publication(
        marker=marker, expected=retry, event_log=case.events, sink=case.sink
    )
    assert selected == case.terminal
    assert _read_candidate_terminal_intent(marker) == case.terminal
    assert (
        _candidate_terminal_intent_for_publication(
            marker=marker, expected=retry, event_log=case.events, sink=case.sink
        )
        == case.terminal
    )
    recovered, selected_ref = case.sink.recover_candidate_terminal(selected)
    assert recovered == case.terminal
    assert selected_ref == written.cas_ref
    assert case.sink.get_head(case.terminal) == case.head
    assert len(case.events.list_events(event_id=fields["event_id"], limit=2)) == 1


def test_saved_marker_repairs_real_artifact_before_event_once_without_n5(
    tmp_path: Path, pending_terminal: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The existing selected payload/event is appended once after a writer crash."""
    case = pending_terminal
    _forbid_n5(monkeypatch)
    marker = tmp_path / "terminal.started"
    _write_candidate_terminal_intent(marker, case.terminal)
    opts, fields = candidate_terminal_writer_inputs(case.terminal)
    interrupted = write_authority_artifact(
        case.cas, case.terminal.model_dump(mode="json"), opts, **fields
    )
    assert case.events.list_events(event_id=fields["event_id"], limit=2) == []
    saved = _candidate_terminal_intent_for_publication(
        marker=marker, expected=case.terminal, event_log=case.events, sink=case.sink
    )
    recovered = _recover_candidate_terminal_authority_artifact(
        case.cas, case.events, saved, opts, **fields
    )
    assert recovered.cas_ref == interrupted.cas_ref
    assert case.sink.recover_candidate_terminal(saved) == (saved, interrupted.cas_ref)
    repeated = _recover_candidate_terminal_authority_artifact(
        case.cas, case.events, saved, opts, **fields
    )
    assert repeated.cas_ref == interrupted.cas_ref
    assert len(case.events.list_events(event_id=fields["event_id"], limit=2)) == 1
    assert case.sink.get_head(case.terminal) == case.head


@pytest.mark.parametrize("payload", [b"", b"{", b"null", b"[]", b"{}"])
def test_incomplete_or_untyped_terminal_intent_refuses(tmp_path: Path, payload: bytes) -> None:
    marker = tmp_path / "terminal.started"
    marker.write_bytes(payload)
    with pytest.raises(ValueError, match="candidate_evaluation_terminal_intent_invalid"):
        _read_candidate_terminal_intent(marker)
    assert marker.read_bytes() == payload


def test_symlinked_terminal_intent_refuses_without_reading_target(
    tmp_path: Path, terminal: AcquisitionCandidateRouteLoopReceipt
) -> None:
    target = tmp_path / "other-action.started"
    _write_candidate_terminal_intent(target, terminal)
    marker = tmp_path / "terminal.started"
    marker.symlink_to(target)
    before = target.read_bytes()
    with pytest.raises((OSError, ValueError)):
        _read_candidate_terminal_intent(marker)
    assert target.read_bytes() == before


def test_hardlinked_terminal_intent_refuses(
    tmp_path: Path, terminal: AcquisitionCandidateRouteLoopReceipt
) -> None:
    marker = tmp_path / "terminal.started"
    _write_candidate_terminal_intent(marker, terminal)
    other = tmp_path / "other.started"
    other.hardlink_to(marker)
    with pytest.raises(ValueError, match="candidate_evaluation_terminal_intent_invalid"):
        _read_candidate_terminal_intent(marker)
    assert marker.read_bytes() == other.read_bytes()


def test_oversized_terminal_intent_refuses_without_replacement(tmp_path: Path) -> None:
    marker = tmp_path / "terminal.started"
    marker.write_bytes(b" " * (1_048_576 + 1))
    with pytest.raises(ValueError, match="candidate_evaluation_terminal_intent_invalid"):
        _read_candidate_terminal_intent(marker)
    assert marker.stat().st_size == 1_048_577
