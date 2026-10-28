"""Exercise live NL producer ownership, bounded close, and actual begin receipts."""

from __future__ import annotations

import asyncio
import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.llm import LLMSettlementOwnershipError
from polisyos.fabric.connectors.resilience.circuit_breaker import CircuitBreaker
from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError
from polisyos.runtime.http.resilience import BlockingDependencyGuard
from polisyos.runtime.http.services.control.job_nl_context import _ControlNLJobContext
from polisyos.runtime.http.services.control.job_nl_execution import ControlNLJobExecutionMixin
from polisyos.runtime.http.services.control.nl_pipeline import NaturalLanguagePipelineRefusalError
from polisyos.runtime.http.services.control.producer_basis import _ControlJobProducerBasis
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand
from polisyos.scientist.orchestration.engine import BudgetLedgerProducerRunBinding
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    _gateway_cache_reuse_scope,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReusePrincipal,
    InMemoryPromptCache,
)


def _create_job(store: ControlPlaneStore, *, known: bool) -> Any:
    scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established" if known else "not_established",
        "tenant_id": "tenant-a" if known else None,
        "cell_id": "cell-a" if known else None,
        "actor_subject": "actor-a" if known else None,
        "actor_authenticated": known,
        "actor_roles": ["analyst"] if known else [],
    }
    payload = {
        "job_id": "job-a",
        "run_id": "run-a",
        "job_kind": "natural_language_run",
        "pipeline_id": None,
        "payload_ref": "sha256:fixture-payload",
        "submitted_by": "actor-a" if known else None,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {"candidate": True},
        "capability_manifest_ref": None,
        "execution_scope": scope,
    }
    return store.create_job(
        job_id="job-a",
        kind="natural_language_run",
        run_id="run-a",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref=None,
        payload_ref="sha256:fixture-payload",
        submitted_by="actor-a" if known else None,
        creation_event_payload=payload,
    )


def _binding() -> BudgetLedgerProducerRunBinding:
    return BudgetLedgerProducerRunBinding(
        run_id="run-a",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="dev",
        control_job_id="job-a",
    )


def test_legacy_unknown_scope_refuses_llm_work_with_a_scoped_resubmission_path(
    tmp_path: Path,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "unknown.sqlite3")
    _create_job(store, known=False)
    leased = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert leased is not None
    service = ControlNLJobExecutionMixin()
    service._control_store = store
    with store.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=leased.attempt):
        admission = store.current_execution_job_admission()
        assert admission.scope.status == "not_established"
        context = _ControlNLJobContext(
            job=admission.job,
            admission=admission,
            execution_scope=admission.scope,
            payload={"request": "candidate only"},
            capability_manifest_ref="",
            execution_intent_binding={},
            intent_band=ExecutionIntentBand.CANDIDATE_ONLY,
            evaluation_safety=None,
            execution_intent="candidate_only",
            execution_intent_limitation=None,
            model_name="simulated-qwen",
            compiler_context={},
            trusted_source_context={},
            profile_id=None,
        )
        # Candidate state remains unknown. It is not promoted to an invented
        # tenant owner solely to acquire the protected physical-work capability.
        service._persist_current_nl_owner_projection(context)
        with pytest.raises(NaturalLanguagePipelineRefusalError) as caught:
            service._compile_control_nl_job(context)
        assert caught.value.code == "nl_producer_ownership_not_established"
        assert "authenticated scoped route" in str(caught.value)
        assert "execution_owner_binding" not in store.get_job("job-a").progress


