"""Shared runtime security helpers for HTTP and WebSocket entrypoints."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims

_FIXTURE_IDENTITY_ENV = "POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY"
_FIXTURE_IDENTITY_ISSUER = "polisyos://fixture-identity"

AUTHORIZATION_STATE_FIELDS = (
    "user_claims",
    "authenticated_tenant_id",
    "access_scope",
    "tenant_id",
    "cell_id",
    "cell_tier",
    "authz_decision",
    "authz_policy",
    "authz_reasons",
    "authz_allowed_columns",
    "authz_resource",
    "authz_bound_resource",
    "authz_action_bound_resource",
    "authz_resource_frozen",
    "authz_body_sha256",
    "authz_matched_route",
    "authz_route_requirement",
    "authz_effective_scope",
    "authz_scope_provenance",
    "authz_step_up_requirement",
    "authz_action_dependency",
    "authz_step_up_dependency",
    "action_permission_verification",
    "step_up_verification",
)


class RuntimeStepUpAssertionVerifier(Protocol):
    """Security-config shape for a context-bound external assertion verifier."""

    def verify(self, token: str, context: Any) -> Any:
        """Return one typed proof or raise a fail-closed verifier error."""
        ...


class RuntimeStepUpReplayStore(Protocol):
    """Security-config shape for atomic durable assertion consumption."""

    def consume_step_up_assertion(
        self,
        *,
        assertion_id: str,
        expires_at: int,
    ) -> bool:
        """Return true only for the first durable consumption."""
        ...


class RuntimeHumanDecisionCustody(Protocol):
    """Attested signer, verifier, and trust policy for decision custody."""

    @property
    def available(self) -> bool:
        """Return whether the deployment supplied the complete custody chain."""
        ...

    @property
    def signer(self) -> Any | None:
        """Return the exact deployment signer when custody is available."""
        ...

    @property
    def verifier(self) -> Any | None:
        """Return the exact deployment verifier when custody is available."""
        ...

    @property
    def trust_policy(self) -> Any | None:
        """Return the exact immutable producer trust policy."""
        ...

    @property
    def signer_identity(self) -> str | None:
        """Return the deployment-bound custody signer identity."""
        ...

    @property
    def verifier_epoch(self) -> str | None:
        """Return the frozen deployment verifier epoch."""
        ...

    @property
    def unavailability_code(self) -> str | None:
        """Return the typed fail-closed reason when custody is unavailable."""
        ...


@dataclass(frozen=True, slots=True)
class RuntimeSecurityConfig:
    """Bundle runtime security collaborators and fail-closed policy toggles."""

    identity_provider: Any | None
    cell_registry: Any | None
    opa_client: Any | None
    authz_enforce: bool
    authz_shadow_mode: bool
    allow_fixture_identity: bool
    step_up_verifier: RuntimeStepUpAssertionVerifier | None = None
    step_up_replay_store: RuntimeStepUpReplayStore | None = None
    human_decision_custody: RuntimeHumanDecisionCustody | None = None


def is_fixture_identity_enabled(*, explicit: bool | None = None) -> bool:
    """Return whether development fixture identity is explicitly enabled."""
    if explicit is not None:
        return bool(explicit)
    raw = os.getenv(_FIXTURE_IDENTITY_ENV)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_fixture_identity_claims() -> UserIdentityClaims:
    """Return the explicit development-only fixture identity."""
    return UserIdentityClaims(
        sub="fixture-analyst",
        email="fixture-analyst@polisyos.local",
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
        roles=frozenset({PolicyOSRole.ANALYST}),
        mfa_verified=True,
        iss=_FIXTURE_IDENTITY_ISSUER,
        aud="polisyos-web",
        exp=4_102_444_800,
        iat=1,
        jti="fixture-identity-jti",
    )


def is_fixture_identity_claims(value: object) -> bool:
    """Return whether claims carry the reserved development-fixture issuer."""
    return bool(isinstance(value, UserIdentityClaims) and value.iss == _FIXTURE_IDENTITY_ISSUER)


def clear_request_auth_context(state: Any) -> None:
    """Remove auth-derived state so deny paths cannot leak trusted context."""
    for field_name in AUTHORIZATION_STATE_FIELDS:
        if hasattr(state, field_name):
            try:
                delattr(state, field_name)
            except AttributeError:
                setattr(state, field_name, None)


__all__ = [
    "AUTHORIZATION_STATE_FIELDS",
    "PolicyOSRole",
    "RuntimeHumanDecisionCustody",
    "RuntimeSecurityConfig",
    "RuntimeStepUpAssertionVerifier",
    "RuntimeStepUpReplayStore",
    "UserIdentityClaims",
    "build_fixture_identity_claims",
    "clear_request_auth_context",
    "is_fixture_identity_claims",
    "is_fixture_identity_enabled",
]
