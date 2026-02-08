from __future__ import annotations

from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.registry import CellRegistry
from polisyos.core.security.router import resolve_routing


def test_resolve_routing_accepts_lowercase_tenant_header() -> None:
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=5)
    tenant = TenantSpec(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        name="tenant-a",
        region="us-gov-west-1",
    )
    registry.register_cell(cell)
    registry.register_tenant(tenant, cell.cell_id)

    resolved = resolve_routing(headers={"x-tenant-id": tenant.tenant_id}, registry=registry)
    assert resolved.tenant_id == tenant.tenant_id
    assert resolved.cell_id == cell.cell_id
