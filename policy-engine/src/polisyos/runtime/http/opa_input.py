"""Runtime-owned OPA input carrying sealed action and resource authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.security.authz import AuthzInput
from polisyos.runtime.http.authorization import (
    CANONICAL_ROLE_AUTHORIZATION_SOURCE,
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    ActionPermissionVerification,
)
from polisyos.runtime.http.permissions import RuntimePermission, permissions_for_roles
from polisyos.runtime.http.resource_binding import (
    BindingAuthority,
    BoundAuthorizationResource,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any


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
    """Extend the principal OPA envelope with one verified runtime action contract.

    The base :class:`AuthzInput` remains available to non-mutating legacy policy
    consumers. Runtime mutations use this subtype so action permission, exact
    resource class, binding authority, principal grants, and grant provenance
    reach OPA as one immutable value.
    """

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
        """Build the OPA envelope from one exact preflight/binding handshake.

        Args:
            base_input: Core identity/request/resource projection.
            verification: Exact action proof emitted by the route dependency.
            bound_resource: Exact frozen resource emitted by the binder.
            principal_permissions: Optional deployment-owned exact grants. When
                absent, the current canonical role projection is used.
            authorization_source: Declared grant provenance. When absent, the
                canonical server role projection is declared.

        Returns:
            An immutable OPA input carrying the sealed runtime contract.

        Raises:
            TypeError: If any producer is not the exact expected runtime type.
            ValueError: If the producers disagree about action or resource.
        """
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


__all__ = [
    "CANONICAL_ROLE_AUTHORIZATION_SOURCE",
    "DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE",
    "RuntimeActionAuthzInput",
    "RuntimePrincipalAuthzInput",
]
