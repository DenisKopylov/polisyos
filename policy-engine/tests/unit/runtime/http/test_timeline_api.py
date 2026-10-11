from __future__ import annotations

from types import SimpleNamespace

from polisyos_tests_runtime_http_conftest import _runtime_api_request

import polisyos.runtime.http.services.lineage as lineage_module
import polisyos.runtime.http.services.timeline as timeline_module
from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_manifest_profile_sha256,
    artifact_ref_identity_key,
    resolve_manifest_by_profile,
)


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
    """Keep the sensitive core refusal and a separate safe real-graph positive."""
    client = runtime_api_env["client"]
    core_denied = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/lineage?max_depth=32&max_nodes=1000",
    )
    assert core_denied.status_code == 409
    denied_payload = core_denied.json()
    assert denied_payload["code"] == "authority_surface_admission_blocked"
    denied_decision = denied_payload["authority_surface_decision"]
    assert denied_decision["purpose"] == "runtime_closeout_authority"
    assert denied_decision["reason"] == "authority_purpose_forbidden"
    assert denied_decision["visible_downgrade"] is True
    assert any(
        contributor["basis"] == "selected_manifest"
        and contributor["authority_boundary_ref"]
        == "boundary-runtime-api-secret-lineage-refusal"
        and contributor["reason"] == "authority_purpose_forbidden"
        and contributor["visible_downgrade"]
        for contributor in denied_decision["authority_contributors"]
    )

    run_id = runtime_api_env["core_run_id_secondary"]
    response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{run_id}/lineage?max_depth=32&max_nodes=1000",
    )
    assert response.status_code == 200, response.text
    lineage = response.json()["lineage"]
    assert lineage["is_complete"] is True
    assert lineage["total_nodes"] >= 3
    assert lineage["total_edges"] >= 2
    ctx = runtime_api_env["app"].state.runtime_api_ctx
    run = ctx.run_index.get_run(run_id)
    expected_roots = list(run.details.root_artifacts)
    if not expected_roots and run.decision_packet_ref is not None:
        expected_roots = [run.decision_packet_ref]
    assert len(expected_roots) == 1
    assert expected_roots[0].manifest_profile_sha256 is not None

    expected_refs: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
    pending = list(expected_roots)
    while pending:
        selected_ref = pending.pop()
        selected_key = artifact_ref_identity_key(selected_ref)
        if selected_key in expected_refs:
            continue
        manifest = _runtime_api_request(
            runtime_api_env, ctx.store.get_manifest, selected_ref
        )
        verification = _runtime_api_request(
            runtime_api_env, ctx.store.verify, selected_ref
        )
        assert verification.ok is True
        assert selected_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            manifest
        )
        assert selected_ref.kind == manifest.kind
        assert selected_ref.media_type == manifest.media_type
        expected_refs[selected_key] = selected_ref
        for input_ref in manifest.inputs:
            profile = input_ref.manifest_profile_sha256
            assert profile is not None
            child_manifest = _runtime_api_request(
                runtime_api_env,
                resolve_manifest_by_profile,
                ctx.store,
                input_ref.artifact_id,
                profile,
            )
            pending.append(
                ArtifactRef(
                    artifact_id=input_ref.artifact_id,
                    kind=child_manifest.kind,
                    media_type=child_manifest.media_type,
                    manifest_profile_sha256=profile,
                )
            )

    actual_roots = [
        ArtifactRef.model_validate(ref) for ref in lineage["root_artifact_refs"]
    ]
    assert [artifact_ref_identity_key(ref) for ref in actual_roots] == [
        artifact_ref_identity_key(ref) for ref in expected_roots
    ]
    actual_nodes = {
        (
            node["artifact_id"],
            node["kind"],
            node["media_type"],
            node.get("manifest_profile_sha256"),
        )
        for node in lineage["nodes"]
    }
    assert actual_nodes == set(expected_refs)


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
    run = ctx.run_index.get_run(runtime_api_env["core_run_id_secondary"])
    root_artifact_refs = list(run.details.root_artifacts)
    if not root_artifact_refs and run.decision_packet_ref is not None:
        root_artifact_refs = [run.decision_packet_ref]
    assert len(root_artifact_refs) == 1
    selected_root = root_artifact_refs[0]
    assert selected_root.manifest_profile_sha256 is not None
    selected_manifest = _runtime_api_request(
        runtime_api_env, ctx.store.get_manifest, selected_root
    )
    selected_verification = _runtime_api_request(
        runtime_api_env, ctx.store.verify, selected_root
    )
    assert selected_verification.ok is True
    assert selected_root.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        selected_manifest
    )
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
        preserve_manifest_profiles,
    ):
        captured.update(
            {
                "store": store,
                "root_id": root_id,
                "max_depth": max_depth,
                "max_nodes": max_nodes,
                "verify_integrity": verify_integrity,
                "preserve_manifest_profiles": preserve_manifest_profiles,
                "timeout_seconds": timeout_seconds,
                "batch_size": batch_size,
            }
        )
        return SimpleNamespace(nodes={}, edges=(), timed_out=True, is_complete=False)

    monkeypatch.setattr(lineage_module, "resolve_dependency_graph", _fake_resolve_dependency_graph)

    view = _runtime_api_request(
        runtime_api_env,
        ctx.lineage.build_for_artifact_ids,
        root_artifact_refs,
        max_depth=5,
        max_nodes=7,
        timeout_seconds=0.25,
    )

    assert captured["store"] is ctx.store
    assert captured["root_id"] in root_artifact_refs
    assert artifact_ref_identity_key(captured["root_id"]) == artifact_ref_identity_key(
        selected_root
    )
    assert len(view.root_artifact_refs) == 1
    assert artifact_ref_identity_key(view.root_artifact_refs[0]) == artifact_ref_identity_key(
        selected_root
    )
    assert captured["max_depth"] == 5
    assert captured["max_nodes"] == 7
    assert captured["verify_integrity"] is True
    assert captured["preserve_manifest_profiles"] is True
    assert captured["timeout_seconds"] == 0.25
    assert captured["batch_size"] == 128
    assert view.is_complete is False
    assert view.total_nodes == 0


def test_run_timeline_preserves_trace_artifact_reference_identity(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/timeline")
    assert response.status_code == 200

    events = response.json()["timeline"]["events"]
    for event in events:
        assert event["input_artifact_ids"] == [
            ref["artifact_id"] for ref in event["input_artifact_refs"]
        ]
        assert event["output_artifact_ids"] == [
            ref["artifact_id"] for ref in event["output_artifact_refs"]
        ]


def test_temporal_lineage_roots_do_not_match_a_sibling_manifest_profile() -> None:
    from polisyos.core.contracts.runtime import RunTimelineEvent
    from polisyos.runtime.http.routes.runs import _filter_temporal_lineage_roots

    artifact_id = "sha256:" + "a" * 64
    selected = ArtifactRef(
        artifact_id=artifact_id,
        kind="runtime.test_payload",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "1" * 64,
    )
    sibling = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "2" * 64})
    event = RunTimelineEvent(
        index=0,
        timestamp="2026-01-01T00:00:00Z",
        phase="producer",
        event="OUTPUT",
        output_artifact_ids=[artifact_id],
        output_artifact_refs=[sibling],
    )

    roots, limited = _filter_temporal_lineage_roots([selected], [event])

    assert roots == []
    assert limited is True
