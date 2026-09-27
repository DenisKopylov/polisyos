"""Shared fixtures for exact route-bound control service authorization tests."""

from __future__ import annotations

import hashlib

from polisyos.core.contracts.control import NaturalLanguageRunRequest


def bound_nl_authorization_proof(
    claims: object,
    request: NaturalLanguageRunRequest,
):
    """Build a sealed proof with the exact `/runs/nl` route requirement."""
    from polisyos.runtime.http.authorization import (
        _BOUND_ACTION_PERMISSION_SEAL,
        ActionPermissionVerification,
        BoundActionPermissionVerification,
    )
    from polisyos.runtime.http.permissions import permissions_for_roles
    from polisyos.runtime.http.resource_binding import (
        BindingAuthority,
        BoundAuthorizationResource,
        _binding_resource_urn,
        _canonical_json,
        _digest_payload,
    )
    from polisyos.runtime.http.routes.control import _LAUNCH_NL_RUN_AUTHZ
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _nl_request_body_bytes,
    )

    requirement = _LAUNCH_NL_RUN_AUTHZ.requirement
    body_sha256 = "sha256:" + hashlib.sha256(_nl_request_body_bytes(request)).hexdigest()
    query_sha256 = "sha256:" + hashlib.sha256(b"").hexdigest()
    selectors = (("tenant_id", _canonical_json(claims.tenant_id)),)
    digest = _digest_payload(
        {
            "binding_version": "runtime.authorization.resource.v1",
            "permission": requirement.permission.value,
            "resource_kind": requirement.resource_binding.resource_kind,
            "authority": BindingAuthority.TENANT_COLLECTION.value,
            "tenant_id": claims.tenant_id,
            "body_sha256": body_sha256,
            "query_sha256": query_sha256,
            "selectors": selectors,
            "resolved_context_sha256": None,
        }
    )
    resource = BoundAuthorizationResource(
        requirement=requirement,
        tenant_id=claims.tenant_id,
        resource_kind=(
            f"{requirement.resource_binding.resource_kind}."
            f"{BindingAuthority.TENANT_COLLECTION.value}"
        ),
        resource_id=_binding_resource_urn(digest),
        resource_digest=digest,
        authority=BindingAuthority.TENANT_COLLECTION,
        body_sha256=body_sha256,
        query_sha256=query_sha256,
        canonical_selectors=selectors,
    )
    verification = ActionPermissionVerification(
        requirement=requirement,
        subject=claims.sub,
        tenant_id=claims.tenant_id,
        jwt_id=claims.jti,
        roles=claims.roles,
        authorization_source="canonical_role_permissions",
        granted_permissions=tuple(permissions_for_roles(claims.roles)),
    )
    return BoundActionPermissionVerification(
        verification=verification,
        bound_resource=resource,
        _seal=_BOUND_ACTION_PERMISSION_SEAL,
    )
