"""Durable physical-call admission for Scientist backtest Foundry replicas.

One unit is durably reserved before a newly admitted delegate call. An interrupted
reserved operation remains consumed and unresolved; this owner does not estimate
or claim monetary price. A result-cache hit that bypasses the Foundry port does
not enter this owner and consumes no new physical-call unit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from polisyos.core.artifacts import ArtifactTenantContextInfo
from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.core.contracts import ExecPlanRef, ExecuteRequest, ExecuteResult
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerBacktestInvocationProfileV2,
    BudgetLedgerBacktestInvocationReservationV2,
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.orchestration.engine.context import FoundryPort


class BacktestFoundryInvocationScopeV1(BaseModel):
    """Exact backtest, replica and logical horizon-step identity for one call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scientist.backtest_foundry_invocation_scope.v1"] = (
        "scientist.backtest_foundry_invocation_scope.v1"
    )
    backtest_run_id: str = Field(min_length=1)
    replica_run_id: str = Field(min_length=1)
    replica_index: StrictInt = Field(ge=1)
    replica_seed: StrictInt
    horizon_step_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_identity(self) -> BacktestFoundryInvocationScopeV1:
        values = (self.backtest_run_id, self.replica_run_id, self.horizon_step_id)
        if any(not value.strip() or value != value.strip() for value in values):
            raise ValueError("backtest_foundry_invocation_scope_not_established")
        if self.backtest_run_id == self.replica_run_id:
            raise ValueError("backtest_foundry_replica_run_identity_conflict")
        return self


class BacktestFoundryInvocationReplayRefused(RuntimeError):
    """A previously reserved operation cannot issue another physical call."""

    def __init__(self, reservation: BudgetLedgerBacktestInvocationReservationV2) -> None:
        self.reservation = reservation
        super().__init__(
            "backtest_foundry_invocation_replay_not_reexecuted:"
            f"{reservation.status}:{reservation.operation_id}"
        )


@dataclass(slots=True)
class BacktestFoundryDispatchState:
    """Report whether one invocation crossed into the configured Foundry port."""

    entered: bool = False


@dataclass(frozen=True, slots=True)
class BacktestFoundryInvocationBudget:
    """Bind a configured physical-call profile to its existing durable ledger owner."""

    ledger: FileBudgetLedger
    profile: BudgetLedgerBacktestInvocationProfileV2

    def __post_init__(self) -> None:
        if type(self.ledger) is not FileBudgetLedger:
            raise TypeError("backtest_foundry_budget_ledger_untyped")
        if type(self.profile) is not BudgetLedgerBacktestInvocationProfileV2:
            raise TypeError("backtest_foundry_invocation_profile_untyped")
        self.validate_current()

    def validate_current(self) -> None:
        """Require the exact owner-selected profile to remain current in this ledger."""
        snapshot = self.ledger.snapshot()
        selected = snapshot.invocation_profiles.get(self.profile.run_binding.run_id)
        if type(selected) is not BudgetLedgerBacktestInvocationProfileV2 or selected != self.profile:
            raise ValueError("backtest_foundry_invocation_profile_not_current")


def build_backtest_foundry_invocation_identity(
    *,
    profile: BudgetLedgerBacktestInvocationProfileV2,
    scope: BacktestFoundryInvocationScopeV1,
    request: ExecuteRequest,
    derived_tenant_context: ArtifactTenantContextInfo | None = None,
) -> tuple[str, str]:
    """Build stable ledger identities from the exact run, step and request.

    The operation ID denotes the logical physical-call slot and remains stable
    across retries of that slot. The separate request digest binds the actual
    request bytes; changing the request under an existing slot is a conflict.
    """
    if type(profile) is not BudgetLedgerBacktestInvocationProfileV2:
        raise TypeError("backtest_foundry_invocation_profile_untyped")
    if type(scope) is not BacktestFoundryInvocationScopeV1:
        raise TypeError("backtest_foundry_invocation_scope_untyped")
    if type(request) is not ExecuteRequest:
        raise TypeError("backtest_foundry_execute_request_untyped")
    if (
        derived_tenant_context is not None
        and type(derived_tenant_context) is not ArtifactTenantContextInfo
    ):
        raise TypeError("backtest_foundry_tenant_context_untyped")
    binding = profile.run_binding
    if type(binding) is not BudgetLedgerProducerRunBinding:
        raise TypeError("backtest_foundry_run_binding_untyped")
    if scope.backtest_run_id != binding.run_id:
        raise ValueError("backtest_foundry_invocation_run_scope_mismatch")
    if request.exec_config.seed != scope.replica_seed:
        raise ValueError("backtest_foundry_invocation_seed_scope_mismatch")
    if derived_tenant_context is not None and (
        derived_tenant_context.tenant_id != binding.tenant_id
        or derived_tenant_context.cell_id != binding.cell_id
    ):
        raise ValueError("backtest_foundry_invocation_tenant_scope_mismatch")

    operation_identity = {
        "algorithm": "polisyos.backtest_foundry_invocation_slot.v1",
        "work_unit": profile.work_unit,
        "profile_digest": profile.profile_digest,
        "run_binding": binding.model_dump(mode="json"),
        "backtest_run_id": scope.backtest_run_id,
        "replica_run_id": scope.replica_run_id,
        "replica_index": scope.replica_index,
        "replica_seed": scope.replica_seed,
        "horizon_step_id": scope.horizon_step_id,
    }
    operation_id = content_hash(
        to_canonical_bytes(operation_identity, CanonSpec(forbid_floats=False))
    )
    request_identity = {
        "algorithm": "polisyos.backtest_foundry_execute_request.v1",
        "operation_id": operation_id,
        "request": request.model_dump(mode="json", round_trip=True),
        "request_fields_set": sorted(request.model_fields_set),
        "exec_config_fields_set": sorted(request.exec_config.model_fields_set),
        "derived_tenant_context": (
            None
            if derived_tenant_context is None
            else derived_tenant_context.model_dump(mode="json", round_trip=True)
        ),
    }
    request_digest = content_hash(
        to_canonical_bytes(request_identity, CanonSpec(forbid_floats=False))
    )
    return operation_id, request_digest


