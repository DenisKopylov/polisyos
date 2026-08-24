"""Run-bound accountable human-decision routes."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Annotated, Any, NoReturn, cast

from anyio import to_thread
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.runtime.http.authorization import (
    ActionPermissionVerification,
    BoundActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    enforce_run_tenant_access,
    ensure_request_id,
    get_human_decision_service,
    get_optional_human_decision_service,
    get_runtime_api_context,
    record_data_access_audit,
    require_access_scope,
    set_authz_resource,
)
from polisyos.runtime.http.errors import conflict, forbidden, service_unavailable
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import (
    human_decision_create_from_bound_request,
)
from polisyos.runtime.http.services.human_decision_contracts import (
    HumanDecisionCreateCommand,
    HumanDecisionCreateResponse,
    HumanDecisionExposureSurface,
    HumanDecisionGateReason,
    HumanDecisionGateResponse,
    HumanDecisionMode,
    HumanDecisionPA2GateInput,
    HumanDecisionProductionGateInput,
    HumanDecisionSourceKind,
    HumanDecisionWriteContext,
)
from polisyos.runtime.http.services.human_decisions import (
    HumanDecisionExposureDelivery,
    HumanDecisionOperationalResolutionError,
    HumanDecisionPersistenceError,
    HumanDecisionService,
    HumanDecisionUnavailableError,
)
from polisyos.runtime.http.step_up import StepUpClass, require_step_up
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    DecisionAction,
    HumanDecisionRecord,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import APIRouter, Depends, Query, Request, Response
    from starlette.types import Message, Receive, Scope, Send

    from polisyos.runtime.http.services.run_index import IndexedRunRecord
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Query, Request, Response
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Query = cast("Any", None)
        Request = cast("Any", Any)
        Response = cast("Any", Any)


_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


class HumanDecisionMutationRequest(BaseModel):
    """Strict caller-authored fields; authority and custody fields are forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: HumanDecisionSourceKind
    source_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    production_packet_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    decision_request_ref: str | None = Field(default=None, min_length=1, max_length=300)
    decision_request_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    basis_ref: str | None = Field(default=None, min_length=1, max_length=300)
    basis_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    principal_binding_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    reviewer_separation_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    presentation_contract_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    action_kind: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_.:-]*$",
        max_length=120,
    )
    action: DecisionAction
    decision_mode: HumanDecisionMode
    accountability_statement: str = Field(min_length=1, max_length=500)
    dissent_statement: str = Field(min_length=1, max_length=1_000)
    override_reason: str | None = Field(default=None, min_length=1, max_length=1_000)
    blocking_reason: str | None = Field(default=None, min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def _source_arm(self) -> HumanDecisionMutationRequest:
        if self.source_kind == "agent_action_authority":
            if self.source_ref is None or self.action_kind is None:
                raise ValueError("PA2 decisions require source_ref and action_kind")
            if self.production_packet_ref is not None:
                raise ValueError("PA2 decisions cannot carry a production packet")
        elif self.action_kind is not None:
            raise ValueError("production decisions cannot carry PA2 action_kind")
        return self


_GATE_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.human_decision_gate",
        path_parameter="run_id",
        query_selector_parameters=("source_kind",),
        allow_empty_body=True,
    ),
)
_RECORD_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.human_decision_record",
        path_parameter="run_id",
        query_selector_parameters=("record_ref",),
        allow_empty_body=True,
    ),
)
_REVIEW_EFFECTIVENESS_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.human_decision_review_effectiveness",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)
_EVIDENCE_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_REVIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.human_decision_evidence",
        path_parameter="run_id",
        path_selector_parameters=("artifact_id",),
        allow_empty_body=True,
    ),
)
_CREATE_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.human_decision",
        path_parameter="run_id",
    ),
)
_CREATE_STEP_UP = require_step_up(StepUpClass.HUMAN_DECISION)
_RuntimeContextDependency = Annotated[
    RuntimeApiContext,
    Depends(get_runtime_api_context),
]
_HumanDecisionServiceDependency = Annotated[
    HumanDecisionService,
    Depends(get_human_decision_service),
]
_OptionalHumanDecisionServiceDependency = Annotated[
    HumanDecisionService | None,
    Depends(get_optional_human_decision_service),
]


