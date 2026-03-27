"""Tests for QuotaEnforcer — WS3 multi-tenancy quota enforcement."""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

sys.path.insert(0, "src")

from polisyos.core.security.quota_enforcer import QuotaEnforcer, QuotaExceededError
from polisyos.core.security.tenant_quota import TenantQuotaLimits, TenantQuotaState


def _make_enforcer(
    *,
    max_concurrent: int = 5,
    max_daily: int = 10,
    max_nodes: int = 100,
    concurrent_runs: int = 0,
    daily_run_count: int = 0,
) -> QuotaEnforcer:
    limits = TenantQuotaLimits(
        max_concurrent_runs=max_concurrent,
        max_runs_per_day=max_daily,
        max_nodes_per_run=max_nodes,
    )
    state = TenantQuotaState(
        tenant_id="t-test",
        concurrent_runs=concurrent_runs,
        daily_run_count=daily_run_count,
        last_reset_date=date.today().isoformat(),
    )
    return QuotaEnforcer(limits=limits, state=state)


class TestCheckRunStart:
    def test_check_run_start_ok(self) -> None:
        enforcer = _make_enforcer(concurrent_runs=2, daily_run_count=3)
        # Should not raise
        enforcer.check_run_start()

    def test_check_run_start_concurrent_exceeded(self) -> None:
        enforcer = _make_enforcer(max_concurrent=3, concurrent_runs=3)
        with pytest.raises(QuotaExceededError, match="concurrent_runs"):
            enforcer.check_run_start()

    def test_check_run_start_daily_exceeded(self) -> None:
        enforcer = _make_enforcer(max_daily=5, daily_run_count=5)
        with pytest.raises(QuotaExceededError, match="daily_runs"):
            enforcer.check_run_start()


class TestRecordRunLifecycle:
    def test_record_run_start_increments(self) -> None:
        enforcer = _make_enforcer()
        assert enforcer.state.concurrent_runs == 0
        assert enforcer.state.daily_run_count == 0

        enforcer.record_run_start()

        assert enforcer.state.concurrent_runs == 1
        assert enforcer.state.daily_run_count == 1

    def test_record_run_end_decrements(self) -> None:
        enforcer = _make_enforcer(concurrent_runs=2)
        enforcer.record_run_end()
        assert enforcer.state.concurrent_runs == 1

        # Should not go below 0
        enforcer.record_run_end()
        enforcer.record_run_end()
        assert enforcer.state.concurrent_runs == 0


class TestLLMSpend:
    def test_record_llm_spend(self) -> None:
        enforcer = _make_enforcer()
        enforcer.record_llm_spend(Decimal("1.50"))
        enforcer.record_llm_spend(Decimal("2.25"))
        assert enforcer.state.daily_llm_spend_usd == Decimal("3.75")


class TestNodeCount:
    def test_check_node_count(self) -> None:
        enforcer = _make_enforcer(max_nodes=50)
        # Within limit — should not raise
        enforcer.check_node_count(50)

        # Exceeds limit
        with pytest.raises(QuotaExceededError, match="nodes_per_run"):
            enforcer.check_node_count(51)


class TestDailyReset:
    def test_daily_reset(self) -> None:
        enforcer = _make_enforcer(daily_run_count=5)
        enforcer.state.daily_llm_spend_usd = Decimal("10.00")

        # Simulate date change by setting last_reset_date to yesterday
        enforcer.state.last_reset_date = "2020-01-01"

        enforcer.check_run_start()

        assert enforcer.state.daily_run_count == 0
        assert enforcer.state.daily_llm_spend_usd == Decimal("0")


class TestQuotaExceededError:
    def test_quota_exceeded_error_message(self) -> None:
        err = QuotaExceededError(
            tenant_id="t-abc",
            resource="concurrent_runs",
            limit="5",
            current="6",
        )
        assert err.tenant_id == "t-abc"
        assert err.resource == "concurrent_runs"
        assert err.limit == "5"
        assert err.current == "6"
        assert "t-abc" in str(err)
        assert "concurrent_runs" in str(err)
