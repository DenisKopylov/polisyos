from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import PutOptions
from polisyos.core.run.context import RunContext
from polisyos.core.run.manifest import RunManifest
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.trace import RunTerminality
from polisyos.core.trace.record import TraceRecord, TraceRefs
from polisyos.runtime.http.routes import runs as runs_routes
from polisyos.runtime.http.services.channel_contracts import RunDetailSnapshot
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


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
    assert runs_snapshot["schema_version"] == "policyos.runtime.runs_list_snapshot.v2"
    assert isinstance(runs_snapshot["runs"], list)
    assert {run["run_terminality"] for run in runs_snapshot["runs"]} == {"terminal"}

    run_snapshot = _read_first_sse_snapshot(
        client, f"/api/v1/runs/{runtime_api_env['core_run_id']}/live"
    )
    assert run_snapshot["contract_id"] == "policyos.runtime.run_detail_snapshot"
    assert run_snapshot["schema_version"] == "policyos.runtime.run_detail_snapshot.v2"
    assert run_snapshot["run_id"] == runtime_api_env["core_run_id"]
    assert run_snapshot["run_terminality"] == "terminal"


def test_runs_sse_emission_rejects_marker_complete_malformed_payload() -> None:
    class _ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    now = datetime.now(UTC)

    async def _emit() -> None:
        stream = runs_routes._stream_payloads(
            lambda: {
                "contract_id": "policyos.runtime.runs_list_snapshot",
                "schema_version": "policyos.runtime.runs_list_snapshot.v2",
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


def test_runs_sse_exit_consumes_producer_terminality_not_status_text() -> None:
    class _ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    now = datetime.now(UTC)
    snapshot = RunDetailSnapshot(
        run_id="R_novel_terminal_label",
        cursor=now,
        status="still_running_but_owner_finalized_v47",
        run_terminality=RunTerminality.TERMINAL,
        timeline_events=0,
        agent_attempts=0,
        agent_steps=0,
        governance_issues=0,
        decision_review_required=False,
        generated_at=now,
    )

    async def _emit_terminal() -> str:
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
        event = await anext(stream)
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        return event

    event = asyncio.run(_emit_terminal())

    assert "still_running_but_owner_finalized_v47" in event
    assert '"run_terminality": "terminal"' in event


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
        "schema_version": "policyos.runtime.runs_list_snapshot.v2",
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
        "schema_version": "policyos.runtime.runs_list_snapshot.v2",
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


def test_run_terminality_is_producer_owned_and_novel_status_labels_stay_opaque(
    runtime_api_env,
) -> None:
    app = runtime_api_env["app"]
    ctx = app.state.runtime_api_ctx
    store = ctx.store
    run_id = "R_terminality_novel_status"
    registry_ref = store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=run_id,
        run_dir=runtime_api_env["cas_root"] / "runs" / run_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )

    ctx.run_index.refresh(force=True)
    active = runtime_api_env["client"].get(f"/api/v1/runs?q={run_id}").json()["runs"][0]
    assert active["run_terminality"] == RunTerminality.NON_TERMINAL

    novel_status = "still_running_but_owner_finalized_v47"
    run.finalize(status=novel_status)
    ctx.run_index.refresh(force=True)
    finalized = runtime_api_env["client"].get(f"/api/v1/runs?q={run_id}").json()["runs"][0]

    assert finalized["status"] == novel_status
    assert finalized["run_terminality"] == RunTerminality.TERMINAL
    live_snapshot = runs_routes._build_run_live_payload(run_id, ctx)
    assert live_snapshot.status == novel_status
    assert live_snapshot.run_terminality is RunTerminality.TERMINAL


def test_unknown_run_terminality_cannot_be_read_as_non_terminal(runtime_api_env) -> None:
    app = runtime_api_env["app"]
    ctx = app.state.runtime_api_ctx
    store = ctx.store
    run_id = "R_legacy_terminality_absent"
    registry_ref = store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    now = datetime.now(UTC).replace(microsecond=0)
    manifest = RunManifest(
        run_id=run_id,
        registry_bundle=registry_ref,
        status="completed",
        started_at=now,
        finished_at=now,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    manifest_ref = store.put_json(
        manifest,
        PutOptions(kind="core.run_manifest", media_type="application/json"),
    )
    trace_path = runtime_api_env["cas_root"] / "runs" / run_id / "trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_records = (
        TraceRecord(run_id=run_id, phase="core", event="RUN_STARTED"),
        TraceRecord(
            run_id="R_foreign_terminal_fact",
            phase="core",
            event="RUN_FINALIZED",
            run_terminality=RunTerminality.TERMINAL,
            refs=TraceRefs(outputs=[manifest_ref]),
        ),
        TraceRecord(
            run_id=run_id,
            phase="core",
            event="RUN_FINALIZED",
            refs=TraceRefs(outputs=[manifest_ref]),
        ),
    )
    trace_path.write_text(
        "".join(f"{record.model_dump_json(exclude_none=True)}\n" for record in legacy_records),
        encoding="utf-8",
    )

    ctx.run_index.refresh(force=True)
    projected = runtime_api_env["client"].get(f"/api/v1/runs?q={run_id}").json()["runs"][0]

    assert projected["status"] == "completed"
    assert projected["finished_at"] is not None
    assert projected["run_terminality"] == RunTerminality.NOT_ESTABLISHED
    assert projected["run_terminality"] != RunTerminality.NON_TERMINAL
    assert "core_run_trace_run_id_mismatch" in projected["warnings"]


@pytest.mark.parametrize(
    ("lifecycle_record", "warning"),
    [
        (
            {"event": "RUN_FINALIZED", "run_terminality": "future_terminal_state"},
            "core_run_trace_record_invalid",
        ),
        (
            {"event": "RUN_STARTED", "run_terminality": "terminal"},
            "core_run_terminality_fact_conflict",
        ),
        (
            {
                "phase": "not_the_lifecycle_owner",
                "event": "RUN_FINALIZED",
                "run_terminality": "terminal",
            },
            "core_run_terminality_fact_conflict",
        ),
        (
            {"event": "RUN_FINALIZED"},
            "core_run_finalized_without_terminality",
        ),
    ],
)
def test_untrusted_lifecycle_transition_degrades_non_terminal_to_not_established(
    runtime_api_env,
    lifecycle_record: dict[str, str],
    warning: str,
) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run_id = "R_terminality_invalid_fact"
    registry_ref = ctx.store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    run_dir = runtime_api_env["cas_root"] / "runs" / run_id
    RunContext.start(
        store=ctx.store,
        registry_bundle=registry_ref,
        run_id=run_id,
        run_dir=run_dir,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    with (run_dir / "trace.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "run_id": run_id,
                    "phase": "core",
                    **lifecycle_record,
                }
            )
            + "\n"
        )

    ctx.run_index.refresh(force=True)
    projected = runtime_api_env["client"].get(f"/api/v1/runs?q={run_id}").json()["runs"][0]

    assert projected["run_terminality"] == RunTerminality.NOT_ESTABLISHED
    assert projected["run_terminality"] != RunTerminality.NON_TERMINAL
    assert warning in projected["warnings"]


