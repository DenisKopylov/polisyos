"""Run-bound acquisition route projection and deferred action composition."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import OperationClass, OperationContract, OperationInvocationRecord
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteClosureError,
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
    VerifiedAcquisitionRouteClosure,
    persist_world_commit_and_reenter,
    resume_world_committed_reentry,
)
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AgentActionAuthorityGateway,
    AgentActionAuthorityRefused,
    AgentActionIntent,
    agent_action_authority_scope,
    agent_action_content_hash,
    produce_agent_action_authority_decision,
    reserve_agent_external_action,
)

from .control import ControlPlaneService
from .human_decisions import HumanDecisionService

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.http.execution_policy import RuntimePrincipal

    from .control_plane_store import AcquisitionActionHeadRecord, ControlJobRecord

_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_IMPLEMENTATION_REF = "polisyos.runtime.acquisition_route_loop.owner_port.v1"


class AcquisitionActionServiceError(ValueError):
    """Typed fail-closed error from the acquisition service boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AcquisitionRouteReplayPins(BaseModel):
    """Server-projected pins callers may only echo for optimistic concurrency."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_job_id: str = Field(min_length=1)
    compiled_ref: str = Field(pattern=_SHA256_PATTERN)
    compiled_content_hash: str = Field(pattern=_SHA256_PATTERN)
    terminal_event_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=_SHA256_PATTERN)
    cost_basis_hash: str = Field(pattern=_SHA256_PATTERN)


class AcquisitionRouteMutationRequest(BaseModel):
    """Strict caller fields; route facts, status, authority, and epochs are forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    route_projection_hash: str = Field(pattern=_SHA256_PATTERN)
    planner_report_hash: str = Field(pattern=_SHA256_PATTERN)
    replay_pins: AcquisitionRouteReplayPins
    idempotency_key: str = Field(min_length=1, max_length=200)
    human_decision_record_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)


class AcquisitionRouteProjection(BaseModel):
    """Read-only current route with independent execution and authority postures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionRouteProjection@1.0"] = "AcquisitionRouteProjection@1.0"
    tenant_id: str
    cell_id: str
    run_id: str
    route_id: str = Field(pattern=_SHA256_PATTERN)
    route_projection_hash: str = Field(pattern=_SHA256_PATTERN)
    planner_report_hash: str = Field(pattern=_SHA256_PATTERN)
    planner_record_id: str
    recommended_strategy: str
    cost_basis: dict[str, object]
    replay_pins: AcquisitionRouteReplayPins
    route_status: Literal["costed_actionable"] = "costed_actionable"
    authority_capability: Literal["ready", "producer_missing"]
    execution_capability: Literal["ready", "producer_missing"]
    qualification_status: Literal["pending_epoch_activation"] = "pending_epoch_activation"
    qualification_predicate: Literal["not_established"] = "not_established"
    qualification_reason: Literal["policy_admission_missing"] = "policy_admission_missing"
    world_growth: Literal["no_growth"] = "no_growth"
    authority_badge: Literal["behavioral_fixture_not_production"] = (
        "behavioral_fixture_not_production"
    )
    external_nonclosures: tuple[str, ...] = (
        "fresh_positive_production_route:absent/unallocated",
        "current_mandate_owner:producer_missing",
        "deterministic_admission_bundle:producer_missing",
        "non_fixture_n13b_owner_port:bridge_missing",
    )


class AcquisitionRouteListResponse(BaseModel):
    """Run-bound list response; the current closure admits at most one route."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    routes: tuple[AcquisitionRouteProjection, ...]


