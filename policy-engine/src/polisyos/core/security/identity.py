"""Identity primitives for user/service authentication in Zero Trust mode."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from pydantic import ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.core.security.exceptions import (
    CrossTenantAccessError,
    IdentityNotAvailableError,
    IdentityVerificationError,
    MFARequiredError,
    TokenValidationError,
)

logger = get_logger("polisyos.security.identity")

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry

    class _PydanticBaseModel:
        model_config: ClassVar[ConfigDict]

        def __init__(self, /, **data: Any) -> None: ...
else:
    from pydantic import BaseModel as _PydanticBaseModel


class PolicyOSRole(str, Enum):
    """PolicyOS roles mapped from external identity providers."""

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    SERVICE = "service"
    SYSTEM = "system"


class PIIAccessLevel(str, Enum):
    """PII access ceiling for a principal."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


ROLE_PII_CEILING: dict[PolicyOSRole, PIIAccessLevel] = {
    PolicyOSRole.ADMIN: PIIAccessLevel.CRITICAL,
    PolicyOSRole.ANALYST: PIIAccessLevel.HIGH,
    PolicyOSRole.VIEWER: PIIAccessLevel.LOW,
    PolicyOSRole.SERVICE: PIIAccessLevel.HIGH,
    PolicyOSRole.SYSTEM: PIIAccessLevel.CRITICAL,
}

_ROLE_ORDER: tuple[PolicyOSRole, ...] = (
    PolicyOSRole.ADMIN,
    PolicyOSRole.ANALYST,
    PolicyOSRole.VIEWER,
    PolicyOSRole.SERVICE,
    PolicyOSRole.SYSTEM,
)

_LEVEL_ORDER: tuple[PIIAccessLevel, ...] = (
    PIIAccessLevel.NONE,
    PIIAccessLevel.LOW,
    PIIAccessLevel.MEDIUM,
    PIIAccessLevel.HIGH,
    PIIAccessLevel.CRITICAL,
)


@dataclass(frozen=True, slots=True)
class ServiceIdentityInfo:
    """Store a verified SPIFFE workload identity and certificate validity window."""

    spiffe_id: str
    trust_domain: str
    cell_id: str
    service_name: str
    certificate_serial: str
    issued_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        """Return whether the SPIFFE certificate validity window has passed."""
        return bool(self.expires_at) and time.time() > self.expires_at

    def to_otel_attributes(self) -> dict[str, str]:
        """Render SPIFFE identity attributes for tracing/audit correlation."""
        return {
            "identity.spiffe_id": self.spiffe_id,
            "identity.trust_domain": self.trust_domain,
            "identity.cell_id": self.cell_id,
            "identity.service_name": self.service_name,
        }


