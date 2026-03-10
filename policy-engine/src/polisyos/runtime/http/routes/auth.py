from __future__ import annotations

from collections.abc import Iterable

from polisyos.core.contracts.runtime import AuthMeResponse
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.runtime.http.dependencies import build_meta

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Request = object  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/auth", tags=["runtime-auth"]) if APIRouter else None

_ROLE_PERMISSIONS: dict[PolicyOSRole, frozenset[str]] = {
    PolicyOSRole.ADMIN: frozenset(
        {
            "dashboard.view",
            "evidence.promotions.approve",
            "evidence.promotions.reject",
            "evidence.review",
            "evidence.view",
            "knowledge.view",
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
    fallback_roles = frozenset({PolicyOSRole.ANALYST})
    permissions = _resolve_permissions(fallback_roles)
    return AuthMeResponse(
        meta=build_meta(type("FallbackRequest", (), {"state": type("State", (), {"request_id": "fallback-auth-me"})()})()),
        user_id="fixture-analyst",
        display_name="Fixture Analyst",
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        principal_type="user",
        cell_id="cell-a",
        roles=_sorted_roles(fallback_roles),
        permissions=permissions,
        mfa_verified=True,
        feature_overrides={"enableReviewCollaboration": "runs.review" in permissions},
    )


if router is not None:

    @router.get("/me", response_model=AuthMeResponse, operation_id="get_auth_me")
    def get_auth_me(request: Request) -> AuthMeResponse:
        claims = getattr(request.state, "user_claims", None)
        if not isinstance(claims, UserIdentityClaims):
            fallback = _fallback_identity()
            return fallback.model_copy(
                update={
                    "meta": build_meta(request),
                }
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
