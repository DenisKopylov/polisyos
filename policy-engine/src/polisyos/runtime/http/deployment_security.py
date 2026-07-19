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
from functools import partial
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.runtime.http.authorization import (
    CANONICAL_ROLE_AUTHORIZATION_SOURCE,
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    DeploymentPrincipalGrantResolver,
)
from polisyos.runtime.http.authz_middleware import AuthzInput, OPAClient
from polisyos.runtime.http.cell_router_middleware import CellRegistry, TenantNotFoundError
from polisyos.runtime.http.deployment_security_attestation import (
    DeploymentSecurityAttestationError,
    register_deployment_security_attestation,
    require_attested_deployment_component,
    require_registered_deployment_security,
)
from polisyos.runtime.http.deployment_security_attestation import (
    require_installed_deployment_security as _require_installed_deployment_security,
)
from polisyos.runtime.http.jwt_auth_middleware import (
    SPIFFEIdentityProvider,
    TokenValidationError,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.step_up import JWTStepUpAssertionVerifier

if TYPE_CHECKING:
    from typing import Any

    from polisyos.runtime.http.security import UserIdentityClaims

_CONFIG_PATH_ENV = "POLISYOS_RUNTIME_SERVICE_PRINCIPAL_GRANTS_PATH"
_TRUSTED_JWT_ALGORITHMS = frozenset({"RS256", "ES256", "EdDSA"})
_STEP_UP_JWKS_CACHE_TTL_SECONDS = 300
_T = TypeVar("_T")


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


class _DeploymentJWKSClient:
    """Pin one PyJWT client identity while its verified key set may rotate."""

    __slots__ = ("_client", "_jwks_uri", "_lifespan_seconds")

    def __init__(self, *, jwks_uri: str, lifespan_seconds: int) -> None:
        try:
            import jwt as pyjwt
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Deployment JWT verification requires PyJWT"
            ) from exc
        client_type = getattr(pyjwt, "PyJWKClient", None)
        if not isinstance(client_type, type):
            raise RuntimeError("PyJWT does not expose a usable PyJWKClient")
        self._jwks_uri = jwks_uri
        self._lifespan_seconds = lifespan_seconds
        self._client = client_type(
            jwks_uri,
            cache_jwk_set=True,
            lifespan=lifespan_seconds,
        )

    def get_signing_key_from_jwt(self, token: str) -> object:
        """Resolve one signing key through the pinned deployment client."""
        return self._client.get_signing_key_from_jwt(token)


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
        self._jwks_client = _DeploymentJWKSClient(
            jwks_uri=config.jwks_uri,
            lifespan_seconds=_STEP_UP_JWKS_CACHE_TTL_SECONDS,
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
        self._deployment_audience = config.audience
        self._deployment_provenance = config.provenance
        self._deployment_jwks_client = _DeploymentJWKSClient(
            jwks_uri=config.jwks_uri,
            lifespan_seconds=config.jwks_cache_ttl_seconds,
        )

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
            unverified_payload = pyjwt.decode(
                jwt_token,
                options={"verify_signature": False, "verify_aud": False},
            )
        except Exception as exc:
            raise TokenValidationError("Token header validation failed") from exc
        algorithm = str(header.get("alg", "")).strip()
        if algorithm not in self._deployment_algorithms:
            raise TokenValidationError("JWT algorithm is not trusted by deployment policy")
        if unverified_payload.get("aud") != self._deployment_audience or type(
            unverified_payload.get("aud")
        ) is not str:
            raise TokenValidationError(
                "Deployment JWT audience must be an exact singleton match"
            )
        return super().extract_user_claims(
            jwt_token,
            expected_cell_id=expected_cell_id,
        )

    def _get_jwks_client(self, pyjwt_module: object) -> _DeploymentJWKSClient:
        """Return the factory-pinned client instead of a replaceable cache entry."""
        if getattr(pyjwt_module, "PyJWKClient", None) is None:
            raise TokenValidationError("PyJWT JWKS support is unavailable")
        return self._deployment_jwks_client


class _DeploymentNoDecisionCache:
    """Make every deployment policy decision a live OPA decision."""

    __slots__ = ()

    def get(self, _key: str, default: _T | None = None) -> _T | None:
        """Always miss; policy authority is never retained in process memory."""
        return default

    def set(self, _key: str, _value: object) -> None:
        """Discard results after the current request has consumed them."""


class DeploymentOPAClient(OPAClient):
    """Query the deployment OPA endpoint without mutable decision/session authority."""

    def __init__(self, config: OPADeploymentConfig) -> None:
        if type(config) is not OPADeploymentConfig:
            raise TypeError("config must be an OPADeploymentConfig")
        super().__init__(
            opa_url=config.url,
            policy_path=config.policy_path,
            cache_ttl_seconds=0.0,
            timeout_seconds=config.timeout_seconds,
        )
        self._cache = _DeploymentNoDecisionCache()

    async def _query_opa(self, authz_input: AuthzInput) -> dict[str, Any]:
        """Use a request-local session so stored collaborators cannot redirect policy."""
        import aiohttp

        url = f"{self._opa_url}/v1/data/{self._policy_path}"
        body = {"input": authz_input.to_opa_input()}
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.post(url, json=body) as response,
        ):
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"OPA returned {response.status}: {text}")
            payload = await response.json()
            result = payload.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("OPA response missing object result")
            return result


