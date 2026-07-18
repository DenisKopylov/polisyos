"""Fail-closed action-permission contracts for runtime HTTP mutations.

Route modules declare one :class:`ActionPermissionDependency` for every unsafe
operation.  The declaration is both executable admission logic and the typed
handshake consumed by the pre-policy resource binder.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.runtime.http.access_audit import (
    RuntimeAuthorizationAuditError,
    RuntimeAuthorizationOutcome,
    emit_runtime_authorization_audit,
)
from polisyos.runtime.http.errors import (
    RuntimeHTTPError,
    forbidden,
    service_unavailable,
    unauthorized,
)
from polisyos.runtime.http.permissions import RuntimePermission, permissions_for_roles

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from fastapi import Request
    from fastapi.routing import APIRoute as _ImportedAPIRoute

    _APIRoute: type[_ImportedAPIRoute] | None

    class _DependencyNode(Protocol):
        """Minimal FastAPI dependency-tree shape used by route inspection."""

        call: object
        dependencies: Sequence[_DependencyNode]

    class _Route(Protocol):
        """Minimal APIRoute shape used by the structural authorization gate."""

        dependant: _DependencyNode
        methods: set[str]
        path: str

    class _Application(Protocol):
        """Minimal FastAPI application shape used by the structural gate."""

        routes: Sequence[object]

else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import Request
        from fastapi.routing import APIRoute as _ImportedAPIRoute
    except ModuleNotFoundError:  # pragma: no cover
        Request = cast("Any", object)
        _APIRoute: Any | None = None
    else:  # pragma: no cover - import wiring only
        _APIRoute = _ImportedAPIRoute

    _DependencyNode = Any
    _Route = Any
    _Application = Any


_UNSAFE_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_VERIFICATION_STATE_FIELD = "action_permission_verification"


@dataclass(frozen=True, slots=True)
class MatchedAuthorizationRoute:
    """Frozen route identity shared by action, binding, step-up, and audit."""

    method: str
    path_template: str
    name: str
    path_parameters: tuple[tuple[str, str], ...]


def principal_from_access_scope(
    scope: AccessScope,
) -> tuple[str, str, str, frozenset[PolicyOSRole]]:
    """Return one canonical principal tuple from a verified access scope.

    User, delegated-user, and service scopes deliberately share this path so
    resource binding cannot drift from action-permission identity semantics.
    """
    if not isinstance(scope, AccessScope):
        raise TypeError("scope must be an AccessScope")
    subject = scope.user_sub or scope.spiffe_id
    tenant_id = scope.tenant_id
    identity_id = scope.delegation_jti or scope.jwt_jti or scope.spiffe_id
    if not subject or not tenant_id or not identity_id:
        raise unauthorized(
            "The verified access scope lacks bound principal identity",
            code="action_identity_unbound",
        )
    return subject, tenant_id, identity_id, scope.roles


class ResourceBindingSource(StrEnum):
    """Closed strategies by which a route's policy resource must be bound."""

    OWNED_EXISTING_PATH = "owned_existing_path"
    OWNED_EXISTING_BATCH = "owned_existing_batch"
    RESOLVED_SELECTOR = "resolved_selector"
    RESOLVED_SELECTOR_BATCH = "resolved_selector_batch"
    CANDIDATE_TARGET_SLOT = "candidate_target_slot"
    OWNED_PARENT_OR_REQUEST_COMPOSITE = "owned_parent_or_request_composite"
    REQUEST_COMPOSITE = "request_composite"
    TENANT_COLLECTION = "tenant_collection"