class _ExactExposureResponse(Response):
    """Complete the audit receipt only after the exact final body was accepted."""

    def __init__(
        self,
        delivery: HumanDecisionExposureDelivery,
        *,
        service: HumanDecisionService,
    ) -> None:
        prepared = service.prepare_exposure_audit_event(delivery)
        super().__init__(
            content=delivery.content,
            status_code=200,
            media_type=delivery.media_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Encoding": "identity",
                "ETag": f'"{delivery.artifact_ref}"',
                "X-Content-Type-Options": "nosniff",
                "X-PolicyOS-Exposure-Session": delivery.session_ref,
            },
        )
        self._service = service
        self._reserved = prepared
        self._expected_content = delivery.content

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        completed = False
        body_frames = 0

        async def _send(message: Message) -> None:
            nonlocal body_frames, completed
            if message.get("type") == "http.response.body":
                body_frames += 1
                body = message.get("body", b"")
                if (
                    body_frames != 1
                    or bool(message.get("more_body", False))
                    or type(body) is not bytes
                    or body != self._expected_content
                ):
                    raise RuntimeError("exposure response must emit one exact terminal body frame")
            await send(message)
            if message.get("type") == "http.response.body" and not bool(
                message.get("more_body", False)
            ):
                if completed:
                    raise RuntimeError("exposure response completed more than once")
                completed = True
                await to_thread.run_sync(
                    partial(self._service.complete_exposure_audit_event, self._reserved)
                )

        await super().__call__(scope, receive, _send)


def _action_proof(
    request: Request,
    dependency: Callable[
        [Request],
        ActionPermissionVerification | BoundActionPermissionVerification,
    ],
) -> ActionPermissionVerification | BoundActionPermissionVerification:
    proof = dependency(request)
    if type(proof) not in {
        ActionPermissionVerification,
        BoundActionPermissionVerification,
    }:
        raise forbidden(
            "Human-decision route lacks a verified principal proof",
            code="human_decision_permission_unverified",
        )
    return proof


def _require_run(
    request: Request,
    *,
    ctx: RuntimeApiContext,
    run_id: str,
) -> IndexedRunRecord:
    run = ctx.run_index.get_run(run_id)
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    return run


def _run_tenant_id(run: IndexedRunRecord) -> str:
    """Return the tenant already admitted by `_require_run`, or fail closed."""
    tenant_id = run.details.tenant_id
    if not isinstance(tenant_id, str) or not tenant_id:
        raise service_unavailable(
            "The run lacks a tenant binding",
            code="human_decision_run_tenant_unbound",
        )
    return tenant_id


def _gate_input(
    *,
    source_kind: HumanDecisionSourceKind,
    tenant_id: str,
    run_id: str,
    source_ref: str | None,
    production_packet_ref: str | None,
    decision_request_ref: str | None,
    decision_request_digest: str | None,
    basis_ref: str | None,
    principal_binding_ref: str | None,
    reviewer_separation_ref: str | None,
    presentation_contract_ref: str | None,
    exposure_session_ref: str | None,
    basis_digest: str | None,
    action_kind: str | None,
) -> HumanDecisionPA2GateInput | HumanDecisionProductionGateInput:
    if source_kind == "agent_action_authority":
        if source_ref is None or action_kind is None:
            raise conflict(
                "PA2 gate requires exact source_ref and action_kind",
                code="DS9-DECISION-SOURCE-INVALID",
            )
        return HumanDecisionPA2GateInput(
            source_kind=source_kind,
            source_ref=source_ref,
            action_kind=action_kind,
            tenant_id=tenant_id,
            run_id=run_id,
            decision_request_ref=decision_request_ref,
            decision_request_digest=decision_request_digest,
            basis_ref=basis_ref,
            principal_binding_ref=principal_binding_ref,
            reviewer_separation_ref=reviewer_separation_ref,
            presentation_contract_ref=presentation_contract_ref,
            exposure_session_ref=exposure_session_ref,
            basis_digest=basis_digest,
        )
    return HumanDecisionProductionGateInput(
        source_kind=source_kind,
        source_ref=source_ref,
        production_packet_ref=production_packet_ref,
        tenant_id=tenant_id,
        run_id=run_id,
        decision_request_ref=decision_request_ref,
        decision_request_digest=decision_request_digest,
        basis_ref=basis_ref,
        principal_binding_ref=principal_binding_ref,
        reviewer_separation_ref=reviewer_separation_ref,
        presentation_contract_ref=presentation_contract_ref,
        exposure_session_ref=exposure_session_ref,
        basis_digest=basis_digest,
    )


