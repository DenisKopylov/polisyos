from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.cell_router_middleware import CellRouterMiddleware


@pytest.fixture
def app_with_router() -> tuple[FastAPI, list[str]]:
    app = FastAPI()
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=50)
    registry.register_cell(cell)

    tenants: list[str] = []
    for index in range(3):
        tenant_id = f"aaaaaaaa-aaaa-aaaa-aaaa-{index:012d}"
        tenant = TenantSpec(
            tenant_id=tenant_id,
            name=f"tenant-{index}",
            region="us-gov-west-1",
        )
        registry.register_tenant(tenant, cell.cell_id)
        tenants.append(tenant_id)

    app.add_middleware(CellRouterMiddleware, registry=registry)

    @app.get("/test")
    async def test_endpoint(request: Request) -> dict[str, str]:
        return {
            "tenant_id": request.state.tenant_id,
            "cell_id": request.state.cell_id,
        }

    return app, tenants


def test_routing_success(app_with_router: tuple[FastAPI, list[str]]) -> None:
    app, tenants = app_with_router
    client = TestClient(app)
    response = client.get("/test", headers={"X-Tenant-ID": tenants[0]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == tenants[0]
    assert "X-Cell-ID" in response.headers


def test_missing_header(app_with_router: tuple[FastAPI, list[str]]) -> None:
    app, _ = app_with_router
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 401