def _validate_binding_token(value: str | None, *, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value or value != value.strip():
        raise TypeError(f"{field_name} must be a non-empty, trimmed string")


@dataclass(frozen=True, slots=True)
class ResourceBindingSpec:
    """Describe the only admissible pre-policy binding strategy for a route.

    ``body_field`` names a top-level array/identifier field for batch sources.
    ``parent_field`` names an optional owned parent carried in a request body.
    ``selector_fields`` identifies the request fields that form a canonical
    composite or candidate target. ``required_selector_fields`` is the closed
    subset that must be present and non-null before policy evaluation;
    ``required_selector_alternatives`` expresses disjunctive normal form where
    at least one complete selector group must be present.
    ``parent_required`` distinguishes routes whose owned parent is mandatory
    from routes that honestly support an unscoped request composite. The binder
    additionally content-binds the exact request bytes; these names never
    establish ownership by themselves.
    """

    source: ResourceBindingSource
    resource_kind: str
    path_parameter: str | None = None
    body_field: str | None = None
    parent_field: str | None = None
    selector_fields: tuple[str, ...] = ()
    required_selector_fields: tuple[str, ...] = ()
    required_selector_alternatives: tuple[tuple[str, ...], ...] = ()
    parent_required: bool = False
    allow_empty_body: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source, ResourceBindingSource):
            raise TypeError("resource binding source must be a ResourceBindingSource")
        _validate_binding_token(self.resource_kind, field_name="resource_kind")
        _validate_binding_token(self.path_parameter, field_name="path_parameter")
        _validate_binding_token(self.body_field, field_name="body_field")
        _validate_binding_token(self.parent_field, field_name="parent_field")
        if not isinstance(self.selector_fields, tuple):
            raise TypeError("selector_fields must be an immutable tuple")
        if not isinstance(self.required_selector_fields, tuple):
            raise TypeError("required_selector_fields must be an immutable tuple")
        if not isinstance(self.required_selector_alternatives, tuple):
            raise TypeError(
                "required_selector_alternatives must be an immutable tuple"
            )
        if not isinstance(self.parent_required, bool):
            raise TypeError("parent_required must be a bool")
        if not isinstance(self.allow_empty_body, bool):
            raise TypeError("allow_empty_body must be a bool")
        for selector in self.selector_fields:
            _validate_binding_token(selector, field_name="selector_fields entry")
        for selector in self.required_selector_fields:
            _validate_binding_token(
                selector,
                field_name="required_selector_fields entry",
            )
        for alternative in self.required_selector_alternatives:
            if not isinstance(alternative, tuple) or not alternative:
                raise TypeError(
                    "required_selector_alternatives entries must be non-empty tuples"
                )
            for selector in alternative:
                _validate_binding_token(
                    selector,
                    field_name="required_selector_alternatives entry",
                )
            if len(set(alternative)) != len(alternative):
                raise ValueError(
                    "required_selector_alternatives groups must not contain duplicates"
                )
        if len(set(self.selector_fields)) != len(self.selector_fields):
            raise ValueError("selector_fields must not contain duplicates")
        if len(set(self.required_selector_fields)) != len(self.required_selector_fields):
            raise ValueError("required_selector_fields must not contain duplicates")
        if not set(self.required_selector_fields).issubset(self.selector_fields):
            raise ValueError(
                "required_selector_fields must be a subset of selector_fields"
            )
        if len(set(self.required_selector_alternatives)) != len(
            self.required_selector_alternatives
        ):
            raise ValueError("required_selector_alternatives must not contain duplicates")
        if any(
            not set(alternative).issubset(self.selector_fields)
            for alternative in self.required_selector_alternatives
        ):
            raise ValueError(
                "required_selector_alternatives must be subsets of selector_fields"
            )

        self._validate_source_fields()

    def _validate_source_fields(self) -> None:
        source = self.source
        if source in {
            ResourceBindingSource.OWNED_EXISTING_PATH,
            ResourceBindingSource.RESOLVED_SELECTOR,
        }:
            if self.path_parameter is None:
                raise ValueError(f"{source.value} requires path_parameter")
            self._reject_fields(
                "body_field",
                "parent_field",
                "selector_fields",
                "required_selector_fields",
                "required_selector_alternatives",
                "parent_required",
            )
            return

        if source in {
            ResourceBindingSource.OWNED_EXISTING_BATCH,
            ResourceBindingSource.RESOLVED_SELECTOR_BATCH,
        }:
            if self.body_field is None:
                raise ValueError(f"{source.value} requires body_field")
            self._reject_fields(
                "path_parameter",
                "parent_field",
                "selector_fields",
                "required_selector_fields",
                "required_selector_alternatives",
                "parent_required",
            )
            return

        if source is ResourceBindingSource.CANDIDATE_TARGET_SLOT:
            if self.body_field is not None or self.parent_field is not None:
                raise ValueError("candidate_target_slot cannot use body_field or parent_field")
            if self.parent_required:
                raise ValueError("candidate_target_slot cannot require a body parent")
            if self.path_parameter is None and not self.selector_fields:
                raise ValueError("candidate_target_slot requires path_parameter or selector_fields")
            return

        if source is ResourceBindingSource.OWNED_PARENT_OR_REQUEST_COMPOSITE:
            if self.parent_field is None:
                raise ValueError("owned_parent_or_request_composite requires parent_field")
            self._reject_fields("path_parameter", "body_field")
            return

        if source is ResourceBindingSource.REQUEST_COMPOSITE:
            if not self.selector_fields:
                raise ValueError("request_composite requires selector_fields")
            self._reject_fields(
                "path_parameter",
                "body_field",
                "parent_field",
                "parent_required",
            )
            return

        if source is ResourceBindingSource.TENANT_COLLECTION:
            self._reject_fields(
                "path_parameter",
                "body_field",
                "parent_field",
                "selector_fields",
                "required_selector_fields",
                "required_selector_alternatives",
                "parent_required",
            )
            return

        raise TypeError(f"unsupported resource binding source: {source!r}")

    def _reject_fields(self, *field_names: str) -> None:
        populated = [name for name in field_names if bool(getattr(self, name))]
        if populated:
            joined = ", ".join(populated)
            raise ValueError(f"{self.source.value} does not accept {joined}")


