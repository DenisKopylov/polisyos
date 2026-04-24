"""Access scope model propagated with each authenticated request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole, UserIdentityClaims


@dataclass(frozen=True, slots=True)
class AccessScope:
    """Immutable per-request access scope used by authz and observability."""

    tenant_id: str
    cell_id: str | None
    principal_type: str
    user_sub: str
    roles: frozenset[PolicyOSRole]
    max_pii_tier: PIIAccessLevel
    mfa_verified: bool
    spiffe_id: str = ""
    delegation_jti: str = ""
    jwt_jti: str = ""

    @staticmethod
    def from_user_claims(claims: UserIdentityClaims) -> AccessScope:
        return AccessScope(
            tenant_id=claims.tenant_id,
            cell_id=claims.cell_id,
            principal_type="user",
            user_sub=claims.sub,
            roles=claims.roles,
            max_pii_tier=claims.max_pii_access,
            mfa_verified=claims.mfa_verified,
            jwt_jti=claims.jti,
        )

    @staticmethod
    def for_service(
        *,
        tenant_id: str,
        cell_id: str | None,
        spiffe_id: str,
        roles: frozenset[PolicyOSRole] | None = None,
    ) -> AccessScope:
        return AccessScope(
            tenant_id=tenant_id,
            cell_id=cell_id,
            principal_type="service",
            user_sub="",
            roles=roles or frozenset({PolicyOSRole.SERVICE}),
            max_pii_tier=PIIAccessLevel.HIGH,
            mfa_verified=False,
            spiffe_id=spiffe_id,
        )

    def to_otel_attributes(self) -> dict[str, str]:
        return {
            "tenant.id": self.tenant_id,
            "tenant.cell_id": self.cell_id or "",
            "identity.principal_type": self.principal_type,
            "identity.user_sub": self.user_sub,
            "identity.spiffe_id": self.spiffe_id,
            "authz.roles": ",".join(sorted(role.value for role in self.roles)),
            "authz.max_pii_tier": self.max_pii_tier.value,
            "authz.mfa_verified": str(self.mfa_verified).lower(),
            "authz.delegation_jti": self.delegation_jti,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "cell_id": self.cell_id,
            "principal_type": self.principal_type,
            "user_sub": self.user_sub,
            "roles": [role.value for role in sorted(self.roles, key=lambda r: r.value)],
            "max_pii_tier": self.max_pii_tier.value,
            "mfa_verified": self.mfa_verified,
            "spiffe_id": self.spiffe_id,
            "delegation_jti": self.delegation_jti,
            "jwt_jti": self.jwt_jti,
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> AccessScope:
        roles_raw = raw.get("roles")
        if isinstance(roles_raw, list):
            roles = frozenset(PolicyOSRole(str(item)) for item in roles_raw)
        else:
            roles = frozenset({PolicyOSRole.VIEWER})

        return AccessScope(
            tenant_id=str(raw.get("tenant_id", "")),
            cell_id=str(raw["cell_id"]) if raw.get("cell_id") else None,
            principal_type=str(raw.get("principal_type", "user")),
            user_sub=str(raw.get("user_sub", "")),
            roles=roles,
            max_pii_tier=PIIAccessLevel(str(raw.get("max_pii_tier", "none"))),
            mfa_verified=bool(raw.get("mfa_verified", False)),
            spiffe_id=str(raw.get("spiffe_id", "")),
            delegation_jti=str(raw.get("delegation_jti", "")),
            jwt_jti=str(raw.get("jwt_jti", "")),
        )


__all__ = ["AccessScope"]
