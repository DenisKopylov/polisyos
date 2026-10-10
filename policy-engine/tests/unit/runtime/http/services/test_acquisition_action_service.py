from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionRouteMutationRequest,
)
from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionScope
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
