"""Behavioral witnesses for identified compute accounting; synthetic costs only."""

from __future__ import annotations

import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSettlementOutcomeUnknownError,
    FileBudgetLedger,
)

REQUEST = "1" * 64
SETTLEMENT = "2" * 64


def _owner(path: Path) -> FileBudgetLedger:
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    )
    return ledger


def test_two_racing_reservations_share_the_actual_ledger_lock(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    owner = _owner(path)
    other = FileBudgetLedger(path)

    def attempt(event: str) -> str:
        try:
            other.reserve_compute(event, REQUEST, "run", Decimal("0.75"))
        except ValueError:
            return "refused"
        return "reserved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, ("event-a", "event-b")))
    assert sorted(outcomes) == ["refused", "reserved"]
    snapshot = owner.snapshot()
    assert snapshot.state.reserved["run"] == Decimal("0.75")
    assert len(snapshot.compute_reservations) == 1


def test_settlement_is_atomic_and_exact_retries_charge_once(tmp_path: Path) -> None:
    owner = _owner(tmp_path / "budget.json")
    owner.reserve_compute("event", REQUEST, "run", Decimal("0.75"))
    with pytest.raises(ValueError, match="legacy_mutation_cannot_consume"):
        owner.release("run", Decimal("0.75"))
    first = owner.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.4"))
    again = owner.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.4"))
    assert again == first
    state = owner.snapshot().state
    assert state.spent["run"] == Decimal("0.4")
    assert state.reserved["run"] == Decimal("0")
    with pytest.raises(ValueError, match="compute_settlement_event_conflict"):
        owner.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.5"))


def test_lost_settlement_ack_is_reconciled_without_second_charge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "budget.json"
    owner = _owner(path)
    owner.reserve_compute("event", REQUEST, "run", Decimal("0.75"))
    persist = owner._persist_snapshot

    def write_then_lose_ack(snapshot):
        persist(snapshot)
        raise OSError("synthetic lost acknowledgement")

    monkeypatch.setattr(owner, "_persist_snapshot", write_then_lose_ack)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        owner.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.4"))
    fresh = FileBudgetLedger(path)
    resolved = fresh.resolve_compute("event")
    assert resolved is not None and resolved.status == "settled"
    assert fresh.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.4")) == resolved
    assert fresh.snapshot().state.spent["run"] == Decimal("0.4")


def test_unknown_cost_keeps_reservation_and_blocks_next_work(tmp_path: Path) -> None:
    owner = _owner(tmp_path / "budget.json")
    owner.reserve_compute("event", REQUEST, "run", Decimal("0.2"))
    assert owner.mark_compute_unknown("event", REQUEST).status == "unknown"
    with pytest.raises(ValueError, match="unresolved_reservation"):
        owner.reserve_compute("next", REQUEST, "run", Decimal("0.1"))
    assert owner.snapshot().state.reserved["run"] == Decimal("0.2")
    owner.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.1"))
    assert owner.reserve_compute("next", REQUEST, "run", Decimal("0.1")).status == "reserved"


def test_v15_legacy_and_other_writers_preserve_identified_records(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    owner = _owner(path)
    data = json.loads(path.read_text())
    data["schema_version"] = "1.5"
    del data["compute_reservations"]
    path.write_text(json.dumps(data))
    reopened = FileBudgetLedger(path)
    assert reopened.snapshot().compute_reservations == {}
    reopened.reserve_compute("event", REQUEST, "run", Decimal("0.2"))
    reopened.record_spend("other", Decimal("0.1"))
    reopened.begin_producer_event("llm", REQUEST, "other", "model", "provider")
    reopened.settle_producer_event(
        "llm",
        REQUEST,
        SETTLEMENT,
        "other",
        "model",
        "provider",
        Decimal("0.1"),
        "reported",
        None,
    )
    assert reopened.resolve_compute("event").status == "reserved"


def test_lost_reservation_ack_recovers_without_new_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "budget.json"
    owner = _owner(path)
    persist = owner._persist_snapshot

    def write_then_lose_ack(snapshot):
        persist(snapshot)
        raise OSError("synthetic lost acknowledgement")

    monkeypatch.setattr(owner, "_persist_snapshot", write_then_lose_ack)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        owner.reserve_compute("event", REQUEST, "run", Decimal("0.7"))
    fresh = FileBudgetLedger(path)
    record = fresh.resolve_compute("event")
    assert record is not None and record.status == "reserved"
    assert fresh.reserve_compute("event", REQUEST, "run", Decimal("0.7")) == record
    assert fresh.snapshot().state.reserved["run"] == Decimal("0.7")
    with pytest.raises(ValueError, match="event_conflict"):
        fresh.reserve_compute("event", REQUEST, "run", Decimal("0.6"))


def test_unknown_ack_readback_cannot_become_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.scientist.orchestration.engine import budget_ledger

    path = tmp_path / "budget.json"
    owner = _owner(path)
    owner.reserve_compute("event", REQUEST, "run", Decimal("0.2"))

    def cannot_sync(_path: Path) -> None:
        raise OSError("synthetic durability outage")

    monkeypatch.setattr(budget_ledger, "_fsync_dir", cannot_sync)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        owner.resolve_compute("event")
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        owner.reserve_compute("event", REQUEST, "run", Decimal("0.2"))


def test_corrupt_reservation_balance_and_missing_new_field_refuse(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    owner = _owner(path)
    owner.reserve_compute("event", REQUEST, "run", Decimal("0.2"))
    data = json.loads(path.read_text())
    data["state"]["reserved"]["run"] = "0"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="identified reservations exceed"):
        FileBudgetLedger(path).snapshot()
    del data["compute_reservations"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="missing snapshot.compute_reservations"):
        FileBudgetLedger(path).snapshot()


def test_compute_and_legacy_receipt_kinds_cannot_alias(tmp_path: Path) -> None:
    owner = _owner(tmp_path / "budget.json")
    owner.reserve_compute("event", REQUEST, "run", Decimal("0.3"))
    with pytest.raises(ValueError, match="budget_event_kind_conflict"):
        owner.settle_spend("event", "run", Decimal("0.2"), payload_digest=SETTLEMENT)
    with pytest.raises(ValueError, match="budget_event_kind_conflict"):
        owner.begin_producer_event("event", REQUEST, "run", "model", "provider")
    owner.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.2"))
    with pytest.raises(ValueError, match="budget_event_kind_conflict"):
        owner.settle_spend("event", "run", Decimal("0.2"), payload_digest=SETTLEMENT)
    with pytest.raises(ValueError, match="budget_event_kind_conflict"):
        owner.settle_producer_event(
            "event",
            REQUEST,
            SETTLEMENT,
            "run",
            "model",
            "provider",
            Decimal("0.2"),
            "reported",
            None,
        )
    with pytest.raises(ValueError, match="budget_event_kind_conflict"):
        owner.resolve_spend("event")
    with pytest.raises(ValueError, match="budget_event_kind_conflict"):
        owner.resolve_producer_event("event")
    assert owner.snapshot().state.spent["run"] == Decimal("0.2")

    owner.settle_spend("legacy", "run", Decimal("0.1"), payload_digest=SETTLEMENT)
    with pytest.raises(ValueError, match="compute_reservation_event_conflict"):
        owner.reserve_compute("legacy", REQUEST, "run", Decimal("0.1"))
    with pytest.raises(ValueError, match="budget_event_kind_conflict"):
        owner.resolve_compute("legacy")
    owner.begin_producer_event("producer", REQUEST, "run", "model", "provider")
    with pytest.raises(ValueError, match="compute_reservation_event_conflict"):
        owner.reserve_compute("producer", REQUEST, "run", Decimal("0.1"))


@pytest.mark.parametrize("compute_first", [False, True])
@pytest.mark.parametrize("operation", ["release", "commit"])
def test_legacy_and_identified_reservations_keep_separate_floor(
    tmp_path: Path, *, compute_first: bool, operation: str
) -> None:
    owner = _owner(tmp_path / "budget.json")
    if compute_first:
        owner.reserve_compute("event", REQUEST, "run", Decimal("0.2"))
    assert owner.reserve("run", Decimal("0.1")).reserved
    if not compute_first:
        owner.reserve_compute("event", REQUEST, "run", Decimal("0.2"))
    mutate = owner.release if operation == "release" else owner.commit_reservation
    with pytest.raises(ValueError, match="legacy_mutation_cannot_consume"):
        mutate("run", Decimal("0.2"))
    assert mutate("run", Decimal("0.1")).applied_amount == Decimal("0.1")
    assert owner.snapshot().state.reserved["run"] == Decimal("0.2")
    owner.settle_compute("event", REQUEST, SETTLEMENT, Decimal("0.15"))
    assert owner.snapshot().state.reserved["run"] == Decimal("0")


def _process_reserve(path: str, event: str, barrier, result) -> None:
    owner = FileBudgetLedger(Path(path))
    barrier.wait()
    try:
        owner.reserve_compute(event, REQUEST, "run", Decimal("0.75"))
    except ValueError as exc:
        result.put(("refused", str(exc)))
    else:
        result.put(("reserved", event))


def test_two_processes_compete_on_one_durable_owner(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    owner = _owner(path)
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    result = ctx.Queue()
    processes = [
        ctx.Process(target=_process_reserve, args=(str(path), event, barrier, result))
        for event in ("event-a", "event-b")
    ]
    for process in processes:
        process.start()
    outcomes = [result.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    assert sorted(item[0] for item in outcomes) == ["refused", "reserved"]
    assert [item[1] for item in outcomes if item[0] == "refused"] == [
        "compute_budget_unresolved_reservation"
    ]
    snapshot = owner.snapshot()
    assert len(snapshot.compute_reservations) == 1
    assert snapshot.state.reserved["run"] == Decimal("0.75")
