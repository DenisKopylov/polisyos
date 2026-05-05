from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from polisyos.core.security.exceptions import (
    IdentityNotAvailableError,
    IdentityVerificationError,
    TokenValidationError,
)
from polisyos.core.security.identity import (
    PolicyOSRole,
    SPIFFEIdentityProvider,
    infer_mfa_verified,
    map_roles_from_claims,
)
from polisyos.core.security.settings import SecuritySettings


class _MetricsStub:
    def __init__(self) -> None:
        self.failures: list[tuple[str, str]] = []

    def record_identity_failure(self, *, reason: str, provider: str) -> None:
        self.failures.append((reason, provider))


def test_map_roles_from_claims_combines_realm_and_client_roles() -> None:
    payload = {
        "realm_access": {"roles": ["polisyos_analyst"]},
        "resource_access": {"polisyos-web": {"roles": ["tenant_admin"]}},
    }

    roles = map_roles_from_claims(payload, client_id="polisyos-web")

    assert roles == frozenset({PolicyOSRole.ANALYST, PolicyOSRole.ADMIN})


def test_map_roles_defaults_to_viewer() -> None:
    roles = map_roles_from_claims({}, client_id="polisyos-web")
    assert roles == frozenset({PolicyOSRole.VIEWER})


def test_infer_mfa_verified_from_amr_and_acr() -> None:
    assert infer_mfa_verified({"amr": ["webauthn"]}) is True
    assert infer_mfa_verified({"acr": "2"}) is True
    assert infer_mfa_verified({"amr": ["pwd"]}) is False


def test_parse_spiffe_id_valid() -> None:
    parsed = SPIFFEIdentityProvider._parse_spiffe_id(
        "spiffe://polisyos.io/cell/cell-a/svc/scientist"
    )

    assert parsed["trust_domain"] == "polisyos.io"
    assert parsed["cell_id"] == "cell-a"
    assert parsed["service_name"] == "scientist"


def test_parse_spiffe_id_rejects_invalid() -> None:
    with pytest.raises(IdentityVerificationError):
        SPIFFEIdentityProvider._parse_spiffe_id("invalid-spiffe")


def test_jwks_cache_is_thread_safe() -> None:
    provider = SPIFFEIdentityProvider(
        keycloak_issuer_url="https://issuer.example",
        keycloak_jwks_uri="https://issuer.example/jwks",
        expected_audience="polisyos-web",
    )
    init_calls: list[str] = []

    class _FakePyJWT:
        class PyJWKClient:
            def __init__(self, uri: str, **kwargs) -> None:
                del kwargs
                init_calls.append(uri)

    with ThreadPoolExecutor(max_workers=8) as pool:
        clients = list(pool.map(lambda _: provider._get_jwks_client(_FakePyJWT), range(32)))

    assert len(init_calls) == 1
    assert len({id(client) for client in clients}) == 1


def test_jwt_key_rotation_rejects_untrusted_or_revoked_kid() -> None:
    provider = SPIFFEIdentityProvider(
        keycloak_issuer_url="https://issuer.example",
        keycloak_jwks_uri="https://issuer.example/jwks",
        expected_audience="polisyos-web",
        allowed_jwt_kids=frozenset({"active-key"}),
        revoked_jwt_kids=frozenset({"revoked-key"}),
    )

    class _FakePyJWT:
        @staticmethod
        def get_unverified_header(token: str) -> dict[str, str]:
            return {"kid": token}

    assert provider._validated_jwt_key_id(_FakePyJWT, "active-key") == "active-key"
    with pytest.raises(TokenValidationError, match="active trust set"):
        provider._validated_jwt_key_id(_FakePyJWT, "unknown-key")
    with pytest.raises(TokenValidationError, match="revoked"):
        provider._validated_jwt_key_id(_FakePyJWT, "revoked-key")


def test_jwks_cache_ttl_is_configurable() -> None:
    provider = SPIFFEIdentityProvider(
        keycloak_issuer_url="https://issuer.example",
        keycloak_jwks_uri="https://issuer.example/jwks",
        expected_audience="polisyos-web",
        jwks_cache_ttl_seconds=17,
    )
    init_kwargs: list[dict[str, object]] = []

    class _FakePyJWT:
        class PyJWKClient:
            def __init__(self, uri: str, **kwargs) -> None:
                del uri
                init_kwargs.append(kwargs)

    provider._get_jwks_client(_FakePyJWT)

    assert init_kwargs == [{"cache_jwk_set": True, "lifespan": 17}]


def test_identity_provider_factory_wires_rotation_settings() -> None:
    settings = SecuritySettings(
        POLISYOS_KEYCLOAK_ISSUER_URL="https://issuer.example",
        POLISYOS_KEYCLOAK_JWKS_URI="https://issuer.example/jwks",
        POLISYOS_KEYCLOAK_AUDIENCE="polisyos-web",
        POLISYOS_KEYCLOAK_CLIENT_ID="polisyos-web",
        POLISYOS_JWT_REQUIRED_MFA_ROLES="admin",
        POLISYOS_JWT_ALLOWED_KIDS="active-key,next-key",
        POLISYOS_JWT_REVOKED_KIDS="revoked-key",
        POLISYOS_JWKS_CACHE_TTL_SECONDS=23,
    )

    provider = SPIFFEIdentityProvider.from_settings(settings)

    assert provider._required_mfa_roles == frozenset({PolicyOSRole.ADMIN})
    assert provider._allowed_jwt_kids == frozenset({"active-key", "next-key"})
    assert provider._revoked_jwt_kids == frozenset({"revoked-key"})
    assert provider._jwks_cache_ttl_seconds == 23


def test_identity_provider_uses_injected_metrics_for_spiffe_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _MetricsStub()
    provider = SPIFFEIdentityProvider(
        keycloak_issuer_url="https://issuer.example",
        keycloak_jwks_uri="https://issuer.example/jwks",
        expected_audience="polisyos-web",
        metrics=metrics,
    )

    monkeypatch.delenv("POLISYOS_SERVICE_SPIFFE_ID", raising=False)
    monkeypatch.setattr(
        "polisyos.core.security.identity.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    with pytest.raises(IdentityNotAvailableError, match="No SPIFFE identity available"):
        provider.get_own_identity()

    assert metrics.failures == [("spiffe_not_available", "spiffe")]


def test_identity_provider_factory_accepts_metrics_override() -> None:
    metrics = _MetricsStub()
    settings = SecuritySettings(
        POLISYOS_KEYCLOAK_ISSUER_URL="https://issuer.example",
        POLISYOS_KEYCLOAK_JWKS_URI="https://issuer.example/jwks",
        POLISYOS_KEYCLOAK_AUDIENCE="polisyos-web",
        POLISYOS_KEYCLOAK_CLIENT_ID="polisyos-web",
    )

    provider = SPIFFEIdentityProvider.from_settings(settings, metrics=metrics)

    assert provider._metrics is metrics
