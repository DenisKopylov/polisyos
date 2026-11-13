from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core import canon
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactIntegrityError,
    ArtifactRef,
    artifact_ref_for_manifest,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control.run_lifecycle import (
    AcquisitionRouteLoopAuthoritySink,
    _read_verified_acquisition_action_phase,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlDiagnosticEventRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionSelectedEvaluation
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateRouteLoopReceipt,
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
    AcquisitionRouteRecoveryRequired,
    persist_world_commit_and_reenter,
    resume_world_committed_reentry,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _receipt(
    *,
    receipt_phase: str,
    coarse_phase: str,
    recovery_state: str,
    predecessor_receipt_ref: str | None,
    owner_receipt_refs: tuple[str, ...] = (),
) -> AcquisitionRoutePhaseReceipt:
    return AcquisitionRoutePhaseReceipt(
        receipt_id=f"receipt-{receipt_phase}",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-source",
        route_id="sha256:" + "a" * 64,
        action_generation=1,
        job_id="job-acquisition",
        compiled_ref="sha256:" + "b" * 64,
        planner_report_hash="sha256:" + "c" * 64,
        cost_basis_hash="sha256:" + "d" * 64,
        decision_ref="sha256:" + "e" * 64,
        coarse_phase=coarse_phase,
        receipt_phase=receipt_phase,
        recovery_state=recovery_state,
        predecessor_receipt_ref=predecessor_receipt_ref,
        owner_receipt_refs=owner_receipt_refs,
        generated_at=NOW,
    )


def test_active_owner_receipt_persists_reentry_pending_before_callback(
    tmp_path: Path,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=store, artifact_store=cas)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas,
        event_log=event_log,
        control_store=store,
    )
    requested = sink.persist_phase(
        _receipt(
            receipt_phase="requested",
            coarse_phase="requested",
            recovery_state="none",
            predecessor_receipt_ref=None,
        )
    )
    executing = sink.persist_phase(
        _receipt(
            receipt_phase="executing",
            coarse_phase="executing",
            recovery_state="none",
            predecessor_receipt_ref=requested.receipt_ref,
        )
    )
    pending = _receipt(
        receipt_phase="world_committed_reentry_pending",
        coarse_phase="world_committed",
        recovery_state="reentry_recovery_required",
        predecessor_receipt_ref=executing.receipt_ref,
        owner_receipt_refs=("sha256:" + "f" * 64,),
    )
    reentry_calls = 0

    def crash_after_readback() -> str:
        nonlocal reentry_calls
        reentry_calls += 1
        durable = sink.get_head(pending)
        assert durable is not None
        assert durable.receipt_phase == "world_committed_reentry_pending"
        assert durable.recovery_state == "reentry_recovery_required"
        raise RuntimeError("crash-after-world-commit")

    with pytest.raises(AcquisitionRouteRecoveryRequired):
        persist_world_commit_and_reenter(
            sink=sink,
            pending_receipt=pending,
            reentry=crash_after_readback,
        )

    assert reentry_calls == 1
    pending_durable = sink.get_head(pending)
    assert pending_durable is not None

    def complete_reentry() -> str:
        current = sink.get_head(pending)
        assert current == pending_durable
        assert current.receipt_phase == "world_committed_reentry_pending"
        assert current.receipt_ref == pending_durable.receipt_ref
        assert current.durable_event_id == pending_durable.durable_event_id
        assert all(
            row.event.event_type != "polisyos.runtime.acquisition.route_loop.v1"
            for row in event_log.list_events(run_id=pending.run_id, job_id=pending.job_id)
        )
        return "sha256:" + "1" * 64

    recovered = resume_world_committed_reentry(
        sink=sink,
        pending_receipt=pending,
        reentry=complete_reentry,
    )
    assert recovered.receipt_phase == "terminal"
    assert recovered.recovery_state == "complete"
    assert recovered.predecessor_receipt_ref == pending_durable.receipt_ref
    assert recovered.receipt_ref != pending_durable.receipt_ref
    assert recovered.durable_event_id != pending_durable.durable_event_id

    terminal_manifest = cas.get_manifest(recovered.receipt_ref)
    assert terminal_manifest.kind == "runtime_quality.acquisition_route_loop_receipt"
    assert terminal_manifest.artifact_schema is not None
    assert terminal_manifest.artifact_schema.name == "polisyos.runtime.AcquisitionRouteLoopReceipt"
    terminal_payload = canon.from_canonical_bytes(cas.get_bytes(recovered.receipt_ref))
    assert terminal_payload["schema_version"] == "AcquisitionRouteLoopReceipt@1.0"
    assert terminal_payload["receipt_phase"] == "terminal"
    assert terminal_payload["predecessor_receipt_ref"] == pending_durable.receipt_ref
    assert terminal_payload["reentry_receipt_ref"] == "sha256:" + "1" * 64

    terminal_events = event_log.list_events(event_id=recovered.durable_event_id)
    assert len(terminal_events) == 1
    assert terminal_events[0].event.event_type == "polisyos.runtime.acquisition.route_loop.v1"

    with pytest.raises(ValueError, match="receipt_phase"):
        _receipt(
            receipt_phase="terminal",
            coarse_phase="terminal",
            recovery_state="complete",
            predecessor_receipt_ref=pending_durable.receipt_ref,
            owner_receipt_refs=("sha256:" + "1" * 64,),
        )


