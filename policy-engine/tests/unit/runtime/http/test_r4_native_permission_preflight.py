"""Cheap action-permission admission checks for the native cancellation fixture."""

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.requests import Request

from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.runtime.http import deployment_security
from polisyos.runtime.http.authorization import (
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    ActionPermissionVerification,
)
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.routes.control import _CANCEL_JOB_AUTHZ
from tests._helpers.runtime_http import deployment_security_config_mapping


def test_r4_cancellation_action_permission_uses_exact_managed_principal(tmp_path: Path) -> None:
    """Run the real action owner only; this is not an OPA or cancellation proof."""
    config = deployment_security_config_mapping(tmp_path)
    principal = config["service_principals"][0]
    principal["subject"] = "r4-native-fixture"
    tenant = principal["tenant_id"]
    cell = principal["cell_id"]
    claims = UserIdentityClaims(
        sub="r4-native-fixture",
        tenant_id=tenant,
        cell_id=cell,
        roles=frozenset({PolicyOSRole.ADMIN}),
        mfa_verified=True,
        iss="https://idp.example",
        aud="polisyos-runtime",
        exp=9_999_999_999,
        iat=1,
        jti="r4-native-permission-preflight",
    )
    app = Starlette()

    def authorize(permissions: list[str], actual_claims: UserIdentityClaims):
        principal["permissions"] = permissions
        runtime = deployment_security.build_deployment_security(
            deployment_security.DeploymentSecurityConfig.from_mapping(config)
        )
        app.state.runtime_deployment_principal_grants = runtime.principal_grants
        request = Request({"type": "http", "app": app, "state": {}})
        request.state.user_claims = actual_claims
        return _CANCEL_JOB_AUTHZ._authorize(request)

    allowed = ["runs.launch", "runs.view", "jobs.cancel"]
    result = authorize(allowed, claims)
    assert type(result) is ActionPermissionVerification
    assert result.subject == claims.sub
    assert result.authorization_source == DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE
    assert RuntimePermission.JOBS_CANCEL in result.granted_permissions
    for permissions, actual in (
        (["runs.launch", "runs.view"], claims),
        (allowed, claims.model_copy(update={"iss": "https://wrong.example"})),
        (allowed, claims.model_copy(update={"cell_id": "foreign-cell"})),
        (allowed, claims.model_copy(update={"sub": "unmanaged-subject"})),
    ):
        with pytest.raises(RuntimeHTTPError) as denied:
            authorize(permissions, actual)
        assert denied.value.code == "action_permission_denied"
