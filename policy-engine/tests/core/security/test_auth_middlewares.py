from __future__ import annotations

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

try:  # pragma: no cover - optional dependency guard
    import jwt as _jwt  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("PyJWT is not installed", allow_module_level=True)

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.delegation import DelegationTokenManager
from polisyos.core.security.exceptions import MFARequiredError
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole, UserIdentityClaims
from polisyos.runtime.http.authz_middleware import AuthzMiddleware
from polisyos.runtime.http.jwt_auth_middleware import JWTAuthMiddleware


class _FakeIdentityProvider:
    def __init__(self, claims: UserIdentityClaims) -> None:
        self._claims = claims

    def extract_user_claims(self, jwt_token: str, *, expected_cell_id: str | None = None):
        del jwt_token
        del expected_cell_id
        return self._claims


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


class _AllowOPAWithColumns:
    async def check(self, authz_input):  # noqa: ANN001
        del authz_input
        return AuthzResult(
            decision=AuthzDecision.ALLOW,
            policy="polisyos/authz/decision",
            audit_entry={"allowed_columns": ["claim_id", "confidence"]},
        )


class _MfaIdentityProvider:
    def extract_user_claims(self, jwt_token: str, *, expected_cell_id: str | None = None):
        del jwt_token
        del expected_cell_id
        raise MFARequiredError("MFA is required")


def _claims(tenant_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") -> UserIdentityClaims:
    return UserIdentityClaims(
        sub="user-1",
        email="user@example.com",
        tenant_id=tenant_id,
        cell_id="cell-a",
        roles=frozenset({PolicyOSRole.ANALYST}),
        mfa_verified=True,
        iss="https://idp.example/realms/polisyos",
        aud="polisyos-web",
        exp=9_999_999_999,
        iat=1,
        jti="jwt-1",
    )


def test_jwt_middleware_sets_authenticated_scope() -> None:
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware, identity_provider=_FakeIdentityProvider(_claims()))

    @app.get("/secure")
    async def secure(request: Request) -> dict[str, str]:
        return {
            "tenant": request.state.authenticated_tenant_id,
            "scope_tenant": request.state.access_scope.tenant_id,
        }

    client = TestClient(app)
    response = client.get("/secure", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["tenant"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_jwt_middleware_rejects_tenant_header_mismatch() -> None:
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware, identity_provider=_FakeIdentityProvider(_claims()))

    @app.get("/secure")
    async def secure() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    response = client.get(
        "/secure",
        headers={
            "Authorization": "Bearer token",
            "X-Tenant-ID": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"] == "tenant_binding_mismatch"


def test_jwt_middleware_returns_403_when_mfa_required() -> None:
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware, identity_provider=_MfaIdentityProvider())

    @app.get("/secure")
    async def secure() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    response = client.get("/secure", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403
    assert response.json()["error"] == "mfa_required"


def test_authz_middleware_allows_valid_delegation() -> None:
    app = FastAPI()
    manager = DelegationTokenManager(signing_key="test-secret", ttl_seconds=60)
    issuer = "spiffe://polisyos.io/cell/cell-a/svc/scientist"
    audience = "spiffe://polisyos.io/cell/cell-a/svc/fabric"

    scope = AccessScope(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
        principal_type="user",
        user_sub="user-1",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
        jwt_jti="jwt-1",
    )
    token = manager.issue_token(scope=scope, issuer=issuer, audience=audience)

    app.add_middleware(
        AuthzMiddleware,
        opa_client=_AllowOPA(),
        enforce=True,
        delegation_manager=manager,
        delegation_header="x-policyos-context",
        mtls_spiffe_header="l5d-client-id",
        trusted_delegators=frozenset({issuer}),
        service_spiffe_id=audience,
    )

    @app.get("/internal/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    response = client.get(
        "/internal/ping",
        headers={
            "X-PolicyOS-Context": token,
            "l5d-client-id": issuer,
        },
    )
    assert response.status_code == 200


def test_authz_middleware_rejects_deny_decision() -> None:
    app = FastAPI()
    app.add_middleware(AuthzMiddleware, opa_client=_DenyOPA(), enforce=True)

    @app.get("/secure")
    async def secure() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    response = client.get("/secure")
    assert response.status_code == 403
    assert response.json()["error"] in {"missing_access_scope", "authorization_denied"}


def test_authz_middleware_exposes_allowed_columns_on_request_state() -> None:
    app = FastAPI()
    app.add_middleware(
        JWTAuthMiddleware,
        identity_provider=_FakeIdentityProvider(_claims()),
    )
    app.add_middleware(AuthzMiddleware, opa_client=_AllowOPAWithColumns(), enforce=True)

    @app.get("/api/v1/data/claims")
    async def data_endpoint(request: Request) -> dict[str, list[str]]:
        columns = list(getattr(request.state, "authz_allowed_columns", ()))
        return {"allowed_columns": columns}

    client = TestClient(app)
    response = client.get(
        "/api/v1/data/claims",
        headers={
            "Authorization": "Bearer token",
            "X-Tenant-ID": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        },
    )
    assert response.status_code == 200
    assert response.json()["allowed_columns"] == ["claim_id", "confidence"]
