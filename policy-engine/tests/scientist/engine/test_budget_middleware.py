"""Tests for BudgetMiddleware and BudgetState enhancements."""

from __future__ import annotations

import threading
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.engine.budget import BudgetExhaustedError, BudgetLimit, BudgetState
from polisyos.scientist.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.engine.budget_middleware import BudgetMiddleware


def _budget(max_usd: str = "100", spent: str = "0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
        spent={"run": Decimal(spent)},
    )


# ── BudgetState new features ─────────────────────────────────────────


class TestBudgetStateProviderSpent:
    def test_record_with_provider(self) -> None:
        bs = _budget()
        bs.record_spend("run", Decimal("10"), provider="openai")
        bs.record_spend("run", Decimal("5"), provider="anthropic")
        bs.record_spend("run", Decimal("3"), provider="openai")
        assert bs.provider_spent["openai"] == Decimal("13")
        assert bs.provider_spent["anthropic"] == Decimal("5")
        assert bs.spent["run"] == Decimal("18")

    def test_record_without_provider(self) -> None:
        bs = _budget()
        bs.record_spend("run", Decimal("10"))
        assert bs.provider_spent == {}
        assert bs.spent["run"] == Decimal("10")


class TestBudgetStateReservation:
    def test_reserve_reduces_remaining(self) -> None:
        bs = _budget(max_usd="100")
        assert bs.remaining("run") == Decimal("100")
        assert bs.reserve("run", Decimal("30")) is True
        assert bs.remaining("run") == Decimal("70")

    def test_reserve_fails_when_insufficient(self) -> None:
        bs = _budget(max_usd="10")
        assert bs.reserve("run", Decimal("20")) is False
        assert bs.remaining("run") == Decimal("10")

    def test_release_restores_remaining(self) -> None:
        bs = _budget(max_usd="100")
        bs.reserve("run", Decimal("40"))
        released = bs.release("run", Decimal("40"))
        assert released == Decimal("40")
        assert bs.remaining("run") == Decimal("100")

    def test_release_clamps_to_zero(self) -> None:
        bs = _budget(max_usd="100")
        released = bs.release("run", Decimal("50"))  # nothing reserved
        assert released == Decimal("0")
        assert bs.reserved["run"] == Decimal("0")

    def test_commit_converts_to_spend(self) -> None:
        bs = _budget(max_usd="100")
        bs.reserve("run", Decimal("20"))
        committed = bs.commit_reservation("run", Decimal("20"))
        assert committed == Decimal("20")
        assert bs.reserved.get("run", Decimal(0)) == Decimal("0")
        assert bs.spent["run"] == Decimal("20")
        assert bs.remaining("run") == Decimal("80")

    def test_remaining_accounts_for_reserved(self) -> None:
        bs = _budget(max_usd="100", spent="30")
        bs.reserve("run", Decimal("20"))
        assert bs.remaining("run") == Decimal("50")

    def test_would_exceed_accounts_for_reserved(self) -> None:
        bs = _budget(max_usd="100")
        bs.reserve("run", Decimal("90"))
        assert bs.would_exceed("run", Decimal("15")) is True
        assert bs.would_exceed("run", Decimal("10")) is False

    def test_reserve_no_limit(self) -> None:
        bs = BudgetState()
        assert bs.reserve("run", Decimal("1000")) is True


class TestBudgetStateThresholdAlerts:
    def test_alert_at_80(self) -> None:
        bs = _budget(max_usd="100", spent="80")
        assert bs.threshold_alerts("run") == [80]

    def test_alert_at_90(self) -> None:
        bs = _budget(max_usd="100", spent="90")
        assert bs.threshold_alerts("run") == [90]

    def test_no_alert_below_80(self) -> None:
        bs = _budget(max_usd="100", spent="79")
        assert bs.threshold_alerts("run") == []

    def test_no_limit_no_alert(self) -> None:
        bs = BudgetState()
        assert bs.threshold_alerts("run") == []


