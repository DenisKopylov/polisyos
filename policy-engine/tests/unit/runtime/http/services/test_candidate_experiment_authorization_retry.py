"""Service-seam retry controls for an already verified action history.

The sink, authority and continuation ports are controlled collaborators here.
Real CAS/SQL phase replay and signed authorization have separate tests; these
checks establish no approval, numerical result or publication permission.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
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
    VerifiedCandidateExperimentOrigin,
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


@dataclass(frozen=True)
class _FixtureVoiDecision:
    scheduler_action: str
    scheduler_reason: str


@dataclass(frozen=True)
class _FixtureCycle:
    cycle_index: int
    voi_decision: _FixtureVoiDecision


def _verified_origin(base: Any) -> VerifiedCandidateExperimentOrigin:
    """Build the exact source carrier needed by execute revalidation tests."""
    voi = base.source_cycle.voi_decision
    return VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=base.tenant_id,
        cell_id=base.cell_id,
        run_id=base.run_id,
        source_job_id=base.source_job_id,
        source_payload_ref=base.source_payload_ref,
        capability_manifest_ref=base.capability_manifest_ref,
        request_content_hash=base.request_content_hash,
        route_id=base.route_id,
        policy_ref=base.policy_ref,
        policy_scope=base.policy_scope,
        generation_run=None,
        source_cycle=_FixtureCycle(
            cycle_index=base.source_cycle.cycle_index,
            voi_decision=_FixtureVoiDecision(
                scheduler_action=voi.scheduler_action, scheduler_reason=voi.scheduler_reason
            ),
        ),
        design_problem_basis=None,
        planner_report=None,
        planner_record=None,
    )


def _case(
    monkeypatch: pytest.MonkeyPatch, *, state: str, renewed_authority: bool = True
) -> dict[str, Any]:
    origin, request = _candidate_experiment_action_fixture()
    base = _requested_phase()
    origin.source_cycle.voi_decision = base.voi_decision.model_copy(
        update={"candidate_id": origin.policy_scope.candidate_id}
    )
    origin.capability_manifest_ref = _hash("b")
    origin.current_action_head = None
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
    source_job = SimpleNamespace(job_id=origin.source_job_id)
    source_event = {"job_id": origin.source_job_id}
    source_outbox = SimpleNamespace(payload=source_event)
    source_inputs = source_job, source_event, source_outbox
    store = SimpleNamespace(
        list_acquisition_action_heads_for_source=lambda **_: () if state == "new" else (head,),
        get_job=lambda selected: source_job
        if selected == origin.source_job_id
        else (None if state == "new" else job),
        get_job_created_event_payload=lambda _: source_event,
        get_job_created_outbox_event=lambda _: source_outbox,
    )
    reused_head_origins: list[object] = []
    sink = SimpleNamespace(
        verify_action_head=lambda _: outcome,
        _verify_action_head_with_origin=lambda _head, *, verified_origin: (
            reused_head_origins.append(verified_origin) or outcome
        ),
        get_head=lambda _: head,
    )
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
    history_requests: list[dict[str, Any]] = []

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
        history_requests.append(kwargs)
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

    service._require_authority_provider = lambda: SimpleNamespace(
        for_candidate_experiment_job=replay
    )
    service._revalidate_candidate_experiment_execute_origin = lambda **_: origin
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
        "history_requests": history_requests,
        "origin": origin,
        "store": store,
        "sink": sink,
        "reused_head_origins": reused_head_origins,
        "terminal_history": terminal_history,
        "port": port,
        "continuation": continuation,
        "source_inputs": source_inputs,
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


@pytest.mark.parametrize("state", ["new", "pending", "running"])
def test_execute_carries_original_history_without_reusing_the_pending_origin(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """History uses this call's original proof while the live replay stays separate."""
    case = _case(monkeypatch, state=state)
    service = case["service"]
    historical_origin = case["origin"]
    current_origin = SimpleNamespace(
        **{
            **vars(historical_origin),
            "current_action_head": None if state == "new" else case["sink"].get_head(None),
        }
    )
    origin_reads: list[bool] = []
    execute_origin_reads: list[dict[str, Any]] = []

    def resolve_origin(**kwargs):
        origin_reads.append(kwargs["require_current"])
        return historical_origin

    def revalidate_origin(**kwargs):
        execute_origin_reads.append(kwargs)
        return current_origin

    service._candidate_experiment_origin_for_request = resolve_origin
    service._revalidate_candidate_experiment_execute_origin = revalidate_origin
    case["port"]._world_growth_bridge.preflight_candidate_experiment_evaluation = (
        lambda **_: replace(case["continuation"], origin=current_origin)
    )
    enqueued: list[dict[str, Any]] = []
    execute_options = {}
    if state == "new":

        @dataclass(frozen=True)
        class PreparedPublication:
            """Controlled publication carrier; SQL admission has separate coverage."""

            step_up_expires_at: int | None = None

        deadline = int(time.time()) + 300
        execute_options["step_up_expires_at"] = deadline
        service.control_service.enqueue_acquisition_job = lambda **values: enqueued.append(values)
        case["sink"].prepare_experiment_phase_publication = lambda *_: PreparedPublication()
        monkeypatch.setattr(
            owner.artifacts,
            "profile_bound_ref",
            lambda _store, ref: ref.model_copy(update={"manifest_profile_sha256": _hash("f")}),
        )

    result = service.execute_candidate_experiment(
        **case["kwargs"], decision_ref=case["effective"], **execute_options
    )

    assert result.status == "accepted"
    assert origin_reads == [False]
    assert len(execute_origin_reads) == 2
    assert execute_origin_reads[0]["origin"] is historical_origin
    assert execute_origin_reads[0]["expected_head"] is (
        case["sink"].get_head(None) if state in {"pending", "running"} else None
    )
    assert execute_origin_reads[1]["origin"] is current_origin
    assert execute_origin_reads[1]["expected_head"] is current_origin.current_action_head
    assert case["reused_head_origins"] == ([historical_origin] if state == "pending" else [])
    (history_request,) = case["history_requests"]
    assert history_request["verified_origin"] is historical_origin
    assert historical_origin.current_action_head is None
    assert (current_origin.current_action_head is None) == (state == "new")
    assert all(
        actual is expected
        for actual, expected in zip(
            history_request["verified_source_inputs"], case["source_inputs"], strict=True
        )
    )
    assert case["calls"] == [
        ("history", case["effective"]),
        ("replay", case["effective"]),
        ("verify", case["effective"]),
    ]
    assert len(enqueued) == (1 if state == "new" else 0)
    if state == "new":
        assert enqueued[0]["prepared_acquisition_action_head"].step_up_expires_at == deadline