@dataclass(frozen=True, slots=True, init=False, eq=False, weakref_slot=True)
class RuntimeDeploymentSecurity:
    """Factory-produced collaborators plus exact service-principal grants.

    Direct construction is forbidden because exact collaborator types do not
    prove that every value originated from this bundle's strict configuration
    document. :func:`build_deployment_security` is the sole assembly path.
    """

    config: DeploymentSecurityConfig
    identity_provider: DeploymentIdentityProvider = field(repr=False)
    cell_registry: CellRegistry = field(repr=False)
    opa_client: DeploymentOPAClient = field(repr=False)
    step_up_verifier: DeploymentJWTStepUpAssertionVerifier = field(repr=False)
    principal_grants: DeploymentPrincipalGrantResolver = field(repr=False)

    def __init__(
        self,
        *,
        config: DeploymentSecurityConfig,
        identity_provider: DeploymentIdentityProvider,
        cell_registry: CellRegistry,
        opa_client: DeploymentOPAClient,
        step_up_verifier: DeploymentJWTStepUpAssertionVerifier,
        principal_grants: DeploymentPrincipalGrantResolver,
    ) -> None:
        raise TypeError(
            "RuntimeDeploymentSecurity is factory-only; use build_deployment_security(config)"
        )

    def __post_init__(self) -> None:
        if type(self.config) is not DeploymentSecurityConfig:
            raise TypeError("config must be a DeploymentSecurityConfig")
        if type(self.identity_provider) is not DeploymentIdentityProvider:
            raise TypeError("identity_provider must come from deployment configuration")
        if type(self.cell_registry) is not CellRegistry:
            raise TypeError("cell_registry must come from deployment configuration")
        if type(self.opa_client) is not DeploymentOPAClient:
            raise TypeError("opa_client must come from deployment configuration")
        if type(self.step_up_verifier) is not DeploymentJWTStepUpAssertionVerifier:
            raise TypeError("step_up_verifier must come from deployment configuration")
        if type(self.principal_grants) is not DeploymentPrincipalGrantResolver:
            raise TypeError("principal_grants must come from deployment configuration")


_CANONICAL_DEPLOYMENT_BEHAVIOR_ORIGINS: tuple[object, ...] = (
    _DeploymentJWKSClient.get_signing_key_from_jwt,
    _DeploymentNoDecisionCache.get,
    _DeploymentNoDecisionCache.set,
    DeploymentIdentityProvider.extract_user_claims,
    DeploymentIdentityProvider._validated_jwt_key_id,
    DeploymentIdentityProvider._get_jwks_client,
    CellRegistry.resolve,
    CellRegistry.resolve_cell,
    CellRegistry.to_json,
    DeploymentOPAClient.check,
    DeploymentOPAClient._query_opa,
    DeploymentJWTStepUpAssertionVerifier.verify,
    DeploymentJWTStepUpAssertionVerifier._validated_header,
    DeploymentPrincipalGrantResolver.permissions_for_principal,
    DeploymentPrincipalGrantResolver.resolve_claim_permissions,
)


