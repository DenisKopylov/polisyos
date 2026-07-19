"""Public routes review module API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.authz import AuthzInput
from polisyos.core.security.exceptions import MFARequiredError, TokenValidationError
from polisyos.core.security.router import (
    TENANT_HEADER,
    MissingTenantHeaderError,
    TenantRoutingError,
    resolve_routing,
)
from polisyos.runtime.http.container import (
    resolve_review_collaboration_hub,
    resolve_runtime_api_context,
    resolve_runtime_rate_limiter,
    resolve_runtime_review_opa_guard,
    resolve_runtime_security,
)
from polisyos.runtime.http.deployment_security_attestation import (
    DeploymentSecurityAttestationError,
    require_attested_deployment_component,
    require_installed_deployment_security,
)
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)
from polisyos.runtime.http.security import (
    RuntimeSecurityConfig,
    build_fixture_identity_claims,
    is_fixture_identity_claims,
)

if TYPE_CHECKING:
    from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

    from polisyos.core.security.authz import OPAClient
    from polisyos.core.security.identity import SPIFFEIdentityProvider
    from polisyos.core.security.registry import CellRegistry
    from polisyos.runtime.http.services.review_collaboration import (
        ReviewChannel,
        ReviewCollaborationHub,
    )
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Query = cast("Any", None)
        WebSocket = cast("Any", Any)
        WebSocketDisconnect = cast("Any", Exception)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/review", tags=["review-collaboration"])


router = _build_router()
_VALID_CHANNELS = {"review.cursor", "review.lock", "review.presence"}


@dataclass(frozen=True, slots=True)
class _ReviewSocketSecurityContext:
    claims: Any
    scope: AccessScope
    tenant_id: str
    cell_id: str | None
    headers: dict[str, str]


def _get_review_collaboration_hub(websocket: WebSocket) -> ReviewCollaborationHub:
    hub = resolve_review_collaboration_hub(websocket)
    if hub is not None:
        return hub
    raise RuntimeDependencyUnavailableError("review collaboration hub is not initialized")


def _get_runtime_security_config(websocket: WebSocket) -> RuntimeSecurityConfig:
    config = resolve_runtime_security(websocket)
    if config is None:
        raise RuntimeDependencyUnavailableError("runtime security config is not initialized")
    return config


def _resolve_run_id(review_id: str, explicit_run_id: str | None) -> str | None:
    if explicit_run_id:
        return explicit_run_id
    if review_id.startswith("run:"):
        parts = review_id.split(":")
        if len(parts) >= 2 and parts[1]:
            return parts[1]
    return None


def _get_review_opa_guard(websocket: WebSocket) -> Any:
    return resolve_runtime_review_opa_guard(websocket)


async def _authenticate_review_socket(websocket: WebSocket) -> _ReviewSocketSecurityContext | None:
    try:
        require_installed_deployment_security(websocket)
    except DeploymentSecurityAttestationError:
        await websocket.close(code=4503, reason="Deployment security attestation failed")
        return None
    config = _get_runtime_security_config(websocket)
    headers = {str(key).lower(): value for key, value in websocket.headers.items()}
    auth_header = headers.get("authorization", "")
    claims = None

    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if not token or config.identity_provider is None:
            await websocket.close(code=4401, reason="Missing or unsupported bearer token")
            return None
        try:
            identity_provider = cast(
                "SPIFFEIdentityProvider",
                require_attested_deployment_component(
                    websocket,
                    component_name="identity_provider",
                    candidate=config.identity_provider,
                ),
            )
            claims = identity_provider.extract_user_claims(token)
        except DeploymentSecurityAttestationError:
            await websocket.close(
                code=4503,
                reason="Deployment security attestation failed",
            )
            return None
        except MFARequiredError:
            await websocket.close(code=4403, reason="MFA required")
            return None
        except TokenValidationError:
            await websocket.close(code=4401, reason="Invalid bearer token")
            return None
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
            await websocket.close(code=4401, reason="Invalid bearer token")
            return None
        if is_fixture_identity_claims(claims):
            await websocket.close(
                code=4401,
                reason="Fixture identity is development-only",
            )
            return None
    elif config.allow_fixture_identity:
        claims = build_fixture_identity_claims()
    else:
        await websocket.close(code=4401, reason="Authentication required")
        return None

    tenant_header = headers.get(TENANT_HEADER.lower())
    if tenant_header and tenant_header != claims.tenant_id:
        await websocket.close(code=4403, reason="Tenant binding mismatch")
        return None

    effective_tenant_id = claims.tenant_id or tenant_header
    if not effective_tenant_id:
        await websocket.close(code=4401, reason="Tenant scope is required")
        return None

    if config.cell_registry is None:
        return _ReviewSocketSecurityContext(
            claims=claims,
            scope=AccessScope.from_user_claims(claims),
            tenant_id=effective_tenant_id,
            cell_id=claims.cell_id,
            headers=headers,
        )

    routing_headers = dict(headers)
    routing_headers[TENANT_HEADER] = effective_tenant_id
    try:
        cell_registry = cast(
            "CellRegistry",
            require_attested_deployment_component(
                websocket,
                component_name="cell_registry",
                candidate=config.cell_registry,
            ),
        )
        routing = resolve_routing(
            headers=routing_headers,
            registry=cell_registry,
            tenant_header=TENANT_HEADER,
        )
    except MissingTenantHeaderError:
        await websocket.close(code=4401, reason="Tenant scope is required")
        return None
    except TenantRoutingError:
        await websocket.close(code=4403, reason="Unknown tenant route")
        return None

    if claims.cell_id and claims.cell_id != routing.cell_id:
        await websocket.close(code=4403, reason="Cell binding mismatch")
        return None

    return _ReviewSocketSecurityContext(
        claims=claims,
        scope=AccessScope.from_user_claims(claims),
        tenant_id=routing.tenant_id,
        cell_id=routing.cell_id,
        headers=headers,
    )


async def _authorize_review_action(
    websocket: WebSocket,
    *,
    security_ctx: _ReviewSocketSecurityContext,
    channel: str,
    review_id: str,
    run_id: str | None,
    action: str,
) -> bool:
    try:
        require_installed_deployment_security(websocket)
    except DeploymentSecurityAttestationError:
        await websocket.close(code=4503, reason="Deployment security attestation failed")
        return False
    runtime_ctx = resolve_runtime_api_context(websocket)
    resource_tenant_id = security_ctx.tenant_id
    resolved_run_id = _resolve_run_id(review_id, run_id)
    if runtime_ctx is not None and resolved_run_id:
        try:
            run = runtime_ctx.run_index.get_run(resolved_run_id)
        except KeyError:
            await websocket.close(code=4404, reason="Review run not found")
            return False
        if not run.details.tenant_id or run.details.tenant_id != security_ctx.scope.tenant_id:
            await websocket.close(code=4403, reason="Cross-tenant review access denied")
            return False
        resource_tenant_id = run.details.tenant_id

    config = _get_runtime_security_config(websocket)
    if config.opa_client is None:
        return True
    try:
        opa_client = cast(
            "OPAClient",
            require_attested_deployment_component(
                websocket,
                component_name="opa_client",
                candidate=config.opa_client,
            ),
        )
    except DeploymentSecurityAttestationError:
        await websocket.close(code=4503, reason="Deployment security attestation failed")
        return False

    authz_input = AuthzInput.for_http_request(
        request_method="WEBSOCKET",
        request_path="/api/v1/review/live",
        request_headers=security_ctx.headers,
        scope=security_ctx.scope,
        resource_tenant_id=resource_tenant_id,
        resource_kind=f"runtime.review.{channel}.{action}",
    )
    guard = _get_review_opa_guard(websocket)
    try:
        if guard is not None:
            result = await guard.run(opa_client.check, authz_input)
        else:
            result = await opa_client.check(authz_input)
    except RuntimeDependencyTimeoutError:
        await websocket.close(code=4504, reason="Review authorization dependency timed out")
        return False
    except RuntimeDependencyUnavailableError:
        await websocket.close(code=4503, reason="Review authorization dependency unavailable")
        return False
    if "OPA_UNREACHABLE" in result.reasons:
        if guard is not None:
            guard.record_failure()
        await websocket.close(code=4503, reason="Review authorization dependency unavailable")
        return False
    if result.is_allowed:
        return True
    await websocket.close(code=4403, reason="Review authorization denied")
    return False


if router is not None:

    @router.websocket("/live")
    async def review_live(
        websocket: WebSocket,
        channel: str = Query(...),
        review_id: str = Query(..., min_length=1),
        run_id: str | None = Query(default=None),
        participant_id: str | None = Query(default=None),
        display_name: str | None = Query(default=None),
        accent_color: str | None = Query(default=None),
    ) -> None:
        if channel not in _VALID_CHANNELS:
            await websocket.close(code=4400, reason="Unsupported collaboration channel")
            return

        security_ctx = await _authenticate_review_socket(websocket)
        if security_ctx is None:
            return
        rate_limiter = resolve_runtime_rate_limiter(websocket)
        if rate_limiter is not None:
            allowed, _ = rate_limiter.check_request(
                tenant_id=security_ctx.tenant_id,
                method="GET",
                path="/api/v1/review/live",
            )
            if not allowed:
                await websocket.close(code=4429, reason="Review live stream rate limit exceeded")
                return
            acquired, _ = rate_limiter.acquire_live_stream(
                tenant_id=security_ctx.tenant_id,
                path="/api/v1/review/live",
            )
            if not acquired:
                await websocket.close(code=4429, reason="Too many concurrent review live streams")
                return
        else:
            acquired = False
        if not await _authorize_review_action(
            websocket,
            security_ctx=security_ctx,
            channel=channel,
            review_id=review_id,
            run_id=run_id,
            action="connect",
        ):
            if acquired and rate_limiter is not None:
                rate_limiter.release_live_stream(
                    tenant_id=security_ctx.tenant_id,
                    path="/api/v1/review/live",
                )
            return
        if not await _authorize_review_action(
            websocket,
            security_ctx=security_ctx,
            channel=channel,
            review_id=review_id,
            run_id=run_id,
            action="subscribe",
        ):
            if acquired and rate_limiter is not None:
                rate_limiter.release_live_stream(
                    tenant_id=security_ctx.tenant_id,
                    path="/api/v1/review/live",
                )
            return

        await websocket.accept()
        hub = _get_review_collaboration_hub(websocket)
        participant_value = (
            participant_id
            if is_fixture_identity_claims(security_ctx.claims) and participant_id
            else security_ctx.claims.sub
        )
        session = hub.build_session(
            channel=cast("ReviewChannel", channel),
            display_name=display_name or security_ctx.claims.email or security_ctx.claims.sub,
            participant_id=participant_value,
            review_id=review_id,
            run_id=_resolve_run_id(review_id, run_id),
            accent_color=accent_color,
        )
        await hub.dispatch(await hub.register(websocket, session))

        try:
            while True:
                raw_payload = await websocket.receive_text()
                try:
                    payload = json.loads(raw_payload) if raw_payload else {}
                except json.JSONDecodeError:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                message_type = str(payload.get("type") or "message").strip().lower() or "message"
                if not await _authorize_review_action(
                    websocket,
                    security_ctx=security_ctx,
                    channel=channel,
                    review_id=review_id,
                    run_id=run_id,
                    action=f"message.{message_type}",
                ):
                    break
                await hub.dispatch(await hub.handle_message(session, payload, websocket=websocket))
        except WebSocketDisconnect:
            pass
        finally:
            await hub.dispatch(await hub.unregister(session))
            if acquired and rate_limiter is not None:
                rate_limiter.release_live_stream(
                    tenant_id=security_ctx.tenant_id,
                    path="/api/v1/review/live",
                )
