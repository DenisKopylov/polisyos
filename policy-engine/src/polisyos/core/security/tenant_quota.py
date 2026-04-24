"""Tenant quota limits and state models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TenantQuotaLimits(BaseModel):
    """Per-tenant resource limits."""

    model_config = ConfigDict(extra="forbid")

    max_concurrent_runs: int = Field(default=10, ge=1)
    max_llm_spend_usd_per_day: Decimal = Field(default=Decimal("100"))
    max_storage_bytes: int = Field(default=10 * 1024**3)  # 10 GB
    max_nodes_per_run: int = Field(default=200, ge=1)
    max_runs_per_day: int = Field(default=100, ge=1)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    enforcement_mode: Literal["warn", "block"] = "block"


class TenantQuotaState(BaseModel):
    """Mutable per-tenant quota usage tracking."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    concurrent_runs: int = 0
    daily_llm_spend_usd: Decimal = Decimal("0")
    daily_run_count: int = 0
    storage_bytes_used: int = 0
    last_reset_date: str = ""  # YYYY-MM-DD, auto-reset when day changes

    def maybe_reset_daily(self) -> None:
        """Reset daily counters if date changed."""
        today = date.today().isoformat()
        if self.last_reset_date != today:
            self.daily_llm_spend_usd = Decimal("0")
            self.daily_run_count = 0
            self.last_reset_date = today
