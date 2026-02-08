"""Signed delegation token for secure propagation of user context between services."""
from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.exceptions import DelegationError, DelegationVerificationError
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole


class DelegationContextClaims(BaseModel):
    """Claims carried by signed delegation token."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iss: str = Field(min_length=1)
    aud: str = Field(min_length=1)
    iat: int
    exp: int
    jti: str = Field(min_length=1)

    tenant_id: str = Field(min_length=1)
    cell_id: str | None = None
    principal_type: str = "user"
    user_sub: str = ""
    roles: tuple[str, ...] = ()
    max_pii_tier: str = PIIAccessLevel.NONE.value
    mfa_verified: bool = False
    spiffe_id: str = ""

    jwt_jti: str = ""
    parent_delegation_jti: str = ""
    trace_id: str = ""

    def to_access_scope(self) -> AccessScope:
        parsed_roles = frozenset(PolicyOSRole(role) for role in self.roles) or frozenset(
            {PolicyOSRole.VIEWER}
        )
        return AccessScope(
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            principal_type=self.principal_type,
            user_sub=self.user_sub,
            roles=parsed_roles,
            max_pii_tier=PIIAccessLevel(self.max_pii_tier),
            mfa_verified=self.mfa_verified,
            spiffe_id=self.spiffe_id,
            delegation_jti=self.jti,
            jwt_jti=self.jwt_jti,
        )


class DelegationTokenManager:
    """Issues and verifies signed delegation tokens.

    Default algorithm is HS256 with a shared secret. It can be switched to any
    PyJWT-supported algorithm by changing configuration and key material.
    """

    def __init__(
        self,
        *,
        signing_key: str,
        algorithm: str = "HS256",
        ttl_seconds: int = 60,
        clock_skew_seconds: int = 5,
    ) -> None:
        if not signing_key:
            raise DelegationError("Delegation signing key must not be empty")
        self._signing_key = signing_key
        self._algorithm = algorithm
        self._ttl = max(ttl_seconds, 1)
        self._clock_skew = max(clock_skew_seconds, 0)

    def issue_token(
        self,
        *,
        scope: AccessScope,
        issuer: str,
        audience: str,
        trace_id: str = "",
    ) -> str:
        """Issue short-lived signed delegation token from an AccessScope."""

        now = datetime.now(timezone.utc)
        claims = DelegationContextClaims(
            iss=issuer,
            aud=audience,
            iat=int(now.timestamp()),
            exp=int((now + timedelta(seconds=self._ttl)).timestamp()),
            jti=f"dlg_{secrets.token_hex(8)}",
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            principal_type=scope.principal_type,
            user_sub=scope.user_sub,
            roles=tuple(sorted(role.value for role in scope.roles)),
            max_pii_tier=scope.max_pii_tier.value,
            mfa_verified=scope.mfa_verified,
            spiffe_id=scope.spiffe_id,
            jwt_jti=scope.jwt_jti,
            parent_delegation_jti=scope.delegation_jti,
            trace_id=trace_id,
        )

        try:
            import jwt as pyjwt
        except ModuleNotFoundError as exc:
            raise DelegationError(
                "PyJWT is required for delegation tokens. Install policy-engine[multi-tenant]."
            ) from exc

        return str(
            pyjwt.encode(
                claims.model_dump(mode="json"),
                self._signing_key,
                algorithm=self._algorithm,
            )
        )

    def verify_token(
        self,
        token: str,
        *,
        expected_audience: str,
        trusted_issuers: frozenset[str],
    ) -> DelegationContextClaims:
        """Verify delegation token and return normalized claims."""

        try:
            import jwt as pyjwt
        except ModuleNotFoundError as exc:
            raise DelegationVerificationError(
                "PyJWT is required for delegation token verification"
            ) from exc

        try:
            payload = pyjwt.decode(
                token,
                self._signing_key,
                algorithms=[self._algorithm],
                audience=expected_audience,
                options={"require": ["iss", "aud", "exp", "iat", "jti", "tenant_id"]},
                leeway=self._clock_skew,
            )
        except pyjwt.InvalidTokenError as exc:
            raise DelegationVerificationError(f"Invalid delegation token: {exc}") from exc

        claims = DelegationContextClaims.model_validate(payload)
        if claims.iss not in trusted_issuers:
            raise DelegationVerificationError(
                f"Delegation issuer {claims.iss!r} is not trusted"
            )
        return claims

    def reissue_for_hop(
        self,
        *,
        token: str,
        expected_audience: str,
        trusted_issuers: frozenset[str],
        new_issuer: str,
        new_audience: str,
        trace_id: str = "",
    ) -> str:
        """Verify and reissue token for the next hop preserving principal context."""

        claims = self.verify_token(
            token,
            expected_audience=expected_audience,
            trusted_issuers=trusted_issuers,
        )
        scope = claims.to_access_scope()
        scope = replace(scope, delegation_jti=claims.jti)
        return self.issue_token(
            scope=scope,
            issuer=new_issuer,
            audience=new_audience,
            trace_id=trace_id,
        )


__all__ = ["DelegationContextClaims", "DelegationTokenManager"]
