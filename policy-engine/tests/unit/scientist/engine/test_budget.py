"""Tests for BudgetState, BudgetLimit, BudgetExhaustedError."""

from __future__ import annotations

from decimal import Decimal

import pytest
from polisyos.scientist.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)


class TestBudgetLimit:
    def test_basic_creation(self):
        limit = BudgetLimit(key="run", max_usd=Decimal("10.00"))
        assert limit.key == "run"
        assert limit.max_usd == Decimal("10.00")
        assert limit.soft_limit_usd is None

    def test_with_soft_limit(self):
        limit = BudgetLimit(
            key="run",
            max_usd=Decimal("10.00"),
            soft_limit_usd=Decimal("8.00"),
        )
        assert limit.soft_limit_usd == Decimal("8.00")

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            BudgetLimit(key="x", max_usd=Decimal("1"), unknown="y")


class TestBudgetState:
    def test_remaining_no_limit(self):
        state = BudgetState()
        assert state.remaining("run") is None

    def test_remaining_with_limit(self):
        state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.00"))},
            spent={"run": Decimal("3.50")},
        )
        assert state.remaining("run") == Decimal("6.50")

    def test_remaining_no_spend(self):
        state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.00"))},
        )
        assert state.remaining("run") == Decimal("5.00")

    def test_would_exceed_false(self):
        state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.00"))},
            spent={"run": Decimal("3.00")},
        )
        assert state.would_exceed("run", Decimal("5.00")) is False

    def test_would_exceed_true(self):
        state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.00"))},
            spent={"run": Decimal("8.00")},
        )
        assert state.would_exceed("run", Decimal("5.00")) is True

    def test_would_exceed_no_limit(self):
        state = BudgetState()
        assert state.would_exceed("run", Decimal("999.00")) is False

    def test_record_spend(self):
        state = BudgetState()
        state.record_spend("run", Decimal("1.50"))
        assert state.spent["run"] == Decimal("1.50")
        state.record_spend("run", Decimal("2.50"))
        assert state.spent["run"] == Decimal("4.00")

    def test_is_soft_limit_exceeded(self):
        state = BudgetState(
            limits={
                "run": BudgetLimit(
                    key="run",
                    max_usd=Decimal("10.00"),
                    soft_limit_usd=Decimal("7.00"),
                )
            },
            spent={"run": Decimal("8.00")},
        )
        assert state.is_soft_limit_exceeded("run") is True

    def test_is_soft_limit_not_exceeded(self):
        state = BudgetState(
            limits={
                "run": BudgetLimit(
                    key="run",
                    max_usd=Decimal("10.00"),
                    soft_limit_usd=Decimal("7.00"),
                )
            },
            spent={"run": Decimal("5.00")},
        )
        assert state.is_soft_limit_exceeded("run") is False

    def test_is_soft_limit_no_soft(self):
        state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.00"))},
        )
        assert state.is_soft_limit_exceeded("run") is False


class TestBudgetStateConversion:
    def test_from_experiment_budgets(self):
        budgets = {
            "run_max_usd": Decimal("10.00"),
            "run_spent_usd": Decimal("3.00"),
            "node:plan_max_usd": Decimal("2.00"),
        }
        state = BudgetState.from_experiment_budgets(budgets)
        assert state.limits["run"].max_usd == Decimal("10.00")
        assert state.spent["run"] == Decimal("3.00")
        assert state.limits["node:plan"].max_usd == Decimal("2.00")

    def test_to_experiment_budgets(self):
        state = BudgetState(
            limits={
                "run": BudgetLimit(
                    key="run",
                    max_usd=Decimal("10.00"),
                    soft_limit_usd=Decimal("8.00"),
                )
            },
            spent={"run": Decimal("3.00")},
        )
        result = state.to_experiment_budgets()
        assert result["run_max_usd"] == Decimal("10.00")
        assert result["run_soft_limit_usd"] == Decimal("8.00")
        assert result["run_spent_usd"] == Decimal("3.00")

    def test_roundtrip(self):
        original = {
            "run_max_usd": Decimal("10.00"),
            "run_spent_usd": Decimal("3.00"),
        }
        state = BudgetState.from_experiment_budgets(original)
        result = state.to_experiment_budgets()
        assert result["run_max_usd"] == original["run_max_usd"]
        assert result["run_spent_usd"] == original["run_spent_usd"]


class TestBudgetExhaustedError:
    def test_is_policy_os_error(self):
        err = BudgetExhaustedError("exceeded")
        from polisyos.core.errors import PolicyOSError

        assert isinstance(err, PolicyOSError)

    def test_default_stage(self):
        assert BudgetExhaustedError.default_stage == "scientist.engine.budget"
