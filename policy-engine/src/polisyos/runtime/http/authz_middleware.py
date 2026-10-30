"""Fail-closed route authorization, resource binding, and OPA evaluation."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping, MutableMapping
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, Never, cast

from anyio import to_thread

from polisyos.common.logger import get_logger
from polisyos.core.security import (
    AccessScope,
    AuthzInput,
    OPAClient,
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
    RuntimeAuthorizationAuditError,
    RuntimeAuthorizationOutcome,
    RuntimeAuthorizationTargetDecision,
    emit_runtime_authorization_audit_async,
)
from polisyos.runtime.http.authorization import (
    CANONICAL_ROLE_AUTHORIZATION_SOURCE,
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    ActionPermissionDependency,
    ActionPermissionVerification,
    BoundActionPermissionVerification,
    DeploymentPrincipalGrantResolver,
    MatchedAuthorizationRoute,
    OptionalActionPermissionDependency,
    OptionalActionPermissionResult,
    ResourceBindingSource,
    RouteAuthorizationRequirement,
    get_route_action_permission_dependency,
    get_route_optional_action_permission_dependency,
    route_action_permission_dependencies,
    route_optional_action_permission_dependencies,
)
from polisyos.runtime.http.errors import (
    RuntimeHTTPError,
    bad_request,
    forbidden,
    problem_response,
)
from polisyos.runtime.http.permissions import RuntimePermission, permissions_for_roles
from polisyos.runtime.http.resource_binding import (
    BindingAuthority,
    BoundAuthorizationResource,
    _reconcile_bound_policy_targets,
    bind_authorization_resource,
)
from polisyos.runtime.http.security import (
    AUTHORIZATION_STATE_FIELDS,
    clear_request_auth_context,
)

logger = get_logger("polisyos.security.authz")
_MISSING_AUTHORIZATION_STATE = object()


def _restore_authorization_state_value(state: object, name: str, value: object) -> None:
    """Restore an authorization snapshot without losing present ``None`` values."""
    if value is _MISSING_AUTHORIZATION_STATE:
        # Starlette State delegates deletion to a dict and raises KeyError when absent.
        with suppress(AttributeError, KeyError):
            delattr(state, name)
        return
    setattr(state, name, value)


def _recheck_optional_run_owner(
    request: Request,
    matched_request: Request,
    requirement: RouteAuthorizationRequirement,
) -> RuntimeHTTPError | None:
    """Reuse the canonical run-owner guard after an optional run binding refusal."""
    binding = requirement.resource_binding
    if (
        binding.source is not ResourceBindingSource.OWNED_EXISTING_PATH
        or binding.resource_kind != "runtime.run.method_execution_selection"
        or binding.path_parameter != "run_id"
    ):
        return None
    run_id = matched_request.path_params.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return None

    from polisyos.runtime.http.dependencies import (
        enforce_run_tenant_access,
        get_runtime_api_context,
    )

    try:
        context = get_runtime_api_context(request)
        run = context.run_index.get_run(run_id)
        enforce_run_tenant_access(request, ctx=context, run=run)
    except RuntimeHTTPError as exc:
        if exc.code in {"run_tenant_mismatch", "run_tenant_unscoped"}:
            return exc
        # Missing caller scope or another runtime failure cannot confirm ownership.
        return None
    except KeyError:
        # A removed/unresolved run keeps the original binding refusal.
        return None
    except Exception:
        # A recheck failure must never turn the original refusal into admission.
        logger.exception("Optional run-owner recheck failed; preserving binding refusal")
    return None


@dataclass(frozen=True, slots=True)
class RuntimePrincipalAuthzInput(AuthzInput):
    """Extend the core OPA envelope with exact deployment principal grants."""

    principal_permissions: tuple[RuntimePermission, ...] = ()
    authorization_source: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.principal_permissions, tuple) or any(
            not isinstance(permission, RuntimePermission)
            for permission in self.principal_permissions
        ):
            raise TypeError("principal_permissions must be a tuple of RuntimePermission values")
        if (
            tuple(sorted(set(self.principal_permissions), key=lambda item: item.value))
            != self.principal_permissions
        ):
            raise ValueError("principal_permissions must be unique and canonically ordered")
        if (
            not isinstance(self.authorization_source, str)
            or not self.authorization_source
            or self.authorization_source != self.authorization_source.strip()
        ):
            raise TypeError("authorization_source must be a non-empty trimmed string")

    @classmethod
    def from_verified_principal(
        cls,
        *,
        base_input: AuthzInput,
        principal_permissions: Iterable[RuntimePermission],
        authorization_source: str,
    ) -> RuntimePrincipalAuthzInput:
        """Project one server-resolved exact principal grant into the OPA envelope."""
        if type(base_input) is not AuthzInput:
            raise TypeError("base_input must be an exact AuthzInput")
        canonical_permissions = tuple(
            sorted(set(principal_permissions), key=lambda permission: permission.value)
        )
        if any(
            not isinstance(permission, RuntimePermission) for permission in canonical_permissions
        ):
            raise TypeError("principal permissions must use RuntimePermission values")
        return cls(
            request_method=base_input.request_method,
            request_path=base_input.request_path,
            request_headers=dict(base_input.request_headers),
            identity_tenant_id=base_input.identity_tenant_id,
            identity_cell_id=base_input.identity_cell_id,
            identity_principal_type=base_input.identity_principal_type,
            identity_roles=base_input.identity_roles,
            identity_mfa_verified=base_input.identity_mfa_verified,
            identity_sub=base_input.identity_sub,
            identity_spiffe_id=base_input.identity_spiffe_id,
            peer_spiffe_id=base_input.peer_spiffe_id,
            resource_tenant_id=base_input.resource_tenant_id,
            resource_kind=base_input.resource_kind,
            resource_artifact_id=base_input.resource_artifact_id,
            resource_pii_tier=base_input.resource_pii_tier,
            resource_metric_id=base_input.resource_metric_id,
            resource_columns=base_input.resource_columns,
            resource_requires_anonymization=base_input.resource_requires_anonymization,
            principal_permissions=canonical_permissions,
            authorization_source=authorization_source,
        )

    def to_opa_input(self) -> dict[str, Any]:
        """Return the core payload plus exact principal grants and provenance."""
        payload = super().to_opa_input()
        payload["identity"]["permissions"] = [item.value for item in self.principal_permissions]
        payload["identity"]["authorization_source"] = self.authorization_source
        return payload


@dataclass(frozen=True, slots=True)
class RuntimeActionAuthzInput(RuntimePrincipalAuthzInput):
    """Extend the principal OPA envelope with one sealed runtime action contract."""

    action_permission: RuntimePermission | None = None
    action_resource_class: str = ""
    action_binding_authority: BindingAuthority | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.action_permission, RuntimePermission):
            raise TypeError("action_permission must be a RuntimePermission")
        if (
            not isinstance(self.action_resource_class, str)
            or not self.action_resource_class
            or self.action_resource_class != self.action_resource_class.strip()
        ):
            raise TypeError("action_resource_class must be a non-empty trimmed string")
        if not isinstance(self.action_binding_authority, BindingAuthority):
            raise TypeError("action_binding_authority must be a BindingAuthority")

    @classmethod
    def from_bound_action(
        cls,
        *,
        base_input: AuthzInput,
        verification: ActionPermissionVerification,
        bound_resource: BoundAuthorizationResource,
        principal_permissions: Iterable[RuntimePermission] | None = None,
        authorization_source: str | None = None,
    ) -> RuntimeActionAuthzInput:
        """Build the OPA envelope from one exact preflight/binding handshake."""
        if type(base_input) is not AuthzInput:
            raise TypeError("base_input must be an exact AuthzInput")
        if type(verification) is not ActionPermissionVerification:
            raise TypeError("verification must be an exact ActionPermissionVerification")
        if type(bound_resource) is not BoundAuthorizationResource:
            raise TypeError("bound_resource must be an exact BoundAuthorizationResource")
        requirement = verification.requirement
        if bound_resource.requirement is not requirement:
            raise ValueError("action verification and resource binding must share identity")
        expected_tenant_id = bound_resource.tenant_id or ""
        if (
            base_input.resource_tenant_id != expected_tenant_id
            or base_input.resource_kind != bound_resource.resource_kind
            or base_input.resource_artifact_id != bound_resource.resource_id
        ):
            raise ValueError("base OPA resource does not match the frozen binding")

        sealed_permissions = getattr(verification, "granted_permissions", None)
        if sealed_permissions is not None:
            sealed_permissions = tuple(sealed_permissions)
            if any(
                not isinstance(permission, RuntimePermission) for permission in sealed_permissions
            ):
                raise TypeError("sealed principal permissions must use RuntimePermission values")
        raw_permissions = tuple(
            (
                sealed_permissions
                if sealed_permissions is not None
                else permissions_for_roles(verification.roles)
            )
            if principal_permissions is None
            else principal_permissions
        )
        if any(not isinstance(permission, RuntimePermission) for permission in raw_permissions):
            raise TypeError("principal permissions must use RuntimePermission values")
        canonical_permissions = tuple(
            sorted(set(raw_permissions), key=lambda permission: permission.value)
        )
        if sealed_permissions is not None and canonical_permissions != tuple(
            sorted(set(sealed_permissions), key=lambda permission: permission.value)
        ):
            raise ValueError("principal permissions differ from the sealed action verification")

        sealed_source = getattr(verification, "authorization_source", None)
        source = (
            (sealed_source if sealed_source is not None else CANONICAL_ROLE_AUTHORIZATION_SOURCE)
            if authorization_source is None
            else authorization_source
        )
        if sealed_source is not None and source != sealed_source:
            raise ValueError("authorization source differs from the sealed action verification")

        return cls(
            request_method=base_input.request_method,
            request_path=base_input.request_path,
            request_headers=dict(base_input.request_headers),
            identity_tenant_id=base_input.identity_tenant_id,
            identity_cell_id=base_input.identity_cell_id,
            identity_principal_type=base_input.identity_principal_type,
            identity_roles=base_input.identity_roles,
            identity_mfa_verified=base_input.identity_mfa_verified,
            identity_sub=base_input.identity_sub,
            identity_spiffe_id=base_input.identity_spiffe_id,
            peer_spiffe_id=base_input.peer_spiffe_id,
            resource_tenant_id=base_input.resource_tenant_id,
            resource_kind=base_input.resource_kind,
            resource_artifact_id=base_input.resource_artifact_id,
            resource_pii_tier=base_input.resource_pii_tier,
            resource_metric_id=base_input.resource_metric_id,
            resource_columns=base_input.resource_columns,
            resource_requires_anonymization=base_input.resource_requires_anonymization,
            action_permission=requirement.permission,
            action_resource_class=requirement.resource_binding.resource_kind,
            action_binding_authority=bound_resource.authority,
            principal_permissions=canonical_permissions,
            authorization_source=source,
        )

    def to_opa_input(self) -> dict[str, Any]:
        """Return the core payload plus the sealed runtime action contract."""
        payload = super().to_opa_input()
        permission = self.action_permission
        authority = self.action_binding_authority
        if not isinstance(permission, RuntimePermission) or not isinstance(
            authority,
            BindingAuthority,
        ):
            raise TypeError("runtime action OPA input is incomplete")
        payload["action"] = {"permission": permission.value}
        payload["resource"]["class"] = self.action_resource_class
        payload["resource"]["binding_authority"] = authority.value
        return payload


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi.routing import APIRoute
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Match
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from polisyos.core.security import DelegationTokenManager
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
    Message = dict[str, Any]
    Receive = Any
    Response = Any
    Scope = dict[str, Any]
    Send = Any


_PUBLIC_PATHS = frozenset(
    {"/health", "/ready", "/metrics", "/auth/callback", "/api/v1/public-decisions/verification"}
)
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
_SEALED_AUTHORIZATION_STATE_FIELDS = frozenset(AUTHORIZATION_STATE_FIELDS) | {
    "runtime_authorization_audit_emitted",
    "runtime_authorization_audit_terminal",
}


@dataclass(frozen=True, slots=True)
class _AuthorizationFailure:
    """Pair one fail-closed response with its durable denial reason."""

    response: Response
    reason: str


@dataclass(slots=True)
class _AuthorizationStateSeal:
    """Track any attempted mutation of protected authorization state."""

    violated: bool = False


def _require_policy_target_allow(allowed: bool | None) -> None:
    """Admit a related resource only after its own actual canonical policy ALLOW."""
    if allowed is not True:
        raise forbidden(
            "A required comparison source is not authorized",
            code="related_run_authorization_denied",
        )


class _AuthorizationStateMutationError(RuntimeError):
    """Signal an attempted handler-side mutation of sealed authority state."""


class _FrozenAuthorizationMapping(MutableMapping[str, object]):
    """Mapping-shaped immutable value retained for legacy read consumers.

    This deliberately does not inherit from ``dict``. Python's base ``dict``
    descriptors can mutate a subclass without invoking its overrides.
    """

    def __init__(
        self,
        value: dict[str, object],
        *,
        seal: _AuthorizationStateSeal,
    ) -> None:
        self._values = MappingProxyType(
            {key: _freeze_authorization_value(item, seal=seal) for key, item in value.items()}
        )
        self._seal = seal

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def _reject(self) -> Never:
        self._seal.violated = True
        raise _AuthorizationStateMutationError("frozen authorization resource cannot be mutated")

    def __setitem__(self, key: str, value: object) -> None:
        del key, value
        self._reject()

    def __delitem__(self, key: str) -> None:
        del key
        self._reject()

    def clear(self) -> None:
        self._reject()

    def pop(self, key: str, default: object = None) -> object:
        del key, default
        self._reject()

    def popitem(self) -> tuple[str, object]:
        self._reject()

    def setdefault(self, key: str, default: object = None) -> object:
        del key, default
        self._reject()

    def update(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._reject()

    def __ior__(self, value: object) -> _FrozenAuthorizationMapping:
        del value
        self._reject()


class _SealedAuthorizationState(MutableMapping[str, object]):
    """ASGI state mapping that rejects protected authority-field replacement.

    Protected values live only in an unreferenced backing dictionary exposed
    through ``MappingProxyType``. Mutable downstream state is held separately.
    """

    def __init__(
        self,
        value: dict[str, object],
        *,
        seal: _AuthorizationStateSeal,
    ) -> None:
        protected: dict[str, object] = {}
        mutable: dict[str, object] = {}
        for key, item in value.items():
            if _is_sealed_authorization_field(key):
                protected[key] = _freeze_authorization_value(item, seal=seal)
            else:
                mutable[key] = item
        self._protected = MappingProxyType(protected)
        self._mutable = mutable
        self._seal = seal

    def __getitem__(self, key: str) -> object:
        try:
            return self._protected[key]
        except KeyError:
            return self._mutable[key]

    def __iter__(self) -> Iterator[str]:
        yield from self._protected
        yield from self._mutable

    def __len__(self) -> int:
        return len(self._protected) + len(self._mutable)

    def _reject(self, key: str) -> Never:
        self._seal.violated = True
        raise _AuthorizationStateMutationError(f"authorization state field {key!r} is sealed")

    def __setitem__(self, key: str, value: object) -> None:
        if _is_sealed_authorization_field(key):
            self._reject(key)
        self._mutable[key] = value

    def __delitem__(self, key: str) -> None:
        if _is_sealed_authorization_field(key):
            self._reject(key)
        del self._mutable[key]

    def clear(self) -> None:
        self._reject("<bulk-clear>")

    def pop(self, key: str, default: object = None) -> object:
        if _is_sealed_authorization_field(key):
            self._reject(key)
        return self._mutable.pop(key, default)

    def popitem(self) -> tuple[str, object]:
        self._reject("<bulk-popitem>")

    def setdefault(self, key: str, default: object = None) -> object:
        if _is_sealed_authorization_field(key):
            self._reject(key)
        return self._mutable.setdefault(key, default)

    def update(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._reject("<bulk-update>")

    def __ior__(self, value: object) -> _SealedAuthorizationState:
        del value
        self._reject("<bulk-update>")


def _is_sealed_authorization_field(key: str) -> bool:
    return bool(
        key in _SEALED_AUTHORIZATION_STATE_FIELDS
        or key.startswith("authz_")
        or key.startswith("runtime_authorization_audit_")
    )


def _freeze_authorization_value(
    value: object,
    *,
    seal: _AuthorizationStateSeal,
) -> object:
    if isinstance(value, dict):
        return _FrozenAuthorizationMapping(value, seal=seal)
    if isinstance(value, list):
        return tuple(_freeze_authorization_value(item, seal=seal) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_authorization_value(item, seal=seal) for item in value)
    return value


def _seal_authorization_state(
    scope: Scope,
    *,
    receive: Receive,
) -> tuple[Request, _AuthorizationStateSeal]:
    state = scope.get("state")
    if not isinstance(state, dict):
        raise _AuthorizationStateMutationError(
            "ASGI authorization state is unavailable for sealing"
        )
    seal = _AuthorizationStateSeal()
    scope["state"] = _SealedAuthorizationState(
        cast("dict[str, object]", state),
        seal=seal,
    )
    return Request(scope, receive=receive), seal


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
        from polisyos.runtime.http.deployment_security_attestation import (
            require_attested_deployment_setting,
        )

        require_attested_deployment_setting(
            request,
            setting_name="authorization_perimeter",
            candidate=(
                self._enforce,
                self._shadow_mode,
                self._public_paths,
                self._delegation_manager,
                self._trusted_delegators,
            ),
            expected=(True, False, _PUBLIC_PATHS, None, frozenset()),
        )
        method = str(request.method).upper()
        path = str(request.url.path)
        unsafe = method in _UNSAFE_METHODS
        if not unsafe and path in self._public_paths:
            await self._app(scope, receive, send)
            return
        matched: tuple[APIRoute, dict[str, Any]] | None = None
        action_guarded = unsafe
        optional_action_dependency: OptionalActionPermissionDependency | None = None
        if not unsafe:
            matched = self._match_route(scope, method=method)
            if matched is not None:
                action_guarded = bool(route_action_permission_dependencies(cast("Any", matched[0])))
                optional_dependencies = route_optional_action_permission_dependencies(
                    cast("Any", matched[0])
                )
                if optional_dependencies:
                    optional_action_dependency = get_route_optional_action_permission_dependency(
                        cast("Any", matched[0])
                    )
        if not action_guarded and optional_action_dependency is None and self._opa is None:
            await self._app(scope, receive, send)
            return

        peer_spiffe_id = request.headers.get(self._mtls_spiffe_header, "")
        effective_scope, provenance, denied = self._resolve_effective_scope(
            request,
            peer_spiffe_id=peer_spiffe_id,
            unsafe=action_guarded,
        )
        if denied is not None:
            await self._send_failure(
                request,
                denied,
                scope=scope,
                receive=receive,
                send=send,
            )
            return
        if effective_scope is None:
            failure = _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=401 if unsafe else 403,
                    code="missing_access_scope",
                    detail="No authenticated access scope found in request context",
                ),
                reason="missing_access_scope",
            )
            await self._send_failure(
                request,
                failure,
                scope=scope,
                receive=receive,
                send=send,
                audit=action_guarded,
            )
            return

        request.state.access_scope = effective_scope
        request.state.authz_effective_scope = effective_scope
        request.state.authz_scope_provenance = provenance

        downstream_receive = receive
        bound_resource: BoundAuthorizationResource | None = None
        if action_guarded:
            binding_scope_token = set_current_access_scope(effective_scope)
            try:
                if matched is None:
                    matched = self._match_route(scope, method=method)
                if matched is not None:
                    route, child_scope = matched
                    matched_scope = dict(scope)
                    matched_scope.update(child_scope)
                    matched_request = Request(matched_scope, receive=receive)
                    preflight_error = await to_thread.run_sync(
                        partial(
                            self._preflight_action_dependency,
                            matched_request,
                            route,
                        )
                    )
                    if preflight_error is not None:
                        await self._send_failure(
                            matched_request,
                            preflight_error,
                            scope=scope,
                            receive=receive,
                            send=send,
                        )
                        return
                    try:
                        if unsafe:
                            body_bytes, downstream_receive = await _capture_and_replay_body(
                                request,
                                receive,
                                ceiling=self._body_ceiling,
                            )
                        else:
                            body_bytes = b""
                        requirement = cast(
                            "RouteAuthorizationRequirement",
                            matched_request.state.authz_route_requirement,
                        )
                        bound_resource = await to_thread.run_sync(
                            partial(
                                bind_authorization_resource,
                                matched_request,
                                requirement,
                                body_bytes,
                                max_body_bytes=self._body_ceiling,
                            )
                        )
                    except RuntimeHTTPError as exc:
                        await self._send_failure(
                            matched_request,
                            _AuthorizationFailure(
                                response=_response_for_runtime_error(
                                    matched_request,
                                    exc,
                                ),
                                reason=exc.code or exc.error,
                            ),
                            scope=scope,
                            receive=receive,
                            send=send,
                        )
                        return
                    self._freeze_binding(matched_request, bound_resource)
                elif unsafe and self._path_has_unsafe_route(scope):
                    await self._send_failure(
                        request,
                        _AuthorizationFailure(
                            response=self._problem(
                                request,
                                status_code=503,
                                code="authorization_contract_violation",
                                detail=(
                                    "Unsafe route could not be matched to one authorized operation"
                                ),
                            ),
                            reason="authorization_contract_violation",
                        ),
                        scope=scope,
                        receive=receive,
                        send=send,
                    )
                    return
                else:
                    await self._app(scope, receive, send)
                    return
            finally:
                reset_current_access_scope(binding_scope_token)

        shadow_deny = False
        if self._opa is not None:
            base_authz_input: AuthzInput | None = None
            resource = self._opa_resource(
                request,
                bound_resource=bound_resource,
                unsafe=action_guarded,
            )
            if resource is None:
                await self._send_failure(
                    request,
                    _AuthorizationFailure(
                        response=self._problem(
                            request,
                            status_code=503,
                            code="authorization_resource_unbound",
                            detail=(
                                "Unsafe request reached policy evaluation without a frozen resource"
                            ),
                        ),
                        reason="authorization_resource_unbound",
                    ),
                    scope=scope,
                    receive=receive,
                    send=send,
                )
                return
            base_authz_input = AuthzInput.for_http_request(
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
            authz_input: AuthzInput = base_authz_input
            if action_guarded:
                verification = getattr(
                    request.state,
                    "action_permission_verification",
                    None,
                )
                if (
                    type(verification) is not ActionPermissionVerification
                    or type(bound_resource) is not BoundAuthorizationResource
                ):
                    await self._send_failure(
                        request,
                        _AuthorizationFailure(
                            response=self._problem(
                                request,
                                status_code=503,
                                code="authorization_contract_violation",
                                detail=(
                                    "OPA evaluation lacks the exact action/resource "
                                    "preflight handshake"
                                ),
                            ),
                            reason="authorization_contract_violation",
                        ),
                        scope=scope,
                        receive=downstream_receive,
                        send=send,
                    )
                    return
                try:
                    authz_input = RuntimeActionAuthzInput.from_bound_action(
                        base_input=base_authz_input,
                        verification=verification,
                        bound_resource=bound_resource,
                        principal_permissions=cast(
                            "Any",
                            getattr(verification, "granted_permissions", None),
                        ),
                        authorization_source=cast(
                            "Any",
                            getattr(verification, "authorization_source", None),
                        ),
                    )
                except (TypeError, ValueError) as exc:
                    await self._send_failure(
                        request,
                        _AuthorizationFailure(
                            response=self._problem(
                                request,
                                status_code=503,
                                code="authorization_contract_violation",
                                detail=str(exc),
                            ),
                            reason="authorization_contract_violation",
                        ),
                        scope=scope,
                        receive=downstream_receive,
                        send=send,
                    )
                    return
            else:
                deployment_grants = getattr(
                    getattr(self._runtime_app, "state", object()),
                    "runtime_deployment_principal_grants",
                    None,
                )
                if deployment_grants is not None:
                    from polisyos.runtime.http.deployment_security_attestation import (
                        require_attested_deployment_component,
                    )
                    from polisyos.runtime.http.security import UserIdentityClaims

                    deployment_grants = cast(
                        "DeploymentPrincipalGrantResolver",
                        require_attested_deployment_component(
                            request,
                            component_name="principal_grants",
                            candidate=deployment_grants,
                        ),
                    )

                    if type(deployment_grants) is not DeploymentPrincipalGrantResolver:
                        await self._send_failure(
                            request,
                            _AuthorizationFailure(
                                response=self._problem(
                                    request,
                                    status_code=503,
                                    code="authorization_contract_violation",
                                    detail=("Deployment principal grant state has an invalid type"),
                                ),
                                reason="authorization_contract_violation",
                            ),
                            scope=scope,
                            receive=downstream_receive,
                            send=send,
                        )
                        return
                    claims = getattr(request.state, "user_claims", None)
                    if isinstance(claims, UserIdentityClaims):
                        deployment_permissions = deployment_grants.resolve_claim_permissions(
                            claims,
                            effective_subject=effective_scope.user_sub,
                            effective_tenant_id=effective_scope.tenant_id,
                            effective_cell_id=effective_scope.cell_id,
                        )
                        if deployment_permissions is not None:
                            try:
                                authz_input = RuntimePrincipalAuthzInput.from_verified_principal(
                                    base_input=base_authz_input,
                                    principal_permissions=deployment_permissions,
                                    authorization_source=(DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE),
                                )
                            except (TypeError, ValueError) as exc:
                                await self._send_failure(
                                    request,
                                    _AuthorizationFailure(
                                        response=self._problem(
                                            request,
                                            status_code=503,
                                            code="authorization_contract_violation",
                                            detail=str(exc),
                                        ),
                                        reason="authorization_contract_violation",
                                    ),
                                    scope=scope,
                                    receive=downstream_receive,
                                    send=send,
                                )
                                return
            opa_scope_token = set_current_access_scope(effective_scope)
            try:
                opa_response, shadow_deny, _policy_allowed = await self._evaluate_opa(
                    request,
                    authz_input,
                    fail_closed=action_guarded,
                )
            finally:
                reset_current_access_scope(opa_scope_token)
            if opa_response is not None:
                await opa_response(scope, receive, send)
                return
        else:
            base_authz_input = None

        if bound_resource is not None and bound_resource.policy_targets:
            target_response = await self._evaluate_bound_policy_targets(
                request,
                bound_resource,
                matched=matched,
                scope=effective_scope,
                peer_spiffe_id=peer_spiffe_id,
                base_input=base_authz_input,
            )
            if target_response is not None:
                await target_response(scope, downstream_receive, send)
                return

        if optional_action_dependency is not None:
            if matched is None:
                await self._send_failure(
                    request,
                    _AuthorizationFailure(
                        response=self._problem(
                            request,
                            status_code=503,
                            code="authorization_contract_violation",
                            detail="The optional action route could not be matched",
                        ),
                        reason="authorization_contract_violation",
                    ),
                    scope=scope,
                    receive=downstream_receive,
                    send=send,
                )
                return
            optional_result, optional_failure = await self._evaluate_optional_action(
                request,
                matched,
                optional_action_dependency,
                peer_spiffe_id=peer_spiffe_id,
                base_authz_input=base_authz_input,
            )
            if optional_failure is not None:
                await self._send_failure(
                    request,
                    optional_failure,
                    scope=scope,
                    receive=downstream_receive,
                    send=send,
                    audit=False,
                )
                return
            if type(optional_result) is not OptionalActionPermissionResult:
                await self._send_failure(
                    request,
                    _AuthorizationFailure(
                        response=self._problem(
                            request,
                            status_code=503,
                            code="authorization_contract_violation",
                            detail="The optional action result is invalid",
                        ),
                        reason="authorization_contract_violation",
                    ),
                    scope=scope,
                    receive=downstream_receive,
                    send=send,
                )
                return
            request.state.optional_action_permission_result = optional_result

        if action_guarded and bound_resource is not None:
            if bound_resource.policy_targets:
                dependency_response = await self._complete_target_admission_operation(
                    request,
                    partial(
                        to_thread.run_sync,
                        partial(self._execute_bound_authorization_dependencies, request),
                    ),
                )
                if dependency_response is not None:
                    await dependency_response(scope, downstream_receive, send)
                    return
            else:
                dependency_error = await to_thread.run_sync(
                    partial(self._execute_bound_authorization_dependencies, request)
                )
                if dependency_error is not None:
                    await self._send_failure(
                        request,
                        dependency_error,
                        scope=scope,
                        receive=downstream_receive,
                        send=send,
                    )
                    return

        scope_token = set_current_access_scope(effective_scope)
        try:
            downstream_send = _shadow_header_sender(send) if shadow_deny else send
            downstream_request = request
            state_seal: _AuthorizationStateSeal | None = None
            if action_guarded and bound_resource is not None:
                downstream_request, state_seal = _seal_authorization_state(
                    scope,
                    receive=downstream_receive,
                )
                downstream_send = self._binding_integrity_sender(
                    downstream_request,
                    binding=bound_resource,
                    state_seal=state_seal,
                    scope=scope,
                    receive=downstream_receive,
                    downstream_send=downstream_send,
                    failure_send=send,
                )
            try:
                await self._app(scope, downstream_receive, downstream_send)
            except _AuthorizationStateMutationError:
                if action_guarded and bound_resource is not None:
                    await self._send_failure(
                        downstream_request,
                        _AuthorizationFailure(
                            response=self._problem(
                                downstream_request,
                                status_code=503,
                                code="authorization_binding_integrity_violation",
                                detail=(
                                    "The frozen authorization resource changed during mutation"
                                ),
                            ),
                            reason="authorization_binding_integrity_violation",
                        ),
                        scope=scope,
                        receive=downstream_receive,
                        send=send,
                    )
                    return
                raise
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
    ) -> _AuthorizationFailure | None:
        from polisyos.runtime.http.step_up import get_route_step_up_dependency

        try:
            dependency = get_route_action_permission_dependency(cast("Any", route))
            step_up_dependency = get_route_step_up_dependency(
                cast("Any", route),
                action_dependency=dependency,
            )
        except RuntimeError as exc:
            return _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_contract_violation",
                    detail=str(exc),
                ),
                reason="authorization_contract_violation",
            )

        overrides = getattr(self._runtime_app, "dependency_overrides", {})
        if isinstance(overrides, dict) and dependency in overrides:
            return _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_dependency_overridden",
                    detail="The route action-permission dependency is overridden",
                ),
                reason="authorization_dependency_overridden",
            )
        if (
            step_up_dependency is not None
            and isinstance(overrides, dict)
            and step_up_dependency in overrides
        ):
            return _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_dependency_overridden",
                    detail="The route step-up dependency is overridden",
                ),
                reason="authorization_dependency_overridden",
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
            return _AuthorizationFailure(
                response=_response_for_runtime_error(request, exc),
                reason=exc.code or exc.error,
            )
        return None

    def _execute_bound_authorization_dependencies(
        self,
        request: Request,
    ) -> _AuthorizationFailure | None:
        """Execute the sealed route gates before any route application can run."""
        from polisyos.runtime.http.authorization import ActionPermissionDependency
        from polisyos.runtime.http.step_up import (
            StepUpAssertionVerification,
            StepUpDependency,
        )

        action_dependency = getattr(request.state, "authz_action_dependency", None)
        step_up_dependency = getattr(request.state, "authz_step_up_dependency", None)
        if type(action_dependency) is not ActionPermissionDependency:
            return _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_contract_violation",
                    detail="The matched route action dependency was not sealed",
                ),
                reason="authorization_contract_violation",
            )
        try:
            binding = getattr(request.state, "authz_bound_resource", None)
            if type(binding) is BoundAuthorizationResource and binding.policy_targets:
                effective_scope = getattr(request.state, "authz_effective_scope", None)
                if not isinstance(effective_scope, AccessScope):
                    raise RuntimeError("Related target admission has no verified access scope")
                token = set_current_access_scope(effective_scope)
                try:
                    _reconcile_bound_policy_targets(request, binding)
                finally:
                    reset_current_access_scope(token)
            action_verification = action_dependency(request)
            if type(action_verification) is not BoundActionPermissionVerification:
                raise RuntimeError("The action dependency did not consume the frozen resource")
            if step_up_dependency is None:
                return None
            if type(step_up_dependency) is not StepUpDependency:
                raise RuntimeError("The matched route step-up dependency was not sealed")
            step_up_verification = step_up_dependency(request)
            if type(step_up_verification) is not StepUpAssertionVerification:
                raise RuntimeError("The step-up dependency returned an invalid proof")
        except RuntimeHTTPError as exc:
            return _AuthorizationFailure(
                response=_response_for_runtime_error(request, exc),
                reason=exc.code or exc.error,
            )
        except RuntimeError as exc:
            return _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_contract_violation",
                    detail=str(exc),
                ),
                reason="authorization_contract_violation",
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
        state_seal: _AuthorizationStateSeal,
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
                state_seal=state_seal,
                require_executed_dependencies=successful_response is not False,
            ):
                rejected = True
                if response_started:
                    raise RuntimeError(
                        "authorization binding changed after response emission began"
                    )
                await self._send_failure(
                    request,
                    _AuthorizationFailure(
                        response=self._problem(
                            request,
                            status_code=503,
                            code="authorization_binding_integrity_violation",
                            detail=("The frozen authorization resource changed during mutation"),
                        ),
                        reason="authorization_binding_integrity_violation",
                    ),
                    scope=scope,
                    receive=receive,
                    send=failure_send,
                )
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
        state_seal: _AuthorizationStateSeal,
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
        if (
            require_executed_dependencies
            and getattr(
                state,
                "authz_step_up_requirement",
                None,
            )
            is not None
        ):
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
            not state_seal.violated
            and permission_proof_matches
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
    ) -> tuple[AccessScope | None, str, _AuthorizationFailure | None]:
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

    async def _complete_target_admission_operation(
        self,
        request: Request,
        operation: Callable[[], Awaitable[_AuthorizationFailure | None]],
    ) -> Response | None:
        """Terminalize every ordinary process-live target admission failure once.

        The operation includes policy/dependency calls and their cleanup. Its
        real evaluated prefix is already held on the original sealed request.
        Cancellation and other BaseException exits, and process crashes, are
        outside this boundary; it is not an audit crash-durability mechanism.
        """
        try:
            failure = await operation()
            if failure is not None and type(failure) is not _AuthorizationFailure:
                raise TypeError("Target admission returned an invalid terminal result")
        except Exception as exc:
            # One complete process-live quantity, rather than an exception-name
            # allowlist. Preserve a typed refusal; unexpected errors reveal no detail.
            failure = (
                _AuthorizationFailure(
                    response=_response_for_runtime_error(request, exc),
                    reason=exc.code or exc.error,
                )
                if isinstance(exc, RuntimeHTTPError)
                else _AuthorizationFailure(
                    response=self._problem(
                        request,
                        status_code=503,
                        code="related_run_admission_unavailable",
                        detail="Related target admission could not be completed",
                    ),
                    reason="related_run_admission_unavailable",
                )
            )
        if failure is None:
            return None
        try:
            emitted = await emit_runtime_authorization_audit_async(
                request,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason=failure.reason,
                raise_on_failure=True,
            )
        except Exception:
            # Exactly one attempt through the existing idempotent sealed owner.
            # Failure to record is itself a refusal, never a retry or invented event.
            emitted = False
        if not emitted:
            return self._problem(
                request,
                status_code=503,
                code="authorization_audit_unavailable",
                detail="Authorization audit is unavailable; comparison denied",
            )
        return failure.response

    async def _evaluate_bound_policy_targets(
        self,
        request: Request,
        binding: BoundAuthorizationResource,
        *,
        matched: tuple[APIRoute, dict[str, Any]] | None,
        scope: AccessScope,
        peer_spiffe_id: str,
        base_input: AuthzInput | None,
    ) -> Response | None:
        """Apply the common terminal boundary to the whole related policy operation."""
        return await self._complete_target_admission_operation(
            request,
            partial(
                self._admit_bound_policy_targets,
                request,
                binding,
                matched=matched,
                scope=scope,
                peer_spiffe_id=peer_spiffe_id,
                base_input=base_input,
            ),
        )

    async def _admit_bound_policy_targets(
        self,
        request: Request,
        binding: BoundAuthorizationResource,
        *,
        matched: tuple[APIRoute, dict[str, Any]] | None,
        scope: AccessScope,
        peer_spiffe_id: str,
        base_input: AuthzInput | None,
    ) -> _AuthorizationFailure | None:
        """Evaluate the complete source set; return failures without emitting audit."""
        decisions: list[RuntimeAuthorizationTargetDecision] = []
        request.state.authz_policy_target_decisions = ()

        def deny(response: Response, reason: str) -> _AuthorizationFailure:
            return _AuthorizationFailure(response=response, reason=reason)

        if self._opa is None or base_input is None or matched is None:
            return deny(
                self._problem(
                    request,
                    status_code=503,
                    code="related_run_policy_unavailable",
                    detail="Every comparison source requires an available authorization policy",
                ),
                "related_run_policy_unavailable",
            )
        verification = getattr(request.state, "action_permission_verification", None)
        if type(verification) is not ActionPermissionVerification:
            return deny(
                self._problem(
                    request,
                    status_code=503,
                    code="authorization_contract_violation",
                    detail="Related target authorization requires the exact permission preflight",
                ),
                "authorization_contract_violation",
            )
        _route, child_scope = matched
        previous = {
            name: getattr(request.state, name, _MISSING_AUTHORIZATION_STATE)
            for name in ("authz_decision", "authz_policy", "authz_reasons", "authz_allowed_columns")
        }
        token = set_current_access_scope(scope)
        try:

            async def reconcile_whole_set() -> _AuthorizationFailure | None:
                matched_scope = dict(request.scope)
                matched_scope.update(child_scope)
                matched_request = Request(matched_scope, receive=request.receive)
                try:
                    current = await to_thread.run_sync(
                        partial(
                            bind_authorization_resource,
                            matched_request,
                            binding.requirement,
                            b"",
                            max_body_bytes=self._body_ceiling,
                        )
                    )
                except RuntimeHTTPError as exc:
                    return deny(_response_for_runtime_error(request, exc), exc.code)
                if current != binding:
                    return deny(
                        self._problem(
                            request,
                            status_code=409,
                            code="comparison_target_set_changed",
                            detail="The comparison source set changed during authorization",
                        ),
                        "comparison_target_set_changed",
                    )
                return None

            for target in binding.policy_targets:
                target_base = AuthzInput.for_http_request(
                    request_method=base_input.request_method,
                    request_path=base_input.request_path,
                    request_headers=dict(base_input.request_headers),
                    scope=scope,
                    peer_spiffe_id=peer_spiffe_id,
                    resource_tenant_id=target.tenant_id or "",
                    resource_kind=target.resource_kind,
                    resource_artifact_id=target.resource_id,
                )
                target_input = RuntimeActionAuthzInput.from_bound_action(
                    base_input=target_base, verification=verification, bound_resource=target
                )
                response, _shadow, allowed = await self._evaluate_opa(
                    request,
                    target_input,
                    fail_closed=True,
                    defer_policy_denial=True,
                    defer_failure_audit=True,
                )
                if response is not None:
                    return deny(response, "related_run_policy_dependency_unavailable")
                try:
                    _require_policy_target_allow(allowed)
                except RuntimeHTTPError:
                    decisions.append(
                        RuntimeAuthorizationTargetDecision(
                            resource_id=target.resource_id,
                            resource_digest=target.resource_digest,
                            permission=target.requirement.permission.value,
                            outcome=RuntimeAuthorizationOutcome.DENY,
                            opa_policy=request.state.authz_policy,
                            opa_reasons=tuple(request.state.authz_reasons),
                        )
                    )
                    request.state.authz_policy_target_decisions = tuple(decisions)
                    changed = await reconcile_whole_set()
                    if changed is not None:
                        return changed
                    return deny(
                        self._problem(
                            request,
                            status_code=403,
                            code="related_run_authorization_denied",
                            detail="A required comparison source is not authorized",
                        ),
                        "related_run_authorization_denied",
                    )
                decisions.append(
                    RuntimeAuthorizationTargetDecision(
                        resource_id=target.resource_id,
                        resource_digest=target.resource_digest,
                        permission=target.requirement.permission.value,
                        outcome=RuntimeAuthorizationOutcome.ALLOW,
                        opa_policy=request.state.authz_policy,
                        opa_reasons=tuple(request.state.authz_reasons),
                    )
                )
                request.state.authz_policy_target_decisions = tuple(decisions)
                changed = await reconcile_whole_set()
                if changed is not None:
                    return changed
            return None
        finally:
            reset_current_access_scope(token)
            for name, value in previous.items():
                _restore_authorization_state_value(request.state, name, value)

    async def _evaluate_optional_action(
        self,
        request: Request,
        matched: tuple[APIRoute, dict[str, Any]],
        dependency: OptionalActionPermissionDependency,
        *,
        peer_spiffe_id: str,
        base_authz_input: AuthzInput | None,
    ) -> tuple[OptionalActionPermissionResult | None, _AuthorizationFailure | None]:
        """Evaluate one optional projection action through the shared OPA/binder path."""
        route, child_scope = matched
        matched_scope = dict(request.scope)
        matched_scope.update(child_scope)
        matched_request = Request(matched_scope, receive=request.receive)
        requirement = dependency.requirement
        action_dependency = ActionPermissionDependency(requirement)
        verification_field = "action_permission_verification"
        previous_verification = getattr(
            request.state,
            verification_field,
            _MISSING_AUTHORIZATION_STATE,
        )
        try:
            verification = action_dependency._authorize(matched_request)
        except RuntimeHTTPError as exc:
            if exc.code != "action_permission_denied":
                return None, _AuthorizationFailure(
                    response=_response_for_runtime_error(request, exc),
                    reason=exc.code or exc.error,
                )
            result = OptionalActionPermissionResult(
                requirement=requirement,
                allowed=False,
                denial_class="permission_denied",
            )
            audit_failure = await self._audit_optional_action(
                request,
                route=route,
                child_scope=child_scope,
                requirement=requirement,
                bound_resource=None,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason="action_permission_denied",
            )
            if audit_failure is not None:
                return None, audit_failure
            return result, None

        if type(verification) is not ActionPermissionVerification:
            return None, _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_contract_violation",
                    detail="Optional action preflight returned an invalid proof",
                ),
                reason="authorization_contract_violation",
            )

        try:
            bound_resource = await to_thread.run_sync(
                partial(
                    bind_authorization_resource,
                    matched_request,
                    requirement,
                    b"",
                    max_body_bytes=self._body_ceiling,
                )
            )
        except RuntimeHTTPError as exc:
            # The canonical owner guard owns a confirmed run refusal and its
            # single caller-scoped data-access event. Do not emit a provisional
            # binding denial that could duplicate that event or replace its 403.
            owner_error = await to_thread.run_sync(
                partial(
                    _recheck_optional_run_owner,
                    request,
                    matched_request,
                    requirement,
                )
            )
            if owner_error is not None:
                return None, _AuthorizationFailure(
                    response=_response_for_runtime_error(request, owner_error),
                    reason=owner_error.code or owner_error.error,
                )
            audit_failure = await self._audit_optional_action(
                request,
                route=route,
                child_scope=child_scope,
                requirement=requirement,
                bound_resource=None,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason=exc.code or exc.error,
            )
            if audit_failure is not None:
                return None, audit_failure
            return None, _AuthorizationFailure(
                response=_response_for_runtime_error(request, exc),
                reason=exc.code or exc.error,
            )
        finally:
            _restore_authorization_state_value(
                request.state,
                verification_field,
                previous_verification,
            )

        scope = getattr(request.state, "authz_effective_scope", None)
        if not isinstance(scope, AccessScope):
            return None, _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_binding_identity_required",
                    detail="Optional action binding has no verified access scope",
                ),
                reason="authorization_binding_identity_required",
            )
        action_input: AuthzInput | None = None
        if self._opa is not None:
            if base_authz_input is None:
                return None, _AuthorizationFailure(
                    response=self._problem(
                        request,
                        status_code=503,
                        code="authorization_contract_violation",
                        detail="Optional action OPA input is unavailable",
                    ),
                    reason="authorization_contract_violation",
                )
            action_base_input = AuthzInput.for_http_request(
                request_method=base_authz_input.request_method,
                request_path=base_authz_input.request_path,
                request_headers=dict(base_authz_input.request_headers),
                scope=scope,
                peer_spiffe_id=peer_spiffe_id,
                resource_tenant_id=bound_resource.tenant_id or "",
                resource_kind=bound_resource.resource_kind,
                resource_artifact_id=bound_resource.resource_id,
                resource_pii_tier=base_authz_input.resource_pii_tier,
                resource_metric_id=base_authz_input.resource_metric_id,
                resource_columns=base_authz_input.resource_columns,
                resource_requires_anonymization=base_authz_input.resource_requires_anonymization,
            )
            try:
                action_input = RuntimeActionAuthzInput.from_bound_action(
                    base_input=action_base_input,
                    verification=verification,
                    bound_resource=bound_resource,
                )
            except (TypeError, ValueError) as exc:
                return None, _AuthorizationFailure(
                    response=self._problem(
                        request,
                        status_code=503,
                        code="authorization_contract_violation",
                        detail=str(exc),
                    ),
                    reason="authorization_contract_violation",
                )

        outcome = RuntimeAuthorizationOutcome.ALLOW
        denial_class: Literal["permission_denied", "policy_denied"] | None = None
        if action_input is not None:
            opa_scope_token = set_current_access_scope(scope)
            try:
                opa_response, _shadow_deny, policy_allowed = await self._evaluate_opa(
                    request,
                    action_input,
                    fail_closed=True,
                    defer_policy_denial=True,
                )
            finally:
                reset_current_access_scope(opa_scope_token)
            if opa_response is not None:
                return None, _AuthorizationFailure(
                    response=opa_response,
                    reason="optional_action_authorization_unavailable",
                )
            if policy_allowed is not True:
                outcome = RuntimeAuthorizationOutcome.DENY
                denial_class = "policy_denied"

        denial_reason = (
            "authorization_denied" if outcome is RuntimeAuthorizationOutcome.DENY else ""
        )
        audit_failure = await self._audit_optional_action(
            request,
            route=route,
            child_scope=child_scope,
            requirement=requirement,
            bound_resource=bound_resource,
            outcome=outcome,
            denial_reason=denial_reason,
        )
        if audit_failure is not None:
            return None, audit_failure
        return (
            OptionalActionPermissionResult(
                requirement=requirement,
                allowed=outcome is RuntimeAuthorizationOutcome.ALLOW,
                denial_class=denial_class,
            ),
            None,
        )

    async def _audit_optional_action(
        self,
        request: Request,
        *,
        route: APIRoute,
        child_scope: dict[str, Any],
        requirement: RouteAuthorizationRequirement,
        bound_resource: BoundAuthorizationResource | None,
        outcome: RuntimeAuthorizationOutcome,
        denial_reason: str,
    ) -> _AuthorizationFailure | None:
        """Append an optional action audit under its exact permission/resource context."""
        state = request.state
        previous_values = {
            name: getattr(state, name, _MISSING_AUTHORIZATION_STATE)
            for name in (
                "authz_route_requirement",
                "authz_matched_route",
                "authz_bound_resource",
                "authz_resource_frozen",
                "authz_resource",
                "authz_policy",
                "authz_reasons",
            )
        }
        path_parameters = tuple(
            sorted(
                (str(key), str(value)) for key, value in child_scope.get("path_params", {}).items()
            )
        )
        state.authz_route_requirement = requirement
        state.authz_matched_route = MatchedAuthorizationRoute(
            method=request.method.upper(),
            path_template=route.path,
            name=route.name,
            path_parameters=path_parameters,
        )
        state.authz_bound_resource = bound_resource
        state.authz_resource_frozen = bound_resource is not None
        if outcome is RuntimeAuthorizationOutcome.DENY and denial_reason != "authorization_denied":
            state.authz_policy = ""
            state.authz_reasons = []
        if bound_resource is not None:
            state.authz_resource = bound_resource.to_opa_resource()
        try:
            await emit_runtime_authorization_audit_async(
                request,
                outcome=outcome,
                denial_reason=denial_reason,
                raise_on_failure=True,
            )
        except RuntimeAuthorizationAuditError:
            return _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=503,
                    code="authorization_audit_unavailable",
                    detail="Authorization audit is unavailable; optional projection withheld",
                ),
                reason="authorization_audit_unavailable",
            )
        finally:
            for name, value in previous_values.items():
                _restore_authorization_state_value(state, name, value)
        return None

    async def _evaluate_opa(
        self,
        request: Request,
        authz_input: AuthzInput,
        *,
        fail_closed: bool,
        defer_policy_denial: bool = False,
        defer_failure_audit: bool = False,
    ) -> tuple[Response | None, bool, bool | None]:
        opa = self._opa
        if opa is None:
            return None, False, None
        from polisyos.runtime.http.deployment_security_attestation import (
            require_attested_deployment_component,
        )

        opa = cast(
            "OPAClient",
            require_attested_deployment_component(
                request,
                component_name="opa_client",
                candidate=opa,
            ),
        )
        try:
            result = await self._opa_breaker.execute(
                lambda: asyncio.wait_for(
                    opa.check(authz_input),
                    timeout=self._opa_timeout_seconds,
                )
            )
        except TimeoutError:
            if not defer_failure_audit:
                await emit_runtime_authorization_audit_async(
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
                None,
            )
        except CircuitOpenError:
            if not defer_failure_audit:
                await emit_runtime_authorization_audit_async(
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
                None,
            )
        request.state.authz_decision = result.decision.value
        request.state.authz_policy = result.policy
        request.state.authz_reasons = list(result.reasons)
        request.state.authz_allowed_columns = _extract_allowed_columns(result.audit_entry)
        if "OPA_UNREACHABLE" in result.reasons:
            self._opa_breaker.record_failure()
            if not defer_failure_audit:
                await emit_runtime_authorization_audit_async(
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
                None,
            )
        if result.is_allowed:
            return None, False, True
        if defer_policy_denial:
            return None, False, False
        if fail_closed or (self._enforce and not self._shadow_mode):
            if not defer_failure_audit:
                await emit_runtime_authorization_audit_async(
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
                None,
            )
        logger.warning(
            "AUTHZ_SHADOW_DENY %s",
            {
                "error": "authorization_denied",
                "policy": result.policy,
                "reasons": list(result.reasons),
            },
        )
        return None, True, False

    def _deny_or_shadow(
        self,
        request: Request,
        *,
        reason: str,
        detail: str,
        fail_closed: bool,
    ) -> _AuthorizationFailure | None:
        if fail_closed or (self._enforce and not self._shadow_mode):
            return _AuthorizationFailure(
                response=self._problem(
                    request,
                    status_code=403,
                    code=reason,
                    detail=detail,
                ),
                reason=reason,
            )
        logger.warning("AUTHZ_SHADOW_GUARD %s", {"error": reason, "detail": detail})
        return None

    async def _send_failure(
        self,
        request: Request,
        failure: _AuthorizationFailure,
        *,
        scope: Scope,
        receive: Receive,
        send: Send,
        audit: bool = True,
    ) -> None:
        """Emit one idempotent denial and send its fail-closed response."""
        if audit:
            binding = getattr(request.state, "authz_bound_resource", None)
            strict_target_admission = type(binding) is BoundAuthorizationResource and bool(
                binding.policy_targets
            )
            try:
                emitted = await emit_runtime_authorization_audit_async(
                    request,
                    outcome=RuntimeAuthorizationOutcome.DENY,
                    denial_reason=failure.reason,
                    raise_on_failure=strict_target_admission,
                )
            except RuntimeAuthorizationAuditError:
                emitted = False
            if strict_target_admission and not emitted:
                failure = _AuthorizationFailure(
                    response=self._problem(
                        request,
                        status_code=503,
                        code="authorization_audit_unavailable",
                        detail="Authorization audit is unavailable; admission denied",
                    ),
                    reason="authorization_audit_unavailable",
                )
        with suppress(_AuthorizationStateMutationError):
            clear_request_auth_context(request.state)
        await failure.response(scope, receive, send)

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


__all__ = [
    "AuthzInput",
    "AuthzMiddleware",
    "MatchedAuthorizationRoute",
    "OPAClient",
    "RuntimeActionAuthzInput",
    "RuntimePrincipalAuthzInput",
]
