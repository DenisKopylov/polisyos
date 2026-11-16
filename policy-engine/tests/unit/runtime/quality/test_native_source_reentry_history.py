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
