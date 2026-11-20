"""Native checkpoint selection through real CAS, diagnostic and Control owners.

The upstream Native world/source and physical-result owners are outside this
component fixture. It proves selected recording, lease boundaries and incomplete
claim policy, not a completed Native continuation or an independent N5 result.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlJobExecutionAdmissionError,
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.quality import native_source_reentry_history as history
from polisyos.runtime.quality.candidate_source_reentry_history import _n5_checkpoint_event
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    CandidateSummary,
)
from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_action_job
from tests.unit.runtime.quality.test_native_derivation_action_history import _native_requested


@dataclass(frozen=True)
class _Case:
    cas: artifacts.FileSystemCAS
    events: RuntimeDiagnosticEventLog
    control: ControlPlaneStore
    head: AcquisitionActionHeadRecord
    worker: str
    attempt: int
    prepared: history.NativeSourceReentryPrepared

    def fence(self) -> object:
        return self.control.job_execution_fence(
            job_id=self.head.job_id, worker_id=self.worker, attempt=self.attempt
        )


def _parent(cas: artifacts.FileSystemCAS, kind: str, name: str) -> artifacts.ArtifactRef:
    return cas.put_json(
        {"test_owned_input": name, "authority_purpose": "candidate_only"},
        artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
        return_selected_profile=True,
    )


@pytest.fixture
def selected_case(tmp_path: Path) -> _Case:
    """Supply real selection owners; Native semantic parents are test-owned inputs."""
    cas = artifacts.FileSystemCAS(tmp_path / "cas")
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    ) as control:
        requested = _native_requested(cas, index=1, now=datetime.now(UTC))
        job, worker, attempt = _create_action_job(control, job_id=requested.job_id)
        events = RuntimeDiagnosticEventLog(store=control, artifact_store=cas)
        owner_output = _parent(cas, "test.native_owner_output", "selected owner boundary")
        with control.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):

            def append_test_owned_phase(
                phase: object, generation: int
            ) -> AcquisitionActionHeadRecord:
                # This typed parent is an opaque upstream boundary. Calling the
                # full route AuthoritySink here would also require actual provider
                # outcome/activation proof, outside this recording-owner test.
                ref = cas.put_json(
                    phase.model_dump(mode="json"),
                    artifacts.ArtifactWriteOptions(
                        kind="runtime_quality.acquisition_route_phase_receipt",
                        media_type="application/json",
                        schema=artifacts.SchemaInfo(
                            name="polisyos.runtime.AcquisitionRoutePhaseReceipt", version="1.3"
                        ),
                    ),
                    history._CANON,
                    return_selected_profile=True,
                )
                return control.advance_acquisition_action_head(
                    tenant_id=phase.tenant_id,
                    cell_id=phase.cell_id,
                    run_id=phase.run_id,
                    source_job_id=phase.source_job_id,
                    route_id=phase.route_id,
                    action_generation=phase.action_generation,
                    expected_head_generation=generation,
                    receipt_ref=str(ref.artifact_id),
                    receipt_sha256=str(ref.artifact_id),
                    durable_event_id=f"test-owned-phase-{generation}",
                    coarse_phase=phase.coarse_phase,
                    receipt_phase=phase.receipt_phase,
                    recovery_state=phase.recovery_state,
                    job_id=phase.job_id,
                    predecessor_receipt_ref=phase.predecessor_receipt_ref,
                    receipt_manifest_profile_sha256=ref.manifest_profile_sha256,
                )

            head = append_test_owned_phase(requested, 0)
            for index, phase in enumerate(
                ("executing", "outcome_selected", "world_committed_reentry_pending"), start=1
            ):
                pending_phase = type(requested).model_validate(
                    {
                        **requested.model_dump(mode="python"),
                        "receipt_id": f"{job.job_id}.{phase}",
                        "receipt_phase": phase,
                        "coarse_phase": "world_committed" if index == 3 else "executing",
                        "recovery_state": "reentry_recovery_required" if index == 3 else "none",
                        "predecessor_receipt_ref": head.receipt_ref,
                        "owner_receipt_refs": (str(owner_output.artifact_id),) if index > 1 else (),
                        "generated_at": requested.generated_at + timedelta(microseconds=index),
                    }
                )
                head = append_test_owned_phase(pending_phase, index)
        pending = artifacts.ArtifactRef(
            artifact_id=head.receipt_ref,
            kind="runtime_quality.acquisition_route_phase_receipt",
            media_type="application/json",
            manifest_profile_sha256=head.receipt_manifest_profile_sha256,
        )
        subject = history.NativeSourceReentrySubject(
            pending_action_ref=pending,
            native_world_checkpoint_ref=_parent(
                cas, "runtime_quality.native_derivation_world_checkpoint", "world"
            ),
            native_input_collection_ref=_parent(
                cas, "runtime_quality.native_derivation_input_collection", "collection"
            ),
            original_generic_input_ref=_parent(
                cas, "runtime.quality.generic_cycle_simulation_n5_input", "original input"
            ),
            original_profile_ref=_parent(
                cas, "runtime.quality.generic_cycle_simulation_profile", "original profile"
            ),
            context_job_ref=_parent(
                cas, "runtime.quality.cycle_substrate_context_job", "current context"
            ),
            original_profile_selection_ref="sha256:" + "4" * 64,
            current_profile_selection_ref="sha256:" + "5" * 64,
            originating_attempt=attempt,
            execution_profile=job.effective_execution_profile,
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            source_job_id=head.source_job_id,
            action_job_id=head.job_id,
            action_generation=head.action_generation,
            route_id=head.route_id,
            source_run_id="generation_run",
            stable_design_problem_ref="sha256:" + "6" * 64,
            design_problem_ref="sha256:" + "7" * 64,
            cycle_index=1,
        )
        grounding = CandidateGroundingObservation(
            candidate_id="candidate-a",
            status="grounding_unavailable",
            grounding_score=0.0,
        )
        summary = CandidateSummary(
            candidate_id="candidate-a",
            content_hash="sha256:" + "8" * 64,
            cycle_index=1,
            proxy_score=0.5,
            voi_estimate=1.0,
            grounding_status="grounding_unavailable",
            grounding_score=0.0,
            current_valid=False,
            front="research",
            high_proxy=False,
            low_grounding=True,
        )
        schedule = SchedulingDecision.model_validate(
            {
                "candidate_id": "candidate-a",
                "priority": 1.0,
                "recommended_action": "advance",
                "reason": "test-owned completed scheduling",
                "economics": {
                    "candidate_id": "candidate-a",
                    "recommended_action": "advance",
                    "expected_improvement_per_usd": 1.0,
                    "expected_falsification_value": 0.0,
                    "expected_governance_value": 0.0,
                    "timeout_risk": 0.0,
                    "replay_cost_usd": 0.0,
                    "calibration_debt": 0.0,
                    "current_pareto_position": "unassessed",
                },
            }
        )
        prepared = history.NativeSourceReentryPrepared(
            subject=subject,
            n4_source_ref=_parent(cas, "runtime.generation_source_handoff", "n4"),
            n5_input_ref=_parent(
                cas, "runtime.quality.generic_cycle_simulation_n5_input", "actual input"
            ),
            candidate_id="candidate-a",
            candidate_content_hash=summary.content_hash,
            grounding_observations=(grounding,),
            candidate_summaries=(summary,),
            schedule=schedule,
        )
        yield _Case(
            cas,
            RuntimeDiagnosticEventLog(store=control, artifact_store=cas),
            control,
            head,
            worker,
            attempt,
            prepared,
        )


def _write(case: _Case, value: history._Member) -> artifacts.ArtifactRef:
    return case.cas.put_json(
        value.model_dump(mode="json"),
        history._options(value),
        history._CANON,
        return_selected_profile=True,
    )


def _event(
    case: _Case, ref: artifacts.ArtifactRef, value: history._Member, member: history.Member
) -> object:
    return _n5_checkpoint_event(
        head=case.head,
        ref=ref,
        options=history._options(value),
        event_id=history._event_id(value.subject, member),
        event_time=datetime.now(UTC),
        execution_profile=value.subject.execution_profile,
        phase=history._phase(member),
    )


def _select(case: _Case, value: history._Member, member: history.Member) -> artifacts.ArtifactRef:
    ref = _write(case, value)
    event = _event(case, ref, value, member)
    case.control.append_native_source_reentry_checkpoint(
        pending_head=case.head, prepared_event=case.events.prepare(event)
    )
    return ref


def _read(
    case: _Case,
    member: history.Member,
    *,
    store: artifacts.ArtifactStore | None = None,
    subject: history.NativeSourceReentrySubject | None = None,
) -> object:
    selected_store = case.cas if store is None else store
    return history.read_native_source_reentry_member(
        store=selected_store,
        events=RuntimeDiagnosticEventLog(store=case.control, artifact_store=selected_store),
        subject=case.prepared.subject if subject is None else subject,
        member=member,
    )


def _advance_test_terminal(case: _Case) -> None:
    """Publish an independently selected successor in the test SQL owner."""
    ref = _parent(case.cas, "test.native_terminal_owner", "successor")
    case.control.advance_acquisition_action_head(
        tenant_id=case.head.tenant_id,
        cell_id=case.head.cell_id,
        run_id=case.head.run_id,
        source_job_id=case.head.source_job_id,
        route_id=case.head.route_id,
        action_generation=case.head.action_generation,
        expected_head_generation=case.head.head_generation,
        receipt_ref=str(ref.artifact_id),
        receipt_sha256=str(ref.artifact_id),
        durable_event_id="test-terminal-successor",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=case.head.job_id,
        predecessor_receipt_ref=case.head.receipt_ref,
        receipt_manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _progress_under_selected_owner(
    case: _Case, monkeypatch: pytest.MonkeyPatch
) -> tuple[history.NativeSourceReentryCoordinator, list[AcquisitionActionHeadRecord]]:
    # Only the full upstream Native semantic sweep is substituted. Every
    # checkpoint read, diagnostic selection and current lease/head stays real.
    coordinator = object.__new__(history.NativeSourceReentryCoordinator)
    coordinator.bridge = SimpleNamespace(
        artifact_store=case.cas,
        event_log=case.events,
        control_store=case.control,
        _source_control_service=SimpleNamespace(_generic_cycle_simulation_admission_owner=None),
    )
    coordinator.closure = SimpleNamespace(generation_run=None)
    coordinator.handoff = SimpleNamespace(
        context=SimpleNamespace(world_model_record_content_hash="test-owned selected world")
    )
    observed = []

    def current(self):
        assert self is coordinator
        admission = case.control.current_execution_job_admission()
        head = case.control.get_acquisition_action_head(
            tenant_id=case.head.tenant_id,
            cell_id=case.head.cell_id,
            run_id=case.head.run_id,
            source_job_id=case.head.source_job_id,
            route_id=case.head.route_id,
            action_generation=case.head.action_generation,
        )
        assert head is not None
        observed.append(head)
        return head, case.prepared.subject.model_copy(
            update={"originating_attempt": admission.attempt}
        )

    monkeypatch.setattr(history.NativeSourceReentryCoordinator, "_current", current)
    return coordinator, observed


def test_native_generic_selection_reuse_requires_the_exact_live_route_and_bridge(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import native_generic_context
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteLoop,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        NativeDerivationWorldCheckpoint,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
        GenericCycleSimulationAdmissionOwner,
    )
    from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
        _linkage_problem,
    )

    case = selected_case
    subject = case.prepared.subject
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=case.cas)
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = case.cas
    bridge.control_store = case.control
    bridge.action_head_sink = SimpleNamespace(
        current_action_outcome=lambda **scope: SimpleNamespace(
            head=case.control.list_acquisition_action_heads(**scope)[-1]
        )
    )
    bridge._source_control_service = SimpleNamespace(
        _generic_cycle_simulation_admission_owner=owner,
        _control_store=case.control,
        _diagnostic_event_log=case.events,
        resolve_completed_control_job_core_run_source=lambda *args: None,
        acquisition_route_sink=None,
    )
    owner._native_world_action_owner = bridge._source_control_service
    problem = _linkage_problem()
    # Substitutes stop at the complete upstream route and World selection
    # owners. Lease admission and the exact binding between them remain real.
    closure = VerifiedAcquisitionRouteClosure.model_construct(
        tenant_id=subject.tenant_id,
        cell_id=subject.cell_id,
        run_id=subject.run_id,
        source_job_id=subject.source_job_id,
        route_id=subject.route_id,
        source_payload_ref="sha256:" + "a" * 64,
        generation_run=SimpleNamespace(
            run_id=subject.source_run_id, design_problem_ref=subject.stable_design_problem_ref
        ),
        source_cycle=SimpleNamespace(cycle_index=subject.cycle_index - 1),
    )
    checkpoint = SimpleNamespace(
        tenant_id=subject.tenant_id,
        cell_id=subject.cell_id,
        run_id=subject.run_id,
        action_job_id=subject.action_job_id,
        route_id=subject.route_id,
        source_job_id=subject.source_job_id,
        collection_refs=(subject.native_input_collection_ref,),
    )
    context = object()
    handoff = GenericCycleNativeWorldContextHandoffV1.model_construct(
        context=context,
        context_job_ref=subject.context_job_ref,
        profile=SimpleNamespace(profile_selection_ref=subject.original_profile_selection_ref),
        profile_ref=subject.original_profile_ref,
        native_world_checkpoint_ref=subject.native_world_checkpoint_ref,
        original_generic_input_ref=subject.original_generic_input_ref,
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_job_id=subject.source_job_id,
        job_id=subject.action_job_id,
        run_id=subject.run_id,
        tenant_id=subject.tenant_id,
        cell_id=subject.cell_id,
    )
    selected = SimpleNamespace(
        checkpoint=checkpoint,
        checkpoint_ref=subject.native_world_checkpoint_ref,
        pending_action_phase_ref=subject.pending_action_ref,
        original_generic_input_ref=subject.original_generic_input_ref,
        original_profile=handoff.profile,
        original_profile_ref=subject.original_profile_ref,
    )
    seen = []

    def resolve_route(self, *, run_id, route_id, action_job_id):
        assert (run_id, route_id, action_job_id) == (
            subject.run_id,
            subject.route_id,
            subject.action_job_id,
        )
        return closure

    def resolve_selection(self, actual_closure, actual_ref):
        assert self is bridge
        seen.append((actual_closure, actual_ref))
        return selected

    monkeypatch.setattr(native_generic_context, "_current_bridge", lambda actual: bridge)
    monkeypatch.setattr(NativeDerivationWorldCheckpoint, "model_validate", lambda _wire: checkpoint)
    monkeypatch.setattr(
        VerifiedAcquisitionRouteClosure, "design_problem_basis", property(lambda _: problem)
    )
    monkeypatch.setattr(AcquisitionRouteLoop, "resolve_current_route", resolve_route)
    monkeypatch.setattr(native_generic_context, "_context", lambda *_: context)
    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner,
        "resolve_for_current_job",
        lambda *_args, **_kwargs: handoff,
    )
    monkeypatch.setattr(
        AcquisitionWorldGrowthBridge, "resolve_native_derived_world_selection", resolve_selection
    )

    inputs = {"checkpoint_ref": subject.native_world_checkpoint_ref, "problem": problem}
    with case.fence():
        history.NativeSourceReentryCoordinator(
            bridge=bridge,
            closure=closure,
            handoff=handoff,
            collection_ref=subject.native_input_collection_ref,
        )
        assert seen == [(closure, subject.native_world_checkpoint_ref)]
        with pytest.raises(ValueError, match="generic_native_world_bridge_owner_mismatch"):
            native_generic_context._current_selection(
                owner,
                **inputs,
                expected_bridge=object.__new__(AcquisitionWorldGrowthBridge),
                expected_closure=closure,
            )
        changed = closure.model_copy(update={"source_payload_ref": "sha256:" + "b" * 64})
        with pytest.raises(ValueError, match="generic_native_world_current_route_changed"):
            native_generic_context._current_selection(
                owner,
                **inputs,
                expected_bridge=bridge,
                expected_closure=changed,
            )
    assert seen == [(closure, subject.native_world_checkpoint_ref)]


def test_native_progress_bounds_full_currentness_to_two_cuts(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, observed = _progress_under_selected_owner(selected_case, monkeypatch)
    with selected_case.fence():
        assert coordinator.progress() == history.NativeSourceReentryProgress()
    assert observed == [selected_case.head, selected_case.head]


@pytest.mark.parametrize("change", ["selected-event", "head", "lease"])
def test_native_progress_refuses_changed_observed_cut(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    case = selected_case
    coordinator, _observed = _progress_under_selected_owner(case, monkeypatch)
    verify = history._verify_native_source_reentry_progress

    def verify_then_change(**kwargs):
        result = verify(**kwargs)
        if change == "selected-event":
            assert _select(case, case.prepared, "prepared") is not None
        elif change == "head":
            _advance_test_terminal(case)
        else:
            with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
                connection.execute(
                    "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                    ("2000-01-01T00:00:00Z", case.head.job_id),
                )
        return result

    monkeypatch.setattr(history, "_verify_native_source_reentry_progress", verify_then_change)
    reason = {
        "selected-event": "native_reentry_checkpoint_selection_changed",
        "head": "native_reentry_current_head_changed",
        "lease": "lease is not current",
    }[change]
    try:
        with case.fence(), pytest.raises((ValueError, ControlJobLeaseLostError), match=reason):
            coordinator.progress()
    finally:
        if change == "selected-event":
            assert _read(case, "prepared")[1] == case.prepared


def test_native_progress_refuses_lease_expiry_after_final_source_read(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    case = selected_case
    coordinator, observed = _progress_under_selected_owner(case, monkeypatch)
    current = history.NativeSourceReentryCoordinator._current

    def check_then_expire(self):
        cut = current(self)
        if len(observed) == 2:
            with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
                connection.execute(
                    "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                    ("2000-01-01T00:00:00Z", case.head.job_id),
                )
        return cut

    monkeypatch.setattr(history.NativeSourceReentryCoordinator, "_current", check_then_expire)
    events_before = case.control.list_diagnostic_events(job_id=case.head.job_id)
    artifacts_before = tuple(case.cas.root.rglob("*.json"))
    with case.fence(), pytest.raises(ControlJobLeaseLostError, match="lease is not current"):
        coordinator.progress()
    assert observed == [case.head, case.head]
    assert case.control.list_diagnostic_events(job_id=case.head.job_id) == events_before
    assert tuple(case.cas.root.rglob("*.json")) == artifacts_before


def test_native_progress_refuses_sql_member_selected_during_final_source_read(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = selected_case
    coordinator, observed = _progress_under_selected_owner(case, monkeypatch)
    current = history.NativeSourceReentryCoordinator._current

    def check_then_select(self):
        cut = current(self)
        if len(observed) == 2:
            _select(case, case.prepared, "prepared")
        return cut

    monkeypatch.setattr(history.NativeSourceReentryCoordinator, "_current", check_then_select)
    with (
        case.fence(),
        pytest.raises(ValueError, match="native_reentry_checkpoint_selection_changed"),
    ):
        coordinator.progress()
    assert observed == [case.head, case.head]
    assert _read(case, "prepared")[1] == case.prepared


def _prepare_selected(case: _Case, coordinator: history.NativeSourceReentryCoordinator):
    value = case.prepared
    return coordinator.prepare(
        n4_source_ref=value.n4_source_ref,
        input_ref=value.n5_input_ref,
        candidate_id=value.candidate_id,
        candidate_hash=value.candidate_content_hash,
        grounding=value.grounding_observations,
        summaries=value.candidate_summaries,
        schedule=value.schedule,
    )


def test_native_transition_selects_five_members_under_three_full_cuts_each(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.generation_cycle import (
        AcquisitionOverlayReentryReceipt,
        GenerationCycleRecord,
        SimulationPortObservation,
    )
    from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import _v3_fixture

    case = selected_case
    coordinator, observed = _progress_under_selected_owner(case, monkeypatch)
    # This selection-owner fixture has no numerical producer. Supply shaped
    # external evidence and bound semantic verifier substitutes at that seam.
    checked = []
    monkeypatch.setattr(coordinator, "_verify_prepared", lambda value: checked.append(value))
    monkeypatch.setattr(coordinator, "_verify_n5", lambda *values: checked.append(values[-1]))
    monkeypatch.setattr(coordinator, "_verify_cycle", lambda *values: checked.append(values[-1]))
    value = case.prepared
    subject = value.subject
    simulation = SimulationPortObservation(
        candidate_id=value.candidate_id,
        status="joint_simulated",
        generic_n4_source_ref=value.n4_source_ref,
        generic_context_job_ref=subject.context_job_ref,
        generic_profile_ref=subject.original_profile_ref,
        generic_n5_input_ref=value.n5_input_ref,
        generic_profile_selection_ref=subject.original_profile_selection_ref,
        generic_n5_execution_ref=_parent(
            case.cas, "runtime.quality.generic_cycle_simulation_n5_execution", "N5 execution"
        ),
        simulation_result_ref=_parent(
            case.cas, "runtime.quality.joint_simulation_result", "N5 result"
        ),
    )
    digest = subject.stable_design_problem_ref
    _, fixture = _v3_fixture()
    receipt = AcquisitionOverlayReentryReceipt.issue(
        schema_version="policyos.runtime.acquisition_overlay_reentry.v1",
        source_run_id=subject.source_run_id,
        design_problem_ref=digest,
        source_cycle_index=0,
        source_candidate_ref=value.candidate_id,
        overlay_receipt_ref=digest,
        overlay_receipt_content_hash=digest,
        baseline_content_hash=digest,
        overlay_path="fixture-overlay",
        epoch_id=1,
        passport_id="fixture-passport",
        passport_variable_id="fixture-variable",
        admitted_observation_count=1,
        semantic_epoch_ref=digest,
        semantic_epoch_production_receipt_ref=digest,
        semantic_epoch_production_receipt_content_hash=digest,
        new_cycle=GenerationCycleRecord.model_validate(fixture["cycles"][0]),
        candidate_summaries=value.candidate_summaries,
    )

    with case.fence():
        prepared = _prepare_selected(case, coordinator)
        cuts = [len(observed)]
        coordinator.claim("n5_claimed", prepared)
        cuts.append(len(observed))
        n5_completed = coordinator.complete_n5(prepared, simulation)
        cuts.append(len(observed))
        coordinator.claim("tail_claimed", n5_completed)
        cuts.append(len(observed))
        cycle_completed = coordinator.complete_cycle(n5_completed, receipt)
        cuts.append(len(observed))

        selected = {
            key: _read(case, key)
            for key in ("prepared", "n5_claimed", "n5_completed", "tail_claimed", "cycle_completed")
        }
        ids = {history._event_id(subject, key) for key in selected}
        rows = case.control.list_diagnostic_events(job_id=case.head.job_id)
        assert {row.event.event_id for row in rows if row.event.event_id in ids} == ids
        assert selected["prepared"][0] == prepared
        assert selected["n5_claimed"][1].predecessor_ref == prepared
        assert selected["n5_completed"][0] == n5_completed
        assert selected["tail_claimed"][1].predecessor_ref == n5_completed
        assert selected["cycle_completed"][0] == cycle_completed
        assert checked == [
            selected[key][1] for key in ("prepared", "n5_completed", "cycle_completed")
        ]
    assert cuts == [3, 6, 9, 12, 15]


@pytest.mark.parametrize(
    "boundary", ["cas-put", "sql-append", "pre-member", "post-member", "progress-member"]
)
def test_native_transition_rechecks_actual_active_catalog_around_event(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    boundary: str,
) -> None:
    import duckdb

    from polisyos.data_forge.domains.catalog.knowledge.overlay import OverlayAdmissionError
    from tests._helpers.semantic_epoch_native import _real_epoch_scenario
    from tests.unit.runtime.quality.test_acquisition_executor import _activate_real_epoch_scenario

    case = selected_case
    coordinator, _observed = _progress_under_selected_owner(case, monkeypatch)
    monkeypatch.setattr(coordinator, "_verify_prepared", lambda _value: None)
    scenario = _real_epoch_scenario(tmp_path / "catalog-owner")
    _production, activation = _activate_real_epoch_scenario(scenario)
    epoch = (scenario.passport.epoch_id, scenario.passport.passport_id)
    current = history.NativeSourceReentryCoordinator._current
    saved = None
    target = "n5_claimed" if boundary == "pre-member" else "prepared"
    prepared = None
    if target == "n5_claimed":
        with case.fence():
            prepared = _select(case, case.prepared, "prepared")
    expect_selected = boundary in {"sql-append", "post-member"}
    staged = False
    appended = False
    post_reads = reads = 0

    def deactivate():
        nonlocal saved
        if saved is not None:
            return
        assert (_read(case, target) is not None) is expect_selected
        with duckdb.connect(str(scenario.overlay.overlay_path)) as connection:
            saved = connection.execute(
                "SELECT semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
                "FROM acquisition_epochs WHERE epoch_id = ? AND passport_id = ?",
                epoch,
            ).fetchone()
            connection.execute(
                "UPDATE acquisition_epochs SET epoch_activation_state = 'pending_epoch_activation', "
                "semantic_epoch_production_receipt_ref = NULL, activated_overlay_receipt_ref = NULL "
                "WHERE epoch_id = ? AND passport_id = ?",
                epoch,
            )

    put_json = case.cas.put_json
    append = case.control.append_native_source_reentry_checkpoint
    read = coordinator._read_selected

    def put_then_deactivate(*args, **kwargs):
        nonlocal staged
        ref = put_json(*args, **kwargs)
        if ref.kind == history._KIND:
            staged = True
            if boundary == "cas-put":
                deactivate()
        return ref

    def append_then_deactivate(**kwargs):
        nonlocal appended
        row = append(**kwargs)
        appended = True
        if boundary == "sql-append":
            deactivate()
        return row

    def read_then_deactivate(subject, member):
        nonlocal post_reads, reads
        selected = read(subject, member)
        reads += 1
        if appended:
            post_reads += 1
        if (
            (boundary == "pre-member" and staged and not appended and member == "prepared")
            or (boundary == "post-member" and post_reads == 2)
            or (boundary == "progress-member" and reads == 10)
        ):
            if boundary in {"pre-member", "post-member"}:
                assert selected is not None and selected[0].manifest_profile_sha256 is not None
            deactivate()
        return selected

    def check_current(self):
        scenario.overlay.read_activated_semantic_epoch_observations(
            receipt_ref=activation.receipt_ref,
            artifact_store=scenario.store,
            passport=scenario.passport,
            authority=scenario.authority,
        )
        return current(self)

    monkeypatch.setattr(case.cas, "put_json", put_then_deactivate)
    monkeypatch.setattr(
        case.control, "append_native_source_reentry_checkpoint", append_then_deactivate
    )
    monkeypatch.setattr(history.NativeSourceReentryCoordinator, "_current", check_current)
    monkeypatch.setattr(coordinator, "_read_selected", read_then_deactivate)

    def observe():
        if prepared is not None:
            return coordinator.claim("n5_claimed", prepared)
        if boundary == "progress-member":
            return coordinator.progress()
        return _prepare_selected(case, coordinator)

    with (
        case.fence(),
        pytest.raises(OverlayAdmissionError, match="epoch_activation_state_not_active"),
    ):
        observe()
    assert saved is not None
    selected = _read(case, target)
    assert (selected is not None) is expect_selected
    if expect_selected:
        original = case.control.list_diagnostic_events(job_id=case.head.job_id)
        with duckdb.connect(str(scenario.overlay.overlay_path)) as connection:
            connection.execute(
                "UPDATE acquisition_epochs SET epoch_activation_state = 'active', "
                "semantic_epoch_production_receipt_ref = ?, activated_overlay_receipt_ref = ? "
                "WHERE epoch_id = ? AND passport_id = ?",
                (*saved, *epoch),
            )
        with case.fence():
            assert _prepare_selected(case, coordinator) == selected[0]
        assert case.control.list_diagnostic_events(job_id=case.head.job_id) == original


def test_native_transition_keeps_sql_claim_absence_decisive_at_append(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = selected_case
    coordinator, observed = _progress_under_selected_owner(case, monkeypatch)
    append = ControlPlaneStore.append_native_source_reentry_checkpoint
    with case.fence():
        prepared = _select(case, case.prepared, "prepared")
        competing = history.NativeSourceReentryClaim(
            subject=case.prepared.subject,
            member="n5_claimed",
            predecessor_ref=prepared,
        )
        winning_ref = _write(case, competing)
        competing_event = case.events.prepare(_event(case, winning_ref, competing, "n5_claimed"))

        def competing_append(self, **kwargs):
            assert observed == [case.head, case.head]
            assert _read(case, "n5_claimed") is None
            append(self, pending_head=case.head, prepared_event=competing_event)
            return append(self, **kwargs)

        monkeypatch.setattr(
            ControlPlaneStore, "append_native_source_reentry_checkpoint", competing_append
        )
        with pytest.raises(
            ValueError, match="native_source_reentry_checkpoint_claim_already_selected"
        ):
            coordinator.claim("n5_claimed", prepared)
        with pytest.raises(ValueError, match="native_reentry_uncommitted_claim_not_established"):
            coordinator.claim("n5_claimed", prepared)
        event_id = history._event_id(case.prepared.subject, "n5_claimed")
        assert len(case.control.list_diagnostic_events(event_id=event_id)) == 1
        assert _read(case, "n5_claimed") == (winning_ref, competing)
        assert _read(case, "n5_completed") is None


@pytest.mark.parametrize("change", ["lease", "head", "selected-predecessor-profile"])
def test_native_transition_refuses_late_changed_effect_inputs(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    case = selected_case
    coordinator, observed = _progress_under_selected_owner(case, monkeypatch)
    current = history.NativeSourceReentryCoordinator._current
    put_json = case.cas.put_json
    with case.fence():
        prepared = _select(case, case.prepared, "prepared")
    sibling = case.cas.put_json(
        case.prepared.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(kind=prepared.kind, media_type=prepared.media_type),
        history._CANON,
        return_selected_profile=True,
    )
    assert sibling.artifact_id == prepared.artifact_id and sibling != prepared
    profile = case.cas._manifest_path_for_ref(
        prepared.artifact_id, prepared.manifest_profile_sha256
    )
    held = profile.with_name(profile.name + ".held")

    def check_then_change(self):
        cut = current(self)
        if len(observed) == 2:
            if change == "lease":
                with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
                    connection.execute(
                        "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                        ("2000-01-01T00:00:00Z", case.head.job_id),
                    )
            elif change == "head":
                _advance_test_terminal(case)
        return cut

    def put_then_remove_profile(*args, **kwargs):
        ref = put_json(*args, **kwargs)
        if change == "selected-predecessor-profile" and ref.kind == history._KIND:
            profile.rename(held)
            assert case.cas.verify(sibling).ok
        return ref

    monkeypatch.setattr(history.NativeSourceReentryCoordinator, "_current", check_then_change)
    monkeypatch.setattr(case.cas, "put_json", put_then_remove_profile)
    try:
        error, reason = {
            "lease": (ControlJobLeaseLostError, "lease is not current"),
            "head": (ValueError, "native_reentry_current_head_changed"),
            "selected-predecessor-profile": (FileNotFoundError, None),
        }[change]
        with case.fence(), pytest.raises(error, match=reason):
            coordinator.claim("n5_claimed", prepared)
    finally:
        if held.exists():
            held.rename(profile)
    assert _read(case, "prepared")[0] == prepared
    assert _read(case, "n5_claimed") is None


def test_native_preparation_requires_selected_event_and_exact_profile(selected_case: _Case) -> None:
    """Orphan CAS bytes and a same-blob sibling profile do not select preparation."""
    case = selected_case
    orphan = _write(case, case.prepared)
    assert _read(case, "prepared") is None
    with case.fence():
        selected = _select(case, case.prepared, "prepared")
    assert selected == orphan
    reader = artifacts.FileSystemCAS.open_existing_read_only(case.cas.root)
    reopened_ref, reopened = _read(case, "prepared", store=reader)
    assert artifacts.artifact_ref_identity_key(reopened_ref) == artifacts.artifact_ref_identity_key(
        selected
    )
    assert reopened.model_dump(mode="json") == case.prepared.model_dump(mode="json")
    assert (
        reopened.subject.original_profile_selection_ref
        != reopened.subject.current_profile_selection_ref
    )
    sibling = case.cas.put_json(
        case.prepared.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(kind=selected.kind, media_type=selected.media_type),
        history._CANON,
        return_selected_profile=True,
    )
    assert sibling.artifact_id == selected.artifact_id
    assert sibling.manifest_profile_sha256 != selected.manifest_profile_sha256
    path = case.cas._manifest_path_for_ref(selected.artifact_id, selected.manifest_profile_sha256)
    held = path.with_name(path.name + ".held")
    path.rename(held)
    try:
        assert reader.verify(sibling).ok
        with pytest.raises((FileNotFoundError, ValueError)):
            _read(case, "prepared", store=reader)
    finally:
        held.rename(path)
    assert _read(case, "prepared", store=reader)[1].model_dump(mode="json") == reopened.model_dump(
        mode="json"
    )


@pytest.mark.parametrize("mutation", ["source", "state", "subject", "profile"])
def test_native_checkpoint_publication_rejects_foreign_event_metadata(
    selected_case: _Case, mutation: str
) -> None:
    case = selected_case
    ref = _write(case, case.prepared)
    event = _event(case, ref, case.prepared, "prepared")
    updates = {
        "source": {"event_source": "polisyos.runtime"},
        "state": {"state_after": "terminal"},
        "subject": {
            "event_subject": event.event_subject.removesuffix(str(ref.manifest_profile_sha256))
            + "not-selected"
        },
        "profile": {"execution_profile": "sandbox"},
    }[mutation]
    expected_error = ControlJobExecutionAdmissionError if mutation == "profile" else ValueError
    expected_code = (
        "native_source_reentry_checkpoint_job_scope_mismatch"
        if mutation == "profile"
        else "native_source_reentry_checkpoint_event_binding_invalid"
    )
    with case.fence(), pytest.raises(expected_error, match=f"^{expected_code}$"):
        case.control.append_native_source_reentry_checkpoint(
            pending_head=case.head,
            prepared_event=case.events.prepare(event.model_copy(update=updates)),
        )
    assert _read(case, "prepared") is None


def test_native_checkpoint_requires_live_lease_but_history_grants_no_permission(
    selected_case: _Case, tmp_path: Path
) -> None:
    case = selected_case
    with pytest.raises(ControlJobLeaseLostError):
        _select(case, case.prepared, "prepared")
    with case.fence():
        selected = _select(case, case.prepared, "prepared")
        foreign_head = replace(case.head, receipt_manifest_profile_sha256="sha256:" + "0" * 64)
        with pytest.raises(
            ValueError, match="native_source_reentry_checkpoint_pending_head_changed"
        ):
            case.control.append_native_source_reentry_checkpoint(
                pending_head=foreign_head,
                prepared_event=case.events.prepare(
                    _event(case, selected, case.prepared, "prepared")
                ),
            )
    with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
        connection.execute(
            "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00Z", case.head.job_id),
        )
    assert _read(case, "prepared")[0] == selected
    with pytest.raises(ControlJobLeaseLostError):
        case.fence()
    foreign_head = replace(case.head, receipt_manifest_profile_sha256="sha256:" + "0" * 64)
    with pytest.raises(ControlJobLeaseLostError):
        case.control.append_native_source_reentry_checkpoint(
            pending_head=foreign_head,
            prepared_event=case.events.prepare(_event(case, selected, case.prepared, "prepared")),
        )


@pytest.mark.parametrize(
    "field", ["current_profile_selection_ref", "original_profile_selection_ref", "context_job_ref"]
)
def test_native_checkpoint_does_not_relabel_selected_subject(
    selected_case: _Case, field: str
) -> None:
    case = selected_case
    with case.fence():
        _select(case, case.prepared, "prepared")
    replacement = (
        "sha256:" + "9" * 64
        if field.endswith("selection_ref")
        else _parent(case.cas, "runtime.quality.cycle_substrate_context_job", "foreign context")
    )
    subject = case.prepared.subject.model_copy(update={field: replacement})
    with pytest.raises(ValueError, match="native_reentry_checkpoint_subject_mismatch"):
        _read(case, "prepared", subject=subject)


def test_selected_native_claim_does_not_establish_completed_work(
    selected_case: _Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chain policy refuses an actual selected start with no completed member.

    Source semantic replay is the explicit upstream boundary of this component;
    the selected CAS/event/head reads below use their real owners.
    """
    case = selected_case
    with case.fence():
        prepared_ref = _select(case, case.prepared, "prepared")
        claim = history.NativeSourceReentryClaim(
            subject=case.prepared.subject, member="n5_claimed", predecessor_ref=prepared_ref
        )
        _select(case, claim, "n5_claimed")
        with pytest.raises(
            ValueError, match="native_source_reentry_checkpoint_claim_already_selected"
        ):
            _select(case, claim, "n5_claimed")
    # The semantic Native source remains outside this recording-owner fixture.
    # Both current and historical consumers use the same extracted cut law.
    monkeypatch.setattr(history, "_verify_native_source_reentry_prepared", lambda **kwargs: None)
    with pytest.raises(ValueError, match="native_reentry_n5_completion_not_established"):
        history._verify_native_source_reentry_progress(
            store=case.cas,
            owner=None,
            source_generation_run=None,
            world_model_record_content_hash="sha256:" + "a" * 64,
            prepared=_read(case, "prepared"),
            n5=_read(case, "n5_completed"),
            cycle=_read(case, "cycle_completed"),
            n5_claim=_read(case, "n5_claimed"),
            tail_claim=_read(case, "tail_claimed"),
        )
    assert _read(case, "n5_completed") is None


