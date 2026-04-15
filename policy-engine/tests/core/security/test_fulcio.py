from __future__ import annotations

import types
import pytest

from polisyos.core.security.slsa.config import SLSAConfig, SlsaMode
from polisyos.core.security.slsa.fulcio import FulcioClient


class _StaticOIDCTokenProvider:
    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(self) -> str:
        return self._token


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_fulcio_sign_reads_verified_oidc_claims(monkeypatch) -> None:
    issuer = "https://issuer.example"
    audience = "polisyos-scientist"
    subject = "user@example.com"
    token = "valid-token"

    monkeypatch.setattr(
        "polisyos.core.security.slsa.fulcio.httpx.get",
        lambda *args, **kwargs: _FakeResponse({"jwks_uri": f"{issuer}/jwks"}),
    )

    class _FakeSigningKey:
        def __init__(self, key: object) -> None:
            self.key = key

    class _FakePyJWKClient:
        def __init__(self, uri: str, **kwargs) -> None:
            self.uri = uri
            self.kwargs = kwargs

        def get_signing_key_from_jwt(self, jwt_token: str) -> _FakeSigningKey:
            assert jwt_token == token
            return _FakeSigningKey("verified-public-key")

    class _InvalidTokenError(Exception):
        pass

    fake_jwt = types.SimpleNamespace(
        PyJWKClient=_FakePyJWKClient,
        ExpiredSignatureError=type("ExpiredSignatureError", (Exception,), {}),
        InvalidTokenError=_InvalidTokenError,
        decode=lambda jwt_token, key, algorithms, audience, issuer, options: {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": 1_700_000_000,
            "exp": 4_102_444_800,
        }
        if jwt_token == token and key == "verified-public-key"
        else (_ for _ in ()).throw(_InvalidTokenError("invalid")),
    )
    monkeypatch.setitem(__import__("sys").modules, "jwt", fake_jwt)

    client = FulcioClient(
        SLSAConfig(
            mode=SlsaMode.PUBLIC,
            oidc_issuer=issuer,
            oidc_client_id=audience,
        ),
        oidc_provider=_StaticOIDCTokenProvider(token),
    )
    monkeypatch.setattr(
        client,
        "_request_fulcio_chain",
        lambda **kwargs: [
            "-----BEGIN CERTIFICATE-----\nleaf\n-----END CERTIFICATE-----\n",
            "-----BEGIN CERTIFICATE-----\nroot\n-----END CERTIFICATE-----\n",
        ],
    )

    result = client.sign(b"payload")

    assert result.oidc_issuer == issuer
    assert result.oidc_subject == subject
    assert result.certificate_chain


def test_fulcio_sign_rejects_invalid_oidc_before_request(monkeypatch) -> None:
    issuer = "https://issuer.example"
    audience = "polisyos-scientist"
    token = "invalid-token"

    monkeypatch.setattr(
        "polisyos.core.security.slsa.fulcio.httpx.get",
        lambda *args, **kwargs: _FakeResponse({"jwks_uri": f"{issuer}/jwks"}),
    )

    class _FakeSigningKey:
        def __init__(self, key: object) -> None:
            self.key = key

    class _FakePyJWKClient:
        def __init__(self, uri: str, **kwargs) -> None:
            self.uri = uri
            self.kwargs = kwargs

        def get_signing_key_from_jwt(self, jwt_token: str) -> _FakeSigningKey:
            assert jwt_token == token
            return _FakeSigningKey("verified-public-key")

    class _InvalidTokenError(Exception):
        pass

    fake_jwt = types.SimpleNamespace(
        PyJWKClient=_FakePyJWKClient,
        ExpiredSignatureError=type("ExpiredSignatureError", (Exception,), {}),
        InvalidTokenError=_InvalidTokenError,
        decode=lambda *args, **kwargs: (_ for _ in ()).throw(
            _InvalidTokenError("audience mismatch")
        ),
    )
    monkeypatch.setitem(__import__("sys").modules, "jwt", fake_jwt)

    client = FulcioClient(
        SLSAConfig(
            mode=SlsaMode.PUBLIC,
            oidc_issuer=issuer,
            oidc_client_id=audience,
        ),
        oidc_provider=_StaticOIDCTokenProvider(token),
    )
    monkeypatch.setattr(
        client,
        "_request_fulcio_chain",
        lambda **kwargs: pytest.fail("Fulcio should not be called for invalid OIDC tokens"),
    )

    with pytest.raises(RuntimeError, match="OIDC token validation failed"):
        client.sign(b"payload")
