"""Resolve Zero Trust, OPA, TEE, SBOM, and multi-tenant settings from env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from polisyos.common.env_parsing import parse_bool as _parse_bool
from polisyos.common.env_parsing import parse_float as _parse_float
from polisyos.common.env_parsing import parse_int as _parse_int


@dataclass(frozen=True)
class SecuritySettings:
    """Runtime settings for tenant isolation and Zero Trust components."""

    POLISYOS_ENV: str = "dev"  # dev|prod|airgap
    POLISYOS_DB_BACKEND: str = ""  # postgres|duckdb (empty = auto by env profile)

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
    POLISYOS_JWT_ALLOWED_KIDS: str = ""
    POLISYOS_JWT_REVOKED_KIDS: str = ""
    POLISYOS_JWKS_CACHE_TTL_SECONDS: int = 300

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

    POLISYOS_PII_ENABLED: bool = True

    POLISYOS_TEE_ENABLED: bool = False
    POLISYOS_TEE_REQUIRED: bool = False
    POLISYOS_TEE_PLATFORM: str = "sev-snp"
    POLISYOS_TEE_REPORT_PATH: str = ""
    POLISYOS_TEE_MAX_REPORT_AGE_SECONDS: int = 300
    POLISYOS_TEE_MIN_TCB_VERSION: int = 0
    POLISYOS_TEE_MIN_GUEST_SVN: int = 0
    POLISYOS_TEE_EXPECTED_MEASUREMENTS: str = ""
    POLISYOS_TEE_EXPECTED_HOST_DATA: str = ""
    POLISYOS_TEE_REQUIRE_SIGNATURE_VALIDATION: bool = True
    POLISYOS_TEE_CACHE_TTL_SECONDS: int = 300
    POLISYOS_TEE_ENFORCE_TIERS: str = "dedicated"

    POLISYOS_SBOM_ENABLED: bool = False
    POLISYOS_SBOM_PATH: str = ""
    POLISYOS_SBOM_CVSS_THRESHOLD: float = 7.0
    POLISYOS_SBOM_GRYPE_DB_PATH: str = ""
    POLISYOS_SBOM_ALLOWED_CVES: str = ""

    @lru_cache(maxsize=1)
    def allowed_regions(self) -> frozenset[str]:
        """Return normalized region allowlist values used by cell/tenant routing."""
        return frozenset(
            region.strip() for region in self.POLISYOS_ALLOWED_REGIONS.split(",") if region.strip()
        )

    @lru_cache(maxsize=1)
    def trusted_delegators(self) -> frozenset[str]:
        """Return SPIFFE/service principals allowed to forward delegation context."""
        return frozenset(
            item.strip() for item in self.POLISYOS_TRUSTED_DELEGATORS.split(",") if item.strip()
        )

    @lru_cache(maxsize=1)
    def required_mfa_roles(self) -> frozenset[str]:
        """Return lowercased role names that require MFA in JWT validation."""
        return frozenset(
            item.strip().lower()
            for item in self.POLISYOS_JWT_REQUIRED_MFA_ROLES.split(",")
            if item.strip()
        )

    @lru_cache(maxsize=1)
    def allowed_jwt_kids(self) -> frozenset[str]:
        """Return JWT signing key IDs accepted during the current rotation window."""
        return frozenset(
            item.strip() for item in self.POLISYOS_JWT_ALLOWED_KIDS.split(",") if item.strip()
        )

    @lru_cache(maxsize=1)
    def revoked_jwt_kids(self) -> frozenset[str]:
        """Return JWT signing key IDs that must be rejected even if JWKS exposes them."""
        return frozenset(
            item.strip() for item in self.POLISYOS_JWT_REVOKED_KIDS.split(",") if item.strip()
        )

    @lru_cache(maxsize=1)
    def tee_expected_measurements(self) -> tuple[str, ...]:
        """Return normalized launch measurements accepted by TEE attestation policy."""
        return tuple(
            item.strip().lower()
            for item in self.POLISYOS_TEE_EXPECTED_MEASUREMENTS.split(",")
            if item.strip()
        )

    @lru_cache(maxsize=1)
    def tee_enforce_tiers(self) -> frozenset[str]:
        """Return cell tiers that must pass the TEE gatekeeper."""
        return frozenset(
            item.strip().lower()
            for item in self.POLISYOS_TEE_ENFORCE_TIERS.split(",")
            if item.strip()
        )

    @lru_cache(maxsize=1)
    def sbom_allowed_cves(self) -> frozenset[str]:
        """Return uppercase CVE IDs exempted from SBOM gate failures."""
        return frozenset(
            item.strip().upper()
            for item in self.POLISYOS_SBOM_ALLOWED_CVES.split(",")
            if item.strip()
        )

    @property
    def authz_enforce(self) -> bool:
        """Return `True` when OPA decisions should block requests."""
        return self.POLISYOS_AUTHZ_MODE.strip().lower() == "enforce"

    @property
    def authz_shadow(self) -> bool:
        """Return `True` when OPA decisions are logged but not enforced."""
        return self.POLISYOS_AUTHZ_MODE.strip().lower() == "shadow"

    @property
    def normalized_env(self) -> str:
        """Normalize `POLISYOS_ENV` into `dev`, `prod`, or `airgap`."""
        env = self.POLISYOS_ENV.strip().lower()
        if env in {"production", "prod"}:
            return "prod"
        if env in {"airgap", "air-gapped"}:
            return "airgap"
        return "dev"

    @property
    def is_prod(self) -> bool:
        """Return `True` for production posture."""
        return self.normalized_env == "prod"

    @property
    def is_airgap(self) -> bool:
        """Return `True` for air-gapped deployment posture."""
        return self.normalized_env == "airgap"

    @property
    def is_dev(self) -> bool:
        """Return `True` for developer/local posture."""
        return self.normalized_env == "dev"

    @property
    def db_backend(self) -> str:
        """Return explicit DB backend or derive a safe default from deployment posture."""
        explicit = self.POLISYOS_DB_BACKEND.strip().lower()
        if explicit:
            return explicit
        return "postgres" if self.is_prod else "duckdb"

    @property
    def tee_enabled(self) -> bool:
        """Return whether TEE checks should run for this process."""
        return self.POLISYOS_TEE_ENABLED or self.is_prod

    @property
    def tee_required(self) -> bool:
        """Return whether TEE failures must block execution for this process."""
        if self.POLISYOS_TEE_REQUIRED:
            return True
        return self.tee_enabled and self.is_prod


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    """Return cached security settings resolved from `POLISYOS_*` env vars.

    The resolver derives safe defaults from `POLISYOS_ENV`: production enables
    authn/authz/TEE/SBOM by default, while dev keeps those controls optional
    unless explicitly turned on.
    """
    env_name = os.getenv("POLISYOS_ENV", "dev").strip().lower()
    default_tee_enabled = env_name in {"prod", "production"}
    default_tee_required = env_name in {"prod", "production"}
    default_authn_enabled = env_name in {"prod", "production"}
    default_authz_mode = "enforce" if env_name in {"prod", "production"} else "off"
    default_pii_enabled = env_name in {"prod", "production", "airgap"}
    default_sbom_enabled = env_name in {"prod", "production", "airgap"}

    return SecuritySettings(
        POLISYOS_ENV=os.getenv("POLISYOS_ENV", "dev"),
        POLISYOS_DB_BACKEND=os.getenv("POLISYOS_DB_BACKEND", ""),
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
        POLISYOS_AUTHN_ENABLED=_parse_bool(
            os.getenv("POLISYOS_AUTHN_ENABLED"),
            default_authn_enabled,
        ),
        POLISYOS_AUTHZ_MODE=os.getenv("POLISYOS_AUTHZ_MODE", default_authz_mode),
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
        POLISYOS_JWT_ALLOWED_KIDS=os.getenv("POLISYOS_JWT_ALLOWED_KIDS", ""),
        POLISYOS_JWT_REVOKED_KIDS=os.getenv("POLISYOS_JWT_REVOKED_KIDS", ""),
        POLISYOS_JWKS_CACHE_TTL_SECONDS=_parse_int(
            os.getenv("POLISYOS_JWKS_CACHE_TTL_SECONDS"),
            300,
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
        POLISYOS_PII_ENABLED=_parse_bool(
            os.getenv("POLISYOS_PII_ENABLED"),
            default_pii_enabled,
        ),
        POLISYOS_TEE_ENABLED=_parse_bool(
            os.getenv("POLISYOS_TEE_ENABLED"),
            default_tee_enabled,
        ),
        POLISYOS_TEE_REQUIRED=_parse_bool(
            os.getenv("POLISYOS_TEE_REQUIRED"),
            default_tee_required,
        ),
        POLISYOS_TEE_PLATFORM=os.getenv("POLISYOS_TEE_PLATFORM", "sev-snp"),
        POLISYOS_TEE_REPORT_PATH=os.getenv("POLISYOS_TEE_REPORT_PATH", ""),
        POLISYOS_TEE_MAX_REPORT_AGE_SECONDS=_parse_int(
            os.getenv("POLISYOS_TEE_MAX_REPORT_AGE_SECONDS"),
            300,
        ),
        POLISYOS_TEE_MIN_TCB_VERSION=_parse_int(
            os.getenv("POLISYOS_TEE_MIN_TCB_VERSION"),
            0,
        ),
        POLISYOS_TEE_MIN_GUEST_SVN=_parse_int(
            os.getenv("POLISYOS_TEE_MIN_GUEST_SVN"),
            0,
        ),
        POLISYOS_TEE_EXPECTED_MEASUREMENTS=os.getenv(
            "POLISYOS_TEE_EXPECTED_MEASUREMENTS",
            "",
        ),
        POLISYOS_TEE_EXPECTED_HOST_DATA=os.getenv("POLISYOS_TEE_EXPECTED_HOST_DATA", ""),
        POLISYOS_TEE_REQUIRE_SIGNATURE_VALIDATION=_parse_bool(
            os.getenv("POLISYOS_TEE_REQUIRE_SIGNATURE_VALIDATION"),
            True,
        ),
        POLISYOS_TEE_CACHE_TTL_SECONDS=_parse_int(
            os.getenv("POLISYOS_TEE_CACHE_TTL_SECONDS"),
            300,
        ),
        POLISYOS_TEE_ENFORCE_TIERS=os.getenv("POLISYOS_TEE_ENFORCE_TIERS", "dedicated"),
        POLISYOS_SBOM_ENABLED=_parse_bool(
            os.getenv("POLISYOS_SBOM_ENABLED"),
            default_sbom_enabled,
        ),
        POLISYOS_SBOM_PATH=os.getenv("POLISYOS_SBOM_PATH", ""),
        POLISYOS_SBOM_CVSS_THRESHOLD=_parse_float(
            os.getenv("POLISYOS_SBOM_CVSS_THRESHOLD"),
            7.0,
        ),
        POLISYOS_SBOM_GRYPE_DB_PATH=os.getenv("POLISYOS_SBOM_GRYPE_DB_PATH", ""),
        POLISYOS_SBOM_ALLOWED_CVES=os.getenv("POLISYOS_SBOM_ALLOWED_CVES", ""),
    )


__all__ = ["SecuritySettings", "get_security_settings"]
