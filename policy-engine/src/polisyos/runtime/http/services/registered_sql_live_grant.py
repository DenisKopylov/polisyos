"""Live, deployment-authenticated issuer verifier for one C105 owner.

The C105 neutral port must invoke only its owner-pinned instance.  This module
cannot install that pin on its own and deliberately does not mint a C105
SourceAdmissionAuthority.  A witness is input to a verifier, never authority.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from polisyos.core.artifacts.manifest import artifact_ref_identity_key
from polisyos.core.contracts.decision_validity import SourceRegistrationReceipt
from polisyos.runtime.http.authz_middleware import _SealedAuthorizationState
from polisyos.runtime.http.deployment_security import require_installed_deployment_security
from polisyos.runtime.http.errors import forbidden, service_unavailable
from polisyos.runtime.http.services.registered_sql_service import (
    RegisteredSQLCommand,
    RegisteredSQLRequestAdmission,
    _installed_owner,
    _require_registered_sql_request_identity,
    require_registered_sql_request,
)
from polisyos.runtime.http.services.registered_sql_service_contracts import (
    RegisteredSQLMaterializationRequest,
    RegisteredSQLRegistrationRequest,
    RegisteredSQLWithdrawalRequest,
)
from polisyos.scientist.validation.source_admission_port import SourceIssuerCall, SourceIssuerScope

if TYPE_CHECKING:
    from fastapi import Request


@dataclass(frozen=True, slots=True, init=False)
class RegisteredSQLLiveGrantWitness:
    """Carry one real served request to the owner-selected issuer verifier.

    Constructor access is not authority: the verifier repeats the deployment,
    grant, owner, body, action and operation checks. Its witness factory verifies
    the bearer signature once before the transaction. This
    object must never be serialized, logged, or treated as a durable receipt.
    """

    request: Request = field(repr=False)
    command: RegisteredSQLCommand
    body_bytes: bytes = field(repr=False)
    initial: RegisteredSQLRequestAdmission = field(repr=False)
    initial_slot_json: str = field(repr=False)
    initial_command_json: str = field(repr=False)
    bearer_sha256: str = field(repr=False)
    proof: object = field(repr=False)
    claims_json: str = field(repr=False)
    _seal: object = field(repr=False, compare=False)

    def __init__(self) -> None:
        raise TypeError("a source grant witness requires the installed Runtime verifier")


def _bearer(request: Request) -> str:
    raw = request.headers.get("authorization", "")
    if not raw.startswith("Bearer "):
        raise forbidden("A source-service bearer is required", code="registered_sql_bearer_missing")
    token = raw[7:]
    if not token or token != token.strip() or any(char in token for char in "\r\n"):
        raise forbidden(
            "The source-service bearer is invalid", code="registered_sql_bearer_invalid"
        )
    return token


def _require_sealed_request(request: Request, proof: object) -> None:
    state = request.scope.get("state")
    if (
        type(state) is not _SealedAuthorizationState
        or state._seal.violated
        or getattr(request.state, "action_permission_verification", None) is not proof
    ):
        raise forbidden(
            "The served action proof is not sealed", code="registered_sql_action_unsealed"
        )


def _same_ref(left: object, right: object) -> bool:
    try:
        return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)
    except (AttributeError, TypeError, ValueError):
        return False


def _registration_matches(
    registration: SourceRegistrationReceipt, scope: SourceIssuerScope, genesis_id: str
) -> bool:
    return bool(
        type(registration) is SourceRegistrationReceipt
        and registration.event_id == genesis_id
        and registration.issuer_key == scope.issuer_key
        and registration.tenant_id == scope.tenant_id
        and registration.cell_id == scope.cell_id
        and registration.provider_id == scope.provider_id
        and registration.registration_key == scope.registration_key
        and _same_ref(registration.effective_view_contract_ref, scope.effective_view_contract_ref)
        and _same_ref(registration.use_contract_ref, scope.use_contract_ref)
    )


class _AppReference:
    """Minimal adapter for the already installed app/owner reconciliation."""

    def __init__(self, app: object) -> None:
        self.app = app


class RegisteredSQLLiveGrantVerifier:
    """Reverify the exact deployment request and its one admissible SQL act."""

    __slots__ = ("_app", "_deployment", "_owner", "_witness_seal")

    def __init__(self, app: object) -> None:
        deployment = require_installed_deployment_security(app)
        if deployment is None:
            raise service_unavailable(
                "The SQL source issuer has no installed deployment",
                code="registered_sql_deployment_not_established",
            )
        owner, _store = _installed_owner(_AppReference(app))
        self._app = app
        self._deployment = deployment
        self._owner = owner
        self._witness_seal = object()

    def _require_pin(self) -> None:
        try:
            self._owner._require_registered_sql_issuer_verifier(self)
            installed = require_installed_deployment_security(self._app)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            raise service_unavailable(
                "The SQL source issuer is not pinned to the installed validity owner",
                code="registered_sql_source_owner_verification_missing",
            ) from exc
        if (
            type(self) is not RegisteredSQLLiveGrantVerifier
            or type(self).verify is not _ORIGINAL_VERIFY
            or installed is not self._deployment
        ):
            raise service_unavailable(
                "The SQL source issuer is not pinned to the installed validity owner",
                code="registered_sql_source_owner_verification_missing",
            )

    def witness(
        self,
        request: Request,
        *,
        command: RegisteredSQLCommand,
        body_bytes: bytes,
    ) -> RegisteredSQLLiveGrantWitness:
        """Resolve the selected inputs once, then create a non-authoritative witness."""
        self._require_pin()
        admission = require_registered_sql_request(request, command=command, body_bytes=body_bytes)
        proof = getattr(request.state, "action_permission_verification", None)
        _require_sealed_request(request, proof)
        token = _bearer(request)
        try:
            # Network-capable identity verification occurs only before C105's
            # transaction. The opaque witness retains its exact result.
            verified_claims = self._deployment.identity_provider.extract_user_claims(
                token, expected_cell_id=admission.slot.cell_id
            )
        except Exception as exc:
            raise forbidden(
                "The source bearer cannot be verified", code="registered_sql_bearer_invalid"
            ) from exc
        if verified_claims != getattr(request.state, "user_claims", None):
            raise forbidden(
                "The source bearer identity changed", code="registered_sql_bearer_invalid"
            )
        claims_json = verified_claims.model_dump_json()
        slot_json = admission.slot.model_dump_json()
        command_json = command.model_dump_json()
        bearer_sha256 = hashlib.sha256(token.encode("utf-8")).hexdigest()
        witness = object.__new__(RegisteredSQLLiveGrantWitness)
        for name, value in (
            ("request", request),
            ("command", command),
            ("body_bytes", bytes(body_bytes)),
            ("initial", admission),
            ("initial_slot_json", slot_json),
            ("initial_command_json", command_json),
            ("bearer_sha256", bearer_sha256),
            ("proof", proof),
            ("claims_json", claims_json),
            ("_seal", self._witness_seal),
        ):
            object.__setattr__(witness, name, value)
        # A served JWT must pass the same verifier later used at the commit fence.
        if type(command) is RegisteredSQLRegistrationRequest:
            call = SourceIssuerCall(operation="genesis", event_id=command.event_id)
        elif type(command) is RegisteredSQLWithdrawalRequest:
            call = SourceIssuerCall(
                operation="withdraw",
                event_id=command.event_id,
                expected_predecessor=command.expected_predecessor,
                target=command.target,
            )
        else:
            call = SourceIssuerCall(
                operation="acquire",
                event_id=command.event_id,
                expected_predecessor=command.expected_predecessor,
            )
        self.verify(witness, call)
        return witness

    def verify(self, witness: object, call: SourceIssuerCall) -> SourceIssuerScope:
        """Recheck the verified witness and source operation at the decisive fence.

        This method performs no network or CAS access. It checks the opaque
        verifier-created witness and rechecks the sealed proof, claims expiry,
        exact operation and deployment attestation.
        """
        self._require_pin()
        if (
            type(witness) is not RegisteredSQLLiveGrantWitness
            or type(call) is not SourceIssuerCall
            or getattr(witness, "_seal", None) is not self._witness_seal
        ):
            raise forbidden(
                "The SQL source witness is invalid", code="registered_sql_grant_invalid"
            )
        request = witness.request
        if getattr(request, "app", None) is not self._app:
            raise forbidden(
                "The source request belongs to another app", code="registered_sql_grant_invalid"
            )
        _require_sealed_request(request, witness.proof)
        token = _bearer(request)
        if (
            hashlib.sha256(token.encode("utf-8")).hexdigest() != witness.bearer_sha256
            or getattr(request, "_body", None) != witness.body_bytes
        ):
            raise forbidden("The source request changed", code="registered_sql_grant_invalid")
        current = _require_registered_sql_request_identity(
            request, command=witness.command, body_bytes=witness.body_bytes
        )
        if (
            current.owner is not self._owner
            or current != witness.initial
            or current.slot.model_dump_json() != witness.initial_slot_json
            or witness.command.model_dump_json() != witness.initial_command_json
        ):
            raise forbidden("The source grant changed", code="registered_sql_grant_invalid")
        claims = getattr(request.state, "user_claims", None)
        if claims is None or claims.model_dump_json() != witness.claims_json:
            raise forbidden(
                "The source bearer identity changed", code="registered_sql_bearer_invalid"
            )
        # Verify the pin again before returning to the owner's transaction.
        self._require_pin()
        slot, command = current.slot, current.command
        if type(command) is RegisteredSQLRegistrationRequest:
            permitted = frozenset({"genesis", "read_event"})
            allowed_calls = {"genesis", "read_event"}
        elif type(command) is RegisteredSQLWithdrawalRequest:
            permitted = frozenset({"withdraw", "read_event"})
            allowed_calls = {"withdraw", "read_event"}
        else:
            permitted = frozenset({"admit", "read_event"})
            allowed_calls = {"read_event", "current_head", "acquire", "admit"}
        result = SourceIssuerScope(
            issuer_key=slot.issuer_key,
            tenant_id=slot.tenant_id,
            cell_id=slot.cell_id,
            provider_id=slot.provider_id,
            registration_key=slot.registration_key,
            effective_view_contract_ref=slot.effective_view_contract_ref,
            use_contract_ref=slot.use_contract_ref,
            permitted_operations=permitted,
        )
        if call.operation not in allowed_calls:
            raise forbidden(
                "The source operation is outside this grant",
                code="registered_sql_grant_scope_mismatch",
            )
        if call.operation == "read_event":
            if call.event_id not in {slot.registration_event_id, command.event_id}:
                raise forbidden(
                    "The requested event is outside this grant",
                    code="registered_sql_grant_scope_mismatch",
                )
            if call.expected_predecessor is not None and (
                type(command) is RegisteredSQLRegistrationRequest
                or call.expected_predecessor != command.expected_predecessor
            ):
                raise forbidden(
                    "The event predecessor changed", code="registered_sql_grant_scope_mismatch"
                )
        elif type(command) is RegisteredSQLRegistrationRequest:
            if call.event_id != slot.registration_event_id:
                raise forbidden(
                    "The genesis event changed", code="registered_sql_grant_scope_mismatch"
                )
        elif (
            command.event_id == slot.registration_event_id
            or call.event_id != command.event_id
            or call.expected_predecessor != command.expected_predecessor
        ):
            raise forbidden(
                "The source command changed", code="registered_sql_grant_scope_mismatch"
            )
        if call.registration is not None and not _registration_matches(
            call.registration, result, slot.registration_event_id
        ):
            raise forbidden(
                "The source registration changed", code="registered_sql_grant_scope_mismatch"
            )
        # Initial withdrawal is checked again after the owner resolves its target.
        if (
            call.operation in {"current_head", "admit", "withdraw"}
            and call.registration is None
            and (call.operation != "withdraw" or call.target is None)
        ):
            raise forbidden(
                "The source registration is required",
                code="registered_sql_grant_scope_mismatch",
            )
        if call.operation == "withdraw" and (
            type(command) is not RegisteredSQLWithdrawalRequest or call.target != command.target
        ):
            raise forbidden(
                "The withdrawal target changed", code="registered_sql_grant_scope_mismatch"
            )
        if call.operation == "admit" and call.materialization is None:
            raise forbidden(
                "The SQL occurrence is required", code="registered_sql_grant_scope_mismatch"
            )
        if call.materialization is not None:
            materialization = call.materialization
            if (
                type(command) is not RegisteredSQLMaterializationRequest
                or call.event_id != command.event_id
                or materialization.registration != call.registration
                or materialization.occurrence_id != command.occurrence_id
                or not _same_ref(materialization.request_ref, command.request_ref)
            ):
                raise forbidden(
                    "The SQL occurrence changed", code="registered_sql_grant_scope_mismatch"
                )

        return result


_ORIGINAL_VERIFY = RegisteredSQLLiveGrantVerifier.verify


def install_registered_sql_live_grant_verifier(app: object) -> None:
    """Install after deployment security and this exact app are attested.

    The Runtime composition root is trusted. A missing source capability leaves
    the normal HTTP route fail-closed; no caller-chosen validator is installed.
    """
    deployment = require_installed_deployment_security(app)
    if deployment is None or not deployment.config.registered_sql_sources:
        return
    verifier = RegisteredSQLLiveGrantVerifier(app)
    verifier._owner._install_registered_sql_issuer_verifier(verifier)
    verifier._require_pin()
