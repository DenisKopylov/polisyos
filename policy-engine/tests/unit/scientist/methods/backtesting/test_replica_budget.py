"""Stable identities for durable Native backtest physical-call accounting."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from polisyos.core.artifacts import ArtifactTenantContextInfo
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts import (
    ExecPlanRef,
    ExecuteRequest,
    ExecuteResult,
    FoundryExecConfig,
    FoundryInputBindingsRef,
    SimulationResultRef,
)
from polisyos.scientist.methods.backtesting.replica_budget import (
    BacktestFoundryDispatchState,
    BacktestFoundryInvocationBudget,
    BacktestFoundryInvocationReplayRefused,
    BacktestFoundryInvocationScopeV1,
    build_backtest_foundry_horizon_step_id,
    build_backtest_foundry_invocation_identity,
    execute_backtest_foundry_once,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetBacktestInvocationQuotaV2,
    BudgetLedgerBacktestInvocationProfileV2,
    BudgetLedgerBacktestInvocationQuotaExhaustedError,
    BudgetLedgerBacktestInvocationUnresolvedError,
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)


def _profile(*, total: int = 2) -> BudgetLedgerBacktestInvocationProfileV2:
    binding = BudgetLedgerProducerRunBinding(
        run_id="backtest-run-1",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="profile-a",
        control_job_id="control-job-1",
    )
    policy = BudgetBacktestInvocationQuotaV2(allocation_id="allocation-1", total_units=total)
    return BudgetLedgerBacktestInvocationProfileV2.from_policy(binding, policy)


def _request(*, notes: list[str] | None = None, seed: int = 12) -> ExecuteRequest:
    artifact_id = ArtifactID(f"sha256:{'a' * 64}")
    profile = f"sha256:{'b' * 64}"
    return ExecuteRequest(
        exec_plan_ref=ExecPlanRef(
            artifact_id=artifact_id,
            manifest_profile_sha256=profile,
        ),
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=artifact_id,
            manifest_profile_sha256=profile,
        ),
        exec_config=FoundryExecConfig(seed=seed),
        notes=[] if notes is None else notes,
    )


def _scope(
    *, backtest_run_id: str = "backtest-run-1", horizon_step_id: str = "t2"
) -> BacktestFoundryInvocationScopeV1:
    return BacktestFoundryInvocationScopeV1(
        backtest_run_id=backtest_run_id,
        replica_run_id="backtest-run-1-replica-1",
        replica_index=1,
        replica_seed=12,
        horizon_step_id=horizon_step_id,
    )


class _CountingFoundryPort:
    def __init__(
        self, *, result: ExecuteResult | None = None, error: Exception | None = None
    ) -> None:
        self.calls = 0
        self.result = result
        self.error = error

    def execute(
        self,
        store: object,
        request: ExecuteRequest,
        *,
        derived_tenant_context: ArtifactTenantContextInfo | None = None,
    ) -> ExecuteResult:
        del store, request, derived_tenant_context
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("test port requires a result or error")
        return self.result


def test_invocation_identity_replays_same_slot_and_binds_changed_request() -> None:
    profile = _profile()
    context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    operation, request_digest = build_backtest_foundry_invocation_identity(
        profile=profile,
        scope=_scope(),
        request=_request(),
        derived_tenant_context=context,
    )
    replay_operation, replay_digest = build_backtest_foundry_invocation_identity(
        profile=profile,
        scope=_scope(),
        request=_request(),
        derived_tenant_context=context,
    )
    assert (replay_operation, replay_digest) == (operation, request_digest)

    changed_operation, changed_digest = build_backtest_foundry_invocation_identity(
        profile=profile,
        scope=_scope(),
        request=_request(notes=["changed input request"]),
        derived_tenant_context=context,
    )
    assert changed_operation == operation
    assert changed_digest != request_digest

    next_step_operation, _ = build_backtest_foundry_invocation_identity(
        profile=profile,
        scope=_scope(horizon_step_id="t3"),
        request=_request(),
        derived_tenant_context=context,
    )
    assert next_step_operation != operation


def test_invocation_identity_requires_the_bound_run_seed_and_tenant_scope() -> None:
    profile = _profile()
    with pytest.raises(ValueError, match="run_scope_mismatch"):
        build_backtest_foundry_invocation_identity(
            profile=profile,
            scope=_scope(backtest_run_id="foreign-backtest-run"),
            request=_request(),
        )

    with pytest.raises(ValueError, match="seed_scope_mismatch"):
        build_backtest_foundry_invocation_identity(
            profile=profile,
            scope=_scope(),
            request=_request(seed=13),
        )

    with pytest.raises(ValueError, match="tenant_scope_mismatch"):
        build_backtest_foundry_invocation_identity(
            profile=profile,
            scope=_scope(),
            request=_request(),
            derived_tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-foreign", cell_id="cell-a"
            ),
        )


def test_foundry_call_is_reserved_once_and_completed_replay_does_not_dispatch(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(ledger_path)
    ledger.load_or_bootstrap(BudgetState())
    profile = _profile()
    ledger.configure_backtest_invocation_profile(profile)
    expected_result = ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(artifact_id=ArtifactID(f"sha256:{'c' * 64}")),
    )
    delegate = _CountingFoundryPort(result=expected_result)
    tenant_context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    dispatch_state = BacktestFoundryDispatchState()

    result = execute_backtest_foundry_once(
        ledger=ledger,
        profile=profile,
        scope=_scope(),
        delegate=delegate,
        store=object(),
        request=_request(),
        derived_tenant_context=tenant_context,
        dispatch_state=dispatch_state,
    )
    assert result == expected_result
    assert delegate.calls == 1
    assert dispatch_state.entered is True

    replay_state = BacktestFoundryDispatchState()

    with pytest.raises(BacktestFoundryInvocationReplayRefused) as replay:
        execute_backtest_foundry_once(
            ledger=FileBudgetLedger(ledger_path),
            profile=profile,
            scope=_scope(),
            delegate=delegate,
            store=object(),
            request=_request(),
            derived_tenant_context=tenant_context,
            dispatch_state=replay_state,
        )
    assert replay.value.reservation.status == "completed"
    assert delegate.calls == 1
    assert replay_state.entered is False


def test_quota_refusal_happens_before_dispatch_start_is_observed(tmp_path: Path) -> None:
    ledger = FileBudgetLedger(tmp_path / "budget.json")
    ledger.load_or_bootstrap(BudgetState())
    profile = _profile(total=1)
    ledger.configure_backtest_invocation_profile(profile)
    budget = BacktestFoundryInvocationBudget(ledger=ledger, profile=profile)
    delegate = _CountingFoundryPort(
        result=ExecuteResult(
            ok=True,
            simulation_result_ref=SimulationResultRef(
                artifact_id=ArtifactID(f"sha256:{'c' * 64}")
            ),
        )
    )
    tenant_context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")

    budget.validate_current()
    execute_backtest_foundry_once(
        ledger=budget.ledger,
        profile=budget.profile,
        scope=_scope(),
        delegate=delegate,
        store=object(),
        request=_request(),
        derived_tenant_context=tenant_context,
        dispatch_state=BacktestFoundryDispatchState(),
    )
    denied_state = BacktestFoundryDispatchState()
    with pytest.raises(BudgetLedgerBacktestInvocationQuotaExhaustedError):
        execute_backtest_foundry_once(
            ledger=budget.ledger,
            profile=budget.profile,
            scope=_scope(horizon_step_id="t3"),
            delegate=delegate,
            store=object(),
            request=_request(),
            derived_tenant_context=tenant_context,
            dispatch_state=denied_state,
        )

    assert delegate.calls == 1
    assert denied_state.entered is False


def test_horizon_step_slots_are_stable_and_count_each_real_replica_step(
    tmp_path: Path,
) -> None:
    ledger = FileBudgetLedger(tmp_path / "budget.json")
    ledger.load_or_bootstrap(BudgetState())
    profile = _profile(total=2)
    ledger.configure_backtest_invocation_profile(profile)
    tenant_context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    request = _request()
    first_step = _scope(
        horizon_step_id=build_backtest_foundry_horizon_step_id(
            state_step=2, exec_plan_ref=request.exec_plan_ref
        )
    )
    second_step = _scope(
        horizon_step_id=build_backtest_foundry_horizon_step_id(
            state_step=3, exec_plan_ref=request.exec_plan_ref
        )
    )
    delegate = _CountingFoundryPort(
        result=ExecuteResult(
            ok=True,
            simulation_result_ref=SimulationResultRef(
                artifact_id=ArtifactID(f"sha256:{'c' * 64}")
            ),
        )
    )

    for scope in (first_step, second_step):
        execute_backtest_foundry_once(
            ledger=ledger,
            profile=profile,
            scope=scope,
            delegate=delegate,
            store=object(),
            request=request,
            derived_tenant_context=tenant_context,
            dispatch_state=BacktestFoundryDispatchState(),
        )

    with pytest.raises(BacktestFoundryInvocationReplayRefused):
        execute_backtest_foundry_once(
            ledger=ledger,
            profile=profile,
            scope=first_step,
            delegate=delegate,
            store=object(),
            request=request,
            derived_tenant_context=tenant_context,
            dispatch_state=BacktestFoundryDispatchState(),
        )
    with pytest.raises(ValueError, match="identity_conflict"):
        execute_backtest_foundry_once(
            ledger=ledger,
            profile=profile,
            scope=first_step,
            delegate=delegate,
            store=object(),
            request=_request(notes=["changed payload for same horizon step"]),
            derived_tenant_context=tenant_context,
            dispatch_state=BacktestFoundryDispatchState(),
        )

    reservations = ledger.snapshot().invocation_reservations
    assert len(reservations) == 2
    assert delegate.calls == 2


def test_same_horizon_step_is_reserved_once_across_ledger_instances(tmp_path: Path) -> None:
    ledger_path = tmp_path / "shared-budget.json"
    first_ledger = FileBudgetLedger(ledger_path)
    first_ledger.load_or_bootstrap(BudgetState())
    profile = _profile(total=2)
    first_ledger.configure_backtest_invocation_profile(profile)
    second_ledger = FileBudgetLedger(ledger_path)
    tenant_context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    entered = Event()
    finish = Event()

    class _HoldingFoundryPort(_CountingFoundryPort):
        def execute(
            self,
            store: object,
            request: ExecuteRequest,
            *,
            derived_tenant_context: ArtifactTenantContextInfo | None = None,
        ) -> ExecuteResult:
            del store, request, derived_tenant_context
            self.calls += 1
            entered.set()
            if not finish.wait(timeout=5):
                raise TimeoutError("controlled Foundry dispatch was not released")
            assert self.result is not None
            return self.result

    result = ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(
            artifact_id=ArtifactID(f"sha256:{'c' * 64}")
        ),
    )
    first_delegate = _HoldingFoundryPort(result=result)
    second_delegate = _CountingFoundryPort(result=result)
    scope = _scope()
    request = _request()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            execute_backtest_foundry_once,
            ledger=first_ledger,
            profile=profile,
            scope=scope,
            delegate=first_delegate,
            store=object(),
            request=request,
            derived_tenant_context=tenant_context,
            dispatch_state=BacktestFoundryDispatchState(),
        )
        assert entered.wait(timeout=5)
        with pytest.raises(BacktestFoundryInvocationReplayRefused) as replay:
            execute_backtest_foundry_once(
                ledger=second_ledger,
                profile=profile,
                scope=scope,
                delegate=second_delegate,
                store=object(),
                request=request,
                derived_tenant_context=tenant_context,
                dispatch_state=BacktestFoundryDispatchState(),
            )
        assert replay.value.reservation.status == "reserved"
        assert second_delegate.calls == 0
        finish.set()
        assert first.result(timeout=5) == result

    assert first_delegate.calls == 1
    reservations = FileBudgetLedger(ledger_path).snapshot().invocation_reservations
    assert len(reservations) == 1
    assert next(iter(reservations.values())).status == "completed"


def test_missing_or_foreign_tenant_context_refuses_before_reservation(tmp_path: Path) -> None:
    ledger = FileBudgetLedger(tmp_path / "budget.json")
    ledger.load_or_bootstrap(BudgetState())
    profile = _profile()
    ledger.configure_backtest_invocation_profile(profile)
    delegate = _CountingFoundryPort(result=ExecuteResult(ok=True))
    original_snapshot = ledger.snapshot()

    for tenant_context, error in (
        (None, "backtest_foundry_tenant_context_not_established"),
        (
            ArtifactTenantContextInfo(tenant_id="foreign-tenant", cell_id="cell-a"),
            "tenant_scope_mismatch",
        ),
    ):
        with pytest.raises((TypeError, ValueError), match=error):
            execute_backtest_foundry_once(
                ledger=ledger,
                profile=profile,
                scope=_scope(),
                delegate=delegate,
                store=object(),
                request=_request(),
                derived_tenant_context=tenant_context,  # type: ignore[arg-type]
                dispatch_state=BacktestFoundryDispatchState(),
            )
        assert ledger.snapshot() == original_snapshot

    assert delegate.calls == 0


def test_unknown_foundry_outcome_stays_reserved_and_blocks_the_next_step(
    tmp_path: Path,
) -> None:
    ledger = FileBudgetLedger(tmp_path / "budget.json")
    ledger.load_or_bootstrap(BudgetState())
    profile = _profile()
    ledger.configure_backtest_invocation_profile(profile)
    delegate = _CountingFoundryPort(error=OSError("lost response"))
    tenant_context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    dispatch_state = BacktestFoundryDispatchState()

    with pytest.raises(OSError, match="lost response"):
        execute_backtest_foundry_once(
            ledger=ledger,
            profile=profile,
            scope=_scope(),
            delegate=delegate,
            store=object(),
            request=_request(),
            derived_tenant_context=tenant_context,
            dispatch_state=dispatch_state,
        )
    assert delegate.calls == 1
    assert dispatch_state.entered is True

    operation_id, _ = build_backtest_foundry_invocation_identity(
        profile=profile, scope=_scope(), request=_request()
    )
    reservation = ledger.resolve_backtest_invocation(operation_id, profile=profile)
    assert reservation is not None and reservation.status == "unknown"
    with pytest.raises(BacktestFoundryInvocationReplayRefused):
        execute_backtest_foundry_once(
            ledger=ledger,
            profile=profile,
            scope=_scope(),
            delegate=delegate,
            store=object(),
            request=_request(),
            derived_tenant_context=tenant_context,
            dispatch_state=BacktestFoundryDispatchState(),
        )
    with pytest.raises(BudgetLedgerBacktestInvocationUnresolvedError):
        execute_backtest_foundry_once(
            ledger=ledger,
            profile=profile,
            scope=_scope(horizon_step_id="t3"),
            delegate=delegate,
            store=object(),
            request=_request(),
            derived_tenant_context=tenant_context,
            dispatch_state=BacktestFoundryDispatchState(),
        )
    assert delegate.calls == 1