@pytest.mark.parametrize(
    "movement",
    [
        "stable_default",
        "changed_current_policy",
        "unexpected_head",
        "stable_predecessor",
        "changed_predecessor_head",
        "changed_predecessor_cas",
        "stable_pending",
        "changed_pending_head",
    ],
)
def test_execute_origin_revalidation_reopens_live_policy_and_exact_heads(
    monkeypatch: pytest.MonkeyPatch, movement: str
) -> None:
    """The execute shortcut rechecks current policy and the complete SQL frontier."""
    from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord

    case = _case(monkeypatch, state="new")
    del case["service"]._revalidate_candidate_experiment_execute_origin
    origin = _verified_origin(case["origin"])
    request = case["kwargs"]["request"]
    expected_head = None
    selected_head = None
    selected_receipt = None
    heads: tuple[AcquisitionActionHeadRecord, ...] = ()
    if movement in {
        "stable_predecessor",
        "changed_predecessor_head",
        "changed_predecessor_cas",
    }:
        prior = _case(monkeypatch, state="completed")["terminal_history"]
        origin = replace(origin, candidate_terminal_history_chain=(prior,))
        request = request.model_copy(
            update={
                "replay_pins": request.replay_pins.model_copy(
                    update={"predecessor_terminal_ref": prior.terminal_ref}
                )
            }
        )
        heads = (prior.head,)
        selected_head = prior.head
        selected_receipt = prior.terminal
        if movement == "changed_predecessor_head":
            selected_head = replace(prior.head, receipt_ref=_hash("8"), receipt_sha256=_hash("8"))
        elif movement == "changed_predecessor_cas":
            selected_receipt = prior.terminal.model_copy(update={"receipt_id": "changed"})
    action_job_id = AcquisitionActionService._candidate_experiment_job_id(origin, request)
    if movement in {"unexpected_head", "stable_pending", "changed_pending_head"}:
        pending = replace(
            _candidate_current_action_head(),
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            source_job_id=origin.source_job_id,
            route_id=origin.route_id,
            job_id="foreign-job" if movement == "unexpected_head" else action_job_id,
            action_generation=1,
            receipt_phase="requested",
            coarse_phase="requested",
            recovery_state="none",
        )
        heads = (pending,)
        if movement != "unexpected_head":
            expected_head = pending
        if movement == "changed_pending_head":
            heads = (replace(pending, receipt_ref=_hash("7"), receipt_sha256=_hash("7")),)

    live_root = replace(
        origin,
        current_action_head=None,
        current_terminal_history=None,
        candidate_terminal_history_chain=(),
    )
    if movement == "changed_current_policy":
        live_root = replace(
            live_root,
            policy_ref=_ref("runtime_quality.candidate_unpriced_acquisition_policy", "b"),
        )
    root_reads: list[str] = []
    loop = SimpleNamespace(
        _resolve_candidate_experiment_source=lambda *, run_id: (
            root_reads.append(run_id) or live_root
        ),
        _selected_candidate_experiment_receipt=lambda _head: selected_receipt,
    )
    case["service"]._candidate_experiment_loop = lambda **_: loop
    selected_reads: list[int] = []
    case["service"].control_service._control_store = SimpleNamespace(
        list_acquisition_action_heads_for_source=lambda **_: heads,
        get_acquisition_action_head=lambda **kwargs: selected_reads.append(
            kwargs["action_generation"]
        )
        or selected_head,
    )

    if movement in {
        "changed_current_policy",
        "unexpected_head",
        "changed_predecessor_head",
        "changed_predecessor_cas",
        "changed_pending_head",
    }:
        with pytest.raises(AcquisitionActionServiceError):
            case["service"]._revalidate_candidate_experiment_execute_origin(
                origin=origin, request=request, expected_head=expected_head
            )
    else:
        current = case["service"]._revalidate_candidate_experiment_execute_origin(
            origin=origin, request=request, expected_head=expected_head
        )
        assert current.current_action_head == expected_head
    assert root_reads == [origin.run_id]
    assert selected_reads == (
        [1]
        if movement
        in {
            "stable_predecessor",
            "changed_predecessor_head",
            "changed_predecessor_cas",
        }
        else []
    )


