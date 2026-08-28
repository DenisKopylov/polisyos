"""Red-first HTTP boundary test for the DS17 confidence-ledger risk-spend route."""

from __future__ import annotations

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi.routing import APIRoute
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.permissions import RuntimePermission
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)

_PATH = "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
_DYNAMIC_PATH = "/api/v1/exports/governed-projections/{projection_id}"


def _secure_client(runtime_api_env, *, role: PolicyOSRole, suffix: str):
    """Create one tenant-bound caller for the protected-operation assertion."""
    bearer = _fixture_bearer(suffix)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-{suffix}",
            roles=frozenset({role}),
        ),
    )
    return client, {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }


def test_confidence_ledger_risk_spend_operation_is_typed_and_protected(
    runtime_api_env,
) -> None:
    """Require the static reviewer operation; C00 observes its dynamic-route 422 red."""
    analyst, analyst_headers = _secure_client(
        runtime_api_env,
        role=PolicyOSRole.ANALYST,
        suffix="ds17-analyst",
    )
    viewer, viewer_headers = _secure_client(
        runtime_api_env,
        role=PolicyOSRole.VIEWER,
        suffix="ds17-viewer",
    )
    response = analyst.get(_PATH, headers=analyst_headers)

    assert response.status_code == 200, (
        "DS17 C02 missing: the typed review-protected confidence-ledger risk-spend "
        f"operation is absent at {_PATH}; received HTTP {response.status_code}: {response.text}"
    )

    routes = [route for route in analyst.app.routes if isinstance(route, APIRoute)]
    static_index, static_route = next(
        (index, route)
        for index, route in enumerate(routes)
        if route.path == _PATH and "GET" in route.methods
    )
    dynamic_index, _ = next(
        (index, route)
        for index, route in enumerate(routes)
        if route.path == _DYNAMIC_PATH and "GET" in route.methods
    )
    dependency = get_route_action_permission_dependency(static_route)
    assert static_index < dynamic_index
    assert dependency.requirement.permission is RuntimePermission.RUNS_REVIEW
    assert dependency.requirement.resource_binding.source is ResourceBindingSource.TENANT_COLLECTION

    payload = response.json()
    assert payload["projection_id"] == "confidence-ledger-risk-spend"
    assert payload["intended_audience"] == "REVIEWER"
    assert payload["availability"] in {"available", "source_blocked"}

    denied = viewer.get(_PATH, headers=viewer_headers)
    assert denied.status_code == 403
    assert denied.json()["code"] == "action_permission_denied"
