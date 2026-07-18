from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi.testclient import TestClient
    from starlette.requests import Request
    from starlette.websockets import WebSocketDisconnect
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.execution_policy import RuntimeBootstrapError
from polisyos.runtime.http.security import build_fixture_identity_claims
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)


@pytest.mark.parametrize("profile", ["research", "governed", "production"])
@pytest.mark.parametrize("configuration", ["explicit", "environment"])
def test_fixture_identity_is_refused_outside_development_profile(
    profile: str,
    configuration: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", profile)
    kwargs: dict[str, Any] = {}
    if configuration == "explicit":
        kwargs["allow_fixture_identity"] = True
    else:
        monkeypatch.setenv("POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY", "1")

    with pytest.raises(RuntimeBootstrapError, match="fixture identity"):
        create_runtime_api_app(cas_root=tmp_path / ".polisyos", **kwargs)


def test_fixture_identity_remains_explicitly_available_in_development_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    app = create_runtime_api_app(
        cas_root=tmp_path / ".polisyos",
        allow_fixture_identity=True,
    )

    response = TestClient(app).get("/api/v1/auth/me")

    assert response.status_code == 200, response.json()
    assert response.json()["user_id"] == "fixture-analyst"


def test_identity_provider_cannot_return_fixture_identity(runtime_api_env) -> None:
    bearer = _fixture_bearer("provider-returned-fixture")
    client, _cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(bearer, build_fixture_identity_claims())

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {bearer}"},
    )

    assert response.status_code == 401, response.json()
    assert response.json()["code"] == "fixture_identity_forbidden"


def test_review_websocket_rejects_provider_returned_fixture_identity(
    runtime_api_env,
) -> None:
    bearer = _fixture_bearer("review-provider-returned-fixture")
    client, _cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(bearer, build_fixture_identity_claims())

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(
            "/api/v1/review/live?channel=review.presence&review_id=run:fixture:governance",
            headers={"Authorization": f"Bearer {bearer}"},
        ),
    ):
        pass

    assert exc.value.code == 4401
    assert exc.value.reason == "Fixture identity is development-only"


def test_auth_me_does_not_synthesize_viewer_role_for_verified_empty_roles(
    runtime_api_env,
) -> None:
    bearer = _fixture_bearer("verified-empty-roles")
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
            jti="jwt-verified-empty-roles",
            roles=frozenset(),
        ),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
        },
    )

    assert response.status_code == 200, response.json()
    assert response.json()["roles"] == []
    assert response.json()["permissions"] == []


def test_auth_me_without_verified_claims_is_401_even_when_fallback_was_requested(
    runtime_api_env,
) -> None:
    from polisyos.runtime.http.errors import RuntimeHTTPError
    from polisyos.runtime.http.routes.auth import get_auth_me
    from polisyos.runtime.http.security import RuntimeSecurityConfig

    client, _cell, _provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    app = client.app
    security = app.state.runtime_security
    assert isinstance(security, RuntimeSecurityConfig)
    fallback_requested = replace(security, allow_fixture_identity=True)
    app.state.runtime_security = fallback_requested
    app.state.runtime_container.runtime_security = fallback_requested
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/api/v1/auth/me",
            "raw_path": b"/api/v1/auth/me",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 443),
            "app": app,
        }
    )

    with pytest.raises(RuntimeHTTPError) as exc:
        get_auth_me(request)

    assert exc.value.status_code == 401
    assert exc.value.code == "missing_user_claims"


def test_fixture_identity_cannot_request_non_development_execution_profile(
    runtime_api_env,
) -> None:
    response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            "execution_profile": "research",
        },
    )

    assert response.status_code == 422, response.json()
    assert response.json()["code"] == "fixture_identity_profile_forbidden"


def test_genuine_identity_is_not_classified_as_fixture() -> None:
    from polisyos.runtime.http.security import is_fixture_identity_claims

    claims = _claims(
        tenant_id="tenant-a",
        cell_id="cell-a",
        jti="genuine-jti",
        roles=frozenset({PolicyOSRole.ADMIN}),
    )

    assert is_fixture_identity_claims(claims) is False


def test_shadow_mode_safe_read_never_synthesizes_service_identity() -> None:
    from types import SimpleNamespace

    from polisyos.runtime.http.authz_middleware import AuthzMiddleware

    async def _app(scope, receive, send) -> None:
        del scope, receive, send

    middleware = AuthzMiddleware(
        _app,
        runtime_app=SimpleNamespace(router=SimpleNamespace(routes=[])),
        enforce=False,
        shadow_mode=True,
    )
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/api/v1/runs",
            "raw_path": b"/api/v1/runs",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 443),
        }
    )

    scope, provenance, denial = middleware._resolve_effective_scope(
        request,
        peer_spiffe_id="spiffe://unverified/peer",
        unsafe=False,
    )

    assert scope is None
    assert provenance != "shadow_service_fallback"
    assert denial is None
