from __future__ import annotations

import asyncio

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.exceptions import TokenValidationError
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import (
    _assert_runtime_security_middleware_order,
    create_runtime_api_app,
)


class _AllowOPA:
    async def check(self, authz_input):
        del authz_input
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _DenyOPA:
    async def check(self, authz_input):
        del authz_input
        return AuthzResult(
            decision=AuthzDecision.DENY,
            policy="polisyos/authz/decision",
            reasons=("DENY_TEST",),
        )


class _SelectiveReviewOPA:
    async def check(self, authz_input):
        kind = getattr(authz_input, "resource_kind", "")
        if str(kind).endswith("message.cursor.update"):
            return AuthzResult(
                decision=AuthzDecision.DENY,
                policy="polisyos/authz/decision",
                reasons=("MESSAGE_DENIED",),
            )
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _SlowOPA:
    async def check(self, authz_input):
        del authz_input
        await asyncio.sleep(0.2)
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


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


def _fixture_bearer(suffix: str) -> str:
    return f"token-{suffix}"


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
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 200


def test_runtime_api_denies_cross_tenant_run_access(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("b")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-b",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_b"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    payload = response.json()
    assert payload["code"] == "run_tenant_mismatch"


def test_runtime_api_authz_deny_blocks_endpoint(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_DenyOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-deny",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    assert response.json()["error"] == "authorization_denied"


def test_runtime_api_authz_timeout_returns_gateway_timeout(
    monkeypatch: pytest.MonkeyPatch,
    runtime_api_env,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_OPA_TIMEOUT_SECONDS", "0.05")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_SlowOPA(),
        claims_by_token={},
    )
    claims_bearer = _fixture_bearer("a-timeout")
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-timeout",
        ),
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )

    assert response.status_code == 504
    assert response.json()["code"] == "authz_dependency_timeout"


def test_runtime_api_denies_cross_tenant_artifact_access(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("b")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-b-artifact",
        ),
    )

    response = client.get(
        f"/api/v1/artifacts/{runtime_api_env['workflow_report_artifact_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_b"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    assert response.json()["code"] == "artifact_tenant_mismatch"


def test_runtime_api_denies_unscoped_artifact_access(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-unscoped-artifact",
        ),
    )

    response = client.get(
        f"/api/v1/artifacts/{runtime_api_env['root_artifact_id']}",
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )
    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    assert response.json()["code"] == "artifact_tenant_unscoped"


def test_runtime_api_rejects_missing_claims_fail_closed(runtime_api_env) -> None:
    client, _, _ = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )

    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}",
        headers={"X-Tenant-ID": runtime_api_env["tenant_a"]},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "missing_bearer_token"


def test_runtime_api_auth_me_requires_claims_without_explicit_fixture_flag(runtime_api_env) -> None:
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        allow_fixture_identity=False,
    )
    client = TestClient(app)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "missing_access_scope"


def test_runtime_api_cross_tenant_compare_requires_explicit_capability(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-compare",
        ),
    )

    response = client.get(
        (
            f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}"
            f"/compare/{runtime_api_env['cross_tenant_run_id']}"
        ),
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "cross_tenant_compare_forbidden"


def test_runtime_security_middleware_order_guard_detects_reordering(runtime_api_env) -> None:
    client, _, _ = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    app = client.app

    _assert_runtime_security_middleware_order(
        app,
        security_middlewares_enabled=True,
    )

    app.user_middleware[0], app.user_middleware[1] = app.user_middleware[1], app.user_middleware[0]
    with pytest.raises(RuntimeError):
        _assert_runtime_security_middleware_order(
            app,
            security_middlewares_enabled=True,
        )


def test_review_websocket_rejects_anonymous_connect(runtime_api_env) -> None:
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        allow_fixture_identity=False,
    )
    client = TestClient(app)

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(
            f"/api/v1/review/live?channel=review.presence&review_id=run:{runtime_api_env['core_run_id']}:governance"
        ),
    ):
        pass

    assert exc.value.code == 4401


def test_review_websocket_rechecks_message_authorization(runtime_api_env) -> None:
    claims_bearer = _fixture_bearer("a")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_SelectiveReviewOPA(),
        claims_by_token={},
    )
    provider.put_claim(
        claims_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-a-review",
        ),
    )

    with client.websocket_connect(
        (
            f"/api/v1/review/live?channel=review.cursor"
            f"&review_id=run:{runtime_api_env['core_run_id']}:governance"
        ),
        headers={
            "Authorization": f"Bearer {claims_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    ) as websocket:
        assert websocket.receive_json()["type"] == "cursor.snapshot"
        websocket.send_json({"type": "cursor.update", "x": 0.2, "y": 0.4})
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_json()

    assert exc.value.code == 4403