def test_native_history_reader_requires_the_same_selected_store_owner(selected_case: _Case) -> None:
    case = selected_case
    with case.fence():
        _select(case, case.prepared, "prepared")
    reader = artifacts.FileSystemCAS.open_existing_read_only(case.cas.root)
    with pytest.raises(TypeError, match="native_reentry_history_owner_required"):
        history.read_native_source_reentry_member(
            store=reader, events=case.events, subject=case.prepared.subject, member="prepared"
        )
    assert _read(case, "prepared", store=reader) is not None


def _historical_prefix(case: _Case, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Adapt only unproved upstream input/world; retain actual selection owners."""
    from polisyos.runtime.quality import native_generic_context
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
    )

    subject = case.prepared.subject
    record = SimpleNamespace(
        job_id=subject.action_job_id,
        run_id=subject.run_id,
        tenant_id=subject.tenant_id,
        cell_id=subject.cell_id,
        source_run_id=subject.source_run_id,
        cycle_index=subject.cycle_index,
        design_problem_ref=subject.design_problem_ref,
        context_job_ref=subject.context_job_ref,
        native_current_profile_selection_ref=subject.current_profile_selection_ref,
    )
    selection = SimpleNamespace(
        pending_action_phase=SimpleNamespace(action_generation=subject.action_generation),
        checkpoint=SimpleNamespace(
            source_job_id=subject.source_job_id,
            route_id=subject.route_id,
            collection_refs=(subject.native_input_collection_ref,),
        ),
        pending_action_phase_ref=subject.pending_action_ref,
        checkpoint_ref=subject.native_world_checkpoint_ref,
        original_generic_input_ref=subject.original_generic_input_ref,
        original_profile_ref=subject.original_profile_ref,
        original_profile=SimpleNamespace(
            profile_selection_ref=subject.original_profile_selection_ref
        ),
        world_model_record=SimpleNamespace(content_hash="sha256:" + "a" * 64),
    )
    monkeypatch.setattr(
        GenericCycleSimulationN5InputV1, "model_validate", classmethod(lambda cls, raw: record)
    )
    monkeypatch.setattr(native_generic_context, "_selection_for_input", lambda *args: selection)
    monkeypatch.setattr(history, "_verify_native_source_reentry_prepared", lambda **kwargs: None)
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=case.cas)
    owner.bind_native_world_history(control_store=case.control, event_log=case.events)
    return {
        "store": case.cas,
        "events": case.events,
        "owner": owner,
        "input_ref": case.prepared.n5_input_ref,
        "source_generation_run": SimpleNamespace(
            run_id=subject.source_run_id,
            design_problem_ref=subject.stable_design_problem_ref,
        ),
        "receipt": SimpleNamespace(
            source_run_id=subject.source_run_id,
            source_cycle_index=subject.cycle_index - 1,
            new_cycle=SimpleNamespace(cycle_index=subject.cycle_index),
        ),
        "expected_action_job_id": subject.action_job_id,
        "expected_action_generation": subject.action_generation,
        "expected_source_job_id": subject.source_job_id,
        "expected_route_id": subject.route_id,
        "expected_run_id": subject.run_id,
        "expected_tenant_id": subject.tenant_id,
        "expected_cell_id": subject.cell_id,
    }


def test_full_native_history_requires_the_selected_prepared_event(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = selected_case
    args = _historical_prefix(case, monkeypatch)
    before = tuple(case.cas.root.rglob("*.json"))
    with pytest.raises(ValueError, match="native_reentry_prepared_checkpoint_missing"):
        history.read_native_source_reentry_history(**args)
    assert tuple(case.cas.root.rglob("*.json")) == before
    with pytest.raises(ControlJobLeaseLostError):
        case.control.current_execution_job_record()


@pytest.mark.parametrize("profile_graft", [False, True])
def test_full_native_history_does_not_promote_preparation_to_completed_result(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
    profile_graft: bool,
) -> None:
    case = selected_case
    with case.fence():
        ref = _select(case, case.prepared, "prepared")
    args = _historical_prefix(case, monkeypatch)
    if profile_graft:
        foreign = case.cas.put_json(
            case.prepared.model_dump(mode="json"),
            replace(history._options(case.prepared), inputs=[]),
            history._CANON,
            return_selected_profile=True,
        )
        assert foreign.artifact_id == ref.artifact_id
        assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
        path = case.cas._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
        held = path.with_name(path.name + ".held")
        path.rename(held)
        try:
            assert case.cas.verify(foreign).ok
            with pytest.raises((FileNotFoundError, ValueError)):
                history.read_native_source_reentry_history(**args)
        finally:
            held.rename(path)
    else:
        with pytest.raises(ValueError, match="native_reentry_history_completion_not_established"):
            history.read_native_source_reentry_history(**args)
    with pytest.raises(ControlJobLeaseLostError):
        case.control.current_execution_job_record()


@pytest.mark.parametrize(
    "field",
    ["expected_action_job_id", "expected_source_job_id", "expected_tenant_id", "expected_route_id"],
)
def test_full_native_history_refuses_foreign_source_action_scope(
    selected_case: _Case,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    case = selected_case
    with case.fence():
        _select(case, case.prepared, "prepared")
    args = _historical_prefix(case, monkeypatch)
    args[field] = "sha256:" + "f" * 64 if field == "expected_route_id" else "foreign-scope"
    with pytest.raises(ValueError, match="native_reentry_history_source_scope_mismatch"):
        history.read_native_source_reentry_history(**args)
    with pytest.raises(ControlJobLeaseLostError):
        case.control.current_execution_job_record()