@dataclass(frozen=True, slots=True)
class RouteAuthorizationRequirement:
    """Bind one canonical action permission to one resource-binding contract."""

    permission: RuntimePermission
    resource_binding: ResourceBindingSpec

    def __post_init__(self) -> None:
        if not isinstance(self.permission, RuntimePermission):
            raise TypeError("permission must be a RuntimePermission")
        if type(self.resource_binding) is not ResourceBindingSpec:
            raise TypeError("resource_binding must be a ResourceBindingSpec")


@dataclass(frozen=True, slots=True)
class ActionPermissionVerification:
    """Frozen proof that the exact route requirement admitted this principal."""

    requirement: RouteAuthorizationRequirement
    subject: str
    tenant_id: str
    jwt_id: str
    roles: frozenset[PolicyOSRole]


@dataclass(frozen=True, slots=True)
class BoundActionPermissionVerification:
    """Proof that the route dependency consumed one exact frozen resource."""

    verification: ActionPermissionVerification
    bound_resource: object

    def __post_init__(self) -> None:
        if type(self.verification) is not ActionPermissionVerification:
            raise TypeError("verification must be an ActionPermissionVerification")
        if self.bound_resource is None:
            raise TypeError("bound_resource must be the exact frozen resource object")


@dataclass(frozen=True, slots=True)
class ActionPermissionDependency:
    """Executable, inspectable FastAPI dependency for exact action permission."""

    requirement: RouteAuthorizationRequirement
    __polisyos_action_permission__: RouteAuthorizationRequirement = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if type(self.requirement) is not RouteAuthorizationRequirement:
            raise TypeError("requirement must be a RouteAuthorizationRequirement")
        object.__setattr__(
            self,
            "__polisyos_action_permission__",
            self.requirement,
        )

    def __call__(
        self,
        request: Request,
    ) -> ActionPermissionVerification | BoundActionPermissionVerification:
        """Authorize and append the terminal decision before handler execution."""
        try:
            verification = self._authorize(request)
        except RuntimeHTTPError as exc:
            emit_runtime_authorization_audit(
                request,
                outcome=RuntimeAuthorizationOutcome.DENY,
                denial_reason=exc.code or exc.error,
                raise_on_failure=False,
            )
            raise
        if (
            type(verification) is BoundActionPermissionVerification
            and getattr(request.state, "authz_step_up_requirement", None) is None
        ):
            try:
                emit_runtime_authorization_audit(
                    request,
                    outcome=RuntimeAuthorizationOutcome.ALLOW,
                    raise_on_failure=True,
                )
            except RuntimeAuthorizationAuditError as exc:
                raise service_unavailable(
                    "Authorization audit is unavailable; mutation denied",
                    code="authorization_audit_unavailable",
                ) from exc
        return verification

    def _authorize(
        self,
        request: Request,
    ) -> ActionPermissionVerification | BoundActionPermissionVerification:
        """Return the exact route proof or raise a typed fail-closed error."""
        state = getattr(request, "state", object())
        scope = getattr(state, "authz_effective_scope", None)
        if not isinstance(scope, AccessScope):
            scope = getattr(state, "access_scope", None)
        claims_value = getattr(state, "user_claims", None)
        claims = claims_value if isinstance(claims_value, UserIdentityClaims) else None
        if not isinstance(scope, AccessScope) and claims is None:
            raise unauthorized(
                "A verified identity or delegated access scope is required for this action",
                code="action_identity_required",
            )
        if not isinstance(scope, AccessScope) and claims is not None and claims.is_expired:
            raise unauthorized(
                "The verified user identity has expired",
                code="action_identity_expired",
            )

        if isinstance(scope, AccessScope):
            subject, tenant_id, identity_id, roles = principal_from_access_scope(scope)
        else:
            if claims is None:  # pragma: no cover - narrowed by the fail-closed guard above
                raise unauthorized(
                    "A verified identity is required for this action",
                    code="action_identity_required",
                )
            roles = claims.roles
            subject = claims.sub
            tenant_id = claims.tenant_id
            identity_id = claims.jti

        granted_permissions = permissions_for_roles(roles)
        if self.requirement.permission not in granted_permissions:
            raise forbidden(
                f"Permission {self.requirement.permission.value!r} is required",
                code="action_permission_denied",
            )

        verification = ActionPermissionVerification(
            requirement=self.requirement,
            subject=subject,
            tenant_id=tenant_id,
            jwt_id=identity_id,
            roles=roles,
        )
        state = request.state
        existing = getattr(state, _VERIFICATION_STATE_FIELD, None)
        if existing is not None:
            if type(existing) is BoundActionPermissionVerification:
                if existing.verification != verification:
                    raise forbidden(
                        "A different action-permission requirement was already verified",
                        code="action_permission_context_mismatch",
                    )
                frozen_resource = getattr(state, "authz_bound_resource", None)
                if (
                    frozen_resource is not existing.bound_resource
                    or not getattr(state, "authz_resource_frozen", False)
                    or getattr(frozen_resource, "requirement", None)
                    is not self.requirement
                ):
                    raise forbidden(
                        "The action-permission proof is not bound to the frozen resource",
                        code="action_permission_resource_mismatch",
                    )
                return existing
            if type(existing) is not ActionPermissionVerification:
                raise forbidden(
                    "Action-permission verification state is invalid",
                    code="action_permission_context_invalid",
                )
            if existing != verification:
                raise forbidden(
                    "A different action-permission requirement was already verified",
                    code="action_permission_context_mismatch",
                )
            if getattr(state, "authz_resource_frozen", False):
                frozen_resource = getattr(state, "authz_bound_resource", None)
                sealed_resource = getattr(state, "authz_action_bound_resource", None)
                if (
                    frozen_resource is None
                    or frozen_resource is not sealed_resource
                    or getattr(frozen_resource, "requirement", None)
                    is not self.requirement
                ):
                    raise forbidden(
                        "The action-permission proof cannot consume the frozen resource",
                        code="action_permission_resource_mismatch",
                    )
                consumed = BoundActionPermissionVerification(
                    verification=existing,
                    bound_resource=frozen_resource,
                )
                setattr(state, _VERIFICATION_STATE_FIELD, consumed)
                return consumed
            return existing

        setattr(state, _VERIFICATION_STATE_FIELD, verification)
        return verification


