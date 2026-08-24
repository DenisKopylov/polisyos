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


class _AlwaysTrueReplayStore:
    def consume_step_up_assertion(self, *, assertion_id: str, expires_at: int) -> bool:
        del assertion_id, expires_at
        return True


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


def _config_mapping_with_human_decision_custody(
    tmp_path: Path,
) -> dict[str, object]:
    from polisyos.core.artifacts.signing import KeyPair

    tmp_path.mkdir(parents=True, exist_ok=True)
    pair = KeyPair.generate()
    private_key_path = tmp_path / "human-decision-custody.pem"
    public_key_path = tmp_path / "human-decision-custody.pub"
    private_key_path.write_bytes(pair.private_pem())
    public_key_path.write_bytes(pair.public_pem())
    raw = _config_mapping(tmp_path)
    raw["human_decision_custody"] = {
        "signer_identity": "service://runtime/human-decision-custody",
        "private_key_path": str(private_key_path),
        "public_key_path": str(public_key_path),
        "verifier_epoch": "ds9-deployment-epoch",
        "provenance": {
            "source": "deployment_environment",
            "reference": "POLISYOS_RUNTIME_HUMAN_DECISION_CUSTODY",
        },
        "revoked_key_ids": [],
        "trusted_producers": [
            {
                "artifact_kind": "runtime_quality.agent_action_human_decision",
                "schema_name": "polisyos.runtime.HumanDecisionRecord",
                "schema_version": "2.0",
                "signer_identity": "service://runtime/human-decision-custody",
                "public_key_path": str(public_key_path),
            }
        ],
    }
    return raw


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


def test_human_decision_custody_is_typed_unavailable_when_unconfigured(
    tmp_path: Path,
) -> None:
    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )

    custody = runtime.human_decision_custody
    assert type(custody) is security.DeploymentHumanDecisionCustody
    assert custody.available is False
    assert custody.unavailability_code == "DS9-DECISION-PRODUCER-MISSING"
    assert custody.signer is None
    assert custody.verifier is None


def test_human_decision_custody_rejects_private_public_key_mismatch(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.signing import KeyPair

    security = _deployment_security_module()
    raw = _config_mapping_with_human_decision_custody(tmp_path)
    custody = raw["human_decision_custody"]
    assert isinstance(custody, dict)
    mismatched_public_path = tmp_path / "mismatched-custody.pub"
    mismatched_public_path.write_bytes(KeyPair.generate().public_pem())
    custody["public_key_path"] = str(mismatched_public_path)

    with pytest.raises(ValueError, match=r"private|public|key"):
        security.build_deployment_security(security.DeploymentSecurityConfig.from_mapping(raw))


@pytest.mark.parametrize(
    "mutation",
    [
        "component",
        "signer",
        "verifier",
        "trust_policy",
        "strict_identity",
        "signer_build_statement",
        "trusted_key_map",
    ],
)
def test_human_decision_custody_is_part_of_factory_attestation(
    tmp_path: Path,
    mutation: str,
) -> None:
    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(
            _config_mapping_with_human_decision_custody(tmp_path / "first")
        )
    )
    replacement = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(
            _config_mapping_with_human_decision_custody(tmp_path / "second")
        )
    )
    if mutation == "component":
        object.__setattr__(
            runtime,
            "human_decision_custody",
            replacement.human_decision_custody,
        )
    elif mutation == "signer":
        object.__setattr__(
            runtime.human_decision_custody,
            "signer",
            replacement.human_decision_custody.signer,
        )
    elif mutation == "verifier":
        object.__setattr__(
            runtime.human_decision_custody,
            "verifier",
            replacement.human_decision_custody.verifier,
        )
    elif mutation == "trust_policy":
        object.__setattr__(
            runtime.human_decision_custody,
            "trust_policy",
            replacement.human_decision_custody.trust_policy,
        )
    elif mutation == "strict_identity":
        object.__setattr__(
            runtime.human_decision_custody.verifier,
            "_strict_identity",
            False,
        )
    elif mutation == "signer_build_statement":
        object.__setattr__(
            runtime.human_decision_custody.signer,
            "build_statement",
            lambda *_args, **_kwargs: object(),
        )
    else:
        object.__setattr__(
            runtime.human_decision_custody.verifier,
            "_trusted_keys",
            {},
        )

    with pytest.raises(TypeError, match=r"factory|attest|bundle"):
        security.require_factory_produced_deployment_security(runtime)


