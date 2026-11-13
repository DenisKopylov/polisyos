"""Candidate experiment phase persistence refuses incomplete owner composition."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    ArtifactWriteOptions,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control.run_lifecycle import (
    AcquisitionRouteLoopAuthoritySink,
    _read_verified_acquisition_action_phase,
)
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
    AcquisitionCandidateExperimentTerminalReceiptV2,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.diagnostic_events import load_diagnostic_event_type_registry
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import LoopVOIDecision


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


def _ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_hash(digit),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_hash("f"),
    )


def _phase() -> AcquisitionCandidateExperimentPhaseReceipt:
    scope = CandidateUnpricedPolicyScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        design_problem_ref=_hash("1"),
        design_problem_basis_ref=_hash("2"),
        source_cycle_index=0,
        candidate_id="candidate-a",
        candidate_content_hash=_hash("3"),
        requirement_id="requirement-a",
        compiled_requirement_ref="compiled-requirement-a",
        candidate_digest=_hash("4"),
        planner_report_hash=_hash("5"),
        compiled_ref=_ref("runtime.compiled_recursive_generation_cycle", "6"),
        planner_report_ref=_ref("runtime.acquisition_planner_report", "7"),
        compiler_report_ref=_ref("runtime.data_requirement_compilation_report", "8"),
        configured_port_source_ref=_ref("runtime.quality.n7_configured_candidate_port_source", "9"),
    )
    return AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        {
            "receipt_id": "action-a.requested",
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "run_id": "run-a",
            "source_job_id": "source-a",
            "route_id": _hash("a"),
            "action_generation": 1,
            "job_id": "action-a",
            "source_payload_ref": _hash("b"),
            "capability_manifest_ref": _hash("c"),
            "request_content_hash": _hash("d"),
            "policy_scope": scope,
            "policy_ref": _ref("runtime_quality.candidate_unpriced_acquisition_policy", "e"),
            "authority_decision_ref": _ref("runtime_quality.agent_action_authority_decision", "0"),
            "voi_decision": LoopVOIDecision(
                candidate_id="candidate-a",
                terminal_kind="human_decision_required",
                scheduler_action="reject",
                scheduler_reason="roi_below_threshold",
                priority=0.0,
                next_action="escalate",
                reason="roi_below_threshold",
            ),
            "coarse_phase": "requested",
            "receipt_phase": "requested",
            "recovery_state": "none",
            "generated_at": datetime(2026, 11, 4, tzinfo=UTC),
        }
    )


def test_empty_experiment_history_is_empty_and_requested_phase_requires_atomic_publish(
    tmp_path: Path,
) -> None:
    """A typed phase cannot become a head without the real source and PA2 owners."""
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=database, artifact_store=artifact_store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=database,
    )
    phase = _phase()

    assert (
        sink.experiment_action_outcomes(
            tenant_id=phase.tenant_id,
            cell_id=phase.cell_id,
            run_id=phase.run_id,
            source_job_id=phase.source_job_id,
            route_id=phase.route_id,
        )
        == ()
    )
    with pytest.raises(
        ValueError, match="candidate_experiment_requested_phase_requires_atomic_job_publish"
    ):
        sink.persist_experiment_phase(phase)
    assert sink.get_head(phase) is None
    assert event_log.list_events(run_id=phase.run_id, job_id=phase.job_id, limit=10) == []


def test_candidate_experiment_phase_event_is_registered_as_cas_authority() -> None:
    contract = load_diagnostic_event_type_registry().event_types[
        "polisyos.runtime.acquisition.candidate_experiment_phase.v1"
    ]
    assert contract.category == "acquisition_candidate_experiment_phase"
    assert contract.allowed_event_sources == ("polisyos.runtime.quality.acquisition_route_loop",)
    assert contract.authority_role == "runtime_authority"
    assert contract.payload_ref_policy == "cas_required"
    assert contract.phase_required is contract.producer_required is True
    assert contract.serious_no_sampling is True


def test_terminal_recovery_counts_selected_profiles_instead_of_inventory_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A default alias can repeat one profile while a second profile remains ambiguous."""
    phase = _phase()
    pending_ref = _hash("a")
    action = _ref("runtime_quality.acquisition_candidate_action_receipt", "b")
    blocker = _ref("runtime_quality.acquisition_evaluation_decision", "c")
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_validate(
        {
            **phase.model_dump(
                exclude={
                    "schema_version",
                    "coarse_phase",
                    "receipt_phase",
                    "recovery_state",
                    "candidate_receipt_ref",
                }
            ),
            "receipt_id": "action-a.terminal",
            "predecessor_receipt_ref": pending_ref,
            "owner_receipt_refs": (str(action.artifact_id), str(blocker.artifact_id)),
            "terminal_outcome": "candidate_blocked",
            "candidate_action_ref": action,
            "blocker_ref": blocker,
            "blocker_reason": "test blocked",
        }
    )
    head = AcquisitionActionHeadRecord(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        route_id=phase.route_id,
        action_generation=phase.action_generation,
        head_generation=4,
        receipt_ref=pending_ref,
        receipt_sha256=pending_ref.removeprefix("sha256:"),
        durable_event_id="event-a",
        coarse_phase="executing",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        job_id=phase.job_id,
        predecessor_receipt_ref=_hash("d"),
        created_at=phase.generated_at,
    )
    owner = cast(
        "dispatch.CandidateExperimentReentryOwner",
        object.__new__(dispatch.CandidateExperimentReentryOwner),
    )
    object.__setattr__(owner, "terminal", terminal)
    object.__setattr__(owner, "predecessor_head", head)
    monkeypatch.setattr(AcquisitionRouteLoopAuthoritySink, "get_head", lambda *_: head)
    monkeypatch.setattr(dispatch, "_revalidate_candidate_experiment_reentry_owner", lambda _: None)

    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    store = FileSystemCAS(tmp_path / "cas").for_tenant(phase.tenant_id, cell_id=phase.cell_id)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store,
        event_log=RuntimeDiagnosticEventLog(store=database, artifact_store=store),
        control_store=database,
    )
    closure = ArtifactSameInputClosureInfo(
        closure_id=f"acquisition-route:{terminal.receipt_id}",
        status="closed",
        closure_sha256="1" * 64,
        run_id=phase.run_id,
        job_id=phase.job_id,
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
    )
    options = ArtifactWriteOptions(
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        schema=SchemaInfo(
            name="polisyos.runtime.AcquisitionCandidateExperimentTerminalReceipt", version="1.0"
        ),
        producer=ProducerInfo(
            component="polisyos.runtime.acquisition_route_loop", version="2026.08.28+ds15-c02"
        ),
        tenant_context=ArtifactTenantContextInfo(tenant_id=phase.tenant_id, cell_id=phase.cell_id),
        same_input_closure=closure,
    )
    payload = terminal.model_dump(mode="json")
    canon = CanonSpec(forbid_floats=False)
    selected = store.put_json(payload, options, canon, return_selected_profile=True)
    monkeypatch.setattr(
        RuntimeDiagnosticEventLog,
        "list_events",
        lambda *_args, **_kwargs: (
            SimpleNamespace(event=SimpleNamespace(payload_ref=str(selected.artifact_id))),
        ),
    )
    inventory = store.inventory_snapshot(artifact_id=selected.artifact_id)
    assert inventory.verdict == "pass" and len(inventory.entries) == 2
    assert {
        artifact_ref_identity_key(artifact_ref_for_manifest(entry.manifest))
        for entry in inventory.entries
    } == {artifact_ref_identity_key(selected)}
    # The intentionally unsigned fixture reaches the later authority check.
    with pytest.raises(
        ValueError, match=r"^candidate_experiment_terminal_recovery_authority_missing$"
    ):
        sink.recover_candidate_experiment_terminal(terminal, predecessor_head=head, owner=owner)

    alternate = store.put_json(
        payload,
        replace(
            options, same_input_closure=closure.model_copy(update={"closure_sha256": "2" * 64})
        ),
        canon,
        return_selected_profile=True,
    )
    assert alternate.artifact_id == selected.artifact_id
    assert alternate.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(
        ValueError, match=r"^candidate_experiment_terminal_recovery_cas_not_unique$"
    ):
        sink.recover_candidate_experiment_terminal(terminal, predecessor_head=head, owner=owner)


