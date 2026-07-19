"""Deployment-owned identity, policy, and step-up verifier composition.

This module is the single Runtime HTTP bootstrap path for production security
collaborators.  It deliberately contains no bearer token or signing secret:
operators inject the short-lived caller token separately, while this contract
resolves only verification endpoints, public key policy, provenance, cell
placement, OPA, and exact service-principal action grants.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.security.authz import OPAClient
from polisyos.core.security.exceptions import TenantNotFoundError, TokenValidationError
from polisyos.core.security.identity import SPIFFEIdentityProvider, UserIdentityClaims
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.authorization import (
    CANONICAL_ROLE_AUTHORIZATION_SOURCE,
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    DeploymentPrincipalGrantResolver,
)
from polisyos.runtime.http.permissions import RuntimePermission  # noqa: TC001
from polisyos.runtime.http.step_up import JWTStepUpAssertionVerifier

_CONFIG_PATH_ENV = "POLISYOS_RUNTIME_SERVICE_PRINCIPAL_GRANTS_PATH"
_TRUSTED_JWT_ALGORITHMS = frozenset({"RS256", "ES256", "EdDSA"})


def _non_empty(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


class VerifierProvenance(BaseModel):
    """Name the deployment source of verifier trust without retaining secrets."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source: str = Field(min_length=1)
    reference: str = Field(min_length=1)

    @field_validator("source", "reference")
    @classmethod
    def _validate_provenance_text(cls, value: str) -> str:
        return _non_empty(value, field_name="verifier provenance")


class _VerifierTrustConfig(BaseModel):
    """Shared public-key verifier trust policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    algorithms: tuple[str, ...]
    jwks_uri: str = Field(min_length=1)
    allowed_key_ids: frozenset[str]
    revoked_key_ids: frozenset[str] = frozenset()
    provenance: VerifierProvenance

    @field_validator("issuer", "audience", "jwks_uri")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        return _non_empty(value, field_name="verifier field")

    @field_validator("algorithms")
    @classmethod
    def _validate_algorithms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not normalized:
            raise ValueError("verifier algorithms must be an explicit trusted set")
        unknown = set(normalized) - _TRUSTED_JWT_ALGORITHMS
        if unknown:
            raise ValueError(f"untrusted verifier algorithms: {sorted(unknown)}")
        return normalized

    @field_validator("allowed_key_ids", "revoked_key_ids")
    @classmethod
    def _validate_key_ids(cls, value: frozenset[str]) -> frozenset[str]:
        normalized = frozenset(item.strip() for item in value if item.strip())
        if len(normalized) != len(value):
            raise ValueError("verifier key ids must be non-empty trimmed strings")
        return normalized

    @model_validator(mode="after")
    def _validate_rotation_policy(self) -> Self:
        if not self.allowed_key_ids:
            raise ValueError("verifier allowed_key_ids must declare the active key set")
        overlap = self.allowed_key_ids & self.revoked_key_ids
        if overlap:
            raise ValueError(f"verifier key ids cannot be active and revoked: {sorted(overlap)}")
        return self


class IdentityVerifierConfig(_VerifierTrustConfig):
    """OIDC/JWKS verification policy for genuine runtime bearer identity."""

    keycloak_client_id: str = "polisyos-runtime"
    jwks_cache_ttl_seconds: int = Field(default=300, ge=1, le=86_400)


class StepUpVerifierConfig(_VerifierTrustConfig):
    """Fresh one-use step-up assertion verification policy."""

    maximum_age_seconds: int = Field(gt=0, le=3_600)
    clock_skew_seconds: int = Field(default=30, ge=0, le=300)


class OPADeploymentConfig(BaseModel):
    """Deployment endpoint and timeout for the canonical OPA decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    url: str = Field(min_length=1)
    policy_path: str = Field(default="polisyos/authz/decision", min_length=1)
    timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @field_validator("url", "policy_path")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        return _non_empty(value, field_name="OPA deployment field")