def test_human_decision_custody_signs_and_strictly_verifies_exact_cas(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(
            _config_mapping_with_human_decision_custody(tmp_path)
        )
    )
    custody = runtime.human_decision_custody
    assert custody.signer is not None
    assert custody.verifier is not None
    assert custody.signer_identity is not None
    store = FileSystemCAS(tmp_path / "custody-cas")
    artifact_ref = store.put_bytes(
        b"custodied human decision",
        ArtifactWriteOptions(
            kind="test.human_decision_custody",
            media_type="application/octet-stream",
        ),
    )

    store.sign_artifact(
        artifact_ref.artifact_id,
        custody.signer,
        signer_identity=custody.signer_identity,
    )
    result = store.verify_signature(
        artifact_ref.artifact_id,
        custody.verifier,
        strict_identity=True,
    )

    assert result.ok is True
    assert result.signer_identity == custody.signer_identity
    assert result.expected_identity == custody.signer_identity


def test_human_decision_custody_rejects_revoked_active_signer(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.signing import Ed25519Signer

    security = _deployment_security_module()
    raw = _config_mapping_with_human_decision_custody(tmp_path)
    custody = raw["human_decision_custody"]
    assert isinstance(custody, dict)
    signer = Ed25519Signer.from_path(Path(str(custody["private_key_path"])))
    custody["revoked_key_ids"] = [signer.key_id]

    with pytest.raises(ValueError, match="revoked"):
        security.build_deployment_security(security.DeploymentSecurityConfig.from_mapping(raw))


def test_runtime_deployment_security_cannot_mix_collaborators_across_documents(
    tmp_path: Path,
) -> None:
    security = _deployment_security_module()
    config_a = security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    raw_b = _config_mapping(tmp_path)
    identity_b = raw_b["identity_verifier"]
    assert isinstance(identity_b, dict)
    identity_b.update(
        {
            "issuer": "https://idp-b.example",
            "jwks_uri": "https://idp-b.example/.well-known/jwks.json",
        }
    )
    config_b = security.DeploymentSecurityConfig.from_mapping(raw_b)
    runtime_a = security.build_deployment_security(config_a)

    with pytest.raises(TypeError, match=r"factory|build_deployment_security"):
        security.RuntimeDeploymentSecurity(
            config=config_b,
            identity_provider=runtime_a.identity_provider,
            cell_registry=runtime_a.cell_registry,
            opa_client=runtime_a.opa_client,
            step_up_verifier=runtime_a.step_up_verifier,
            principal_grants=runtime_a.principal_grants,
            human_decision_custody=runtime_a.human_decision_custody,
        )

    runtime_b = security.build_deployment_security(config_b)
    assert runtime_b.config is config_b
    assert runtime_b.identity_provider is not runtime_a.identity_provider


def test_non_development_bootstrap_and_probe_reject_object_new_forged_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError
    from polisyos.runtime.http.permissions import RuntimePermission

    security = _deployment_security_module()
    genuine = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    forged = object.__new__(security.RuntimeDeploymentSecurity)
    for field_name in (
        "config",
        "identity_provider",
        "cell_registry",
        "opa_client",
        "step_up_verifier",
        "principal_grants",
        "human_decision_custody",
    ):
        object.__setattr__(forged, field_name, getattr(genuine, field_name))

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")

    with pytest.raises(RuntimeBootstrapError, match=r"factory|attest|bundle"):
        create_runtime_api_app(
            cas_root=tmp_path / "forged-cas",
            deployment_security=forged,
        )
    with pytest.raises(TypeError, match=r"factory|attest|bundle"):
        security.verify_exact_deployment_principal_token(
            forged,
            "synthetic-probe-token",
            required_permissions=frozenset(
                {RuntimePermission.RUNS_LAUNCH, RuntimePermission.RUNS_VIEW}
            ),
        )


def test_non_development_bootstrap_and_probe_reject_replaced_factory_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError
    from polisyos.runtime.http.permissions import RuntimePermission

    security = _deployment_security_module()
    config_a = security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    raw_b = _config_mapping(tmp_path)
    identity_b = raw_b["identity_verifier"]
    assert isinstance(identity_b, dict)
    identity_b.update(
        {
            "issuer": "https://idp-b.example",
            "jwks_uri": "https://idp-b.example/.well-known/jwks.json",
        }
    )
    runtime_a = security.build_deployment_security(config_a)
    runtime_b = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(raw_b)
    )
    object.__setattr__(runtime_a, "identity_provider", runtime_b.identity_provider)

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")

    with pytest.raises(RuntimeBootstrapError, match=r"factory|attest|bundle"):
        create_runtime_api_app(
            cas_root=tmp_path / "replaced-cas",
            deployment_security=runtime_a,
        )
    with pytest.raises(TypeError, match=r"factory|attest|bundle"):
        security.verify_exact_deployment_principal_token(
            runtime_a,
            "synthetic-probe-token",
            required_permissions=frozenset(
                {RuntimePermission.RUNS_LAUNCH, RuntimePermission.RUNS_VIEW}
            ),
        )