def _reuse_terminal(occurrence: ArtifactRef) -> AcquisitionCandidateExperimentTerminalReceiptV2:
    """Build a candidate-only blocked terminal, without asserting effect authority."""
    phase = _phase()
    action = _ref("runtime_quality.acquisition_candidate_action_receipt", "b")
    blocker = _ref("runtime_quality.acquisition_evaluation_decision", "c")
    return AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(
        {
            **phase.model_dump(
                exclude={
                    "schema_version",
                    "coarse_phase",
                    "receipt_phase",
                    "recovery_state",
                    "candidate_receipt_ref",
                }
            ),
            "schema_version": "AcquisitionCandidateExperimentTerminalReceipt@2.0",
            "receipt_id": "action-a.reuse-terminal",
            "predecessor_receipt_ref": _hash("a"),
            "owner_receipt_refs": (
                str(action.artifact_id),
                str(blocker.artifact_id),
                str(occurrence.artifact_id),
            ),
            "terminal_outcome": "candidate_blocked",
            "candidate_action_ref": action,
            "blocker_ref": blocker,
            "blocker_reason": "test blocked",
            "reuse_occurrence_ref": occurrence,
        }
    )


def _reuse_event_inputs(
    receipt: AcquisitionCandidateExperimentTerminalReceiptV2,
) -> tuple[str, ...]:
    """Spell out this fixture's lineage independently of the production walker."""
    scope = receipt.policy_scope
    return tuple(
        sorted(
            {
                *receipt.owner_receipt_refs,
                receipt.predecessor_receipt_ref,
                receipt.source_payload_ref,
                receipt.capability_manifest_ref,
                str(receipt.policy_ref.artifact_id),
                str(receipt.authority_decision_ref.artifact_id),
                str(scope.compiled_ref.artifact_id),
                str(scope.planner_report_ref.artifact_id),
                str(scope.compiler_report_ref.artifact_id),
                str(scope.configured_port_source_ref.artifact_id),
            }
        )
    )


