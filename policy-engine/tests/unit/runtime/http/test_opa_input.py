from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.permissions import permissions_for_roles

_VIEWER_BEARER = "viewer-bearer-1"


class _IdentityProvider:
    def __init__(self, claims: UserIdentityClaims) -> None:
        self._claims = claims

    def extract_user_claims(
        self,
        jwt_token: str,
        *,
        expected_cell_id: str | None = None,
    ) -> UserIdentityClaims:
        if jwt_token != _VIEWER_BEARER or (
            expected_cell_id is not None and expected_cell_id != self._claims.cell_id
        ):
            raise ValueError("test identity does not match the requested cell")
        return self._claims


class _CaptureOPA:
    def __init__(self) -> None:
        self.inputs: list[Any] = []

    async def check(self, authz_input: Any) -> AuthzResult:
        self.inputs.append(authz_input)
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="test/allow")


def test_caller_permission_header_cannot_expand_opa_principal_projection(runtime_api_env) -> None:
    tenant_id = str(runtime_api_env["tenant_a"])
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=10)
    registry.register_cell(cell)
    for candidate_tenant in (tenant_id, str(runtime_api_env["tenant_b"])):
        registry.register_tenant(
            TenantSpec(
                tenant_id=candidate_tenant,
                name=f"tenant-{candidate_tenant[:8]}",
                region="us-gov-west-1",
            ),
            cell.cell_id,
        )

    roles = frozenset({PolicyOSRole.VIEWER})
    claims = UserIdentityClaims(
        sub="viewer-opa-input",
        tenant_id=tenant_id,
        cell_id=cell.cell_id,
        roles=roles,
        mfa_verified=True,
        iss="https://idp.example",
        aud="polisyos-runtime",
        exp=4_102_444_800,
        iat=1,
        jti="jwt-viewer-opa-input",
    )
    opa = _CaptureOPA()
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        enable_security_middlewares=True,
        identity_provider=_IdentityProvider(claims),
        cell_registry=registry,
        opa_client=opa,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runs/batch",
            headers={
                "Authorization": f"Bearer {_VIEWER_BEARER}",
                "X-Tenant-ID": tenant_id,
                "X-PolicyOS-Permissions": "platform.admin,runs.production_approval.create",
                "X-PolicyOS-Authorization-Source": "caller-asserted",
            },
            json={"run_ids": [runtime_api_env["core_run_id"]]},
        )

    assert response.status_code == 200, response.text
    assert len(opa.inputs) == 1
    payload = opa.inputs[0].to_opa_input()
    assert payload["action"] == {"permission": "runs.batch.read"}
    assert payload["identity"]["authorization_source"] == "canonical_role_permissions"
    assert set(payload["identity"]["permissions"]) == {
        permission.value for permission in permissions_for_roles(roles)
    }
    assert "platform.admin" not in payload["identity"]["permissions"]
    assert "runs.production_approval.create" not in payload["identity"]["permissions"]