@dataclass(frozen=True, slots=True)
class _DeploymentSecurityAttestation:
    """Module-owned proof binding a factory instance to its exact composition."""

    config: DeploymentSecurityConfig
    config_fingerprint: str
    authority_state_fingerprint: str
    components: tuple[
        DeploymentIdentityProvider,
        CellRegistry,
        DeploymentOPAClient,
        DeploymentJWTStepUpAssertionVerifier,
        DeploymentPrincipalGrantResolver,
    ]


def _deployment_config_fingerprint(config: DeploymentSecurityConfig) -> str:
    serialized = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _deployment_components(
    runtime: RuntimeDeploymentSecurity,
) -> tuple[
    DeploymentIdentityProvider,
    CellRegistry,
    DeploymentOPAClient,
    DeploymentJWTStepUpAssertionVerifier,
    DeploymentPrincipalGrantResolver,
]:
    return (
        runtime.identity_provider,
        runtime.cell_registry,
        runtime.opa_client,
        runtime.step_up_verifier,
        runtime.principal_grants,
    )


def _instance_callable_state(value: object) -> tuple[tuple[str, int], ...]:
    try:
        namespace = vars(value)
    except TypeError:
        return ()
    return tuple(
        sorted(
            (name, id(member))
            for name, member in namespace.items()
            if callable(member)
        )
    )


def _deployment_grant_state(
    resolver: DeploymentPrincipalGrantResolver,
) -> dict[str, object]:
    permissions_by_identity = getattr(resolver, "_permissions_by_identity", None)
    managed_subjects = getattr(resolver, "_managed_subjects", None)
    if type(permissions_by_identity) is not MappingProxyType:
        raise TypeError("deployment principal grant mapping is not immutable")
    if type(managed_subjects) is not frozenset or any(
        not isinstance(subject, str) or not subject for subject in managed_subjects
    ):
        raise TypeError("deployment principal managed-subject state is invalid")
    grants: list[tuple[tuple[str, str, str, str, str], tuple[str, ...]]] = []
    for identity_key, permissions in permissions_by_identity.items():
        if (
            not isinstance(identity_key, tuple)
            or len(identity_key) != 5
            or any(not isinstance(value, str) or not value for value in identity_key)
            or type(permissions) is not frozenset
            or any(not isinstance(permission, RuntimePermission) for permission in permissions)
        ):
            raise TypeError("deployment principal grant state is invalid")
        grants.append(
            (
                identity_key,
                tuple(sorted(permission.value for permission in permissions)),
            )
        )
    grants.sort()
    return {
        "grants": [
            {"identity": list(identity_key), "permissions": list(permissions)}
            for identity_key, permissions in grants
        ],
        "managed_subjects": sorted(managed_subjects),
        "instance_callables": _instance_callable_state(resolver),
    }