def test_terminal_fact_is_absorbing_against_a_later_non_terminal_fact(runtime_api_env) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run_id = "R_terminality_regression"
    registry_ref = ctx.store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    run_dir = runtime_api_env["cas_root"] / "runs" / run_id
    run = RunContext.start(
        store=ctx.store,
        registry_bundle=registry_ref,
        run_id=run_id,
        run_dir=run_dir,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    run.finalize(status="completed")
    with (run_dir / "trace.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            TraceRecord(
                run_id=run_id,
                phase="core",
                event="RUN_STARTED",
                run_terminality=RunTerminality.NON_TERMINAL,
                tenant_id=runtime_api_env["tenant_a"],
                cell_id=runtime_api_env["cell_a"],
            ).model_dump_json(exclude_none=True)
            + "\n"
        )

    ctx.run_index.refresh(force=True)
    projected = runtime_api_env["client"].get(f"/api/v1/runs?q={run_id}").json()["runs"][0]

    assert projected["run_terminality"] == RunTerminality.NOT_ESTABLISHED
    assert "core_run_terminality_fact_regression" in projected["warnings"]


def test_foreign_finalize_journal_cannot_sign_or_clear_another_run(runtime_api_env) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run_id = "R_terminality_journal_owner"
    registry_ref = ctx.store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    run_dir = runtime_api_env["cas_root"] / "runs" / run_id
    RunContext.start(
        store=ctx.store,
        registry_bundle=registry_ref,
        run_id=run_id,
        run_dir=run_dir,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    foreign_manifest = RunManifest(
        run_id="R_foreign_finalize_journal",
        registry_bundle=registry_ref,
        status="completed",
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    journal_path = run_dir / ".finalize-journal.json"
    journal_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_manifest": foreign_manifest.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )

    ctx.run_index.refresh(force=True)
    projected = runtime_api_env["client"].get(f"/api/v1/runs?q={run_id}").json()["runs"][0]

    assert projected["run_terminality"] == RunTerminality.NON_TERMINAL
    assert journal_path.exists()
    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(record.event != "RUN_FINALIZED" for record in records)


def test_finalize_recovery_refuses_journal_without_owner_start(runtime_api_env) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run_id = "R_terminality_journal_without_owner"
    registry_ref = ctx.store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    run_dir = runtime_api_env["cas_root"] / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.jsonl"
    trace_path.write_text(
        TraceRecord(
            run_id=run_id,
            phase="observer",
            event="RUN_OBSERVED",
        ).model_dump_json(exclude_none=True)
        + "\n",
        encoding="utf-8",
    )
    foreign_manifest = RunManifest(
        run_id="R_foreign_journal_without_owner",
        registry_bundle=registry_ref,
        status="completed",
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    journal_path = run_dir / ".finalize-journal.json"
    journal_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_manifest": foreign_manifest.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )

    ctx.run_index.refresh(force=True)

    assert journal_path.exists()
    assert "RUN_FINALIZED" not in trace_path.read_text(encoding="utf-8")


def test_recovery_rebinds_unlinked_terminal_event_to_its_manifest(runtime_api_env) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run_id = "R_terminality_recovery_binding"
    registry_ref = ctx.store.put_json(
        {"registry": {}},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    run_dir = runtime_api_env["cas_root"] / "runs" / run_id
    run = RunContext.start(
        store=ctx.store,
        registry_bundle=registry_ref,
        run_id=run_id,
        run_dir=run_dir,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    trace_path = run_dir / "trace.jsonl"
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(
            TraceRecord(
                run_id=run_id,
                phase="core",
                event="RUN_FINALIZED",
                run_terminality=RunTerminality.TERMINAL,
            ).model_dump_json(exclude_none=True)
            + "\n"
        )
    pending_manifest = run.run_manifest.model_copy(deep=True)
    pending_manifest.status = "completed"
    pending_manifest.finished_at = datetime.now(UTC).replace(microsecond=0)
    journal_path = run_dir / ".finalize-journal.json"
    journal_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_manifest": pending_manifest.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )

    ctx.run_index.refresh(force=True)

    assert journal_path.exists() is False
    finalized = [
        record
        for record in (
            TraceRecord.model_validate_json(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
        )
        if record.phase == "core" and record.event == "RUN_FINALIZED"
    ]
    assert len(finalized) == 2
    assert finalized[0].refs.outputs == []
    assert len(finalized[1].refs.outputs) == 1
    assert finalized[1].refs.outputs[0].kind == "core.run_manifest"


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
    bearer = _fixture_bearer("reissue-inherited-control-plane")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-reissue-inherited-control-plane",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    with client:
        response = client.post(
            f"/api/v1/control/runs/{runtime_api_env['core_run_id']}/reissue",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
        )
    assert response.status_code == 422

    payload = response.json()
    assert payload["code"] == "durable_worker_required"
