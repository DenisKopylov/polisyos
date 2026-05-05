from __future__ import annotations

import pytest
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.exceptions import CellCapacityError, TenantNotFoundError
from polisyos.core.security.registry import CellRegistry


def test_register_and_resolve_tenant() -> None:
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=2)
    registry.register_cell(cell)

    tenant = TenantSpec(name="tenant-a", region="us-gov-west-1")
    registry.register_tenant(tenant, cell.cell_id)

    resolved = registry.resolve(tenant.tenant_id)
    assert resolved.cell_id == cell.cell_id
    assert resolved.cell_tier == cell.tier.value


def test_capacity_guard() -> None:
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=1)
    registry.register_cell(cell)

    registry.register_tenant(TenantSpec(name="a", region="us-gov-west-1"), cell.cell_id)
    with pytest.raises(CellCapacityError):
        registry.register_tenant(TenantSpec(name="b", region="us-gov-west-1"), cell.cell_id)


def test_unknown_tenant_raises() -> None:
    registry = CellRegistry()
    with pytest.raises(TenantNotFoundError):
        registry.resolve("11111111-1111-1111-1111-111111111111")