def _deployment_cell_registry_fingerprint(registry: CellRegistry) -> str:
    snapshot = CellRegistry.to_json(registry)
    serialized = json.dumps(
        snapshot,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _deployment_jwks_client_state(value: object) -> dict[str, object]:
    if type(value) is not _DeploymentJWKSClient:
        raise TypeError("deployment JWKS client identity changed")
    client = getattr(value, "_client", None)
    get_signing_key = getattr(type(client), "get_signing_key_from_jwt", None)
    if client is None or not callable(get_signing_key):
        raise TypeError("deployment JWKS verifier client is invalid")
    return {
        "wrapper_identity": id(value),
        "jwks_uri": getattr(value, "_jwks_uri", None),
        "lifespan_seconds": getattr(value, "_lifespan_seconds", None),
        "client_identity": id(client),
        "client_type": f"{type(client).__module__}.{type(client).__qualname__}",
        "client_get_signing_key_origin": id(get_signing_key),
        "client_instance_callables": _instance_callable_state(client),
    }


def _deployment_authority_state_fingerprint(
    runtime: RuntimeDeploymentSecurity,
) -> str:
    """Hash immutable authority state while exempting operational caches.

    Verified key material inside the pinned PyJWT clients and metrics may rotate
    during normal operation. The client identities, configured trust roots,
    exact class behavior, instance overrides, grant/cell state, and cache-free
    OPA transport remain attested, so refresh cannot re-compose authority.
    """
    identity = runtime.identity_provider
    opa = runtime.opa_client
    step_up = runtime.step_up_verifier
    identity_jwks_cache = getattr(identity, "_jwks_cache", None)
    if type(identity_jwks_cache) is not dict or identity_jwks_cache:
        raise TypeError("deployment identity inherited JWKS cache must remain empty")
    opa_cache = getattr(opa, "_cache", None)
    if type(opa_cache) is not _DeploymentNoDecisionCache:
        raise TypeError("deployment OPA decision cache identity changed")
    if getattr(opa, "_session", None) is not None:
        raise TypeError("deployment OPA must not retain a mutable client session")
    payload: dict[str, object] = {
        "identity": {
            "issuer": getattr(identity, "_issuer", None),
            "jwks_uri": getattr(identity, "_jwks_uri", None),
            "audience": getattr(identity, "_audience", None),
            "client_id": getattr(identity, "_client_id", None),
            "spiffe_socket": getattr(identity, "_spiffe_socket", None),
            "trust_domain": getattr(identity, "_trust_domain", None),
            "allowed_cells": sorted(getattr(identity, "_allowed_cells", None) or ()),
            "required_mfa_roles": sorted(
                role.value for role in getattr(identity, "_required_mfa_roles", ())
            ),
            "allowed_key_ids": sorted(getattr(identity, "_allowed_jwt_kids", ())),
            "revoked_key_ids": sorted(getattr(identity, "_revoked_jwt_kids", ())),
            "jwks_cache_ttl_seconds": getattr(
                identity,
                "_jwks_cache_ttl_seconds",
                None,
            ),
            "inherited_jwks_cache_expires": getattr(
                identity,
                "_jwks_cache_expires",
                None,
            ),
            "pinned_jwks_client": _deployment_jwks_client_state(
                getattr(identity, "_deployment_jwks_client", None)
            ),
            "deployment_algorithms": sorted(
                getattr(identity, "_deployment_algorithms", ())
            ),
            "deployment_audience": getattr(identity, "_deployment_audience", None),
            "deployment_provenance": identity.deployment_provenance.model_dump(
                mode="json"
            ),
            "instance_callables": _instance_callable_state(identity),
        },
        "opa": {
            "url": getattr(opa, "_opa_url", None),
            "policy_path": getattr(opa, "_policy_path", None),
            "cache_max_size": getattr(opa, "_cache_max_size", None),
            "cache_ttl": getattr(opa, "_cache_ttl", None),
            "timeout": getattr(opa, "_timeout", None),
            "decision_cache_identity": id(opa_cache),
            "instance_callables": _instance_callable_state(opa),
        },
        "cell_registry": {
            "fingerprint": _deployment_cell_registry_fingerprint(runtime.cell_registry),
            "instance_callables": _instance_callable_state(runtime.cell_registry),
        },
        "step_up": {
            "issuer": getattr(step_up, "_issuer", None),
            "audience": getattr(step_up, "_audience", None),
            "algorithms": list(getattr(step_up, "_algorithms", ())),
            "maximum_age_seconds": getattr(step_up, "_maximum_age_seconds", None),
            "clock_skew_seconds": getattr(step_up, "_clock_skew_seconds", None),
            "verification_key_is_none": getattr(step_up, "_verification_key", None)
            is None,
            "jwks_uri": getattr(step_up, "_jwks_uri", None),
            "pinned_jwks_client": _deployment_jwks_client_state(
                getattr(step_up, "_jwks_client", None)
            ),
            "allowed_key_ids": sorted(getattr(step_up, "_allowed_key_ids", ())),
            "revoked_key_ids": sorted(getattr(step_up, "_revoked_key_ids", ())),
            "deployment_provenance": step_up.deployment_provenance.model_dump(
                mode="json"
            ),
            "clock_identity": id(getattr(step_up, "_clock", None)),
            "instance_callables": _instance_callable_state(step_up),
        },
        "principal_grants": _deployment_grant_state(runtime.principal_grants),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _deployment_behavior_origins(
    runtime: RuntimeDeploymentSecurity,
) -> tuple[object, ...]:
    return (
        _DeploymentJWKSClient.get_signing_key_from_jwt,
        _DeploymentNoDecisionCache.get,
        _DeploymentNoDecisionCache.set,
        type(runtime.identity_provider).extract_user_claims,
        type(runtime.identity_provider)._validated_jwt_key_id,
        type(runtime.identity_provider)._get_jwks_client,
        type(runtime.cell_registry).resolve,
        type(runtime.cell_registry).resolve_cell,
        type(runtime.cell_registry).to_json,
        type(runtime.opa_client).check,
        type(runtime.opa_client)._query_opa,
        type(runtime.step_up_verifier).verify,
        type(runtime.step_up_verifier)._validated_header,
        type(runtime.principal_grants).permissions_for_principal,
        type(runtime.principal_grants).resolve_claim_permissions,
    )


def _validate_deployment_security_attestation(
    value: object,
    *,
    attestation: _DeploymentSecurityAttestation,
) -> None:
    if type(value) is not RuntimeDeploymentSecurity:
        raise TypeError("deployment security factory type changed")
    runtime = value
    RuntimeDeploymentSecurity.__post_init__(runtime)
    config_fingerprint = _deployment_config_fingerprint(runtime.config)
    components = _deployment_components(runtime)
    authority_state_fingerprint = _deployment_authority_state_fingerprint(runtime)
    behavior_origins = _deployment_behavior_origins(runtime)
    if (
        runtime.config is not attestation.config
        or not compare_digest(config_fingerprint, attestation.config_fingerprint)
        or not compare_digest(
            authority_state_fingerprint,
            attestation.authority_state_fingerprint,
        )
        or behavior_origins != _CANONICAL_DEPLOYMENT_BEHAVIOR_ORIGINS
        or any(
            component is not attested_component
            for component, attested_component in zip(
                components,
                attestation.components,
                strict=True,
            )
        )
    ):
        raise TypeError("deployment security factory attestation is invalid")


def require_factory_produced_deployment_security(
    value: object,
) -> RuntimeDeploymentSecurity:
    """Return an intact factory-produced bundle or fail closed.

    Exact outer type is insufficient in Python because ``object.__new__`` and
    ``object.__setattr__`` can bypass a frozen dataclass constructor. The private
    weak registry proves that the factory created this identity and that neither
    its configuration nor any authority-bearing collaborator was replaced.
    """
    if type(value) is not RuntimeDeploymentSecurity:
        raise TypeError(
            "deployment security must be a factory-attested RuntimeDeploymentSecurity bundle"
        )
    try:
        require_registered_deployment_security(value)
    except DeploymentSecurityAttestationError as exc:
        raise TypeError("deployment security factory attestation is invalid") from exc
    return value


def require_installed_deployment_security(
    subject: object,
) -> RuntimeDeploymentSecurity | None:
    """Validate the installed deployment bundle and narrow its registered type."""
    runtime = _require_installed_deployment_security(subject)
    if runtime is None:
        return None
    if type(runtime) is not RuntimeDeploymentSecurity:
        raise DeploymentSecurityAttestationError(
            "installed deployment security type changed"
        )
    return runtime


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
    opa_client = DeploymentOPAClient(config.opa)
    runtime = object.__new__(RuntimeDeploymentSecurity)
    object.__setattr__(runtime, "config", config)
    object.__setattr__(runtime, "identity_provider", identity_provider)
    object.__setattr__(runtime, "cell_registry", registry)
    object.__setattr__(runtime, "opa_client", opa_client)
    object.__setattr__(
        runtime,
        "step_up_verifier",
        DeploymentJWTStepUpAssertionVerifier(config.step_up_verifier),
    )
    object.__setattr__(
        runtime,
        "principal_grants",
        DeploymentPrincipalGrantResolver(
            (grant.identity_key, grant.permissions) for grant in config.service_principals
        ),
    )
    runtime.__post_init__()
    attestation = _DeploymentSecurityAttestation(
        config=config,
        config_fingerprint=_deployment_config_fingerprint(config),
        authority_state_fingerprint=_deployment_authority_state_fingerprint(runtime),
        components=_deployment_components(runtime),
    )
    register_deployment_security_attestation(
        runtime,
        validator=partial(
            _validate_deployment_security_attestation,
            attestation=attestation,
        ),
        components={
            "identity_provider": runtime.identity_provider,
            "cell_registry": runtime.cell_registry,
            "opa_client": runtime.opa_client,
            "step_up_verifier": runtime.step_up_verifier,
            "principal_grants": runtime.principal_grants,
        },
    )
    return require_factory_produced_deployment_security(runtime)


def is_deployment_step_up_verifier(value: object) -> bool:
    """Return whether ``value`` is the exact deployment-produced verifier type."""
    return type(value) is DeploymentJWTStepUpAssertionVerifier


def verify_exact_deployment_principal_token(
    runtime: RuntimeDeploymentSecurity,
    bearer_token: str,
    *,
    required_permissions: frozenset[RuntimePermission],
) -> UserIdentityClaims:
    """Verify one bearer and require its exact deployment-managed action set.

    This preflight is intentionally stricter than normal route authorization:
    an operations probe is a narrowly provisioned witness, so an unmanaged role
    fallback or a managed principal with additional authority must not produce a
    passing probe.
    """
    runtime = require_factory_produced_deployment_security(runtime)
    if (
        not isinstance(bearer_token, str)
        or not bearer_token.strip()
        or bearer_token != bearer_token.strip()
        or any(character in bearer_token for character in "\r\n")
    ):
        raise RuntimeError("probe bearer token is unavailable or malformed")
    if not required_permissions or any(
        not isinstance(permission, RuntimePermission)
        for permission in required_permissions
    ):
        raise TypeError("required_permissions must be canonical RuntimePermission values")
    try:
        claims = runtime.identity_provider.extract_user_claims(bearer_token)
    except TokenValidationError as exc:
        raise RuntimeError(
            "probe bearer failed deployment identity verification"
        ) from exc
    runtime = require_factory_produced_deployment_security(runtime)
    granted_permissions = runtime.principal_grants.permissions_for_principal(
        issuer=claims.iss,
        audience=claims.aud,
        subject=claims.sub,
        tenant_id=claims.tenant_id,
        cell_id=claims.cell_id,
    )
    if granted_permissions != required_permissions:
        raise RuntimeError(
            "probe bearer does not resolve to the exact deployment service-principal grant"
        )
    return claims


__all__ = [
    "CANONICAL_ROLE_AUTHORIZATION_SOURCE",
    "DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE",
    "DeploymentIdentityProvider",
    "DeploymentJWTStepUpAssertionVerifier",
    "DeploymentOPAClient",
    "DeploymentSecurityAttestationError",
    "DeploymentSecurityConfig",
    "IdentityVerifierConfig",
    "OPADeploymentConfig",
    "RuntimeDeploymentSecurity",
    "ServicePrincipalGrant",
    "StepUpVerifierConfig",
    "VerifierProvenance",
    "build_deployment_security",
    "is_deployment_step_up_verifier",
    "require_attested_deployment_component",
    "require_factory_produced_deployment_security",
    "require_installed_deployment_security",
    "verify_exact_deployment_principal_token",
]