@pytest.mark.parametrize("movement", ["source_job", "source_head"])
def test_execute_carried_history_rechecks_actual_rows_before_authority_or_enqueue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, movement: str
) -> None:
    """SQL movement after the origin read invalidates the carried historical proof.

    The source proof and authority collaborators remain controlled seams. The
    actual history loader must reject the changed SQL before reaching either.
    """
    from contextlib import closing

    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedCandidateExperimentOrigin
    from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_job

    case = _case(monkeypatch, state="new")
    service = case["service"]
    base = case["origin"]
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "execute-history.sqlite3")
    ) as database:
        source_job = _create_job(
            database,
            job_id=base.source_job_id,
            kind="natural_language_run",
            run_id=base.run_id,
        )
        origin = VerifiedCandidateExperimentOrigin(
            schema_version="polisyos.runtime.candidate_experiment_origin.v1",
            **{
                key: getattr(base, key)
                for key in (
                    "tenant_id",
                    "cell_id",
                    "run_id",
                    "source_job_id",
                    "request_content_hash",
                    "route_id",
                    "policy_ref",
                    "policy_scope",
                    "source_cycle",
                )
            },
            source_payload_ref=source_job.payload_ref,
            capability_manifest_ref=source_job.capability_manifest_ref,
            generation_run=None,
            design_problem_basis=None,
            planner_report=None,
            planner_record=None,
        )
        request = case["kwargs"]["request"]
        case["kwargs"]["request"] = request.model_copy(
            update={
                "replay_pins": request.replay_pins.model_copy(
                    update={"source_payload_ref": source_job.payload_ref}
                )
            }
        )
        service.control_service._control_store = database
        service._candidate_experiment_origin_for_request = lambda **_: origin
        service._revalidate_candidate_experiment_execute_origin = lambda **_: origin
        service.load_candidate_experiment_decision_history = (
            lambda **values: AcquisitionActionService.load_candidate_experiment_decision_history(
                service, **values
            )
        )

        def forbid_source_proof(**_kwargs):
            pytest.fail("changed SQL reached source proof reuse")

        def forbid_authority():
            pytest.fail("changed SQL reached PA2 history")

        service._candidate_experiment_loop = forbid_source_proof
        service._require_candidate_experiment_authority_provider = forbid_authority
        service._require_authority_provider = forbid_authority

        def move_rows(**_kwargs):
            if movement == "source_job":
                database._execute(
                    "UPDATE control_jobs SET payload_ref = ? WHERE job_id = ?",
                    (_hash("e"), source_job.job_id),
                )
            else:
                database._execute(
                    "INSERT INTO runtime_acquisition_action_heads "
                    "(tenant_id,cell_id,run_id,source_job_id,route_id,action_generation,"
                    "head_generation,receipt_ref,receipt_sha256,durable_event_id,coarse_phase,"
                    "receipt_phase,recovery_state,job_id,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        origin.tenant_id,
                        origin.cell_id,
                        origin.run_id,
                        origin.source_job_id,
                        _hash("0"),
                        1,
                        1,
                        _hash("1"),
                        _hash("1"),
                        "changed-history-head",
                        "requested",
                        "requested",
                        "none",
                        "foreign-action",
                        "2026-11-18T00:00:00+00:00",
                    ),
                )
            return replace(case["continuation"], origin=origin)

        case["port"]._world_growth_bridge.preflight_candidate_experiment_evaluation = move_rows
        reason = (
            "candidate_experiment_history_source_changed"
            if movement == "source_job"
            else "candidate_experiment_action_history_conflict"
        )
        with pytest.raises(AcquisitionActionServiceError, match=reason):
            service.execute_candidate_experiment(**case["kwargs"], decision_ref=case["effective"])
        assert case["calls"] == []