class ServicePrincipalGrant(BaseModel):
    """Bind one external principal identity to an exact canonical action set."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    permissions: frozenset[RuntimePermission] = Field(min_length=1)

    @field_validator("issuer", "audience", "subject", "tenant_id", "cell_id")
    @classmethod
    def _validate_binding_text(cls, value: str) -> str:
        return _non_empty(value, field_name="service-principal binding")

    @property
    def identity_key(self) -> tuple[str, str, str, str, str]:
        """Return the exact issuer/audience/subject/tenant/cell identity tuple."""
        return (
            self.issuer.rstrip("/"),
            self.audience,
            self.subject,
            self.tenant_id,
            self.cell_id,
        )


class DeploymentSecurityConfig(BaseModel):
    """Strict authored deployment contract for the Runtime security chain."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    identity_verifier: IdentityVerifierConfig
    step_up_verifier: StepUpVerifierConfig
    cell_registry_path: Path
    opa: OPADeploymentConfig
    service_principals: tuple[ServicePrincipalGrant, ...] = ()

    @model_validator(mode="after")
    def _validate_unique_principals(self) -> Self:
        keys = [grant.identity_key for grant in self.service_principals]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate exact service principal binding")
        return self

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> DeploymentSecurityConfig:
        """Validate an already-resolved deployment configuration mapping."""
        if not isinstance(raw, Mapping):
            raise TypeError("deployment security configuration must be a mapping")
        return cls.model_validate(dict(raw))

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> DeploymentSecurityConfig:
        """Load the strict deployment document from its configured filesystem path.

        The historical environment name is retained for compatibility with the
        ratified ops contract. The referenced JSON contains the whole public
        verification/grant document, not a bearer or signing secret.
        """
        resolved = os.environ if env is None else env
        raw_path = str(resolved.get(_CONFIG_PATH_ENV, "")).strip()
        if not raw_path:
            raise ValueError(f"{_CONFIG_PATH_ENV} is required")
        path = Path(raw_path).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"deployment security configuration is unreadable: {path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("deployment security configuration must contain a JSON object")
        return cls.from_mapping(payload)


class DeploymentJWTStepUpAssertionVerifier(JWTStepUpAssertionVerifier):
    """JWT verifier whose trust is proven by a strict deployment contract."""

    def __init__(self, config: StepUpVerifierConfig) -> None:
        if type(config) is not StepUpVerifierConfig:
            raise TypeError("config must be a StepUpVerifierConfig")
        super().__init__(
            issuer=config.issuer,
            audience=config.audience,
            algorithms=config.algorithms,
            maximum_age_seconds=config.maximum_age_seconds,
            clock_skew_seconds=config.clock_skew_seconds,
            jwks_uri=config.jwks_uri,
            allowed_key_ids=config.allowed_key_ids,
            revoked_key_ids=config.revoked_key_ids,
        )
        self._deployment_provenance = config.provenance

    @property
    def deployment_provenance(self) -> VerifierProvenance:
        """Return the non-secret configuration source that established trust."""
        return self._deployment_provenance


class DeploymentIdentityProvider(SPIFFEIdentityProvider):
    """OIDC provider constrained to the exact deployment algorithm/provenance policy."""

    def __init__(self, config: IdentityVerifierConfig) -> None:
        if type(config) is not IdentityVerifierConfig:
            raise TypeError("config must be an IdentityVerifierConfig")
        super().__init__(
            keycloak_issuer_url=config.issuer,
            keycloak_jwks_uri=config.jwks_uri,
            expected_audience=config.audience,
            keycloak_client_id=config.keycloak_client_id,
            allowed_jwt_kids=config.allowed_key_ids,
            revoked_jwt_kids=config.revoked_key_ids,
            jwks_cache_ttl_seconds=config.jwks_cache_ttl_seconds,
        )
        self._deployment_algorithms = frozenset(config.algorithms)
        self._deployment_provenance = config.provenance

    @property
    def deployment_provenance(self) -> VerifierProvenance:
        """Return the non-secret configuration source that established trust."""
        return self._deployment_provenance

    def extract_user_claims(
        self,
        jwt_token: str,
        *,
        expected_cell_id: str | None = None,
    ) -> UserIdentityClaims:
        """Reject algorithms outside the deployment set before normal JWT verification."""
        try:
            import jwt as pyjwt

            header = pyjwt.get_unverified_header(jwt_token)
        except Exception as exc:
            raise TokenValidationError("Token header validation failed") from exc
        algorithm = str(header.get("alg", "")).strip()
        if algorithm not in self._deployment_algorithms:
            raise TokenValidationError("JWT algorithm is not trusted by deployment policy")
        return super().extract_user_claims(
            jwt_token,
            expected_cell_id=expected_cell_id,
        )


