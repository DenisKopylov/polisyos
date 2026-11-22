"""Reconcile precommit terminal history with the actual event and frontier owners."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control.run_lifecycle import _acquisition_route_receipt_inputs
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    AcquisitionEvaluationFrontierKey,
    AcquisitionEvaluationFrontierRecord,
    AcquisitionEvaluationFrontierValue,
)
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality import acquisition_evaluation_history as history_owner
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasisV2,
    AcquisitionEvaluationDecisionV2,
    AcquisitionSelectedEvaluation,
    CandidateAcquisitionEvaluationBasis,
    CandidateAcquisitionEvaluationDecision,
    CandidateExperimentTerminalHistory,
    ResolvedAcquisitionEvaluation,
)
from polisyos.runtime.quality.acquisition_model_transition import CandidateModelRevision
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentTerminalReceipt,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationResult,
    PhysicalSimulationWorkObservation,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _hash,
    _ref,
    _requested_phase,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService


def _write_terminal(
    service: ControlPlaneService, terminal: AcquisitionCandidateExperimentTerminalReceipt
) -> artifacts.ArtifactRef:
    inputs = _acquisition_route_receipt_inputs(terminal)
    generated = terminal.generated_at.isoformat()
    return write_runtime_authority_artifact(
        service._artifact_store,
        service._diagnostic_event_log,
        terminal.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(
            kind="runtime_quality.acquisition_route_loop_receipt",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.runtime.AcquisitionCandidateExperimentTerminalReceipt", version="1.0"
            ),
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.acquisition_route_loop", version="2026.08.28+ds15-c02"
            ),
            governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
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
        generated_at=generated,
        as_of_time=generated,
        same_input_closure={
            "closure_id": f"acquisition-route:{terminal.receipt_id}",
            "status": "closed",
            "tenant_id": terminal.tenant_id,
            "cell_id": terminal.cell_id,
            "run_id": terminal.run_id,
            "job_id": terminal.job_id,
            "closure_sha256": terminal.route_id,
            "evidence_input_refs": inputs,
        },
        input_refs=inputs,
        effective_mode_ref=terminal.route_id,
        validation_status="pass",
        blocking_status="non_blocking",
        governance={
            "classification": "internal",
            "authority_boundary": "runtime.acquisition_route_loop",
            "pii": "none",
            "retention_policy": "runtime-quality-90d",
            "review_status": "runtime_verified",
            "override_policy": "no_override",
            "approval_policy": "pa2_ds9_decision_required",
        },
        event_source="polisyos.runtime.quality.acquisition_route_loop",
        event_type="polisyos.runtime.acquisition.candidate_experiment_terminal.v1",
        event_subject=f"run/{terminal.run_id}/job/{terminal.job_id}/acquisition/terminal",
        state_before="candidate_input_reentry_pending",
        state_after="terminal",
        canon_spec=CanonSpec(forbid_floats=False),
    ).cas_ref


@pytest.fixture
def custody_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Adapt the upstream historical evaluator and keep the new CAS/event joins real."""
    service = _build_control_service(tmp_path)
    base = _requested_phase()
    head = AcquisitionActionHeadRecord(
        tenant_id=base.tenant_id,
        cell_id=base.cell_id,
        run_id=base.run_id,
        source_job_id=base.source_job_id,
        route_id=base.route_id,
        action_generation=4,
        head_generation=5,
        receipt_ref=_hash("9"),
        receipt_sha256=_hash("9"),
        durable_event_id="pending-event",
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        job_id=base.job_id,
        predecessor_receipt_ref=_hash("8"),
        created_at=base.generated_at,
        receipt_manifest_profile_sha256=_hash("f"),
    )
    basis_ref = _ref("runtime_quality.acquisition_evaluation_basis", "a")
    evaluation_ref = _ref("runtime.quality.candidate_simulation_execution", "b")
    prior_basis = _ref("runtime_quality.acquisition_evaluation_basis", "2")
    prior_execution = _ref("runtime.quality.candidate_simulation_execution", "3")
    decision_ref = _ref("runtime_quality.acquisition_evaluation_decision", "c")
    action_ref = _ref("runtime_quality.acquisition_candidate_action_receipt", "d")
    selected = AcquisitionSelectedEvaluation(
        candidate_id=base.policy_scope.candidate_id,
        candidate_content_hash=base.policy_scope.candidate_content_hash,
        design_problem_ref=base.policy_scope.design_problem_basis_ref,
        world_model_record_hash=_hash("5"),
        evaluation_job_id=head.job_id,
        evaluation_run_id=head.run_id,
        generation_run_id="generation-run-4",
        cycle_index=2,
        n4_source_ref=_ref("runtime.quality.n4_candidate_scenario_source", "6"),
        context_job_ref=_ref("runtime.quality.cycle_substrate_context_job", "7"),
        n5_input_ref=_ref("runtime.quality.candidate_simulation_n5_input", "8"),
        n5_execution_ref=evaluation_ref,
        n5_result_ref=_ref("polisyos.runtime.joint_simulation_result", "9"),
    )
    terminal = AcquisitionCandidateExperimentTerminalReceipt(
        receipt_id=f"{head.job_id}.terminal",
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        run_id=head.run_id,
        source_job_id=head.source_job_id,
        route_id=head.route_id,
        action_generation=head.action_generation,
        job_id=head.job_id,
        source_payload_ref=base.source_payload_ref,
        capability_manifest_ref=base.capability_manifest_ref,
        request_content_hash=base.request_content_hash,
        policy_scope=base.policy_scope,
        policy_ref=base.policy_ref,
        authority_decision_ref=base.authority_decision_ref,
        voi_decision=base.voi_decision,
        predecessor_receipt_ref=head.receipt_ref,
        owner_receipt_refs=(str(action_ref.artifact_id), str(decision_ref.artifact_id)),
        generated_at=base.generated_at + timedelta(minutes=1),
        terminal_outcome="candidate_reentry_completed",
        candidate_action_ref=action_ref,
        candidate_reentry_ref=_ref("runtime_quality.candidate_source_reentry_receipt", "e"),
        evaluation_decision_ref=decision_ref,
        selected_basis_ref=basis_ref,
        selected_evaluation_witness_ref=evaluation_ref,
        selected_evaluation=selected.model_copy(update={"basis_ref": basis_ref}),
    )
    ref = _write_terminal(service, terminal)
    verified = service.acquisition_route_sink._read_verified_action_phase(
        str(ref.artifact_id), selected_ref=ref
    )
    key = AcquisitionEvaluationFrontierKey(
        head.tenant_id,
        head.cell_id,
        head.source_job_id,
        base.policy_scope.design_problem_ref,
        base.policy_scope.candidate_id,
    )
    frontier = AcquisitionEvaluationFrontierRecord(
        key=key,
        revision=3,
        selected_evaluation_witness_ref=str(prior_execution.artifact_id),
        selected_evaluation_content_hash=_hash("4"),
        basis_ref=str(prior_basis.artifact_id),
        basis_content_hash=_hash("5"),
        decision_ref=_hash("6"),
        frontier_ref=_hash("7"),
    )
    prior_selected = selected.model_copy(
        update={"basis_ref": prior_basis, "n5_execution_ref": prior_execution}
    )
    decision = CandidateAcquisitionEvaluationDecision.model_construct(
        **vars(key),
        comparison_result="not_established",
        predicate_provenance="not_established",
        prior_basis_ref=prior_basis,
        prior_evaluation=prior_selected,
        expected_frontier_revision=3,
        expected_frontier_ref=frontier.frontier_ref,
    )
    basis = CandidateAcquisitionEvaluationBasis.model_construct(
        basis_role="evaluated",
        predicate_provenance="recomputed",
        evaluation=selected,
        content_hash=_hash("1"),
    )
    evaluation = ResolvedAcquisitionEvaluation(
        selected=selected,
        execution=SimpleNamespace(content_hash=_hash("0")),
        source=None,
        input_record=None,
        result=None,
        handoff=None,
    )
    history = CandidateExperimentTerminalHistory(
        head=head,
        terminal_ref=ref,
        terminal=terminal,
        origin=None,
        phase_chain=(verified,),
        action=None,
        source=None,
        budget_window=None,
        decision=decision,
        current_basis=None,
        selected_basis=basis,
        evaluation=evaluation,
        reentry=SimpleNamespace(),
        continuation=None,
        frontier_before=frontier,
        frontier_after=None,
        reentry_evaluation=evaluation,
    )
    case = SimpleNamespace(service=service, history=history, frontier=frontier, verified=verified)
    monkeypatch.setattr(
        history_owner, "verify_candidate_experiment_terminal_history", lambda **_: case.history
    )
    monkeypatch.setattr(
        service._control_store, "read_acquisition_evaluation_frontier", lambda _key: case.frontier
    )
    try:
        yield case
    finally:
        service._control_store.close()