def _raise_unavailable(exc: HumanDecisionUnavailableError) -> NoReturn:
    reason = exc.gate.reasons[0] if exc.gate.reasons else None
    raise conflict(
        reason.message if reason is not None else "Human-decision gate is unavailable",
        code=reason.code if reason is not None else f"human_decision_{exc.gate.status}",
    ) from exc


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/runs", tags=["human-decisions"])


router = _build_router()

if router is not None:

    @router.get(
        "/{run_id}/human-decision-gate",
        response_model=HumanDecisionGateResponse,
        operation_id="get_run_human_decision_gate",
        dependencies=[Depends(_GATE_AUTHZ)],
    )
    def get_run_human_decision_gate(
        run_id: str,
        request: Request,
        ctx: _RuntimeContextDependency,
        service: _OptionalHumanDecisionServiceDependency,
        source_kind: Annotated[HumanDecisionSourceKind, Query()],
        source_ref: Annotated[str | None, Query(pattern=_SHA256_PATTERN)] = None,
        production_packet_ref: Annotated[
            str | None,
            Query(pattern=_SHA256_PATTERN),
        ] = None,
        decision_request_ref: Annotated[str | None, Query()] = None,
        principal_binding_ref: Annotated[
            str | None,
            Query(pattern=_SHA256_PATTERN),
        ] = None,
        reviewer_separation_ref: Annotated[
            str | None,
            Query(pattern=_SHA256_PATTERN),
        ] = None,
        presentation_contract_ref: Annotated[
            str | None,
            Query(pattern=_SHA256_PATTERN),
        ] = None,
        exposure_session_ref: Annotated[
            str | None,
            Query(pattern=_SHA256_PATTERN),
        ] = None,
        basis_digest: Annotated[str | None, Query(pattern=_SHA256_PATTERN)] = None,
        action_kind: Annotated[
            str | None,
            Query(pattern=r"^[a-z][a-z0-9_.:-]*$"),
        ] = None,
    ) -> HumanDecisionGateResponse:
        run = _require_run(request, ctx=ctx, run_id=run_id)
        tenant_id = _run_tenant_id(run)
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="runtime.run.human_decision_gate",
            artifact_id=run_id,
        )
        proof = _action_proof(request, _GATE_AUTHZ)
        gate_input = _gate_input(
            source_kind=source_kind,
            tenant_id=tenant_id,
            run_id=run_id,
            source_ref=source_ref,
            production_packet_ref=production_packet_ref,
            decision_request_ref=decision_request_ref,
            decision_request_digest=None,
            basis_ref=None,
            principal_binding_ref=principal_binding_ref,
            reviewer_separation_ref=reviewer_separation_ref,
            presentation_contract_ref=presentation_contract_ref,
            exposure_session_ref=exposure_session_ref,
            basis_digest=basis_digest,
            action_kind=action_kind,
        )
        if service is None:
            reason = HumanDecisionGateReason(
                code="DS9-DECISION-PRODUCER-MISSING",
                message="The deployment human-decision producer is unavailable.",
                status="producer_missing",
            )
            record_data_access_audit(
                request,
                resource_id=run_id,
                resource_kind="runtime.run.human_decision_gate",
                tenant_id=tenant_id,
                outcome="human_decision_gate_producer_missing",
            )
            return HumanDecisionGateResponse(
                status="producer_missing",
                reasons=(reason,),
                reason_codes=(reason.code,),
                source_kind=source_kind,
                source_ref=source_ref,
                tenant_id=tenant_id,
                run_id=run_id,
                decision_request_ref=decision_request_ref,
                decision_request_digest=None,
                governed_action_key=None,
                decision_request=None,
                mandate=None,
                exposure=HumanDecisionExposureSurface(
                    exposure_session_ref=None,
                    required_artifact_digests=(),
                    completed_artifact_digests=(),
                ),
                contestability=None,
                resolved_at=datetime.now(UTC),
                verifier_epoch="producer-missing",
            )
        initial = service.resolve_gate(gate_input, bound_permission=proof)
        if isinstance(gate_input, HumanDecisionPA2GateInput) and {
            reason.code for reason in initial.reasons
        } == {"DS9-EXPOSURE-SESSION-PRODUCER-MISSING"}:
            try:
                issued = service.issue_exposure_session(
                    gate_input,
                    bound_permission=proof,
                )
            except HumanDecisionUnavailableError as exc:
                _raise_unavailable(exc)
            except HumanDecisionPersistenceError as exc:
                raise service_unavailable(
                    "Human-decision exposure session could not be custodied",
                    code="human_decision_exposure_session_nonreceipt",
                ) from exc
            gate_input = gate_input.model_copy(update={"exposure_session_ref": issued.session_ref})
        surface = service.resolve_gate_response(
            gate_input,
            bound_permission=proof,
        )
        record_data_access_audit(
            request,
            resource_id=run_id,
            resource_kind="runtime.run.human_decision_gate",
            tenant_id=tenant_id,
            outcome="human_decision_gate_resolved",
        )
        return surface

    @router.post(
        "/{run_id}/human-decisions",
        response_model=HumanDecisionCreateResponse,
        status_code=201,
        operation_id="create_run_human_decision",
        dependencies=[Depends(_CREATE_AUTHZ), Depends(_CREATE_STEP_UP)],
    )
    def create_run_human_decision(
        run_id: str,
        body: HumanDecisionMutationRequest,
        request: Request,
        ctx: _RuntimeContextDependency,
        service: _HumanDecisionServiceDependency,
    ) -> HumanDecisionCreateResponse:
        run = _require_run(request, ctx=ctx, run_id=run_id)
        tenant_id = _run_tenant_id(run)
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="runtime.run.human_decision",
            artifact_id=run_id,
        )
        proof = _action_proof(request, _CREATE_AUTHZ)
        if type(proof) is not BoundActionPermissionVerification:
            raise forbidden(
                "Human-decision mutation lacks its frozen pre-OPA resource",
                code="authorization_binding_context_missing",
            )
        bound_context = human_decision_create_from_bound_request(request)
        bound_body = bound_context.get("body")
        exposure_session_ref = bound_context.get("exposure_session_ref")
        if (
            not isinstance(bound_body, dict)
            or HumanDecisionMutationRequest.model_validate(bound_body) != body
            or not isinstance(exposure_session_ref, str)
        ):
            raise forbidden(
                "Human-decision body changed after authorization",
                code="authorization_binding_context_mismatch",
            )
        gate_input = _gate_input(
            source_kind=body.source_kind,
            tenant_id=tenant_id,
            run_id=run_id,
            source_ref=body.source_ref,
            production_packet_ref=body.production_packet_ref,
            decision_request_ref=body.decision_request_ref,
            decision_request_digest=body.decision_request_digest,
            basis_ref=body.basis_ref,
            principal_binding_ref=body.principal_binding_ref,
            reviewer_separation_ref=body.reviewer_separation_ref,
            presentation_contract_ref=body.presentation_contract_ref,
            exposure_session_ref=exposure_session_ref,
            basis_digest=body.basis_digest,
            action_kind=body.action_kind,
        )
        command = HumanDecisionCreateCommand(
            gate_input=gate_input,
            decision_action=body.action,
            decision_mode=body.decision_mode,
            accountability_statement=body.accountability_statement,
            dissent_statement=body.dissent_statement,
            override_reason=body.override_reason,
            blocking_reason=body.blocking_reason,
        )
        scope = require_access_scope(request)
        request_id = ensure_request_id(request)
        owner = scope.user_sub or scope.spiffe_id
        try:
            receipt = service.create_record(
                command,
                bound_permission=proof,
                write_context=HumanDecisionWriteContext(
                    tenant_id=tenant_id,
                    cell_id=run.details.cell_id,
                    run_id=run_id,
                    job_id=f"human-decision-http-{request_id}",
                    trace_id=str(getattr(request.state, "trace_id", None) or f"trace-{request_id}"),
                    span_id=str(getattr(request.state, "span_id", None) or f"span-{request_id}"),
                    parent_span_id=None,
                    owner=owner,
                    requested_execution_profile="governed",
                    effective_execution_profile="governed",
                    effective_mode_ref="runtime://human-decision/http",
                ),
            )
        except HumanDecisionUnavailableError as exc:
            _raise_unavailable(exc)
        except HumanDecisionOperationalResolutionError as exc:
            raise conflict(
                "Human-decision operational authority is not current",
                code=exc.code,
            ) from exc
        except HumanDecisionPersistenceError as exc:
            raise service_unavailable(
                "Human-decision custody did not complete",
                code="human_decision_custody_nonreceipt",
            ) from exc
        record_data_access_audit(
            request,
            resource_id=receipt.record_ref,
            tenant_id=tenant_id,
            outcome="human_decision_record_created",
        )
        return HumanDecisionCreateResponse(
            run_id=run_id,
            record_ref=receipt.record_ref,
            record_digest=receipt.record_digest,
            record=receipt.record,
            durable_event_id=receipt.durable_event_id,
            reservation_id=receipt.reservation_id,
            reservation_version=receipt.reservation_version,
        )

    @router.get(
        "/{run_id}/human-decisions",
        response_model=HumanDecisionRecord,
        operation_id="get_run_human_decision_record",
        dependencies=[Depends(_RECORD_AUTHZ)],
    )
    def get_run_human_decision_record(
        run_id: str,
        request: Request,
        record_ref: Annotated[str, Query(pattern=_SHA256_PATTERN)],
        ctx: _RuntimeContextDependency,
        service: _HumanDecisionServiceDependency,
    ) -> HumanDecisionRecord:
        run = _require_run(request, ctx=ctx, run_id=run_id)
        tenant_id = _run_tenant_id(run)
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="runtime.run.human_decision_record",
            artifact_id=record_ref,
        )
        _ = _action_proof(request, _RECORD_AUTHZ)
        try:
            record = service.read_record(
                record_ref,
                tenant_id=tenant_id,
                run_id=run_id,
            )
        except HumanDecisionOperationalResolutionError as exc:
            raise conflict(
                "Human-decision record is not a current custodied v2 record",
                code=exc.code,
            ) from exc
        record_data_access_audit(
            request,
            resource_id=record_ref,
            tenant_id=tenant_id,
            outcome="human_decision_record_read",
        )
        return record

    @router.get(
        "/{run_id}/human-decisions/review-effectiveness",
        operation_id="get_run_human_decision_review_effectiveness",
        dependencies=[Depends(_REVIEW_EFFECTIVENESS_AUTHZ)],
    )
    def get_run_human_decision_review_effectiveness(
        run_id: str,
        request: Request,
        ctx: _RuntimeContextDependency,
    ) -> None:
        run = _require_run(request, ctx=ctx, run_id=run_id)
        tenant_id = _run_tenant_id(run)
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="runtime.run.human_decision_review_effectiveness",
            artifact_id=run_id,
        )
        _ = _action_proof(request, _REVIEW_EFFECTIVENESS_AUTHZ)
        raise service_unavailable(
            "Review-effectiveness projection is not installed",
            code="review_effectiveness_producer_missing",
        )

    @router.get(
        "/{run_id}/human-decision-evidence/{artifact_id}/content",
        response_class=Response,
        operation_id="get_run_human_decision_evidence_content",
        dependencies=[Depends(_EVIDENCE_AUTHZ)],
    )
    def get_run_human_decision_evidence_content(
        run_id: str,
        artifact_id: str,
        request: Request,
        ctx: _RuntimeContextDependency,
        service: _HumanDecisionServiceDependency,
    ) -> Response:
        run = _require_run(request, ctx=ctx, run_id=run_id)
        tenant_id = _run_tenant_id(run)
        set_authz_resource(
            request,
            tenant_id=tenant_id,
            kind="runtime.run.human_decision_evidence",
            artifact_id=artifact_id,
        )
        proof = _action_proof(request, _EVIDENCE_AUTHZ)
        session_ref = request.headers.get(
            "X-PolicyOS-Human-Decision-Exposure",
            "",
        ).strip()
        if not session_ref:
            raise conflict(
                "Human-decision evidence requires an exact exposure session",
                code="DS9-EXPOSURE-SESSION-PRODUCER-MISSING",
            )
        try:
            delivery = service.resolve_exposure_delivery(
                tenant_id=tenant_id,
                run_id=run_id,
                session_ref=session_ref,
                artifact_ref=artifact_id,
                bound_permission=proof,
            )
            response = _ExactExposureResponse(delivery, service=service)
        except HumanDecisionOperationalResolutionError as exc:
            raise conflict(
                "Human-decision evidence delivery is not admitted",
                code=exc.code,
            ) from exc
        except HumanDecisionPersistenceError as exc:
            raise service_unavailable(
                "Human-decision exposure receipt could not be prepared",
                code="human_decision_exposure_nonreceipt",
            ) from exc
        record_data_access_audit(
            request,
            resource_id=artifact_id,
            tenant_id=tenant_id,
            outcome="human_decision_evidence_delivery_prepared",
        )
        return cast("Response", response)


__all__ = ["router"]
