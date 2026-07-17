from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.runtime.http.routes import runs as runs_routes


def _read_first_sse_snapshot(client: Any, path: str) -> dict[str, Any]:
    with client.stream("GET", path) as response:
        assert response.status_code == 200
        body = "".join(chunk for chunk in response.iter_text() if chunk)

    for event_block in body.split("\n\n"):
        if "event: snapshot" not in event_block:
            continue
        data_line = next(line for line in event_block.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))
        assert isinstance(payload, dict)
        return payload
    raise AssertionError(f"No snapshot event emitted by {path}")


def test_hidden_runs_sse_channels_emit_versioned_contracts(runtime_api_env, monkeypatch) -> None:
    monkeypatch.setattr(
        runs_routes.LiveStreamPolicy,
        "from_env",
        classmethod(
            lambda cls: cls(
                min_interval_seconds=0.01,
                max_interval_seconds=0.01,
                keepalive_seconds=10.0,
                max_duration_seconds=0.02,
            )
        ),
    )
    client = runtime_api_env["client"]

    runs_snapshot = _read_first_sse_snapshot(client, "/api/v1/runs/live")
    assert runs_snapshot["contract_id"] == "policyos.runtime.runs_list_snapshot"
    assert runs_snapshot["schema_version"] == "policyos.runtime.runs_list_snapshot.v1"
    assert isinstance(runs_snapshot["runs"], list)

    run_snapshot = _read_first_sse_snapshot(
        client, f"/api/v1/runs/{runtime_api_env['core_run_id']}/live"
    )
    assert run_snapshot["contract_id"] == "policyos.runtime.run_detail_snapshot"
    assert run_snapshot["schema_version"] == "policyos.runtime.run_detail_snapshot.v1"
    assert run_snapshot["run_id"] == runtime_api_env["core_run_id"]


def test_runs_sse_emission_rejects_marker_complete_malformed_payload() -> None:
    class _ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    now = datetime.now(UTC)

    async def _emit() -> None:
        stream = runs_routes._stream_payloads(
            lambda: {
                "contract_id": "policyos.runtime.runs_list_snapshot",
                "schema_version": "policyos.runtime.runs_list_snapshot.v1",
                "cursor": now,
                "generated_at": now,
                "page": {"count": 0, "total": 0, "next_cursor": None},
                "status_counts": {},
                "runs": "present-but-not-a-run-list",
            },
            _ConnectedRequest(),
            policy=runs_routes.LiveStreamPolicy(
                min_interval_seconds=0.01,
                max_interval_seconds=0.01,
                keepalive_seconds=10.0,
                max_duration_seconds=1.0,
            ),
        )
        with pytest.raises(ValidationError):
            await anext(stream)
        await stream.aclose()

    asyncio.run(_emit())


def test_runs_sse_timeout_emits_a_versioned_strict_contract() -> None:
    class _ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    async def _emit_timeout() -> dict[str, Any]:
        stream = runs_routes._stream_payloads(
            lambda: pytest.fail("the snapshot builder must not run after timeout"),
            _ConnectedRequest(),
            policy=runs_routes.LiveStreamPolicy(
                min_interval_seconds=0.01,
                max_interval_seconds=0.01,
                keepalive_seconds=10.0,
                max_duration_seconds=0.0,
            ),
        )
        event_block = await anext(stream)
        await stream.aclose()
        assert "event: stream.timeout" in event_block
        data_line = next(
            line for line in event_block.splitlines() if line.startswith("data: ")
        )
        payload = json.loads(data_line.removeprefix("data: "))
        assert isinstance(payload, dict)
        return payload

    payload = asyncio.run(_emit_timeout())

    assert payload["contract_id"] == "policyos.runtime.runs_stream_timeout"
    assert payload["schema_version"] == "policyos.runtime.runs_stream_timeout.v1"
    assert payload["reason"] == "stream_timeout_budget_exhausted"
    assert payload["cursor"] == payload["generated_at"]


def test_runs_sse_final_encoder_rejects_malformed_timeout_data() -> None:
    encoder = getattr(runs_routes, "_encode_validated_runs_sse", None)
    assert callable(encoder), "runs data events require one final validated encoder"

    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        encoder(
            {
                "contract_id": "policyos.runtime.runs_stream_timeout",
                "schema_version": "policyos.runtime.runs_stream_timeout.v1",
                "cursor": now,
                "generated_at": now,
                "reason": "stream_timeout_budget_exhausted",
                "uncontracted": "must-fail-closed",
            },
            event="stream.timeout",
        )


def test_runs_sse_snapshot_and_timeout_share_final_data_encoder(monkeypatch) -> None:
    class _ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    now = datetime.now(UTC)
    snapshot = {
        "contract_id": "policyos.runtime.runs_list_snapshot",
        "schema_version": "policyos.runtime.runs_list_snapshot.v1",
        "cursor": now,
        "generated_at": now,
        "page": {"count": 0, "total": 0, "next_cursor": None},
        "status_counts": {},
        "runs": [],
    }
    monotonic_values = iter((0.0, 0.0, 0.0, 0.0, 2.0))
    monkeypatch.setattr(runs_routes, "monotonic", lambda: next(monotonic_values))

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(runs_routes.asyncio, "sleep", _no_sleep)
    calls: list[str] = []

    def _recording_encoder(
        payload: object,
        *,
        event: str,
        event_id: str | None = None,
    ) -> str:
        calls.append(event)
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        assert isinstance(payload, dict)
        return runs_routes._encode_sse(payload, event=event, event_id=event_id)

    monkeypatch.setattr(
        runs_routes,
        "_encode_validated_runs_sse",
        _recording_encoder,
        raising=False,
    )

    async def _emit() -> list[str]:
        stream = runs_routes._stream_payloads(
            lambda: snapshot,
            _ConnectedRequest(),
            policy=runs_routes.LiveStreamPolicy(
                min_interval_seconds=0.01,
                max_interval_seconds=0.01,
                keepalive_seconds=10.0,
                max_duration_seconds=1.0,
            ),
        )
        events = [await anext(stream), await anext(stream)]
        await stream.aclose()
        return events

    events = asyncio.run(_emit())

    assert "event: snapshot" in events[0]
    assert events[1].splitlines()[0] == "event: stream.timeout"
    assert calls == ["snapshot", "stream.timeout"]


