"""Per-tenant quota configuration registry."""

from __future__ import annotations

import threading
from typing import Any

from polisyos.core.security.quota_enforcer import QuotaEnforcer
from polisyos.core.security.tenant_quota import TenantQuotaLimits, TenantQuotaState


class TenantQuotaRegistry:
    """Thread-safe registry of per-tenant quota limits and state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._limits: dict[str, TenantQuotaLimits] = {}
        self._states: dict[str, TenantQuotaState] = {}
        self._default_limits = TenantQuotaLimits()

    def get_limits(self, tenant_id: str) -> TenantQuotaLimits:
        with self._lock:
            return self._limits.get(tenant_id, self._default_limits)

    def set_limits(self, tenant_id: str, limits: TenantQuotaLimits) -> None:
        with self._lock:
            self._limits[tenant_id] = limits

    def get_state(self, tenant_id: str) -> TenantQuotaState:
        with self._lock:
            if tenant_id not in self._states:
                self._states[tenant_id] = TenantQuotaState(tenant_id=tenant_id)
            return self._states[tenant_id]

    def get_enforcer(self, tenant_id: str, audit: Any = None) -> QuotaEnforcer:
        """Get or create a QuotaEnforcer for the given tenant."""
        return QuotaEnforcer(
            limits=self.get_limits(tenant_id),
            state=self.get_state(tenant_id),
            audit=audit,
        )

    def load_from_config(self, config: dict[str, Any]) -> None:
        """Load tenant limits from a config dict.

        Expected format: {"tenants": {"tenant_id": {...limits...}}}
        """
        tenants = config.get("tenants", {})
        for tenant_id, limits_dict in tenants.items():
            self.set_limits(tenant_id, TenantQuotaLimits.model_validate(limits_dict))