@pytest.fixture
def generation_owner(tmp_path):
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=store, artifact_store=cas)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas, event_log=event_log, control_store=store
    )
    return sink, store, cas


def _generation_identity():
    return {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "job-source",
        "route_id": "sha256:" + "a" * 64,
    }


def test_current_outcome_selection_ignores_non_outcome_raw_and_parquet_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real owner evidence is classified before the selected outcome is verified."""
    from decimal import Decimal
    from types import SimpleNamespace

    import duckdb

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core import artifacts
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        AcquisitionWorldGrowthConfig,
        AcquisitionWorldGrowthReceipt,
        AcquisitionWorldGrowthRoute,
    )
    from tests._helpers.semantic_epoch_native import (
        finalize_native_epoch_case,
        make_native_epoch_case,
    )

    native = make_native_epoch_case(tmp_path / "native")
    finalized = finalize_native_epoch_case(native)
    cas = native.store
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=cas)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas, event_log=events, control_store=control
    )
    requested = sink.persist_phase(
        _receipt(
            receipt_phase="requested",
            coarse_phase="requested",
            recovery_state="none",
            predecessor_receipt_ref=None,
        )
    )
    executing = _receipt(
        receipt_phase="executing",
        coarse_phase="executing",
        recovery_state="none",
        predecessor_receipt_ref=requested.receipt_ref,
    )
    executing_head = sink.persist_phase(executing)
    raw_ref = native.scenario.passport.raw_artifact_id
    assert cas.get_manifest(raw_ref).kind == "fabric.acquisition.raw_evidence"
    assert cas.get_manifest(raw_ref).canon is None
    parquet_path = tmp_path / "observed.parquet"
    with duckdb.connect() as connection:
        connection.execute("COPY (SELECT 1 AS observed) TO ? (FORMAT PARQUET)", [str(parquet_path)])
    parquet_bytes = parquet_path.read_bytes()
    assert parquet_bytes.startswith(b"PAR1") and parquet_bytes.endswith(b"PAR1")
    parquet_ref = cas.put_bytes(
        parquet_bytes,
        artifacts.PutOptions(kind="fixture.observed_parquet", media_type="application/parquet"),
    )
    assert cas.get_manifest(parquet_ref).canon is None

    query = native.scenario.query
    selection = AcquisitionWorldGrowthRoute(
        tenant_id=executing.tenant_id,
        cell_id=executing.cell_id,
        run_id=executing.run_id,
        route_id=executing.route_id,
        design_problem_ref="sha256:" + "1" * 64,
        epoch_id=native.scenario.passport.epoch_id,
        epoch_scope_identity=query.scope_identity,
        authority_purpose=query.authority_purpose,
        valid_effect_coordinate_evidence_ref=query.valid_effect_coordinate_evidence_ref,
        visibility_knowledge_cutoff_evidence_ref=query.visibility_knowledge_cutoff_evidence_ref,
        purpose_admission_cutoff_evidence_ref=query.purpose_admission_cutoff_evidence_ref,
        facet_source_refs={},
        reentry_budget_usd=Decimal("0.10"),
    )
    growth = AcquisitionWorldGrowthReceipt(
        selection=selection,
        binding_id="fixture-binding",
        activation=finalized.receipt,
        passport_id=native.scenario.passport.passport_id,
        admitted_observation_delta=finalized.activated.admitted_observation_count,
        previously_active_observations=0,
        live_evidence_refs=(raw_ref, str(parquet_ref.artifact_id)),
        action_phase_ref=executing_head.receipt_ref,
    )
    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(),
        repo_root=tmp_path,
        runtime_root=tmp_path,
        authority=native.scenario.authority,
        artifact_store=cas,
        event_log=events,
        epoch_deployment=native.deployment,
    )
    closure = SimpleNamespace(
        **_generation_identity(),
        compiled_ref=executing.compiled_ref,
        cost_basis_hash=executing.cost_basis_hash,
    )

    def persist(record: AcquisitionWorldGrowthReceipt) -> str:
        result = bridge._persist(
            closure,
            record.model_dump(mode="json"),
            "runtime_quality.acquisition_world_growth_receipt",
            AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
            "world_committed",
        )
        assert isinstance(result, str)
        return result

    growth_ref = persist(growth)
    refs = (raw_ref, str(parquet_ref.artifact_id), growth_ref, executing_head.receipt_ref)
    assert sink._verified_current_action_outcome_ref(
        executing, executing_head.receipt_ref, refs
    ) == (growth_ref)

    # A stable wrong-schema view is not rescued by matching bytes or an event.
    growth_id = ArtifactID.model_validate(growth_ref)
    _, default_manifest_path = cas._paths(growth_id)
    original_manifest_bytes = default_manifest_path.read_bytes()
    original_manifest = cas.get_manifest(growth_id)
    wrong_schema = artifacts.SchemaInfo(name="fixture.WrongGrowth", version="1.1")
    wrong_manifest = original_manifest.model_copy(update={"artifact_schema": wrong_schema})
    wrong_profile = artifacts.artifact_manifest_profile_sha256(wrong_manifest)
    wrong_view_path = cas._layout.view_manifest_path(growth_id, wrong_profile)
    assert not wrong_view_path.exists()
    wrong_manifest_bytes = wrong_manifest.model_dump_json(by_alias=True, exclude_none=True).encode()
    try:
        wrong_view_path.write_bytes(wrong_manifest_bytes)
        default_manifest_path.write_bytes(wrong_manifest_bytes)
        with pytest.raises(ValueError, match="acquisition_action_owner_receipt_binding_mismatch"):
            sink._verified_current_action_outcome_ref(executing, executing_head.receipt_ref, refs)
    finally:
        default_manifest_path.write_bytes(original_manifest_bytes)
        wrong_view_path.unlink(missing_ok=True)

    # A default view changing between the classification and strict reads also refuses.
    import polisyos.runtime.http.services.control.run_lifecycle as lifecycle

    original_read = lifecycle.read_core_manifest_profile

    def changed_between_reads(store, selector, **kwargs):
        manifest, declaration = original_read(store, selector, **kwargs)
        if str(selector) == growth_ref and not kwargs.get("allow_profile_absent"):
            manifest = manifest.model_copy(update={"artifact_schema": wrong_schema})
        return manifest, declaration

    with monkeypatch.context() as context:
        context.setattr(lifecycle, "read_core_manifest_profile", changed_between_reads)
        with pytest.raises(ValueError, match="acquisition_action_owner_manifest_changed"):
            sink._verified_current_action_outcome_ref(executing, executing_head.receipt_ref, refs)
    assert sink._verified_current_action_outcome_ref(
        executing, executing_head.receipt_ref, refs
    ) == (growth_ref)

    # A recognized outcome still requires a declared, usable canonical profile.
    outcome_body = cas.get_bytes(growth_ref)
    base_options = {
        "kind": "runtime_quality.acquisition_world_growth_receipt",
        "media_type": "application/json",
        "schema": artifacts.SchemaInfo(
            name=AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME, version="1.1"
        ),
    }
    absent = cas.put_bytes(outcome_body + b" ", artifacts.PutOptions(**base_options))
    unknown_canon = artifacts.CanonInfo.from_spec(canon.CanonSpec(forbid_floats=False)).model_copy(
        update={"version": "99.0"}
    )
    wrong_canon = cas.put_bytes(
        outcome_body + b"  ", artifacts.PutOptions(**base_options, canon=unknown_canon)
    )
    for bad_ref in (absent, wrong_canon):
        with pytest.raises(CanonicalProfileRefusalError):
            sink._verified_current_action_outcome_ref(
                executing,
                executing_head.receipt_ref,
                (raw_ref, str(bad_ref.artifact_id), growth_ref),
            )

    missing_ref = "sha256:" + "f" * 64
    with pytest.raises((FileNotFoundError, ValueError)):
        sink._verified_current_action_outcome_ref(
            executing, executing_head.receipt_ref, (missing_ref, growth_ref)
        )
    wrong_kind = cas.put_bytes(
        b'{"test":"wrong-kind"}',
        artifacts.PutOptions(kind="fixture.not_candidate", media_type="application/json"),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="acquisition_candidate_owner_profile_invalid"):
        sink._verified_current_action_outcome_ref(
            executing,
            executing_head.receipt_ref,
            (str(wrong_kind.artifact_id), growth_ref),
            candidate_receipt_ref=wrong_kind,
        )
    retagged_view = wrong_kind.model_copy(
        update={"kind": "runtime_quality.acquisition_candidate_action_receipt"}
    )
    with pytest.raises(ValueError):
        sink._verified_current_action_outcome_ref(
            executing,
            executing_head.receipt_ref,
            (str(retagged_view.artifact_id), growth_ref),
            candidate_receipt_ref=retagged_view,
        )
    unselected_candidate = cas.put_bytes(
        b'{"candidate":true}',
        artifacts.PutOptions(
            kind="runtime_quality.acquisition_candidate_action_receipt",
            media_type="application/json",
            canon=artifacts.CanonInfo.from_spec(canon.CanonSpec(forbid_floats=False)),
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="acquisition_candidate_owner_profile_missing"):
        sink._verified_current_action_outcome_ref(
            executing,
            executing_head.receipt_ref,
            (str(unselected_candidate.artifact_id), growth_ref),
        )
    missing_view = ArtifactRef(
        artifact_id=wrong_kind.artifact_id,
        kind="runtime_quality.acquisition_candidate_action_receipt",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )
    with pytest.raises((FileNotFoundError, ValueError)):
        sink._verified_current_action_outcome_ref(
            executing,
            executing_head.receipt_ref,
            (str(missing_view.artifact_id), growth_ref),
            candidate_receipt_ref=missing_view,
        )
    with pytest.raises(ValueError, match="acquisition_candidate_owner_profile_invalid"):
        sink._verified_current_action_outcome_ref(
            executing,
            executing_head.receipt_ref,
            (growth_ref,),
            candidate_receipt_ref=missing_view,
        )
    second = persist(growth.model_copy(update={"binding_id": "second-valid-outcome"}))
    with pytest.raises(ValueError, match="acquisition_action_owner_outcome_missing_or_ambiguous"):
        sink._verified_current_action_outcome_ref(
            executing, executing_head.receipt_ref, (raw_ref, growth_ref, second)
        )


def _persist_generation(sink, *, generation, job_id, terminal_outcome=None):
    """Exercise the real receipt owner; supplied owner refs are fixture evidence."""
    common = {"action_generation": generation, "job_id": job_id}
    requested = _receipt(
        receipt_phase="requested",
        coarse_phase="requested",
        recovery_state="none",
        predecessor_receipt_ref=None,
    )
    requested = AcquisitionRoutePhaseReceipt.model_validate({**requested.model_dump(), **common})
    head = sink.persist_phase(requested)
    executing = AcquisitionRoutePhaseReceipt.model_validate(
        {
            **requested.model_dump(),
            "receipt_id": "receipt-executing",
            "receipt_phase": "executing",
            "coarse_phase": "executing",
            "predecessor_receipt_ref": head.receipt_ref,
        }
    )
    head = sink.persist_phase(executing)
    if terminal_outcome is None:
        return head
    terminal_base = executing
    terminal_predecessor = head
    if terminal_outcome == "reentry_completed":
        terminal_base = executing.model_copy(
            update={
                "receipt_id": "receipt-world-committed-reentry-pending",
                "receipt_phase": "world_committed_reentry_pending",
                "coarse_phase": "world_committed",
                "recovery_state": "reentry_recovery_required",
                "predecessor_receipt_ref": head.receipt_ref,
                "owner_receipt_refs": ("sha256:" + "f" * 64,),
            }
        )
        terminal_predecessor = sink.persist_phase(terminal_base)
    terminal = AcquisitionRouteLoopReceipt.model_validate(
        {
            **terminal_base.model_dump(exclude={"schema_version"}),
            "receipt_id": "receipt-terminal",
            "receipt_phase": "terminal",
            "coarse_phase": "terminal",
            "recovery_state": "complete",
            "predecessor_receipt_ref": terminal_predecessor.receipt_ref,
            "terminal_outcome": terminal_outcome,
            "owner_receipt_refs": ("sha256:" + "f" * 64,),
            "reentry_receipt_ref": (
                "sha256:" + "1" * 64 if terminal_outcome == "reentry_completed" else None
            ),
        }
    )
    return sink.persist_terminal(terminal)


class _QueryOnlyDiagnosticRows:
    """Read actual diagnostic rows without presenting a mutable store identity."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def list_diagnostic_events(
        self,
        *,
        event_id: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        limit: int = 500,
    ) -> list[ControlDiagnosticEventRecord]:
        with closing(
            sqlite3.connect(self._path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                "SELECT row_id, event_json, payload_ref, payload_inline_json, "
                "payload_sha256, created_at FROM control_diagnostic_events "
                "WHERE (? IS NULL OR event_id = ?) AND (? IS NULL OR run_id = ?) "
                "AND (? IS NULL OR job_id = ?) ORDER BY row_id ASC LIMIT ?",
                (event_id, event_id, run_id, run_id, job_id, job_id, max(1, min(limit, 1000))),
            ).fetchall()
        return [
            ControlDiagnosticEventRecord(
                row_id=row["row_id"],
                event=DiagnosticEvent.model_validate_json(row["event_json"]),
                payload_ref=row["payload_ref"],
                payload_inline=(
                    json.loads(row["payload_inline_json"]) if row["payload_inline_json"] else None
                ),
                payload_sha256=row["payload_sha256"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]


@pytest.mark.parametrize(
    ("corruption", "error_type", "message"),
    [
        (None, None, None),
        ("missing_event", ValueError, "authority_orphan_cas"),
        ("corrupt_event", ValueError, "authority_payload_mismatch"),
        ("missing_manifest", FileNotFoundError, None),
        ("corrupt_manifest", ArtifactIntegrityError, "Selected manifest profile mismatch"),
        ("corrupt_receipt", ArtifactIntegrityError, None),
    ],
)
def test_readonly_phase_reader_reconciles_actual_sqlite_history(
    generation_owner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str | None,
    error_type: type[Exception] | None,
    message: str | None,
) -> None:
    """A fresh read needs selected bytes and actual rows, without writer capabilities."""
    sink, database, cas = generation_owner
    terminal = _persist_generation(
        sink, generation=1, job_id="readonly-history", terminal_outcome="quarantined_no_growth"
    )
    phases = sink.current_action_outcome(**_generation_identity()).phase_chain
    writable = {
        phase.receipt_ref: sink._read_verified_action_phase(phase.receipt_ref) for phase in phases
    }
    terminal_ref = artifact_ref_for_manifest(
        cas.get_manifest(ArtifactID.model_validate(terminal.receipt_ref))
    )
    assert terminal_ref.manifest_profile_sha256 is not None
    root = tmp_path / "cas"
    artifact_hex = terminal.receipt_ref.removeprefix("sha256:")
    member_root = root / "artifacts" / "sha256" / artifact_hex[:2] / artifact_hex[2:4]
    manifest = member_root / (
        artifact_hex
        + ".view."
        + terminal_ref.manifest_profile_sha256.removeprefix("sha256:")
        + ".manifest.json"
    )
    if corruption == "missing_event":
        database._execute(
            "DELETE FROM control_diagnostic_events WHERE event_id = ?",
            (terminal.durable_event_id,),
        )
    elif corruption == "corrupt_event":
        record = database.list_diagnostic_events(event_id=terminal.durable_event_id)[0]
        altered = record.event.model_copy(update={"state_after": "requested"})
        database._execute(
            "UPDATE control_diagnostic_events SET event_json = ? WHERE event_id = ?",
            (altered.model_dump_json(), terminal.durable_event_id),
        )
    elif corruption == "missing_manifest":
        manifest.unlink()
    elif corruption == "corrupt_manifest":
        altered_manifest = json.loads(manifest.read_text())
        altered_manifest["producer"]["version"] = "tampered"
        manifest.write_text(json.dumps(altered_manifest))
    elif corruption == "corrupt_receipt":
        blob = member_root / (artifact_hex + ".blob")
        blob.write_bytes(blob.read_bytes() + b" ")

    def pins() -> dict[str, str]:
        paths = [path for path in root.rglob("*") if path.is_file()]
        paths.extend(
            path for path in tmp_path.glob("control.sqlite3*") if path.suffix != ".sqlite3-shm"
        )
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

    readonly = FileSystemCAS.open_existing_read_only(root)
    events = RuntimeDiagnosticEventLog(
        store=_QueryOnlyDiagnosticRows(tmp_path / "control.sqlite3"), artifact_store=readonly
    )
    # Opening an existing WAL-mode database may initialize an empty WAL/SHM.
    # Freeze after reader setup; the proof below must preserve every data byte.
    events.list_events(event_id=terminal.durable_event_id)
    before = pins()
    assert not hasattr(readonly, "put_json")

    def forbid_store_construction(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("historical reader must not construct ControlPlaneStore")

    monkeypatch.setattr(ControlPlaneStore, "__init__", forbid_store_construction)
    with tenant_scope(None, tenant_id=terminal.tenant_id, cell_id=terminal.cell_id):
        if error_type is not None:
            with pytest.raises(error_type, match=message):
                _read_verified_acquisition_action_phase(
                    artifact_store=readonly,
                    event_log=events,
                    receipt_ref=terminal.receipt_ref,
                    selected_ref=terminal_ref,
                )
        else:
            for phase in phases:
                assert writable[phase.receipt_ref] == _read_verified_acquisition_action_phase(
                    artifact_store=readonly,
                    event_log=events,
                    receipt_ref=phase.receipt_ref,
                    selected_ref=(
                        terminal_ref if phase.receipt_ref == terminal.receipt_ref else None
                    ),
                )
    assert pins() == before


def test_missing_candidate_frontier_owner_has_no_authority_side_effects(
    generation_owner, monkeypatch
):
    """A removed owner cannot write a terminal even with an existing real action head."""
    from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch

    sink, store, cas = generation_owner
    head = _persist_generation(sink, generation=1, job_id="first-job")
    phase = sink.verify_action_head(head).latest_receipt

    def ref(kind: str, digit: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=ArtifactID.model_validate("sha256:" + digit * 64),
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "f" * 64,
        )

    action = ref("runtime_quality.acquisition_candidate_action_receipt", "1")
    decision = ref("runtime_quality.acquisition_evaluation_decision", "2")
    basis = ref("runtime_quality.acquisition_evaluation_basis", "3")
    execution = ref("runtime.quality.candidate_simulation_execution", "4")
    selected = AcquisitionSelectedEvaluation(
        candidate_id="candidate",
        candidate_content_hash="sha256:" + "5" * 64,
        design_problem_ref="sha256:" + "6" * 64,
        world_model_record_hash="sha256:" + "7" * 64,
        evaluation_job_id="source-job",
        evaluation_run_id="source-run",
        generation_run_id="generation-run",
        cycle_index=0,
        n4_source_ref=ref("runtime.quality.n4_candidate_scenario_source", "8"),
        context_job_ref=ref("runtime.quality.cycle_substrate_context_job", "9"),
        n5_input_ref=ref("runtime.quality.candidate_simulation_n5_input", "a"),
        n5_execution_ref=execution,
        n5_result_ref=ref("polisyos.runtime.joint_simulation_result", "b"),
        basis_ref=basis,
    )
    terminal = AcquisitionCandidateRouteLoopReceipt(
        **phase.model_dump(
            exclude={
                "schema_version",
                "receipt_id",
                "coarse_phase",
                "receipt_phase",
                "recovery_state",
                "predecessor_receipt_ref",
                "owner_receipt_refs",
                "candidate_receipt_ref",
            }
        ),
        receipt_id="candidate-retained-owner-removal",
        terminal_outcome="candidate_evaluation_retained",
        predecessor_receipt_ref=head.receipt_ref,
        owner_receipt_refs=(str(action.artifact_id), str(decision.artifact_id)),
        candidate_action_ref=action,
        evaluation_decision_ref=decision,
        selected_basis_ref=basis,
        selected_evaluation_witness_ref=execution,
        selected_evaluation=selected,
        current_continuation_ref=ref(
            "runtime_quality.candidate_acquisition_retained_continuation", "c"
        ),
    )

    class TypedBasisRef(ArtifactRef):
        pass

    typed_basis = TypedBasisRef.model_validate(basis.model_dump())
    fields = {name: getattr(terminal, name) for name in type(terminal).model_fields}
    same_view = AcquisitionCandidateRouteLoopReceipt.model_validate(
        {**fields, "selected_evaluation": selected.model_copy(update={"basis_ref": typed_basis})}
    )
    assert same_view.selected_evaluation is not None
    foreign_view = typed_basis.model_copy(update={"manifest_profile_sha256": "sha256:" + "e" * 64})
    with pytest.raises(ValueError, match="candidate_terminal_evaluation_binding_invalid"):
        AcquisitionCandidateRouteLoopReceipt.model_validate(
            {
                **fields,
                "selected_evaluation": selected.model_copy(update={"basis_ref": foreign_view}),
            }
        )

    class ExtendedBasisRef(ArtifactRef):
        extra_meaning: str = "unverified"

    extended = ExtendedBasisRef.model_validate(basis.model_dump())
    with pytest.raises(ValueError, match="candidate_terminal_ref_subtype_semantics_unsupported"):
        AcquisitionCandidateRouteLoopReceipt.model_validate(
            {**fields, "selected_evaluation": selected.model_copy(update={"basis_ref": extended})}
        )
    before_ids = {str(ref) for ref in cas.iter_artifact_ids()}
    before_events = store.list_diagnostic_events(run_id="run-a", limit=500)
    monkeypatch.delattr(dispatch, "candidate_terminal_frontier_cas", raising=False)
    with pytest.raises(ValueError, match="acquisition_candidate_terminal_history_not_established"):
        sink.persist_terminal(terminal)
    assert {str(ref) for ref in cas.iter_artifact_ids()} == before_ids
    assert store.list_diagnostic_events(run_id="run-a", limit=500) == before_events
    assert sink.get_head(phase) == head


def test_duplicate_executing_phase_is_refused_before_head_advances(generation_owner):
    sink, _store, _cas = generation_owner
    head = _persist_generation(sink, generation=1, job_id="first-job")
    current = sink.verify_action_head(head).latest_receipt
    duplicate = AcquisitionRoutePhaseReceipt.model_validate(
        {
            **current.model_dump(mode="python"),
            "receipt_id": "forged-second-executing",
            "predecessor_receipt_ref": head.receipt_ref,
        }
    )
    with pytest.raises(ValueError, match="acquisition_action_phase_transition_invalid"):
        sink.persist_phase(duplicate)
    assert sink.get_head(duplicate) == head
    assert sink.resolve_action_generation(**_generation_identity(), job_id="first-job") == 1


def test_action_generation_preserves_quarantine_and_reuses_exact_job(generation_owner):
    sink, store, cas = generation_owner
    identity = _generation_identity()
    assert sink.resolve_action_generation(**identity, job_id="first-job") == 1
    first = _persist_generation(
        sink, generation=1, job_id="first-job", terminal_outcome="quarantined_no_growth"
    )
    first_bytes = cas.get_bytes(first.receipt_ref)
    assert sink.resolve_action_generation(**identity, job_id="first-job") == 1
    assert sink.resolve_action_generation(**identity, job_id="second-job") == 2
    second = _persist_generation(sink, generation=2, job_id="second-job")
    assert sink.resolve_action_generation(**identity, job_id="second-job") == 2
    assert sink.resolve_action_generation(**identity, job_id="first-job") == 1
    heads = store.list_acquisition_action_heads(**identity)
    assert heads == (first, second)
    assert cas.get_bytes(first.receipt_ref) == first_bytes
    assert store.get_acquisition_action_head(**identity, action_generation=1) == first


def test_source_history_heads_are_exactly_scoped_across_route_ids(generation_owner):
    sink, store, _cas = generation_owner

    def persist_current(identity: dict[str, str], *, job_id: str, action_generation: int = 1):
        requested = _receipt(
            receipt_phase="requested",
            coarse_phase="requested",
            recovery_state="none",
            predecessor_receipt_ref=None,
        ).model_copy(
            update={
                **identity,
                "receipt_id": f"{job_id}.requested",
                "job_id": job_id,
                "action_generation": action_generation,
            }
        )
        head = sink.persist_phase(requested)
        executing = requested.model_copy(
            update={
                "receipt_id": f"{job_id}.executing",
                "receipt_phase": "executing",
                "coarse_phase": "executing",
                "predecessor_receipt_ref": head.receipt_ref,
            }
        )
        return sink.persist_phase(executing)

    first_identity = _generation_identity()
    second_route_identity = {
        **first_identity,
        "route_id": "sha256:" + "b" * 64,
    }
    foreign_job_identity = {**first_identity, "source_job_id": "job-other"}
    foreign_run_identity = {**first_identity, "run_id": "run-other"}
    expected = (
        persist_current(first_identity, job_id="route-a-job"),
        persist_current(second_route_identity, job_id="route-b-job", action_generation=2),
    )
    persist_current(foreign_job_identity, job_id="foreign-job", action_generation=3)
    persist_current(foreign_run_identity, job_id="foreign-run", action_generation=4)

    observed = store.list_acquisition_action_heads_for_source(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-source",
    )

    assert observed == expected
    assert tuple(row.route_id for row in observed) == (
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
    )
    with pytest.raises(ValueError, match="acquisition_action_source_scope_invalid"):
        store.list_acquisition_action_heads_for_source(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id=" ",
            source_job_id="job-source",
        )


def test_new_action_generation_refuses_pending_owner(generation_owner):
    sink, _store, _cas = generation_owner
    _persist_generation(sink, generation=1, job_id="first-job")
    with pytest.raises(ValueError, match="acquisition_action_generation_not_reopenable"):
        sink.resolve_action_generation(**_generation_identity(), job_id="second-job")


def test_reentry_terminal_head_allows_successor_generation(generation_owner):
    sink, _store, _cas = generation_owner
    # Route resolution verifies the persisted growth and v3 continuation before
    # this lifecycle step can advance to the next generation.
    _persist_generation(
        sink, generation=1, job_id="first-job", terminal_outcome="reentry_completed"
    )
    assert sink.resolve_action_generation(**_generation_identity(), job_id="second-job") == 2
    outcomes = sink.action_outcomes(**_generation_identity())
    assert len(outcomes) == 1
    assert outcomes[0].latest_receipt.terminal_outcome == "reentry_completed"


def test_action_outcomes_refuse_nonterminal_predecessor(generation_owner):
    sink, _store, _cas = generation_owner
    _persist_generation(sink, generation=1, job_id="first-job")
    _persist_generation(sink, generation=2, job_id="second-job")
    with pytest.raises(ValueError, match="acquisition_action_generation_predecessor_not_terminal"):
        sink.action_outcomes(**_generation_identity())


def test_action_generation_refuses_row_marker_without_terminal_custody(generation_owner):
    sink, store, _cas = generation_owner
    head = _persist_generation(sink, generation=1, job_id="first-job")
    store._execute(
        "UPDATE runtime_acquisition_action_heads SET coarse_phase = 'terminal', "
        "receipt_phase = 'terminal', recovery_state = 'complete' WHERE receipt_ref = ?",
        (head.receipt_ref,),
    )
    with pytest.raises(ValueError, match="acquisition_action_head_binding_mismatch"):
        sink.resolve_action_generation(**_generation_identity(), job_id="second-job")


def test_action_generation_requires_current_receipt_readback(generation_owner, monkeypatch):
    sink, store, cas = generation_owner
    head = _persist_generation(
        sink, generation=1, job_id="first-job", terminal_outcome="quarantined_no_growth"
    )
    before = store.list_acquisition_action_heads(**_generation_identity())
    original = cas.get_bytes

    def unreadable(ref):
        if str(ref) == head.receipt_ref:
            raise OSError("selected terminal receipt unreadable")
        return original(ref)

    monkeypatch.setattr(cas, "get_bytes", unreadable)
    with pytest.raises(OSError, match="selected terminal receipt unreadable"):
        sink.resolve_action_generation(**_generation_identity(), job_id="second-job")
    assert store.list_acquisition_action_heads(**_generation_identity()) == before


def test_action_generation_refuses_same_job_in_multiple_generations(generation_owner):
    sink, _store, _cas = generation_owner
    _persist_generation(
        sink, generation=1, job_id="first-job", terminal_outcome="quarantined_no_growth"
    )
    _persist_generation(sink, generation=2, job_id="first-job")
    with pytest.raises(ValueError, match="acquisition_action_job_generation_ambiguous"):
        sink.resolve_action_generation(**_generation_identity(), job_id="first-job")


def test_current_action_outcome_uses_latest_generation_after_store_reopen(
    tmp_path: Path,
) -> None:
    control_path = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=control_path)
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas,
        event_log=RuntimeDiagnosticEventLog(store=store, artifact_store=cas),
        control_store=store,
    )
    scope = _generation_identity()
    first = _persist_generation(
        sink, generation=1, job_id="job-acquisition-one", terminal_outcome="quarantined_no_growth"
    )
    requested = _receipt(
        receipt_phase="requested",
        coarse_phase="requested",
        recovery_state="none",
        predecessor_receipt_ref=None,
    ).model_copy(
        update={
            "receipt_id": "receipt-generation-two-requested",
            "job_id": "job-acquisition-two",
            "action_generation": 2,
        }
    )
    requested_head = sink.persist_phase(requested)
    executing = requested.model_copy(
        update={
            "receipt_id": "receipt-generation-two-executing",
            "receipt_phase": "executing",
            "coarse_phase": "executing",
            "predecessor_receipt_ref": requested_head.receipt_ref,
        }
    )
    executing_head = sink.persist_phase(executing)
    active = sink.current_action_outcome(**scope)
    assert active is not None
    assert active.head.action_generation == 2
    assert active.latest_receipt.receipt_phase == "executing"
    assert active.executing_phase_ref == executing_head.receipt_ref
    assert active.executing_phase == executing
    assert tuple(item.receipt.receipt_phase for item in active.phase_chain) == (
        "requested",
        "executing",
    )

    unrelated_source = requested.model_copy(
        update={
            "receipt_id": "receipt-other-source-requested",
            "job_id": "job-other-source",
            "source_job_id": "other-source",
            "action_generation": 99,
        }
    )
    sink.persist_phase(unrelated_source)
    assert sink.action_outcomes(**scope)[0].head == first

    reopened_store = ControlPlaneStore(backend="sqlite", sqlite_path=control_path)
    reopened_sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=cas,
        event_log=RuntimeDiagnosticEventLog(store=reopened_store, artifact_store=cas),
        control_store=reopened_store,
    )
    reopened = reopened_sink.current_action_outcome(**scope)
    assert reopened == active


def test_current_action_outcome_rejects_a_missing_requested_ancestor(
    generation_owner, monkeypatch
) -> None:
    sink, store, cas = generation_owner
    requested = sink.persist_phase(
        _receipt(
            receipt_phase="requested",
            coarse_phase="requested",
            recovery_state="none",
            predecessor_receipt_ref=None,
        )
    )
    executing = AcquisitionRoutePhaseReceipt.model_validate(
        {
            **_receipt(
                receipt_phase="executing",
                coarse_phase="executing",
                recovery_state="none",
                predecessor_receipt_ref=requested.receipt_ref,
            ).model_dump(),
            "receipt_id": "receipt-current-executing",
        }
    )
    current = sink.persist_phase(executing)
    original_get_bytes = cas.get_bytes

    def missing_requested(ref):
        if str(ref) == requested.receipt_ref:
            raise OSError("requested ancestor unavailable")
        return original_get_bytes(ref)

    monkeypatch.setattr(cas, "get_bytes", missing_requested)
    with pytest.raises(OSError, match="requested ancestor unavailable"):
        sink.current_action_outcome(**_generation_identity())
    assert (
        store.get_acquisition_action_head(**_generation_identity(), action_generation=1) == current
    )


def test_current_action_outcome_rejects_forged_event_input_refs(
    generation_owner, monkeypatch
) -> None:
    sink, _store, _cas = generation_owner
    current = _persist_generation(sink, generation=1, job_id="first-job")
    event_log = sink._event_log
    original_list_events = event_log.list_events

    def forged_inputs(**kwargs):
        records = original_list_events(**kwargs)
        if not any(record.event.event_id == current.durable_event_id for record in records):
            return records
        return [
            replace(
                record,
                event=record.event.model_copy(update={"input_refs": ("sha256:" + "f" * 64,)}),
            )
            if record.event.event_id == current.durable_event_id
            else record
            for record in records
        ]

    monkeypatch.setattr(event_log, "list_events", forged_inputs)
    with pytest.raises(ValueError):
        sink.current_action_outcome(**_generation_identity())
