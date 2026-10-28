"""Validate a registered-SQL service request against the installed Runtime.

A live route proof is not, by itself, the neutral owner's verified producer
witness. The installed verifier and producer independently establish both.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_manifest_profile_sha256,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts.decision_validity import RegisteredSQLUseContract
from polisyos.core.security import AccessScope, UserIdentityClaims, tenant_scope
from polisyos.runtime.http.authorization import (
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    BoundActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.deployment_security import require_installed_deployment_security
from polisyos.runtime.http.errors import forbidden, service_unavailable, unprocessable_entity
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resilience import _require_runtime_ambient_ownership
from polisyos.runtime.http.resource_binding import (
    BindingAuthority,
    BoundAuthorizationResource,
    _canonical_json,
    _digest_payload,
    _parse_json_object,
)
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.registered_sql_service_contracts import (
    RegisteredSQLMaterializationRequest,
    RegisteredSQLRegistrationRequest,
    RegisteredSQLWithdrawalRequest,
)
from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLViewContract
from polisyos.scientist.validation.decision_validity import DecisionValidityService

if TYPE_CHECKING:
    from fastapi import Request

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.runtime.http.authorization import ActionPermissionDependency
    from polisyos.runtime.http.services.registered_sql_service_config import RegisteredSQLSourceSlot


_SELECTORS = ("slot_id", "request_ref", "event_id", "occurrence_id", "expected_predecessor")
REGISTERED_SQL_ADMIT_AUTHZ = require_action_permission(
    RuntimePermission.REGISTERED_SQL_ADMIT,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.registered_sql.materialization",
        selector_fields=_SELECTORS,
        required_selector_fields=_SELECTORS,
    ),
)


_REGISTER_SELECTORS = ("slot_id", "event_id")
_WITHDRAW_SELECTORS = ("slot_id", "event_id", "expected_predecessor", "target")
REGISTERED_SQL_REGISTER_AUTHZ = require_action_permission(
    RuntimePermission.REGISTERED_SQL_REGISTER,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.registered_sql.registration",
        selector_fields=_REGISTER_SELECTORS,
        required_selector_fields=_REGISTER_SELECTORS,
    ),
)
REGISTERED_SQL_WITHDRAW_AUTHZ = require_action_permission(
    RuntimePermission.REGISTERED_SQL_WITHDRAW,
    ResourceBindingSpec(
        source=ResourceBindingSource.REQUEST_COMPOSITE,
        resource_kind="runtime.registered_sql.withdrawal",
        selector_fields=_WITHDRAW_SELECTORS,
        required_selector_fields=_WITHDRAW_SELECTORS,
    ),
)

RegisteredSQLCommand = (
    RegisteredSQLMaterializationRequest
    | RegisteredSQLRegistrationRequest
    | RegisteredSQLWithdrawalRequest
)


def _command_action(command: RegisteredSQLCommand) -> ActionPermissionDependency:
    if type(command) is RegisteredSQLMaterializationRequest:
        return REGISTERED_SQL_ADMIT_AUTHZ
    if type(command) is RegisteredSQLRegistrationRequest:
        return REGISTERED_SQL_REGISTER_AUTHZ
    if type(command) is RegisteredSQLWithdrawalRequest:
        return REGISTERED_SQL_WITHDRAW_AUTHZ
    raise ValueError("registered_sql_command_type_invalid")


@dataclass(frozen=True, slots=True)
class RegisteredSQLRequestAdmission:
    """A verified request boundary, explicitly not C105 source authority."""

    slot: RegisteredSQLSourceSlot
    command: RegisteredSQLCommand
    principal_key: tuple[str, str, str, str, str]
    request_body_sha256: str
    resource_digest: str
    owner: DecisionValidityService


def _require_selected_content(
    store: ArtifactStore, ref: ArtifactRef, *, tenant_id: str, cell_id: str
) -> None:
    """Resolve bytes and exact manifest profile in the established tenant scope."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("registered_sql_selected_profile_required")
    manifest = store.get_manifest(ref)
    payload = store.get_bytes(ref)
    if (
        (manifest.artifact_id, manifest.kind, manifest.media_type)
        != (ref.artifact_id, ref.kind, ref.media_type)
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
        or (
            manifest.tenant_context is not None
            and (
                manifest.tenant_context.tenant_id != tenant_id
                or manifest.tenant_context.cell_id != cell_id
            )
        )
        or hashlib.sha256(payload).hexdigest() != ref.artifact_id.hex
        or len(payload) != manifest.byte_size
        or not store.verify(ref).ok
    ):
        raise ValueError("registered_sql_selected_content_mismatch")


