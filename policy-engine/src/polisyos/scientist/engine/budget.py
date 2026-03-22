"""LLM cost budget models and enforcement."""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.core.errors import ErrorCategory, PolicyOSError

logger = get_logger(__name__)


class BudgetLimit(BaseModel):
    """A single budget threshold."""

    model_config = ConfigDict(extra="forbid")

    key: str
    max_usd: Decimal
    soft_limit_usd: Decimal | None = None


class BudgetState(BaseModel):
    """Tracks limits and cumulative spend across budget keys.

    Thread-safe via external locking (callers should hold a lock
    when calling ``record_spend``).

    Budget key conventions for ``ExperimentState.budgets``:

    * ``run_max_usd``   — total run budget
    * ``run_spent_usd`` — cumulative spend
    * ``node:{alias}_max_usd`` — per-node budget
    * ``global_max_usd`` — cross-run budget (optional)
    """

    model_config = ConfigDict(extra="forbid")

    limits: dict[str, BudgetLimit] = Field(default_factory=dict)
    spent: dict[str, Decimal] = Field(default_factory=dict)

    def remaining(self, key: str) -> Decimal | None:
        """Return remaining budget for *key*, or ``None`` if no limit set."""
        limit = self.limits.get(key)
        if limit is None:
            return None
        current_spend = self.spent.get(key, Decimal(0))
        return limit.max_usd - current_spend

    def would_exceed(self, key: str, estimated_cost: Decimal) -> bool:
        """Return ``True`` if spending *estimated_cost* would exceed budget."""
        remaining = self.remaining(key)
        if remaining is None:
            return False
        return estimated_cost > remaining

    def record_spend(self, key: str, amount: Decimal) -> None:
        """Add *amount* to cumulative spend for *key*."""
        current = self.spent.get(key, Decimal(0))
        self.spent[key] = current + amount

    def is_soft_limit_exceeded(self, key: str) -> bool:
        """Check if soft limit has been crossed for *key*."""
        limit = self.limits.get(key)
        if limit is None or limit.soft_limit_usd is None:
            return False
        return self.spent.get(key, Decimal(0)) > limit.soft_limit_usd

    @classmethod
    def from_experiment_budgets(
        cls,
        budgets: dict[str, Decimal],
    ) -> BudgetState:
        """Build a ``BudgetState`` from ``ExperimentState.budgets``."""
        limits: dict[str, BudgetLimit] = {}
        spent: dict[str, Decimal] = {}

        for key, value in budgets.items():
            if key.endswith("_max_usd"):
                budget_key = key.removesuffix("_max_usd")
                limits[budget_key] = BudgetLimit(key=budget_key, max_usd=value)
            elif key.endswith("_spent_usd"):
                budget_key = key.removesuffix("_spent_usd")
                spent[budget_key] = value

        return cls(limits=limits, spent=spent)

    def to_experiment_budgets(self) -> dict[str, Decimal]:
        """Serialize back to ``ExperimentState.budgets`` format."""
        result: dict[str, Decimal] = {}
        for key, limit in self.limits.items():
            result[f"{key}_max_usd"] = limit.max_usd
            if limit.soft_limit_usd is not None:
                result[f"{key}_soft_limit_usd"] = limit.soft_limit_usd
        for key, amount in self.spent.items():
            result[f"{key}_spent_usd"] = amount
        return result


class BudgetExhaustedError(PolicyOSError):
    """Raised when an LLM call would exceed the budget."""

    default_stage = "scientist.engine.budget"
    default_category = ErrorCategory.VALIDATION
