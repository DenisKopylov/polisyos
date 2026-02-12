"""Authorization middleware with delegation verification and OPA policy checks."""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.authz import AuthzInput, OPAClient
from polisyos.core.security.delegation import DelegationTokenManager
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.runtime.http.errors import problem_response

logger = logging.getLogger("polisyos.security.authz")


try:  # pragma: no cover - optional runtime dependency
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
except ModuleNotFoundError:  # pragma: no cover
    BaseHTTPMiddleware = object  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    Response = Any  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]


_PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/auth/callback"})


class AuthzMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Run per-request authorization checks against OPA sidecar."""

    def __init__(
        self,
        app: Any,
        *,
        opa_client: OPAClient,
        enforce: bool = True,
        shadow_mode: bool = False,
        public_paths: frozenset[str] = _PUBLIC_PATHS,
        delegation_manager: DelegationTokenManager | None = None,
        delegation_header: str = "x-policyos-context",
        mtls_spiffe_header: str = "l5d-client-id",
        trusted_delegators: frozenset[str] = frozenset(),
        service_spiffe_id: str | None = None,
    ) -> None:
        if JSONResponse is None:
            raise RuntimeError("AuthzMiddleware requires starlette/fastapi dependencies")
        super().__init__(app)
        self._opa = opa_client
        self._enforce = enforce
        self._shadow_mode = shadow_mode
        self._public_paths = public_paths
        self._delegation_manager = delegation_manager
        self._delegation_header = delegation_header.lower()
        self._mtls_spiffe_header = mtls_spiffe_header.lower()
        self._trusted_delegators = trusted_delegators
        self._service_spiffe_id = service_spiffe_id or os.getenv("POLISYOS_SERVICE_SPIFFE_ID", "")

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        path = str(getattr(request.url, "path", ""))
        if path in self._public_paths:
            return await call_next(request)

        peer_spiffe_id = request.headers.get(self._mtls_spiffe_header, "")

        scope = getattr(request.state, "access_scope", None)
        delegation_token = request.headers.get(self._delegation_header, "")
        if delegation_token:
            if self._delegation_manager is None:
                deny = self._deny_or_shadow(
                    request,
                    reason="delegation_not_configured",
                    detail="Delegation token supplied but verifier is not configured",
                )
                if deny is not None:
                    return deny
            if not peer_spiffe_id:
                deny = self._deny_or_shadow(
                    request,
                    reason="missing_peer_identity",
                    detail="Delegation token requires mTLS peer identity",
                )
                if deny is not None:
                    return deny
            if self._trusted_delegators and peer_spiffe_id not in self._trusted_delegators:
                deny = self._deny_or_shadow(
                    request,
                    reason="untrusted_delegator",
                    detail=f"Peer {peer_spiffe_id!r} is not allowed to delegate user context",
                )
                if deny is not None:
                    return deny
            if not self._service_spiffe_id:
                deny = self._deny_or_shadow(
                    request,
                    reason="service_identity_not_set",
                    detail="POLISYOS_SERVICE_SPIFFE_ID is required for delegation audience binding",
                )
                if deny is not None:
                    return deny

            try:
                claims = self._delegation_manager.verify_token(
                    delegation_token,
                    expected_audience=self._service_spiffe_id,
                    trusted_issuers=self._trusted_delegators or frozenset({peer_spiffe_id}),
                )
            except Exception as exc:
                deny = self._deny_or_shadow(
                    request,
                    reason="invalid_delegation",
                    detail=str(exc),
                )
                if deny is not None:
                    return deny

            scope = claims.to_access_scope()
            request.state.access_scope = scope

        if scope is None:
            scope = get_current_access_scope_or_none()

        if scope is None:
            deny = self._deny_or_shadow(
                request,
                reason="missing_access_scope",
                detail="No authenticated access scope found in request context",
            )
            if deny is not None:
                return deny
            scope = AccessScope.for_service(
                tenant_id=str(getattr(request.state, "tenant_id", "")),
                cell_id=getattr(request.state, "cell_id", None),
                spiffe_id=peer_spiffe_id,
            )

        routed_cell_id = getattr(request.state, "cell_id", None)
        if routed_cell_id and scope.cell_id and routed_cell_id != scope.cell_id:
            deny = self._deny_or_shadow(
                request,
                reason="cell_binding_mismatch",
                detail=f"Scope bound to cell {scope.cell_id!r}, routed into {routed_cell_id!r}",
            )
            if deny is not None:
                return deny

        resource = getattr(request.state, "authz_resource", None)
        resource_ctx = resource if isinstance(resource, dict) else {}

        authz_input = AuthzInput.for_http_request(
            request_method=request.method,
            request_path=path,
            request_headers={key.lower(): value for key, value in request.headers.items()},
            scope=scope,
            peer_spiffe_id=peer_spiffe_id,
            resource_tenant_id=str(resource_ctx.get("tenant_id", scope.tenant_id)),
            resource_kind=str(resource_ctx.get("kind", "http_resource")),
            resource_artifact_id=str(resource_ctx.get("artifact_id", "")),
            resource_pii_tier=str(resource_ctx.get("pii_tier", "none")),
            resource_metric_id=str(resource_ctx.get("metric_id", "")),
            resource_columns=tuple(resource_ctx.get("columns", ()) or ()),
            resource_requires_anonymization=bool(
                resource_ctx.get("requires_anonymization", False)
            ),
        )

        result = await self._opa.check(authz_input)
        request.state.authz_decision = result.decision.value
        request.state.authz_policy = result.policy
        request.state.authz_reasons = list(result.reasons)
        request.state.authz_allowed_columns = _extract_allowed_columns(result.audit_entry)
        if not result.is_allowed:
            if self._enforce and not self._shadow_mode:
                request_id = getattr(getattr(request, "state", object()), "request_id", None)
                return problem_response(
                    status_code=403,
                    code="authorization_denied",
                    detail="Request was denied by authorization policy",
                    request_id=request_id,
                    instance=path,
                    error="authorization_denied",
                    title="Authorization denied",
                    extensions={
                        "policy": result.policy,
                        "reasons": list(result.reasons),
                    },
                )
            payload = {
                "error": "authorization_denied",
                "policy": result.policy,
                "reasons": list(result.reasons),
            }
            logger.warning("AUTHZ_SHADOW_DENY %s", payload)

        scope_token = set_current_access_scope(scope)
        try:
            response = await call_next(request)
        finally:
            reset_current_access_scope(scope_token)

        if not result.is_allowed and self._shadow_mode:
            response.headers["X-PolicyOS-Authz-Shadow-Deny"] = "true"
        return response

    def _deny_or_shadow(self, request: Request, *, reason: str, detail: str) -> Response | None:
        payload = {"error": reason, "detail": detail}
        if self._enforce and not self._shadow_mode:
            request_id = getattr(getattr(request, "state", object()), "request_id", None)
            return problem_response(
                status_code=403,
                code=reason,
                detail=detail,
                request_id=request_id,
                instance=str(getattr(getattr(request, "url", object()), "path", "")),
                error=reason,
            )
        logger.warning("AUTHZ_SHADOW_GUARD %s", payload)
        return None


def _extract_allowed_columns(audit_entry: dict[str, Any]) -> tuple[str, ...]:
    if not isinstance(audit_entry, dict):
        return ()

    allowed = audit_entry.get("allowed_columns")
    if allowed is None:
        data_classification = audit_entry.get("data_classification")
        if isinstance(data_classification, dict):
            allowed = data_classification.get("allowed_columns")

    if isinstance(allowed, set):
        return tuple(sorted(str(item) for item in allowed))
    if isinstance(allowed, (list, tuple)):
        return tuple(str(item) for item in allowed)
    return ()


__all__ = ["AuthzMiddleware"]
