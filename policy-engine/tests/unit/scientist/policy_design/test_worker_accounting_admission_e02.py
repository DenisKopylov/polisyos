"""Real ledger input and pre-factory admission for both policy workers."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.policy_design import adversary, translator
from polisyos.scientist.policy_design._llm_accounting import (
    PolicyWorkerAccountingAdmissionError,
)
from polisyos.scientist.policy_design.adversary import (
    ScenarioAdversaryWorker,
    ScenarioAttackSurface,
)
from polisyos.scientist.policy_design.translator import PolicyTranslatorWorker

from .test_phase_b_policy_workers import _translator_bundle


def _middleware(path: Path) -> BudgetMiddleware:
    return BudgetMiddleware(
        BudgetState(
            limits={
                key: BudgetLimit(key=key, max_usd=Decimal("1"))
                for key in ("policy_adversary", "policy_translator", "policy_briefing")
            }
        ),
        ledger=FileBudgetLedger(path),
    )


def _observe_real_factory(
    monkeypatch: pytest.MonkeyPatch, worker_kind: str
) -> list[dict[str, Any]]:
    module = adversary if worker_kind == "adversary" else translator
    original = module.create_traced_gateway_client
    entries: list[dict[str, Any]] = []

    def observed(**kwargs: Any) -> Any:
        entries.append(dict(kwargs))
        return original(**kwargs)

    monkeypatch.setattr(module, "create_traced_gateway_client", observed)
    return entries


def _operation(
    worker_kind: str,
    middleware: BudgetMiddleware | None,
    raw: BudgetState | None,
) -> Callable[[], Any]:
    if worker_kind == "adversary":
        worker = ScenarioAdversaryWorker(budget_middleware=middleware)
        return lambda: worker.propose(
            ScenarioAttackSurface(candidate_id="actual-admission"), budget_state=raw
        )
    worker = PolicyTranslatorWorker(budget_middleware=middleware)
    bundle = _translator_bundle().model_copy(update={"budget_state": raw})
    return lambda: worker.translate(bundle)


@pytest.mark.parametrize("worker_kind", ["adversary", "translator"])
@pytest.mark.parametrize("profile", ["raw", "mixed", "mixed-same-state"])
def test_raw_state_cannot_replace_or_join_actual_initialized_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker_kind: str, profile: str
) -> None:
    path = tmp_path / "actual-ledger.json"
    middleware = _middleware(path)
    before = path.read_bytes()
    raw = (
        middleware.budget_state
        if profile == "mixed-same-state"
        else BudgetState(
            limits={"policy_adversary": BudgetLimit(key="policy_adversary", max_usd=Decimal(0))}
        )
    )
    entries = _observe_real_factory(monkeypatch, worker_kind)
    operation = _operation(worker_kind, None if profile == "raw" else middleware, raw)

    with pytest.raises(PolicyWorkerAccountingAdmissionError) as captured:
        operation()

    assert captured.value.code == (
        "worker_budget_owner_required" if profile == "raw" else "worker_budget_owner_conflict"
    )
    assert entries == []
    assert path.read_bytes() == before
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.reserved == {}
    assert snapshot.spend_receipts == {}
    assert snapshot.completion_obligations == {}


@pytest.mark.parametrize("worker_kind", ["adversary", "translator"])
@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_current_owner_read_is_required_after_worker_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker_kind: str, fault: str
) -> None:
    path = tmp_path / "actual-ledger.json"
    middleware = _middleware(path)
    operation = _operation(worker_kind, middleware, None)
    entries = _observe_real_factory(monkeypatch, worker_kind)
    if fault == "missing":
        # Fixture removal, not cleanup: the actual admitted owner's input
        # disappears before invocation. Workers must not bootstrap a replacement.
        path.unlink()
        before = None
    else:
        path.write_bytes(b'{"schema_version":"1.2", "incomplete":true}')
        before = path.read_bytes()

    with pytest.raises(PolicyWorkerAccountingAdmissionError) as captured:
        operation()

    assert captured.value.code == "worker_budget_owner_unavailable"
    assert captured.value.__cause__ is not None
    assert entries == []
    if before is None:
        assert not path.exists()
    else:
        assert path.read_bytes() == before


@pytest.mark.parametrize("worker_kind", ["adversary", "translator"])
def test_ledgerless_middleware_cannot_claim_worker_accounting_owner(
    monkeypatch: pytest.MonkeyPatch, worker_kind: str
) -> None:
    state = BudgetState(
        limits={"policy_adversary": BudgetLimit(key="policy_adversary", max_usd=Decimal("1"))}
    )
    before = state.model_dump(mode="json")
    entries = _observe_real_factory(monkeypatch, worker_kind)

    with pytest.raises(PolicyWorkerAccountingAdmissionError) as captured:
        _operation(worker_kind, BudgetMiddleware(state), None)

    assert captured.value.code == "worker_budget_owner_unavailable"
    assert isinstance(captured.value.__cause__, RuntimeError)
    assert entries == []
    assert state.model_dump(mode="json") == before
