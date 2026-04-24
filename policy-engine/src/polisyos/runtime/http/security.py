"""Shared runtime security helpers for HTTP and WebSocket entrypoints."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims

_FIXTURE_IDENTITY_ENV = "POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY"

_AUTH_STATE_FIELDS = (
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
)


@dataclass(frozen=True, slots=True)
class RuntimeSecurityConfig:
    """Bundle runtime security collaborators and fail-closed policy toggles."""

    identity_provider: Any | None
    cell_registry: Any | None
    opa_client: Any | None
    authz_enforce: bool
    authz_shadow_mode: bool
    allow_fixture_identity: bool


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
        iss="polisyos://fixture-identity",
        aud="polisyos-web",
        exp=4_102_444_800,
        iat=1,
        jti="fixture-identity-jti",
    )


def clear_request_auth_context(state: Any) -> None:
    """Remove auth-derived state so deny paths cannot leak trusted context."""
    for field_name in _AUTH_STATE_FIELDS:
        if hasattr(state, field_name):
            try:
                delattr(state, field_name)
            except AttributeError:
                setattr(state, field_name, None)


__all__ = [
    "RuntimeSecurityConfig",
    "build_fixture_identity_claims",
    "clear_request_auth_context",
    "is_fixture_identity_enabled",
]
