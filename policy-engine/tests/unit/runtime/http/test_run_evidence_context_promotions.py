from __future__ import annotations

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.security.identity import PolicyOSRole
from polisyos.ir.model_layer.queries import DataViewRequest
from polisyos.runtime.http.services.debug import _data_view_request_ref_from_snapshot
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


def _selected_profile_ref(store: FileSystemCAS, ref):
    """Bind this fixture to the manifest view selected by the CAS."""
    manifest = store.get_manifest(ref)
    return type(ref).model_validate(
        {
            **ref.model_dump(mode="python"),
            "manifest_profile_sha256": artifact_manifest_profile_sha256(manifest),
        }
    )


def _promotion_status(body: dict[str, object], promotion_id: str) -> str:
    context = body["context"]
    assert isinstance(context, dict)
    candidates = context["promotion_candidates"]
    assert isinstance(candidates, list)
    for candidate in candidates:
        assert isinstance(candidate, dict)
        if candidate.get("promotion_id") == promotion_id:
            status = candidate.get("status")
            assert isinstance(status, str)
            return status
    raise AssertionError(f"promotion candidate {promotion_id!r} not found")


def test_run_evidence_context_reflects_live_promotion_decisions(runtime_api_env) -> None:
    bearer = _fixture_bearer("live-promotion-decisions")
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
            jti="jwt-live-promotion-decisions",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    run_id = runtime_api_env["core_run_id"]
    promotion_id = runtime_api_env["promotion_candidate_id"]
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    store = FileSystemCAS(runtime_api_env["cas_root"])
    for artifact_id in (
        runtime_api_env["experiment_state_artifact_id"],
        runtime_api_env["decision_packet_artifact_id"],
        runtime_api_env["execution_plan_artifact_id"],
    ):
        store.record_artifact_owner(
            artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.runtime_http.live_promotion_decisions",
        )

    with client:
        source_candidates = (
            runtime_api_env["app"].state._control_service.list_promotion_candidates().candidates
        )
        candidate = next(
            item for item in source_candidates if item.promotion_id == promotion_id
        )
        retrieval = client.app.state._control_service._retrieval
        with retrieval._state_lock:
            retrieval._store_promotion_candidate_locked(candidate)

        response = client.get(f"/api/v1/runs/{run_id}/evidence-context", headers=headers)
        assert response.status_code == 200
        assert _promotion_status(response.json(), promotion_id) == "pending"

        approve = client.post(
            f"/api/v1/control/data/promotion/{promotion_id}/approve",
            headers={
                **headers,
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={"reason": "fixture smoke approve"},
        )
        assert approve.status_code == 200
        assert approve.json()["status"] == "approved"

        response = client.get(f"/api/v1/runs/{run_id}/evidence-context", headers=headers)
        assert response.status_code == 200
        assert _promotion_status(response.json(), promotion_id) == "approved"

        reject = client.post(
            f"/api/v1/control/data/promotion/{promotion_id}/reject",
            headers={
                **headers,
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={"reason": "fixture smoke reject"},
        )
        assert reject.status_code == 200
        assert reject.json()["status"] == "rejected"

        response = client.get(f"/api/v1/runs/{run_id}/evidence-context", headers=headers)
        assert response.status_code == 200
        assert _promotion_status(response.json(), promotion_id) == "rejected"


def test_run_evidence_context_links_fabric_trace_materialization_and_timeline(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(f"/api/v1/runs/{run_id}/evidence-context")
    assert response.status_code == 200
    context = response.json()["context"]

    fabric_ref = context["fabric_retrieval_trace_ref"]
    materialization_refs = context["materialization_refs"]
    production_context = context["production_data_evidence_context"]
    related_artifact_ids = {item["artifact_id"] for item in context["related_artifacts"]}

    assert fabric_ref["artifact_id"].startswith("sha256:")
    assert fabric_ref["artifact_id"] in related_artifact_ids
    assert materialization_refs["data_snapshot_ref"]["artifact_id"] == (
        runtime_api_env["data_snapshot_artifact_id"]
    )
    assert materialization_refs["input_bindings_ref"]["artifact_id"] == (
        runtime_api_env["input_bindings_artifact_id"]
    )
    assert production_context["fabric_retrieval_trace_ref"] == fabric_ref["artifact_id"]
    assert production_context["materialization_refs"]["quality_report_ref"] == (
        runtime_api_env["quality_artifact_id"]
    )

    timeline_response = client.get(f"/api/v1/runs/{run_id}/timeline")
    assert timeline_response.status_code == 200
    events = timeline_response.json()["timeline"]["events"]
    selection_events = [
        event
        for event in events
        if event["phase"] == "fabric.source_selection"
        and event["event"].startswith("SOURCE_SELECTION_TRACE_PERSISTED")
    ]
    assert selection_events
    selection_event = selection_events[0]
    assert "prod-msme-panel" in selection_event["event"]
    assert fabric_ref["artifact_id"] in selection_event["output_artifact_ids"]
    assert materialization_refs["data_snapshot_ref"]["artifact_id"] in (
        selection_event["input_artifact_ids"]
    )


def test_snapshot_request_resolver_requires_one_exact_selected_source_profile(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request_ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="request-profile-bound",
            view_type="table",
            metrics=["fixture.dataset"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )
    request_ref = _selected_profile_ref(store, request_ref)
    snapshot_ref = store.put_json(
        {"fixture": "snapshot"},
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                InputRef(
                    artifact_id=request_ref.artifact_id,
                    role="data_view_request_ref",
                    manifest_profile_sha256=request_ref.manifest_profile_sha256,
                )
            ],
        ),
    )

    snapshot_ref = _selected_profile_ref(store, snapshot_ref)
    resolved, warning = _data_view_request_ref_from_snapshot(store, snapshot_ref)
    assert warning is None
    assert resolved is not None
    assert resolved.artifact_id == request_ref.artifact_id
    assert resolved.manifest_profile_sha256 == request_ref.manifest_profile_sha256

    unresolved, warning = _data_view_request_ref_from_snapshot(
        store,
        snapshot_ref.model_copy(update={"manifest_profile_sha256": None}),
    )
    assert unresolved is None
    assert warning == "data_snapshot_profile_not_established"


def test_snapshot_request_resolver_refuses_wrong_profile_and_ambiguous_edge(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request_body = DataViewRequest(
        schema_version="1.0",
        request_id="same-content",
        view_type="table",
        metrics=["fixture.dataset"],
    )
    valid_request = store.put_json(
        request_body,
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )
    valid_request = _selected_profile_ref(store, valid_request)
    wrong_kind_view = store.put_json(
        request_body,
        ArtifactWriteOptions(
            kind="fixture.not_a_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )
    assert valid_request.artifact_id == wrong_kind_view.artifact_id
    assert valid_request.manifest_profile_sha256 != wrong_kind_view.manifest_profile_sha256

    wrong_kind_view = _selected_profile_ref(store, wrong_kind_view)
    wrong_selected_source = store.put_json(
        {"fixture": "snapshot"},
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                InputRef(
                    artifact_id=wrong_kind_view.artifact_id,
                    role="data_view_request_ref",
                    manifest_profile_sha256=wrong_kind_view.manifest_profile_sha256,
                )
            ],
        ),
    )
    wrong_selected_source = _selected_profile_ref(store, wrong_selected_source)
    unresolved, warning = _data_view_request_ref_from_snapshot(store, wrong_selected_source)
    assert unresolved is None
    assert warning == "data_view_request_manifest_kind_mismatch"

    ambiguous_snapshot = store.put_json(
        {"fixture": "ambiguous"},
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                InputRef(
                    artifact_id=valid_request.artifact_id,
                    role="data_view_request_ref",
                    manifest_profile_sha256=valid_request.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=valid_request.artifact_id,
                    role="data_view_request_ref",
                    manifest_profile_sha256=valid_request.manifest_profile_sha256,
                ),
            ],
        ),
    )
    ambiguous_snapshot = _selected_profile_ref(store, ambiguous_snapshot)
    unresolved, warning = _data_view_request_ref_from_snapshot(store, ambiguous_snapshot)
    assert unresolved is None
    assert warning == "data_view_request_edge_ambiguous"


def test_snapshot_request_resolver_refuses_request_profile_field_drift(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request_body = DataViewRequest(
        schema_version="1.0",
        request_id="same-bytes-different-manifest-profile",
        view_type="table",
        metrics=["fixture.dataset"],
    )
    selected_request = store.put_json(
        request_body,
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )
    selected_request = _selected_profile_ref(store, selected_request)
    other_profile_same_id = store.put_json(
        request_body,
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.1"),
        ),
    )
    assert selected_request.artifact_id == other_profile_same_id.artifact_id
    assert selected_request.manifest_profile_sha256 != other_profile_same_id.manifest_profile_sha256
    snapshot_ref = store.put_json(
        {"fixture": "snapshot"},
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                InputRef(
                    artifact_id=selected_request.artifact_id,
                    role="data_view_request_ref",
                    manifest_profile_sha256=selected_request.manifest_profile_sha256,
                )
            ],
        ),
    )

    snapshot_ref = _selected_profile_ref(store, snapshot_ref)
    resolved, warning = _data_view_request_ref_from_snapshot(
        store,
        snapshot_ref,
        expected_request_ref=other_profile_same_id,
    )
    assert resolved is None
    assert warning == "data_view_request_ref_does_not_match_snapshot_lineage"

    stale_snapshot_ref = store.put_json(
        {"fixture": "stale"},
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                InputRef(
                    artifact_id=selected_request.artifact_id,
                    role="data_view_request_ref",
                    manifest_profile_sha256=f"sha256:{'f' * 64}",
                )
            ],
        ),
    )
    stale_snapshot_ref = _selected_profile_ref(store, stale_snapshot_ref)
    resolved, warning = _data_view_request_ref_from_snapshot(store, stale_snapshot_ref)
    assert resolved is None
    assert warning == "data_view_request_profile_resolution_failed"