def require_action_permission(
    permission: RuntimePermission,
    resource_binding: ResourceBindingSpec,
) -> ActionPermissionDependency:
    """Build one executable route dependency from typed authorization inputs.

    Raw permission strings and raw resource-source strings are intentionally
    rejected even when their values happen to match enum members.
    """
    if not isinstance(permission, RuntimePermission):
        raise TypeError("permission must be a RuntimePermission")
    if type(resource_binding) is not ResourceBindingSpec:
        raise TypeError("resource_binding must be a ResourceBindingSpec")
    return ActionPermissionDependency(
        RouteAuthorizationRequirement(
            permission=permission,
            resource_binding=resource_binding,
        )
    )


def iter_route_dependency_calls(route: _Route) -> Iterator[object]:
    """Yield every dependency call in ``route`` recursively and in tree order."""

    def _walk(node: _DependencyNode, active_nodes: frozenset[int]) -> Iterator[object]:
        node_id = id(node)
        if node_id in active_nodes:
            raise RuntimeError("FastAPI dependency graph contains a cycle")
        next_active = active_nodes | {node_id}
        for child in node.dependencies:
            yield child.call
            yield from _walk(child, next_active)

    yield from _walk(route.dependant, frozenset())


def route_action_permission_dependencies(
    route: _Route,
) -> tuple[ActionPermissionDependency, ...]:
    """Return only genuine executable action dependencies declared by ``route``."""
    return tuple(
        dependency
        for dependency in iter_route_dependency_calls(route)
        if type(dependency) is ActionPermissionDependency
    )


def _route_label(route: _Route) -> str:
    unsafe_methods = sorted(set(route.methods) & _UNSAFE_HTTP_METHODS)
    method_label = ",".join(unsafe_methods) if unsafe_methods else "<safe>"
    return f"{method_label} {route.path}"