def test_reuse_terminal_is_a_distinct_executing_transition_with_exact_action_identity() -> None:
    phase = _phase()
    terminal = _reuse_terminal(_ref("runtime_quality.candidate_experiment_reuse_occurrence", "d"))
    assert AcquisitionRouteLoopAuthoritySink._allowed_predecessor_phases(terminal) == frozenset(
        {"executing"}
    )
    assert AcquisitionRouteLoopAuthoritySink._same_action_identity(phase, terminal)

    wrong_authority = terminal.model_copy(
        update={
            "authority_decision_ref": terminal.authority_decision_ref.model_copy(
                update={"manifest_profile_sha256": _hash("e")}
            )
        }
    )
    assert not AcquisitionRouteLoopAuthoritySink._same_action_identity(phase, wrong_authority)
    wrong_job = terminal.model_copy(update={"job_id": "another-action"})
    assert not AcquisitionRouteLoopAuthoritySink._same_action_identity(phase, wrong_job)
    legacy = AcquisitionCandidateExperimentTerminalReceipt.model_validate(
        terminal.model_dump(exclude={"schema_version", "reuse_occurrence_ref"})
    )
    assert AcquisitionRouteLoopAuthoritySink._allowed_predecessor_phases(legacy) == frozenset(
        {"candidate_input_reentry_pending"}
    )


def test_reuse_terminal_cannot_publish_without_live_owner(tmp_path: Path) -> None:
    terminal = _reuse_terminal(_ref("runtime_quality.candidate_experiment_reuse_occurrence", "d"))
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    store = FileSystemCAS(tmp_path / "cas").for_tenant(terminal.tenant_id, cell_id=terminal.cell_id)
    event_log = RuntimeDiagnosticEventLog(store=database, artifact_store=store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store, event_log=event_log, control_store=database
    )
    before = {path for path in (tmp_path / "cas").rglob("*") if path.is_file()}
    with pytest.raises(
        ValueError, match="candidate_experiment_reuse_terminal_owner_not_established"
    ):
        sink.persist_terminal(terminal)
    with pytest.raises(
        ValueError, match="candidate_experiment_reuse_terminal_owner_not_established"
    ):
        sink._persist_terminal_receipt(terminal)

    class _UntrustedReuseSubclass(AcquisitionCandidateExperimentTerminalReceiptV2):
        pass

    subclass = _UntrustedReuseSubclass.model_validate(terminal.model_dump())
    with pytest.raises(
        ValueError, match="candidate_experiment_reuse_terminal_owner_not_established"
    ):
        sink._persist_terminal_receipt(subclass)
    assert sink.get_head(terminal) is None
    assert event_log.list_events(run_id=terminal.run_id, job_id=terminal.job_id, limit=10) == []
    assert {path for path in (tmp_path / "cas").rglob("*") if path.is_file()} == before