def test_snapshot_request_resolver_rejects_unsupported_schema_and_malformed_body(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)

    def resolve_payload(payload: object, *, schema_name: str, schema_version: str):
        request_ref = store.put_json(
            payload,
            ArtifactWriteOptions(
                kind="ir.data_view_request",
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=schema_version),
            ),
        )
        request_ref = _selected_profile_ref(store, request_ref)
        snapshot_ref = store.put_json(
            {"fixture": request_ref.artifact_id.hex},
            ArtifactWriteOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                inputs=[
                    InputRef(
                        artifact_id=request_ref.artifact_id,
                        role="data_view_request_ref",
                        manifest_profile_sha256=request_ref.manifest_profile_sha256,
                    )
                ],
            ),
        )
        snapshot_ref = _selected_profile_ref(store, snapshot_ref)
        return _data_view_request_ref_from_snapshot(store, snapshot_ref)

    wrong_schema, warning = resolve_payload(
        DataViewRequest(
            schema_version="1.0",
            request_id="wrong-schema",
            view_type="table",
            metrics=["fixture.dataset"],
        ),
        schema_name="polisyos.ir.DataViewRequest",
        schema_version="2.0",
    )
    assert wrong_schema is None
    assert warning == "data_view_request_schema_not_supported"

    malformed, warning = resolve_payload(
        {"request_id": "missing-required-data-view-fields"},
        schema_name="polisyos.ir.DataViewRequest",
        schema_version="1.0",
    )
    assert malformed is None
    assert warning == "data_view_request_payload_invalid"