def test_runs_sse_keepalive_comment_bypasses_data_encoder(monkeypatch) -> None:
    class _ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    now = datetime.now(UTC)
    snapshot = {
        "contract_id": "policyos.runtime.runs_list_snapshot",
        "schema_version": "policyos.runtime.runs_list_snapshot.v1",
        "cursor": now,
        "generated_at": now,
        "page": {"count": 0, "total": 0, "next_cursor": None},
        "status_counts": {},
        "runs": [],
    }
    monotonic_values = iter((0.0, 0.0, 0.0, 0.0, 0.1, 0.1, 0.1))
    monkeypatch.setattr(runs_routes, "monotonic", lambda: next(monotonic_values))

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(runs_routes.asyncio, "sleep", _no_sleep)
    calls: list[str] = []

    def _recording_encoder(
        payload: object,
        *,
        event: str,
        event_id: str | None = None,
    ) -> str:
        calls.append(event)
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        assert isinstance(payload, dict)
        return runs_routes._encode_sse(payload, event=event, event_id=event_id)

    monkeypatch.setattr(
        runs_routes,
        "_encode_validated_runs_sse",
        _recording_encoder,
        raising=False,
    )

    async def _emit() -> list[str]:
        stream = runs_routes._stream_payloads(
            lambda: snapshot,
            _ConnectedRequest(),
            policy=runs_routes.LiveStreamPolicy(
                min_interval_seconds=0.01,
                max_interval_seconds=0.01,
                keepalive_seconds=0.05,
                max_duration_seconds=10.0,
            ),
        )
        events = [await anext(stream), await anext(stream)]
        await stream.aclose()
        return events

    events = asyncio.run(_emit())

    assert events[1] == ": keep-alive\n\n"
    assert calls == ["snapshot"]


def test_list_runs_returns_only_core_sources(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/runs?limit=20")
    assert response.status_code == 200

    payload = response.json()
    run_ids = {item["run_id"] for item in payload["runs"]}
    assert runtime_api_env["core_run_id"] in run_ids
    assert runtime_api_env["core_run_id_secondary"] in run_ids

    by_id = {item["run_id"]: item for item in payload["runs"]}
    assert by_id[runtime_api_env["core_run_id"]]["source_kind"] == "core_run"
    assert by_id[runtime_api_env["core_run_id"]]["execution_profile"] == "governed"
    assert by_id[runtime_api_env["core_run_id"]]["control_job_id"] == "job_ctrl_fixture_001"
    assert by_id[runtime_api_env["core_run_id_secondary"]]["source_kind"] == "core_run"


def test_get_run_details_returns_normalized_payload(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    core = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")
    assert core.status_code == 200
    core_payload = core.json()["run"]
    assert core_payload["source_kind"] == "core_run"
    assert core_payload["has_workflow_report"] is True
    assert core_payload["tenant_id"] == runtime_api_env["tenant_a"]
    assert core_payload["execution_profile"] == "governed"
    assert core_payload["control_job_id"] == "job_ctrl_fixture_001"
    assert (
        core_payload["capability_manifest_ref"]["artifact_id"]
        == runtime_api_env["capability_manifest_artifact_id"]
    )

    secondary = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id_secondary']}")
    assert secondary.status_code == 200
    secondary_payload = secondary.json()["run"]
    assert secondary_payload["source_kind"] == "core_run"
    assert secondary_payload["tenant_id"] == runtime_api_env["tenant_a"]
    assert secondary_payload["execution_profile"] is None


def test_list_runs_cursor_pagination(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    first_page = client.get("/api/v1/runs?limit=1")
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["page"]["count"] == 1
    next_cursor = first_payload["page"]["next_cursor"]
    assert isinstance(next_cursor, str)

    second_page = client.get(f"/api/v1/runs?limit=1&cursor={next_cursor}")
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["page"]["count"] == 1


def test_list_runs_applies_server_side_query_filter_before_pagination(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    target_query = runtime_api_env["core_run_id"].lower()
    response = client.get(f"/api/v1/runs?limit=20&q={target_query}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["page"]["total"] == 1
    assert payload["page"]["count"] == 1
    assert [item["run_id"] for item in payload["runs"]] == [runtime_api_env["core_run_id"]]


def test_evaluate_feedback_endpoint_persists_monitoring_report(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.post(
        f"/api/v1/control/runs/{runtime_api_env['core_run_id']}/feedback/evaluate"
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["action"] == "evaluate_feedback"
    assert payload["monitoring_report_ref"] is not None
    assert payload["compare_report_ref"] is not None
    assert payload["reissue_plan_ref"] is not None


def test_reissue_endpoint_fails_closed_without_durable_control_plane(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.post(f"/api/v1/control/runs/{runtime_api_env['core_run_id']}/reissue")
    assert response.status_code == 422

    payload = response.json()
    assert payload["code"] == "durable_worker_required"
