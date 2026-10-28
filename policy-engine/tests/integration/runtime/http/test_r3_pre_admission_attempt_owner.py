from __future__ import annotations

import asyncio
import hashlib
import json
import os
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control.job_nl_execution import ControlNLJobExecutionMixin
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env
from tests.unit.runtime.http.test_control_api import _secure_control_client


@pytest.mark.parametrize(
    ("usage", "expected_origin", "preenqueue_failure", "remove_settlement"),
    [
        ({"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 0.0015}, "reported", None, False),
        ({"prompt_tokens": 2, "completion_tokens": 1}, "estimated", None, False),
        (None, "unknown", None, False),
        (None, "unknown", "cancelled", False),
        (
            {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 0.0015},
            "reported",
            "cancelled",
            False,
        ),
        (
            {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 0.0015},
            "reported",
            "ordinary_exception",
            False,
        ),
        ({"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 0.0015}, "reported", None, True),
    ],
    ids=(
        "reported",
        "estimated",
        "unknown",
        "unknown-cost-cancel-before-enqueue",
        "cancel-after-settlement-before-enqueue",
        "ordinary-failure-after-settlement-before-enqueue",
        "remove-settlement-keep-job-markers",
    ),
)
def test_actual_nl_post_gateway_settlement_reopens_and_serves_same_run(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    usage: dict[str, Any] | None,
    expected_origin: str,
    preenqueue_failure: str | None,
    remove_settlement: bool,
) -> None:
    """Prove one admitted route event plus same-scope reuse at the fresh GET consumer."""
    observed: list[dict[str, Any]] = []
    completions: list[dict[str, Any]] = []
    api_key = "sk-r3-local-gateway-test-key"

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            observed.append({"method": "GET", "path": self.path})
            if self.path == "/health":
                self._send({"status": "ok"})
            elif self.path == "/v1/models":
                self._send({"data": [{"id": "gpt-4o"}]})
            elif self.path == "/api/models/capabilities":
                self._send({"models": [{"model": "gpt-4o"}]})
            elif self.path == "/api/pricing":
                self._send({"source": "controlled fixture"})
            else:
                self._send({"error": "unexpected path"}, status=404)

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            request_id = f"r3-provider-request-{len(completions) + 1}"
            observed.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "request_id": request_id,
                    "idempotency_key_present": bool(self.headers.get("x-idempotency-key")),
                    "authorization_present": self.headers.get("Authorization")
                    == f"Bearer {api_key}",
                }
            )
            completions.append(body)
            payload: dict[str, Any] = {
                "model": "response-model-label-is-not-authority",
                "provider": "response-provider-label-is-not-authority",
                "id": request_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"status":"ok"}'},
                        "finish_reason": "stop",
                    }
                ],
            }
            if usage is not None:
                payload["usage"] = usage
            response = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", request_id)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PROVIDER", "controlled-local-gateway")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", api_key)
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "300")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "128")
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    for proxy in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(proxy, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")

    provider_module = __import__(
        "polisyos.scientist.orchestration.llm.provider_verification", fromlist=["*"]
    )
    run_lifecycle = __import__(
        "polisyos.runtime.http.services.control.run_lifecycle", fromlist=["*"]
    )
    monkeypatch.setattr(provider_module, "_PREFLIGHT_CACHE", {})
    monkeypatch.setattr(provider_module, "_PREFLIGHT_COMPLETION_CACHE", {})
    actual_settle = BudgetMiddleware.settle_producer_event_safe
    lost_ack_event_ids: list[str] = []

    def _lose_one_ack_after_durable_write(self: Any, *args: Any, **kwargs: Any) -> Any:
        record = actual_settle(self, *args, **kwargs)
        if not lost_ack_event_ids:
            lost_ack_event_ids.append(record.event_id)
            raise OSError("controlled lost acknowledgement after durable ledger write")
        return record

    monkeypatch.setattr(
        BudgetMiddleware, "settle_producer_event_safe", _lose_one_ack_after_durable_write
    )
    actual_prepare = provider_module.prepare_cached_request
    prepared_calls: list[Any] = []

    def capture_prepared(*args: Any, **kwargs: Any) -> Any:
        request = actual_prepare(*args, **kwargs)
        prepared_calls.append(request)
        return request

    monkeypatch.setattr(provider_module, "prepare_cached_request", capture_prepared)
    actual_preflight = run_lifecycle.run_provider_preflight
    reports: list[Any] = []
    preflight_calls: list[dict[str, Any]] = []
    preenqueue_hook_entered: list[str] = []
    preenqueue_exception_types: list[str] = []

    async def _capture_actual_preflight(**kwargs: Any) -> Any:
        # The first call is the ordinary POST path. The second is a same-binding
        # retry witness: the real producer/cache must append a distinct reuse event.
        preflight_calls.append(dict(kwargs))
        before = len(prepared_calls)
        first = await actual_preflight(**kwargs)
        assert len(prepared_calls) == before + 1
        first_plan = prepared_calls[-1]
        first_event = next(check for check in first.checks if check.name == "tiny_completion")
        assert first_event.details["producer_event"]["request_digest"] == first_plan.request_digest
        reports.append(first)
        if preenqueue_failure == "cancelled":
            preenqueue_hook_entered.append("after_provider_settlement_before_enqueue")
            try:
                raise asyncio.CancelledError("controlled cancellation after durable preflight")
            except BaseException as exc:
                preenqueue_exception_types.append(type(exc).__name__)
                raise
        if preenqueue_failure == "ordinary_exception":
            preenqueue_hook_entered.append("after_provider_settlement_before_enqueue")
            try:
                raise RuntimeError("controlled ordinary failure after durable preflight")
            except BaseException as exc:
                preenqueue_exception_types.append(type(exc).__name__)
                raise
        retry = await actual_preflight(**kwargs)
        assert prepared_calls[-1] is not first_plan
        assert prepared_calls[-1].request_digest == first_plan.request_digest
        retry_event = next(check for check in retry.checks if check.name == "tiny_completion")
        assert retry_event.details["producer_event"]["request_digest"] == first_plan.request_digest
        reports.append(retry)
        return first

    monkeypatch.setattr(run_lifecycle, "run_provider_preflight", _capture_actual_preflight)

    def _stop_after_core_run_admission(self: Any, context: Any) -> None:
        del self
        assert context.core_run_id is not None
        assert context.core_run_context is not None
        raise RuntimeError("r3_test_boundary_after_core_run_admission")

    monkeypatch.setattr(
        ControlNLJobExecutionMixin, "_execute_control_nl_job", _stop_after_core_run_admission
    )

    env = build_runtime_api_env(tmp_path, include_test_client=False)
    client, _cell_id, headers = _secure_control_client(
        env,
        role=PolicyOSRole.ADMIN,
        case_id=f"r3-{expected_origin}",
    )
    try:
        with client:
            request_json = NaturalLanguageRunRequest(
                request="Measure the bounded cost of a local policy analysis.",
                execution_profile="research",
                llm_models=["gpt-4o"],
                max_iterations=1,
                policy_flags={"allow_mock_fallback": False},
            ).model_dump(mode="json", exclude_unset=True)
            idempotency_headers = {
                **headers,
                "Idempotency-Key": f"r214-preflight-{expected_origin}",
            }
            missing_attempt = client.get(
                "/api/v1/control/admission-attempts/by-idempotency-key",
                headers={**headers, "Idempotency-Key": "r215-no-row-control"},
            )
            # Not-found is unknown, not evidence that provider work did not occur.
            assert missing_attempt.status_code == 404, missing_attempt.text
            if preenqueue_failure is not None:
                failure_response = client.post(
                    "/api/v1/control/runs/nl",
                    headers={
                        **idempotency_headers,
                        "X-Request-ID": f"r214-{preenqueue_failure}",
                    },
                    json=request_json,
                )
                assert preenqueue_hook_entered == ["after_provider_settlement_before_enqueue"]
                expected_exception = (
                    "CancelledError" if preenqueue_failure == "cancelled" else "RuntimeError"
                )
                assert preenqueue_exception_types == [expected_exception]
                assert failure_response.status_code == 500, failure_response.text
                assert "NameError" not in failure_response.text
                assert "asyncio" not in failure_response.text
                assert len(preflight_calls) == 1
                assert len(reports) == 1
                binding = preflight_calls[0]["producer_run_binding"]
                assert binding.run_id
                assert binding.control_job_id
                assert binding.profile_id == "research"
                assert reports[0].status == "ok"
                assert len(completions) == 1
                assert len(lost_ack_event_ids) == 1
                ledger_path = Path(env["cas_root"]) / "runs" / ".runtime" / "llm-cost-ledger.json"
                records = FileBudgetLedger(ledger_path).snapshot().producer_settlements
                orphaned = [record for record in records.values() if record.run_binding == binding]
                assert len(orphaned) == 1
                assert orphaned[0].event_id == lost_ack_event_ids[0]
                assert orphaned[0].cost_origin == expected_origin
                assert orphaned[0].status == (
                    "unknown" if expected_origin == "unknown" else "committed"
                )
                assert orphaned[0].amount == (
                    None if expected_origin == "unknown" else Decimal("0.0015")
                )
                # The attempt is durable before job enqueue; the missing ControlJob
                # is not used as evidence that an unknown or committed charge vanished.
                service = client.app.state._control_service
                assert service._control_store.get_job(binding.control_job_id) is None
                assert service.get_latest_job_for_run(binding.run_id) is None
                orphan_get = client.get(
                    f"/api/v1/control/jobs/{binding.control_job_id}", headers=headers
                )
                assert orphan_get.status_code == 404, orphan_get.text
                retry_response = client.post(
                    "/api/v1/control/runs/nl",
                    headers=idempotency_headers,
                    json=request_json,
                )
                assert retry_response.status_code == 409, retry_response.text
                retry_payload = retry_response.json()
                attempt_id = retry_response.headers.get(
                    "X-Control-Admission-Attempt-ID"
                ) or retry_payload.get("pre_admission_attempt_id")
                assert attempt_id
                assert retry_payload.get("pre_admission_attempt_id") == attempt_id
                assert len(preflight_calls) == 1
                assert len(completions) == 1
                attempt_history_response = client.get(
                    f"/api/v1/control/admission-attempts/{attempt_id}",
                    headers=headers,
                )
                assert attempt_history_response.status_code == 200, attempt_history_response.text
                assert attempt_history_response.headers["cache-control"] == "no-store"
                attempt_history = attempt_history_response.json()
                by_key_response = client.get(
                    "/api/v1/control/admission-attempts/by-idempotency-key",
                    headers=idempotency_headers,
                )
                assert by_key_response.status_code == 200, by_key_response.text
                assert by_key_response.headers["cache-control"] == "no-store"
                by_key_history = by_key_response.json()
                assert by_key_history["attempt_id"] == attempt_history["attempt_id"]
                assert by_key_history["status"] == attempt_history["status"]
                assert by_key_history["producer_event_ids"] == attempt_history["producer_event_ids"]
                assert by_key_history["history"] == attempt_history["history"]
                assert by_key_response.request.url.path == (
                    "/api/v1/control/admission-attempts/by-idempotency-key"
                )
                assert by_key_response.request.url.query == b""
                expected_attempt_status = (
                    "cancelled" if preenqueue_failure == "cancelled" else "failed"
                )
                assert attempt_history["status"] == expected_attempt_status
                assert [event["event_type"] for event in attempt_history["history"]] == [
                    "started",
                    "settled",
                    expected_attempt_status,
                ]
                assert attempt_history["job_id"] is None
                assert attempt_history["run_id"] == binding.run_id
                assert attempt_history["effective_execution_profile"] == "research"
                assert attempt_history["producer_event_observation"] == "complete"
                assert attempt_history["producer_event_ids"] == [orphaned[0].event_id]
                assert attempt_history["history"][-1]["producer_event_ids"] == [
                    orphaned[0].event_id
                ]
                fresh_attempt = client.get(
                    f"/api/v1/control/admission-attempts/{attempt_id}",
                    headers=headers,
                )
                assert fresh_attempt.status_code == 200, fresh_attempt.text
                assert fresh_attempt.json()["status"] == expected_attempt_status
                assert fresh_attempt.json()["producer_event_ids"] == [orphaned[0].event_id]
                return

            launch_response = client.post(
                "/api/v1/control/runs/nl",
                headers=idempotency_headers,
                json=request_json,
            )
            assert launch_response.status_code == 200, launch_response.text
            launch = launch_response.json()
            assert launch["status"] == "accepted"
            assert launch["effective_execution_profile"] == "research"
            attempt_id = launch_response.headers.get("X-Control-Admission-Attempt-ID")
            assert attempt_id is not None
            attempt_history_response = client.get(
                f"/api/v1/control/admission-attempts/{attempt_id}",
                headers=headers,
            )
            assert attempt_history_response.status_code == 200, attempt_history_response.text
            attempt_history = attempt_history_response.json()
            assert attempt_history["status"] == "admitted"
            assert attempt_history["run_id"] == launch["run_id"]
            assert attempt_history["job_id"] == launch["job_id"]
            assert attempt_history["effective_execution_profile"] == "research"
            assert [event["event_type"] for event in attempt_history["history"]] == [
                "started",
                "settled",
                "admitted",
            ]
            replay_response = client.post(
                "/api/v1/control/runs/nl",
                headers=idempotency_headers,
                json=request_json,
            )
            assert replay_response.status_code == 200, replay_response.text
            assert replay_response.json()["job_id"] == launch["job_id"]
            assert replay_response.headers.get("X-Control-Admission-Attempt-ID") == attempt_id
            assert len(preflight_calls) == 1
            assert len(completions) == 1
            assert len(reports) == 2
            first_report, retry_report = reports
            assert first_report.status == retry_report.status == "ok"
            binding = preflight_calls[0]["producer_run_binding"]
            assert binding.run_id == launch["run_id"]
            assert binding.control_job_id == launch["job_id"]
            assert binding.profile_id == launch["effective_execution_profile"]

            def _tiny(report: Any) -> dict[str, Any]:
                check = next(item for item in report.checks if item.name == "tiny_completion")
                return check.details

            first_details = _tiny(first_report)
            retry_details = _tiny(retry_report)
            first_ref = first_details["producer_event"]
            reuse_ref = retry_details["producer_event"]
            actual_request_id = next(
                row["request_id"] for row in observed if row["method"] == "POST"
            )
            assert first_details["request_id"] == actual_request_id
            assert retry_details["request_id"] == actual_request_id
            assert first_ref["event_id"] != reuse_ref["event_id"]
            assert set(attempt_history["producer_event_ids"]) == {
                first_ref["event_id"],
                reuse_ref["event_id"],
            }
            assert set(attempt_history["history"][1]["producer_event_ids"]) == {
                first_ref["event_id"],
                reuse_ref["event_id"],
            }
            assert lost_ack_event_ids == [first_ref["event_id"]]
            assert first_ref["cost_origin"] == expected_origin
            assert reuse_ref["cost_origin"] == "reuse"
            assert reuse_ref["origin_event_id"] == first_ref["event_id"]
            assert reuse_ref["amount"] == "0"
            assert (
                len(completions) == 1
            )  # Same-binding retry did not dispatch a second provider POST.
            assert completions[0]["model"] == "gpt-4o"
            assert all(row["authorization_present"] for row in observed if row["method"] == "POST")
            assert all(
                row["idempotency_key_present"] for row in observed if row["method"] == "POST"
            )

            service = client.app.state._control_service
            job = service._control_store.get_job(launch["job_id"])
            assert job is not None
            assert job.run_id == launch["run_id"]
            assert job.effective_execution_profile == "research"
            with tenant_scope(None, tenant_id=binding.tenant_id, cell_id=binding.cell_id):
                payload = service._load_payload_ref(
                    job.payload_ref,
                    kind=f"runtime.control_job_payload.{job.kind}",
                )
            assert payload["provider_preflight"]["status"] == "ok"

            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=launch["job_id"],
            )
            terminal_job = service._control_store.get_job(launch["job_id"])
            assert terminal_job is not None and terminal_job.state == "failed"
            assert terminal_job.error_message == "r3_test_boundary_after_core_run_admission"
            core_run_id = terminal_job.progress["core_run_id"]
            assert core_run_id != launch["run_id"]

            ledger_path = Path(env["cas_root"]) / "runs" / ".runtime" / "llm-cost-ledger.json"
            reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
            records = reopened.list_producer_events_for_run_safe(binding)
            by_id = {record.event_id: record for record in records}
            assert set(by_id) == {first_ref["event_id"], reuse_ref["event_id"]}
            provider_record = by_id[first_ref["event_id"]]
            reuse_record = by_id[reuse_ref["event_id"]]
            assert provider_record.run_binding == binding
            assert provider_record.model == "gpt-4o"
            assert provider_record.provider == "controlled-local-gateway"
            assert provider_record.cost_origin == expected_origin
            assert provider_record.status == first_ref["settlement_status"]
            assert provider_record.amount == (
                Decimal(first_ref["amount"]) if first_ref["amount"] is not None else None
            )
            assert reuse_record.cost_origin == "reuse"
            assert reuse_record.origin_event_id == provider_record.event_id
            assert reuse_record.amount == Decimal(0)

            runtime_context = client.app.state.runtime_container.runtime_api_context
            runtime_context.run_index.refresh(force=True)
            runtime_context.debug.bind_producer_settlement_store(reopened)
            get_response = client.get(f"/api/v1/runs/{core_run_id}/agents", headers=headers)
            assert get_response.status_code == 200, get_response.text
            pipeline = get_response.json()["pipeline"]
            served_events = [
                event
                for attempt in pipeline["attempts"]
                for step in attempt["steps"]
                for event in step.get("cost_events", [])
            ]
            served_by_id = {event["event_id"]: event for event in served_events}
            assert len(served_by_id) == len(served_events)
            assert set(by_id).issubset(served_by_id)
            for record in records:
                served = served_by_id[record.event_id]
                assert served["origin_event_id"] == record.origin_event_id
                assert served["cost_origin"] == record.cost_origin
                assert served["settlement_status"] == record.status
                assert served["durability"] == "ledger"
                assert served["receipts"] == (
                    [record.event_id] if record.status == "committed" else []
                )
                assert served["amount"] == (
                    str(record.amount) if record.amount is not None else None
                )
                assert served["payload_digest"] == record.payload_digest
                assert served["model"] == record.model
                assert served["provider"] == record.provider

            if remove_settlement:
                original_snapshot = FileBudgetLedger(ledger_path).snapshot()
                removed_snapshot = original_snapshot.model_copy(
                    update={
                        "state": BudgetState(),
                        "spend_receipts": {},
                        "producer_settlements": {},
                        "recent_mutations": [],
                    }
                )
                removed_path = Path(tmp_path) / "removed-ledger.json"
                removed_path.write_text(
                    removed_snapshot.model_dump_json(exclude_none=True, indent=2),
                    encoding="utf-8",
                )
                removed_reader = BudgetMiddleware(
                    BudgetState(), ledger=FileBudgetLedger(removed_path)
                )
                runtime_context.debug.bind_producer_settlement_store(removed_reader)
                negative_response = client.get(
                    f"/api/v1/runs/{core_run_id}/agents", headers=headers
                )
                assert negative_response.status_code == 200, negative_response.text
                negative_pipeline = negative_response.json()["pipeline"]
                negative_events = [
                    event
                    for attempt in negative_pipeline["attempts"]
                    for step in attempt["steps"]
                    for event in step.get("cost_events", [])
                ]
                assert not (
                    {record.event_id for record in records}
                    & {event["event_id"] for event in negative_events}
                )
                assert payload["provider_preflight"]["status"] == "ok"
                retained_attempt = client.get(
                    f"/api/v1/control/admission-attempts/{attempt_id}",
                    headers=headers,
                )
                assert retained_attempt.status_code == 200, retained_attempt.text
                assert set(retained_attempt.json()["producer_event_ids"]) == {
                    first_ref["event_id"],
                    reuse_ref["event_id"],
                }
    finally:
        capture_path = os.getenv("R3_PROTOCOL_CAPTURE")
        if capture_path:
            with Path(capture_path).open("a", encoding="utf-8") as capture:
                capture.write(
                    json.dumps(
                        {
                            "case": expected_origin,
                            "preenqueue_failure": preenqueue_failure,
                            "remove_settlement": remove_settlement,
                            "provider_http": observed,
                            "provider_completion_count": len(completions),
                            "preflight_reports": [
                                {
                                    "status": report.status,
                                    "event": next(
                                        item.details["producer_event"]
                                        for item in report.checks
                                        if item.name == "tiny_completion"
                                    ),
                                }
                                for report in reports
                            ],
                            "lost_ack_event_ids": lost_ack_event_ids,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        close_runtime_api_env(env)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_nl_route_owner_preempts_generic_x_idempotency_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route-key replay is owner-bound, audited, and still subject to rate limits."""
    from polisyos.runtime.http.services.control import run_lifecycle

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "4")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "default-dev.sqlite3"))

    def _unexpected_preflight(**_kwargs: object) -> object:
        raise AssertionError("default dev must not run research provider preflight")

    monkeypatch.setattr(run_lifecycle, "run_provider_preflight", _unexpected_preflight)
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    client, _cell_id, auth_headers = _secure_control_client(
        env, role=PolicyOSRole.ADMIN, case_id="r216-default-dev"
    )
    request_json = NaturalLanguageRunRequest(
        request="Assess a bounded policy option under the default profile.",
        llm_models=["gpt-4o"],
        max_iterations=1,
        policy_flags={"allow_mock_fallback": False},
    ).model_dump(mode="json", exclude_unset=True)
    generic_key = "r219-generic-cache-sentinel"
    headers = {
        **auth_headers,
        "Idempotency-Key": "r216-default-dev-stable-replay-key",
        "X-Idempotency-Key": generic_key,
    }
    try:
        with client:
            first = client.post("/api/v1/control/runs/nl", headers=headers, json=request_json)
            assert first.status_code == 200, first.text
            payload = first.json()
            assert payload["status"] == "accepted"
            assert payload["effective_execution_profile"] == "dev"
            attempt_id = first.headers.get("X-Control-Admission-Attempt-ID")
            assert attempt_id and len(attempt_id) == 32

            service = client.app.state._control_service
            attempt = service._control_store.get_pre_admission_attempt(attempt_id)
            assert attempt is not None
            assert attempt.effective_execution_profile == "dev"
            assert attempt.run_id == payload["run_id"]
            assert attempt.job_id == payload["job_id"]
            assert [event.event_type for event in attempt.history] == ["started", "admitted"]
            assert all(
                event.producer_event_observation == "not_applicable"
                and not event.producer_event_ids
                for event in attempt.history
            )
            binding = attempt.producer_run_binding
            assert binding is not None
            assert binding["run_id"] == payload["run_id"]
            assert binding["control_job_id"] == payload["job_id"]
            assert binding["profile_id"] == "dev"
            assert binding["tenant_id"] == attempt.intent_binding["tenant_id"]
            assert binding["cell_id"] == attempt.intent_binding["cell_id"]

            replay = client.post("/api/v1/control/runs/nl", headers=headers, json=request_json)
            assert replay.status_code == 200, replay.text
            assert replay.json()["job_id"] == payload["job_id"]
            assert replay.headers.get("X-Control-Admission-Attempt-ID") == attempt_id
            assert replay.headers.get("X-Idempotent-Replay") is None
            by_key = client.get(
                "/api/v1/control/admission-attempts/by-idempotency-key",
                headers=headers,
            )
            assert by_key.status_code == 200, by_key.text
            assert by_key.headers["cache-control"] == "no-store"
            recovered = by_key.json()
            assert recovered["attempt_id"] == attempt_id
            assert recovered["effective_execution_profile"] == "dev"
            assert recovered["status"] == "admitted"
            assert recovered["owner_binding"] == {
                "purpose": "control.nl_pre_admission.v1",
                "scope_kind": "route",
                "scope_id": "control.runs.nl",
                "tenant_id": attempt.tenant_id,
                "cell_id": attempt.cell_id,
                "actor_subject_sha256": hashlib.sha256(
                    str(attempt.actor_subject).encode("utf-8")
                ).hexdigest(),
                "run_id": attempt.run_id,
                "intent_id": attempt.attempt_id,
                "body_sha256": attempt.intent_sha256,
                "request_content_sha256": attempt.intent_binding["request_content_sha256"],
                "effective_execution_profile": "dev",
            }

            second_key_headers = {
                **auth_headers,
                "Idempotency-Key": "r219-distinct-route-key",
                "X-Idempotency-Key": generic_key,
            }
            second = client.post(
                "/api/v1/control/runs/nl", headers=second_key_headers, json=request_json
            )
            assert second.status_code == 200, second.text
            second_payload = second.json()
            second_attempt_id = second.headers.get("X-Control-Admission-Attempt-ID")
            assert second_attempt_id and second_attempt_id != attempt_id
            assert second_payload["job_id"] != payload["job_id"]
            assert second.headers.get("X-Idempotent-Replay") is None
            second_by_key = client.get(
                "/api/v1/control/admission-attempts/by-idempotency-key",
                headers=second_key_headers,
            )
            assert second_by_key.status_code == 200, second_by_key.text
            assert second_by_key.headers["cache-control"] == "no-store"
            assert second_by_key.json()["attempt_id"] == second_attempt_id

            missing_route_key = {**auth_headers, "X-Idempotency-Key": generic_key}
            missing = client.post(
                "/api/v1/control/runs/nl", headers=missing_route_key, json=request_json
            )
            assert missing.status_code == 422, missing.text
            assert missing.headers.get("X-Control-Admission-Attempt-ID") is None
            assert missing.headers.get("X-Control-Pre-Admission-Outcome") == "not_created"
            assert missing.headers.get("X-Idempotent-Replay") is None

            rate_headers = {
                **auth_headers,
                "Idempotency-Key": "r219-rate-limited-route-key",
                "X-Idempotency-Key": generic_key,
            }
            limited = client.post(
                "/api/v1/control/runs/nl", headers=rate_headers, json=request_json
            )
            assert limited.status_code == 429, limited.text
            assert limited.json()["code"] == "rate_limit_exceeded"
            assert limited.headers.get("X-Control-Admission-Attempt-ID") is None
            limited_lookup = client.get(
                "/api/v1/control/admission-attempts/by-idempotency-key",
                headers=rate_headers,
            )
            assert limited_lookup.status_code == 404, limited_lookup.text
            assert limited_lookup.headers["cache-control"] == "no-store"

            audit_path = env["cas_root"] / "runtime" / "audit" / "mutations.jsonl"
            audit_rows = [
                json.loads(line)
                for line in audit_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            nl_rows = [row for row in audit_rows if row["endpoint"] == "/api/v1/control/runs/nl"]
            assert len(nl_rows) == 4
            assert all(row["idempotency_key"] == generic_key for row in nl_rows)
            assert all(
                isinstance(row["request_hash"], str) and len(row["request_hash"]) == 64
                for row in nl_rows
            )
            assert service._control_store.get_job(payload["job_id"]) is not None
            assert service._control_store.get_job(second_payload["job_id"]) is not None
    finally:
        close_runtime_api_env(env)


@pytest.mark.parametrize(
    ("body", "send_key"),
    [
        (
            {"request": "unknown profile is malformed", "execution_profile": "future-profile"},
            True,
        ),
        ({"request": "missing stable identity", "llm_models": ["gpt-4o"]}, False),
    ],
    ids=("malformed-profile-not-defaulted", "missing-idempotency-key-refused"),
)
def test_nl_pre_admission_4xx_marks_noncreated_attempt_and_404_is_uncached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, Any],
    send_key: bool,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    client, _cell_id, auth_headers = _secure_control_client(
        env, role=PolicyOSRole.ADMIN, case_id="r216-not-created"
    )
    key = "r216-known-no-attempt-key"
    headers = {**auth_headers, **({"Idempotency-Key": key} if send_key else {})}
    try:
        with client:
            response = client.post("/api/v1/control/runs/nl", headers=headers, json=body)
            assert response.status_code == 422, response.text
            assert response.headers.get("X-Control-Admission-Attempt-ID") is None
            assert response.headers.get("X-Control-Pre-Admission-Outcome") == "not_created"
            if send_key:
                not_found = client.get(
                    "/api/v1/control/admission-attempts/by-idempotency-key",
                    headers=headers,
                )
                assert not_found.status_code == 404, not_found.text
                assert not_found.headers["cache-control"] == "no-store"
    finally:
        close_runtime_api_env(env)
