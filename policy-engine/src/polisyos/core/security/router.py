"""Framework-agnostic routing helpers for tenant-aware request handling."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from polisyos.core.security.exceptions import TenantIsolationError
from polisyos.core.security.registry import CellRegistry, CellResolution

TENANT_HEADER = "X-Tenant-ID"


@dataclass(frozen=True)
class RoutingResult:
    tenant_id: str
    cell_id: str
    cell_slug: str
    cell_tier: str


class MissingTenantHeaderError(TenantIsolationError):
    """Raised when request has no tenant header."""


class TenantRoutingError(TenantIsolationError):
    """Raised when tenant cannot be routed to a cell."""


def resolve_routing(
    *,
    headers: Mapping[str, str],
    registry: CellRegistry,
    tenant_header: str = TENANT_HEADER,
) -> RoutingResult:
    tenant_id = headers.get(tenant_header) or headers.get(tenant_header.lower())
    if not tenant_id:
        raise MissingTenantHeaderError(f"Missing required header: {tenant_header}")

    try:
        resolution: CellResolution = registry.resolve(tenant_id)
    except TenantIsolationError as exc:
        raise TenantRoutingError(str(exc)) from exc

    return RoutingResult(
        tenant_id=resolution.tenant_id,
        cell_id=resolution.cell_id,
        cell_slug=resolution.cell_slug,
        cell_tier=resolution.cell_tier,
    )


__all__ = [
    "TENANT_HEADER",
    "RoutingResult",
    "MissingTenantHeaderError",
    "TenantRoutingError",
    "resolve_routing",
]
