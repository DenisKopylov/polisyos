from __future__ import annotations

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

try:  # pragma: no cover - optional dependency guard
    import jwt as _jwt  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("PyJWT is not installed", allow_module_level=True)

from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.exceptions import TokenValidationError
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import create_runtime_api_app


class _AllowOPA:
    async def check(self, authz_input):  # noqa: ANN001
        del authz_input
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _DenyOPA:
    async def check(self, authz_input):  # noqa: ANN001
        del authz_input
        return AuthzResult(
            decision=AuthzDecision.DENY,
            policy="polisyos/authz/decision",
            reasons=("DENY_TEST",),
        )


class _IdentityProvider:
    def __init__(self, claims_by_token: dict[str, UserIdentityClaims]) -> None:
        self._claims_by_token = claims_by_token

    def put_claim(self, token: str, claims: UserIdentityClaims) -> None:
        self._claims_by_token[token] = claims

    def extract_user_claims(self, jwt_token: str, *, expected_cell_id: str | None = None):
        claim = self._claims_by_token.get(jwt_token)
        if claim is None:
            raise TokenValidationError("invalid token")
        if expected_cell_id and claim.cell_id and claim.cell_id != expected_cell_id:
            raise TokenValidationError("cell binding mismatch")
        return claim


def _claims(*, tenant_id: str, cell_id: str, jti: str) -> UserIdentityClaims:
    return UserIdentityClaims(
        sub="user-1",
        email="user@example.com",
        tenant_id=tenant_id,
        cell_id=cell_id,
        roles=frozenset({PolicyOSRole.ANALYST}),
        mfa_verified=True,
        iss="https://idp.example/realms/polisyos",
        aud="polisyos-web",
        exp=9_999_999_999,
        iat=1,
        jti=jti,
    )


def _build_secure_client(
    runtime_api_env,
    *,
    opa_client,
    claims_by_token: dict[str, UserIdentityClaims],
):
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=50)
    registry.register_cell(cell)

    for tenant_id in (runtime_api_env["tenant_a"], runtime_api_env["tenant_b"]):
        registry.register_tenant(
            TenantSpec(
                tenant_id=tenant_id,
                name=f"tenant-{tenant_id[:8]}",
                region="us-gov-west-1",
            ),
            cell.cell_id,
        )

    provider = _IdentityProvider(claims_by_token=claims_by_token)
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        enable_security_middlewares=True,
        identity_provider=provider,
        cell_registry=registry,
        opa_client=opa_client,
    )
    return TestClient(app), cell, provider


def test_runtime_api_allows_tenant_scoped_access(runtime_api_env) -> None:
    claims_token = "token-a"
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_token,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_token}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 200


def test_runtime_api_denies_cross_tenant_run_access(runtime_api_env) -> None:
    claims_token = "token-b"
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_token,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-b",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_token}",
            "X-Tenant-ID": runtime_api_env["tenant_b"],
        },
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["code"] == "run_tenant_mismatch"


def test_runtime_api_authz_deny_blocks_endpoint(runtime_api_env) -> None:
    claims_token = "token-a"
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_DenyOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_token,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-deny",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_token}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"] == "authorization_denied"


def test_runtime_api_denies_cross_tenant_artifact_access(runtime_api_env) -> None:
    claims_token = "token-b"
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_token,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-b-artifact",
        ),
    )

    response = client.get(
        f"/api/v1/artifacts/{runtime_api_env['workflow_report_artifact_id']}",
        headers={
            "Authorization": f"Bearer {claims_token}",
            "X-Tenant-ID": runtime_api_env["tenant_b"],
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "artifact_tenant_mismatch"


def test_runtime_api_denies_unscoped_artifact_access(runtime_api_env) -> None:
    claims_token = "token-a"
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_token,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-unscoped-artifact",
        ),
    )

    response = client.get(
        f"/api/v1/artifacts/{runtime_api_env['root_artifact_id']}",
        headers={
            "Authorization": f"Bearer {claims_token}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "artifact_tenant_unscoped"
