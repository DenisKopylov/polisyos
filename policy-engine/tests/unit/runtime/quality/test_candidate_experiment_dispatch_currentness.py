"""Keep candidate-experiment reentry bound to its selected phase and live job."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmission,
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionCandidateSourceRoute,
)
from polisyos.runtime.quality.candidate_acquisition_action import (
    CANDIDATE_ACTION_KIND,
    CandidateAcquisitionActionReceipt,
)
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _requested_phase,
)


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


def _selected_ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_hash(digit),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_hash("f"),
    )


def _reentry_receipts() -> tuple[
    AcquisitionCandidateExperimentPhaseReceipt,
    CandidateAcquisitionActionReceipt,
    ArtifactRef,
]:
    action_ref = _selected_ref(CANDIDATE_ACTION_KIND, "5")
    phase_ref = _selected_ref("runtime_quality.acquisition_candidate_experiment_phase_receipt", "6")
    phase_values = _requested_phase().model_dump(mode="python")
    phase_values.update(
        receipt_id="action-a.pending",
        predecessor_receipt_ref=_hash("e"),
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        owner_receipt_refs=(str(action_ref.artifact_id),),
        candidate_receipt_ref=action_ref,
    )
    phase = AcquisitionCandidateExperimentPhaseReceipt.model_validate(phase_values)
    selection = AcquisitionCandidateSourceRoute(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        route_id=phase.route_id,
        design_problem_ref=phase.policy_scope.design_problem_ref,
        compiled_requirement_ref=phase.policy_scope.compiled_requirement_ref,
        requirement_id=phase.policy_scope.requirement_id,
        candidate_digest=phase.policy_scope.candidate_digest,
        profile_selection_ref=_hash("7"),
        canonical_variable_id="global.unemployment_rate",
        target_slot_id="global.unemployment_rate",
        country_code="USA",
        year=2024,
        population="labor",
        reentry_budget_usd=Decimal("1.00"),
    )
    action = CandidateAcquisitionActionReceipt(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        action_job_id=phase.job_id,
        action_generation=phase.action_generation,
        action_attempt=1,
        selection=selection,
        candidate_budget_window_id="1" * 64,
        candidate_budget_window_digest="2" * 64,
        route_id=phase.route_id,
        action_phase_ref=str(phase_ref.artifact_id),
        selected_action_phase_ref=phase_ref,
        decision_ref=str(phase.authority_decision_ref.artifact_id),
        route_binding_id="component-binding",
        route_binding={"component_only": True},
        attempt_id="component-attempt",
        compiled_requirement_ref=selection.compiled_requirement_ref,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
        profile_selection_ref=selection.profile_selection_ref,
        canonical_variable_id=selection.canonical_variable_id,
        target_slot_id=selection.target_slot_id,
        candidate_source_ref=_selected_ref("runtime.quality.candidate_acquisition_source", "8"),
        compiler_report_ref=phase.policy_scope.compiler_report_ref,
        limitations=("component_only_no_live_effect",),
    )
    return phase, action, phase_ref


def _create_job(
    store: ControlPlaneStore,
    *,
    job_id: str,
    running: bool,
) -> ControlJobRecord | ControlJobExecutionAdmission:
    run_id = "run-a"
    actor = "actor-a"
    payload_ref = _hash("1")
    manifest_ref = _hash("2")
    scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "actor_subject": actor,
        "actor_authenticated": True,
        "actor_roles": ["operator"],
    }
    creation_event = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": "acquisition",
        "pipeline_id": None,
        "payload_ref": payload_ref,
        "submitted_by": actor,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {},
        "capability_manifest_ref": manifest_ref,
        "execution_scope": scope,
    }
    created = store.create_job(
        job_id=job_id,
        kind="acquisition",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=manifest_ref,
        payload_ref=payload_ref,
        submitted_by=actor,
        creation_event_payload=creation_event,
    )
    if not running:
        return created

    worker_id = f"worker-{job_id}"
    store.mark_running(job_id=job_id, worker_id=worker_id, lease_seconds=120)
    leased = store.get_job(job_id)
    assert leased is not None and leased.state == "running"
    with store.job_execution_fence(
        job_id=job_id,
        worker_id=worker_id,
        attempt=leased.attempt,
    ):
        admission = store.current_execution_job_admission()
    return admission


def test_reentry_action_matches_selected_phase_generation_and_real_live_job(
    tmp_path: Path,
) -> None:
    """Use the phase generation; ControlJobRecord has no action_generation field."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    try:
        live_admission = _create_job(store, job_id="action-a", running=True)
        assert type(live_admission) is ControlJobExecutionAdmission
        job = live_admission.job
        assert type(job) is ControlJobRecord
        assert not hasattr(job, "action_generation")

        phase, action, phase_ref = _reentry_receipts()
        assert dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )

        action_at_other_generation = CandidateAcquisitionActionReceipt.model_validate(
            {**action.model_dump(mode="python"), "action_generation": 2}
        )
        phase_at_other_generation = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
            {**phase.model_dump(mode="python"), "action_generation": 2}
        )
        phase_for_other_job = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
            {**phase.model_dump(mode="python"), "job_id": "action-other"}
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action_at_other_generation,
            phase=phase,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase_at_other_generation,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=job,
            selected_action_phase_ref=_hash("9"),
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase_for_other_job,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )

        pending_job = _create_job(store, job_id="action-pending", running=False)
        assert type(pending_job) is ControlJobRecord and pending_job.state == "pending"
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=pending_job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )

        foreign_admission = _create_job(store, job_id="action-foreign", running=True)
        assert type(foreign_admission) is ControlJobExecutionAdmission
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=foreign_admission.job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )
    finally:
        store.close()
