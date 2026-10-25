"""Prove terminal HTE validity delivery waits for the execution fence to release."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def test_completed_hte_outboxes_reconcile_after_terminal_fence_release(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real completion defers outbox delivery until the execution fence releases."""
    pytest.importorskip("econml", reason="portable HTE owner path requires EconML")

    from _helpers import runtime_http as runtime_http_helpers
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from _helpers.runtime_http import (
        _record_fixture_owner,
        build_runtime_api_env,
        close_runtime_api_env,
    )

    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.control_plane_store import (
        _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        ControlJobLeaseLostError,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import (
        _publish_complete_search_task,
        _put_v2_hte_source,
        _request_payload,
    )

    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={
            "repo_root": Path(runtime_http_helpers.__file__).resolve().parents[2],
        },
    )
    secure_client = None
    try:
        service = env["app"].state._control_service
        stop_embedded_control_worker(service)
        tenant_id = env["tenant_a"]
        secure_client, cell, provider = _build_secure_client(
            env,
            opa_client=_AllowOPA(),
            claims_by_token={},
            raise_server_exceptions=True,
        )
        secure_client.app.state.runtime_container.control_service = service
        secure_client.app.state._control_service = service
        cell_id = cell.cell_id
        bearer = _fixture_bearer("completed-hte-terminal-fence")
        provider.put_claim(
            bearer,
            _claims(
                tenant_id=tenant_id,
                cell_id=cell_id,
                jti="jwt-completed-hte-terminal-fence",
                roles=frozenset({PolicyOSRole.ANALYST}),
            ),
        )
        headers = {
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": tenant_id,
        }

        validity_delivery_contexts: list[tuple[str, str, int] | None] = []
        search_delivery_contexts: list[tuple[str, str, int] | None] = []
        published_validity_events: list[tuple[str | None, str | None]] = []
        store = service._control_store
        original_validity_delivery = service._deliver_completed_hte_source_validity_outbox
        original_search_delivery = service._deliver_search_hte_completion_outbox
        original_publish = service.publish_decision_validity_event

        def observe_validity_delivery(delivery: Any) -> bool:
            validity_delivery_contexts.append(store._job_execution_fence.get())
            return original_validity_delivery(delivery)

        def observe_search_delivery(delivery: Any) -> bool:
            search_delivery_contexts.append(store._job_execution_fence.get())
            return original_search_delivery(delivery)

        def observe_publish(
            request: Any,
            *,
            request_id: str | None = None,
            event_id: str | None = None,
        ) -> Any:
            published_validity_events.append((event_id, request.dedupe_key))
            return original_publish(request, request_id=request_id, event_id=event_id)

        monkeypatch.setattr(
            service,
            "_deliver_completed_hte_source_validity_outbox",
            observe_validity_delivery,
        )
        monkeypatch.setattr(
            service,
            "_deliver_search_hte_completion_outbox",
            observe_search_delivery,
        )
        monkeypatch.setattr(service, "publish_decision_validity_event", observe_publish)

        search_store = service._require_search_uncertainty_store()
        run_id = "run-terminal-fence"
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            source_ref = _put_v2_hte_source(
                service._artifact_store,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            _record_fixture_owner(
                service._artifact_store,
                source_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            search_state, ticket_id, binding_ref = _publish_complete_search_task(
                store=search_store,
                service=service,
                source_ref=source_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
            )
            initial_snapshot = search_state.read_current_snapshot(ticket_id)
        assert initial_snapshot is not None
        assert initial_snapshot.resolved_projection is not None
        assert initial_snapshot.resolved_projection.selected_unassessed_observations

        from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
        from polisyos.foundry.methods.selection.history import SelectionHistoryStore

        history = SelectionHistoryStore(
            persist_path=tmp_path / "selection-history" / "executions.jsonl",
            auto_persist=True,
        )
        monkeypatch.setattr(
            MethodDispatcher,
            "_instance",
            MethodDispatcher(runtime_history=history),
        )

        response = secure_client.post(
            "/api/v1/control/runs",
            json=_request_payload(source_ref, binding_ref),
            headers=headers,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        job_id = accepted["job_id"]
        source_run_id = accepted["run_id"]

        assert (
            dispatch_one_control_job(
                store=store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )

        completed = store.get_job(job_id)
        assert completed is not None and completed.state == "completed", (
            f"state={getattr(completed, 'state', None)!r}; "
            f"error={getattr(completed, 'error_message', None)!r}"
        )
        assert completed.run_id == source_run_id
        selection = completed.method_execution_selection
        assert isinstance(selection, Mapping)
        assert selection["method_version"] == "2.0.0"
        selected_hte = selection.get("hte")
        assert isinstance(selected_hte, Mapping)
        assert selected_hte.get("search_uncertainty_task_binding_ref") is not None

        completed_event = store.get_job_terminal_source_event_record(job_id)
        assert completed_event is not None
        assert completed_event.event_type == "job_completed"
        assert completed_event.payload["attempt"] == completed.attempt
        validity_delivery = store.get_outbox_topic_event(
            topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
            event_key=f"{job_id}:job_completed:{completed_event.event_id}",
            job_id=job_id,
        )
        search_delivery = store.get_search_hte_completion_outbox_event(
            job_id=job_id,
            completed_event_id=completed_event.event_id,
        )
        assert validity_delivery is not None and validity_delivery.state == "pending"
        assert search_delivery is not None and search_delivery.state == "pending"
        assert validity_delivery.run_id == source_run_id
        assert search_delivery.run_id == source_run_id
        assert validity_delivery_contexts == []
        assert search_delivery_contexts == []
        assert published_validity_events == []

        # Terminal completion revokes the worker attempt. Maintenance cannot
        # reacquire a stale execution fence to publish either outbox.
        with (
            pytest.raises(ControlJobLeaseLostError),
            store.job_execution_fence(
                job_id=job_id,
                worker_id=completed_event.payload["lease_owner"],
                attempt=completed_event.payload["attempt"],
            ),
        ):
            pytest.fail("a terminal attempt must not regain its execution fence")

        assert service.reconcile_pending_completed_hte_source_validity_events() == 1
        assert validity_delivery_contexts == [None]
        assert search_delivery_contexts == []
        assert len(published_validity_events) == 1
        assert published_validity_events[0][1] == validity_delivery.payload["dedupe_key"]

        published_validity = store.get_outbox_event(validity_delivery.event_id)
        assert published_validity is not None and published_validity.state == "published"
        published_search = store.get_outbox_event(search_delivery.event_id)
        assert published_search is not None and published_search.state == "pending"
        assert published_validity.attempt == 1

        assert service.reconcile_pending_completed_hte_source_validity_events() == 0
        assert validity_delivery_contexts == [None]
        assert search_delivery_contexts == []
        assert len(published_validity_events) == 1
    finally:
        if secure_client is not None:
            secure_client.close()
        close_runtime_api_env(env)