@pytest.mark.parametrize("state", ["new", "pending", "running"])
def test_execute_expired_step_up_stops_after_live_authority_before_publication(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """An expired supplied deadline cannot publish or refresh an admitted action."""
    case = _case(monkeypatch, state=state)
    with pytest.raises(AcquisitionActionServiceError, match="candidate_experiment_step_up_"):
        case["service"].execute_candidate_experiment(
            **case["kwargs"], decision_ref=case["effective"], step_up_expires_at=1
        )
    assert case["calls"] == [
        ("history", case["effective"]),
        ("replay", case["effective"]),
        ("verify", case["effective"]),
    ]


@pytest.mark.parametrize("supply_deadline", [False, True])
def test_pending_refresh_carries_supplied_deadline_and_preserves_legacy_call(
    monkeypatch: pytest.MonkeyPatch, supply_deadline: bool
) -> None:
    """Only an explicitly supplied deadline is added to the refresh publication."""
    case = _case(monkeypatch, state="pending")
    service = case["service"]
    deadline = int(time.time()) + 300
    options = {"step_up_expires_at": deadline} if supply_deadline else {}
    refreshed: list[dict[str, Any]] = []

    def refresh(_phase, _request, *, expected_job, **kwargs):
        assert expected_job == case["store"].get_job(case["sink"].get_head(None).job_id)
        refreshed.append(kwargs)
        return case["sink"].get_head(None)

    case["sink"].refresh_experiment_authorization = refresh
    monkeypatch.setattr(
        owner.artifacts,
        "profile_bound_ref",
        lambda _store, ref: ref.model_copy(update={"manifest_profile_sha256": _hash("f")}),
    )
    decision_ref = _hash("9")
    result = service.execute_candidate_experiment(
        **case["kwargs"], decision_ref=decision_ref, **options
    )
    assert result.authority_decision_ref == decision_ref
    assert result.receipt_phase == "authorization_refreshed"
    assert refreshed == [options]