class TestBudgetStateRoundtrip:
    def test_serialization_with_new_fields(self) -> None:
        bs = _budget(max_usd="100", spent="30")
        bs.record_spend("run", Decimal("10"), provider="openai")
        bs.reserve("run", Decimal("5"))

        data = bs.model_dump()
        bs2 = BudgetState.model_validate(data)
        assert bs2.provider_spent == bs.provider_spent
        assert bs2.reserved == bs.reserved


# ── BudgetMiddleware ──────────────────────────────────────────────────


class TestBudgetMiddleware:
    def test_pre_check_passes(self) -> None:
        mw = BudgetMiddleware(_budget(max_usd="100", spent="50"))
        mw.pre_check("node_a")  # should not raise

    def test_pre_check_blocks_exhausted(self) -> None:
        mw = BudgetMiddleware(_budget(max_usd="100", spent="100"))
        with pytest.raises(BudgetExhaustedError):
            mw.pre_check("node_a")

    def test_threshold_deduplication(self) -> None:
        mw = BudgetMiddleware(_budget(max_usd="100", spent="85"))
        first = mw.check_thresholds("run")
        second = mw.check_thresholds("run")
        assert first == [80]
        assert second == []  # already alerted

    def test_record_spend_safe(self) -> None:
        bs = _budget(max_usd="100")
        mw = BudgetMiddleware(bs)
        mw.record_spend_safe("run", Decimal("10"), provider="openai")
        assert bs.spent["run"] == Decimal("10")
        assert bs.provider_spent["openai"] == Decimal("10")

    def test_reserve_safe(self) -> None:
        bs = _budget(max_usd="100")
        mw = BudgetMiddleware(bs)
        assert mw.reserve_safe("run", Decimal("80")) is True
        assert mw.reserve_safe("run", Decimal("30")) is False

    def test_commit_safe(self) -> None:
        bs = _budget(max_usd="100")
        mw = BudgetMiddleware(bs)
        mw.reserve_safe("run", Decimal("20"))
        assert mw.commit_safe("run", Decimal("20")) == Decimal("20")
        assert bs.spent["run"] == Decimal("20")

    def test_release_safe_returns_actual_released_amount(self) -> None:
        bs = _budget(max_usd="100")
        mw = BudgetMiddleware(bs)
        mw.reserve_safe("run", Decimal("15"))
        assert mw.release_safe("run", Decimal("25")) == Decimal("15")
        assert bs.reserved["run"] == Decimal("0")


