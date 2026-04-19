"""Public routes auth module API."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.contracts.runtime import ApiMeta, AuthMeResponse
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.runtime.http.container import resolve_runtime_security
from polisyos.runtime.http.dependencies import build_meta
from polisyos.runtime.http.errors import unauthorized
from polisyos.runtime.http.security import build_fixture_identity_claims

if TYPE_CHECKING:
    from fastapi import APIRouter, Request
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Request
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Request = cast("Any", object)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/auth", tags=["runtime-auth"])


router = _build_router()

_ROLE_PERMISSIONS: dict[PolicyOSRole, frozenset[str]] = {
    PolicyOSRole.ADMIN: frozenset(
        {
            "dashboard.view",
            "evidence.promotions.approve",
            "evidence.promotions.reject",
            "evidence.review",
            "evidence.view",
            "knowledge.view",
            "mode.analyst",
            "platform.admin",
            "platform.view",
            "runs.launch",
            "runs.review",
            "runs.view",
        }
    ),
    PolicyOSRole.ANALYST: frozenset(
        {
            "dashboard.view",
            "evidence.promotions.approve",
            "evidence.promotions.reject",
            "evidence.review",
            "evidence.view",
            "knowledge.view",
            "mode.analyst",
            "platform.view",
            "runs.launch",
            "runs.review",
            "runs.view",
        }
    ),
    PolicyOSRole.VIEWER: frozenset(
        {
            "dashboard.view",
            "evidence.view",
            "knowledge.view",
            "platform.view",
            "runs.view",
        }
    ),
    PolicyOSRole.SERVICE: frozenset(
        {
            "dashboard.view",
            "evidence.promotions.approve",
            "evidence.promotions.reject",
            "evidence.review",
            "evidence.view",
            "knowledge.view",
            "mode.analyst",
            "platform.admin",
            "platform.view",
            "runs.launch",
            "runs.review",
            "runs.view",
        }
    ),
    PolicyOSRole.SYSTEM: frozenset(
        {
            "dashboard.view",
            "evidence.promotions.approve",
            "evidence.promotions.reject",
            "evidence.review",
            "evidence.view",
            "knowledge.view",
            "mode.analyst",
            "platform.admin",
            "platform.view",
            "runs.launch",
            "runs.review",
            "runs.view",
        }
    ),
}


def _sorted_roles(roles: Iterable[PolicyOSRole]) -> list[str]:
    return sorted((role.value for role in roles), key=str)


def _resolve_permissions(roles: Iterable[PolicyOSRole]) -> list[str]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(_ROLE_PERMISSIONS.get(role, ()))
    return sorted(permissions)


def _fallback_identity() -> AuthMeResponse:
    claims = build_fixture_identity_claims()
    fallback_roles = claims.roles or frozenset({PolicyOSRole.ANALYST})
    permissions = _resolve_permissions(fallback_roles)
    return AuthMeResponse(
        meta=ApiMeta(request_id="fallback-auth-me"),
        user_id=claims.sub,
        display_name=claims.email or claims.sub,
        tenant_id=claims.tenant_id,
        principal_type="user",
        cell_id=claims.cell_id,
        roles=_sorted_roles(fallback_roles),
        permissions=permissions,
        mfa_verified=claims.mfa_verified,
        feature_overrides={"enableReviewCollaboration": "runs.review" in permissions},
    )


if router is not None:

    @router.get("/me", response_model=AuthMeResponse, operation_id="get_auth_me")
    def get_auth_me(request: Request) -> AuthMeResponse:
        claims = getattr(request.state, "user_claims", None)
        if not isinstance(claims, UserIdentityClaims):
            runtime_security = resolve_runtime_security(request)
            if runtime_security is not None and runtime_security.allow_fixture_identity:
                fallback = _fallback_identity()
                return fallback.model_copy(update={"meta": build_meta(request)})
            raise unauthorized(
                "Authenticated user claims are required for /auth/me",
                code="missing_user_claims",
            )

        roles = claims.roles or frozenset({PolicyOSRole.VIEWER})
        permissions = _resolve_permissions(roles)
        return AuthMeResponse(
            meta=build_meta(request),
            user_id=claims.sub,
            display_name=claims.email or claims.sub,
            tenant_id=claims.tenant_id,
            principal_type="user",
            cell_id=claims.cell_id,
            roles=_sorted_roles(roles),
            permissions=permissions,
            mfa_verified=claims.mfa_verified,
            feature_overrides={"enableReviewCollaboration": "runs.review" in permissions},
        )