class UserIdentityClaims(_PydanticBaseModel):
    """Validated JWT claims normalized to PolicyOS identity model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sub: str = Field(min_length=1)
    email: str = ""
    tenant_id: str = Field(min_length=1)
    cell_id: str | None = None
    roles: frozenset[PolicyOSRole] = Field(
        default_factory=lambda: frozenset({PolicyOSRole.VIEWER})
    )
    mfa_verified: bool = False
    iss: str = Field(min_length=1)
    aud: str
    exp: int
    iat: int
    jti: str = ""

    @property
    def is_expired(self) -> bool:
        """Return whether the JWT expiration timestamp is in the past."""
        return time.time() > float(self.exp)

    @property
    def highest_role(self) -> PolicyOSRole:
        """Return the highest-privilege PolicyOS role present in the claim set."""
        for role in _ROLE_ORDER:
            if role in self.roles:
                return role
        return PolicyOSRole.VIEWER

    @property
    def max_pii_access(self) -> PIIAccessLevel:
        """Return the strongest PII tier allowed by any mapped role."""
        levels = [PIIAccessLevel.NONE]
        for role in self.roles:
            levels.append(ROLE_PII_CEILING.get(role, PIIAccessLevel.NONE))
        return max(levels, key=_LEVEL_ORDER.index)

    def to_otel_attributes(self) -> dict[str, str]:
        """Render user identity attributes for trace spans and audit records."""
        return {
            "identity.user_sub": self.sub,
            "identity.tenant_id": self.tenant_id,
            "identity.roles": ",".join(sorted(role.value for role in self.roles)),
            "identity.mfa_verified": str(self.mfa_verified).lower(),
        }


def map_roles_from_claims(payload: dict[str, Any], *, client_id: str) -> frozenset[PolicyOSRole]:
    """Map Keycloak-style role claims into PolicyOS roles."""

    role_map = {
        "polisyos_admin": PolicyOSRole.ADMIN,
        "polisyos_analyst": PolicyOSRole.ANALYST,
        "polisyos_viewer": PolicyOSRole.VIEWER,
        "tenant_admin": PolicyOSRole.ADMIN,
    }

    raw_roles: set[str] = set()
    realm_access = payload.get("realm_access")
    if isinstance(realm_access, dict):
        roles = realm_access.get("roles")
        if isinstance(roles, list):
            raw_roles.update(str(item) for item in roles)

    resource_access = payload.get("resource_access")
    if isinstance(resource_access, dict):
        client_access = resource_access.get(client_id)
        if isinstance(client_access, dict):
            client_roles = client_access.get("roles")
            if isinstance(client_roles, list):
                raw_roles.update(str(item) for item in client_roles)

    mapped = {
        mapped_role
        for source_role, mapped_role in role_map.items()
        if source_role in raw_roles
    }
    if not mapped:
        mapped.add(PolicyOSRole.VIEWER)
    return frozenset(mapped)


def infer_mfa_verified(payload: dict[str, Any]) -> bool:
    """Infer MFA verification from OIDC claims."""

    acr = str(payload.get("acr", ""))
    if acr in {"2", "3", "urn:mace:incommon:iap:silver"}:
        return True

    amr = payload.get("amr", [])
    if isinstance(amr, str):
        amr_values = {amr.lower()}
    elif isinstance(amr, list):
        amr_values = {str(item).lower() for item in amr}
    else:
        amr_values = set()

    return bool(amr_values & {"webauthn", "fido-u2f", "mfa", "otp"})


@runtime_checkable
class ServiceIdentity(Protocol):
    """Resolve local service identity, verify peer SPIFFE IDs, and decode user JWT claims."""

    def get_own_identity(self) -> ServiceIdentityInfo:
        """Return local service identity according to provider-specific rules."""
        ...

    def verify_peer(self, peer_spiffe_id: str) -> ServiceIdentityInfo:
        """Validate a peer service identity and return its normalized SPIFFE metadata."""
        ...

    def extract_user_claims(
        self,
        jwt_token: str,
        *,
        expected_cell_id: str | None = None,
    ) -> UserIdentityClaims:
        """Decode and verify a bearer token, then return normalized user claims."""
        ...


class SPIFFEIdentityProvider:
    """Combine SPIFFE service identity and Keycloak/OIDC JWT validation.

    `get_own_identity()` resolves the workload SPIFFE ID from SPIRE or the
    `POLISYOS_SERVICE_SPIFFE_ID` override, while `extract_user_claims()` validates
    bearer JWTs and enforces MFA requirements for privileged roles.
    """

    def __init__(
        self,
        *,
        keycloak_issuer_url: str,
        keycloak_jwks_uri: str,
        expected_audience: str,
        keycloak_client_id: str = "polisyos-web",
        spiffe_endpoint_socket: str = "unix:///run/spire/sockets/agent.sock",
        trust_domain: str = "polisyos.io",
        allowed_cell_ids: frozenset[str] | None = None,
        required_mfa_roles: frozenset[PolicyOSRole] | None = None,
        allowed_jwt_kids: frozenset[str] | None = None,
        revoked_jwt_kids: frozenset[str] | None = None,
        jwks_cache_ttl_seconds: int = 300,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._issuer = keycloak_issuer_url.rstrip("/")
        self._jwks_uri = keycloak_jwks_uri
        self._audience = expected_audience
        self._client_id = keycloak_client_id
        self._spiffe_socket = spiffe_endpoint_socket
        self._trust_domain = trust_domain
        self._allowed_cells = allowed_cell_ids
        self._required_mfa_roles = required_mfa_roles or frozenset(
            {PolicyOSRole.ADMIN, PolicyOSRole.ANALYST}
        )
        self._allowed_jwt_kids = allowed_jwt_kids or frozenset()
        self._revoked_jwt_kids = revoked_jwt_kids or frozenset()
        self._jwks_cache_ttl_seconds = max(1, int(jwks_cache_ttl_seconds))
        self._metrics = metrics or get_metrics()

        self._workload_client: Any | None = None
        self._jwks_cache: dict[str, Any] = {}
        self._jwks_cache_expires: float = 0.0
        self._jwks_lock = threading.Lock()

    @classmethod
    def from_settings(
        cls,
        settings: Any,
        *,
        metrics: MetricsRegistry | None = None,
    ) -> SPIFFEIdentityProvider:
        """Build an identity provider from resolved security settings.

        This keeps JWT rotation policy (`kid` allow/revoke sets and JWKS TTL)
        attached to the typed bootstrap settings instead of ad-hoc runtime
        wiring.
        """
        return cls(
            keycloak_issuer_url=str(settings.POLISYOS_KEYCLOAK_ISSUER_URL),
            keycloak_jwks_uri=str(settings.POLISYOS_KEYCLOAK_JWKS_URI),
            expected_audience=str(settings.POLISYOS_KEYCLOAK_AUDIENCE),
            keycloak_client_id=str(settings.POLISYOS_KEYCLOAK_CLIENT_ID),
            required_mfa_roles=frozenset(
                PolicyOSRole(role) for role in settings.required_mfa_roles()
            ),
            allowed_jwt_kids=settings.allowed_jwt_kids(),
            revoked_jwt_kids=settings.revoked_jwt_kids(),
            jwks_cache_ttl_seconds=int(settings.POLISYOS_JWKS_CACHE_TTL_SECONDS),
            metrics=metrics,
        )

    def _record_identity_failure(self, *, reason: str, provider: str) -> None:
        self._metrics.record_identity_failure(reason=reason, provider=provider)

    def _ensure_workload_client(self) -> Any:
        if self._workload_client is not None:
            return self._workload_client

        workload_client_type = _load_spiffe_workload_client_type()
        if workload_client_type is None:
            self._workload_client = None
            return None

        try:
            self._workload_client = workload_client_type(spiffe_socket=self._spiffe_socket)
            return self._workload_client
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:  # pragma: no cover - depends on runtime SPIRE env
            raise IdentityNotAvailableError(
                f"Cannot connect SPIRE agent at {self._spiffe_socket}: {exc}"
            ) from exc

    def get_own_identity(self) -> ServiceIdentityInfo:
        """Return this service's SPIFFE identity from env override or SPIRE.

        Raises:
            IdentityNotAvailableError: If no SPIFFE source is configured or the
                workload API cannot be queried.
            IdentityVerificationError: If the SPIFFE ID format is malformed.
        """
        env_spiffe = os.getenv("POLISYOS_SERVICE_SPIFFE_ID", "").strip()
        if env_spiffe:
            parts = self._parse_spiffe_id(env_spiffe)
            return ServiceIdentityInfo(
                spiffe_id=env_spiffe,
                trust_domain=parts["trust_domain"],
                cell_id=parts["cell_id"],
                service_name=parts["service_name"],
                certificate_serial="env",
                issued_at=0.0,
                expires_at=0.0,
            )

        workload = self._ensure_workload_client()
        if workload is None:
            self._record_identity_failure(reason="spiffe_not_available", provider="spiffe")
            raise IdentityNotAvailableError(
                "No SPIFFE identity available: set POLISYOS_SERVICE_SPIFFE_ID or configure SPIRE"
            )

        try:
            svid = workload.fetch_x509_svid()
            spiffe_id = str(svid.spiffe_id)
            parts = self._parse_spiffe_id(spiffe_id)
            cert = svid.leaf
            return ServiceIdentityInfo(
                spiffe_id=spiffe_id,
                trust_domain=parts["trust_domain"],
                cell_id=parts["cell_id"],
                service_name=parts["service_name"],
                certificate_serial=str(cert.serial_number),
                issued_at=cert.not_valid_before_utc.timestamp(),
                expires_at=cert.not_valid_after_utc.timestamp(),
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:  # pragma: no cover - runtime SPIRE dependency
            self._record_identity_failure(reason="spiffe_fetch_failed", provider="spiffe")
            raise IdentityNotAvailableError(str(exc)) from exc

    def verify_peer(self, peer_spiffe_id: str) -> ServiceIdentityInfo:
        """Validate a peer SPIFFE ID against trust-domain and same-cell/federation policy.

        Raises:
            IdentityVerificationError: If the SPIFFE trust domain or ID shape is invalid.
            CrossTenantAccessError: If the peer cell differs from the local cell and
                no federation allowlist admits it.
            IdentityNotAvailableError: If local SPIFFE identity cannot be resolved.
        """
        parts = self._parse_spiffe_id(peer_spiffe_id)

        if parts["trust_domain"] != self._trust_domain:
            self._record_identity_failure(
                reason="spiffe_trust_domain_mismatch",
                provider="spiffe",
            )
            raise IdentityVerificationError(
                f"Unexpected trust domain {parts['trust_domain']!r} != {self._trust_domain!r}"
            )

        own = self.get_own_identity()
        if parts["cell_id"] != own.cell_id:
            if self._allowed_cells and parts["cell_id"] in self._allowed_cells:
                logger.info(
                    "Cross-cell peer accepted via federation allowlist: own=%s peer=%s",
                    own.cell_id,
                    parts["cell_id"],
                )
            else:
                self._record_identity_failure(reason="cross_cell_peer", provider="spiffe")
                raise CrossTenantAccessError(
                    requesting_tenant=own.cell_id,
                    target_tenant=parts["cell_id"],
                    resource="spiffe.peer_identity",
                )

        return ServiceIdentityInfo(
            spiffe_id=peer_spiffe_id,
            trust_domain=parts["trust_domain"],
            cell_id=parts["cell_id"],
            service_name=parts["service_name"],
            certificate_serial="peer",
            issued_at=0.0,
            expires_at=0.0,
        )

    def extract_user_claims(
        self,
        jwt_token: str,
        *,
        expected_cell_id: str | None = None,
    ) -> UserIdentityClaims:
        """Validate a bearer JWT and normalize it to `UserIdentityClaims`.

        Args:
            jwt_token: Encoded OIDC access token presented by an HTTP client.
            expected_cell_id: Optional cell binding expected from the route/middleware.

        Returns:
            Frozen user claims with normalized PolicyOS roles and MFA status.

        Raises:
            TokenValidationError: If PyJWT is unavailable, signature/issuer/audience
                checks fail, required claims are missing, or cell binding mismatches.
            MFARequiredError: If a privileged role is present without a verified
                MFA claim.
        """
        try:
            import jwt as pyjwt
        except ModuleNotFoundError as exc:
            raise TokenValidationError(
                "PyJWT is required for JWT validation. Install policy-engine[multi-tenant]."
            ) from exc

        self._validated_jwt_key_id(pyjwt, jwt_token)
        jwks_client = self._get_jwks_client(pyjwt)

        try:
            signing_key = jwks_client.get_signing_key_from_jwt(jwt_token)
            payload = pyjwt.decode(
                jwt_token,
                signing_key.key,
                algorithms=["RS256", "ES256", "EdDSA"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except pyjwt.ExpiredSignatureError as exc:
            self._record_identity_failure(reason="jwt_expired", provider="keycloak")
            raise TokenValidationError("Token expired") from exc
        except pyjwt.InvalidTokenError as exc:
            self._record_identity_failure(reason="jwt_invalid", provider="keycloak")
            raise TokenValidationError(f"Token validation failed: {exc}") from exc

        tenant_id = str(payload.get("tenant_id", "")).strip()
        if not tenant_id:
            self._record_identity_failure(reason="jwt_missing_tenant", provider="keycloak")
            raise TokenValidationError("Missing required claim: tenant_id")

        token_cell_id = payload.get("cell_id")
        if token_cell_id is not None and not isinstance(token_cell_id, str):
            self._record_identity_failure(
                reason="jwt_invalid_cell_claim",
                provider="keycloak",
            )
            raise TokenValidationError("Invalid claim type: cell_id")

        if expected_cell_id and token_cell_id and token_cell_id != expected_cell_id:
            self._record_identity_failure(
                reason="jwt_cell_binding_mismatch",
                provider="keycloak",
            )
            raise TokenValidationError(
                f"Token bound to cell {token_cell_id!r}, expected {expected_cell_id!r}"
            )

        roles = map_roles_from_claims(payload, client_id=self._client_id)
        mfa_verified = infer_mfa_verified(payload)
        if roles & self._required_mfa_roles and not mfa_verified:
            self._record_identity_failure(reason="jwt_mfa_required", provider="keycloak")
            raise MFARequiredError(
                f"MFA is required for roles: {sorted(role.value for role in roles)}"
            )

        aud_claim = payload.get("aud", self._audience)
        if isinstance(aud_claim, list):
            aud = str(aud_claim[0]) if aud_claim else self._audience
        else:
            aud = str(aud_claim)

        return UserIdentityClaims(
            sub=str(payload["sub"]),
            email=str(payload.get("email", "")),
            tenant_id=tenant_id,
            cell_id=token_cell_id,
            roles=roles,
            mfa_verified=mfa_verified,
            iss=str(payload["iss"]),
            aud=aud,
            exp=int(payload["exp"]),
            iat=int(payload["iat"]),
            jti=str(payload.get("jti", "")),
        )

    def _validated_jwt_key_id(self, pyjwt_module: Any, jwt_token: str) -> str:
        """Validate JWT `kid` against active and revoked rotation sets."""
        try:
            header = pyjwt_module.get_unverified_header(jwt_token)
        except Exception as exc:
            self._record_identity_failure(reason="jwt_invalid_header", provider="keycloak")
            raise TokenValidationError(f"Token header validation failed: {exc}") from exc
        key_id = str(header.get("kid", "")).strip()
        if not key_id:
            self._record_identity_failure(reason="jwt_missing_kid", provider="keycloak")
            raise TokenValidationError("Missing JWT key id (kid)")
        if key_id in self._revoked_jwt_kids:
            self._record_identity_failure(reason="jwt_revoked_kid", provider="keycloak")
            raise TokenValidationError("JWT signing key has been revoked")
        if self._allowed_jwt_kids and key_id not in self._allowed_jwt_kids:
            self._record_identity_failure(reason="jwt_untrusted_kid", provider="keycloak")
            raise TokenValidationError("JWT signing key is not in the active trust set")
        return key_id

    def _get_jwks_client(self, pyjwt_module: Any) -> Any:
        now = time.time()
        cached = self._jwks_cache.get("client")
        if cached is not None and now < self._jwks_cache_expires:
            return cached
        with self._jwks_lock:
            cached = self._jwks_cache.get("client")
            if cached is not None and now < self._jwks_cache_expires:
                return cached
            client = pyjwt_module.PyJWKClient(
                self._jwks_uri,
                cache_jwk_set=True,
                lifespan=self._jwks_cache_ttl_seconds,
            )
            self._jwks_cache["client"] = client
            self._jwks_cache_expires = now + float(self._jwks_cache_ttl_seconds)
            return client

    @staticmethod
    def _parse_spiffe_id(spiffe_id: str) -> dict[str, str]:
        if not spiffe_id.startswith("spiffe://"):
            raise IdentityVerificationError(f"Invalid SPIFFE ID format: {spiffe_id}")

        parts = spiffe_id.removeprefix("spiffe://").split("/")
        # trust-domain / cell / <cell-id> / svc / <service-name>
        if len(parts) < 5 or parts[1] != "cell" or parts[3] != "svc":
            raise IdentityVerificationError(
                f"SPIFFE ID does not match expected schema: {spiffe_id}"
            )

        return {
            "trust_domain": parts[0],
            "cell_id": parts[2],
            "service_name": parts[4],
        }


def _load_spiffe_workload_client_type() -> type[Any] | None:
    try:
        spiffe_module = import_module("spiffe")
    except ModuleNotFoundError:
        return None
    workload_client_type = getattr(spiffe_module, "WorkloadApiClient", None)
    return workload_client_type if isinstance(workload_client_type, type) else None


__all__ = [
    "ROLE_PII_CEILING",
    "MFARequiredError",
    "PIIAccessLevel",
    "PolicyOSRole",
    "SPIFFEIdentityProvider",
    "ServiceIdentity",
    "ServiceIdentityInfo",
    "TokenValidationError",
    "UserIdentityClaims",
    "infer_mfa_verified",
    "map_roles_from_claims",
]
