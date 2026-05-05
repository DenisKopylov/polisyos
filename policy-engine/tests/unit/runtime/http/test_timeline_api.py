from __future__ import annotations

from types import SimpleNamespace

import polisyos.runtime.http.services.lineage as lineage_module
import polisyos.runtime.http.services.timeline as timeline_module


def test_run_timeline_contains_ordered_events(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/timeline")
    assert response.status_code == 200

    timeline = response.json()["timeline"]
    assert timeline["summary"]["total_events"] > 0
    indices = [event["index"] for event in timeline["events"]]
    assert indices == sorted(indices)

    events = {event["event"] for event in timeline["events"]}
    assert "NODE_OK" in events
    assert "NODE_FAIL" in events


def test_run_nodes_endpoint_reads_workflow_report(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/nodes")
    assert response.status_code == 200
    payload = response.json()
    aliases = {node["alias"]: node for node in payload["nodes"]}

    assert "compile_foundry" in aliases
    assert aliases["compile_foundry"]["status"] == "ok"
    assert "run_governance" in aliases
    assert aliases["run_governance"]["status"] == "fail"
    assert aliases["run_governance"]["error_code"] == "governance.blocked"


def test_run_lineage_endpoint_returns_dependency_graph(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/lineage?max_depth=32&max_nodes=1000"
    )
    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert lineage["total_nodes"] >= 1
    assert len(lineage["root_artifact_ids"]) >= 1


def test_timeline_service_uses_trace_index_cache(monkeypatch, runtime_api_env) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run = ctx.run_index.get_run(runtime_api_env["core_run_id"])
    calls = 0
    original = timeline_module._load_trace_events

    def _counting_loader(path):
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(timeline_module, "_load_trace_events", _counting_loader)

    first = ctx.timeline.build_for_run(run)
    second = ctx.timeline.build_for_run(run)

    assert calls == 1
    assert first.timeline.events == second.timeline.events


def test_run_index_force_refresh_reuses_unchanged_records(monkeypatch, runtime_api_env) -> None:
    run_index = runtime_api_env["app"].state.runtime_api_ctx.run_index
    run_index.refresh(force=True)
    calls = 0
    original = run_index._adapt_core_run

    def _counting_adapt(run_dir):
        nonlocal calls
        calls += 1
        return original(run_dir)

    monkeypatch.setattr(run_index, "_adapt_core_run", _counting_adapt)

    run_index.refresh(force=True)

    assert calls == 0


def test_timeline_service_evicts_old_entries_when_cache_is_bounded(
    monkeypatch,
    runtime_api_env,
) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run_a = ctx.run_index.get_run(runtime_api_env["core_run_id"])
    run_b = ctx.run_index.get_run(runtime_api_env["core_run_id_secondary"])
    service = timeline_module.TimelineService(cache_max_entries=1)
    calls = 0
    original = timeline_module._load_trace_events

    def _counting_loader(path):
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(timeline_module, "_load_trace_events", _counting_loader)

    service.build_for_run(run_a)
    service.build_for_run(run_b)
    service.build_for_run(run_a)

    assert calls == 3
    assert len(service._cache) == 1


def test_lineage_service_passes_budget_limits_to_dependency_graph(
    monkeypatch,
    runtime_api_env,
) -> None:
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run = ctx.run_index.get_run(runtime_api_env["core_run_id"])
    root_artifact_ids = ctx.run_index.resolve_root_artifact_ids(run)
    captured: dict[str, object] = {}

    def _fake_resolve_dependency_graph(
        store,
        root_id,
        *,
        max_depth,
        max_nodes,
        verify_integrity,
        timeout_seconds,
        batch_size,
    ):
        captured.update(
            {
                "store": store,
                "root_id": root_id,
                "max_depth": max_depth,
                "max_nodes": max_nodes,
                "verify_integrity": verify_integrity,
                "timeout_seconds": timeout_seconds,
                "batch_size": batch_size,
            }
        )
        return SimpleNamespace(nodes={}, edges=(), timed_out=True, is_complete=False)

    monkeypatch.setattr(lineage_module, "resolve_dependency_graph", _fake_resolve_dependency_graph)

    view = ctx.lineage.build_for_artifact_ids(
        root_artifact_ids,
        max_depth=5,
        max_nodes=7,
        timeout_seconds=0.25,
    )

    assert captured["store"] is ctx.store
    assert captured["root_id"] in root_artifact_ids
    assert captured["max_depth"] == 5
    assert captured["max_nodes"] == 7
    assert captured["verify_integrity"] is True
    assert captured["timeout_seconds"] == 0.25
    assert captured["batch_size"] == 128
    assert view.is_complete is False
    assert view.total_nodes == 0
