"""Public slsa fulcio module API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDSA,
    SECP256R1,
    EllipticCurvePrivateKey,
    generate_private_key,
)
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID

from polisyos.core.canon import content_hash

from .config import SLSAConfig, SlsaMode


class OIDCTokenProvider(Protocol):
    """Provider abstraction for OIDC access token acquisition."""

    def get_token(self) -> str:  # pragma: no cover - protocol
        ...


class EnvOIDCTokenProvider:
    """Reads token from configured environment variable."""

    def __init__(self, token_env: str) -> None:
        self._token_env = token_env

    def get_token(self) -> str:
        import os

        token = os.getenv(self._token_env, "").strip()
        if not token:
            raise RuntimeError(f"OIDC token is not configured in ${self._token_env}")
        return token


@dataclass(frozen=True)
class FulcioSigningResult:
    """Signed payload + certificate data for attestation verification."""

    algorithm: str
    signature_hex: str
    payload_sha256: str
    certificate_pem: str
    certificate_chain: list[str]
    oidc_issuer: str
    oidc_subject: str
    signed_at: str


class FulcioClient:
    """Sign SLSA payloads in local mode or via Fulcio keyless flow."""

    def __init__(
        self,
        config: SLSAConfig,
        *,
        oidc_provider: OIDCTokenProvider | None = None,
    ) -> None:
        self._config = config
        self._oidc = oidc_provider or EnvOIDCTokenProvider(config.oidc_token_env)

    def sign(self, payload: bytes) -> FulcioSigningResult:
        if self._config.mode == SlsaMode.LOCAL:
            return self._sign_local(payload)
        if self._config.mode in {SlsaMode.PRIVATE, SlsaMode.PUBLIC}:
            return self._sign_fulcio(payload)
        raise RuntimeError("SLSA signing is disabled")

    def _sign_local(self, payload: bytes) -> FulcioSigningResult:
        private_key = generate_private_key(SECP256R1())
        cert_pem = self._build_self_signed_certificate(private_key)
        signature = private_key.sign(payload, ECDSA(hashes.SHA256()))

        return FulcioSigningResult(
            algorithm="ecdsa-p256-sha256",
            signature_hex=signature.hex(),
            payload_sha256=_sha256(payload),
            certificate_pem=cert_pem.decode("utf-8"),
            certificate_chain=[],
            oidc_issuer=self._config.oidc_issuer or "local://polisyos",
            oidc_subject=self._config.oidc_subject_fallback,
            signed_at=_utc_now_iso(),
        )

    def _sign_fulcio(self, payload: bytes) -> FulcioSigningResult:
        private_key = generate_private_key(SECP256R1())
        public_key_pem = private_key.public_key().public_bytes(
            Encoding.PEM,
            format=__import__(
                "cryptography.hazmat.primitives.serialization",
                fromlist=["PublicFormat"],
            ).PublicFormat.SubjectPublicKeyInfo,
        )
        oidc_token = self._oidc.get_token()
        claims = self._load_verified_oidc_claims(oidc_token)

        certs = self._request_fulcio_chain(public_key_pem=public_key_pem, oidc_token=oidc_token)
        signature = private_key.sign(payload, ECDSA(hashes.SHA256()))

        certificate_pem = certs[0] if certs else ""
        chain = certs[1:] if len(certs) > 1 else []

        return FulcioSigningResult(
            algorithm="ecdsa-p256-sha256",
            signature_hex=signature.hex(),
            payload_sha256=_sha256(payload),
            certificate_pem=certificate_pem,
            certificate_chain=chain,
            oidc_issuer=str(claims.get("iss") or self._config.oidc_issuer or ""),
            oidc_subject=str(claims.get("sub") or self._config.oidc_subject_fallback),
            signed_at=_utc_now_iso(),
        )

    def _load_verified_oidc_claims(self, oidc_token: str) -> dict[str, object]:
        issuer = self._config.oidc_issuer.strip()
        audience = self._config.oidc_client_id.strip()
        if not issuer:
            raise RuntimeError("Fulcio keyless signing requires POLISYOS_SLSA_OIDC_ISSUER")
        if not audience:
            raise RuntimeError("Fulcio keyless signing requires POLISYOS_SLSA_OIDC_CLIENT_ID")

        try:
            import jwt as pyjwt
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PyJWT is required for Fulcio OIDC token validation") from exc

        jwks_client = pyjwt.PyJWKClient(
            self._discover_oidc_jwks_uri(issuer),
            cache_jwk_set=True,
            lifespan=max(60, int(self._config.timeout_seconds * 10)),
        )
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(oidc_token)
            payload = pyjwt.decode(
                oidc_token,
                signing_key.key,
                algorithms=["RS256", "ES256", "EdDSA"],
                audience=audience,
                issuer=issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except pyjwt.ExpiredSignatureError as exc:
            raise RuntimeError("OIDC token expired") from exc
        except pyjwt.InvalidTokenError as exc:
            raise RuntimeError(f"OIDC token validation failed: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("OIDC token payload must be a JSON object")
        return payload

    def _discover_oidc_jwks_uri(self, issuer: str) -> str:
        response = httpx.get(
            f"{issuer.rstrip('/')}/.well-known/openid-configuration",
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        jwks_uri = payload.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri.strip():
            raise RuntimeError("OIDC discovery document does not include jwks_uri")
        return jwks_uri.strip()

    def _request_fulcio_chain(self, *, public_key_pem: bytes, oidc_token: str) -> list[str]:
        response = httpx.post(
            f"{self._config.fulcio_url.rstrip('/')}/api/v2/signingCert",
            json={
                "publicKeyRequest": {
                    "publicKey": {
                        "content": public_key_pem.decode("utf-8"),
                    },
                    "proofOfPossession": oidc_token,
                }
            },
            headers={"Authorization": f"Bearer {oidc_token}"},
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        chain = payload.get("signedCertificateEmbeddedSct", {}).get("chain", {}).get("certificates", [])
        if not isinstance(chain, list) or not chain:
            raise RuntimeError("Fulcio response does not include certificate chain")

        certs: list[str] = []
        for cert in chain:
            if not isinstance(cert, str):
                continue
            certs.append(_to_pem_if_needed(cert))

        if not certs:
            raise RuntimeError("Fulcio response certificate chain is empty")
        return certs

    def _build_self_signed_certificate(self, private_key: EllipticCurvePrivateKey) -> bytes:
        issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "PolicyOS Local Fulcio"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PolicyOS"),
            ]
        )
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, self._config.oidc_subject_fallback),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PolicyOS"),
            ]
        )
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(minutes=15))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(private_key=private_key, algorithm=hashes.SHA256())
        )
        return cert.public_bytes(Encoding.PEM)

def _to_pem_if_needed(value: str) -> str:
    if "BEGIN CERTIFICATE" in value:
        return value
    wrapped = "\n".join(value[i : i + 64] for i in range(0, len(value), 64))
    return f"-----BEGIN CERTIFICATE-----\n{wrapped}\n-----END CERTIFICATE-----\n"



def _sha256(payload: bytes) -> str:
    return content_hash(payload)



def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