def test_factory_attestation_rejects_post_factory_config_mutation(
    tmp_path: Path,
) -> None:
    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    object.__setattr__(runtime.config.opa, "url", "http://attacker.invalid:8181")

    with pytest.raises(TypeError, match=r"factory|attest|bundle"):
        security.require_factory_produced_deployment_security(runtime)


@pytest.mark.parametrize(
    "mutation",
    [
        "identity_method",
        "principal_grants",
        "opa_method",
        "cell_method",
        "step_up_method",
        "identity_jwks_cache",
        "step_up_jwks_client",
        "opa_decision_cache",
        "opa_session",
    ],
)
def test_non_development_runtime_revalidates_same_object_authority_before_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from types import MappingProxyType

    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.permissions import RuntimePermission

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    app = create_runtime_api_app(
        cas_root=tmp_path / f"same-object-{mutation}",
        deployment_security=runtime,
    )

    if mutation == "identity_method":
        object.__setattr__(
            runtime.identity_provider,
            "extract_user_claims",
            lambda _token, **_kwargs: SimpleNamespace(sub="forged-admin"),
        )
    elif mutation == "principal_grants":
        grant = runtime.config.service_principals[0]
        object.__setattr__(
            runtime.principal_grants,
            "_permissions_by_identity",
            MappingProxyType(
                {
                    grant.identity_key: frozenset(
                        {
                            *grant.permissions,
                            RuntimePermission.EVIDENCE_ACQUIRE,
                        }
                    )
                }
            ),
        )
    elif mutation == "opa_method":
        object.__setattr__(runtime.opa_client, "check", lambda _input: True)
    elif mutation == "cell_method":
        object.__setattr__(
            runtime.cell_registry,
            "resolve",
            lambda _tenant_id: SimpleNamespace(cell_id="attacker-cell"),
        )
    elif mutation == "step_up_method":
        object.__setattr__(
            runtime.step_up_verifier,
            "verify",
            lambda _token, _context: SimpleNamespace(assertion_id="forged-step-up"),
        )
    elif mutation == "identity_jwks_cache":
        runtime.identity_provider._jwks_cache["client"] = SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key="forged")
        )
    elif mutation == "step_up_jwks_client":
        object.__setattr__(
            runtime.step_up_verifier,
            "_jwks_client",
            SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key="forged")),
        )
    elif mutation == "opa_decision_cache":
        object.__setattr__(
            runtime.opa_client,
            "_cache",
            SimpleNamespace(get=lambda _key: SimpleNamespace(is_allowed=True)),
        )
    else:
        object.__setattr__(
            runtime.opa_client,
            "_session",
            SimpleNamespace(post=lambda *_args, **_kwargs: SimpleNamespace()),
        )

    with pytest.raises(TypeError, match=r"factory|attest|bundle"):
        security.verify_exact_deployment_principal_token(
            runtime,
            "synthetic-probe-token",
            required_permissions=frozenset(
                {RuntimePermission.RUNS_LAUNCH, RuntimePermission.RUNS_VIEW}
            ),
        )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "deployment_security_attestation_invalid"