def _prepare(case, *, ref: artifacts.ArtifactRef | None = None):
    return dispatch.prepare_candidate_experiment_terminal_custody(
        control_service=case.service,
        head=case.history.head,
        terminal_ref=ref or case.history.terminal_ref,
    )


@pytest.mark.parametrize(
    ("comparison", "provenance"),
    [("not_established", "not_established"), ("different", "recomputed")],
)
def test_custody_derives_exact_precommit_cas_and_event(
    custody_case, comparison: str, provenance: str
) -> None:
    case = custody_case
    decision = case.history.decision.model_copy(
        update={"comparison_result": comparison, "predicate_provenance": provenance}
    )
    case.history = replace(case.history, decision=decision)

    cas, durable = _prepare(case)

    assert durable == case.verified.durable_event_id
    assert cas.key == case.frontier.key
    assert cas.expected_revision == case.frontier.revision
    assert cas.expected_frontier_ref == case.frontier.frontier_ref
    assert cas.replacement == AcquisitionEvaluationFrontierValue(
        selected_evaluation_witness_ref=str(
            case.history.terminal.selected_evaluation_witness_ref.artifact_id
        ),
        selected_evaluation_content_hash=case.history.evaluation.execution.content_hash,
        basis_ref=str(case.history.terminal.selected_basis_ref.artifact_id),
        basis_content_hash=case.history.selected_basis.content_hash,
        decision_ref=str(case.history.terminal.evaluation_decision_ref.artifact_id),
    )
    assert case.history.decision is decision
    assert (
        case.service._control_store.read_acquisition_evaluation_frontier(cas.key) == case.frontier
    )


