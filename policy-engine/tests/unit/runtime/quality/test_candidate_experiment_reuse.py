"""Exact read-only projection of the prior selected N5 from terminal history."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    CanonInfo,
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control.run_lifecycle import (
    VerifiedAcquisitionActionPhase,
)
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionSelectedEvaluation,
    CandidateExperimentTerminalHistory,
    ResolvedAcquisitionEvaluation,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
    AcquisitionCandidateExperimentTerminalReceiptV2,
    VerifiedCandidateExperimentOrigin,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    POLICY_KIND,
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.candidate_experiment_reuse import (
    CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
    CandidateExperimentReuseActionRequest,
    CandidateExperimentReuseActionSelection,
    _candidate_experiment_reuse_job_id,
    _selected_predecessor_evaluation,
    candidate_experiment_reuse_action_tuple,
)
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _hash,
    _ref,
    _requested_phase,
)

if TYPE_CHECKING:
    from pathlib import Path


def _resolved_evaluation() -> ResolvedAcquisitionEvaluation:
    selected = AcquisitionSelectedEvaluation(
        candidate_id="candidate-a",
        candidate_content_hash=_hash("3"),
        design_problem_ref=_hash("2"),
        world_model_record_hash=_hash("4"),
        evaluation_job_id="job-n5",
        evaluation_run_id="run-a",
        generation_run_id="generation-a",
        cycle_index=1,
        n4_source_ref=_ref("runtime.quality.n4_candidate_scenario_source", "1"),
        context_job_ref=_ref("runtime.quality.cycle_substrate_context_job", "2"),
        n5_input_ref=_ref("runtime.quality.candidate_simulation_n5_input", "3"),
        n5_execution_ref=_ref("runtime.quality.candidate_simulation_execution", "4"),
        n5_result_ref=_ref("polisyos.runtime.joint_simulation_result", "5"),
        basis_ref=_ref("runtime_quality.acquisition_evaluation_basis", "6"),
    )
    return ResolvedAcquisitionEvaluation(
        selected=selected,
        source=SimpleNamespace(),
        input_record=SimpleNamespace(),
        execution=SimpleNamespace(),
        result=SimpleNamespace(),
        handoff=SimpleNamespace(),
    )


def _reuse_policy_scope() -> CandidateUnpricedPolicyScope:
    return CandidateUnpricedPolicyScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        design_problem_ref=_hash("1"),
        design_problem_basis_ref=_hash("2"),
        source_cycle_index=1,
        candidate_id="candidate-a",
        candidate_content_hash=_hash("3"),
        requirement_id="requirement-a",
        compiled_requirement_ref=_hash("4"),
        candidate_digest=_hash("5"),
        planner_report_hash=_hash("6"),
        compiled_ref=_ref("runtime.compiled_recursive_generation_cycle", "7"),
        planner_report_ref=_ref("runtime.acquisition_planner_report", "8"),
        compiler_report_ref=_ref("runtime.data_requirement_compilation_report", "9"),
        configured_port_source_ref=_ref("runtime.quality.n7_configured_candidate_port_source", "a"),
    )


def _reuse_action_selection(
    *,
    request: CandidateExperimentReuseActionRequest | None = None,
    predecessor_terminal_ref: ArtifactRef | None = None,
    **updates: object,
) -> CandidateExperimentReuseActionSelection:
    scope = _reuse_policy_scope()
    identity: dict[str, object] = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "source-a",
        "source_payload_ref": _hash("7"),
        "request_content_hash": _hash("8"),
        "route_id": _hash("b"),
        "predecessor_action_generation": 1,
        "action_generation": 2,
        "predecessor_terminal_ref": predecessor_terminal_ref
        or _ref("runtime_quality.acquisition_route_loop_receipt", "c"),
        "predecessor_action_ref": _ref("runtime_quality.acquisition_candidate_action_receipt", "d"),
        "source_ref": _ref("runtime.quality.candidate_acquisition_source", "e"),
        "n5_input_ref": _ref("runtime.quality.candidate_simulation_n5_input", "1"),
        "n5_execution_ref": _ref("runtime.quality.candidate_simulation_execution", "2"),
        "n5_result_ref": _ref("polisyos.runtime.joint_simulation_result", "3"),
        "policy_ref": _ref(POLICY_KIND, "4"),
        "policy_scope": scope,
        "catalog_source_selection_basis": "legacy_default_candidate_only",
        "catalog_source_content_ref": None,
        "authority_provision_content_sha256": _hash("9"),
        "source_currentness": "source_currentness_not_established",
    }
    if request is None:
        request = CandidateExperimentReuseActionRequest(
            route_id=str(identity["route_id"]),
            predecessor_terminal_ref=identity["predecessor_terminal_ref"],
            predecessor_action_ref=identity["predecessor_action_ref"],
            source_ref=identity["source_ref"],
            n5_input_ref=identity["n5_input_ref"],
            n5_execution_ref=identity["n5_execution_ref"],
            n5_result_ref=identity["n5_result_ref"],
            policy_ref=identity["policy_ref"],
            idempotency_key="reuse-generation-two",
        )
    identity["request"] = request
    identity["action_job_id"] = _candidate_experiment_reuse_job_id(
        tenant_id=str(identity["tenant_id"]),
        cell_id=str(identity["cell_id"]),
        run_id=str(identity["run_id"]),
        source_job_id=str(identity["source_job_id"]),
        source_payload_ref=str(identity["source_payload_ref"]),
        request_content_hash=str(identity["request_content_hash"]),
        route_id=str(identity["route_id"]),
        predecessor_action_generation=int(identity["predecessor_action_generation"]),
        action_generation=int(identity["action_generation"]),
        policy_ref=identity["policy_ref"],  # type: ignore[arg-type]
        policy_scope=scope,
        request=request,
        authority_provision_content_sha256=str(identity["authority_provision_content_sha256"]),
        catalog_source_selection_basis=identity["catalog_source_selection_basis"],  # type: ignore[arg-type]
        catalog_source_content_ref=identity["catalog_source_content_ref"],  # type: ignore[arg-type]
    )
    identity.update(updates)
    return CandidateExperimentReuseActionSelection.model_validate(identity)


def _history(
    *, outcome: str, evaluation: ResolvedAcquisitionEvaluation
) -> CandidateExperimentTerminalHistory:
    requested = _requested_phase()
    action_ref = _ref("runtime_quality.acquisition_candidate_action_receipt", "7")
    reentry_ref = _ref("runtime_quality.candidate_source_reentry_receipt", "8")
    decision_ref = _ref("runtime_quality.acquisition_evaluation_decision", "9")
    basis_ref = evaluation.selected.basis_ref
    assert basis_ref is not None
    identity = requested.model_dump(
        exclude={
            "schema_version",
            "coarse_phase",
            "receipt_phase",
            "recovery_state",
            "candidate_receipt_ref",
        }
    )
    terminal = AcquisitionCandidateExperimentTerminalReceipt(
        **{
            **identity,
            "receipt_id": "terminal-a",
            "job_id": "action-a",
            "action_generation": 1,
            "predecessor_receipt_ref": _hash("a"),
            "owner_receipt_refs": (
                str(action_ref.artifact_id),
                str(reentry_ref.artifact_id),
                str(decision_ref.artifact_id),
            ),
        },
        terminal_outcome=outcome,
        candidate_action_ref=action_ref,
        candidate_reentry_ref=(reentry_ref if outcome == "candidate_reentry_completed" else None),
        evaluation_decision_ref=decision_ref,
        selected_basis_ref=basis_ref,
        selected_evaluation_witness_ref=evaluation.selected.n5_execution_ref,
        selected_evaluation=evaluation.selected,
        current_continuation_ref=(
            _ref("runtime_quality.candidate_acquisition_retained_continuation", "a")
            if outcome == "candidate_evaluation_retained"
            else None
        ),
    )
    return CandidateExperimentTerminalHistory(
        head=SimpleNamespace(),
        terminal_ref=_ref("runtime_quality.acquisition_route_loop_receipt", "b"),
        terminal=terminal,
        origin=SimpleNamespace(),
        phase_chain=(),
        action=SimpleNamespace(),
        source=SimpleNamespace(),
        budget_window=SimpleNamespace(),
        decision=None,
        current_basis=None,
        selected_basis=None,
        evaluation=(evaluation if outcome == "candidate_evaluation_retained" else None),
        reentry=None,
        continuation=None,
        frontier_before=None,
        frontier_after=None,
        reentry_evaluation=(evaluation if outcome == "candidate_reentry_completed" else None),
    )


def _persist_fixture_receipt(
    store: FileSystemCAS,
    receipt: AcquisitionCandidateExperimentPhaseReceipt
    | AcquisitionCandidateExperimentTerminalReceipt,
) -> ArtifactRef:
    canon_spec = CanonSpec(forbid_floats=False)
    kind, name = (
        (
            "runtime_quality.acquisition_candidate_experiment_phase_receipt",
            "polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
        )
        if type(receipt) is AcquisitionCandidateExperimentPhaseReceipt
        else (
            "runtime_quality.acquisition_route_loop_receipt",
            "polisyos.runtime.AcquisitionCandidateExperimentTerminalReceipt",
        )
    )
    return store.put_json(
        receipt.model_dump(mode="json"),
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=name, version=receipt.schema_version.rsplit("@", 1)[-1]),
            producer=ProducerInfo(component="test.candidate_experiment_reuse", version="1.0"),
            canon=CanonInfo.from_spec(canon_spec),
        ),
        canon_spec,
        return_selected_profile=True,
    )


def _v2_reuse_history(
    store: FileSystemCAS, *, blocked: bool = False
) -> tuple[CandidateExperimentTerminalHistory, ResolvedAcquisitionEvaluation]:
    from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
        CandidateExperimentReuseOccurrence,
    )

    selection = _reuse_action_selection()
    evaluation = _resolved_evaluation()
    selected = evaluation.selected.model_copy(
        update={
            "n5_input_ref": selection.n5_input_ref,
            "n5_execution_ref": selection.n5_execution_ref,
            "n5_result_ref": selection.n5_result_ref,
        }
    )
    evaluation = replace(evaluation, selected=selected)
    source_action_job_id = "physical-source-action-1"
    source = SimpleNamespace(
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        job_id=source_action_job_id,
        route_id=selection.route_id,
    )
    action = SimpleNamespace(
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        source_job_id=selection.source_job_id,
        route_id=selection.route_id,
        action_job_id=source_action_job_id,
        action_generation=selection.predecessor_action_generation,
        candidate_source_ref=selection.source_ref,
    )

    prior_history = _history(outcome="candidate_evaluation_retained", evaluation=evaluation)
    prior_terminal_fields = prior_history.terminal.model_dump(mode="python")
    prior_terminal_fields.update(
        {
            "receipt_id": source_action_job_id + ".candidate-experiment.terminal",
            "tenant_id": selection.tenant_id,
            "cell_id": selection.cell_id,
            "run_id": selection.run_id,
            "source_job_id": selection.source_job_id,
            "route_id": selection.route_id,
            "action_generation": selection.predecessor_action_generation,
            "job_id": source_action_job_id,
            "source_payload_ref": selection.source_payload_ref,
            "request_content_hash": selection.request_content_hash,
            "policy_scope": selection.policy_scope,
            "policy_ref": selection.policy_ref,
            "candidate_action_ref": selection.predecessor_action_ref,
            "owner_receipt_refs": (
                str(selection.predecessor_action_ref.artifact_id),
                str(prior_history.terminal.evaluation_decision_ref.artifact_id),
            ),
        }
    )
    prior_terminal = AcquisitionCandidateExperimentTerminalReceipt.model_validate(
        prior_terminal_fields
    )
    prior_terminal_ref = _persist_fixture_receipt(store, prior_terminal)
    selection = _reuse_action_selection(predecessor_terminal_ref=prior_terminal_ref)
    prior_head = SimpleNamespace(
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        source_job_id=selection.source_job_id,
        route_id=selection.route_id,
        action_generation=selection.predecessor_action_generation,
        job_id=source_action_job_id,
        receipt_ref=str(selection.predecessor_terminal_ref.artifact_id),
        receipt_manifest_profile_sha256=(
            selection.predecessor_terminal_ref.manifest_profile_sha256
        ),
        predecessor_receipt_ref=prior_terminal.predecessor_receipt_ref,
        receipt_phase="terminal",
    )
    prior_history = replace(
        prior_history,
        terminal_ref=selection.predecessor_terminal_ref,
        terminal=prior_terminal,
        head=prior_head,
        action=action,
        source=source,
    )

    control_payload_ref = _ref("runtime.control_job_payload.acquisition", "b")
    decision_ref = _ref("runtime_quality.agent_action_authority_decision", "c")
    occurrence_ref = _ref("runtime_quality.candidate_experiment_reuse_occurrence", "0")
    requested = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        {
            **prior_terminal.model_dump(
                mode="python",
                include=set(AcquisitionCandidateExperimentPhaseReceipt.model_fields)
                - {"schema_version"},
            ),
            "receipt_id": selection.action_job_id + ".candidate-experiment.requested",
            "action_generation": selection.action_generation,
            "job_id": selection.action_job_id,
            "predecessor_receipt_ref": None,
            "authority_decision_ref": decision_ref,
            "owner_receipt_refs": (),
            "coarse_phase": "requested",
            "receipt_phase": "requested",
            "recovery_state": "none",
        }
    )
    requested_ref = _persist_fixture_receipt(store, requested)
    executing = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        {
            **requested.model_dump(mode="python"),
            "receipt_id": selection.action_job_id + ".candidate-experiment.executing",
            "predecessor_receipt_ref": str(requested_ref.artifact_id),
            "coarse_phase": "executing",
            "receipt_phase": "executing",
        }
    )
    phase_ref = _persist_fixture_receipt(store, executing)
    occurrence = CandidateExperimentReuseOccurrence(
        selection=selection,
        executing_phase_ref=phase_ref,
        control_payload_ref=control_payload_ref,
        pa2_decision_ref=decision_ref,
    )
    current_continuation_ref = _ref(
        "runtime_quality.candidate_acquisition_retained_continuation", "e"
    )
    evaluation_decision_ref = _ref("runtime_quality.acquisition_evaluation_decision", "f")
    terminal_fields = prior_terminal.model_dump(mode="python")
    terminal_fields.update(
        {
            "schema_version": "AcquisitionCandidateExperimentTerminalReceipt@2.0",
            "receipt_id": selection.action_job_id + ".candidate-experiment-reuse.terminal",
            "action_generation": selection.action_generation,
            "job_id": selection.action_job_id,
            "predecessor_receipt_ref": str(phase_ref.artifact_id),
            "authority_decision_ref": decision_ref,
            "owner_receipt_refs": tuple(
                sorted(
                    str(ref.artifact_id)
                    for ref in (
                        selection.predecessor_action_ref,
                        evaluation_decision_ref,
                        occurrence_ref,
                    )
                )
            ),
            "terminal_outcome": "candidate_blocked" if blocked else "candidate_evaluation_retained",
            "evaluation_decision_ref": None if blocked else evaluation_decision_ref,
            "selected_basis_ref": None if blocked else selected.basis_ref,
            "selected_evaluation_witness_ref": None if blocked else selected.n5_execution_ref,
            "selected_evaluation": None if blocked else selected,
            "current_continuation_ref": None if blocked else current_continuation_ref,
            "blocker_ref": evaluation_decision_ref if blocked else None,
            "blocker_reason": (
                "candidate_experiment_reuse_numerical_basis_not_established" if blocked else None
            ),
            "reuse_occurrence_ref": occurrence_ref,
        }
    )
    terminal = AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(terminal_fields)
    terminal_ref = _persist_fixture_receipt(store, terminal)
    current_head = SimpleNamespace(
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        source_job_id=selection.source_job_id,
        route_id=selection.route_id,
        action_generation=selection.action_generation,
        job_id=selection.action_job_id,
        receipt_ref=str(terminal_ref.artifact_id),
        receipt_manifest_profile_sha256=terminal_ref.manifest_profile_sha256,
        predecessor_receipt_ref=str(phase_ref.artifact_id),
        receipt_phase="terminal",
    )
    origin = VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        source_job_id=selection.source_job_id,
        source_payload_ref=selection.source_payload_ref,
        capability_manifest_ref=_hash("1"),
        request_content_hash=selection.request_content_hash,
        route_id=selection.route_id,
        policy_ref=selection.policy_ref,
        policy_scope=selection.policy_scope,
        generation_run=SimpleNamespace(),
        source_cycle=SimpleNamespace(),
        design_problem_basis=SimpleNamespace(),
        planner_report=SimpleNamespace(),
        planner_record=SimpleNamespace(),
        current_terminal_history=prior_history,
        candidate_terminal_history_chain=(prior_history,),
    )
    history = CandidateExperimentTerminalHistory(
        head=current_head,
        terminal_ref=terminal_ref,
        terminal=terminal,
        origin=origin,
        phase_chain=tuple(
            VerifiedAcquisitionActionPhase(
                receipt_ref=str(ref.artifact_id),
                receipt=receipt,
                durable_event_id=receipt.receipt_id + ".event",
                event=SimpleNamespace(),
            )
            for ref, receipt in (
                (requested_ref, requested),
                (phase_ref, executing),
                (terminal_ref, terminal),
            )
        ),
        action=action,
        source=source,
        budget_window=None,
        decision=None,
        current_basis=None,
        selected_basis=None,
        evaluation=None if blocked else evaluation,
        reentry=None,
        continuation=None,
        frontier_before=None,
        frontier_after=None,
        reuse_occurrence=occurrence,
        reuse_occurrence_ref=occurrence_ref,
    )
    return history, evaluation


@pytest.mark.parametrize(
    ("outcome", "selected_field"),
    [
        ("candidate_reentry_completed", "reentry_evaluation"),
        ("candidate_evaluation_retained", "evaluation"),
    ],
)
def test_selected_predecessor_evaluation_uses_terminal_bound_n5(
    outcome: str, selected_field: str
) -> None:
    evaluation = _resolved_evaluation()
    history = _history(outcome=outcome, evaluation=evaluation)

    selected = _selected_predecessor_evaluation(history)

    assert selected is evaluation
    assert selected.selected.n5_input_ref == evaluation.selected.n5_input_ref
    assert selected.selected.n5_execution_ref == evaluation.selected.n5_execution_ref
    assert selected.selected.n5_result_ref == evaluation.selected.n5_result_ref
    assert getattr(history, selected_field) is evaluation


def test_selected_predecessor_evaluation_accepts_v2_same_b_without_new_n5(
    tmp_path: Path,
) -> None:
    history, evaluation = _v2_reuse_history(FileSystemCAS(tmp_path / "cas"))

    selected = _selected_predecessor_evaluation(history)

    assert selected is evaluation
    assert history.reuse_occurrence is not None
    assert selected.selected.n5_input_ref == history.reuse_occurrence.selection.n5_input_ref
    assert selected.selected.n5_execution_ref == history.reuse_occurrence.selection.n5_execution_ref
    assert selected.selected.n5_result_ref == history.reuse_occurrence.selection.n5_result_ref
    assert history.action.action_generation == 1
    assert history.head.action_generation == 2
    assert history.origin.current_action_head is None
    assert history.terminal.predecessor_receipt_ref == history.phase_chain[-2].receipt_ref
    assert history.terminal.predecessor_receipt_ref != str(
        history.reuse_occurrence.selection.predecessor_terminal_ref.artifact_id
    )


def test_selected_predecessor_evaluation_rejects_unselected_or_blocked_v2_reuse(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    history, evaluation = _v2_reuse_history(store)

    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_predecessor_history_unverified",
    ):
        _selected_predecessor_evaluation(replace(history, reuse_occurrence_ref=None))

    blocked, _ = _v2_reuse_history(store, blocked=True)
    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_predecessor_history_unverified",
    ):
        _selected_predecessor_evaluation(blocked)

    # Keep the signed selection and job stable. Substitute only the profile
    # supplied by the resolved numerical evaluation.
    wrong_result_ref = evaluation.selected.n5_result_ref.model_copy(
        update={"manifest_profile_sha256": _hash("0")}
    )
    wrong_evaluation = replace(
        evaluation,
        selected=evaluation.selected.model_copy(update={"n5_result_ref": wrong_result_ref}),
    )
    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_predecessor_n5_binding_mismatch",
    ):
        _selected_predecessor_evaluation(replace(history, evaluation=wrong_evaluation))


def test_selected_predecessor_evaluation_rejects_missing_n5_evidence() -> None:
    history = _history(outcome="candidate_reentry_completed", evaluation=_resolved_evaluation())
    unbound = history.terminal.model_copy(
        update={
            "selected_evaluation_witness_ref": _ref(
                "runtime_quality.candidate_source_reentry_receipt", "c"
            )
        }
    )
    history = replace(history, terminal=unbound)

    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_predecessor_n5_binding_mismatch",
    ):
        _selected_predecessor_evaluation(history)


def test_reuse_action_tuple_is_distinct_no_fetch_and_binds_candidate_only_refs() -> None:
    selection = _reuse_action_selection()

    operation, invocation, intent = candidate_experiment_reuse_action_tuple(selection)

    assert operation.operation_id == CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND
    assert operation.operation_class == "BIND"
    assert operation.cost_model == {
        "source_fetch": "none",
        "new_n5_invocations": 0,
        "monetary_cost": "not_established",
    }
    assert operation.authority_transform == {"kind": "preserves"}
    assert len(operation.consumes) == 7
    assert [port.constraints["artifact_ref"] for port in operation.consumes] == [
        ref.model_dump(mode="json")
        for ref in (
            selection.predecessor_terminal_ref,
            selection.predecessor_action_ref,
            selection.source_ref,
            selection.n5_input_ref,
            selection.n5_execution_ref,
            selection.n5_result_ref,
            selection.policy_ref,
        )
    ]
    assert invocation.status == "started"
    assert invocation.applicability_result == "not_established"
    assert invocation.budget_delta == {}
    assert invocation.input_artifacts == []
    assert invocation.parameters["request"] == selection.request.model_dump(
        mode="json", exclude={"human_decision_record_ref"}
    )
    assert invocation.parameters["effect"] == {
        "purpose": "candidate_only",
        "source_fetch": "none",
        "new_n5_invocations": 0,
        "source_currentness": "source_currentness_not_established",
        "observed_admission": False,
        "publication_authority": False,
    }
    assert intent.action_kind == CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND
    assert "current_action_phase_ref" not in CandidateExperimentReuseActionSelection.model_fields


def test_human_decision_ref_stays_in_request_but_not_stable_pa2_action_identity() -> None:
    selection = _reuse_action_selection()
    request_with_human_ref = CandidateExperimentReuseActionRequest.model_validate(
        {
            **selection.request.model_dump(mode="python"),
            "human_decision_record_ref": _hash("a"),
        }
    )
    second = _reuse_action_selection(request=request_with_human_ref)

    _, first_invocation, _ = candidate_experiment_reuse_action_tuple(selection)
    _, second_invocation, _ = candidate_experiment_reuse_action_tuple(second)
    first_body = selection.request.model_dump(mode="json")
    second_body = second.request.model_dump(mode="json")

    assert second.action_job_id == selection.action_job_id
    assert first_body["human_decision_record_ref"] is None
    assert second_body["human_decision_record_ref"] == _hash("a")
    assert "human_decision_record_ref" not in second_invocation.parameters["request"]
    assert second_invocation.parameters == first_invocation.parameters
    assert second_invocation.invocation_id == first_invocation.invocation_id


def test_reuse_action_selection_rejects_same_bytes_with_different_selected_profile() -> None:
    selection = _reuse_action_selection()
    alternate_profile = selection.n5_result_ref.model_copy(
        update={"manifest_profile_sha256": _hash("5")}
    )
    assert alternate_profile.artifact_id == selection.n5_result_ref.artifact_id
    assert (
        alternate_profile.manifest_profile_sha256 != selection.n5_result_ref.manifest_profile_sha256
    )
    request = CandidateExperimentReuseActionRequest.model_validate(
        {
            **selection.request.model_dump(mode="python"),
            "n5_result_ref": alternate_profile,
        }
    )

    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_request_selection_mismatch",
    ):
        CandidateExperimentReuseActionSelection.model_validate(
            {**selection.model_dump(mode="python"), "request": request}
        )


def test_reuse_action_selection_rejects_wrong_predecessor_and_job_or_key_identity() -> None:
    selection = _reuse_action_selection()
    wrong_predecessor = _ref("runtime_quality.acquisition_route_loop_receipt", "5")
    request = CandidateExperimentReuseActionRequest.model_validate(
        {
            **selection.request.model_dump(mode="python"),
            "predecessor_terminal_ref": wrong_predecessor,
        }
    )
    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_request_selection_mismatch",
    ):
        CandidateExperimentReuseActionSelection.model_validate(
            {**selection.model_dump(mode="python"), "request": request}
        )

    with pytest.raises(ValueError, match="candidate_experiment_reuse_job_identity_mismatch"):
        CandidateExperimentReuseActionSelection.model_validate(
            {
                **selection.model_dump(mode="python"),
                "action_job_id": "candidate-experiment-reuse-" + ("f" * 64),
            }
        )

    changed_key_request = CandidateExperimentReuseActionRequest.model_validate(
        {
            **selection.request.model_dump(mode="python"),
            "idempotency_key": "different-reuse-request",
        }
    )
    with pytest.raises(ValueError, match="candidate_experiment_reuse_job_identity_mismatch"):
        CandidateExperimentReuseActionSelection.model_validate(
            {**selection.model_dump(mode="python"), "request": changed_key_request}
        )
