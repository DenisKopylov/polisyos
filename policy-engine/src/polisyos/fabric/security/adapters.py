"""Fabric adapter over the canonical core security context contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.security import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)


@dataclass(frozen=True)
class FabricSecurityContext:
    """Security context projected into Fabric data-access decisions."""

    tenant_id: str | None
    cell_id: str | None
    access_scope: Any | None

    @property
    def is_tenant_scoped(self) -> bool:
        """Return whether Fabric is executing inside a tenant scope."""
        return self.tenant_id is not None


@dataclass(frozen=True)
class FabricSecurityAdapter:
    """Package-local access point for canonical core security context."""

    def current_context(self) -> FabricSecurityContext:
        """Return the current core security context in Fabric terms."""
        return FabricSecurityContext(
            tenant_id=get_current_tenant_id_or_none(),
            cell_id=get_current_cell_id(),
            access_scope=get_current_access_scope_or_none(),
        )


def get_fabric_security_adapter() -> FabricSecurityAdapter:
    """Return the default Fabric security adapter."""
    return FabricSecurityAdapter()


__all__ = [
    "FabricSecurityAdapter",
    "FabricSecurityContext",
    "get_fabric_security_adapter",
]
