from __future__ import annotations

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

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


def test_routing_accepts_lowercase_header(app_with_router: tuple[FastAPI, list[str]]) -> None:
    app, tenants = app_with_router
    client = TestClient(app)
    response = client.get("/test", headers={"x-tenant-id": tenants[0]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == tenants[0]


def test_missing_header(app_with_router: tuple[FastAPI, list[str]]) -> None:
    app, _ = app_with_router
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 401


def test_routing_rejects_authenticated_tenant_mismatch(
    app_with_router: tuple[FastAPI, list[str]],
) -> None:
    app, tenants = app_with_router

    @app.middleware("http")
    async def inject_claim_tenant(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.authenticated_tenant_id = tenants[0]
        return await call_next(request)

    client = TestClient(app)
    response = client.get("/test", headers={"X-Tenant-ID": tenants[1]})
    assert response.status_code == 403
    assert response.json()["error"] == "tenant_binding_mismatch"


def test_cell_router_middleware_accepts_injected_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "polisyos.runtime.http.cell_router_middleware._default_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    middleware = CellRouterMiddleware(
        FastAPI(),
        registry=CellRegistry(),
        metrics=object(),  # type: ignore[arg-type]
    )

    assert middleware._metrics is not None