@pytest.mark.parametrize(
    "mutation",
    [
        "identity_public_paths",
        "authorization_enforcement",
        "delegation_manager",
        "step_up_replay_store",
    ],
)
def test_non_development_runtime_revalidates_perimeter_objects_before_bypass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    app = create_runtime_api_app(
        cas_root=tmp_path / f"perimeter-{mutation}",
        deployment_security=runtime,
        enable_security_middlewares=True,
    )

    def _middleware(name: str) -> Any:
        current = cast("Any", app).middleware_stack
        while current is not None:
            if type(current).__name__ == name:
                return current
            current = getattr(current, "app", None)
        raise AssertionError(f"middleware {name!r} was not installed")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/health").status_code == 200
        if mutation == "identity_public_paths":
            identity_middleware = _middleware("JWTAuthMiddleware")
            object.__setattr__(
                identity_middleware,
                "_public_paths",
                frozenset({"/health", "/api/v1/control/data/ingest"}),
            )
        elif mutation == "authorization_enforcement":
            object.__setattr__(_middleware("AuthzMiddleware"), "_enforce", False)
        elif mutation == "delegation_manager":
            object.__setattr__(
                _middleware("AuthzMiddleware"),
                "_delegation_manager",
                SimpleNamespace(decode_and_validate=lambda *_args, **_kwargs: object()),
            )
        else:
            object.__setattr__(
                cast("Any", app).state.runtime_security,
                "step_up_replay_store",
                _AlwaysTrueReplayStore(),
            )
        response = client.get("/health")

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "deployment_security_attestation_invalid"


def test_non_development_review_socket_rejects_removed_deployment_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from polisyos.runtime.http.app import create_runtime_api_app

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    app = create_runtime_api_app(
        cas_root=tmp_path / "review-installation-removal",
        deployment_security=runtime,
        enable_security_middlewares=True,
    )

    with TestClient(app) as client:
        cast("Any", app).state.runtime_deployment_security = None
        with (
            pytest.raises(WebSocketDisconnect) as raised,
            client.websocket_connect(
                "/api/v1/review/live?channel=review.cursor&review_id=review-ds20"
            ),
        ):
            pass

    assert raised.value.code == 4503
    assert raised.value.reason == "Deployment security attestation failed"


def test_non_development_request_revalidates_authority_after_entry_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    import time
    from types import MappingProxyType

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.permissions import RuntimePermission
    from tests.unit.runtime.http.deployment_security_test_support import (
        LocalJWKSStub,
    )

    security = _deployment_security_module()
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    runtime_holder: dict[str, Any] = {}

    def _mutate_grants_during_key_fetch() -> None:
        runtime = runtime_holder["runtime"]
        grant = runtime.config.service_principals[0]
        object.__setattr__(
            runtime.principal_grants,
            "_permissions_by_identity",
            MappingProxyType(
                {
                    grant.identity_key: frozenset(
                        {
                            *grant.permissions,
                            RuntimePermission.EVIDENCE_ACQUIRE,
                        }
                    )
                }
            ),
        )

    jwks_server = LocalJWKSStub(
        private_key,
        on_request=_mutate_grants_during_key_fetch,
    )
    jwks_uri = jwks_server.start()
    request.addfinalizer(jwks_server.close)
    raw_config = _config_mapping(tmp_path)
    identity_config = raw_config["identity_verifier"]
    assert isinstance(identity_config, dict)
    identity_config["jwks_uri"] = jwks_uri
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(raw_config)
    )
    runtime_holder["runtime"] = runtime
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    app = create_runtime_api_app(
        cas_root=tmp_path / "post-entry-authority-mutation",
        deployment_security=runtime,
        enable_security_middlewares=True,
    )
    audit_events: list[dict[str, Any]] = []

    class _AuditCapture:
        def append(self, entry: dict[str, Any]) -> None:
            audit_events.append(entry)

    audit_capture = _AuditCapture()
    cast("Any", app).state.runtime_container.runtime_access_audit = audit_capture
    cast("Any", app).state.runtime_access_audit = audit_capture
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://idp.example",
            "aud": "polisyos-runtime",
            "sub": "runtime-canary",
            "tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "cell_id": "018f47a0-0000-7000-8000-000000000001",
            "realm_access": {"roles": ["polisyos_viewer"]},
            "amr": ["pwd", "mfa"],
            "iat": now,
            "exp": now + 60,
            "jti": f"post-entry-authority-mutation-{now}",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "identity-2026-07"},
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/control/data/ingest",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            },
            json={},
        )

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "deployment_security_attestation_invalid"
    assert len(audit_events) == 1
    assert audit_events[0]["outcome"] == "deny"
    assert audit_events[0]["denial_reason"] == ("deployment_security_attestation_invalid")


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
        assert runtime.principal_grants.permissions_for_principal(**mismatched) == frozenset()


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


