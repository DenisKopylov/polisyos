"""Candidate experiment phase persistence refuses incomplete owner composition."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    ArtifactWriteOptions,
    FileSystemCAS,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control.run_lifecycle import (
    AcquisitionRouteLoopAuthoritySink,
)
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
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