@pytest.mark.parametrize("exit_kind", ["normal", "error", "cancel"])
@pytest.mark.parametrize("stall_at", ["authorizer", "ledger_begin"])
def test_running_dependency_timeout_closes_without_holding_the_job_transaction(
    monkeypatch: Any,
    tmp_path: Path,
    exit_kind: str,
    stall_at: str,
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "job.sqlite3")
    _create_job(store, known=True)
    leased = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert leased is not None
    ledger = FileBudgetLedger(tmp_path / "ledger.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    entered, release, returned = threading.Event(), threading.Event(), threading.Event()
    closure: list[bool] = []

    class StalledOwner:
        def authorize_reuse(self, request: Any) -> CacheReuseDecision:
            if stall_at == "authorizer":
                entered.set()
            try:
                if stall_at == "authorizer":
                    assert release.wait(3)
                return CacheReuseDecision(
                    issuer="component-fixture",
                    epoch="epoch-a",
                    actor_id=request.actor_id,
                    tenant=request.tenant,
                    scope=request.scope,
                    purpose=request.purpose,
                    model=request.model,
                    parameters_digest=request.parameters_digest,
                    evidence=request.evidence,
                )
            finally:
                if stall_at == "authorizer":
                    returned.set()

    if stall_at == "ledger_begin":
        original_begin = ledger.begin_producer_event

        def paused_ledger_begin(*args: Any, **kwargs: Any) -> Any:
            # Middleware's actual monetary mutex is already held here. The
            # run/attempt have been captured before durable dependency I/O.
            entered.set()
            try:
                assert release.wait(3)
                return original_begin(*args, **kwargs)
            finally:
                returned.set()

        monkeypatch.setattr(ledger, "begin_producer_event", paused_ledger_begin)

    import hashlib

    content = b"immutable local fixture"
    context = {
        "tenant": "tenant-a",
        "scope": "tenant-a/cell-a",
        "purpose": "test",
        "snapshot": {
            "ref": "sha256:" + hashlib.sha256(content).hexdigest(),
            "version": "profile-a",
            "immutable": True,
            "content": content,
            "content_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
        },
    }
    guard = BlockingDependencyGuard(
        dependency_name="control_plane_store",
        timeout_seconds=0.1,
        breaker=CircuitBreaker("c05-timeout"),
        executor_max_workers=2,
    )
    try:
        with (
            ThreadPoolExecutor(max_workers=2) as requests,
            store.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=leased.attempt),
        ):
            admission = store.current_execution_job_admission()
            try:
                with (
                    middleware.producer_run_binding_scope(_binding(), control_job_attempt=1),
                    _gateway_cache_reuse_scope(
                        authorizer=StalledOwner(),
                        principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
                        context=context,
                        cache=InMemoryPromptCache(),
                        run_id="run-a",
                        settlement_store=middleware,
                        reuse_guard=guard.run,
                        validate_admission=lambda: guard.run(
                            store.verify_llm_producer_admission, expected=admission
                        ),
                        on_close=closure.append,
                    ),
                ):
                    client = create_traced_gateway_client(
                        model_name="simulated-qwen",
                        config=GatewayLLMConfig(
                            base_url="http://fixture.invalid", api_key="fixture"
                        ),
                    )
                    assert client is not None
                    copied = contextvars.copy_context()
                    producing = requests.submit(
                        copied.run,
                        lambda: asyncio.run(client.generate(user="same", temperature=0)),
                    )
                    assert entered.wait(3)
                    # This real concurrent write would block behind the
                    # former SQL transaction surrounding the callback.
                    updating = requests.submit(
                        store.update_progress_state,
                        job_id="job-a",
                        state="running",
                        progress={"phase": "concurrent"},
                        expected_lease_owner="worker-a",
                        expected_attempt=leased.attempt,
                    )
                    updating.result(timeout=1)
                    with pytest.raises(RuntimeDependencyTimeoutError):
                        producing.result(timeout=2)
                    if exit_kind == "error":
                        raise RuntimeError("scope exit")
                    if exit_kind == "cancel":
                        raise asyncio.CancelledError()
            except (RuntimeError, asyncio.CancelledError):
                assert exit_kind != "normal"
            # Actual timed-out callback is still blocked; all closes returned.
            assert not returned.is_set()
            assert closure == [False]
            assert store.current_execution_job_record().progress["phase"] == "concurrent"
            with pytest.raises(LLMSettlementOwnershipError, match="scope_closed"):
                asyncio.run(client.generate(user="same", temperature=0))
            assert not client.unwrap().calls
            # The fixture stalls before acquiring the file's own lock.
            assert not FileBudgetLedger(tmp_path / "ledger.json").snapshot().producer_settlements
    finally:
        release.set()
        assert returned.wait(3)
        guard.close()
    snapshot = FileBudgetLedger(tmp_path / "ledger.json").snapshot()
    if stall_at == "ledger_begin":
        rows = tuple(snapshot.producer_settlements.values())
        assert len(rows) == 1 and rows[0].status == "pending"
        assert rows[0].run_binding == _binding() and rows[0].control_job_attempt == 1
    else:
        assert not snapshot.producer_settlements
    assert not client.unwrap().calls


@pytest.mark.asyncio
async def test_actual_begin_receipt_with_lost_attempt_is_refused_before_dispatch(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "job.sqlite3")
    _create_job(store, known=True)
    leased = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert leased is not None
    ledger_path = tmp_path / "actual-begin.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    actual_begin = middleware.begin_producer_event_safe

    def lose_attempt(*args: Any, **kwargs: Any) -> Any:
        token = middleware._producer_attempt_scope.set(None)
        try:
            return actual_begin(*args, **kwargs)
        finally:
            middleware._producer_attempt_scope.reset(token)

    monkeypatch.setattr(middleware, "begin_producer_event_safe", lose_attempt)
    persisted: list[Any] = []
    basis = _ControlJobProducerBasis(
        run_binding=_binding(),
        attempt=1,
        persist=persisted.append,
        readback=middleware.resolve_producer_event_safe,
    )
    with store.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=leased.attempt):
        admission = store.current_execution_job_admission()
        with (
            middleware.producer_run_binding_scope(_binding(), control_job_attempt=1),
            _gateway_cache_reuse_scope(
                authorizer=None,
                principal=None,
                context=None,
                cache=None,
                run_id="run-a",
                settlement_store=middleware,
                reuse_guard=lambda operation: operation(),
                validate_admission=lambda: store.verify_llm_producer_admission(expected=admission),
                intent_observer=basis.observe,
                on_close=basis.close_admission,
            ),
        ):
            client = create_traced_gateway_client(
                model_name="simulated-qwen",
                config=GatewayLLMConfig(
                    base_url="http://fixture.invalid", api_key="fixture", cache_maxsize=0
                ),
            )
            assert client is not None
            with pytest.raises(ValueError, match="producer_basis_actual_begin_not_established"):
                await client.generate(user="same", temperature=0)
            assert store.verify_llm_producer_admission(expected=admission).attempt == 1
            assert not client.unwrap().calls
    rows = FileBudgetLedger(ledger_path).list_producer_events_for_run(_binding())
    assert len(rows) == 1 and rows[0].status == "pending"
    assert rows[0].run_binding == _binding() and rows[0].control_job_attempt is None
    assert not persisted and basis.closed_snapshot() == (False, ())