def _installed_owner(request: Request) -> tuple[DecisionValidityService, ArtifactStore]:
    """Join the installed control service, debug reader, and exact CAS owner."""
    container = getattr(request.app.state, "runtime_container", None)
    control = getattr(container, "control_service", None)
    context = getattr(container, "runtime_api_context", None)
    owner = getattr(control, "_decision_validity_service", None)
    store = getattr(context, "store", None)
    debug = getattr(context, "debug", None)
    if (
        type(control) is not ControlPlaneService
        or owner is not getattr(container, "decision_validity_service", None)
        or type(owner) is not DecisionValidityService
        or owner is not getattr(debug, "bound_decision_validity_owner", None)
        or store is None
        or owner._store is not store
        or getattr(control, "_artifact_store", None) is not store
        or getattr(request.app.state, "_control_service", None) is not control
    ):
        raise service_unavailable(
            "The installed validity owner cannot be established",
            code="registered_sql_source_owner_unavailable",
        )
    return owner, store


def _require_registered_sql_request_identity(
    request: Request,
    *,
    command: RegisteredSQLCommand,
    body_bytes: bytes,
) -> RegisteredSQLRequestAdmission:
    """Reconcile the exact bound request, service grant, slot, and C105 owner.

    This return value is a request admission only; it cannot mint a source
    authority or a materialization. The service independently owns its source
    act even when a worker initiates the authenticated HTTP request.
    """
    action = _command_action(command)
    deployment = require_installed_deployment_security(request)
    if deployment is None:
        raise service_unavailable(
            "An attested deployment is required",
            code="registered_sql_deployment_not_established",
        )
    proof = getattr(request.state, "action_permission_verification", None)
    claims = getattr(request.state, "user_claims", None)
    scope = getattr(request.state, "authz_effective_scope", None)
    if (
        type(proof) is not BoundActionPermissionVerification
        or type(claims) is not UserIdentityClaims
        or type(scope) is not AccessScope
        or claims.is_expired
        or getattr(request.state, "authz_action_dependency", None) is not action
        or getattr(request.state, "authz_resource_frozen", False) is not True
        or getattr(request.state, "authz_bound_resource", None) is not proof.bound_resource
        or getattr(request.state, "authz_action_bound_resource", None) is not proof.bound_resource
        or action._authorize(request) is not proof
    ):
        raise forbidden(
            "A live source-specific bound service proof is required",
            code="registered_sql_action_proof_not_established",
        )
    verification = proof.verification
    resource = proof.bound_resource
    if (
        type(resource) is not BoundAuthorizationResource
        or verification.requirement is not action.requirement
        or resource.requirement is not verification.requirement
        or verification.authorization_source != DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE
        or verification.requirement.permission is not action.requirement.permission
        or resource.authority is not BindingAuthority.REQUEST_BOUND
        or resource.tenant_id is not None
        or resource.resolved_context is not None
        or scope.user_sub != claims.sub
        or scope.tenant_id != claims.tenant_id
        or scope.cell_id != claims.cell_id
        or scope.jwt_jti != claims.jti
        or bool(scope.delegation_jti)
        or verification.subject != claims.sub
        or verification.tenant_id != claims.tenant_id
        or verification.jwt_id != claims.jti
        or not claims.cell_id
        or not claims.jti
    ):
        raise forbidden(
            "Source authorization is not bound to the verified service identity",
            code="registered_sql_service_identity_mismatch",
        )

    try:
        decoded = _parse_json_object(body_bytes)
        parsed = type(command).model_validate_json(body_bytes, strict=True)
        query_bytes = request.scope.get("query_string", b"")
        if not isinstance(query_bytes, bytes) or parsed != command:
            raise ValueError("registered_sql_request_mismatch")
        selectors = tuple(
            sorted(
                (name, _canonical_json(decoded[name]))
                for name in action.requirement.resource_binding.selector_fields
            )
        )
        body_hash = "sha256:" + hashlib.sha256(body_bytes).hexdigest()
        query_hash = "sha256:" + hashlib.sha256(query_bytes).hexdigest()
        digest = _digest_payload(
            {
                "binding_version": "runtime.authorization.resource.v1",
                "permission": action.requirement.permission.value,
                "resource_kind": verification.requirement.resource_binding.resource_kind,
                "authority": resource.authority.value,
                "tenant_id": None,
                "body_sha256": body_hash,
                "query_sha256": query_hash,
                "selectors": selectors,
                "resolved_context_sha256": None,
            }
        )
        if (
            resource.body_sha256 != body_hash
            or resource.query_sha256 != query_hash
            or resource.resource_digest != digest
            or resource.canonical_selectors != selectors
        ):
            raise ValueError("registered_sql_resource_mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        raise forbidden(
            "The source request does not match its frozen authorization resource",
            code="registered_sql_resource_mismatch",
        ) from exc

    principal_key = (
        claims.iss.rstrip("/"),
        claims.aud,
        claims.sub,
        claims.tenant_id,
        claims.cell_id,
    )
    slots = deployment.config.registered_sql_sources
    slot = next((item for item in slots if item.slot_id == command.slot_id), None)
    grants = deployment.principal_grants.resolve_claim_permissions(
        claims,
        effective_subject=verification.subject,
        effective_tenant_id=verification.tenant_id,
        effective_cell_id=scope.cell_id,
    )
    if (
        slot is None
        or slot.identity_key != principal_key
        or grants is None
        or action.requirement.permission not in grants
        or tuple(sorted(grants, key=lambda value: value.value)) != verification.granted_permissions
    ):
        raise forbidden(
            "This service is not appointed to the selected source slot",
            code="registered_sql_slot_not_authorized",
        )

    if (
        type(command) is RegisteredSQLRegistrationRequest
        and command.event_id != slot.registration_event_id
    ):
        raise forbidden(
            "The genesis event is not configured for this slot",
            code="registered_sql_slot_not_authorized",
        )
    owner, _store = _installed_owner(request)
    return RegisteredSQLRequestAdmission(slot, command, principal_key, body_hash, digest, owner)


