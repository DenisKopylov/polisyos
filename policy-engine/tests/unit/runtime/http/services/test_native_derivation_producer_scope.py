"""Actual traced LLM begin/settlement under the Native budget composition.

The source admission and current-phase resolver are explicit scripted boundaries.
The ledger, action-window selector, observer, traced client, begin/readback and
settlement are real. These controls do not establish a real Native source,
protected action grant, N4 run, provider invoice, or numerical simulation.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import ClassVar

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, artifact_ref_for_manifest
from polisyos.core.llm import LLMSettlementOwnershipError, TracedLLMClient
from polisyos.core.llm.settlement import LLMManagedProducerOutcomeError, LLMSettledResponse
from polisyos.core.llm.traced_client import has_managed_prepared_producer_request
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.quality import native_settled_draft
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthAttempt
from polisyos.runtime.quality.design_generation import RecordingLLMClient
from polisyos.scientist.orchestration.engine import (
    BudgetExhaustedError,
    BudgetState,
    ProducerBudgetObserver,
)
from polisyos.scientist.orchestration.llm._n4_request import _request_args
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    create_traced_gateway_client,
)
from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
    _settle,
    _unit_window,
)


def _producer_case(tmp_path, monkeypatch):
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "prior-source", Decimal("0.01"))
    binding = case.binding
    case.closure.source_job_id = binding.control_job_id
    case.closure.tenant_id = binding.tenant_id
    case.closure.cell_id = binding.cell_id
    case.closure.route_id = case.boundary.phase.route_id
    service = ControlPlaneService.__new__(ControlPlaneService)
    service._llm_producer_settlement_store = case.service._llm_producer_settlement_store
    service._control_store = SimpleNamespace(
        get_job=lambda _: SimpleNamespace(state="completed", attempt=7),
        current_native_acquisition_custody_recovery=lambda: None,
    )
    service._artifact_store = object()
    service._diagnostic_event_log = object()
    case.bridge._source_control_service = service
    monkeypatch.setattr(service, "verify_acquisition_source_budget_owner", lambda **_: binding)
    monkeypatch.setattr(service, "acquisition_source_global_budget_usd", lambda **_: Decimal("5"))
    monkeypatch.setattr(
        case.bridge,
        "_current_native_reentry_action",
        lambda **_: (case.boundary.selection, case.boundary.phase, case.boundary.admission),
    )
    monkeypatch.setattr(
        case.bridge,
        "_native_derivation_budget_profile",
        lambda _: (None, case.boundary.selection.profile_selection_ref),
    )
    window = case.bridge._native_derivation_budget_window(
        closure=case.closure, action_phase_ref=case.boundary.phase_ref, create=True
    )
    state = BudgetState.model_validate(
        {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
    )
    observer = ProducerBudgetObserver(
        settlement_store=service._llm_producer_settlement_store,
        producer_run_binding=binding,
        budget_state=state,
        reentry_budget_scope=window.scope,
        invocation_selection_pending=True,
    )
    return case, service, window, observer


def _client():
    client = create_traced_gateway_client(
        model_name="simulated-qwen",
        config=GatewayLLMConfig(
            base_url="http://fixture.invalid", api_key="fixture", cache_maxsize=0
        ),
    )
    assert client is not None
    return client


@pytest.mark.asyncio
async def test_native_scope_reuses_original_ledger_and_settles_actual_begin(tmp_path, monkeypatch):
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    case, service, window, observer = _producer_case(tmp_path, monkeypatch)
    with service.native_derivation_producer_scope(
        bridge=case.bridge,
        closure=case.closure,
        observer=observer,
        reentry_budget_scope=window.scope,
    ):
        client = _client()
        await client.generate(user="bounded controlled candidate", temperature=0)
        assert len(client.unwrap().calls) == 1
    rows = service._llm_producer_settlement_store.list_producer_events_for_run_safe(case.binding)
    actual = [row for row in rows if row.event_id != "prior-source"]
    assert len(actual) == 1
    assert actual[0].status == "committed"
    assert actual[0].run_binding == case.binding
    assert actual[0].key == f"nl-run:{case.binding.run_id}"
    # Current action admission is separate from original producer attribution.
    assert actual[0].control_job_attempt == 7
    assert observer.observe().producer_spent_usd >= 0


@pytest.mark.asyncio
@pytest.mark.parametrize("graft", ["lease", "window", "budget"])
async def test_native_scope_refuses_changed_owner_before_dispatch(tmp_path, monkeypatch, graft):
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    case, service, window, observer = _producer_case(tmp_path, monkeypatch)
    with service.native_derivation_producer_scope(
        bridge=case.bridge,
        closure=case.closure,
        observer=observer,
        reentry_budget_scope=window.scope,
    ):
        client = _client()
        if graft == "lease":
            case.boundary.admission = replace(case.boundary.admission, attempt=2)
        elif graft == "window":
            monkeypatch.setattr(
                service._llm_producer_settlement_store,
                "resolve_reentry_budget_window_safe",
                lambda _: None,
            )
        else:
            _settle(case, "other-source-spend", Decimal("0.11"))
        expected_error = BudgetExhaustedError if graft == "budget" else ValueError
        with pytest.raises(expected_error) as caught:
            await client.generate(user="must not dispatch", temperature=0)
        if graft == "budget":
            assert "current USD run allocation exhausted" in str(caught.value)
        assert not client.unwrap().calls
    rows = service._llm_producer_settlement_store.list_producer_events_for_run_safe(case.binding)
    assert all(row.event_id in {"prior-source", "other-source-spend"} for row in rows)


@pytest.mark.asyncio
async def test_native_scope_requires_actual_begin_readback_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    case, service, window, observer = _producer_case(tmp_path, monkeypatch)
    with service.native_derivation_producer_scope(
        bridge=case.bridge,
        closure=case.closure,
        observer=observer,
        reentry_budget_scope=window.scope,
    ):
        client = _client()
        monkeypatch.setattr(
            service._llm_producer_settlement_store, "resolve_producer_event_safe", lambda _: None
        )
        with pytest.raises(ValueError, match="native_reentry_producer_begin_readback_mismatch"):
            await client.generate(user="must retain real begin", temperature=0)
        assert not client.unwrap().calls
    rows = service._llm_producer_settlement_store.list_producer_events_for_run_safe(case.binding)
    assert len(rows) == 2
    assert sum(row.status == "pending" for row in rows) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "drift", [None, "post_begin", "source", "deferral", "lease", "head", "window_lease"]
)
@pytest.mark.parametrize("outer_trace", [False, True], ids=["direct", "nested"])
async def test_owned_direct_native_scope_rechecks_at_transaction_and_actual_post(
    tmp_path, monkeypatch, drift, outer_trace
):
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    case, service, window, observer = _producer_case(tmp_path, monkeypatch)
    budget = service._llm_producer_settlement_store
    control = service._control_store
    scope = case.boundary
    selected_head = SimpleNamespace(route_id=scope.phase.route_id, revision=4)
    head = selected_head
    recovery = SimpleNamespace(
        settled_draft=object(),
        failed_lease_started_at=datetime.now(UTC),
        event=SimpleNamespace(
            payload={"failed_event": {"created_at": datetime.now(UTC).isoformat()}}
        ),
        head=selected_head,
    )
    control.current_native_acquisition_custody_recovery = lambda: recovery
    control.current_execution_job_admission = lambda: scope.admission
    control.current_execution_job_record = lambda: SimpleNamespace(
        job_id=scope.admission.job.job_id,
        lease_owner=scope.admission.job.lease_owner,
        attempt=scope.admission.attempt,
    )
    control.list_acquisition_action_heads_for_source = lambda **_: (head,)
    cas = service._artifact_store = FileSystemCAS(tmp_path / "paid-cas")
    stored = cas.put_json(
        {"disposition": "quarantined_no_growth"},
        ArtifactWriteOptions(
            kind="runtime_quality.acquisition_world_growth_native_admission_deferral",
            media_type="application/json",
        ),
    )
    deferral = artifact_ref_for_manifest(cas.get_manifest(stored))
    sidecar = cas._manifest_path_for_ref(deferral.artifact_id, deferral.manifest_profile_sha256)
    assert deferral.manifest_profile_sha256 is not None and sidecar.is_file()
    paid = case.closure.prior_paid_input_admission = SimpleNamespace(
        attempt_ref=object(), lineage_inputs=lambda: (("deferral", deferral),)
    )
    monkeypatch.setattr(
        case.bridge,
        "_read",
        lambda *_, **__: AcquisitionWorldGrowthAttempt.model_construct(selection=scope.selection),
    )
    monkeypatch.setattr(case.bridge, "_growth_pointer", lambda *_, **__: tmp_path / "world.json")
    monkeypatch.setattr(case.bridge, "_attempt_pointer_ref", lambda *_, **__: paid.attempt_ref)
    monkeypatch.setattr(native_settled_draft, "_verify_settled_draft", lambda *_, **__: None)
    monkeypatch.setattr(
        native_settled_draft, "_native_settled_draft_scope", lambda *_: nullcontext()
    )

    calls = []
    revoked = False
    transport_session_ready = False

    def resolve_current(**_):
        calls.append("full")
        if revoked:
            raise ValueError("selected paid proof revoked")
        return scope.selection, scope.phase, scope.admission

    def validate_live_source(*_):
        calls.append("live")
        if revoked:
            raise ValueError("selected paid proof revoked")

    monkeypatch.setattr(case.bridge, "_current_native_reentry_action", resolve_current)
    monkeypatch.setattr(
        case.bridge, "_verify_paid_native_attempt_current_source", validate_live_source
    )
    real_begin = budget.begin_producer_event_safe

    def begin(*args, **kwargs):
        nonlocal revoked
        record = real_begin(*args, **kwargs)
        if drift == "post_begin":
            revoked = True
        return record

    monkeypatch.setattr(budget, "begin_producer_event_safe", begin)
    read_window = budget.resolve_reentry_budget_window_safe

    def resolve_window(reentry_scope):
        result = read_window(reentry_scope)
        if drift == "window_lease" and transport_session_ready:
            scope.admission = replace(scope.admission, attempt=scope.admission.attempt + 1)
        return result

    monkeypatch.setattr(budget, "resolve_reentry_budget_window_safe", resolve_window)

    class Answer:
        status = 200
        headers: ClassVar[dict[str, str]] = {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def text(self):
            return '{"choices":[{"message":{"content":"{}"}}],"usage":{"cost_usd":0.001}}'

    class Session:
        def post(self, _url, **_kwargs):
            calls.append("post")
            return Answer()

    async def session(_timeout):
        nonlocal head, revoked, transport_session_ready
        transport_session_ready = True
        if drift == "source":
            revoked = True
        elif drift == "deferral":
            sidecar.unlink()
        elif drift == "lease":
            scope.admission = replace(scope.admission, attempt=scope.admission.attempt + 1)
        elif drift == "head":
            head = SimpleNamespace(route_id=scope.phase.route_id, revision=5)
        return Session()

    observations = []
    with service.native_derivation_producer_scope(
        bridge=case.bridge,
        closure=case.closure,
        observer=observer,
        reentry_budget_scope=window.scope,
    ):
        client = create_traced_gateway_client(
            model_name="m",
            call_observer=observations.append,
            config=GatewayLLMConfig(
                base_url="http://fixture.invalid",
                api_key="fixture",
                max_retries=0,
                cache_maxsize=0,
                enable_prompt_sanitizer=False,
            ),
        )
        assert client is not None
        monkeypatch.setattr(client.unwrap(), "_ensure_session", session)
        recorder = RecordingLLMClient(
            client, model_id="m", producer_problem_ref="sha256:" + "a" * 64
        )
        caller = TracedLLMClient(recorder) if outer_trace else recorder
        request = _request_args(
            caller,
            stage="formalizer" if outer_trace else "drafter_multipass",
            instance=None if outer_trace else "side_effects_check",
            system="system",
            user="candidate",
        )
        assert has_managed_prepared_producer_request(caller, request)
        calls.clear()
        if drift is None:
            result = await caller.generate(**request)
            assert type(result) is LLMSettledResponse
            assert result.content == "{}"
        else:
            with pytest.raises(
                LLMManagedProducerOutcomeError, match="managed_admission_failed"
            ) as refused:
                await caller.generate(**request)
            cause = refused.value.__cause__
            assert isinstance(cause, LLMSettlementOwnershipError)
            assert str(cause) in {
                "producer_managed_direct_admission_failed",
                "producer_managed_direct_dispatch_refused",
            }
            assert isinstance(cause.__cause__, ValueError)
        if outer_trace and drift is None:
            successful_calls = list(calls)
            records_before_conflicts = budget.list_producer_events_for_run_safe(case.binding)
            for other_caller, refusal in (
                (
                    TracedLLMClient(recorder, producer_settlement_store=budget),
                    "producer_prepared_transport_outer_conflict",
                ),
                (TracedLLMClient(caller), "producer_prepared_transport_changed"),
            ):
                other_request = _request_args(
                    other_caller, stage="formalizer", system="system", user="candidate"
                )
                calls.clear()
                if refusal == "producer_prepared_transport_outer_conflict":
                    with pytest.raises(LLMManagedProducerOutcomeError) as rejected_owner:
                        has_managed_prepared_producer_request(other_caller, other_request)
                    assert rejected_owner.value.reason == "managed_admission_failed"
                    assert isinstance(rejected_owner.value.__cause__, LLMSettlementOwnershipError)
                else:
                    assert not has_managed_prepared_producer_request(other_caller, other_request)
                with pytest.raises(LLMSettlementOwnershipError, match=refusal):
                    await other_caller.generate(**other_request)
                assert not calls
            assert records_before_conflicts == budget.list_producer_events_for_run_safe(
                case.binding
            )
            calls[:] = successful_calls
    expected = ["full", "full"]
    if drift not in ("post_begin", "deferral"):
        expected.append("live")
    if drift is None:
        expected.append("post")
    assert calls == expected
    records = budget.list_producer_events_for_run_safe(case.binding)
    (new_event,) = (record for record in records if record.event_id != "prior-source")
    assert new_event.status == ("committed" if drift is None else "pending")
    assert len(observations) == (1 if drift is None else 0)
    if drift is None:
        ack = result.settlement.ack
        assert (ack.status, ack.durability, ack.receipts) == (
            "committed",
            "ledger",
            (new_event.event_id,),
        )
        assert (ack.event_id, ack.payload_digest) == (new_event.event_id, new_event.payload_digest)
        assert observations[0]["event_id"] == new_event.event_id


@pytest.mark.parametrize(
    "case_kind", ["current", "foreign_tenant", "foreign_cell", "expired_lease"]
)
def test_native_budget_action_reopens_actual_control_lease(tmp_path, monkeypatch, case_kind):
    from datetime import timedelta

    from polisyos.runtime.http.services import control_plane_store as control_owner
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from tests.unit.runtime.http.test_control_plane_store_action_head_history import (
        _create_pending_action_job,
        _make_store,
    )

    store = _make_store(tmp_path)
    job = _create_pending_action_job(store)
    leased = store.lease_next_job(worker_id="native-budget-worker", lease_seconds=60)
    assert leased is not None
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    service = ControlPlaneService.__new__(ControlPlaneService)
    service._control_store = bridge.control_store = store
    service._artifact_store = bridge.artifact_store = object()
    service._diagnostic_event_log = bridge.event_log = object()
    service._acquisition_route_sink = bridge.action_head_sink = object()
    bridge._source_control_service = service
    closure = SimpleNamespace(
        run_id=job.run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        source_job_id="source-job",
        route_id="sha256:" + "a" * 64,
        native_derivation_leaf_scope=object(),
    )
    phase = SimpleNamespace(job_id=job.job_id)
    # Only source/phase semantic proofs are adapters here; the job lease,
    # immutable creation-envelope reconciliation and tenant/cell proof are real.
    monkeypatch.setattr(bridge, "selection", lambda _: object())
    monkeypatch.setattr(bridge, "_validate_action_phase", lambda *_: phase)
    monkeypatch.setattr(
        bridge,
        "_native_derivation_route_reader",
        lambda **_: SimpleNamespace(resolve_current_route=lambda **_: closure),
    )
    with store.job_execution_fence(
        job_id=job.job_id, worker_id=leased.lease_owner, attempt=leased.attempt
    ):
        if case_kind == "foreign_tenant":
            closure.tenant_id = "foreign-tenant"
        elif case_kind == "foreign_cell":
            closure.cell_id = "foreign-cell"
        elif case_kind == "expired_lease":
            expired = datetime.now(UTC) + timedelta(hours=1)
            monkeypatch.setattr(control_owner, "_utc_now", lambda: expired)
        if case_kind == "current":
            _, actual_phase, admission = bridge._current_native_reentry_action(
                closure=closure, action_phase_ref="sha256:" + "b" * 64
            )
            assert actual_phase is phase and admission.matches_job_record(leased)
        else:
            with pytest.raises(
                (AcquisitionRouteClosureError, control_owner.ControlJobLeaseLostError)
            ):
                bridge._current_native_reentry_action(
                    closure=closure, action_phase_ref="sha256:" + "b" * 64
                )


@pytest.mark.parametrize("profile_version", [1, 2])
def test_native_new_work_refuses_actual_legacy_profile_without_quota(monkeypatch, profile_version):
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV1,
        GenericCycleN5RequestProfileV2,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec

    fields = {"budget_ref": "legacy", "horizon": HorizonSpec(start=0, end=0, step=1)}
    if profile_version == 1:
        n5 = GenericCycleN5RequestProfileV1(**fields)
    else:
        n5 = GenericCycleN5RequestProfileV2(
            **fields,
            ncm_plan_refs=(
                ArtifactRef(
                    artifact_id="sha256:" + "a" * 64,
                    kind="ir.ncm_spec",
                    media_type="application/json",
                    manifest_profile_sha256="sha256:" + "b" * 64,
                ),
            ),
        )
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    # The new policy predicate receives an actual typed legacy request; source
    # financial provenance is an explicit adapter, not an authority claim.
    bridge._source_control_service = SimpleNamespace(
        read_original_run_budget_scope=lambda **_: SimpleNamespace(
            scope_explicit=True, run_budget_scope="metered_paid_producers_and_bounded_candidate"
        )
    )
    monkeypatch.setattr(bridge, "_native_derivation_budget_profile", lambda _: (n5, "original-key"))
    with pytest.raises(AcquisitionRouteClosureError) as caught:
        bridge._require_native_reentry_standard_capacity(object(), None)
    assert caught.value.code == "native_reentry_standard_quota_not_established"


@pytest.mark.parametrize(
    ("cut", "expected"),
    [
        ("none", ["quota", "gateway"]),
        ("prepared", ["quota"]),
        ("n5_completed", []),
        ("cycle_completed", []),
    ],
)
def test_native_readiness_uses_checkpoint_owner_not_gateway_or_available_capacity(
    monkeypatch, cut, expected
):
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.native_source_reentry_history import (
        NativeSourceReentryCoordinator,
        NativeSourceReentryProgress,
    )

    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    closure = object()
    coordinator = NativeSourceReentryCoordinator.__new__(NativeSourceReentryCoordinator)
    coordinator.bridge, coordinator.closure = bridge, closure
    pair = (object(), object())
    progress = NativeSourceReentryProgress(
        prepared=None if cut == "none" else pair,
        n5_completed=pair if cut in {"n5_completed", "cycle_completed"} else None,
        cycle_completed=pair if cut == "cycle_completed" else None,
    )
    calls = []
    # Selected checkpoint verification is the explicit boundary of this unit.
    # Production obtains it from this exact canonical coordinator; a caller
    # boolean or arbitrary progress-shaped object is never accepted instead.
    monkeypatch.setattr(coordinator, "progress", lambda: progress)
    monkeypatch.setattr(
        bridge, "_require_native_reentry_standard_capacity", lambda *_: calls.append("quota")
    )
    monkeypatch.setattr(
        bridge, "_require_native_reentry_n4_producer", lambda *_: calls.append("gateway")
    )
    bridge._native_derivation_reentry_readiness(
        closure=closure, observer=object(), coordinator=coordinator
    )
    assert calls == expected


def test_native_readiness_refuses_a_caller_supplied_completion_marker():
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge

    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    with pytest.raises(AcquisitionRouteClosureError) as caught:
        bridge._native_derivation_reentry_readiness(
            closure=object(),
            observer=object(),
            coordinator=SimpleNamespace(progress=lambda: SimpleNamespace(n5_completed=True)),
        )
    assert caught.value.code == "native_reentry_checkpoint_owner_mismatch"


@pytest.mark.parametrize(
    ("started", "model_configured", "error"),
    [
        (True, True, "acquisition_reentry_outcome_not_established"),
        (False, False, "acquisition_reentry_model_unconfigured"),
    ],
)
def test_native_readiness_uses_one_selected_cut_for_preparation_and_producer_gates(
    monkeypatch, started, model_configured, error
):
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.native_source_reentry_history import (
        NativeSourceReentryCoordinator,
        NativeSourceReentryProgress,
    )

    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    closure = object()
    coordinator = NativeSourceReentryCoordinator.__new__(NativeSourceReentryCoordinator)
    coordinator.bridge, coordinator.closure = bridge, closure
    calls = []

    def read_progress():
        calls.append("progress")
        return NativeSourceReentryProgress(prepared=None, n5_completed=None, cycle_completed=None)

    monkeypatch.setattr(coordinator, "progress", read_progress)
    monkeypatch.setattr(
        bridge, "_require_native_reentry_standard_capacity", lambda *_: calls.append("quota")
    )
    monkeypatch.setattr(
        bridge, "_require_native_reentry_n4_producer", lambda *_: calls.append("gateway")
    )
    with pytest.raises(ValueError, match=f"^{error}$"):
        bridge._native_derivation_reentry_readiness(
            closure=closure,
            observer=object(),
            coordinator=coordinator,
            started=started,
            model_configured=model_configured,
        )
    assert calls == ["progress"]


@pytest.mark.parametrize(
    ("mode", "configured", "models", "expected_code"),
    [
        (None, False, ["original-model"], "native_reentry_n4_producer_unconfigured"),
        ("0", False, ["original-model"], "native_reentry_n4_producer_unconfigured"),
        (" TRUE ", False, ["original-model"], None),
        (None, True, ["original-model"], None),
        ("1", True, [], "native_reentry_model_not_established"),
    ],
)
def test_native_new_n4_readiness_uses_the_public_factory_mode_owner(
    tmp_path,
    monkeypatch,
    mode,
    configured,
    models,
    expected_code,
):
    """Reopen real source JSON before configuration-only admission, with no I/O."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.scientist import GatewayLLMConfig

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    selected = store.put_json(
        {"llm_models": models},
        artifacts.ArtifactWriteOptions(
            kind="test.native.original_source_payload", media_type="application/json"
        ),
        return_selected_profile=True,
    )
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = store
    if mode is None:
        monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    else:
        monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", mode)
    lookups = []

    def config_from_env(cls):
        lookups.append(cls)
        return (
            GatewayLLMConfig(base_url="https://fixture.invalid/v1", api_key="fixture-key")
            if configured
            else None
        )

    monkeypatch.setattr(GatewayLLMConfig, "from_env", classmethod(config_from_env))
    closure = SimpleNamespace(source_payload_ref=selected)
    if expected_code is not None:
        with pytest.raises(AcquisitionRouteClosureError) as caught:
            bridge._require_native_reentry_n4_producer(closure)
        assert caught.value.code == expected_code
    else:
        bridge._require_native_reentry_n4_producer(closure)
    assert len(lookups) == (0 if mode in {" TRUE ", "1"} else 1)
    assert store.verify(selected).ok
