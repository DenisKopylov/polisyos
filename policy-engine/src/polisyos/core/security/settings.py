from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class SecuritySettings:
    """Runtime settings for tenant isolation and Zero Trust components."""

    POLISYOS_MULTI_TENANT_ENABLED: bool = False
    POLISYOS_CELL_REGISTRY_PATH: str = ""
    POLISYOS_DEFAULT_CELL_TIER: str = "shared"
    POLISYOS_ALLOWED_REGIONS: str = ""
    POLISYOS_MULTI_TENANT_FAIL_CLOSED: bool = True

    POLISYOS_AUTHN_ENABLED: bool = False
    POLISYOS_AUTHZ_MODE: str = "off"  # off|shadow|enforce
    POLISYOS_EXTERNAL_TENANT_HEADER_FALLBACK: bool = True

    POLISYOS_KEYCLOAK_ISSUER_URL: str = ""
    POLISYOS_KEYCLOAK_JWKS_URI: str = ""
    POLISYOS_KEYCLOAK_CLIENT_ID: str = "polisyos-web"
    POLISYOS_KEYCLOAK_AUDIENCE: str = "polisyos-web"
    POLISYOS_JWT_REQUIRED_MFA_ROLES: str = "admin,analyst"

    POLISYOS_OPA_URL: str = "http://localhost:8181"
    POLISYOS_OPA_POLICY_PATH: str = "polisyos/authz/decision"
    POLISYOS_OPA_TIMEOUT: float = 2.0
    POLISYOS_OPA_CACHE_TTL: float = 30.0
    POLISYOS_OPA_CACHE_SIZE: int = 1000

    POLISYOS_MTLS_SPIFFE_HEADER: str = "l5d-client-id"

    POLISYOS_DELEGATION_REQUIRED: bool = False
    POLISYOS_DELEGATION_HEADER: str = "x-policyos-context"
    POLISYOS_DELEGATION_SECRET: str = ""
    POLISYOS_DELEGATION_ALGORITHM: str = "HS256"
    POLISYOS_DELEGATION_TTL_SECONDS: int = 60
    POLISYOS_TRUSTED_DELEGATORS: str = ""

    def allowed_regions(self) -> set[str]:
        return {
            region.strip()
            for region in self.POLISYOS_ALLOWED_REGIONS.split(",")
            if region.strip()
        }

    def trusted_delegators(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.POLISYOS_TRUSTED_DELEGATORS.split(",")
            if item.strip()
        )

    def required_mfa_roles(self) -> frozenset[str]:
        return frozenset(
            item.strip().lower()
            for item in self.POLISYOS_JWT_REQUIRED_MFA_ROLES.split(",")
            if item.strip()
        )

    @property
    def authz_enforce(self) -> bool:
        return self.POLISYOS_AUTHZ_MODE.strip().lower() == "enforce"

    @property
    def authz_shadow(self) -> bool:
        return self.POLISYOS_AUTHZ_MODE.strip().lower() == "shadow"


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    return SecuritySettings(
        POLISYOS_MULTI_TENANT_ENABLED=_parse_bool(
            os.getenv("POLISYOS_MULTI_TENANT_ENABLED"),
            False,
        ),
        POLISYOS_CELL_REGISTRY_PATH=os.getenv("POLISYOS_CELL_REGISTRY_PATH", ""),
        POLISYOS_DEFAULT_CELL_TIER=os.getenv("POLISYOS_DEFAULT_CELL_TIER", "shared"),
        POLISYOS_ALLOWED_REGIONS=os.getenv(
            "POLISYOS_ALLOWED_REGIONS",
            "",
        ),
        POLISYOS_MULTI_TENANT_FAIL_CLOSED=_parse_bool(
            os.getenv("POLISYOS_MULTI_TENANT_FAIL_CLOSED"),
            True,
        ),
        POLISYOS_AUTHN_ENABLED=_parse_bool(os.getenv("POLISYOS_AUTHN_ENABLED"), False),
        POLISYOS_AUTHZ_MODE=os.getenv("POLISYOS_AUTHZ_MODE", "off"),
        POLISYOS_EXTERNAL_TENANT_HEADER_FALLBACK=_parse_bool(
            os.getenv("POLISYOS_EXTERNAL_TENANT_HEADER_FALLBACK"),
            True,
        ),
        POLISYOS_KEYCLOAK_ISSUER_URL=os.getenv("POLISYOS_KEYCLOAK_ISSUER_URL", ""),
        POLISYOS_KEYCLOAK_JWKS_URI=os.getenv("POLISYOS_KEYCLOAK_JWKS_URI", ""),
        POLISYOS_KEYCLOAK_CLIENT_ID=os.getenv("POLISYOS_KEYCLOAK_CLIENT_ID", "polisyos-web"),
        POLISYOS_KEYCLOAK_AUDIENCE=os.getenv("POLISYOS_KEYCLOAK_AUDIENCE", "polisyos-web"),
        POLISYOS_JWT_REQUIRED_MFA_ROLES=os.getenv(
            "POLISYOS_JWT_REQUIRED_MFA_ROLES", "admin,analyst"
        ),
        POLISYOS_OPA_URL=os.getenv("POLISYOS_OPA_URL", "http://localhost:8181"),
        POLISYOS_OPA_POLICY_PATH=os.getenv("POLISYOS_OPA_POLICY_PATH", "polisyos/authz/decision"),
        POLISYOS_OPA_TIMEOUT=_parse_float(os.getenv("POLISYOS_OPA_TIMEOUT"), 2.0),
        POLISYOS_OPA_CACHE_TTL=_parse_float(os.getenv("POLISYOS_OPA_CACHE_TTL"), 30.0),
        POLISYOS_OPA_CACHE_SIZE=_parse_int(os.getenv("POLISYOS_OPA_CACHE_SIZE"), 1000),
        POLISYOS_MTLS_SPIFFE_HEADER=os.getenv("POLISYOS_MTLS_SPIFFE_HEADER", "l5d-client-id"),
        POLISYOS_DELEGATION_REQUIRED=_parse_bool(
            os.getenv("POLISYOS_DELEGATION_REQUIRED"),
            False,
        ),
        POLISYOS_DELEGATION_HEADER=os.getenv("POLISYOS_DELEGATION_HEADER", "x-policyos-context"),
        POLISYOS_DELEGATION_SECRET=os.getenv("POLISYOS_DELEGATION_SECRET", ""),
        POLISYOS_DELEGATION_ALGORITHM=os.getenv("POLISYOS_DELEGATION_ALGORITHM", "HS256"),
        POLISYOS_DELEGATION_TTL_SECONDS=_parse_int(
            os.getenv("POLISYOS_DELEGATION_TTL_SECONDS"),
            60,
        ),
        POLISYOS_TRUSTED_DELEGATORS=os.getenv("POLISYOS_TRUSTED_DELEGATORS", ""),
    )


__all__ = ["SecuritySettings", "get_security_settings"]