@pytest.mark.parametrize(
    "corruption",
    [
        None,
        "missing_role",
        "wrong_role",
        "wrong_profile",
        "missing_event_input",
        "wrong_event_predecessor",
    ],
)
def test_reuse_terminal_reader_requires_exact_occurrence_edge_and_event_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str | None
) -> None:
    """Selected bytes/event can be read, but wire support alone never makes a head current."""
    phase = _phase()
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    store = FileSystemCAS(tmp_path / "cas").for_tenant(phase.tenant_id, cell_id=phase.cell_id)
    event_log = RuntimeDiagnosticEventLog(store=database, artifact_store=store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store, event_log=event_log, control_store=database
    )
    occurrence_options = ArtifactWriteOptions(
        kind="runtime_quality.candidate_experiment_reuse_occurrence",
        media_type="application/json",
        schema=SchemaInfo(name="test.occurrence", version="1.0"),
        producer=ProducerInfo(component="test.occurrence", version="1"),
    )
    occurrence = store.put_json(
        {"selected": "same content"}, occurrence_options, return_selected_profile=True
    )
    alternate = store.put_json(
        {"selected": "same content"},
        replace(
            occurrence_options, producer=ProducerInfo(component="test.occurrence", version="2")
        ),
        return_selected_profile=True,
    )
    assert occurrence.artifact_id == alternate.artifact_id
    assert occurrence.manifest_profile_sha256 != alternate.manifest_profile_sha256
    terminal = _reuse_terminal(occurrence)
    input_ref = input_ref_from_artifact_ref(
        alternate if corruption == "wrong_profile" else occurrence,
        role=(
            "unexpected_role"
            if corruption == "wrong_role"
            else "candidate_experiment_reuse_occurrence"
        ),
    )
    manifest_inputs: list[InputRef] = [] if corruption == "missing_role" else [input_ref]
    event_inputs = _reuse_event_inputs(terminal)
    if corruption == "missing_event_input":
        event_inputs = tuple(
            ref for ref in event_inputs if ref != str(terminal.authority_decision_ref.artifact_id)
        )
    generated_at = terminal.generated_at.isoformat()
    result = write_runtime_authority_artifact(
        store,
        event_log,
        terminal.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="runtime_quality.acquisition_route_loop_receipt",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.AcquisitionCandidateExperimentTerminalReceipt", version="2.0"
            ),
            producer=ProducerInfo(
                component="polisyos.runtime.acquisition_route_loop", version="2026.08.28+ds15-c02"
            ),
            governance=ArtifactGovernanceInfo(classification="internal"),
            inputs=manifest_inputs,
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
        generated_at=generated_at,
        as_of_time=generated_at,
        same_input_closure={
            "closure_id": f"acquisition-route:{terminal.receipt_id}",
            "status": "closed",
            "run_id": terminal.run_id,
            "job_id": terminal.job_id,
            "tenant_id": terminal.tenant_id,
            "cell_id": terminal.cell_id,
            "evidence_input_refs": event_inputs,
            "closure_sha256": terminal.route_id,
        },
        input_refs=event_inputs,
        effective_mode_ref=terminal.route_id,
        degradation_ledger_ref=None,
        semantic_binding_ref=str(terminal.authority_decision_ref.artifact_id),
        validation_status="pass",
        blocking_status="blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime.acquisition_route_loop",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="pa2_ds9_decision_required",
        ),
        event_id="evt_acquisition_1_experiment_reuse_terminal_test",
        event_source="polisyos.runtime.quality.acquisition_route_loop",
        event_type="polisyos.runtime.acquisition.candidate_experiment_terminal.v1",
        event_subject=f"run/{terminal.run_id}/job/{terminal.job_id}/acquisition/terminal",
        state_before=(
            "outcome_selected" if corruption == "wrong_event_predecessor" else "executing"
        ),
        state_after="terminal",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected = result.cas_ref
    if corruption is not None:
        error = (
            "acquisition_action_phase_event_binding_mismatch"
            if corruption in {"missing_event_input", "wrong_event_predecessor"}
            else "candidate_experiment_reuse_terminal_occurrence_manifest_mismatch"
        )
        with pytest.raises(ValueError, match=error):
            sink._read_verified_action_phase(str(selected.artifact_id), selected_ref=selected)
        with pytest.raises(ValueError, match=error):
            _read_verified_acquisition_action_phase(
                artifact_store=store,
                event_log=event_log,
                receipt_ref=str(selected.artifact_id),
                selected_ref=selected,
            )
        return

    verified = sink._read_verified_action_phase(str(selected.artifact_id), selected_ref=selected)
    assert verified == _read_verified_acquisition_action_phase(
        artifact_store=store,
        event_log=event_log,
        receipt_ref=str(selected.artifact_id),
        selected_ref=selected,
    )
    assert verified.receipt == terminal
    assert verified.event.state_before == "executing"
    with pytest.raises(ValueError, match="candidate_experiment_reuse_terminal_profile_required"):
        sink._read_verified_action_phase(str(selected.artifact_id))
    head = AcquisitionActionHeadRecord(
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=terminal.run_id,
        source_job_id=terminal.source_job_id,
        route_id=terminal.route_id,
        action_generation=terminal.action_generation,
        head_generation=3,
        receipt_ref=str(selected.artifact_id),
        receipt_sha256=str(selected.artifact_id),
        receipt_manifest_profile_sha256=selected.manifest_profile_sha256,
        durable_event_id=verified.durable_event_id,
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=terminal.job_id,
        predecessor_receipt_ref=terminal.predecessor_receipt_ref,
        created_at=terminal.generated_at,
    )
    # Even a selected event and simulated matching SQL head are not a history owner.
    monkeypatch.setattr(
        ControlPlaneStore, "get_acquisition_action_head", lambda *_args, **_kwargs: head
    )
    with pytest.raises(
        ValueError, match="candidate_experiment_terminal_history_owner_not_established"
    ):
        sink.verify_action_head(head)
