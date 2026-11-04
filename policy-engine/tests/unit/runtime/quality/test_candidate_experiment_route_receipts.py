"""Component controls for candidate-experiment receipt shape and closed history.

Selected references here are test values, not CAS ownership evidence. These
checks do not establish a protected action, source rights, or a live lease.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionSelectedEvaluation
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
    AcquisitionRouteClosureError,
    AcquisitionRouteLoop,
    AcquisitionRoutePhaseReceipt,
    parse_acquisition_route_loop_receipt,
    parse_acquisition_route_phase_receipt,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.generation_cycle import LoopVOIDecision

NOW = datetime(2026, 11, 4, tzinfo=UTC)


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


def _ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_hash(digit),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_hash("f"),
    )


def _scope() -> CandidateUnpricedPolicyScope:
    return CandidateUnpricedPolicyScope(
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


def _common() -> dict[str, object]:
    return {
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
        "policy_scope": _scope(),
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
        "generated_at": NOW,
    }


def _phase(**updates: object) -> AcquisitionCandidateExperimentPhaseReceipt:
    return AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        {
            **_common(),
            "coarse_phase": "requested",
            "receipt_phase": "requested",
            "recovery_state": "none",
            **updates,
        }
    )


def test_phase_roundtrip_keeps_selected_inputs_and_actual_roi_without_cost_claim() -> None:
    phase = _phase()
    wire = phase.model_dump(mode="json")
    assert parse_acquisition_route_phase_receipt(wire) == phase
    assert phase.compiled_ref == _scope().compiled_ref
    assert phase.planner_report_hash == _scope().planner_report_hash
    assert wire["voi_decision"]["scheduler_action"] == "reject"
    assert wire["voi_decision"]["scheduler_reason"] == "roi_below_threshold"
    assert wire["request_content_hash"] == _hash("d")
    assert wire["monetary_cost"] == wire["information_value"] == "not_established"
    assert wire["observed_data_authority"] is wire["publication_authority"] is False
    assert "cost_basis_hash" not in wire
    assert "decision_ref" not in wire


@pytest.mark.parametrize(
    "update",
    [
        {"action_generation": True},
        {"tenant_id": "foreign-tenant"},
        {"policy_ref": _ref("runtime_quality.other_policy", "e")},
        {
            "policy_ref": _ref(
                "runtime_quality.candidate_unpriced_acquisition_policy", "e"
            ).model_copy(update={"manifest_profile_sha256": None})
        },
        {"authority_decision_ref": _ref("runtime_quality.other_decision", "0")},
        {"publication_authority": True},
        {"observed_data_authority": 0},
        {"cost_basis_hash": _hash("1")},
        {"predecessor_receipt_ref": _hash("1")},
        {
            "candidate_receipt_ref": _ref(
                "runtime_quality.acquisition_candidate_action_receipt", "1"
            )
        },
    ],
)
def test_invalid_source_authority_or_requested_phase_is_refused(update: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _phase(**update)


@pytest.mark.parametrize(
    ("action", "reason", "candidate"),
    [
        ("advance", "roi_below_threshold", "candidate-a"),
        ("reject", "budget_exhausted", "candidate-a"),
        ("reject", "roi_below_threshold", "candidate-b"),
    ],
)
def test_nonmatching_scheduler_decisions_are_not_relabelled_as_roi_rejection(
    action: str, reason: str, candidate: str
) -> None:
    decision = _common()["voi_decision"]
    assert isinstance(decision, LoopVOIDecision)
    with pytest.raises(ValidationError, match="candidate_experiment_identity_invalid"):
        _phase(
            voi_decision=decision.model_copy(
                update={
                    "scheduler_action": action,
                    "scheduler_reason": reason,
                    "candidate_id": candidate,
                }
            )
        )


def test_phase_requires_selected_action_in_owner_refs_after_execution() -> None:
    action = _ref("runtime_quality.acquisition_candidate_action_receipt", "1")
    executing = _phase(
        receipt_phase="executing",
        coarse_phase="executing",
        predecessor_receipt_ref=_hash("2"),
    )
    assert executing.candidate_receipt_ref is None
    selected = _phase(
        receipt_phase="outcome_selected",
        coarse_phase="executing",
        predecessor_receipt_ref=_hash("3"),
        candidate_receipt_ref=action,
        owner_receipt_refs=(str(action.artifact_id),),
    )
    assert selected.candidate_receipt_ref == action
    pending = _phase(
        receipt_phase="candidate_input_reentry_pending",
        coarse_phase="candidate_input_prepared",
        recovery_state="reentry_recovery_required",
        predecessor_receipt_ref=_hash("4"),
        candidate_receipt_ref=action,
        owner_receipt_refs=(str(action.artifact_id),),
    )
    assert pending.recovery_state == "reentry_recovery_required"
    with pytest.raises(ValidationError, match="candidate_experiment_phase_action_owner_missing"):
        _phase(
            receipt_phase="outcome_selected",
            coarse_phase="executing",
            predecessor_receipt_ref=_hash("3"),
            candidate_receipt_ref=action,
            owner_receipt_refs=(_hash("4"),),
        )


def _terminal_base() -> dict[str, object]:
    action = _ref("runtime_quality.acquisition_candidate_action_receipt", "1")
    return {
        **_common(),
        "receipt_id": "action-a.terminal",
        "predecessor_receipt_ref": _hash("2"),
        "candidate_action_ref": action,
        "owner_receipt_refs": (str(action.artifact_id),),
    }


def test_blocked_terminal_keeps_a_selected_blocker_and_no_evaluation_claim() -> None:
    blocker = _ref("runtime_quality.candidate_source_reentry_receipt", "3")
    data = {
        **_terminal_base(),
        "terminal_outcome": "candidate_blocked",
        "blocker_ref": blocker,
        "blocker_reason": "source_unavailable",
        "owner_receipt_refs": (_hash("1"), str(blocker.artifact_id)),
    }
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_validate(data)
    assert parse_acquisition_route_loop_receipt(terminal.model_dump(mode="json")) == terminal
    assert terminal.selected_evaluation is None
    assert terminal.publication_authority is False
    with pytest.raises(
        ValidationError, match="candidate_experiment_terminal_blocker_owner_missing"
    ):
        AcquisitionCandidateExperimentTerminalReceipt.model_validate(
            {**data, "owner_receipt_refs": (_hash("1"),)}
        )


def test_reentry_terminal_without_evaluation_binds_exact_blocked_witness() -> None:
    decision = _ref("runtime_quality.acquisition_evaluation_decision", "3")
    reentry = _ref("runtime_quality.candidate_source_reentry_receipt", "4")
    data = {
        **_terminal_base(),
        "terminal_outcome": "candidate_reentry_completed",
        "owner_receipt_refs": (_hash("1"), str(decision.artifact_id)),
        "candidate_reentry_ref": reentry,
        "evaluation_decision_ref": decision,
        "selected_basis_ref": _ref("runtime_quality.acquisition_evaluation_basis", "5"),
        "selected_evaluation_witness_ref": reentry,
    }
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_validate(data)
    assert terminal.reentry_receipt_ref == str(reentry.artifact_id)
    assert terminal.selected_evaluation is None
    changed_view = reentry.model_copy(update={"manifest_profile_sha256": _hash("e")})
    with pytest.raises(
        ValidationError, match="candidate_experiment_terminal_blocked_witness_invalid"
    ):
        AcquisitionCandidateExperimentTerminalReceipt.model_validate(
            {**data, "selected_evaluation_witness_ref": changed_view}
        )


def test_retained_terminal_binds_selected_basis_and_execution_view() -> None:
    decision = _ref("runtime_quality.acquisition_evaluation_decision", "3")
    basis = _ref("runtime_quality.acquisition_evaluation_basis", "4")
    execution = _ref("runtime.quality.candidate_simulation_execution", "5")
    selected = AcquisitionSelectedEvaluation(
        candidate_id="candidate-a",
        candidate_content_hash=_hash("3"),
        design_problem_ref=_hash("2"),
        world_model_record_hash=_hash("6"),
        evaluation_job_id="evaluation-a",
        evaluation_run_id="run-a",
        generation_run_id="generation-a",
        cycle_index=0,
        n4_source_ref=_ref("runtime.quality.n4_candidate_scenario_source", "6"),
        context_job_ref=_ref("runtime.quality.cycle_substrate_context_job", "7"),
        n5_input_ref=_ref("runtime.quality.candidate_simulation_n5_input", "8"),
        n5_execution_ref=execution,
        n5_result_ref=_ref("polisyos.runtime.joint_simulation_result", "9"),
        basis_ref=basis,
    )
    data = {
        **_terminal_base(),
        "terminal_outcome": "candidate_evaluation_retained",
        "owner_receipt_refs": (_hash("1"), str(decision.artifact_id)),
        "evaluation_decision_ref": decision,
        "selected_basis_ref": basis,
        "selected_evaluation_witness_ref": execution,
        "selected_evaluation": selected,
        "current_continuation_ref": _ref(
            "runtime_quality.candidate_acquisition_retained_continuation", "a"
        ),
    }
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_validate(data)
    assert terminal.selected_evaluation == selected
    changed_view = execution.model_copy(update={"manifest_profile_sha256": _hash("e")})
    with pytest.raises(ValidationError, match="candidate_experiment_terminal_evaluation_mismatch"):
        AcquisitionCandidateExperimentTerminalReceipt.model_validate(
            {**data, "selected_evaluation_witness_ref": changed_view}
        )
    for foreign in (
        {"candidate_id": "candidate-b"},
        {"candidate_content_hash": _hash("b")},
        {"design_problem_ref": _hash("1")},
        {"evaluation_run_id": "foreign-run"},
    ):
        with pytest.raises(
            ValidationError, match="candidate_experiment_terminal_evaluation_mismatch"
        ):
            AcquisitionCandidateExperimentTerminalReceipt.model_validate(
                {**data, "selected_evaluation": selected.model_copy(update=foreign)}
            )


def test_legacy_phase_uses_its_existing_versioned_reader() -> None:
    legacy = AcquisitionRoutePhaseReceipt(
        receipt_id="legacy",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        route_id=_hash("a"),
        action_generation=1,
        job_id="action-a",
        compiled_ref=_hash("1"),
        planner_report_hash=_hash("2"),
        cost_basis_hash=_hash("3"),
        decision_ref=_hash("4"),
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        generated_at=NOW,
    )
    wire = legacy.model_dump(mode="json")
    reopened = parse_acquisition_route_phase_receipt(wire)
    assert type(reopened) is AcquisitionRoutePhaseReceipt
    assert reopened.model_dump(mode="json") == wire


def _head(*, route_id: str) -> AcquisitionActionHeadRecord:
    return AcquisitionActionHeadRecord(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        route_id=route_id,
        action_generation=1,
        head_generation=1,
        receipt_ref=_hash("1"),
        receipt_sha256=_hash("1"),
        durable_event_id="event-a",
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        job_id="action-a",
        predecessor_receipt_ref=None,
        created_at=NOW,
    )


def test_fold_rejects_foreign_head_and_non_owner_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """The incomplete source fixture samples refusal, not real-owner replay."""
    origin = SimpleNamespace(source_job_id="source-a", route_id=_hash("a"))
    monkeypatch.setattr(
        AcquisitionRouteLoop, "_resolve_candidate_experiment_source", lambda *_args, **_kw: origin
    )

    class Store:
        heads: tuple[AcquisitionActionHeadRecord, ...] = (_head(route_id=_hash("b")),)

        def list_acquisition_action_heads_for_source(self, **_scope: object) -> tuple:
            return self.heads

    class ClaimedReader:
        called = False

        def experiment_action_outcomes(self, **_scope: object) -> tuple:
            self.called = True
            return ()

    store = Store()
    claimed_reader = ClaimedReader()
    loop = object.__new__(AcquisitionRouteLoop)
    loop._tenant_id = "tenant-a"
    loop._cell_id = "cell-a"
    loop._control_store = store
    loop._artifact_store = object()
    loop._event_log = object()
    loop._core_source_resolver = object()
    loop._action_outcome_reader = claimed_reader
    with pytest.raises(
        AcquisitionRouteClosureError, match="candidate_experiment_foreign_action_head"
    ):
        loop.resolve_current_candidate_experiment(run_id="run-a")
    store.heads = ()
    with pytest.raises(
        AcquisitionRouteClosureError, match="candidate_experiment_history_owner_not_composed"
    ):
        loop.resolve_current_candidate_experiment(run_id="run-a")
    assert not claimed_reader.called


def test_historical_cutoff_refuses_until_exclusive_fold_is_available() -> None:
    loop = object.__new__(AcquisitionRouteLoop)
    for cutoff in (1, 2, True):
        with pytest.raises(
            AcquisitionRouteClosureError,
            match="candidate_experiment_historical_cutoff_not_established",
        ):
            loop.resolve_current_candidate_experiment(
                run_id="run-a", before_action_generation=cutoff
            )
