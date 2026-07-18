"""Public routes auth module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.runtime import ApiMeta  # noqa: TC001 - Pydantic resolves at runtime
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.runtime.http.dependencies import build_meta
from polisyos.runtime.http.errors import unauthorized
from polisyos.runtime.http.permissions import RuntimePermission, permissions_for_roles

if TYPE_CHECKING:
    from collections.abc import Iterable

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


class AuthMeResponse(BaseModel):
    """Runtime principal payload with permissions bound to the server vocabulary."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    user_id: str
    display_name: str
    tenant_id: str
    principal_type: Literal["anonymous", "service", "user"] = "user"
    cell_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[RuntimePermission] = Field(default_factory=list)
    mfa_verified: bool = False
    feature_overrides: dict[str, bool] = Field(default_factory=dict)


def _sorted_roles(roles: Iterable[PolicyOSRole]) -> list[str]:
    return sorted((role.value for role in roles), key=str)


if router is not None:

    @router.get("/me", response_model=AuthMeResponse, operation_id="get_auth_me")
    def get_auth_me(request: Request) -> AuthMeResponse:
        claims = getattr(request.state, "user_claims", None)
        if not isinstance(claims, UserIdentityClaims):
            raise unauthorized(
                "Authenticated user claims are required for /auth/me",
                code="missing_user_claims",
            )

        roles = claims.roles
        permissions = permissions_for_roles(roles)
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
            feature_overrides={
                "enableReviewCollaboration": RuntimePermission.RUNS_REVIEW in permissions
            },
        )
