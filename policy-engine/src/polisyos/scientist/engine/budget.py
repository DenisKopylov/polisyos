"""LLM cost budget models and enforcement."""

from __future__ import annotations

from decimal import Decimal

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
    when calling mutating methods like ``record_spend``, ``reserve``,
    ``release``, ``commit_reservation``).

    Budget key conventions for ``ExperimentState.budgets``:

    * ``run_max_usd``   — total run budget
    * ``run_spent_usd`` — cumulative spend
    * ``node:{alias}_max_usd`` — per-node budget
    * ``global_max_usd`` — cross-run budget (optional)
    """

    model_config = ConfigDict(extra="forbid")

    limits: dict[str, BudgetLimit] = Field(default_factory=dict)
    spent: dict[str, Decimal] = Field(default_factory=dict)
    provider_spent: dict[str, Decimal] = Field(default_factory=dict)
    reserved: dict[str, Decimal] = Field(default_factory=dict)

    def remaining(self, key: str) -> Decimal | None:
        """Return remaining budget for *key*, or ``None`` if no limit set."""
        limit = self.limits.get(key)
        if limit is None:
            return None
        current_spend = self.spent.get(key, Decimal(0))
        current_reserved = self.reserved.get(key, Decimal(0))
        return limit.max_usd - current_spend - current_reserved

    def would_exceed(self, key: str, estimated_cost: Decimal) -> bool:
        """Return ``True`` if spending *estimated_cost* would exceed budget."""
        remaining = self.remaining(key)
        if remaining is None:
            return False
        return estimated_cost > remaining

    def record_spend(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> None:
        """Add *amount* to cumulative spend for *key*."""
        current = self.spent.get(key, Decimal(0))
        self.spent[key] = current + amount
        if provider is not None:
            prov_current = self.provider_spent.get(provider, Decimal(0))
            self.provider_spent[provider] = prov_current + amount

    def reserve(self, key: str, amount: Decimal) -> bool:
        """Pre-allocate budget.  Returns ``False`` if insufficient."""
        remaining = self.remaining(key)
        if remaining is None:
            return True
        if amount > remaining:
            return False
        self.reserved[key] = self.reserved.get(key, Decimal(0)) + amount
        return True

    def release(self, key: str, amount: Decimal) -> Decimal:
        """Release previously reserved budget and return the actual released amount."""
        current = self.reserved.get(key, Decimal(0))
        released = min(current, max(Decimal(0), amount))
        self.reserved[key] = max(Decimal(0), current - released)
        return released

    def commit_reservation(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> Decimal:
        """Convert a reservation into actual spend and return the committed amount."""
        committed = self.release(key, amount)
        if committed > 0:
            self.record_spend(key, committed, provider=provider)
        return committed

    def is_soft_limit_exceeded(self, key: str) -> bool:
        """Check if soft limit has been crossed for *key*."""
        limit = self.limits.get(key)
        if limit is None or limit.soft_limit_usd is None:
            return False
        return self.spent.get(key, Decimal(0)) > limit.soft_limit_usd

    def utilization(self, key: str) -> float | None:
        """Return spend / max_usd ratio for *key*, or ``None`` if no limit."""
        limit = self.limits.get(key)
        if limit is None or limit.max_usd <= 0:
            return None
        current = self.spent.get(key, Decimal(0))
        return float(current / limit.max_usd)

    def threshold_alerts(self, key: str) -> list[int]:
        """Return list of crossed thresholds (80, 90) for *key*."""
        limit = self.limits.get(key)
        if limit is None or limit.max_usd <= 0:
            return []
        current = self.spent.get(key, Decimal(0))
        ratio = float(current / limit.max_usd)
        alerts: list[int] = []
        if ratio >= 0.9:
            alerts.append(90)
        elif ratio >= 0.8:
            alerts.append(80)
        return alerts

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
