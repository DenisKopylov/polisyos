"""Actual traced LLM begin/settlement under the Native budget composition.

The source admission and current-phase resolver are explicit scripted boundaries.
The ledger, action-window selector, observer, traced client, begin/readback and
settlement are real. These controls do not establish a real Native source,
protected action grant, N4 run, provider invoice, or numerical simulation.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.scientist.orchestration.engine import (
    BudgetExhaustedError,
    BudgetState,
    ProducerBudgetObserver,
)
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
    service = ControlPlaneService.__new__(ControlPlaneService)
    service._llm_producer_settlement_store = case.service._llm_producer_settlement_store
    service._control_store = SimpleNamespace(
        get_job=lambda _: SimpleNamespace(state="completed", attempt=7)
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


@pytest.mark.parametrize(
    "case_kind", ["current", "foreign_tenant", "foreign_cell", "expired_lease"]
)
def test_native_budget_action_reopens_actual_control_lease(tmp_path, monkeypatch, case_kind):
    from datetime import UTC, datetime, timedelta

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
        lambda _: SimpleNamespace(resolve_current_route=lambda **_: closure),
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