class AcquisitionDecisionRequestResponse(BaseModel):
    """Persisted authority result without an external effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    route_id: str = Field(pattern=_SHA256_PATTERN)
    authority_decision_ref: str = Field(pattern=_SHA256_PATTERN)
    outcome: Literal["decision_required", "decision_available"]
    human_decision_request: dict[str, object] | None = None
    world_growth: Literal["no_growth"] = "no_growth"


class AcquisitionExecutionResponse(BaseModel):
    """Durable deferred-job acceptance response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    route_id: str = Field(pattern=_SHA256_PATTERN)
    job_id: str
    authority_decision_ref: str = Field(pattern=_SHA256_PATTERN)
    status: Literal["accepted"] = "accepted"
    receipt_phase: Literal["requested"] = "requested"
    world_growth: Literal["no_growth"] = "no_growth"


class AcquisitionOwnerExecutionResult(BaseModel):
    """Strict owner-port result; refs denote artifacts the external owner already persisted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionOwnerExecutionResult@1.0"] = (
        "AcquisitionOwnerExecutionResult@1.0"
    )
    disposition: Literal["quarantined_no_growth", "world_committed"]
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)
    admitted_observation_delta: int = Field(ge=0)
    overlay_admission_receipt_ref: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    post_epoch_event_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    authority_badge: Literal["behavioral_fixture_not_production"] = (
        "behavioral_fixture_not_production"
    )

    @model_validator(mode="after")
    def _world_commit_requires_active_owner_evidence(self) -> AcquisitionOwnerExecutionResult:
        if self.disposition == "world_committed":
            if (
                self.admitted_observation_delta <= 0
                or self.overlay_admission_receipt_ref is None
                or self.post_epoch_event_ref is None
            ):
                raise ValueError("world_commit_owner_evidence_incomplete")
        elif (
            self.admitted_observation_delta != 0
            or self.overlay_admission_receipt_ref is not None
            or self.post_epoch_event_ref is not None
        ):
            raise ValueError("quarantine_cannot_claim_world_growth")
        if any(not ref.startswith("sha256:") for ref in self.owner_receipt_refs):
            raise ValueError("owner_receipt_ref_invalid")
        return self


class AcquisitionExecutionPort(Protocol):
    """External owner port; no raw path, CAS, journal, passport, or epoch inputs."""

    def execute(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> AcquisitionOwnerExecutionResult: ...

    def reenter(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        result: AcquisitionOwnerExecutionResult,
    ) -> str: ...

    def resume_reentry(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        owner_receipt_refs: tuple[str, ...],
    ) -> str: ...


class AcquisitionAuthorityGatewayProvider(Protocol):
    """External signed authority inputs resolved by the deployment composition root."""

    def for_request(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
        job_id: str,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway: ...

    def for_job(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
        job_id: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway: ...


class AcquisitionActionService:
    """Compose current route, PA2/DS9 authority, worker, owner port, and recovery."""

    def __init__(
        self,
        *,
        control_service: ControlPlaneService,
        human_decision_service: HumanDecisionService,
        authority_provider: AcquisitionAuthorityGatewayProvider | None = None,
        execution_port: AcquisitionExecutionPort | None = None,
    ) -> None:
        if type(control_service) is not ControlPlaneService:
            raise TypeError("acquisition service requires the exact control service")
        if type(human_decision_service) is not HumanDecisionService:
            raise TypeError("acquisition service requires the exact DS9 service")
        production_execution_port: AcquisitionExecutionPort | None = None
        if execution_port is None:
            from .acquisition_surface_execution import (
                build_production_world_bank_wdi_execution_port,
            )

            execution_port = build_production_world_bank_wdi_execution_port(
                control_service=control_service
            )
            production_execution_port = execution_port
        if authority_provider is not None and any(
            not callable(getattr(authority_provider, name, None))
            for name in ("for_request", "for_job")
        ):
            raise TypeError("acquisition authority provider contract invalid")
        if execution_port is not None and any(
            not callable(getattr(execution_port, name, None))
            for name in ("execute", "reenter", "resume_reentry")
        ):
            raise TypeError("acquisition execution port contract invalid")
        self.control_service = control_service
        self.human_decision_service = human_decision_service
        self._authority_provider = authority_provider
        self._execution_port = execution_port
        self._production_execution_port = production_execution_port
        control_service.bind_acquisition_job_handler(self.handle_job)

    def list_routes(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
    ) -> AcquisitionRouteListResponse:
        """Return the exact current costed route or a typed closure error."""

        closure = self._resolve(tenant_id=tenant_id, cell_id=cell_id, run_id=run_id)
        return AcquisitionRouteListResponse(
            run_id=run_id,
            routes=(self._projection(closure),),
        )

    def get_route(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
    ) -> AcquisitionRouteProjection:
        """Return one exact current route; stale route ids never revive."""

        closure = self._resolve(tenant_id=tenant_id, cell_id=cell_id, run_id=run_id)
        if closure.route_id != route_id:
            raise AcquisitionActionServiceError("acquisition_route_not_current")
        return self._projection(closure)

    def request_decision(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: AcquisitionRouteMutationRequest,
        bound_permission: BoundActionPermissionVerification,
    ) -> AcquisitionDecisionRequestResponse:
        """Persist the PA2 decision/request without consuming or invoking the effect."""

        closure = self._validated_mutation(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=request,
        )
        provider = self._require_authority_provider()
        operation, invocation, intent = self._action_tuple(closure, request)
        job_id = self._job_id(closure, request)

        def _no_effect(_invocation: OperationInvocationRecord) -> object:
            raise RuntimeError("decision request cannot invoke an acquisition effect")

        gateway = provider.for_request(
            closure=closure,
            request=request,
            job_id=job_id,
            bound_permission=bound_permission,
            effect_handler=_no_effect,
        )
        with agent_action_authority_scope(gateway):
            decision = produce_agent_action_authority_decision(
                bound_permission=bound_permission,
                operation=operation,
                invocation=invocation,
                intent=intent,
            )
            persisted = gateway.persist_decision(decision)
        return AcquisitionDecisionRequestResponse(
            run_id=run_id,
            route_id=route_id,
            authority_decision_ref=str(persisted.write_result.cas_ref.artifact_id),
            outcome=(
                "decision_required" if decision.outcome == "refused" else "decision_available"
            ),
            human_decision_request=(
                decision.human_decision_request.model_dump(mode="json")
                if decision.human_decision_request is not None
                else None
            ),
        )

    def execute(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: AcquisitionRouteMutationRequest,
        bound_permission: BoundActionPermissionVerification,
        request_id: str | None,
        principal: RuntimePrincipal | None,
    ) -> AcquisitionExecutionResponse:
        """Reserve a durable allow, persist requested phase, and enqueue without effect."""

        closure = self._validated_mutation(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=request,
        )
        provider = self._require_authority_provider()
        self._require_production_execution_bridge(closure)
        self._require_execution_port()
        operation, invocation, intent = self._action_tuple(closure, request)
        job_id = self._job_id(closure, request)

        def _no_http_effect(_invocation: OperationInvocationRecord) -> object:
            raise RuntimeError("HTTP acquisition reservation cannot invoke an effect")

        gateway = provider.for_request(
            closure=closure,
            request=request,
            job_id=job_id,
            bound_permission=bound_permission,
            effect_handler=_no_http_effect,
        )
        try:
            with agent_action_authority_scope(gateway):
                persisted = reserve_agent_external_action(
                    bound_permission=bound_permission,
                    operation=operation,
                    invocation=invocation,
                    intent=intent,
                )
        except AgentActionAuthorityRefused as exc:
            raise AcquisitionActionServiceError("human_decision_required") from exc
        decision_ref = str(persisted.write_result.cas_ref.artifact_id)
        requested = self._phase_receipt(
            closure=closure,
            job_id=job_id,
            decision_ref=decision_ref,
            receipt_phase="requested",
            predecessor_receipt_ref=None,
            owner_receipt_refs=(),
        )
        head = self.control_service.acquisition_route_sink.get_head(requested)
        if head is None:
            self.control_service.acquisition_route_sink.persist_phase(requested)
        elif head.job_id != job_id or head.receipt_phase not in {
            "requested",
            "executing",
            "world_committed_reentry_pending",
            "terminal",
        }:
            raise AcquisitionActionServiceError("acquisition_action_head_conflict")
        self.control_service.enqueue_acquisition_job(
            job_id=job_id,
            run_id=run_id,
            payload={
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": route_id,
                "decision_ref": decision_ref,
                "request": request.model_dump(mode="json"),
                "operation": operation.model_dump(mode="json"),
                "invocation": invocation.model_dump(mode="json"),
                "intent": intent.model_dump(mode="json"),
            },
            request_id=request_id,
            principal=principal,
        )
        return AcquisitionExecutionResponse(
            run_id=run_id,
            route_id=route_id,
            job_id=job_id,
            authority_decision_ref=decision_ref,
        )

    def handle_job(self, job: ControlJobRecord, payload: dict[str, Any]) -> dict[str, Any]:
        """Load the durable decision, invoke only the sealed port, and recover re-entry only."""

        if job.kind != "acquisition" or job.run_id is None:
            raise AcquisitionActionServiceError("acquisition_job_kind_mismatch")
        request = AcquisitionRouteMutationRequest.model_validate(payload.get("request"))
        closure = self._validated_mutation(
            tenant_id=str(payload.get("tenant_id") or ""),
            cell_id=str(payload.get("cell_id") or ""),
            run_id=job.run_id,
            route_id=str(payload.get("route_id") or ""),
            request=request,
        )
        operation = OperationContract.model_validate(payload.get("operation"))
        invocation = OperationInvocationRecord.model_validate(payload.get("invocation"))
        intent = AgentActionIntent.model_validate(payload.get("intent"))
        expected_tuple = self._action_tuple(closure, request)
        if (operation, invocation, intent) != expected_tuple:
            raise AcquisitionActionServiceError("acquisition_job_action_binding_mismatch")
        decision_ref = str(payload.get("decision_ref") or "")
        seed = self._phase_receipt(
            closure=closure,
            job_id=job.job_id,
            decision_ref=decision_ref,
            receipt_phase="requested",
            predecessor_receipt_ref=None,
            owner_receipt_refs=(),
        )
        sink = self.control_service.acquisition_route_sink
        head = sink.get_head(seed)
        if head is None:
            raise AcquisitionActionServiceError("acquisition_requested_head_missing")
        port = self._require_execution_port()
        if head.receipt_phase == "terminal":
            return {
                "state": "completed",
                "phase": "acquisition",
                "receipt_phase": "terminal",
                "terminal_receipt_ref": head.receipt_ref,
            }
        if head.receipt_phase == "world_committed_reentry_pending":
            pending = self._read_phase_receipt(head.receipt_ref)
            terminal = resume_world_committed_reentry(
                sink=sink,
                pending_receipt=pending,
                reentry=lambda: port.resume_reentry(closure, pending.owner_receipt_refs),
            )
            return self._terminal_progress(terminal)
        if head.receipt_phase != "requested":
            raise AcquisitionActionServiceError("acquisition_action_head_not_recoverable")
        executing = self._phase_receipt(
            closure=closure,
            job_id=job.job_id,
            decision_ref=decision_ref,
            receipt_phase="executing",
            predecessor_receipt_ref=head.receipt_ref,
            owner_receipt_refs=(),
        )
        executing_head = sink.persist_phase(executing)
        result_holder: list[AcquisitionOwnerExecutionResult] = []

        def _effect(_invocation: OperationInvocationRecord) -> object:
            result = AcquisitionOwnerExecutionResult.model_validate(port.execute(closure))
            result_holder.append(result)
            return result

        gateway = self._require_authority_provider().for_job(
            closure=closure,
            request=request,
            job_id=job.job_id,
            effect_handler=_effect,
        )
        persisted = gateway.load_persisted_decision(decision_ref)
        gateway.execute_bound_effect(
            operation=operation,
            invocation=invocation,
            intent=intent,
            persisted=persisted,
        )
        if len(result_holder) != 1:
            raise AcquisitionActionServiceError("acquisition_owner_result_missing")
        result = result_holder[0]
        if result.disposition == "quarantined_no_growth":
            terminal = self._terminal_receipt(
                closure=closure,
                job_id=job.job_id,
                decision_ref=decision_ref,
                predecessor_receipt_ref=executing_head.receipt_ref,
                owner_receipt_refs=result.owner_receipt_refs,
            )
            return self._terminal_progress(sink.persist_terminal(terminal))
        pending = self._phase_receipt(
            closure=closure,
            job_id=job.job_id,
            decision_ref=decision_ref,
            receipt_phase="world_committed_reentry_pending",
            predecessor_receipt_ref=executing_head.receipt_ref,
            owner_receipt_refs=result.owner_receipt_refs,
        )
        terminal = persist_world_commit_and_reenter(
            sink=sink,
            pending_receipt=pending,
            reentry=lambda: port.reenter(closure, result),
        )
        return self._terminal_progress(terminal)

    def _resolve(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
    ) -> VerifiedAcquisitionRouteClosure:
        if not tenant_id or not cell_id or not run_id:
            raise AcquisitionActionServiceError("acquisition_actor_scope_missing")
        loop = AcquisitionRouteLoop(
            control_store=self.control_service._control_store,
            artifact_store=self.control_service._artifact_store,
            event_log=self.control_service._diagnostic_event_log,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        try:
            return loop.resolve_current_route(run_id=run_id)
        except AcquisitionRouteClosureError as exc:
            raise AcquisitionActionServiceError(exc.code) from exc

    def _projection(self, closure: VerifiedAcquisitionRouteClosure) -> AcquisitionRouteProjection:
        execution_bridge_installed = self._production_execution_bridge_installed()
        execution_ready = self._production_execution_bridge_ready(closure)
        return AcquisitionRouteProjection(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            route_id=closure.route_id,
            route_projection_hash=closure.route_id,
            planner_report_hash=agent_action_content_hash(closure.planner_report),
            planner_record_id=closure.planner_record.acquisition_id,
            recommended_strategy=closure.planner_record.recommended_strategy.value,
            cost_basis=closure.cost_basis_record.model_dump(mode="json"),
            replay_pins=self._pins(closure),
            authority_capability=(
                "ready"
                if execution_ready and self._authority_provider is not None
                else "producer_missing"
            ),
            execution_capability=("ready" if execution_ready else "producer_missing"),
            external_nonclosures=(
                "fresh_positive_production_route:absent/unallocated",
                "current_mandate_owner:producer_missing",
                "deterministic_admission_bundle:producer_missing",
                "connector_families_except_worldbank.wdi:surface_out_of_scope",
                *(
                    ("non_fixture_n13b_owner_port:bridge_missing",)
                    if not execution_bridge_installed
                    else (
                        ("worldbank.wdi_route_binding:producer_missing",)
                        if not execution_ready
                        else ()
                    )
                ),
            ),
        )

    def _validated_mutation(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: AcquisitionRouteMutationRequest,
    ) -> VerifiedAcquisitionRouteClosure:
        closure = self._resolve(tenant_id=tenant_id, cell_id=cell_id, run_id=run_id)
        if (
            closure.route_id != route_id
            or request.route_projection_hash != closure.route_id
            or request.planner_report_hash != agent_action_content_hash(closure.planner_report)
            or request.replay_pins != self._pins(closure)
        ):
            raise AcquisitionActionServiceError("acquisition_route_revalidation_required")
        return closure

    @staticmethod
    def _pins(closure: VerifiedAcquisitionRouteClosure) -> AcquisitionRouteReplayPins:
        return AcquisitionRouteReplayPins(
            source_job_id=closure.source_job_id,
            compiled_ref=closure.compiled_ref,
            compiled_content_hash=closure.compiled_content_hash,
            terminal_event_id=closure.terminal_event_id,
            design_problem_ref=closure.design_problem_ref,
            cost_basis_hash=closure.cost_basis_hash,
        )

    @staticmethod
    def _action_tuple(
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
    ) -> tuple[OperationContract, OperationInvocationRecord, AgentActionIntent]:
        operation = OperationContract(
            operation_id=ACQUISITION_ACTION_KIND,
            operation_version="v1",
            operation_class=OperationClass.ACQUIRE,
            consumes=[],
            produces=[],
            formal_preconditions=[],
            allowed_internal_execution=["tool_call"],
            implementation_refs=[
                {
                    "module": "polisyos.runtime.http.services.acquisition_action_service",
                    "symbol": "AcquisitionExecutionPort.execute",
                }
            ],
            cost_model={"cost_basis_hash": closure.cost_basis_hash},
            authority_transform={"kind": "preserves"},
            failure_modes=["authority_refused", "owner_port_failed", "reentry_recovery_required"],
            repair_options=[OperationClass.ESCALATE],
        )
        binding = agent_action_content_hash(
            {
                "tenant_id": closure.tenant_id,
                "cell_id": closure.cell_id,
                "run_id": closure.run_id,
                "route_id": closure.route_id,
                "planner_report_hash": request.planner_report_hash,
                "replay_pins": request.replay_pins.model_dump(mode="json"),
                "idempotency_key": request.idempotency_key,
            }
        )
        invocation = OperationInvocationRecord(
            invocation_id=f"acquisition.execute.{binding.removeprefix('sha256:')}",
            operation_id=operation.operation_id,
            operation_version=operation.operation_version,
            workspace_id=closure.run_id,
            cycle_index=closure.source_cycle.cycle_index,
            selected_by={"producer": "runtime.acquisition_route_loop"},
            selection_rationale_ref=closure.route_id,
            input_artifacts=[],
            parameters={
                "route_id": closure.route_id,
                "planner_report_hash": request.planner_report_hash,
                "cost_basis_hash": closure.cost_basis_hash,
                "compiled_ref": closure.compiled_ref,
            },
            internal_trace={"phase": "deferred_acquisition_reservation"},
            tool_calls=[],
            human_requests=[],
            output_artifacts=[],
            applicability_result="applicable",
            budget_delta={"acquisition_actions": 1},
            status="started",
        )
        return operation, invocation, AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND)

    @staticmethod
    def _job_id(
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
    ) -> str:
        payload = (
            f"{closure.tenant_id}\0{closure.cell_id}\0{closure.run_id}\0{closure.route_id}\0"
            f"{request.planner_report_hash}\0{request.idempotency_key}\0"
            f"{request.human_decision_record_ref or ''}"
        ).encode()
        return f"acquisition-{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def _phase_receipt(
        *,
        closure: VerifiedAcquisitionRouteClosure,
        job_id: str,
        decision_ref: str,
        receipt_phase: Literal["requested", "executing", "world_committed_reentry_pending"],
        predecessor_receipt_ref: str | None,
        owner_receipt_refs: tuple[str, ...],
    ) -> AcquisitionRoutePhaseReceipt:
        coarse, recovery = {
            "requested": ("requested", "none"),
            "executing": ("executing", "none"),
            "world_committed_reentry_pending": (
                "world_committed",
                "reentry_recovery_required",
            ),
        }[receipt_phase]
        return AcquisitionRoutePhaseReceipt(
            receipt_id=f"{job_id}.{receipt_phase}",
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
            action_generation=1,
            job_id=job_id,
            compiled_ref=closure.compiled_ref,
            planner_report_hash=agent_action_content_hash(closure.planner_report),
            cost_basis_hash=closure.cost_basis_hash,
            decision_ref=decision_ref,
            coarse_phase=coarse,
            receipt_phase=receipt_phase,
            recovery_state=recovery,
            predecessor_receipt_ref=predecessor_receipt_ref,
            owner_receipt_refs=owner_receipt_refs,
            generated_at=datetime.now(UTC),
        )

    @staticmethod
    def _terminal_receipt(
        *,
        closure: VerifiedAcquisitionRouteClosure,
        job_id: str,
        decision_ref: str,
        predecessor_receipt_ref: str,
        owner_receipt_refs: tuple[str, ...],
    ) -> AcquisitionRouteLoopReceipt:
        return AcquisitionRouteLoopReceipt(
            receipt_id=f"{job_id}.terminal",
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
            action_generation=1,
            job_id=job_id,
            compiled_ref=closure.compiled_ref,
            planner_report_hash=agent_action_content_hash(closure.planner_report),
            cost_basis_hash=closure.cost_basis_hash,
            decision_ref=decision_ref,
            terminal_outcome="quarantined_no_growth",
            predecessor_receipt_ref=predecessor_receipt_ref,
            owner_receipt_refs=owner_receipt_refs,
            reentry_receipt_ref=None,
            generated_at=datetime.now(UTC),
        )

    def _read_phase_receipt(self, ref: str) -> AcquisitionRoutePhaseReceipt:
        try:
            from polisyos.core import canon

            return AcquisitionRoutePhaseReceipt.model_validate(
                canon.from_canonical_bytes(self.control_service._artifact_store.get_bytes(ref))
            )
        except Exception as exc:
            raise AcquisitionActionServiceError("acquisition_phase_readback_failed") from exc

    @staticmethod
    def _terminal_progress(head: AcquisitionActionHeadRecord) -> dict[str, Any]:
        if head.receipt_phase != "terminal":
            raise AcquisitionActionServiceError("acquisition_terminal_head_missing")
        return {
            "state": "completed",
            "phase": "acquisition",
            "receipt_phase": "terminal",
            "terminal_receipt_ref": head.receipt_ref,
        }

    def _require_authority_provider(self) -> AcquisitionAuthorityGatewayProvider:
        if self._authority_provider is None:
            raise AcquisitionActionServiceError("acquisition_authority_producer_missing")
        return self._authority_provider

    def _production_execution_bridge_installed(self) -> bool:
        from .acquisition_surface_execution import WorldBankWDIAcquisitionExecutionPort

        production_port = getattr(self, "_production_execution_port", None)
        return (
            type(production_port) is WorldBankWDIAcquisitionExecutionPort
            and self._execution_port is production_port
        )

    def _production_execution_bridge_ready(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> bool:
        from polisyos.runtime.quality.acquisition_executor import (
            LiveAcquisitionExecutionError,
        )

        production_port = getattr(self, "_production_execution_port", None)
        if not self._production_execution_bridge_installed():
            return False
        try:
            production_port.require_route_ready(closure)
        except (LiveAcquisitionExecutionError, AcquisitionActionServiceError):
            return False
        return True

    def _require_production_execution_bridge(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> None:
        """Refuse public reservation unless the exact route binding is executable."""

        from polisyos.runtime.quality.acquisition_executor import (
            LiveAcquisitionExecutionError,
        )

        production_port = getattr(self, "_production_execution_port", None)
        if not self._production_execution_bridge_installed():
            raise AcquisitionActionServiceError("acquisition_execution_bridge_missing")
        try:
            production_port.reserve_route_binding(closure)
        except LiveAcquisitionExecutionError as exc:
            raise AcquisitionActionServiceError(exc.code) from exc

    def _require_execution_port(self) -> AcquisitionExecutionPort:
        if self._execution_port is None:
            raise AcquisitionActionServiceError("acquisition_execution_bridge_missing")
        return self._execution_port


__all__ = [
    "AcquisitionActionService",
    "AcquisitionActionServiceError",
    "AcquisitionAuthorityGatewayProvider",
    "AcquisitionDecisionRequestResponse",
    "AcquisitionExecutionPort",
    "AcquisitionExecutionResponse",
    "AcquisitionOwnerExecutionResult",
    "AcquisitionRouteListResponse",
    "AcquisitionRouteMutationRequest",
    "AcquisitionRouteProjection",
    "AcquisitionRouteReplayPins",
]