def get_route_action_permission_dependency(route: _Route) -> ActionPermissionDependency:
    """Return the route's sole genuine dependency or reject an unsafe declaration."""
    label = _route_label(route)
    try:
        dependency_calls = tuple(iter_route_dependency_calls(route))
    except RuntimeError as exc:
        raise RuntimeError(f"{label} has an invalid dependency graph: {exc}") from exc
    impostors = [
        dependency
        for dependency in dependency_calls
        if getattr(dependency, "__polisyos_action_permission__", None) is not None
        and type(dependency) is not ActionPermissionDependency
    ]
    dependencies = tuple(
        dependency
        for dependency in dependency_calls
        if type(dependency) is ActionPermissionDependency
    )
    direct_dependencies = tuple(
        child.call
        for child in route.dependant.dependencies
        if type(child.call) is ActionPermissionDependency
    )
    if impostors:
        raise RuntimeError(f"{label} has a marker-only action-permission dependency")
    if len(dependencies) != 1 or len(direct_dependencies) != 1:
        raise RuntimeError(
            f"{label} requires one direct ActionPermissionDependency; "
            f"found={len(dependencies)} direct={len(direct_dependencies)}"
        )

    dependency = dependencies[0]
    marker = dependency.__polisyos_action_permission__
    if marker is not dependency.requirement or not isinstance(
        marker.permission,
        RuntimePermission,
    ):
        raise RuntimeError(f"{label} has an invalid action-permission marker")
    return dependency


def get_route_authorization_requirement(route: _Route) -> RouteAuthorizationRequirement:
    """Return the route's exact, structurally validated authorization requirement."""
    return get_route_action_permission_dependency(route).requirement


def assert_mutating_route_authorization_contract(app: _Application) -> None:
    """Reject an app containing any unsafe route without one real dependency."""
    api_route = _APIRoute
    if api_route is None:
        raise RuntimeError("route authorization inspection requires FastAPI")

    violations: list[str] = []
    for candidate in app.routes:
        if not isinstance(candidate, api_route):
            continue
        route = cast("_Route", cast("object", candidate))
        if not (set(route.methods) & _UNSAFE_HTTP_METHODS):
            continue
        try:
            _ = get_route_action_permission_dependency(route)
        except RuntimeError as exc:
            violations.append(str(exc))

    if violations:
        details = "\n".join(f"- {violation}" for violation in violations)
        raise RuntimeError("mutating route authorization contract failed:\n" + details)


def install_route_authorization_openapi_contract(app: object) -> None:
    """Project every unsafe route's typed requirement into OpenAPI."""
    application = cast("Any", app)
    original_openapi = application.openapi
    cached: dict[str, Any] | None = None

    def _custom_openapi() -> dict[str, Any]:
        nonlocal cached
        if cached is not None:
            return cached
        schema = deepcopy(original_openapi())
        for candidate in application.routes:
            if _APIRoute is None or not isinstance(candidate, _APIRoute):
                continue
            unsafe_methods = set(candidate.methods) & _UNSAFE_HTTP_METHODS
            if not unsafe_methods:
                continue
            route = cast("_Route", cast("object", candidate))
            requirement = get_route_authorization_requirement(route)
            binding = requirement.resource_binding
            binding_payload = {
                "source": binding.source.value,
                "resource_kind": binding.resource_kind,
                **(
                    {"path_parameter": binding.path_parameter}
                    if binding.path_parameter is not None
                    else {}
                ),
                **({"body_field": binding.body_field} if binding.body_field is not None else {}),
                **(
                    {"parent_field": binding.parent_field}
                    if binding.parent_field is not None
                    else {}
                ),
                **(
                    {"selector_fields": list(binding.selector_fields)}
                    if binding.selector_fields
                    else {}
                ),
                **(
                    {
                        "required_selector_fields": list(
                            binding.required_selector_fields
                        )
                    }
                    if binding.required_selector_fields
                    else {}
                ),
                **(
                    {
                        "required_selector_alternatives": [
                            list(alternative)
                            for alternative in binding.required_selector_alternatives
                        ]
                    }
                    if binding.required_selector_alternatives
                    else {}
                ),
                **({"parent_required": True} if binding.parent_required else {}),
                **({"allow_empty_body": True} if binding.allow_empty_body else {}),
            }
            for method in unsafe_methods:
                operation = schema["paths"][candidate.path][method.lower()]
                operation["x-polisyos-action-permission"] = requirement.permission.value
                operation["x-polisyos-resource-binding"] = binding_payload
        cached = schema
        return schema

    application.openapi = _custom_openapi


__all__ = [
    "ActionPermissionDependency",
    "ActionPermissionVerification",
    "BoundActionPermissionVerification",
    "MatchedAuthorizationRoute",
    "ResourceBindingSource",
    "ResourceBindingSpec",
    "RouteAuthorizationRequirement",
    "assert_mutating_route_authorization_contract",
    "get_route_action_permission_dependency",
    "get_route_authorization_requirement",
    "install_route_authorization_openapi_contract",
    "iter_route_dependency_calls",
    "principal_from_access_scope",
    "require_action_permission",
    "route_action_permission_dependencies",
]
