"""Protected source registration, materialization and withdrawal routes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.security import tenant_scope
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.runtime.http.errors import service_unavailable, unprocessable_entity
from polisyos.runtime.http.services.registered_sql_live_grant import RegisteredSQLLiveGrantVerifier
from polisyos.runtime.http.services.registered_sql_service import (
    REGISTERED_SQL_ADMIT_AUTHZ,
    REGISTERED_SQL_REGISTER_AUTHZ,
    REGISTERED_SQL_WITHDRAW_AUTHZ,
    RegisteredSQLCommand,
    _installed_owner,
)
from polisyos.runtime.http.services.registered_sql_service_contracts import (
    RegisteredSQLMaterializationRequest,
    RegisteredSQLMaterializationResponse,
    RegisteredSQLRegistrationRequest,
    RegisteredSQLRegistrationResponse,
    RegisteredSQLWithdrawalRequest,
    RegisteredSQLWithdrawalResponse,
)
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort
from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer
from polisyos.scientist.validation.source_admission_port import (
    SourceIssuerCall,
    _bind_runtime_source_admission_authority,
)

if TYPE_CHECKING:
    from polisyos.runtime.http.services.registered_sql_live_grant import (
        RegisteredSQLLiveGrantWitness,
    )
    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from polisyos.scientist.validation.source_admission_port import SourceAdmissionAuthority

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Depends, Request
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = cast("Any", None)
    Depends = cast("Any", None)
    Request = cast("Any", Any)

router = (
    APIRouter(prefix="/api/v1/control/registered-sql", tags=["runtime-registered-sql"])
    if APIRouter is not None
    else None
)


async def _authority_for_request(
    request: Request, body: RegisteredSQLCommand
) -> tuple[DecisionValidityService, SourceAdmissionAuthority, RegisteredSQLLiveGrantWitness]:
    owner, _store = _installed_owner(request)
    verifier = getattr(owner, "_registered_sql_issuer_verifier", None)
    if type(verifier) is not RegisteredSQLLiveGrantVerifier:
        raise service_unavailable(
            "The SQL source issuer is not installed",
            code="registered_sql_source_owner_verification_missing",
        )
    body_bytes = await request.body()
    witness = await asyncio.to_thread(
        verifier.witness, request, command=body, body_bytes=body_bytes
    )
    if type(body) is RegisteredSQLRegistrationRequest:
        call = SourceIssuerCall(operation="genesis", event_id=body.event_id)
    elif type(body) is RegisteredSQLWithdrawalRequest:
        call = SourceIssuerCall(
            operation="withdraw",
            event_id=body.event_id,
            expected_predecessor=body.expected_predecessor,
            target=body.target,
        )
    else:
        call = SourceIssuerCall(
            operation="acquire",
            event_id=body.event_id,
            expected_predecessor=body.expected_predecessor,
        )
    authority = _bind_runtime_source_admission_authority(
        owner=owner, verifier=verifier, witness=witness, initial_call=call
    )
    return owner, authority, witness


if router is not None:

    @router.post(
        "/registrations",
        response_model=RegisteredSQLRegistrationResponse,
        operation_id="register_sql_source",
        dependencies=[Depends(REGISTERED_SQL_REGISTER_AUTHZ)],
    )
    async def register_sql_source(
        body: RegisteredSQLRegistrationRequest, request: Request
    ) -> RegisteredSQLRegistrationResponse:
        """Commit or recover the configured genuine source genesis."""
        owner, authority, witness = await _authority_for_request(request, body)
        slot = witness.initial.slot
        registration = owner.register_materialization_source(
            authority,
            event_id=body.event_id,
            registration_key=slot.registration_key,
            effective_view_contract_ref=slot.effective_view_contract_ref,
            use_contract_ref=slot.use_contract_ref,
        )
        return RegisteredSQLRegistrationResponse(registration=registration)

    @router.post(
        "/materializations",
        response_model=RegisteredSQLMaterializationResponse,
        operation_id="admit_registered_sql_materialization",
        dependencies=[Depends(REGISTERED_SQL_ADMIT_AUTHZ)],
    )
    async def admit_registered_sql_materialization(
        body: RegisteredSQLMaterializationRequest, request: Request
    ) -> RegisteredSQLMaterializationResponse:
        """Resolve a genuine genesis before the installed SQL producer runs."""
        owner, authority, witness = await _authority_for_request(request, body)
        registration_event = owner.resolve_source_admission_event(
            authority, event_id=witness.initial.slot.registration_event_id
        )
        if registration_event is None or registration_event.source_registration is None:
            raise service_unavailable(
                "The registered SQL source genesis is unavailable",
                code="registered_sql_registration_missing",
            )
        container = request.app.state.runtime_container
        providers = getattr(container, "control_registry_providers", None)
        registry = getattr(providers, "connectors", None)
        if type(registry) is not ConnectorRegistry:
            raise service_unavailable(
                "The registered SQL source producer is unavailable",
                code="registered_sql_source_producer_unavailable",
            )
        _installed, store = _installed_owner(request)
        if _installed is not owner:
            raise service_unavailable(
                "The registered SQL source owner changed",
                code="registered_sql_source_owner_unavailable",
            )
        port = DefaultFabricPort(
            connector_registry=registry,
            connector_id=witness.initial.slot.connector_id,
            require_fresh_registered_sql=True,
        )
        producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
        slot = witness.initial.slot

        def acquire() -> RegisteredSQLMaterializationResponse:
            # A source act is independently authorized. It may commit even if a
            # later job is cancelled; job publication uses its own lease fence.
            with tenant_scope(None, tenant_id=slot.tenant_id, cell_id=slot.cell_id):
                receipt, _materialization, binding_ref = producer.acquire_and_admit(
                    store=store,
                    request_ref=body.request_ref,
                    registration=registration_event.source_registration,
                    event_id=body.event_id,
                    occurrence_id=body.occurrence_id,
                    expected_predecessor=body.expected_predecessor,
                )
            return RegisteredSQLMaterializationResponse(receipt=receipt, binding_ref=binding_ref)

        try:
            # The selected connector requires a real synchronous driver boundary;
            # do not detach a coroutine from the active HTTP event loop.
            return await asyncio.to_thread(acquire)
        except (FileNotFoundError, OSError) as exc:
            raise service_unavailable(
                "The registered SQL source is unavailable",
                code="registered_sql_source_unavailable",
            ) from exc
        except ValueError as exc:
            raise unprocessable_entity(
                "The registered SQL occurrence could not be admitted",
                code="registered_sql_occurrence_not_admitted",
            ) from exc

    @router.post(
        "/withdrawals",
        response_model=RegisteredSQLWithdrawalResponse,
        operation_id="withdraw_registered_sql_materialization",
        dependencies=[Depends(REGISTERED_SQL_WITHDRAW_AUTHZ)],
    )
    async def withdraw_registered_sql_materialization(
        body: RegisteredSQLWithdrawalRequest, request: Request
    ) -> RegisteredSQLWithdrawalResponse:
        """Withdraw one carrier verified against committed source history."""
        owner, authority, _witness = await _authority_for_request(request, body)
        receipt = owner.transition_materialization(
            authority,
            event_id=body.event_id,
            expected_predecessor=body.expected_predecessor,
            operation="withdraw",
            target=body.target,
        )
        return RegisteredSQLWithdrawalResponse(receipt=receipt)
