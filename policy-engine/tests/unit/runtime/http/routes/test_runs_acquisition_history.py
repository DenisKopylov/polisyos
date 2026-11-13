"""Selected terminal dispatch through the real API history projector.

CAS, typed receipts, producer events, SQL heads and frontiers are real. The full
historical source/budget replay is isolated at its canonical verifier seam here;
the served integration oracle separately exercises that complete authority chain.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.runtime import (
    RunCandidateSimulationAcquisitionHistoryEntryV5,
    RunCandidateSimulationProjection,
    RunDetails,
)
from polisyos.runtime.http.routes import runs
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control.run_lifecycle import (
    _acquisition_route_receipt_inputs,
    _read_verified_acquisition_action_phase,
)
from polisyos.runtime.quality import acquisition_evaluation_history as history_owner
from polisyos.runtime.quality.acquisition_evaluation import (
    CandidateEvaluationTerminalHistory,
    CandidateExperimentTerminalHistory,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentTerminalReceipt,
    AcquisitionCandidateExperimentTerminalReceiptV2,
    AcquisitionCandidateRouteLoopReceipt,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from tests._helpers.runtime_http import _build_control_service
from tests.unit.core.contracts.test_run_candidate_simulation_acquisition_history_v3 import (
    _cheap_consequences,
    _wire_row,
)
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import (
    _bootstrap,
    _create_action_job,
)
from tests.unit.runtime.quality.test_candidate_experiment_reuse_occurrence import (
    _occurrence,
    _write_profile_variant,
)
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _hash,
    _ref,
    _requested_phase,
)

_KIND = "runtime_quality.acquisition_route_loop_receipt"
_EXPERIMENT_SCHEMA = "polisyos.runtime.AcquisitionCandidateExperimentTerminalReceipt"
_LOOP_SCHEMA = "polisyos.runtime.AcquisitionRouteLoopReceipt"


def _case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    epoch: str = "1.0",
    blocked: bool = False,
    kind: str = _KIND,
    schema_name: str = _EXPERIMENT_SCHEMA,
    schema_version: str | None = None,
    previous: SimpleNamespace | None = None,
) -> SimpleNamespace:
    if previous is None:
        store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
        service = _build_control_service(tmp_path / "service", artifact_store=store)
        database = service._control_store
        _, frontier, _ = _bootstrap(database, tmp_path, source_job_id="source-a")
        generation, job_id = 1, "action-a"
        histories: dict[str, CandidateExperimentTerminalHistory] = {}
        calls: list[ArtifactRef] = []
    else:
        store, service, database = previous.store, previous.service, previous.database
        frontier = database.read_acquisition_evaluation_frontier(
            previous.history.frontier_after.key
        )
        generation, job_id = previous.head.action_generation + 1, "action-b"
        histories, calls = previous.histories, previous.calls
    job, worker, attempt = _create_action_job(database, job_id=job_id)
    phase = _requested_phase()
    phase = type(phase).model_validate(
        {**phase.model_dump(mode="python"), "job_id": job_id, "action_generation": generation}
    )
    action_ref = _ref("runtime_quality.acquisition_candidate_action_receipt", "7")
    source_ref = _ref("runtime.quality.candidate_acquisition_source", "8")
    decision_ref = _ref("runtime_quality.acquisition_evaluation_decision", "9")
    prior = _wire_row()["retained_evaluation"]
    prior.update(
        candidate_id=phase.policy_scope.candidate_id,
        candidate_content_hash=phase.policy_scope.candidate_content_hash,
        design_problem_ref=phase.policy_scope.design_problem_basis_ref,
        evaluation_job_id=job.job_id,
        evaluation_run_id=phase.run_id,
    )
    reentry_ref = _ref("runtime_quality.candidate_source_reentry_receipt", "4")
    continuation_ref = _ref("runtime_quality.candidate_acquisition_retained_continuation", "5")
    occurrence_ref = _ref("runtime_quality.candidate_experiment_reuse_occurrence", "6")
    if epoch == "2.0":
        _, occurrence_ref, _ = _occurrence(store)
    predecessor = _hash(str(generation))
    payload = {
        **phase.model_dump(mode="python", exclude={"candidate_receipt_ref"}),
        "schema_version": f"AcquisitionCandidateExperimentTerminalReceipt@{epoch}",
        "receipt_id": f"{job_id}.terminal",
        "coarse_phase": "terminal",
        "receipt_phase": "terminal",
        "recovery_state": "complete",
        "predecessor_receipt_ref": predecessor,
        "owner_receipt_refs": (str(action_ref.artifact_id), str(decision_ref.artifact_id)),
        "terminal_outcome": "candidate_reentry_completed",
        "candidate_action_ref": action_ref,
        "candidate_reentry_ref": reentry_ref,
        "evaluation_decision_ref": decision_ref,
        "selected_basis_ref": prior["basis_ref"],
        "selected_evaluation_witness_ref": prior["n5_execution_ref"],
        "selected_evaluation": prior,
    }
    if epoch == "2.0":
        payload.update(
            terminal_outcome="candidate_evaluation_retained",
            candidate_reentry_ref=None,
            current_continuation_ref=continuation_ref,
            reuse_occurrence_ref=occurrence_ref,
            owner_receipt_refs=(*payload["owner_receipt_refs"], str(occurrence_ref.artifact_id)),
        )
    if blocked:
        blocker = _ref("runtime_quality.candidate_experiment_blocker", "0")
        payload.update(
            terminal_outcome="candidate_blocked",
            candidate_reentry_ref=None,
            evaluation_decision_ref=None,
            selected_basis_ref=None,
            selected_evaluation_witness_ref=None,
            selected_evaluation=None,
            current_continuation_ref=None,
            blocker_ref=blocker,
            blocker_reason="candidate_input_unavailable",
            owner_receipt_refs=(*payload["owner_receipt_refs"], str(blocker.artifact_id)),
        )
    receipt_type = (
        AcquisitionCandidateExperimentTerminalReceipt
        if epoch == "1.0"
        else AcquisitionCandidateExperimentTerminalReceiptV2
    )
    terminal = receipt_type.model_validate(payload)
    inputs = _acquisition_route_receipt_inputs(terminal)
    written = write_runtime_authority_artifact(
        store,
        service._diagnostic_event_log,
        terminal.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version or epoch),
            producer=ProducerInfo(
                component="polisyos.runtime.acquisition_route_loop",
                version="2026.08.28+ds15-c02",
            ),
            inputs=(
                [
                    input_ref_from_artifact_ref(
                        occurrence_ref, role="candidate_experiment_reuse_occurrence"
                    )
                ]
                if epoch == "2.0"
                else []
            ),
        ),
        evidence_id=terminal.receipt_id,
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner="team-runtime-quality",
        reader_contract="runtime.acquisition_route_loop.reader",
        reader_contract_version="1.0",
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=terminal.run_id,
        job_id=terminal.job_id,
        trace_id=f"trace-{terminal.job_id}",
        span_id="span-terminal",
        parent_span_id=None,
        requested_execution_profile="governed",
        effective_execution_profile="governed",
        phase="acquisition_route_loop",
        generated_at=terminal.generated_at.isoformat(),
        as_of_time=terminal.generated_at.isoformat(),
        same_input_closure={
            "closure_id": f"acquisition-route:{terminal.receipt_id}",
            "status": "closed",
            "run_id": terminal.run_id,
            "job_id": terminal.job_id,
            "tenant_id": terminal.tenant_id,
            "cell_id": terminal.cell_id,
            "evidence_input_refs": inputs,
            "closure_sha256": terminal.route_id,
        },
        input_refs=inputs,
        effective_mode_ref=terminal.route_id,
        degradation_ledger_ref=None,
        semantic_binding_ref=str(terminal.authority_decision_ref.artifact_id),
        validation_status="pass",
        blocking_status="blocking" if blocked else "non_blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime.acquisition_route_loop",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="pa2_ds9_decision_required",
        ),
        event_id=f"evt-terminal-{generation}",
        event_source="polisyos.runtime.quality.acquisition_route_loop",
        event_type="polisyos.runtime.acquisition.candidate_experiment_terminal.v1",
        event_subject=f"run/{terminal.run_id}/job/{terminal.job_id}/acquisition/terminal",
        state_before="executing",
        state_after="terminal",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_ref = written.cas_ref
    if kind == _KIND and schema_name == _EXPERIMENT_SCHEMA and schema_version is None:
        assert (
            _read_verified_acquisition_action_phase(
                artifact_store=store,
                event_log=service._diagnostic_event_log,
                receipt_ref=str(selected_ref.artifact_id),
                selected_ref=selected_ref,
            ).receipt
            == terminal
        )
    with database.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        base = {
            "tenant_id": terminal.tenant_id,
            "cell_id": terminal.cell_id,
            "run_id": terminal.run_id,
            "source_job_id": terminal.source_job_id,
            "route_id": terminal.route_id,
            "action_generation": terminal.action_generation,
            "job_id": terminal.job_id,
        }
        database.advance_acquisition_action_head(
            **base,
            expected_head_generation=0,
            receipt_ref=predecessor,
            receipt_sha256=predecessor,
            durable_event_id="evt-requested",
            coarse_phase="executing",
            receipt_phase="executing",
            recovery_state="none",
            predecessor_receipt_ref=None,
        )
        head = database.advance_acquisition_action_head(
            **base,
            expected_head_generation=1,
            receipt_ref=str(selected_ref.artifact_id),
            receipt_sha256=str(selected_ref.artifact_id),
            receipt_manifest_profile_sha256=selected_ref.manifest_profile_sha256,
            durable_event_id=f"evt-terminal-{generation}",
            coarse_phase="terminal",
            receipt_phase="terminal",
            recovery_state="complete",
            predecessor_receipt_ref=predecessor,
        )
    reentry = SimpleNamespace(
        candidate_action_ref=action_ref,
        candidate_source_ref=source_ref,
        data_snapshot_ref=_ref("fabric.data_snapshot", "a"),
        world_model_ref=_ref("runtime.quality.world_model_record", "b"),
        model_declaration_ref=_ref("runtime.quality.candidate_simulation_model_declaration", "c"),
        ncm_ref=_ref("ir.ncm_spec", "d"),
        **{
            name: ArtifactRef.model_validate(prior[name])
            for name in (
                "n4_source_ref",
                "context_job_ref",
                "n5_input_ref",
                "n5_execution_ref",
                "n5_result_ref",
            )
        },
        new_cycle=SimpleNamespace(
            simulation=SimpleNamespace(status="joint_simulated", authority_blockers=()),
            cycle_index=1,
        ),
        source_cycle_index=0,
        source_generation_run_content_hash=_hash("a"),
        continued_generation_run_content_hash=_hash("b"),
        basis_transition=SimpleNamespace(content_hash=_hash("c")),
        limitations=("candidate_only",),
    )
    decision = SimpleNamespace(
        candidate_source_ref=source_ref,
        current_basis_ref=_ref("runtime_quality.acquisition_evaluation_basis", "d"),
        comparison_result="equivalent" if epoch == "2.0" else "different",
        predicate_provenance="recomputed",
        reason_codes=(),
    )
    basis = SimpleNamespace(
        basis_role="evaluated", predicate_provenance="recomputed", limitations=("candidate_only",)
    )
    history = CandidateExperimentTerminalHistory(
        head=head,
        terminal_ref=selected_ref,
        terminal=terminal,
        origin=None,
        phase_chain=(),
        action=None,
        source=None,
        budget_window=None,
        decision=decision,
        current_basis=basis,
        selected_basis=basis,
        evaluation=None,
        reentry=reentry if epoch == "1.0" else None,
        continuation=SimpleNamespace(current_projection=None) if epoch == "2.0" else None,
        frontier_before=frontier,
        frontier_after=frontier,
    )
    histories[head.receipt_ref] = history

    def verify(
        *, control_service: Any, head: Any, terminal_ref: ArtifactRef
    ) -> CandidateExperimentTerminalHistory:
        assert control_service is service
        selected_history = histories[head.receipt_ref]
        proof = _read_verified_acquisition_action_phase(
            artifact_store=store,
            event_log=service._diagnostic_event_log,
            receipt_ref=str(terminal_ref.artifact_id),
            selected_ref=terminal_ref,
        )
        assert proof.receipt == selected_history.terminal
        calls.append(terminal_ref)
        return selected_history

    monkeypatch.setattr(history_owner, "verify_candidate_experiment_terminal_history", verify)
    monkeypatch.setattr(
        type(service),
        "resolve_completed_control_job_core_run_source",
        lambda *_args, **_kwargs: SimpleNamespace(
            run_id="core-a",
            manifest=SimpleNamespace(control_job_id="source-a", outputs=(phase.compiled_ref,)),
        ),
    )
    monkeypatch.setattr(runs, "_candidate_source_current_projection", lambda **_kwargs: None)
    monkeypatch.setattr(runs, "_acquisition_selected_n5_observation", lambda **_kwargs: None)
    monkeypatch.setattr(
        history_owner,
        "project_retained_cheap_consequences",
        lambda _projection: {
            **_cheap_consequences(),
            "candidate_id": prior["candidate_id"],
            "candidate_content_hash": prior["candidate_content_hash"],
        },
    )
    return SimpleNamespace(
        store=store,
        service=service,
        database=database,
        terminal=terminal,
        head=head,
        selected_ref=selected_ref,
        history=history,
        histories=histories,
        calls=calls,
        compiled_ref=phase.compiled_ref,
    )


def _project(case: SimpleNamespace) -> tuple[Any, Any, Any]:
    return runs._candidate_acquisition_history_projection(
        compiled=SimpleNamespace(n4_recursive_source_ref=None, content_hash=_hash("6")),
        compiled_ref=case.compiled_ref,
        recursive_run=None,
        store=case.store,
        control_service=case.service,
        core_run_id="core-a",
        control_job_id="source-a",
        source_status="resolved",
        tenant_id="tenant-a",
        cell_id="cell-a",
    )


def _run_details(
    case: SimpleNamespace, entries: tuple[Any, ...], limitation: str | None
) -> RunDetails:
    return RunDetails(
        run_id="core-a",
        source_kind="core_run",
        status="completed",
        candidate_simulation=RunCandidateSimulationProjection(
            run_id="core-a",
            artifact_status="resolved",
            source_ref=case.compiled_ref,
            source_content_hash=_hash("6"),
            acquisition_history=entries,
            acquisition_history_limitation_code=limitation,
        ),
    )


@pytest.mark.parametrize("epoch", ["1.0", "2.0"])
def test_selected_experiment_terminal_reaches_run_details_v5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, epoch: str
) -> None:
    case = _case(tmp_path, monkeypatch, epoch=epoch)
    entries, limitation, _ = _project(case)
    assert limitation is None
    assert len(entries) == 1
    assert type(entries[0]) is RunCandidateSimulationAcquisitionHistoryEntryV5
    assert entries[0].route_receipt_ref == case.selected_ref
    assert (
        entries[0].selected_evaluation.model_dump()
        == case.terminal.selected_evaluation.model_dump()
    )
    assert entries[0].evaluation_provenance == (
        "retained_prior" if epoch == "2.0" else "new_execution"
    )
    assert case.calls == [case.selected_ref]
    run = _run_details(case, entries, limitation)
    restored = RunDetails.model_validate_json(run.model_dump_json())
    assert restored.candidate_simulation.acquisition_history == entries
    assert entries[0].publication_authority is False
    assert entries[0].observed_admission is False


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "foreign.terminal"},
        {"schema_name": "foreign.TerminalReceipt"},
        {"schema_version": "9.0"},
        {"schema_version": "2.0"},
        {"schema_name": _LOOP_SCHEMA},
    ],
)
def test_terminal_manifest_family_cannot_fall_back_to_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, str]
) -> None:
    case = _case(tmp_path, monkeypatch, **change)
    entries, limitation, _ = _project(case)
    assert entries == ()
    assert limitation == "acquisition_action_history_integrity_not_established"
    assert case.calls == []


@pytest.mark.parametrize(
    "damage",
    ["foreign_profile", "missing_profile", "missing_manifest", "missing_blob", "missing_event"],
)
def test_terminal_requires_selected_manifest_content_and_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    case = _case(tmp_path, monkeypatch)
    if damage in {"foreign_profile", "missing_profile"}:
        foreign_profile = (
            _write_profile_variant(
                case.store,
                case.selected_ref,
                producer=ProducerInfo(
                    component="polisyos.runtime.acquisition_route_loop", version="foreign"
                ),
            ).manifest_profile_sha256
            if damage == "foreign_profile"
            else None
        )
        changed = replace(
            case.head,
            receipt_manifest_profile_sha256=foreign_profile,
        )
        monkeypatch.setattr(
            case.database, "list_acquisition_action_heads_for_source", lambda **_kwargs: (changed,)
        )
    elif damage == "missing_manifest":
        case.store._manifest_path_for_ref(
            case.selected_ref.artifact_id, case.selected_ref.manifest_profile_sha256
        ).unlink()
    elif damage == "missing_blob":
        case.store._paths(case.selected_ref.artifact_id)[0].unlink()
    else:
        # Remove the actual durable event in the disposable fixture DB only.
        with sqlite3.connect(case.service._resolve_control_sqlite_path()) as connection:
            connection.execute(
                "DELETE FROM control_diagnostic_events WHERE event_id = ?",
                (case.head.durable_event_id,),
            )
    entries, limitation, _ = _project(case)
    assert entries == ()
    assert limitation == "acquisition_action_history_integrity_not_established"
    assert case.calls == []


@pytest.mark.parametrize("epoch", ["1.0", "2.0"])
def test_verified_blocked_terminal_is_an_explicit_projection_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, epoch: str
) -> None:
    case = _case(tmp_path, monkeypatch, epoch=epoch, blocked=True)
    entries, limitation, _ = _project(case)
    assert entries == ()
    assert limitation == "acquisition_action_history_terminal_projection_unavailable"
    assert case.calls == [case.selected_ref]
    restored = RunDetails.model_validate_json(
        _run_details(case, entries, limitation).model_dump_json()
    )
    assert restored.candidate_simulation.acquisition_history == ()
    assert restored.candidate_simulation.acquisition_history_limitation_code == limitation
    assert restored.candidate_simulation.publication_authority is False


@pytest.mark.parametrize("epoch", ["1.0", "2.0"])
def test_verified_blocked_terminal_preserves_earlier_history_in_run_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, epoch: str
) -> None:
    earlier = _case(tmp_path, monkeypatch)
    blocked = _case(tmp_path, monkeypatch, epoch=epoch, blocked=True, previous=earlier)
    entries, limitation, _ = _project(blocked)
    assert len(entries) == 1
    assert entries[0].route_receipt_ref == earlier.selected_ref
    assert limitation == "acquisition_action_history_terminal_projection_unavailable"
    assert blocked.calls == [earlier.selected_ref, blocked.selected_ref]
    restored = RunDetails.model_validate_json(
        _run_details(blocked, entries, limitation).model_dump_json()
    )
    projection = restored.candidate_simulation
    assert projection.acquisition_history == entries
    assert projection.acquisition_history_limitation_code == limitation
    assert projection.publication_authority is False
    assert all(row.publication_authority is False for row in projection.acquisition_history)


def test_legacy_candidate_history_keeps_the_same_v5_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path, monkeypatch)
    projected, frontier = runs._candidate_terminal_history_v5_projection(
        verified=case.history,
        store=case.store,
        control_store=case.database,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    legacy = CandidateEvaluationTerminalHistory(
        head=case.head,
        terminal_ref=case.selected_ref,
        terminal=AcquisitionCandidateRouteLoopReceipt.model_validate(
            {
                **{
                    name: getattr(case.terminal, name)
                    for name in AcquisitionCandidateRouteLoopReceipt.model_fields
                    if hasattr(case.terminal, name)
                    and name not in {"schema_version", "compiled_ref"}
                },
                "schema_version": "AcquisitionRouteLoopReceipt@3.0",
                "compiled_ref": str(case.compiled_ref.artifact_id),
                "cost_basis_hash": _hash("0"),
                "decision_ref": _hash("1"),
            }
        ),
        action=None,
        decision=case.history.decision,
        current_basis=case.history.current_basis,
        selected_basis=case.history.selected_basis,
        evaluation=None,
        reentry=case.history.reentry,
        continuation=None,
        frontier=frontier,
    )
    old_projection, old_frontier = runs._candidate_terminal_history_v5_projection(
        verified=legacy,
        store=case.store,
        control_store=case.database,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    assert old_projection == projected and old_frontier == frontier