def build_backtest_foundry_horizon_step_id(
    *, state_step: int, exec_plan_ref: ExecPlanRef
) -> str:
    """Bind a sequential Foundry call slot to its selected state step and plan.

    The state step is stable across retries of one Native horizon position and
    advances when Native replay persists the next state. The exact plan ref
    separates distinct selected model plans that share the same state step.
    The full ExecuteRequest remains in the reservation digest so changed input
    bindings or other request fields at this slot fail closed as identity drift.
    """
    if type(state_step) is not int or state_step < 0:
        raise ValueError("backtest_foundry_state_step_not_established")
    if type(exec_plan_ref) is not ExecPlanRef:
        raise TypeError("backtest_foundry_exec_plan_ref_untyped")
    identity = {
        "algorithm": "polisyos.backtest_foundry_horizon_step.v1",
        "state_step": state_step,
        "exec_plan_ref": exec_plan_ref.model_dump(mode="json", round_trip=True),
    }
    digest = content_hash(to_canonical_bytes(identity, CanonSpec(forbid_floats=False)))
    return f"foundry_execute:{state_step}:{digest}"


def execute_backtest_foundry_once(
    *,
    ledger: FileBudgetLedger,
    profile: BudgetLedgerBacktestInvocationProfileV2,
    scope: BacktestFoundryInvocationScopeV1,
    delegate: FoundryPort,
    store: ArtifactStore,
    request: ExecuteRequest,
    derived_tenant_context: ArtifactTenantContextInfo,
    dispatch_state: BacktestFoundryDispatchState,
) -> ExecuteResult:
    """Reserve one unit and then enter the configured Foundry delegate exactly once.

    A previously reserved operation is never re-dispatched. If the delegate
    raises, its physical outcome is conservatively retained as ``unknown``. A
    process interruption after reservation may leave it ``reserved``; either
    state consumes the unit and blocks later calls in the run. The in-process
    ``dispatch_state.entered`` witness becomes true immediately before entering
    the physical Foundry port. Admission denial and replay leave it false.
    """
    if type(ledger) is not FileBudgetLedger:
        raise TypeError("backtest_foundry_budget_ledger_untyped")
    if type(derived_tenant_context) is not ArtifactTenantContextInfo:
        raise TypeError("backtest_foundry_tenant_context_not_established")
    if type(dispatch_state) is not BacktestFoundryDispatchState:
        raise TypeError("backtest_foundry_dispatch_state_untyped")
    if dispatch_state.entered:
        raise ValueError("backtest_foundry_dispatch_state_already_used")
    execute = delegate.execute
    operation_id, request_digest = build_backtest_foundry_invocation_identity(
        profile=profile,
        scope=scope,
        request=request,
        derived_tenant_context=derived_tenant_context,
    )
    reservation, created = ledger.reserve_backtest_invocation(
        operation_id, request_digest, profile=profile
    )
    if not created:
        raise BacktestFoundryInvocationReplayRefused(reservation)

    try:
        dispatch_state.entered = True
        result = execute(store, request, derived_tenant_context=derived_tenant_context)
    except Exception:
        ledger.finish_backtest_invocation(
            operation_id,
            request_digest,
            profile=profile,
            outcome="unknown",
        )
        raise

    if type(result) is not ExecuteResult:
        ledger.finish_backtest_invocation(
            operation_id,
            request_digest,
            profile=profile,
            outcome="unknown",
        )
        raise TypeError("backtest_foundry_execute_result_untyped")

    outcome: Literal["completed", "failed"] = (
        "completed" if result.ok and result.simulation_result_ref is not None else "failed"
    )
    ledger.finish_backtest_invocation(
        operation_id,
        request_digest,
        profile=profile,
        outcome=outcome,
    )
    return result