@dataclass(frozen=True, slots=True)
class RuntimeDeploymentSecurity:
    """Resolved genuine collaborators plus exact service-principal grants."""

    config: DeploymentSecurityConfig
    identity_provider: DeploymentIdentityProvider = field(repr=False)
    cell_registry: CellRegistry = field(repr=False)
    opa_client: OPAClient = field(repr=False)
    step_up_verifier: DeploymentJWTStepUpAssertionVerifier = field(repr=False)
    principal_grants: DeploymentPrincipalGrantResolver = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.config) is not DeploymentSecurityConfig:
            raise TypeError("config must be a DeploymentSecurityConfig")
        if type(self.identity_provider) is not DeploymentIdentityProvider:
            raise TypeError("identity_provider must come from deployment configuration")
        if type(self.cell_registry) is not CellRegistry:
            raise TypeError("cell_registry must come from deployment configuration")
        if type(self.opa_client) is not OPAClient:
            raise TypeError("opa_client must come from deployment configuration")
        if type(self.step_up_verifier) is not DeploymentJWTStepUpAssertionVerifier:
            raise TypeError("step_up_verifier must come from deployment configuration")
        if type(self.principal_grants) is not DeploymentPrincipalGrantResolver:
            raise TypeError("principal_grants must come from deployment configuration")


def build_deployment_security(config: DeploymentSecurityConfig) -> RuntimeDeploymentSecurity:
    """Build the genuine runtime collaborators from one validated deployment contract."""
    if type(config) is not DeploymentSecurityConfig:
        raise TypeError("config must be a DeploymentSecurityConfig")
    registry = CellRegistry()
    registry_path = config.cell_registry_path.expanduser()
    if not registry_path.is_file():
        raise ValueError(f"cell registry path is unavailable: {registry_path}")
    registry.load_from_json(registry_path)
    for grant in config.service_principals:
        try:
            resolution = registry.resolve(grant.tenant_id)
        except (KeyError, TenantNotFoundError, ValueError) as exc:
            raise ValueError(
                f"service principal tenant is absent from the cell registry: {grant.tenant_id}"
            ) from exc
        if resolution.cell_id != grant.cell_id:
            raise ValueError("service principal cell does not match the deployment registry")
    identity = config.identity_verifier
    identity_provider = DeploymentIdentityProvider(identity)
    opa = config.opa
    opa_client = OPAClient(
        opa_url=opa.url,
        policy_path=opa.policy_path,
        timeout_seconds=opa.timeout_seconds,
    )
    return RuntimeDeploymentSecurity(
        config=config,
        identity_provider=identity_provider,
        cell_registry=registry,
        opa_client=opa_client,
        step_up_verifier=DeploymentJWTStepUpAssertionVerifier(config.step_up_verifier),
        principal_grants=DeploymentPrincipalGrantResolver(
            (grant.identity_key, grant.permissions)
            for grant in config.service_principals
        ),
    )


def is_deployment_step_up_verifier(value: object) -> bool:
    """Return whether ``value`` is the exact deployment-produced verifier type."""
    return type(value) is DeploymentJWTStepUpAssertionVerifier


__all__ = [
    "CANONICAL_ROLE_AUTHORIZATION_SOURCE",
    "DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE",
    "DeploymentIdentityProvider",
    "DeploymentJWTStepUpAssertionVerifier",
    "DeploymentSecurityConfig",
    "IdentityVerifierConfig",
    "OPADeploymentConfig",
    "RuntimeDeploymentSecurity",
    "ServicePrincipalGrant",
    "StepUpVerifierConfig",
    "VerifierProvenance",
    "build_deployment_security",
    "is_deployment_step_up_verifier",
]