class TestBudgetMiddlewareThreadSafety:
    def test_concurrent_record_spend(self) -> None:
        bs = _budget(max_usd="10000")
        mw = BudgetMiddleware(bs)
        barrier = threading.Barrier(10)

        def spend_loop() -> None:
            barrier.wait()
            for _ in range(100):
                mw.record_spend_safe("run", Decimal("1"))

        threads = [threading.Thread(target=spend_loop) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert bs.spent["run"] == Decimal("1000")


class TestFileBudgetLedger:
    def test_ledger_persists_state_across_middleware_instances(self, tmp_path: Path) -> None:
        ledger = FileBudgetLedger(tmp_path / "budget_ledger.json")
        mw_a = BudgetMiddleware(_budget(max_usd="100"), ledger=ledger)
        mw_b = BudgetMiddleware(_budget(max_usd="100"), ledger=ledger)

        assert mw_a.reserve_safe("run", Decimal("30")) is True
        assert mw_b.commit_safe("run", Decimal("20"), provider="openai") == Decimal("20")
        assert mw_a.release_safe("run", Decimal("50")) == Decimal("10")
        assert mw_b.budget_state.spent["run"] == Decimal("20")
        assert mw_b.budget_state.provider_spent["openai"] == Decimal("20")
        assert mw_b.budget_state.reserved["run"] == Decimal("0")

    def test_ledger_mutation_uses_copy_on_write_budget_state(self, tmp_path: Path) -> None:
        ledger = FileBudgetLedger(tmp_path / "budget_ledger.json")
        initial = _budget(max_usd="100")

        loaded = ledger.load_or_bootstrap(initial)
        result = ledger.record_spend("run", Decimal("10"), provider="openai")

        assert initial.spent == {"run": Decimal("0")}
        assert loaded.spent == {"run": Decimal("0")}
        assert result.state.spent["run"] == Decimal("10")
        assert result.state.provider_spent["openai"] == Decimal("10")
        assert result.state.limits is not loaded.limits
        assert result.state.limits["run"] == loaded.limits["run"]
        result.state.spent["run"] = Decimal("25")
        assert loaded.spent == {"run": Decimal("0")}

    def test_ledger_snapshot_exposes_canonical_multi_host_contract(self, tmp_path: Path) -> None:
        ledger = FileBudgetLedger(
            tmp_path / "budget_ledger.json",
            ledger_id="ledger://scientist-phase4",
            host_id="host-a",
            writer_id="host-a:worker-1",
        )

        ledger.load_or_bootstrap(_budget(max_usd="100"))
        snapshot = ledger.snapshot()

        assert snapshot.canonical_contract == "scientist.multi_host_budget_ledger.v1"
        assert snapshot.coordination_mode == "shared_posix_file_lock"
        assert snapshot.ledger_id == "ledger://scientist-phase4"
        assert snapshot.last_writer is not None
        assert snapshot.last_writer.host_id == "host-a"
        assert snapshot.last_writer.writer_id == "host-a:worker-1"
        assert [item.operation for item in snapshot.recent_mutations] == ["bootstrap"]

    def test_ledger_journal_tracks_cross_host_mutation_provenance(self, tmp_path: Path) -> None:
        path = tmp_path / "budget_ledger.json"
        ledger_a = FileBudgetLedger(
            path,
            ledger_id="ledger://scientist-phase4",
            host_id="host-a",
            writer_id="host-a:worker-1",
        )
        ledger_b = FileBudgetLedger(
            path,
            ledger_id="ledger://scientist-phase4",
            host_id="host-b",
            writer_id="host-b:worker-9",
        )

        ledger_a.load_or_bootstrap(_budget(max_usd="100"))
        assert ledger_a.reserve("run", Decimal("30")).reserved is True
        committed = ledger_b.commit_reservation("run", Decimal("10"), provider="openai")
        snapshot = ledger_b.snapshot()

        assert committed.revision == 2
        assert committed.state.spent["run"] == Decimal("10")
        assert committed.state.reserved["run"] == Decimal("20")
        assert snapshot.revision == 2
        assert snapshot.last_writer is not None
        assert snapshot.last_writer.host_id == "host-b"
        assert snapshot.last_writer.writer_id == "host-b:worker-9"
        assert [item.writer.host_id for item in snapshot.recent_mutations] == [
            "host-a",
            "host-a",
            "host-b",
        ]
        assert [item.operation for item in snapshot.recent_mutations] == [
            "bootstrap",
            "reserve",
            "commit_reservation",
        ]
        assert snapshot.recent_mutations[-1].provider == "openai"

    def test_ledger_journal_retention_stays_bounded(self, tmp_path: Path) -> None:
        ledger = FileBudgetLedger(
            tmp_path / "budget_ledger.json",
            host_id="host-a",
            writer_id="host-a:worker-1",
            mutation_history_limit=2,
        )

        ledger.load_or_bootstrap(_budget(max_usd="100"))
        ledger.record_spend("run", Decimal("1"))
        ledger.record_spend("run", Decimal("2"))
        ledger.record_spend("run", Decimal("3"))
        snapshot = ledger.snapshot()

        assert len(snapshot.recent_mutations) == 2
        assert [item.revision for item in snapshot.recent_mutations] == [2, 3]
        assert [item.applied_amount for item in snapshot.recent_mutations] == [
            Decimal("2"),
            Decimal("3"),
        ]
