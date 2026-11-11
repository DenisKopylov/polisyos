"""Service-seam retry controls for an already verified action history.

The sink, authority and continuation ports are controlled collaborators here.
Real CAS/SQL phase replay and signed authorization have separate tests; these
checks establish no approval, numerical result or publication permission.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services import acquisition_action_service as owner
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
)
from polisyos.runtime.quality.acquisition_evaluation import CandidateExperimentTerminalHistory
from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    CandidateExperimentEvaluationPreflight,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
)
from polisyos.runtime.quality.agent_action_authority import AuthenticatedAgentActionDecisionHistory
from tests.unit.runtime.http.services.test_acquisition_action_service import (
    _candidate_current_action_head,
    _candidate_experiment_action_fixture,
)
from tests.unit.runtime.quality.test_candidate_experiment_authorization_refresh import _refreshed
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _hash,
    _ref,
    _requested_phase,
)


def _case(
    monkeypatch: pytest.MonkeyPatch, *, state: str, renewed_authority: bool = True
) -> dict[str, Any]:
    origin, request = _candidate_experiment_action_fixture()
    base = _requested_phase()
    origin.source_cycle.voi_decision = base.voi_decision.model_copy(
        update={"candidate_id": origin.policy_scope.candidate_id}
    )
    job_id = AcquisitionActionService._candidate_experiment_job_id(origin, request)
    requested = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        {
            **base.model_dump(mode="python"),
            "job_id": job_id,
            "tenant_id": origin.tenant_id,
            "cell_id": origin.cell_id,
            "run_id": origin.run_id,
            "source_job_id": origin.source_job_id,
            "route_id": origin.route_id,
            "source_payload_ref": origin.source_payload_ref,
            "request_content_hash": origin.request_content_hash,
            "policy_scope": origin.policy_scope,
            "policy_ref": origin.policy_ref,
            "voi_decision": origin.source_cycle.voi_decision,
        }
    )
    renewed = _refreshed(requested, _hash("3")) if renewed_authority else requested
    if state == "completed":
        action = _ref("runtime_quality.acquisition_candidate_action_receipt", "7")
        blocker = _ref("runtime_quality.candidate_experiment_blocker", "8")
        latest = AcquisitionCandidateExperimentTerminalReceipt.model_validate(
            {
                **{
                    k: v
                    for k, v in renewed.model_dump(mode="python").items()
                    if k in AcquisitionCandidateExperimentTerminalReceipt.model_fields
                },
                "schema_version": "AcquisitionCandidateExperimentTerminalReceipt@1.0",
                "receipt_id": job_id + ".terminal",
                "predecessor_receipt_ref": _hash("4"),
                "coarse_phase": "terminal",
                "receipt_phase": "terminal",
                "recovery_state": "complete",
                "terminal_outcome": "candidate_blocked",
                "candidate_action_ref": action,
                "blocker_ref": blocker,
                "blocker_reason": "controlled already-completed result",
                "owner_receipt_refs": (str(action.artifact_id), str(blocker.artifact_id)),
            }
        )
    elif state == "running":
        latest = renewed.model_copy(
            update={"receipt_phase": "executing", "coarse_phase": "executing"}
        )
    else:
        latest = renewed
    head = replace(
        _candidate_current_action_head(),
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
        job_id=job_id,
        action_generation=1,
        head_generation=3,
        receipt_phase=latest.receipt_phase,
        coarse_phase=latest.coarse_phase,
        recovery_state=latest.recovery_state,
    )
    selected = _ref(
        "runtime_quality.acquisition_route_loop_receipt"
        if state == "completed"
        else "runtime_quality.acquisition_candidate_experiment_phase_receipt",
        "9",
    )
    head = replace(
        head, receipt_ref=str(selected.artifact_id), receipt_sha256=str(selected.artifact_id)
    )
    chain = tuple(
        SimpleNamespace(receipt=receipt)
        for receipt in ((requested, renewed, latest) if renewed_authority else (requested, latest))
    )
    terminal_history = None
    if state == "completed":
        terminal_history = CandidateExperimentTerminalHistory(
            head=head,
            terminal_ref=selected,
            terminal=latest,
            origin=origin,
            phase_chain=chain,
            action=SimpleNamespace(),
            source=SimpleNamespace(),
            budget_window=None,
            decision=None,
            current_basis=None,
            selected_basis=None,
            evaluation=None,
            reentry=None,
            continuation=None,
            frontier_before=None,
            frontier_after=None,
        )
    outcome = SimpleNamespace(
        head=head,
        latest_receipt=latest,
        phase_chain=chain,
        candidate_experiment_terminal_history=terminal_history,
    )
    principal = RuntimePrincipal(
        subject="same-operator",
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        authenticated=True,
        roles=frozenset({"analyst"}),
    )
    initial_ref = str(requested.authority_decision_ref.artifact_id)
    effective_ref = str(renewed.authority_decision_ref.artifact_id)
    payload = {
        "action_kind": owner.CANDIDATE_EXPERIMENT_ACTION_KIND,
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "route_id": origin.route_id,
        "request": request.model_dump(mode="json"),
        "decision_ref": initial_ref,
    }
    job = SimpleNamespace(
        job_id=job_id,
        kind="acquisition",
        run_id=origin.run_id,
        state=state,
        submitted_by=principal.subject,
        payload_ref=_hash("a"),
    )
    store = SimpleNamespace(
        list_acquisition_action_heads_for_source=lambda **_: (head,), get_job=lambda _: job
    )
    sink = SimpleNamespace(verify_action_head=lambda _: outcome, get_head=lambda _: head)
    selection = object()
    continuation = CandidateExperimentEvaluationPreflight(
        origin=origin,
        selection=selection,
        policy_ref=origin.policy_ref,
        configured_profile=None,
        original_model_declaration=None,
        continuation_kind="candidate_source_reentry_n5",
    )
    port = SimpleNamespace(
        preflight_candidate_experiment=lambda **_: selection,
        _world_growth_bridge=SimpleNamespace(
            preflight_candidate_experiment_evaluation=lambda **_: continuation
        ),
    )
    service = object.__new__(AcquisitionActionService)
    calls: list[tuple[str, str]] = []

    def no_enqueue(**_kwargs):
        raise AssertionError("an existing action retry must not enqueue again")

    service.control_service = SimpleNamespace(
        _control_store=store,
        acquisition_route_sink=sink,
        _artifact_store=object(),
        enqueue_acquisition_job=no_enqueue,
    )
    service._candidate_experiment_origin_for_request = lambda **_: origin
    service._require_candidate_experiment_execution_port = lambda: port
    decision = SimpleNamespace(
        outcome="allowed",
        permission_snapshot=SimpleNamespace(subject=principal.subject, tenant_id=origin.tenant_id),
    )

    def history(**kwargs):
        ref = kwargs["decision_ref"]
        calls.append(("history", ref))
        return AuthenticatedAgentActionDecisionHistory(
            decision=decision,
            decision_ref=ref,
            payload_sha256=ref.removeprefix("sha256:"),
            durable_event_id="controlled-seam",
            signer_identity="controlled-seam",
        )

    service.load_candidate_experiment_decision_history = history

    def replay(**kwargs):
        calls.append(("replay", kwargs["decision_ref"]))
        return SimpleNamespace(
            load_persisted_decision=lambda _: SimpleNamespace(decision=decision),
            verify_bound_authorization=lambda **_: calls.append(("verify", effective_ref)),
        )

    service.replay_candidate_experiment_authority = replay
    monkeypatch.setattr(owner, "read_core_json_artifact", lambda *_: SimpleNamespace(value=payload))
    return {
        "service": service,
        "kwargs": {
            "tenant_id": origin.tenant_id,
            "cell_id": origin.cell_id,
            "run_id": origin.run_id,
            "route_id": origin.route_id,
            "request": request,
            "request_id": "retry",
            "principal": principal,
        },
        "initial": initial_ref,
        "effective": effective_ref,
        "selected": selected,
        "phase": latest.receipt_phase,
        "calls": calls,
        "payload": payload,
    }


@pytest.mark.parametrize("state", ["completed", "running", "pending"])
@pytest.mark.parametrize("caller", ["initial", "effective"])
def test_recorded_retry_reports_effective_authority_and_selected_phase_without_reenqueue(
    monkeypatch: pytest.MonkeyPatch, state: str, caller: str
) -> None:
    case = _case(monkeypatch, state=state)
    result = case["service"].execute_candidate_experiment(
        **case["kwargs"], decision_ref=case[caller]
    )
    assert result.authority_decision_ref == case["effective"]
    assert result.receipt_phase == case["phase"]
    assert result.selected_receipt_ref == case["selected"]
    assert case["payload"]["decision_ref"] == case["initial"]
    assert ("history", case["effective"]) in case["calls"]
    if state == "completed":
        assert result.status == "completed"
        assert all(name != "replay" for name, _ in case["calls"])
    else:
        assert result.status == "accepted"
        assert ("verify", case["effective"]) in case["calls"]


def test_completed_retry_cannot_attribute_execution_to_an_unrecorded_new_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(monkeypatch, state="completed")
    with pytest.raises(AcquisitionActionServiceError, match="action_history_conflict"):
        case["service"].execute_candidate_experiment(**case["kwargs"], decision_ref=_hash("9"))
    assert case["calls"] == []


@pytest.mark.parametrize("state", ["completed", "running", "pending"])
def test_legacy_unrenewed_retry_preserves_its_existing_v1_response_wire(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    case = _case(monkeypatch, state=state, renewed_authority=False)
    result = case["service"].execute_candidate_experiment(
        **case["kwargs"], decision_ref=case["initial"]
    )
    wire = result.model_dump(mode="json")
    assert wire == {
        "run_id": case["kwargs"]["run_id"],
        "route_id": case["kwargs"]["route_id"],
        "job_id": result.job_id,
        "authority_decision_ref": case["initial"],
        "status": "completed" if state == "completed" else "accepted",
        "receipt_phase": "terminal" if state == "completed" else "requested",
        "world_growth": "not_established",
    }
