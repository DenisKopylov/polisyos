"""Quota enforcement for multi-tenant execution."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from polisyos.core.security.tenant_quota import TenantQuotaLimits, TenantQuotaState

if TYPE_CHECKING:
    from polisyos.core.security.audit_protocol import AuditLog

_logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when a tenant exceeds their resource quota."""

    def __init__(self, tenant_id: str, resource: str, limit: str, current: str) -> None:
        self.tenant_id = tenant_id
        self.resource = resource
        self.limit = limit
        self.current = current
        super().__init__(
            f"Tenant {tenant_id!r} exceeded quota for {resource}: limit={limit}, current={current}"
        )


class QuotaAccountingError(ValueError):
    """Raised when quota accounting is updated through an untrusted mutation path."""


class QuotaEnforcer:
    """Checks and records quota usage for a single tenant.

    Thread-safety: callers must serialise access if shared across threads.
    """

    def __init__(
        self,
        limits: TenantQuotaLimits,
        state: TenantQuotaState,
        audit: AuditLog | None = None,
    ) -> None:
        self._limits = limits
        self._state = state
        self._audit = audit

    @property
    def limits(self) -> TenantQuotaLimits:
        return self._limits

    @property
    def state(self) -> TenantQuotaState:
        return self._state

    def check_run_start(self) -> None:
        """Pre-flight check before starting a new run. Raises QuotaExceededError."""
        self._state.maybe_reset_daily()

        if self._state.concurrent_runs >= self._limits.max_concurrent_runs:
            raise QuotaExceededError(
                self._state.tenant_id,
                "concurrent_runs",
                str(self._limits.max_concurrent_runs),
                str(self._state.concurrent_runs),
            )
        if self._state.daily_run_count >= self._limits.max_runs_per_day:
            raise QuotaExceededError(
                self._state.tenant_id,
                "daily_runs",
                str(self._limits.max_runs_per_day),
                str(self._state.daily_run_count),
            )

    def record_run_start(self) -> None:
        """Record that a new run has started."""
        self._state.maybe_reset_daily()
        self._state.concurrent_runs += 1
        self._state.daily_run_count += 1
        self._emit_audit("QUOTA_RUN_START")

    def record_run_end(self) -> None:
        """Record that a run has ended."""
        self._state.concurrent_runs = max(0, self._state.concurrent_runs - 1)
        self._emit_audit("QUOTA_RUN_END")

    def check_llm_spend(self, amount: Decimal) -> None:
        """Pre-flight check for whether spending *amount* would exceed block-mode limits."""
        self._state.maybe_reset_daily()
        projected = self._state.daily_llm_spend_usd + amount
        if projected > self._limits.max_llm_spend_usd_per_day:
            if self._limits.enforcement_mode == "block":
                raise QuotaExceededError(
                    self._state.tenant_id,
                    "daily_llm_spend",
                    str(self._limits.max_llm_spend_usd_per_day),
                    str(projected),
                )
            _logger.warning(
                "Tenant %s would exceed daily LLM spend: %s > %s (warn mode)",
                self._state.tenant_id,
                projected,
                self._limits.max_llm_spend_usd_per_day,
            )

    def check_storage_delta(self, delta_bytes: int) -> None:
        """Pre-flight check for whether *delta_bytes* would exceed block-mode limits."""
        if delta_bytes < 0:
            raise QuotaAccountingError(
                "Negative storage deltas require the trusted release_storage() path"
            )
        projected = self._state.storage_bytes_used + delta_bytes
        if projected > self._limits.max_storage_bytes:
            if self._limits.enforcement_mode == "block":
                raise QuotaExceededError(
                    self._state.tenant_id,
                    "storage_bytes",
                    str(self._limits.max_storage_bytes),
                    str(projected),
                )
            _logger.warning(
                "Tenant %s would exceed storage quota: %s > %s (warn mode)",
                self._state.tenant_id,
                projected,
                self._limits.max_storage_bytes,
            )

    def record_llm_spend(self, amount: Decimal) -> None:
        """Record LLM spend and enforce daily limit."""
        self._state.maybe_reset_daily()
        self._state.daily_llm_spend_usd += amount
        if self._state.daily_llm_spend_usd > self._limits.max_llm_spend_usd_per_day:
            if self._limits.enforcement_mode == "block":
                raise QuotaExceededError(
                    self._state.tenant_id,
                    "daily_llm_spend",
                    str(self._limits.max_llm_spend_usd_per_day),
                    str(self._state.daily_llm_spend_usd),
                )
            _logger.warning(
                "Tenant %s exceeded daily LLM spend: %s > %s",
                self._state.tenant_id,
                self._state.daily_llm_spend_usd,
                self._limits.max_llm_spend_usd_per_day,
            )

    def record_storage_delta(self, delta_bytes: int) -> None:
        """Record storage usage change and enforce limit."""
        if delta_bytes < 0:
            raise QuotaAccountingError(
                "Negative storage deltas require the trusted release_storage() path"
            )
        self._state.storage_bytes_used += delta_bytes
        if self._state.storage_bytes_used > self._limits.max_storage_bytes:
            if self._limits.enforcement_mode == "block":
                raise QuotaExceededError(
                    self._state.tenant_id,
                    "storage_bytes",
                    str(self._limits.max_storage_bytes),
                    str(self._state.storage_bytes_used),
                )
            _logger.warning(
                "Tenant %s exceeded storage quota: %s > %s",
                self._state.tenant_id,
                self._state.storage_bytes_used,
                self._limits.max_storage_bytes,
            )

    def release_storage(self, released_bytes: int) -> None:
        """Trusted path for reclaiming storage after verified deletion/compaction."""
        if released_bytes < 0:
            raise QuotaAccountingError("released_bytes must be non-negative")
        self._state.storage_bytes_used = max(0, self._state.storage_bytes_used - released_bytes)
        self._emit_audit("QUOTA_STORAGE_RELEASE")

    def check_node_count(self, current_count: int) -> None:
        """Check if node count exceeds per-run limit."""
        if current_count > self._limits.max_nodes_per_run:
            raise QuotaExceededError(
                self._state.tenant_id,
                "nodes_per_run",
                str(self._limits.max_nodes_per_run),
                str(current_count),
            )

    def _emit_audit(self, action: str) -> None:
        if self._audit is not None:
            self._audit.append(
                run_id="",
                actor="quota_enforcer",
                action=action,
                metadata={
                    "tenant_id": self._state.tenant_id,
                    "concurrent_runs": self._state.concurrent_runs,
                    "daily_run_count": self._state.daily_run_count,
                    "daily_llm_spend_usd": str(self._state.daily_llm_spend_usd),
                },
            )