def test_ordinary_terminal_preparation_stages_canonical_event_without_sql(
    custody_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prove the real CAS/event bridge using an adapted completed checkpoint."""
    case = custody_case
    existing = case.history.terminal
    head = replace(
        case.history.head,
        coarse_phase="world_committed",
        receipt_phase="world_committed_reentry_pending",
        receipt_manifest_profile_sha256=None,
    )
    growth_ref = _hash("a")
    pending = AcquisitionRoutePhaseReceipt(
        receipt_id=f"{head.job_id}.world-committed.evaluation",
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        run_id=head.run_id,
        source_job_id=head.source_job_id,
        route_id=head.route_id,
        action_generation=head.action_generation,
        job_id=head.job_id,
        compiled_ref=_hash("b"),
        planner_report_hash=_hash("c"),
        cost_basis_hash=_hash("d"),
        decision_ref=_hash("e"),
        coarse_phase="world_committed",
        receipt_phase="world_committed_reentry_pending",
        recovery_state="reentry_recovery_required",
        predecessor_receipt_ref=head.predecessor_receipt_ref,
        owner_receipt_refs=tuple(
            sorted((growth_ref, str(existing.evaluation_decision_ref.artifact_id)))
        ),
        generated_at=head.created_at,
    )
    selected = case.history.evaluation.selected
    work = PhysicalSimulationWorkObservation(
        invocation_id="a" * 32,
        event_id="b" * 32,
        physical_spec_ref="c" * 64,
        effective_seed=11,
        status="completed",
        started_at=pending.generated_at,
        completed_at=pending.generated_at + timedelta(seconds=1),
        duration_seconds=1,
        budget_status="not_established",
    )
    evaluation = replace(
        case.history.evaluation,
        result=JointSimulationResult.model_construct(
            diagnostics={
                "physical_work_observations": [work.model_dump(mode="python")],
                "physical_work_capture_status": "observed",
                "physical_work_units": 1,
                "physical_work_unit": work.work_unit,
                "physical_work_usd_cost_status": work.usd_cost_status,
                "requested_replications": 1,
                "replication_seeds": (work.effective_seed,),
            },
            trajectories=(),
        ),
    )
    basis_ref = existing.selected_basis_ref
    reentry_ref = _ref("runtime_quality.acquisition_overlay_reentry_receipt", "f")
    checkpoint = history_owner.VerifiedOrdinaryAcquisitionTerminalCheckpoint(
        job=None,  # The preceding historical proof is outside this component test.
        head=head,
        pending=pending,
        decision_ref=existing.evaluation_decision_ref,
        decision=AcquisitionEvaluationDecisionV2.model_construct(
            expected_frontier_revision=case.frontier.revision,
            expected_frontier_ref=case.frontier.frontier_ref,
        ),
        reentry_ref=reentry_ref,
        reentry=AcquisitionOverlayReentryReceipt.model_construct(),
        selected_basis_ref=basis_ref,
        selected_basis=AcquisitionEvaluationBasisV2.model_construct(
            evaluation=selected, content_hash=case.history.selected_basis.content_hash
        ),
        evaluation=evaluation,
        frontier_before=case.frontier,
        model_revision=CandidateModelRevision(
            previous_input_ref=_ref("runtime.quality.candidate_simulation_n5_input", "1"),
            selected_input_ref=selected.n5_input_ref,
            previous_declaration_ref=_ref(
                "runtime.quality.candidate_simulation_model_declaration", "2"
            ),
            selected_declaration_ref=_ref(
                "runtime.quality.candidate_simulation_model_declaration", "3"
            ),
            previous_ncm_ref=_ref("ir.ncm_spec", "4"),
            selected_ncm_ref=_ref("ir.ncm_spec", "5"),
            previous_basis_ref=case.history.decision.prior_basis_ref,
            selected_basis_ref=basis_ref,
        ),
    )

    def refuse_sql(*_args: object, **_kwargs: object) -> None:
        pytest.fail("terminal preparation must not access SQL")

    with monkeypatch.context() as patch:
        patch.setattr(case.service._control_store, "_sqlite_connection", refuse_sql)
        prepared = dispatch.prepare_ordinary_acquisition_terminal(
            control_service=case.service, checkpoint=checkpoint
        )
        with pytest.raises(
            ValueError, match="ordinary_acquisition_terminal_preparation_checkpoint_mismatch"
        ):
            dispatch.prepare_ordinary_acquisition_terminal(
                control_service=case.service,
                checkpoint=replace(checkpoint, selected_basis_ref=checkpoint.decision_ref),
            )

    terminal = prepared.terminal
    assert terminal.predecessor_receipt_ref == head.receipt_ref
    assert terminal.owner_receipt_refs == pending.owner_receipt_refs
    assert terminal.reentry_receipt_ref == str(reentry_ref.artifact_id)
    assert terminal.selected_evaluation == selected.model_copy(update={"basis_ref": basis_ref})
    assert terminal.selected_evaluation_witness_ref == selected.n5_execution_ref
    assert prepared.reentry_ref == reentry_ref
    assert prepared.work_event_ids == (work.event_id,)
    assert prepared.frontier_cas.key == case.frontier.key
    assert prepared.frontier_cas.expected_revision == case.frontier.revision
    assert prepared.frontier_cas.expected_frontier_ref == case.frontier.frontier_ref
    assert prepared.frontier_cas.replacement == AcquisitionEvaluationFrontierValue(
        selected_evaluation_witness_ref=str(selected.n5_execution_ref.artifact_id),
        selected_evaluation_content_hash=evaluation.execution.content_hash,
        basis_ref=str(basis_ref.artifact_id),
        basis_content_hash=checkpoint.selected_basis.content_hash,
        decision_ref=str(checkpoint.decision_ref.artifact_id),
    )
    event, payload = prepared.prepared_event.publication_values()
    terminal_id = str(prepared.terminal_ref.artifact_id)
    assert (
        event.event_id == f"evt_acquisition_4_loop_terminal_{terminal_id.removeprefix('sha256:')}"
    )
    assert event.event_type == "polisyos.runtime.acquisition.route_loop.v2"
    assert event.state_before == pending.receipt_phase
    assert event.state_after == "terminal"
    assert event.payload_ref == terminal_id
    assert event.input_refs == _acquisition_route_receipt_inputs(terminal)
    assert payload is None
    events = case.service._diagnostic_event_log
    assert not events.list_events(event_id=event.event_id, limit=10)
    events.append(event)
    verified = case.service.acquisition_route_sink._read_verified_action_phase(
        terminal_id, selected_ref=prepared.terminal_ref
    )
    assert (verified.receipt, verified.event) == (terminal, event)


@pytest.mark.parametrize("outcome", ["candidate_evaluation_retained", "candidate_blocked"])
def test_custody_refuses_other_terminal_outcomes(custody_case, outcome: str) -> None:
    case = custody_case
    case.history = replace(
        case.history,
        terminal=case.history.terminal.model_copy(update={"terminal_outcome": outcome}),
    )
    with pytest.raises(ValueError, match="candidate_experiment_custody_new_execution_required"):
        _prepare(case)


@pytest.mark.parametrize(
    ("comparison", "provenance"), [("equivalent", "recomputed"), ("different", "not_established")]
)
def test_custody_refuses_unsupported_comparison(
    custody_case, comparison: str, provenance: str
) -> None:
    case = custody_case
    case.history = replace(
        case.history,
        decision=case.history.decision.model_copy(
            update={"comparison_result": comparison, "predicate_provenance": provenance}
        ),
    )
    with pytest.raises(ValueError, match="candidate_experiment_custody_comparison_invalid"):
        _prepare(case)


@pytest.mark.parametrize("change", ["no_prior", "moved_prior", "other_candidate", "same_execution"])
def test_custody_requires_the_exact_existing_prior_frontier(custody_case, change: str) -> None:
    case = custody_case
    if change == "no_prior":
        case.history = replace(case.history, frontier_before=None)
    elif change == "moved_prior":
        case.frontier = replace(case.frontier, revision=4)
    elif change == "other_candidate":
        case.history = replace(
            case.history,
            frontier_before=replace(
                case.frontier, key=replace(case.frontier.key, candidate_id="other-candidate")
            ),
        )
    else:
        # The hypothetical prior points to this same execution in both sources.
        execution_ref = case.history.terminal.selected_evaluation_witness_ref
        case.frontier = replace(
            case.frontier, selected_evaluation_witness_ref=str(execution_ref.artifact_id)
        )
        decision = case.history.decision
        prior = decision.prior_evaluation.model_copy(update={"n5_execution_ref": execution_ref})
        case.history = replace(
            case.history,
            frontier_before=case.frontier,
            decision=decision.model_copy(update={"prior_evaluation": prior}),
        )
    with pytest.raises(ValueError, match="candidate_experiment_custody_frontier_changed"):
        _prepare(case)


@pytest.mark.parametrize("change", ["missing_evaluation", "unknown_basis", "substituted_execution"])
def test_custody_requires_recomputed_execution_even_when_comparison_is_unknown(
    custody_case, change: str
) -> None:
    case = custody_case
    if change == "missing_evaluation":
        case.history = replace(case.history, evaluation=None)
    elif change == "unknown_basis":
        basis = case.history.selected_basis.model_copy(
            update={"predicate_provenance": "not_established"}
        )
        case.history = replace(case.history, selected_basis=basis)
    else:
        # Match the selected basis to the substituted execution while leaving the owner terminal intact.
        execution = case.history.evaluation
        substituted = execution.selected.model_copy(
            update={"n5_execution_ref": case.history.decision.prior_evaluation.n5_execution_ref}
        )
        case.history = replace(
            case.history,
            selected_basis=case.history.selected_basis.model_copy(
                update={"evaluation": substituted}
            ),
            evaluation=replace(execution, selected=substituted),
        )
    with pytest.raises(ValueError, match="candidate_experiment_terminal_basis_not_recomputed"):
        _prepare(case)


def test_custody_requires_the_selected_manifest(custody_case) -> None:
    case = custody_case
    with pytest.raises(
        ValueError, match="candidate_experiment_custody_predecessor_or_profile_invalid"
    ):
        _prepare(
            case, ref=case.history.terminal_ref.model_copy(update={"manifest_profile_sha256": None})
        )


def test_custody_reopens_actual_terminal_event(custody_case) -> None:
    case = custody_case
    # The adapted history still attests an earlier read. The real CAS/event join must fail.
    case.service._control_store._execute(
        "DELETE FROM control_diagnostic_events WHERE event_id=?", (case.verified.durable_event_id,)
    )
    with pytest.raises(
        ValueError, match=r"(?i)(authority_orphan_cas|did not resolve exactly once)"
    ):
        _prepare(case)