@pytest.mark.parametrize(
    "audience",
    [
        ["polisyos-runtime", "other-service"],
        ["other-service", "polisyos-runtime"],
    ],
)
def test_deployment_identity_provider_rejects_multi_audience_token(
    tmp_path: Path,
    audience: list[str],
) -> None:
    import time

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from polisyos.core.security.exceptions import TokenValidationError

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://idp.example",
            "aud": audience,
            "sub": "runtime-canary",
            "tenant_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "cell_id": "018f47a0-0000-7000-8000-000000000001",
            "realm_access": {"roles": ["polisyos_admin"]},
            "amr": ["pwd", "mfa"],
            "iat": now,
            "exp": now + 60,
            "jti": f"runtime-canary-{now}",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "identity-2026-07"},
    )

    with pytest.raises(TokenValidationError, match=r"audience|singleton|exact"):
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
    from fastapi.testclient import TestClient

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
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("injection_name", "injection"),
    [
        (
            "step_up_replay_store",
            {"step_up_replay_store": _AlwaysTrueReplayStore()},
        ),
        ("delegation_manager", {"delegation_manager": object()}),
        (
            "trusted_delegators",
            {"trusted_delegators": frozenset({"spiffe://delegator.example/runtime"})},
        ),
        ("service_spiffe_id", {"service_spiffe_id": "spiffe://runtime.example/api"}),
        ("authz_enforce", {"authz_enforce": False}),
        ("authz_shadow_mode", {"authz_shadow_mode": True}),
    ],
)
def test_non_development_bootstrap_rejects_direct_authority_injections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    injection_name: str,
    injection: dict[str, Any],
) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")

    with pytest.raises(RuntimeBootstrapError, match=injection_name):
        create_runtime_api_app(
            cas_root=tmp_path / injection_name,
            deployment_security=runtime,
            **injection,
        )


def test_non_development_bootstrap_rejects_runtime_container_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError

    security = _deployment_security_module()
    runtime = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")

    with pytest.raises(RuntimeBootstrapError, match="container_overrides"):
        create_runtime_api_app(
            cas_root=tmp_path / "container-override",
            deployment_security=runtime,
            container_overrides=RuntimeContainerOverrides(),
        )


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

    assert (
        resolver.resolve_claim_permissions(
            claims,
            effective_subject=claims.sub,
            effective_tenant_id=claims.tenant_id,
            effective_cell_id="cell-effective",
        )
        == frozenset()
    )


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
                state=SimpleNamespace(runtime_deployment_principal_grants=runtime.principal_grants)
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


def test_action_dependency_denies_managed_admin_when_effective_cell_differs_from_claim() -> None:
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
        app=SimpleNamespace(state=SimpleNamespace(runtime_deployment_principal_grants=grants)),
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
    # This test isolates grant projection on the development composition built
    # by ``_build_secure_client``. Non-development bundle/alias integrity is
    # covered by the attestation negatives above and must remain all-or-nothing.
    cast("Any", client.app).state.runtime_deployment_principal_grants = runtime.principal_grants
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
