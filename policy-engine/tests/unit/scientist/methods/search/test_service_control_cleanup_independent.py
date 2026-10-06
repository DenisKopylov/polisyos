"""Independent public batch controls with paid custody and checkpoint failures."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.methods.search.service import NativeSearchService
from polisyos.scientist.methods.search.stopping import (
    CompositeStoppingCriterion,
    CostBudgetStopping,
    MaxIterations,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer

pytestmark = pytest.mark.integration


def _stage_a(candidate: dict[str, Any], context: dict[str, Any]) -> tuple[float, bool]:
    return 0.0, True


def _stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {"simulation_results": {"budget_deficit": candidate["cost"]}}


class _PaidTransport:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return {
            "content": "acknowledged local transport response",
            "provider": "independent-batch-provider",
            "request_id": "independent-batch-paid-request",
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 2.375},
        }


def _paid_owner(path: Path) -> tuple[BudgetMiddleware, _PaidTransport, Any]:
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("100"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))
    transport = _PaidTransport()
    caller = LLMBudgetEnforcer(
        client=transport,
        budget_state=state,
        budget_middleware=owner,
        budget_keys=["run"],
        run_id="independent-batch-control",
        model_name="local-fixture-model",
    )
    caller.invoke(
        "one supported producer call",
        _evaluation_id="independent-paid-evaluation",
        _prompt_tokens_estimate=2,
        max_tokens=1,
    )
    snapshot = FileBudgetLedger(path).snapshot()
    assert transport.calls == 1
    assert snapshot.state.spent == {"run": Decimal("2.375")}
    assert snapshot.state.provider_spent == {"independent-batch-provider": Decimal("2.375")}
    assert snapshot.state.reserved == {"run": Decimal("0")}
    assert len(snapshot.spend_receipts) == 1
    receipt = next(iter(snapshot.spend_receipts.values()))
    assert receipt.amount == Decimal("2.375")
    assert receipt.provider == "independent-batch-provider"
    return owner, transport, snapshot


class _BatchSupplier:
    def __init__(self, cause: BaseException) -> None:
        self.cursor = 0
        self.cause = cause
        self.before_refusal: Callable[[], None] | None = None
        self.rollback_refusal: BaseException | None = None
        self.service: NativeSearchService | None = None
        self.acknowledged_ref: Any = None
        self.acknowledged_bytes: bytes | None = None

    def generate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("This control requires the existing batch generator port")

    def generate_batch(
        self,
        history: list[Any],
        current_best: Any,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        assert batch_size > 1
        assert len(history) == 1
        self.cursor += 1
        if self.cursor == 1:
            return []
        assert self.service is not None
        self.acknowledged_ref = self.service.checkpoint_ref
        self.acknowledged_bytes = self.service._store.get_bytes(self.acknowledged_ref)
        if self.before_refusal is not None:
            self.before_refusal()
        raise self.cause

    def get_state(self) -> dict[str, Any]:
        return {"profile": "independent-empty-batch.v1", "cursor": self.cursor}

    def set_state(self, state: dict[str, Any]) -> None:
        if self.rollback_refusal is not None:
            raise self.rollback_refusal
        if (
            state.get("profile") != "independent-empty-batch.v1"
            or type(state.get("cursor")) is not int
        ):
            raise ValueError("independent batch checkpoint refused")
        self.cursor = state["cursor"]


class _PublicationFaultStore(FileSystemCAS):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.failure_phase: str | None = None
        self.failure_write_attempts = 0
        self.unacknowledged_ref: Any = None
        self.refused_readbacks = 0

    def put_json(self, obj: Any, opts: Any, **kwargs: Any) -> Any:
        if self.failure_phase is not None:
            self.failure_write_attempts += 1
            if self.failure_phase == "put":
                raise OSError("independent failure checkpoint put refused")
        ref = super().put_json(obj, opts, **kwargs)
        if self.failure_phase == "readback":
            self.unacknowledged_ref = ref
        return ref

    def get_verified_snapshot(self, ref: Any) -> Any:
        if self.failure_phase == "readback" and ref == self.unacknowledged_ref:
            self.refused_readbacks += 1
            raise OSError("independent post-put verification read refused")
        return super().get_verified_snapshot(ref)


def _service(
    store: FileSystemCAS, owner: BudgetMiddleware, cause: BaseException
) -> tuple[NativeSearchService, _BatchSupplier]:
    supplier = _BatchSupplier(cause)
    controller = SearchController(
        SearchConfig(
            objective=CompositeObjective([BudgetDeficitObjective()]),
            stopping=CompositeStoppingCriterion([MaxIterations(2), CostBudgetStopping(100)]),
            enable_stage_a=False,
            batch_size=2,
            max_empty_generation_attempts=2,
            budget_middleware=owner,
        ),
        supplier,
        _stage_a,
        _stage_b,
    )
    service = NativeSearchService(controller, store=store)
    supplier.service = service
    return service, supplier


def _partial(service: NativeSearchService) -> dict[str, Any]:
    state = service.controller._run_state
    return {
        "history": deepcopy(state.history),
        "evaluations": state.evaluation_iterations,
        "stage_b": state.stage_b_evaluations,
        "paid": state.budget_spent,
        "budget_snapshot": deepcopy(state.budget_snapshot),
        "budget_source": state.budget_snapshot_source,
        "budget_evidence": deepcopy(state.budget_evidence),
        "ledger_id": state.budget_ledger_id,
        "ledger_revision": state.budget_ledger_revision,
        "pending": deepcopy(service._pending_candidates),
        "completed": set(service._completed_candidate_ids),
    }


def _assert_old_ack_and_paid_custody(
    service: NativeSearchService,
    supplier: _BatchSupplier,
    cas_path: Path,
    ledger_path: Path,
    paid_snapshot: Any,
    transport: _PaidTransport,
) -> NativeSearchService:
    assert service.checkpoint_ref == supplier.acknowledged_ref
    assert (
        FileSystemCAS(cas_path).get_bytes(supplier.acknowledged_ref) == supplier.acknowledged_bytes
    )
    state = service.controller._run_state
    assert [row.candidate for row in state.history] == [{"cost": 4}]
    assert state.evaluation_iterations == state.stage_b_evaluations == 1
    assert state.budget_spent == 2.375
    assert state.budget_snapshot_source == "configured_owner_recorded_state"
    assert state.budget_ledger_id == paid_snapshot.ledger_id
    # The controller consumes recorded owner state. Exact receipt custody is
    # independently read below; it must not become a stronger runtime claim.
    assert state.budget_ledger_revision is None
    assert state.budget_evidence["receipt_revision_available"] is False
    assert state.budget_evidence["provider_cost_origin_available"] is False
    assert state.budget_evidence["recorded_by_provider"] == {"independent-batch-provider": 2.375}
    assert service._pending_candidates == {}
    assert len(service._completed_candidate_ids) == 1
    assert FileBudgetLedger(ledger_path).snapshot() == paid_snapshot
    assert transport.calls == 1
    fresh_owner = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    observer, restored_supplier = _service(FileSystemCAS(cas_path), fresh_owner, supplier.cause)
    observer.restore(supplier.acknowledged_ref)
    assert _partial(observer) == _partial(service)
    assert restored_supplier.cursor == 1
    assert observer._failure is None  # The older acknowledged view precedes the refusal.
    assert FileBudgetLedger(ledger_path).snapshot() == paid_snapshot
    return observer


def test_async_rollback_refusal_keeps_original_cause_and_requires_fresh_ack_reader(
    tmp_path: Path,
) -> None:
    ledger_path, cas_path = tmp_path / "paid.json", tmp_path / "cas"
    owner, transport, paid_snapshot = _paid_owner(ledger_path)
    cause = asyncio.CancelledError("original independent batch cancellation")
    service, supplier = _service(FileSystemCAS(cas_path), owner, cause)

    def refuse_rollback() -> None:
        supplier.rollback_refusal = asyncio.CancelledError("secondary rollback refusal")

    supplier.before_refusal = refuse_rollback
    with pytest.raises(asyncio.CancelledError) as raised:
        service.run_search(
            initial_context={"cumulative_cost_usd": 7.5}, initial_candidate={"cost": 4}
        )
    assert raised.value is cause
    assert supplier.cursor == 2  # Restoration failed; the live generator must be fenced.
    assert service._publication_blocked is True
    assert service._failure == f"CancelledError: {cause}"
    with pytest.raises(ValueError, match="reopen_last_acknowledged_ref"):
        service.ask(None, None, {})
    with pytest.raises(ValueError, match="reopen_last_acknowledged_ref"):
        service.checkpoint()
    _assert_old_ack_and_paid_custody(
        service, supplier, cas_path, ledger_path, paid_snapshot, transport
    )


@pytest.mark.parametrize("phase", ["put", "readback"])
def test_failure_checkpoint_publication_phase_keeps_primary_refusal_and_old_ack(
    tmp_path: Path, phase: str
) -> None:
    ledger_path, cas_path = tmp_path / "paid.json", tmp_path / "cas"
    owner, transport, paid_snapshot = _paid_owner(ledger_path)
    store = _PublicationFaultStore(cas_path)
    cause = ValueError("original independent batch refusal")
    service, supplier = _service(store, owner, cause)

    def refuse_publication() -> None:
        store.failure_phase = phase

    supplier.before_refusal = refuse_publication
    with pytest.raises(ValueError) as raised:
        service.run_search(
            initial_context={"cumulative_cost_usd": 7.5}, initial_candidate={"cost": 4}
        )
    assert raised.value is cause
    assert supplier.cursor == 1
    assert service._failure == f"ValueError: {cause}"
    assert service._publication_blocked is True
    assert store.failure_write_attempts == 1
    assert store.refused_readbacks == (1 if phase == "readback" else 0)
    if phase == "readback":
        assert store.unacknowledged_ref != supplier.acknowledged_ref
        persisted = json.loads(FileSystemCAS(cas_path).get_bytes(store.unacknowledged_ref))
        assert persisted["failure"] == service._failure
    else:
        assert store.unacknowledged_ref is None
    with pytest.raises(ValueError, match="reopen_last_acknowledged_ref"):
        service.ask(None, None, {})
    with pytest.raises(ValueError, match="reopen_last_acknowledged_ref"):
        service.checkpoint()
    assert store.failure_write_attempts == 1
    _assert_old_ack_and_paid_custody(
        service, supplier, cas_path, ledger_path, paid_snapshot, transport
    )
