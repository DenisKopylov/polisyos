from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.mutation_policy import RuntimeIdempotencyStore
from polisyos.runtime.http.services import (
    acquisition_action_service as action_service_module,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    AcquisitionRouteMutationRequest,
)
from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionScope
from polisyos.runtime.quality.agent_action_authority import (
    AgentActionAuthorityGateway,
    AgentActionAuthorityWriteContext,
)
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _NeverExecutionPort:
    def execute(self, closure):  # pragma: no cover - replay must stop before owner execution
        del closure
        raise AssertionError("terminal replay must not invoke the owner effect")

    def reenter(self, closure, result):  # pragma: no cover - terminal replay has no re-entry
        del closure, result
        raise AssertionError("terminal replay must not re-enter")

    def resume_reentry(self, closure, owner_receipt_refs):  # pragma: no cover
        del closure, owner_receipt_refs
        raise AssertionError("terminal replay must not resume re-entry")


class _NeverAuthorityProvider:
    def for_job(self, **_kwargs):  # pragma: no cover - terminal replay must stop before authority
        raise AssertionError("terminal replay must not request authority")

    def for_request(self, **_kwargs):  # pragma: no cover
        raise AssertionError("terminal replay must not create a new decision")


@pytest.mark.asyncio
async def test_replayed_terminal_job_reads_cas_head_without_repeating_authority_or_effect(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fixture_wdi_cost_basis(monkeypatch)
    with runtime_api_env["client"]:
        app = runtime_api_env["app"]
        container = app.state.runtime_container
        control = container.control_service
        service = container.acquisition_action_service
        assert type(service) is AcquisitionActionService
        assert service.control_service is control
        tenant_id = str(runtime_api_env["tenant_a"])
        cell_id = str(runtime_api_env["cell_a"])
        run_id = "run-dx0-terminal-replay"

        async with _fixture_route(
            control,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        ) as closure:
            projection = service._projection(closure)
            request = AcquisitionRouteMutationRequest(
                route_projection_hash=projection.route_projection_hash,
                planner_report_hash=projection.planner_report_hash,
                replay_pins=projection.replay_pins,
                idempotency_key="dx0-terminal-replay",
            )
            operation, invocation, intent = service._action_tuple(closure, request)
            job_id = service._job_id(closure, request)
            payload = {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": closure.route_id,
                "decision_ref": "sha256:" + "9" * 64,
                "request": request.model_dump(mode="json"),
                "operation": operation.model_dump(mode="json"),
                "invocation": invocation.model_dump(mode="json"),
                "intent": intent.model_dump(mode="json"),
            }

            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                job = control.enqueue_acquisition_job(
                    job_id=job_id,
                    run_id=run_id,
                    payload=payload,
                    principal=RuntimePrincipal(
                        subject="dx0-terminal-replay",
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        authenticated=True,
                        roles=frozenset({"analyst"}),
                    ),
                )
                sink = control.acquisition_route_sink
                generation = service._action_generation(closure, job_id)
                requested = service._phase_receipt(
                    action_generation=generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=str(payload["decision_ref"]),
                    receipt_phase="requested",
                    predecessor_receipt_ref=None,
                    owner_receipt_refs=(),
                )
                requested_head = sink.persist_phase(requested)
                executing = service._phase_receipt(
                    action_generation=generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=str(payload["decision_ref"]),
                    receipt_phase="executing",
                    predecessor_receipt_ref=requested_head.receipt_ref,
                    owner_receipt_refs=(),
                )
                executing_head = sink.persist_phase(executing)
                owner_ref = control._put_json_artifact(
                    {"disposition": "quarantined_no_growth"},
                    kind="runtime_quality.acquisition_owner_receipt",
                    schema_name="polisyos.runtime.AcquisitionOwnerReceipt",
                )
                terminal = service._terminal_receipt(
                    action_generation=generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=str(payload["decision_ref"]),
                    predecessor_receipt_ref=executing_head.receipt_ref,
                    owner_receipt_refs=(owner_ref,),
                )
                terminal_head = sink.persist_terminal(terminal)

                original_port = service._execution_port
                original_provider = service._authority_provider
                original_movement = service._movement_service
                service._execution_port = _NeverExecutionPort()
                service._authority_provider = _NeverAuthorityProvider()
                service._movement_service = None
                try:
                    scope = ControlJobExecutionScope(
                        status="established",
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        actor_subject="dx0-terminal-replay",
                        actor_authenticated=True,
                        actor_roles=("analyst",),
                    )
                    first = service.handle_job(job, payload, scope)
                    second = service.handle_job(job, payload, scope)
                finally:
                    service._execution_port = original_port
                    service._authority_provider = original_provider
                    service._movement_service = original_movement

            assert first == second
            assert first["receipt_phase"] == "terminal"
            assert first["terminal_receipt_ref"] == terminal_head.receipt_ref


@asynccontextmanager
async def _fixture_route(
    control: Any,
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
) -> AsyncIterator[Any]:
    closure, _source = await persist_wdi_route(
        control,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        job_id="job-dx0-terminal-replay-source",
    )
    yield closure


@pytest.mark.asyncio
async def test_execute_retries_bound_requested_and_terminal_action_identity(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """HTTP retries bind their deterministic job before selecting route history."""
    from tests.unit.runtime.quality.test_agent_action_authority import _proof

    install_fixture_wdi_cost_basis(monkeypatch)
    decision_ref = "sha256:" + "d" * 64
    monkeypatch.setattr(
        action_service_module,
        "reserve_agent_external_action",
        lambda **_kwargs: SimpleNamespace(
            write_result=SimpleNamespace(cas_ref=SimpleNamespace(artifact_id=decision_ref))
        ),
    )
    with runtime_api_env["client"]:
        app = runtime_api_env["app"]
        container = app.state.runtime_container
        control = container.control_service
        service = container.acquisition_action_service
        tenant_id = str(runtime_api_env["tenant_a"])
        cell_id = str(runtime_api_env["cell_a"])
        run_id = "run-dx0-requested-retry"

        class _ControlledAuthorityProvider:
            def for_request(
                self,
                *,
                closure,
                job_id: str,
                bound_permission,
                effect_handler,
                request,
            ) -> AgentActionAuthorityGateway:
                del request
                return AgentActionAuthorityGateway(
                    artifact_store=control._artifact_store,
                    event_log=control._diagnostic_event_log,
                    idempotency_store=RuntimeIdempotencyStore(
                        root=tmp_path / "controlled-idempotency"
                    ),
                    artifact_verifier=artifacts.Ed25519Verifier(),
                    bound_permission=bound_permission,
                    admission_producer_identity="controlled-test-seam",
                    write_context=AgentActionAuthorityWriteContext(
                        tenant_id=closure.tenant_id,
                        cell_id=closure.cell_id,
                        run_id=closure.run_id,
                        job_id=job_id,
                        trace_id=job_id,
                        span_id=f"{job_id}.authority",
                        owner="controlled-test-seam",
                        requested_execution_profile="test",
                        effective_execution_profile="test",
                        effective_mode_ref="fixture://controlled-test-seam",
                    ),
                    contract_refs_by_resource_digest={},
                    mandate_authority_evidence_refs_by_owner_ref={},
                    admission_refs_by_invocation_hash={},
                    effect_bindings=(),
                )

            def for_job(self, **_kwargs):  # pragma: no cover - terminal path stops before authority
                raise AssertionError("terminal replay must not request job authority")

        principal = RuntimePrincipal(
            subject="dx0-requested-retry",
            tenant_id=tenant_id,
            cell_id=cell_id,
            authenticated=True,
            roles=frozenset({"analyst"}),
        )

        async with _fixture_route(
            control,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        ) as closure:
            projection = service._projection(closure)
            request = AcquisitionRouteMutationRequest(
                route_projection_hash=projection.route_projection_hash,
                planner_report_hash=projection.planner_report_hash,
                replay_pins=projection.replay_pins,
                idempotency_key="dx0-requested-retry",
            )
            operation, invocation, intent = service._action_tuple(closure, request)
            monkeypatch.setattr(service, "_authority_provider", _ControlledAuthorityProvider())
            monkeypatch.setattr(service, "_execution_port", _NeverExecutionPort())
            monkeypatch.setattr(service, "_production_execution_bridge_installed", lambda: True)
            monkeypatch.setattr(
                service, "_require_production_execution_bridge", lambda _closure: None
            )
            monkeypatch.setattr(service, "_movement_service", None)

            def execute() -> object:
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    return service.execute(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        run_id=run_id,
                        route_id=closure.route_id,
                        request=request,
                        bound_permission=_proof(),
                        request_id="dx0-requested-retry",
                        principal=principal,
                    )

            with monkeypatch.context() as interrupted_enqueue:
                interrupted_enqueue.setattr(
                    control,
                    "enqueue_acquisition_job",
                    lambda **_kwargs: (_ for _ in ()).throw(
                        RuntimeError("controlled queue interruption")
                    ),
                )
                with pytest.raises(RuntimeError, match="controlled queue interruption"):
                    execute()

            with (
                tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
                pytest.raises(AcquisitionActionServiceError) as pending_route,
            ):
                service.get_route(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=run_id,
                    route_id=closure.route_id,
                )
            assert pending_route.value.code == "acquisition_action_outcome_not_terminal"

            retried = execute()
            job_id = service._job_id(closure, request)
            assert retried.job_id == job_id
            assert retried.authority_decision_ref == decision_ref

            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                sink = control.acquisition_route_sink
                action_generation = service._action_generation(closure, job_id)
                requested = service._phase_receipt(
                    action_generation=action_generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=decision_ref,
                    receipt_phase="requested",
                    predecessor_receipt_ref=None,
                    owner_receipt_refs=(),
                )
                requested_head = sink.get_head(requested)
                assert requested_head is not None
                executing = service._phase_receipt(
                    action_generation=action_generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=decision_ref,
                    receipt_phase="executing",
                    predecessor_receipt_ref=requested_head.receipt_ref,
                    owner_receipt_refs=(),
                )
                executing_head = sink.persist_phase(executing)
                owner_ref = control._put_json_artifact(
                    {"disposition": "quarantined_no_growth"},
                    kind="runtime_quality.acquisition_owner_receipt",
                    schema_name="polisyos.runtime.AcquisitionOwnerReceipt",
                )
                terminal_head = sink.persist_terminal(
                    service._terminal_receipt(
                        action_generation=action_generation,
                        closure=closure,
                        job_id=job_id,
                        decision_ref=decision_ref,
                        predecessor_receipt_ref=executing_head.receipt_ref,
                        owner_receipt_refs=(owner_ref,),
                    )
                )

            terminal_retry = execute()
            assert terminal_retry.job_id == job_id
            assert terminal_retry.route_id == closure.route_id
            assert terminal_retry.receipt_phase == "requested"

            payload = {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": closure.route_id,
                "decision_ref": decision_ref,
                "request": request.model_dump(mode="json"),
                "operation": operation.model_dump(mode="json"),
                "invocation": invocation.model_dump(mode="json"),
                "intent": intent.model_dump(mode="json"),
            }
            job = control._control_store.get_job(job_id)
            assert job is not None
            scope = ControlJobExecutionScope(
                status="established",
                tenant_id=tenant_id,
                cell_id=cell_id,
                actor_subject="dx0-requested-retry",
                actor_authenticated=True,
                actor_roles=("analyst",),
            )
            original_port = service._execution_port
            original_provider = service._authority_provider
            service._execution_port = _NeverExecutionPort()
            service._authority_provider = _NeverAuthorityProvider()
            try:
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    replay = service.handle_job(job, payload, scope)
                    wrong_job = replace(job, job_id=f"{job_id}-sibling")
                    with pytest.raises(AcquisitionActionServiceError) as wrong_identity:
                        service.handle_job(wrong_job, payload, scope)
            finally:
                service._execution_port = original_port
                service._authority_provider = original_provider

            assert replay["receipt_phase"] == "terminal"
            assert replay["terminal_receipt_ref"] == terminal_head.receipt_ref
            assert wrong_identity.value.code == "acquisition_job_identity_mismatch"
            assert payload["request"] == request.model_dump(mode="json")
            assert payload["invocation"] == invocation.model_dump(mode="json")