def require_registered_sql_request(
    request: Request,
    *,
    command: RegisteredSQLCommand,
    body_bytes: bytes,
) -> RegisteredSQLRequestAdmission:
    """Reconcile a live request and resolve all selected source contracts once."""
    admission = _require_registered_sql_request_identity(
        request, command=command, body_bytes=body_bytes
    )
    slot = admission.slot
    owner, store = _installed_owner(request)
    tenant_id, cell_id = admission.principal_key[3:]
    try:
        # The exact Runtime CAS factory proves ownership enforcement; the
        # scoped reads then consult its real selected-view ownership index.
        _require_runtime_ambient_ownership(store)
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            selected_refs = [slot.effective_view_contract_ref, slot.use_contract_ref]
            if type(command) is RegisteredSQLMaterializationRequest:
                selected_refs.append(command.request_ref)
            for reference in selected_refs:
                _require_selected_content(store, reference, tenant_id=tenant_id, cell_id=cell_id)
            view = validate_core_model_json_artifact(
                RegisteredSQLViewContract, store, slot.effective_view_contract_ref
            )
            validate_core_model_json_artifact(
                RegisteredSQLUseContract, store, slot.use_contract_ref
            )
            if view.provider_id != slot.provider_id or view.connector_id != slot.connector_id:
                raise ValueError("registered_sql_slot_view_mismatch")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise unprocessable_entity(
            "The selected source request or contract is not exactly resolvable",
            code="registered_sql_selected_input_not_established",
        ) from exc
    # Reconcile the identity and immutable binding after potentially slow CAS I/O.
    if (
        owner is not admission.owner
        or _require_registered_sql_request_identity(request, command=command, body_bytes=body_bytes)
        != admission
    ):
        raise service_unavailable(
            "The installed deployment changed",
            code="registered_sql_deployment_not_established",
        )
    return admission


def refuse_unverified_source_owner(_admission: RegisteredSQLRequestAdmission) -> None:
    """Fail closed until C105 owns a pinned, non-callback grant/capture verifier."""
    raise service_unavailable(
        "The source grant and producer witness cannot yet be verified by the validity owner",
        code="registered_sql_source_owner_verification_missing",
    )
