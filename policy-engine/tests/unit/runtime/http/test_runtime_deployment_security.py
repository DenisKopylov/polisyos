"""Deployment-owned runtime identity and verifier composition contracts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest


def _deployment_security_module() -> Any:
    from polisyos.runtime.http import deployment_security

    return deployment_security


def _config_mapping(tmp_path: Path) -> dict[str, object]:
    registry_path = tmp_path / "cells.json"
    registry_path.write_text(
        """{
  "cells": [{
    "cell_id": "018f47a0-0000-7000-8000-000000000001",
    "tier": "shared",
    "region": "eu-central-1",
    "max_tenants": 10
  }],
  "tenants": [{
    "tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "name": "Tenant A",
    "tier": "shared",
    "region": "eu-central-1",
    "cell_id": "018f47a0-0000-7000-8000-000000000001"
  }]
}
""",
        encoding="utf-8",
    )
    return {
        "identity_verifier": {
            "issuer": "https://idp.example",
            "audience": "polisyos-runtime",
            "algorithms": ["RS256"],
            "jwks_uri": "https://idp.example/.well-known/jwks.json",
            "allowed_key_ids": ["identity-2026-07"],
            "revoked_key_ids": [],
            "jwks_cache_ttl_seconds": 300,
            "provenance": {
                "source": "deployment_environment",
                "reference": "POLISYOS_RUNTIME_IDENTITY_VERIFIER",
            },
        },
        "step_up_verifier": {
            "issuer": "https://step-up.example",
            "audience": "polisyos-runtime-step-up",
            "algorithms": ["RS256"],
            "jwks_uri": "https://step-up.example/.well-known/jwks.json",
            "allowed_key_ids": ["step-up-2026-07"],
            "revoked_key_ids": [],
            "maximum_age_seconds": 300,
            "clock_skew_seconds": 30,
            "provenance": {
                "source": "deployment_environment",
                "reference": "POLISYOS_RUNTIME_STEP_UP_VERIFIER",
            },
        },
        "cell_registry_path": str(registry_path),
        "opa": {
            "url": "http://opa.example:8181",
            "policy_path": "polisyos/authz/decision",
            "timeout_seconds": 2.0,
        },
        "service_principals": [
            {
                "issuer": "https://idp.example",
                "audience": "polisyos-runtime",
                "subject": "runtime-canary",
                "tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "cell_id": "018f47a0-0000-7000-8000-000000000001",
                "permissions": ["runs.launch", "runs.view"],
            }
        ],
    }


def test_deployment_security_config_is_strict_and_typed(tmp_path: Path) -> None:
    security = _deployment_security_module()
    config = security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))

    assert len(config.service_principals) == 1
    grant = config.service_principals[0]
    assert type(grant) is security.ServicePrincipalGrant
    assert {permission.value for permission in grant.permissions} == {
        "runs.launch",
        "runs.view",
    }
    assert type(config.identity_verifier.provenance) is security.VerifierProvenance
    assert type(config.step_up_verifier.provenance) is security.VerifierProvenance
    runtime = security.build_deployment_security(config)
    assert type(runtime.identity_provider) is security.DeploymentIdentityProvider
    assert runtime.identity_provider.deployment_provenance.reference == (
        "POLISYOS_RUNTIME_IDENTITY_VERIFIER"
    )
    assert runtime.step_up_verifier.deployment_provenance.reference == (
        "POLISYOS_RUNTIME_STEP_UP_VERIFIER"
    )

    malformed = _config_mapping(tmp_path)
    malformed["unexpected"] = True
    with pytest.raises((TypeError, ValueError)):
        security.DeploymentSecurityConfig.from_mapping(malformed)


def test_unknown_service_principal_permission_is_rejected(tmp_path: Path) -> None:
    security = _deployment_security_module()
    raw = _config_mapping(tmp_path)
    principals = raw["service_principals"]
    assert isinstance(principals, list)
    principals[0]["permissions"] = ["runs.launch", "server.unknown"]

    with pytest.raises((TypeError, ValueError), match=r"permission|unknown"):
        security.DeploymentSecurityConfig.from_mapping(raw)


def test_service_principal_resolution_requires_every_identity_dimension(
    tmp_path: Path,
) -> None:
    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    exact = {
        "issuer": "https://idp.example",
        "audience": "polisyos-runtime",
        "subject": "runtime-canary",
        "tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "cell_id": "018f47a0-0000-7000-8000-000000000001",
    }

    resolved = runtime.principal_grants.permissions_for_principal(**exact)
    assert {permission.value for permission in resolved} == {"runs.launch", "runs.view"}

    for field_name in exact:
        mismatched = {**exact, field_name: f"wrong-{field_name}"}
        assert (
            runtime.principal_grants.permissions_for_principal(**mismatched)
            == frozenset()
        )


def test_duplicate_exact_service_principal_is_rejected(tmp_path: Path) -> None:
    security = _deployment_security_module()
    raw = _config_mapping(tmp_path)
    principals = raw["service_principals"]
    assert isinstance(principals, list)
    principals.append(dict(principals[0]))

    with pytest.raises((TypeError, ValueError), match=r"duplicate|principal"):
        security.DeploymentSecurityConfig.from_mapping(raw)


def test_verifier_configuration_rejects_implicit_or_untrusted_key_policy(
    tmp_path: Path,
) -> None:
    security = _deployment_security_module()

    for mutation in (
        {"algorithms": []},
        {"algorithms": ["none"]},
        {"jwks_uri": ""},
        {"allowed_key_ids": ["kid-a"], "revoked_key_ids": ["kid-a"]},
        {"provenance": {"source": "", "reference": ""}},
    ):
        raw = _config_mapping(tmp_path)
        verifier = raw["step_up_verifier"]
        assert isinstance(verifier, dict)
        verifier.update(mutation)
        with pytest.raises((TypeError, ValueError)):
            security.DeploymentSecurityConfig.from_mapping(raw)


def test_deployment_identity_provider_rejects_algorithm_outside_declared_set(
    tmp_path: Path,
) -> None:
    import jwt

    from polisyos.core.security.exceptions import TokenValidationError

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    token = jwt.encode(
        {"sub": "runtime-canary"},
        "test-only-symmetric-key-at-least-32-bytes",
        algorithm="HS256",
        headers={"kid": "identity-2026-07"},
    )

    with pytest.raises(TokenValidationError, match="algorithm"):
        runtime.identity_provider.extract_user_claims(token)


def test_from_env_reads_grants_path_without_absorbing_bearer_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    security = _deployment_security_module()
    config_path = tmp_path / "deployment-security.json"
    import json

    config_path.write_text(json.dumps(_config_mapping(tmp_path)), encoding="utf-8")
    bearer = "secret-canary-bearer-token-must-never-be-retained"
    monkeypatch.setenv("POLISYOS_RUNTIME_SERVICE_PRINCIPAL_GRANTS_PATH", str(config_path))
    monkeypatch.setenv("POLISYOS_RUNTIME_CANARY_BEARER_TOKEN", bearer)

    config = security.DeploymentSecurityConfig.from_env()
    runtime = security.build_deployment_security(config)

    assert bearer not in repr(config)
    assert bearer not in repr(runtime)
    assert not hasattr(config, "bearer_token")
    assert not hasattr(runtime, "bearer_token")


def test_non_development_bootstrap_rejects_protocol_shaped_test_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError

    class _TestVerifier:
        def verify(self, _token: str, _context: object) -> object:
            return object()

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")

    with pytest.raises(
        RuntimeBootstrapError,
        match=r"deployment|verifier|development",
    ):
        create_runtime_api_app(
            cas_root=tmp_path / "cas",
            step_up_verifier=cast("Any", _TestVerifier()),
        )


def test_non_development_bootstrap_requires_exact_deployment_security_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError

    security = _deployment_security_module()
    config = security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    runtime = security.build_deployment_security(config)
    manually_constructed_verifier = security.DeploymentJWTStepUpAssertionVerifier(
        config.step_up_verifier
    )
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")

    with pytest.raises(RuntimeBootstrapError, match=r"RuntimeDeploymentSecurity|bundle"):
        create_runtime_api_app(
            cas_root=tmp_path / "cas",
            identity_provider=runtime.identity_provider,
            cell_registry=runtime.cell_registry,
            opa_client=runtime.opa_client,
            step_up_verifier=manually_constructed_verifier,
        )

    app = create_runtime_api_app(
        cas_root=tmp_path / "bundled-cas",
        deployment_security=runtime,
    )
    assert cast("Any", app).state.runtime_deployment_security is runtime


def test_managed_principal_grants_deny_claim_and_effective_cell_mismatch() -> None:
    from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
    from polisyos.runtime.http.authorization import DeploymentPrincipalGrantResolver
    from polisyos.runtime.http.permissions import RuntimePermission

    resolver = DeploymentPrincipalGrantResolver(
        (
            (
                (
                    "https://idp.example",
                    "polisyos-runtime",
                    "runtime-canary",
                    "tenant-a",
                    "cell-effective",
                ),
                (RuntimePermission.RUNS_LAUNCH,),
            ),
        )
    )
    claims = UserIdentityClaims(
        sub="runtime-canary",
        tenant_id="tenant-a",
        cell_id="cell-claimed",
        roles=frozenset({PolicyOSRole.ADMIN}),
        mfa_verified=True,
        iss="https://idp.example",
        aud="polisyos-runtime",
        exp=4_102_444_800,
        iat=1,
        jti="runtime-canary-token",
    )

    assert resolver.resolve_claim_permissions(
        claims,
        effective_subject=claims.sub,
        effective_tenant_id=claims.tenant_id,
        effective_cell_id="cell-effective",
    ) == frozenset()


def test_action_dependency_uses_exact_service_grant_instead_of_admin_role(
    tmp_path: Path,
) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification,
        ResourceBindingSource,
        ResourceBindingSpec,
        require_action_permission,
    )
    from polisyos.runtime.http.errors import RuntimeHTTPError
    from polisyos.runtime.http.permissions import RuntimePermission

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    claims = UserIdentityClaims(
        sub="runtime-canary",
        tenant_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        cell_id="018f47a0-0000-7000-8000-000000000001",
        roles=frozenset({PolicyOSRole.ADMIN}),
        mfa_verified=True,
        iss="https://idp.example",
        aud="polisyos-runtime",
        exp=4_102_444_800,
        iat=1,
        jti="runtime-canary-token",
    )

    def _request() -> Any:
        state = SimpleNamespace(
            user_claims=claims,
            access_scope=AccessScope.from_user_claims(claims),
        )
        return SimpleNamespace(
            state=state,
            app=SimpleNamespace(
                state=SimpleNamespace(
                    runtime_deployment_principal_grants=runtime.principal_grants
                )
            ),
        )

    binding = ResourceBindingSpec(
        source=ResourceBindingSource.TENANT_COLLECTION,
        resource_kind="runtime.run_collection",
    )
    overbroad_admin_action = require_action_permission(
        RuntimePermission.EVIDENCE_ACQUIRE,
        binding,
    )
    with pytest.raises(RuntimeHTTPError) as exc_info:
        overbroad_admin_action._authorize(_request())
    assert exc_info.value.code == "action_permission_denied"

    granted_action = require_action_permission(RuntimePermission.RUNS_LAUNCH, binding)
    verification = granted_action._authorize(_request())
    assert type(verification) is ActionPermissionVerification
    assert verification.authorization_source == "deployment_service_principal"
    assert {permission.value for permission in verification.granted_permissions} == {
        "runs.launch",
        "runs.view",
    }


def test_action_dependency_denies_managed_admin_when_effective_cell_differs_from_claim(
) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
    from polisyos.runtime.http.authorization import (
        DeploymentPrincipalGrantResolver,
        ResourceBindingSource,
        ResourceBindingSpec,
        require_action_permission,
    )
    from polisyos.runtime.http.errors import RuntimeHTTPError
    from polisyos.runtime.http.permissions import RuntimePermission

    claims = UserIdentityClaims(
        sub="runtime-canary",
        tenant_id="tenant-a",
        cell_id="cell-claimed",
        roles=frozenset({PolicyOSRole.ADMIN}),
        mfa_verified=True,
        iss="https://idp.example",
        aud="polisyos-runtime",
        exp=4_102_444_800,
        iat=1,
        jti="runtime-canary-token",
    )
    effective_scope = replace(
        AccessScope.from_user_claims(claims),
        cell_id="cell-effective",
    )
    effective_cell_id = effective_scope.cell_id
    assert effective_cell_id is not None
    grants = DeploymentPrincipalGrantResolver(
        (
            (
                (
                    claims.iss,
                    claims.aud,
                    claims.sub,
                    claims.tenant_id,
                    effective_cell_id,
                ),
                (RuntimePermission.RUNS_LAUNCH,),
            ),
        )
    )
    request = SimpleNamespace(
        state=SimpleNamespace(
            user_claims=claims,
            authz_effective_scope=effective_scope,
        ),
        app=SimpleNamespace(
            state=SimpleNamespace(runtime_deployment_principal_grants=grants)
        ),
    )
    dependency = require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.run_collection",
        ),
    )

    with pytest.raises(RuntimeHTTPError) as exc_info:
        dependency._authorize(cast("Any", request))
    assert exc_info.value.code == "action_permission_denied"


def test_service_principal_grant_reaches_opa_and_blocks_sibling_mutation(
    tmp_path: Path,
    runtime_api_env: dict[str, Any],
) -> None:
    import json

    from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
    from polisyos.runtime.http.opa_input import (
        RuntimeActionAuthzInput,
        RuntimePrincipalAuthzInput,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _build_secure_client,
        _CaptureOPA,
        _fixture_bearer,
    )

    opa = _CaptureOPA()
    bearer = _fixture_bearer("deployment-service-principal")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    tenant_id = runtime_api_env["tenant_a"]
    provider.put_claim(
        bearer,
        UserIdentityClaims(
            sub="runtime-canary",
            email="runtime-canary@example.invalid",
            tenant_id=tenant_id,
            cell_id=cell.cell_id,
            roles=frozenset({PolicyOSRole.ADMIN}),
            mfa_verified=True,
            iss="https://idp.example",
            aud="polisyos-runtime",
            exp=9_999_999_999,
            iat=1,
            jti="jwt-deployment-service-principal",
        ),
    )
    registry_path = tmp_path / "runtime-cells.json"
    registry_path.write_text(
        json.dumps(
            {
                "cells": [cell.model_dump(mode="json")],
                "tenants": [
                    {
                        "tenant_id": tenant_id,
                        "name": "Runtime tenant",
                        "tier": cell.tier.value,
                        "region": cell.region,
                        "cell_id": cell.cell_id,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    raw = _config_mapping(tmp_path)
    raw["cell_registry_path"] = str(registry_path)
    principals = raw["service_principals"]
    assert isinstance(principals, list)
    principals[0].update(
        {
            "tenant_id": tenant_id,
            "cell_id": cell.cell_id,
            "permissions": ["runs.launch", "runs.view"],
        }
    )
    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(raw)
    )
    cast("Any", client.app).state.runtime_deployment_security = runtime
    cast("Any", client.app).state.runtime_deployment_principal_grants = (
        runtime.principal_grants
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": tenant_id,
    }

    with client:
        allowed = client.post("/api/v1/control/runs/nl", headers=headers, json={})
        safe_read = client.get("/api/v1/control/jobs/missing", headers=headers)
        denied = client.post("/api/v1/control/data/ingest", headers=headers, json={})

    assert allowed.status_code == 422
    assert safe_read.status_code == 404
    assert denied.status_code == 403
    assert denied.json()["code"] == "action_permission_denied"
    assert len(opa.inputs) == 2
    action_payload = opa.inputs[0].to_opa_input()
    read_payload = opa.inputs[1].to_opa_input()
    assert type(opa.inputs[0]) is RuntimeActionAuthzInput
    assert type(opa.inputs[1]) is RuntimePrincipalAuthzInput
    for payload in (action_payload, read_payload):
        assert payload["identity"]["authorization_source"] == ("deployment_service_principal")
        assert payload["identity"]["permissions"] == ["runs.launch", "runs.view"]
