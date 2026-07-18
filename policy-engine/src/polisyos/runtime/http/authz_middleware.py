"""Fail-closed route authorization, resource binding, and OPA evaluation."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.authz import AuthzInput, OPAClient
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
)
from polisyos.runtime.http.access_audit import (
    RuntimeAuthorizationOutcome,
    emit_runtime_authorization_audit,
)
from polisyos.runtime.http.authorization import (
    ActionPermissionVerification,
    BoundActionPermissionVerification,
    MatchedAuthorizationRoute,
    RouteAuthorizationRequirement,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.errors import (
    RuntimeHTTPError,
    bad_request,
    problem_response,
)
from polisyos.runtime.http.resource_binding import (
    BoundAuthorizationResource,
    bind_authorization_resource,
)
from polisyos.runtime.http.security import clear_request_auth_context

logger = get_logger("polisyos.security.authz")

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from fastapi.routing import APIRoute
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Match
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from polisyos.core.security.delegation import DelegationTokenManager
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi.routing import APIRoute
        from starlette.requests import Request
        from starlette.routing import Match
    except ModuleNotFoundError:  # pragma: no cover
        APIRoute = cast("Any", object)
        Match = cast("Any", None)
        Request = cast("Any", object)

    ASGIApp = Any
    Awaitable = Any
    Callable = Any
    DelegationTokenManager = Any
    Mapping = Any
    Message = dict[str, Any]
    Receive = Any
    Response = Any
    Scope = dict[str, Any]
    Send = Any


_PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/auth/callback"})
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SENSITIVE_POLICY_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "x-policyos-context",
        "x-policyos-step-up",
    }
)
_DEFAULT_BODY_CEILING = 1024 * 1024


class AuthzMiddleware:
    """Enforce the real route dependency and bind its resource before OPA."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        runtime_app: object,
        opa_client: OPAClient | None = None,
        enforce: bool = True,
        shadow_mode: bool = False,
        public_paths: frozenset[str] = _PUBLIC_PATHS,
        delegation_manager: DelegationTokenManager | None = None,
        delegation_header: str = "x-policyos-context",
        mtls_spiffe_header: str = "l5d-client-id",
        trusted_delegators: frozenset[str] = frozenset(),
        service_spiffe_id: str | None = None,
    ) -> None:
        self._app = app
        self._runtime_app = runtime_app
        self._opa = opa_client
        self._enforce = enforce
        self._shadow_mode = shadow_mode
        self._public_paths = public_paths
        self._delegation_manager = delegation_manager
        self._delegation_header = delegation_header.lower()
        self._mtls_spiffe_header = mtls_spiffe_header.lower()
        self._trusted_delegators = trusted_delegators
        self._service_spiffe_id = service_spiffe_id or os.getenv("POLISYOS_SERVICE_SPIFFE_ID", "")
        self._opa_timeout_seconds = max(
            float(os.getenv("POLISYOS_RUNTIME_OPA_TIMEOUT_SECONDS", "1.5")),
            0.1,
        )
        self._body_ceiling = _configured_body_ceiling()
        self._opa_breaker = CircuitBreaker(
            circuit_id="runtime.opa",
            config=CircuitBreakerConfig(
                failure_threshold=max(
                    int(os.getenv("POLISYOS_RUNTIME_OPA_BREAKER_FAILURE_THRESHOLD", "3")),
                    1,
                ),
                success_threshold=1,
                timeout_seconds=max(
                    float(os.getenv("POLISYOS_RUNTIME_OPA_BREAKER_TIMEOUT_SECONDS", "30")),
                    1.0,
                ),
                half_open_max_calls=1,
                window_size_seconds=max(
                    float(os.getenv("POLISYOS_RUNTIME_OPA_BREAKER_WINDOW_SECONDS", "60")),
                    1.0,
                ),
                min_throughput=1,
            ),
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        method = str(request.method).upper()
        path = str(request.url.path)
        unsafe = method in _UNSAFE_METHODS
        if not unsafe and path in self._public_paths:
            await self._app(scope, receive, send)
            return
        if not unsafe and self._opa is None:
            await self._app(scope, receive, send)
            return

        peer_spiffe_id = request.headers.get(self._mtls_spiffe_header, "")
        effective_scope, provenance, denied = self._resolve_effective_scope(
            request,
            peer_spiffe_id=peer_spiffe_id,
            unsafe=unsafe,
        )
        if denied is not None:
            await denied(scope, receive, send)
            return
        if effective_scope is None:
            await self._problem(
                request,
                status_code=401 if unsafe else 403,
                code="missing_access_scope",
                detail="No authenticated access scope found in request context",
            )(scope, receive, send)
            return

        request.state.access_scope = effective_scope
        request.state.authz_effective_scope = effective_scope
        request.state.authz_scope_provenance = provenance

        downstream_receive = receive
        bound_resource: BoundAuthorizationResource | None = None
        if unsafe:
            binding_scope_token = set_current_access_scope(effective_scope)
            try:
                matched = self._match_route(scope, method=method)
                if matched is not None:
                    route, child_scope = matched
                    matched_scope = dict(scope)
                    matched_scope.update(child_scope)
                    matched_request = Request(matched_scope, receive=receive)
                    preflight_error = self._preflight_action_dependency(matched_request, route)
                    if preflight_error is not None:
                        await preflight_error(scope, receive, send)
                        return
                    try:
                        body_bytes, downstream_receive = await _capture_and_replay_body(
                            request,
                            receive,
                            ceiling=self._body_ceiling,
                        )
                        requirement = cast(
                            "RouteAuthorizationRequirement",
                            matched_request.state.authz_route_requirement,
                        )
                        bound_resource = bind_authorization_resource(
                            matched_request,
                            requirement,
                            body_bytes,
                            max_body_bytes=self._body_ceiling,
                        )
                    except RuntimeHTTPError as exc:
                        emit_runtime_authorization_audit(
                            matched_request,
                            outcome=RuntimeAuthorizationOutcome.DENY,
                            denial_reason=exc.code or exc.error,
                            raise_on_failure=False,
                        )
                        await _response_for_runtime_error(matched_request, exc)(
                            scope,
                            receive,
                            send,
                        )
                        return
                    self._freeze_binding(matched_request, bound_resource)
                elif self._path_has_unsafe_route(scope):
                    await self._problem(
                        request,
                        status_code=503,
                        code="authorization_contract_violation",
                        detail="Unsafe route could not be matched to one authorized operation",
                    )(scope, receive, send)
                    return
                else:
                    await self._app(scope, receive, send)
                    return
            finally:
                reset_current_access_scope(binding_scope_token)

        shadow_deny = False
        if self._opa is not None:
            resource = self._opa_resource(request, bound_resource=bound_resource, unsafe=unsafe)
            if resource is None:
                await self._problem(
                    request,
                    status_code=503,
                    code="authorization_resource_unbound",
                    detail="Unsafe request reached policy evaluation without a frozen resource",
                )(scope, receive, send)
                return
            authz_input = AuthzInput.for_http_request(
                request_method=method,
                request_path=path,
                request_headers=_policy_headers(request.headers),
                scope=effective_scope,
                peer_spiffe_id=peer_spiffe_id,
                resource_tenant_id=str(resource.get("tenant_id", "")),
                resource_kind=str(resource.get("kind", "")),
                resource_artifact_id=str(resource.get("artifact_id", "")),
                resource_pii_tier=str(resource.get("pii_tier", "none")),
                resource_metric_id=str(resource.get("metric_id", "")),
                resource_columns=_resource_columns(resource.get("columns")),
                resource_requires_anonymization=bool(resource.get("requires_anonymization", False)),
            )
            opa_scope_token = set_current_access_scope(effective_scope)
            try:
                opa_response, shadow_deny = await self._evaluate_opa(
                    request,
                    authz_input,
                    fail_closed=unsafe,
                )
            finally:
                reset_current_access_scope(opa_scope_token)
            if opa_response is not None:
                await opa_response(scope, receive, send)
                return

        if unsafe and bound_resource is not None:
            dependency_error = self._execute_bound_authorization_dependencies(request)
            if dependency_error is not None:
                await dependency_error(scope, downstream_receive, send)
                return

        scope_token = set_current_access_scope(effective_scope)
        try:
            downstream_send = _shadow_header_sender(send) if shadow_deny else send
            if unsafe and bound_resource is not None:
                downstream_send = self._binding_integrity_sender(
                    request,
                    binding=bound_resource,
                    scope=scope,
                    receive=downstream_receive,
                    downstream_send=downstream_send,
                    failure_send=send,
                )
            await self._app(scope, downstream_receive, downstream_send)
        finally:
            reset_current_access_scope(scope_token)

    def _match_route(
        self,
        scope: Scope,
        *,
        method: str,
    ) -> tuple[APIRoute, dict[str, Any]] | None:
        del method
        routes = tuple(getattr(getattr(self._runtime_app, "router", None), "routes", ()))
        for route in routes:
            match, child_scope = cast(
                "tuple[Match, dict[str, Any]]",
                cast("Any", route).matches(scope),
            )
            if match is Match.FULL:
                if not isinstance(route, APIRoute):
                    return None
                return route, child_scope
        return None

    def _path_has_unsafe_route(self, scope: Scope) -> bool:
        routes = tuple(getattr(getattr(self._runtime_app, "router", None), "routes", ()))
        for route in routes:
            match, _child_scope = cast(
                "tuple[Match, dict[str, Any]]",
                cast("Any", route).matches(scope),
            )
            if match is Match.FULL:
                return True
        return False

    def _preflight_action_dependency(
        self,
        request: Request,
        route: APIRoute,
    ) -> Response | None:
        from polisyos.runtime.http.step_up import get_route_step_up_dependency

        try:
            dependency = get_route_action_permission_dependency(cast("Any", route))
            step_up_dependency = get_route_step_up_dependency(
                cast("Any", route),
                action_dependency=dependency,
            )
        except RuntimeError as exc:
            return self._problem(
                request,
                status_code=503,
                code="authorization_contract_violation",
                detail=str(exc),
            )

        overrides = getattr(self._runtime_app, "dependency_overrides", {})
        if isinstance(overrides, dict) and dependency in overrides:
            return self._problem(
                request,
                status_code=503,
                code="authorization_dependency_overridden",
                detail="The route action-permission dependency is overridden",
            )
        if (
            step_up_dependency is not None
            and isinstance(overrides, dict)
            and step_up_dependency in overrides
        ):
            return self._problem(
                request,
                status_code=503,
                code="authorization_dependency_overridden",
                detail="The route step-up dependency is overridden",
            )
        requirement = dependency.requirement
        path_parameters = tuple(
            sorted((str(key), str(value)) for key, value in request.path_params.items())
        )
        request.state.authz_matched_route = MatchedAuthorizationRoute(
            method=request.method.upper(),
            path_template=route.path,
            name=route.name,
            path_parameters=path_parameters,
        )
        request.state.authz_route_requirement = requirement
        request.state.authz_step_up_requirement = (
            step_up_dependency.requirement if step_up_dependency is not None else None
        )
        request.state.authz_action_dependency = dependency
        request.state.authz_step_up_dependency = step_up_dependency
        try:
            _ = dependency(request)
        except RuntimeHTTPError as exc:
            return _response_for_runtime_error(request, exc)
        return None

    def _execute_bound_authorization_dependencies(
        self,
        request: Request,
    ) -> Response | None:
        """Execute the sealed route gates before any route application can run."""
        from polisyos.runtime.http.authorization import ActionPermissionDependency
        from polisyos.runtime.http.step_up import (
            StepUpAssertionVerification,
            StepUpDependency,
        )

        action_dependency = getattr(request.state, "authz_action_dependency", None)
        step_up_dependency = getattr(request.state, "authz_step_up_dependency", None)
        if type(action_dependency) is not ActionPermissionDependency:
            return self._problem(
                request,
                status_code=503,
                code="authorization_contract_violation",
                detail="The matched route action dependency was not sealed",
            )
        try:
            action_verification = action_dependency(request)
            if type(action_verification) is not BoundActionPermissionVerification:
                raise RuntimeError(
                    "The action dependency did not consume the frozen resource"
                )
            if step_up_dependency is None:
                return None
            if type(step_up_dependency) is not StepUpDependency:
                raise RuntimeError("The matched route step-up dependency was not sealed")
            step_up_verification = step_up_dependency(request)
            if type(step_up_verification) is not StepUpAssertionVerification:
                raise RuntimeError("The step-up dependency returned an invalid proof")
        except RuntimeHTTPError as exc:
            return _response_for_runtime_error(request, exc)
        except RuntimeError as exc:
            return self._problem(
                request,
                status_code=503,
                code="authorization_contract_violation",
                detail=str(exc),
            )
        return None

    def _freeze_binding(
        self,
        request: Request,
        binding: BoundAuthorizationResource,
    ) -> None:
        existing = getattr(request.state, "authz_bound_resource", None)
        if existing is not None and existing is not binding:
            raise RuntimeError("authorization resource binding changed within one request")
        verification = getattr(request.state, "action_permission_verification", None)
        if (
            type(verification) is not ActionPermissionVerification
            or verification.requirement is not binding.requirement
        ):
            raise RuntimeError(
                "authorization resource binding lacks the exact permission preflight"
            )
        request.state.authz_bound_resource = binding
        request.state.authz_action_bound_resource = binding
        request.state.authz_resource = binding.to_opa_resource()
        request.state.authz_resource_frozen = True
        request.state.authz_body_sha256 = binding.body_sha256

    def _binding_integrity_sender(
        self,
        request: Request,
        *,
        binding: BoundAuthorizationResource,
        scope: Scope,
        receive: Receive,
        downstream_send: Send,
        failure_send: Send,
    ) -> Send:
        """Reject a handler response if any frozen authorization state changed."""
        rejected = False
        response_started = False
        successful_response: bool | None = None

        async def _send(message: Message) -> None:
            nonlocal rejected, response_started, successful_response
            if rejected:
                return
            message_type = message.get("type")
            status = message.get("status") if message_type == "http.response.start" else None
            if isinstance(status, int):
                successful_response = status < 400
            if not self._binding_is_intact(
                request,
                binding,
                require_executed_dependencies=successful_response is not False,
            ):
                rejected = True
                if response_started:
                    raise RuntimeError(
                        "authorization binding changed after response emission began"
                    )
                await self._problem(
                    request,
                    status_code=503,
                    code="authorization_binding_integrity_violation",
                    detail="The frozen authorization resource changed during mutation",
                )(scope, receive, failure_send)
                return
            if message_type == "http.response.start":
                response_started = True
            await downstream_send(message)

        return _send

    @staticmethod
    def _binding_is_intact(
        request: Request,
        binding: BoundAuthorizationResource,
        *,
        require_executed_dependencies: bool,
    ) -> bool:
        state = request.state
        verification = getattr(state, "action_permission_verification", None)
        # A base proof is valid only when downstream middleware or request
        # validation short-circuits before FastAPI executes route dependencies.
        # Any reached handler necessarily upgrades it to the bound proof.
        bound_permission_proof = bool(
            type(verification) is BoundActionPermissionVerification
            and verification.bound_resource is binding
            and verification.verification.requirement is binding.requirement
        )
        preflight_permission_proof = bool(
            type(verification) is ActionPermissionVerification
            and verification.requirement is binding.requirement
        )
        permission_proof_matches = (
            bound_permission_proof
            if require_executed_dependencies
            else bound_permission_proof or preflight_permission_proof
        )
        if require_executed_dependencies and getattr(
            state,
            "authz_step_up_requirement",
            None,
        ) is not None:
            from polisyos.runtime.http.step_up import (
                step_up_verification_matches_request,
            )

            if type(verification) is not BoundActionPermissionVerification:
                return False
            if not step_up_verification_matches_request(
                request,
                action_verification=verification,
            ):
                return False
        return bool(
            permission_proof_matches
            and getattr(state, "authz_bound_resource", None) is binding
            and getattr(state, "authz_action_bound_resource", None) is binding
            and getattr(state, "authz_resource_frozen", False) is True
            and getattr(state, "authz_body_sha256", None) == binding.body_sha256
            and getattr(state, "authz_resource", None) == binding.to_opa_resource()
        )

    def _resolve_effective_scope(
        self,
        request: Request,
        *,
        peer_spiffe_id: str,
        unsafe: bool,
    ) -> tuple[AccessScope | None, str, Response | None]:
        scope = getattr(request.state, "access_scope", None)
        provenance = _scope_provenance(request, scope)
        delegation_token = request.headers.get(self._delegation_header, "")
        if delegation_token:
            delegation_manager = self._delegation_manager
            checks = (
                (
                    delegation_manager is None,
                    "delegation_not_configured",
                    "Delegation token supplied but verifier is not configured",
                ),
                (
                    not peer_spiffe_id,
                    "missing_peer_identity",
                    "Delegation token requires mTLS peer identity",
                ),
                (
                    bool(self._trusted_delegators)
                    and peer_spiffe_id not in self._trusted_delegators,
                    "untrusted_delegator",
                    f"Peer {peer_spiffe_id!r} is not allowed to delegate user context",
                ),
                (
                    not self._service_spiffe_id,
                    "service_identity_not_set",
                    "POLISYOS_SERVICE_SPIFFE_ID is required for delegation audience binding",
                ),
            )
            for failed, reason, detail in checks:
                if failed:
                    return (
                        scope,
                        provenance,
                        self._deny_or_shadow(
                            request,
                            reason=reason,
                            detail=detail,
                            fail_closed=unsafe,
                        ),
                    )
            try:
                claims = cast("Any", delegation_manager).verify_token(
                    delegation_token,
                    expected_audience=self._service_spiffe_id,
                    trusted_issuers=self._trusted_delegators or frozenset({peer_spiffe_id}),
                )
            except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
                return (
                    scope,
                    provenance,
                    self._deny_or_shadow(
                        request,
                        reason="invalid_delegation",
                        detail=str(exc),
                        fail_closed=unsafe,
                    ),
                )
            scope = claims.to_access_scope()
            request.state.access_scope = scope
            provenance = "delegation"

        if not isinstance(scope, AccessScope):
            ambient_scope = get_current_access_scope_or_none()
            scope = ambient_scope if isinstance(ambient_scope, AccessScope) else None
        if scope is not None:
            routed_cell_id = getattr(request.state, "cell_id", None)
            if routed_cell_id and scope.cell_id and routed_cell_id != scope.cell_id:
                return (
                    scope,
                    provenance,
                    self._deny_or_shadow(
                        request,
                        reason="cell_binding_mismatch",
                        detail=(
                            f"Scope bound to cell {scope.cell_id!r}, routed into {routed_cell_id!r}"
                        ),
                        fail_closed=unsafe,
                    ),
                )
        return scope, provenance, None

    def _opa_resource(
        self,
        request: Request,
        *,
        bound_resource: BoundAuthorizationResource | None,
        unsafe: bool,
    ) -> Mapping[str, object] | None:
        if unsafe:
            frozen = getattr(request.state, "authz_bound_resource", None)
            if (
                type(frozen) is not BoundAuthorizationResource
                or frozen is not bound_resource
                or not getattr(request.state, "authz_resource_frozen", False)
            ):
                return None
            return frozen.to_opa_resource()
        resource = getattr(request.state, "authz_resource", None)
        if isinstance(resource, dict):
            return resource
        scope = getattr(request.state, "authz_effective_scope", None)
        return {
            "tenant_id": scope.tenant_id if isinstance(scope, AccessScope) else "",
            "kind": "http_resource",
            "artifact_id": "",
        }

    async def _evaluate_opa(
        self,
        request: Request,
        authz_input: AuthzInput,
        *,
        fail_closed: bool,
    ) -> tuple[Response | None, bool]:
        opa = self._opa
        if opa is None:
            return None, False
        try:
            result = await self._opa_breaker.execute(
                lambda: asyncio.wait_for(
                    opa.check(authz_input),
                    timeout=self._opa_timeout_seconds,
                )
            )
        except TimeoutError:
            emit_runtime_authorization_audit(
                request,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason="authz_dependency_timeout",
                raise_on_failure=False,
            )
            clear_request_auth_context(request.state)
            return (
                self._problem(
                    request,
                    status_code=504,
                    code="authz_dependency_timeout",
                    detail="Authorization dependency timed out",
                ),
                False,
            )
        except CircuitOpenError:
            emit_runtime_authorization_audit(
                request,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason="authz_dependency_unavailable",
                raise_on_failure=False,
            )
            clear_request_auth_context(request.state)
            return (
                self._problem(
                    request,
                    status_code=503,
                    code="authz_dependency_unavailable",
                    detail="Authorization dependency is temporarily unavailable",
                ),
                False,
            )
        request.state.authz_decision = result.decision.value
        request.state.authz_policy = result.policy
        request.state.authz_reasons = list(result.reasons)
        request.state.authz_allowed_columns = _extract_allowed_columns(result.audit_entry)
        if "OPA_UNREACHABLE" in result.reasons:
            self._opa_breaker.record_failure()
            emit_runtime_authorization_audit(
                request,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason="authz_dependency_unavailable",
                raise_on_failure=False,
            )
            clear_request_auth_context(request.state)
            return (
                self._problem(
                    request,
                    status_code=503,
                    code="authz_dependency_unavailable",
                    detail="Authorization dependency is temporarily unavailable",
                ),
                False,
            )
        if result.is_allowed:
            return None, False
        if fail_closed or (self._enforce and not self._shadow_mode):
            emit_runtime_authorization_audit(
                request,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason="authorization_denied",
                raise_on_failure=False,
            )
            clear_request_auth_context(request.state)
            return (
                problem_response(
                    status_code=403,
                    code="authorization_denied",
                    detail="Request was denied by authorization policy",
                    request_id=_request_id(request),
                    instance=str(request.url.path),
                    error="authorization_denied",
                    title="Authorization denied",
                    extensions={
                        "policy": result.policy,
                        "reasons": list(result.reasons),
                    },
                ),
                False,
            )
        logger.warning(
            "AUTHZ_SHADOW_DENY %s",
            {
                "error": "authorization_denied",
                "policy": result.policy,
                "reasons": list(result.reasons),
            },
        )
        return None, True

    def _deny_or_shadow(
        self,
        request: Request,
        *,
        reason: str,
        detail: str,
        fail_closed: bool,
    ) -> Response | None:
        if fail_closed or (self._enforce and not self._shadow_mode):
            clear_request_auth_context(request.state)
            return self._problem(
                request,
                status_code=403,
                code=reason,
                detail=detail,
            )
        logger.warning("AUTHZ_SHADOW_GUARD %s", {"error": reason, "detail": detail})
        return None

    def _problem(
        self,
        request: Request,
        *,
        status_code: int,
        code: str,
        detail: str,
    ) -> Response:
        return problem_response(
            status_code=status_code,
            code=code,
            detail=detail,
            request_id=_request_id(request),
            instance=str(request.url.path),
            error=code,
        )


async def _capture_and_replay_body(
    request: Request,
    receive: Receive,
    *,
    ceiling: int,
) -> tuple[bytes, Receive]:
    content_encoding = request.headers.get("content-encoding", "identity").strip().lower()
    if content_encoding not in {"", "identity"}:
        raise RuntimeHTTPError(
            status_code=415,
            error="unsupported_media_type",
            detail="Encoded request bodies are not accepted at the authorization boundary",
            code="authorization_body_encoding_unsupported",
        )
    declared_length = request.headers.get("content-length")
    expected_length: int | None = None
    if declared_length is not None:
        try:
            expected_length = int(declared_length)
        except ValueError as exc:
            raise bad_request(
                "Content-Length must be a non-negative integer",
                code="authorization_body_length_invalid",
            ) from exc
        if expected_length < 0:
            raise bad_request(
                "Content-Length must be a non-negative integer",
                code="authorization_body_length_invalid",
            )
        if expected_length > ceiling:
            raise RuntimeHTTPError(
                status_code=413,
                error="payload_too_large",
                detail="Request body exceeds the authorization boundary limit",
                code="authorization_body_too_large",
            )

    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        message_type = message.get("type")
        if message_type == "http.disconnect":
            raise bad_request(
                "Request disconnected before authorization body binding completed",
                code="authorization_body_disconnected",
            )
        if message_type != "http.request":
            raise bad_request(
                "Authorization boundary received an invalid ASGI body message",
                code="authorization_body_stream_invalid",
            )
        chunk = bytes(message.get("body", b""))
        size += len(chunk)
        if size > ceiling:
            raise RuntimeHTTPError(
                status_code=413,
                error="payload_too_large",
                detail="Request body exceeds the authorization boundary limit",
                code="authorization_body_too_large",
            )
        chunks.append(chunk)
        if not message.get("more_body", False):
            break
    body = b"".join(chunks)
    if expected_length is not None and len(body) != expected_length:
        raise bad_request(
            "Content-Length does not match the received authorization body",
            code="authorization_body_length_mismatch",
        )

    delivered = False

    async def _replay() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    return body, _replay


def _configured_body_ceiling() -> int:
    raw = os.getenv("POLISYOS_RUNTIME_AUTHZ_MAX_BODY_BYTES")
    if raw is None:
        return _DEFAULT_BODY_CEILING
    try:
        ceiling = int(raw)
    except ValueError as exc:
        raise ValueError("POLISYOS_RUNTIME_AUTHZ_MAX_BODY_BYTES must be an integer") from exc
    if ceiling <= 0:
        raise ValueError("POLISYOS_RUNTIME_AUTHZ_MAX_BODY_BYTES must be positive")
    return ceiling


def _response_for_runtime_error(request: Request, exc: RuntimeHTTPError) -> Response:
    return problem_response(
        status_code=exc.status_code,
        code=exc.code,
        detail=exc.detail,
        request_id=_request_id(request),
        instance=str(request.url.path),
        error=exc.error,
        extensions=exc.extensions,
    )


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else None


def _scope_provenance(request: Request, scope: object) -> str:
    claims = getattr(request.state, "user_claims", None)
    issuer = str(getattr(claims, "iss", ""))
    if issuer == "polisyos://fixture-identity":
        return "development_fixture"
    if isinstance(scope, AccessScope) and scope.spiffe_id and not scope.user_sub:
        return "spiffe"
    if claims is not None:
        return "jwt"
    return "access_scope"


def _policy_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in headers.items()
        if key.lower() not in _SENSITIVE_POLICY_HEADERS
    }


def _resource_columns(value: object) -> tuple[dict[str, str], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    columns: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            columns.append({str(key): str(entry) for key, entry in item.items()})
    return tuple(columns)


def _shadow_header_sender(send: Send) -> Send:
    async def _send(message: Message) -> None:
        if message.get("type") == "http.response.start":
            headers = list(cast("list[tuple[bytes, bytes]]", message.get("headers", [])))
            headers.append((b"x-policyos-authz-shadow-deny", b"true"))
            message = {**message, "headers": headers}
        await send(message)

    return _send


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


__all__ = ["AuthzMiddleware", "MatchedAuthorizationRoute"]
