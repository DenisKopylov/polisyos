from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

import polisyos.runtime.http.routes.artifacts as artifact_routes
from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.services.artifact_inspector import ArtifactInspectorService
from polisyos.runtime.http.services.bureaucratic_rendering import BureaucraticRenderingService
from polisyos.runtime.http.services.temporal import (
    build_time_source_consistency_audit_projection,
)

FIXTURE_SECRET = "sk-routefixture1234567890"  # noqa: S105
FIXTURE_EMAIL = "policy.fixture@example.org"
FIXTURE_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FIXTURE_CELL_ID = "cell-a"


def test_raw_and_manifest_artifact_surfaces_block_secret_pii(tmp_path) -> None:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root, tenant_id=FIXTURE_TENANT_ID, cell_id=FIXTURE_CELL_ID)
    clean_ref = store.put_json(
        {**_authority_payload(), "fixture": "clean-public-route"},
        PutOptions(
            kind="surface.clean_payload",
            media_type="application/json",
            schema=SchemaInfo(name="surface.clean_payload", version="1.0"),
        ),
    )
    raw_secret_ref = store.put_json(
        {**_authority_payload(), "fixture": "raw-secret", "api_key": FIXTURE_SECRET},
        PutOptions(
            kind="surface.raw_secret_payload",
            media_type="application/json",
            schema=SchemaInfo(name="surface.raw_secret_payload", version="1.0"),
        ),
    )
    manifest_secret_ref = store.put_json(
        {**_authority_payload(), "fixture": "manifest-secret"},
        PutOptions(
            kind="surface.manifest_secret_payload",
            media_type="application/json",
            schema=SchemaInfo(name="surface.manifest_secret_payload", version="1.0"),
            producer=ProducerInfo(component=FIXTURE_EMAIL, version="1.0"),
        ),
    )
    for artifact_ref in (clean_ref, raw_secret_ref, manifest_secret_ref):
        _assert_selected_view_is_owned(store, artifact_ref)

    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )

    with TestClient(app, raise_server_exceptions=True) as client:
        clean = client.get(f"/api/v1/artifacts/{clean_ref.artifact_id}/content")
        raw = client.get(
            f"/api/v1/artifacts/{raw_secret_ref.artifact_id}/content",
            headers={"Accept": "application/octet-stream"},
        )
        download = client.get(
            f"/api/v1/artifacts/{raw_secret_ref.artifact_id}/download",
            headers={"Accept": "application/octet-stream"},
        )
        manifest = client.get(f"/api/v1/artifacts/{manifest_secret_ref.artifact_id}")

    assert clean.status_code == 200
    assert raw.status_code == 409
    assert download.status_code == 409
    assert manifest.status_code == 409
    assert FIXTURE_SECRET not in raw.text
    assert FIXTURE_SECRET not in download.text
    assert FIXTURE_EMAIL not in manifest.text


def test_composed_gate_blocks_declared_inconsistent_time_source_on_raw_and_export(
    tmp_path,
) -> None:
    base = datetime(2026, 6, 16, 12, 5, 11, tzinfo=UTC)
    projection = build_time_source_consistency_audit_projection(
        catalog_watermark=base,
        source_observed_at=base + timedelta(days=1),
        source_published_at=base,
        source_updated_at=base,
        ingested_at=base,
        effective_time=base,
        legal_valid_time=base,
        transaction_time=base,
        as_of_time=base,
        replay_time=base,
        run_started_at=base,
        run_finished_at=base + timedelta(seconds=5),
        node_started_at=base,
        node_finished_at=base + timedelta(seconds=1),
        retention_or_expiry=base + timedelta(days=30),
    )
    assert projection.mismatch_disposition == "inconsistent"
    ref, app = _app_with_surface_payload(
        tmp_path,
        {
            **_authority_payload(),
            "fixture": "stale-watermark-bypass",
            "time_source_projection": projection.model_dump(mode="json"),
        },
    )

    with TestClient(app, raise_server_exceptions=True) as client:
        raw = client.get(
            f"/api/v1/artifacts/{ref}/content",
            headers={"Accept": "application/octet-stream"},
        )
        export = client.get(f"/api/v1/artifacts/{ref}/export")

    assert raw.status_code == 409
    assert export.status_code == 409


def test_composed_gate_blocks_s12_deref_bypass_on_raw_and_export(tmp_path) -> None:
    ref, app = _app_with_surface_payload(
        tmp_path,
        {
            **_authority_payload(),
            "fixture": "s12-authorial-bypass",
            "s12_ref_dereference": {
                "authorial_negative_fixture": {
                    "candidate_only_s12_refs": ["voi://ua-msme/layer3-g5"],
                    "issue_codes": ["s12_ref_non_dereferenceable"],
                    "status": "fail",
                }
            },
        },
    )

    with TestClient(app, raise_server_exceptions=True) as client:
        raw = client.get(
            f"/api/v1/artifacts/{ref}/content",
            headers={"Accept": "application/octet-stream"},
        )
        export = client.get(f"/api/v1/artifacts/{ref}/export")

    assert raw.status_code == 409
    assert export.status_code == 409


def test_default_owner_only_is_not_a_selected_profile_grant_across_surfaces(
    tmp_path,
    monkeypatch,
) -> None:
    cas_root = tmp_path / ".polisyos"
    writer = FileSystemCAS(cas_root)
    payload_marker = "selected-profile-boundary-marker"
    ref = writer.put_json(
        {"fixture": "legacy-default-owner-only", "payload_marker": payload_marker},
        PutOptions(
            kind="surface.legacy_default_owner_only",
            media_type="application/json",
            schema=SchemaInfo(name="surface.legacy_default_owner_only", version="1.0"),
        ),
    )
    writer.record_artifact_owner(
        ref.artifact_id,
        tenant_id=FIXTURE_TENANT_ID,
        cell_id=FIXTURE_CELL_ID,
        writer="artifact-surface-safety-test-legacy-owner",
    )
    scoped_reader = FileSystemCAS(cas_root, tenant_id=FIXTURE_TENANT_ID, cell_id=FIXTURE_CELL_ID)
    default_manifest = scoped_reader.get_manifest(ref.artifact_id)
    selected_profile = artifact_manifest_profile_sha256(default_manifest)
    with pytest.raises(ArtifactOwnershipError):
        scoped_reader.get_manifest_by_profile(ref.artifact_id, selected_profile)

    payload_reads = _track_payload_reads(monkeypatch, ref.artifact_id)
    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    base = f"/api/v1/artifacts/{ref.artifact_id}"
    selected = f"?manifest_profile_sha256={selected_profile}"
    unknown_profile = "sha256:" + "0" * 64
    assert unknown_profile != selected_profile
    with TestClient(app, raise_server_exceptions=False) as client:
        requests = (
            ("manifest-default", base, None),
            ("manifest-selected-without-view-owner", base + selected, None),
            (
                "manifest-unknown-profile",
                base + f"?manifest_profile_sha256={unknown_profile}",
                None,
            ),
            (
                "content-raw-default",
                base + "/content",
                {"Accept": "application/octet-stream"},
            ),
            (
                "content-raw-selected-without-view-owner",
                base + "/content" + selected,
                {"Accept": "application/octet-stream"},
            ),
            ("content-preview-default", base + "/content", None),
            (
                "content-preview-selected-without-view-owner",
                base + "/content" + selected,
                None,
            ),
            ("schema-default", base + "/schema", None),
            ("schema-selected-without-view-owner", base + "/schema" + selected, None),
            ("lineage-default", base + "/lineage", None),
            (
                "download-default",
                base + "/download",
                {"Accept": "application/octet-stream"},
            ),
            (
                "download-selected-without-view-owner",
                base + "/download" + selected,
                {"Accept": "application/octet-stream"},
            ),
            ("export-default", base + "/export", None),
            ("export-selected-without-view-owner", base + "/export" + selected, None),
        )
        responses = [
            (name, client.get(url, headers=headers) if headers else client.get(url))
            for name, url, headers in requests
        ]

    for name, response in responses:
        assert response.status_code == 404, (name, response.status_code, response.text)
        assert response.json()["code"] == "artifact_manifest_profile_not_found", name
        assert payload_marker not in response.text, name
    assert payload_reads == []


def test_exact_profile_owner_can_read_selected_manifest_and_content_surfaces(
    tmp_path,
) -> None:
    cas_root = tmp_path / ".polisyos"
    marker = "exact-profile-owner-positive"
    payload = {
        **_authority_payload(),
        "fixture": "exact-profile-owner",
        "payload_marker": marker,
    }
    writer = FileSystemCAS(cas_root, tenant_id=FIXTURE_TENANT_ID, cell_id=FIXTURE_CELL_ID)
    ref = writer.put_json(
        payload,
        PutOptions(
            kind="surface.exact_profile_owner",
            media_type="application/json",
            schema=SchemaInfo(name="surface.exact_profile_owner", version="1.0"),
        ),
        canon_spec=CanonSpec(max_depth=96),
        return_selected_profile=True,
    )
    _assert_selected_view_is_owned(writer, ref)
    selected_profile = artifact_manifest_profile_sha256(writer.get_manifest(ref))
    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    base = f"/api/v1/artifacts/{ref.artifact_id}"
    params = {"manifest_profile_sha256": selected_profile}
    with TestClient(app, raise_server_exceptions=False) as client:
        manifest = client.get(base, params=params)
        raw_content = client.get(
            f"{base}/content",
            params=params,
            headers={"Accept": "application/octet-stream"},
        )
        semantic_content = client.get(f"{base}/content", params=params)
        schema = client.get(f"{base}/schema", params=params)
        download = client.get(
            f"{base}/download",
            params=params,
            headers={"Accept": "application/octet-stream"},
        )

    assert manifest.status_code == 200, manifest.text
    assert raw_content.status_code == 200, raw_content.text
    assert semantic_content.status_code == 200, semantic_content.text
    assert schema.status_code == 200, schema.text
    assert download.status_code == 200, download.text
    assert marker.encode() in raw_content.content
    assert marker in semantic_content.text
    assert marker.encode() in download.content
    assert manifest.json()["artifact"]["manifest_profile_sha256"] == selected_profile
    assert download.headers["Content-Disposition"].startswith("attachment;")


def test_malformed_present_profile_refuses_before_artifact_payload_reads(
    tmp_path,
    monkeypatch,
) -> None:
    cas_root = tmp_path / ".polisyos"
    marker = "malformed-present-profile-payload"
    writer = FileSystemCAS(cas_root, tenant_id=FIXTURE_TENANT_ID, cell_id=FIXTURE_CELL_ID)
    ref = writer.put_json(
        {
            **_authority_payload(),
            "fixture": "malformed-present-profile",
            "payload_marker": marker,
        },
        PutOptions(
            kind="surface.malformed_present_profile",
            media_type="application/json",
            schema=SchemaInfo(name="surface.malformed_present_profile", version="1.0"),
        ),
    )
    manifest_path = writer._manifest_path_for_ref(ref.artifact_id, None)
    manifest_bytes = json.loads(manifest_path.read_text())
    manifest_bytes["canon"]["unexpected_profile_field"] = "present-and-invalid"
    manifest_path.write_text(json.dumps(manifest_bytes))
    payload_reads = _track_payload_reads(monkeypatch, ref.artifact_id)
    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        content = client.get(
            f"/api/v1/artifacts/{ref.artifact_id}/content",
            headers={"Accept": "application/octet-stream"},
        )
        download = client.get(
            f"/api/v1/artifacts/{ref.artifact_id}/download",
            headers={"Accept": "application/octet-stream"},
        )

    for response in (content, download):
        assert response.status_code == 409, response.text
        assert response.json()["code"].startswith("canon_profile_")
        assert marker not in response.text
    assert payload_reads == []


def test_default_route_hides_an_exact_view_owned_by_another_tenant(tmp_path) -> None:
    cas_root = tmp_path / ".polisyos"
    foreign_tenant_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    foreign_cell_id = "cell-foreign"
    foreign_store = FileSystemCAS(cas_root, tenant_id=foreign_tenant_id, cell_id=foreign_cell_id)
    payload_marker = "foreign-selected-profile-marker"
    ref = foreign_store.put_json(
        {"fixture": "foreign-profile-owner", "payload_marker": payload_marker},
        PutOptions(
            kind="surface.foreign_profile_owner",
            media_type="application/json",
            schema=SchemaInfo(name="surface.foreign_profile_owner", version="1.0"),
        ),
    )
    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    with TestClient(app, raise_server_exceptions=True) as client:
        responses = (
            client.get(
                f"/api/v1/artifacts/{ref.artifact_id}/content",
                headers={"Accept": "application/octet-stream"},
            ),
            client.get(
                f"/api/v1/artifacts/{ref.artifact_id}/download",
                headers={"Accept": "application/octet-stream"},
            ),
            client.get(f"/api/v1/artifacts/{ref.artifact_id}/export"),
        )
    for response in responses:
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "artifact_manifest_profile_not_found"
        assert payload_marker not in response.text
        assert foreign_tenant_id not in response.text


def test_default_route_keeps_missing_blob_distinct_from_missing_profile(
    tmp_path,
) -> None:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root, tenant_id=FIXTURE_TENANT_ID, cell_id=FIXTURE_CELL_ID)
    ref = store.put_json(
        {"fixture": "missing-blob", "value": 1},
        PutOptions(
            kind="surface.missing_blob",
            media_type="application/json",
            schema=SchemaInfo(name="surface.missing_blob", version="1.0"),
        ),
    )
    blob_paths = list((cas_root / "artifacts" / "sha256").glob("*/*/*.blob"))
    assert len(blob_paths) == 1
    blob_path = blob_paths[0]
    original_blob_bytes = blob_path.read_bytes()
    quarantine = tmp_path / "fixture-quarantine"
    quarantine.mkdir()
    quarantined_blob = quarantine / blob_path.name
    blob_path.replace(quarantined_blob)
    assert not blob_path.exists()
    assert quarantined_blob.read_bytes() == original_blob_bytes

    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(f"/api/v1/artifacts/{ref.artifact_id}/content")
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "artifact_not_found", response.text
    assert quarantined_blob.read_bytes() == original_blob_bytes


def _app_with_surface_payload(
    tmp_path,
    payload: dict[str, object],
) -> tuple[str, object]:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root, tenant_id=FIXTURE_TENANT_ID, cell_id=FIXTURE_CELL_ID)
    ref = store.put_json(
        payload,
        PutOptions(
            kind="surface.composed_admission_payload",
            media_type="application/json",
            schema=SchemaInfo(name="surface.composed_admission_payload", version="1.0"),
        ),
    )
    _assert_selected_view_is_owned(store, ref)
    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    return str(ref.artifact_id), app


def test_lineage_routes_block_clean_no_authority(tmp_path) -> None:
    # Regression: the composed gate must be the single chokepoint. A clean
    # no-authority artifact previously reached /api/v1/lineage/... at 200; it
    # must now fail closed (block) like the raw artifact routes.
    artifact_id, app = _app_with_surface_payload(
        tmp_path, {"fixture": "clean-no-authority", "value": 1}
    )
    lineage_id = f"artifact:{artifact_id}"
    with TestClient(app, raise_server_exceptions=False) as client:
        get = client.get(f"/api/v1/lineage/{lineage_id}")
        openlineage = client.get(f"/api/v1/lineage/{lineage_id}/export/openlineage")
        prov = client.get(f"/api/v1/lineage/{lineage_id}/export/prov")
    assert get.status_code == 409
    assert openlineage.status_code == 409
    assert prov.status_code == 409


def _track_payload_reads(monkeypatch, artifact_id):
    """Record payload reads for one fixture object without changing its behavior."""
    reads = []
    original_get_bytes = FileSystemCAS.get_bytes

    def tracked_get_bytes(store, selector):
        selected_id = getattr(selector, "artifact_id", selector)
        if str(selected_id) == str(artifact_id):
            reads.append(selector)
        return original_get_bytes(store, selector)

    monkeypatch.setattr(FileSystemCAS, "get_bytes", tracked_get_bytes)
    return reads


def _assert_selected_view_is_owned(store: FileSystemCAS, ref: ArtifactRef) -> None:
    """Prove the fixture writer owns the exact profile selected by HTTP readers."""
    manifest = store.get_manifest(ref)
    selected = store.get_manifest_by_profile(
        ref.artifact_id,
        artifact_manifest_profile_sha256(manifest),
    )
    assert selected == manifest


def _authority_payload() -> dict[str, object]:
    return {
        "authority_result": "authority",
        "legacy_path_disposition": "authority_path",
        "authority_boundary": {
            "boundary_id": "boundary://runtime-quality/test",
            "source_authority": "runtime_quality",
            "posture": "authority",
            "authoritative_for": [
                "runtime_closeout_authority",
                "publication",
                "dashboard_display",
            ],
            "may_not_use_for": ["scorecard_authority"],
            "rule_version_refs": ["rule://runtime-quality/test"],
        },
    }


def _track_bounded_manifest_reads(monkeypatch):
    """Record real bounded Core manifest read attempts and outcomes for route requests."""
    reads: list[tuple[str, str | None, int | None, bool]] = []
    original_read = artifact_routes.read_core_manifest_profile_bounded

    def tracked_read(store, *args, **kwargs):
        artifact_id = args[0] if args else kwargs.get("artifact_id")
        read_index = len(reads)
        reads.append(
            (
                str(artifact_id),
                kwargs.get("manifest_profile_sha256"),
                kwargs.get("max_manifest_bytes"),
                False,
            )
        )
        result = original_read(store, *args, **kwargs)
        reads[read_index] = (*reads[read_index][:3], True)
        return result

    monkeypatch.setattr(artifact_routes, "read_core_manifest_profile_bounded", tracked_read)
    return reads


def _track_route_surface_calls(monkeypatch, artifact_id: str) -> list[str]:
    """Record actual route projection calls for one artifact without replacing behavior."""
    calls: list[str] = []
    methods = (
        (ArtifactInspectorService, "get_manifest_view"),
        (ArtifactInspectorService, "get_predictive_coverage_diagnostic"),
        (ArtifactInspectorService, "get_content_preview"),
        (ArtifactInspectorService, "get_lineage_view"),
        (ArtifactInspectorService, "get_schema_view"),
        (BureaucraticRenderingService, "render_document"),
        (BureaucraticRenderingService, "export_document"),
    )
    for service_type, method_name in methods:
        original_method = getattr(service_type, method_name)

        def tracked_method(
            service,
            *args,
            _method_name=method_name,
            _original_method=original_method,
            **kwargs,
        ):
            selected_id = args[0] if args else kwargs.get("artifact_id")
            if str(selected_id) == artifact_id:
                calls.append(_method_name)
            return _original_method(service, *args, **kwargs)

        monkeypatch.setattr(service_type, method_name, tracked_method)
    return calls


def _artifact_route_request_cases(artifact_id: str, selected_profile: str | None):
    """Build real HTTP requests for the complete registered artifact route family."""
    root = "/api/v1/artifacts"
    base = f"{root}/{artifact_id}"
    params = {"manifest_profile_sha256": selected_profile} if selected_profile is not None else {}
    render_body = {"genre": "analitichna_zapyska"}
    if selected_profile is not None:
        render_body["manifest_profile_sha256"] = selected_profile

    return {
        ("POST", f"{root}/batch"): lambda client: client.post(
            f"{root}/batch",
            json={"artifact_ids": [artifact_id]},
        ),
        ("GET", f"{root}/{{artifact_id}}"): lambda client: client.get(base, params=params),
        ("GET", f"{root}/{{artifact_id}}/predictive-coverage-diagnostic"): lambda client: (
            client.get(f"{base}/predictive-coverage-diagnostic", params=params)
        ),
        ("GET", f"{root}/{{artifact_id}}/content"): lambda client: client.get(
            f"{base}/content",
            params=params,
            headers={"Accept": "application/octet-stream"},
        ),
        ("GET", f"{root}/{{artifact_id}}/lineage"): lambda client: client.get(
            f"{base}/lineage",
            params=params,
        ),
        ("GET", f"{root}/{{artifact_id}}/schema"): lambda client: client.get(
            f"{base}/schema",
            params=params,
        ),
        ("POST", f"{root}/{{packet_id}}/render"): lambda client: client.post(
            f"{base}/render",
            json=render_body,
        ),
        ("GET", f"{root}/{{packet_id}}/export"): lambda client: client.get(
            f"{base}/export",
            params=params,
        ),
        ("GET", f"{root}/{{artifact_id}}/download"): lambda client: client.get(
            f"{base}/download",
            params=params,
            headers={"Accept": "application/octet-stream"},
        ),
    }


def test_registered_artifact_routes_resolve_selected_views_before_payload_or_projection(
    tmp_path,
    monkeypatch,
) -> None:
    """Exercise every registered route with denied and valid owner-bound manifest views."""
    root = "/api/v1/artifacts"
    cas_root = tmp_path / ".polisyos"
    payload_marker = "route-family-unowned-selected-view-payload-sentinel"
    unscoped_writer = FileSystemCAS(cas_root)
    unowned_ref = unscoped_writer.put_json(
        {
            **_authority_payload(),
            "fixture": "default-owner-without-selected-view-owner",
            "payload_marker": payload_marker,
        },
        PutOptions(
            kind="surface.unowned_selected_route_family",
            media_type="application/json",
            schema=SchemaInfo(name="surface.unowned_selected_route_family", version="1.0"),
        ),
    )
    unscoped_writer.record_artifact_owner(
        unowned_ref.artifact_id,
        tenant_id=FIXTURE_TENANT_ID,
        cell_id=FIXTURE_CELL_ID,
        writer="artifact-route-family-default-only-owner",
    )
    scoped_reader = FileSystemCAS(
        cas_root,
        tenant_id=FIXTURE_TENANT_ID,
        cell_id=FIXTURE_CELL_ID,
    )
    default_manifest = scoped_reader.get_manifest(unowned_ref.artifact_id)
    unowned_profile = artifact_manifest_profile_sha256(default_manifest)
    with pytest.raises(ArtifactOwnershipError):
        scoped_reader.get_manifest_by_profile(unowned_ref.artifact_id, unowned_profile)

    valid_marker = "route-family-valid-exact-selected-profile"
    scoped_writer = FileSystemCAS(
        cas_root,
        tenant_id=FIXTURE_TENANT_ID,
        cell_id=FIXTURE_CELL_ID,
    )
    valid_ref = scoped_writer.put_json(
        {
            **_authority_payload(),
            "fixture": "exact-selected-view-owner",
            "payload_marker": valid_marker,
        },
        PutOptions(
            kind="surface.owned_selected_route_family",
            media_type="application/json",
            schema=SchemaInfo(name="surface.owned_selected_route_family", version="1.0"),
        ),
        canon_spec=CanonSpec(max_depth=96),
        return_selected_profile=True,
    )
    _assert_selected_view_is_owned(scoped_writer, valid_ref)
    valid_profile = artifact_manifest_profile_sha256(scoped_writer.get_manifest(valid_ref))

    denied_id = str(unowned_ref.artifact_id)
    valid_id = str(valid_ref.artifact_id)
    denied_payload_reads = _track_payload_reads(monkeypatch, denied_id)
    manifest_reads = _track_bounded_manifest_reads(monkeypatch)
    route_surface_calls = _track_route_surface_calls(monkeypatch, denied_id)
    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )
    from dataclasses import replace

    from _helpers.runtime_http import _persist_fixture_owner_run

    runtime_context = replace(
        app.state.runtime_container.runtime_api_context,
        allow_candidate_predictive_diagnostic_surface=True,
    )
    app.state.runtime_container.runtime_api_context = runtime_context
    app.state.runtime_api_ctx = runtime_context
    runtime_store = runtime_context.store
    registry_ref = runtime_store.put_json(
        {"registry": {}},
        PutOptions(
            kind="core.registry_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="core.registry_bundle", version="1.0"),
        ),
    )
    _persist_fixture_owner_run(
        runtime_store,
        (unowned_ref, valid_ref),
        runtime_api_env={"app": app, "registry_bundle_ref": registry_ref},
        tenant_id=FIXTURE_TENANT_ID,
        cell_id=FIXTURE_CELL_ID,
    )

    denied_cases = _artifact_route_request_cases(denied_id, None)
    valid_cases = _artifact_route_request_cases(valid_id, valid_profile)
    registered = {
        (method, route.path)
        for route in artifact_routes.router.routes
        if getattr(route, "methods", None) and getattr(route, "endpoint", None) is not None
        for method in route.methods
        if method in {"GET", "POST"}
    }
    assert registered == set(denied_cases)
    assert len(registered) == 9

    with TestClient(app, raise_server_exceptions=False) as client:
        denied_responses = {}
        denied_traces = {}
        for route_key, request_route in denied_cases.items():
            start = len(manifest_reads)
            denied_responses[route_key] = request_route(client)
            denied_traces[route_key] = manifest_reads[start:]

        valid_responses = {}
        valid_traces = {}
        for route_key, request_route in valid_cases.items():
            start = len(manifest_reads)
            valid_responses[route_key] = request_route(client)
            valid_traces[route_key] = manifest_reads[start:]

        batch_route_key = ("POST", f"{root}/batch")
        for route_key, response in denied_responses.items():
            body = response.json()
            if route_key == batch_route_key:
                assert response.status_code == 409, (
                    route_key,
                    response.status_code,
                    response.text,
                )
                assert body["code"] == "artifact_batch_manifest_read_usage_unavailable"
                assert body["extensions"]["consumed_source_bytes"] > 0
                assert body["extensions"]["observed_source_bytes"] is None
            else:
                assert response.status_code == 404, (
                    route_key,
                    response.status_code,
                    response.text,
                )
                assert body["code"] == "artifact_manifest_profile_not_found", route_key
            assert payload_marker not in response.text, route_key
            assert "artifacts" not in body, route_key
            trace = [read for read in denied_traces[route_key] if read[0] == denied_id]
            assert [(profile, limit, succeeded) for _, profile, limit, succeeded in trace] == [
                (None, artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES, True),
                (unowned_profile, artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES, False),
            ], (route_key, trace)

        assert denied_payload_reads == []
        assert route_surface_calls == []

        for route_key, response in valid_responses.items():
            assert response.status_code < 500, (
                route_key,
                response.status_code,
                response.text,
            )
            assert not (
                response.status_code == 404
                and response.json().get("code") == "artifact_manifest_profile_not_found"
            ), (route_key, response.text)
            trace = [read for read in valid_traces[route_key] if read[0] == valid_id]
            assert any(
                profile == valid_profile
                and limit == artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES
                and succeeded
                for _, profile, limit, succeeded in trace
            ), (route_key, trace)

        # Keep the selected-reader marker in place while simulating the forbidden order:
        # consume payload bytes immediately before the exact selected-profile read.
        content_route_key = ("GET", f"{root}/{{artifact_id}}/content")
        reads_before_reorder_probe = len(denied_payload_reads)
        manifest_reads_before_reorder_probe = len(manifest_reads)
        original_bounded_read = artifact_routes.read_core_manifest_profile_bounded

        with pytest.MonkeyPatch.context() as reorder_probe:

            def payload_before_selected_profile(store, *args, **kwargs):
                if kwargs.get("manifest_profile_sha256") == unowned_profile:
                    store.get_bytes(denied_id)
                return original_bounded_read(store, *args, **kwargs)

            reorder_probe.setattr(
                artifact_routes,
                "read_core_manifest_profile_bounded",
                payload_before_selected_profile,
            )
            reordered_response = denied_cases[content_route_key](client)

        assert reordered_response.status_code == 404, reordered_response.text
        assert reordered_response.json()["code"] == "artifact_manifest_profile_not_found"
        assert payload_marker not in reordered_response.text
        assert len(denied_payload_reads[reads_before_reorder_probe:]) == 1
        with pytest.raises(AssertionError):
            assert denied_payload_reads[reads_before_reorder_probe:] == []
        reordered_trace = [
            read
            for read in manifest_reads[manifest_reads_before_reorder_probe:]
            if read[0] == denied_id
        ]
        assert [(profile, succeeded) for _, profile, _, succeeded in reordered_trace] == [
            (None, True),
            (unowned_profile, False),
        ]


def test_batch_counts_duplicate_ids_by_actual_core_manifest_receipts(
    runtime_api_env,
    monkeypatch,
) -> None:
    client = runtime_api_env["client"]
    artifact_id = str(runtime_api_env["decision_packet_artifact_id"])
    store = FileSystemCAS(runtime_api_env["cas_root"])
    selected_profile = artifact_routes.artifact_manifest_profile_sha256(
        store.get_manifest(artifact_id)
    )
    original_read = artifact_routes.read_core_manifest_profile_bounded
    original_budget_factory = artifact_routes._new_artifact_batch_manifest_read_budget
    attempts: list[tuple[str | None, int]] = []
    budgets = []

    def capture_read(*args, **kwargs):
        profile = kwargs.get("manifest_profile_sha256")
        try:
            result = original_read(*args, **kwargs)
        except artifact_routes.CoreJsonReadBoundsRefusalError as exc:
            attempts.append((profile, exc.observed_source_bytes))
            raise
        assert type(result.observed_source_bytes) is int
        attempts.append((profile, result.observed_source_bytes))
        return result

    def capture_budget(requested_id_count: int):
        budget = original_budget_factory(requested_id_count)
        budgets.append(budget)
        return budget

    monkeypatch.setattr(artifact_routes, "read_core_manifest_profile_bounded", capture_read)
    monkeypatch.setattr(
        artifact_routes,
        "_new_artifact_batch_manifest_read_budget",
        capture_budget,
    )
    response = client.post(
        "/api/v1/artifacts/batch",
        json={"artifact_ids": [artifact_id, artifact_id]},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()["artifacts"]) == 2
    assert [profile for profile, _ in attempts] == [
        None,
        selected_profile,
        None,
        selected_profile,
    ]
    assert len(attempts) == 4
    assert all(type(actual) is int for _, actual in attempts)
    assert all(actual > 0 for _, actual in attempts)
    assert len(budgets) == 1
    assert budgets[0].requested_id_count == 2
    assert budgets[0].limit_source_bytes == (2 * 2 * artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES)
    assert budgets[0].consumed_source_bytes == sum(actual for _, actual in attempts)


def test_batch_manifest_budget_stops_at_core_actual_bytes_before_partial_response(
    runtime_api_env,
    monkeypatch,
) -> None:
    client = runtime_api_env["client"]
    artifact_id = str(runtime_api_env["decision_packet_artifact_id"])
    store = FileSystemCAS(runtime_api_env["cas_root"])
    selected_profile = artifact_routes.artifact_manifest_profile_sha256(
        store.get_manifest(artifact_id)
    )
    original_read = artifact_routes.read_core_manifest_profile_bounded
    probe_default = original_read(
        store,
        artifact_routes.ArtifactID.model_validate(artifact_id),
        max_manifest_bytes=artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES,
        allow_profile_absent=True,
    )
    probe_exact = original_read(
        store,
        artifact_routes.ArtifactID.model_validate(artifact_id),
        max_manifest_bytes=artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES,
        manifest_profile_sha256=selected_profile,
        allow_profile_absent=True,
    )
    default_source_bytes = probe_default.observed_source_bytes
    exact_source_bytes = probe_exact.observed_source_bytes
    assert type(default_source_bytes) is int and default_source_bytes > 0
    assert type(exact_source_bytes) is int and exact_source_bytes > 0
    small_limit = default_source_bytes + exact_source_bytes - 1
    assert default_source_bytes < small_limit
    attempts: list[tuple[str | None, int, int, str | None]] = []
    budgets = []
    original_budget_factory = artifact_routes._new_artifact_batch_manifest_read_budget

    def capture_read(*args, **kwargs):
        profile = kwargs.get("manifest_profile_sha256")
        cap = kwargs["max_manifest_bytes"]
        try:
            result = original_read(*args, **kwargs)
        except artifact_routes.CoreJsonReadBoundsRefusalError as exc:
            attempts.append((profile, cap, exc.observed_source_bytes, exc.limit_name))
            raise
        assert type(result.observed_source_bytes) is int
        attempts.append((profile, cap, result.observed_source_bytes, None))
        return result

    def small_budget(requested_id_count: int):
        budget = original_budget_factory(requested_id_count)
        budget.limit_source_bytes = small_limit
        budgets.append(budget)
        return budget

    monkeypatch.setattr(artifact_routes, "read_core_manifest_profile_bounded", capture_read)
    monkeypatch.setattr(
        artifact_routes,
        "_new_artifact_batch_manifest_read_budget",
        small_budget,
    )
    response = client.post(
        "/api/v1/artifacts/batch",
        json={"artifact_ids": [artifact_id]},
    )

    assert response.status_code == 409, response.text
    body = response.json()
    assert body["code"] == "artifact_batch_manifest_read_budget_exceeded"
    assert len(attempts) == 2
    assert attempts[0] == (
        None,
        min(artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES, small_limit),
        default_source_bytes,
        None,
    )
    assert attempts[1][0] == selected_profile
    assert attempts[1][1] == small_limit - default_source_bytes
    assert type(attempts[1][2]) is int
    assert attempts[1][2] <= attempts[1][1]
    assert attempts[1][3] == "max_manifest_bytes"
    assert len(budgets) == 1
    assert budgets[0].consumed_source_bytes == sum(actual for _, _, actual, _ in attempts)
    assert budgets[0].consumed_source_bytes <= small_limit
    assert body["extensions"]["consumed_source_bytes"] == budgets[0].consumed_source_bytes
    assert "artifacts" not in body


def test_batch_has_an_independent_per_manifest_cap_before_payload_or_view_emission(
    runtime_api_env,
    monkeypatch,
) -> None:
    client = runtime_api_env["client"]
    artifact_id = str(runtime_api_env["decision_packet_artifact_id"])
    unscoped_store = FileSystemCAS(runtime_api_env["cas_root"])
    parsed_id = artifact_routes.ArtifactID.model_validate(artifact_id)
    manifest_path = unscoped_store._manifest_path_for_ref(parsed_id, None)
    original_bytes = manifest_path.read_bytes()
    cap = len(original_bytes)
    manifest_path.write_bytes(original_bytes + (b" " * 64))
    surface_checks = []
    original_surface_check = artifact_routes._ensure_surface_admission_allowed

    def capture_surface_check(*args, **kwargs):
        surface_checks.append(kwargs.get("artifact_ref_or_route"))
        return original_surface_check(*args, **kwargs)

    monkeypatch.setattr(
        artifact_routes,
        "_ensure_surface_admission_allowed",
        capture_surface_check,
    )
    attempts = []
    original_read = artifact_routes.read_core_manifest_profile_bounded

    def capture_read(*args, **kwargs):
        try:
            return original_read(*args, **kwargs)
        except artifact_routes.CoreJsonReadBoundsRefusalError as exc:
            attempts.append(
                (
                    exc.limit_name,
                    exc.max_manifest_bytes,
                    exc.observed_source_bytes,
                    exc.observed_manifest_bytes,
                )
            )
            raise

    monkeypatch.setattr(artifact_routes, "INSPECTOR_MANIFEST_MAX_BYTES", cap)
    monkeypatch.setattr(artifact_routes, "read_core_manifest_profile_bounded", capture_read)
    response = client.post(
        "/api/v1/artifacts/batch",
        json={"artifact_ids": [artifact_id]},
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "canon_profile_bounded_manifest_bytes_exceeded"
    assert attempts == [("max_manifest_bytes", cap, 0, cap + 64)]
    assert surface_checks == []
    assert "artifacts" not in response.json()


def test_batch_refuses_default_only_owner_without_exact_view_grant(
    runtime_api_env,
    monkeypatch,
) -> None:
    from _helpers.runtime_http import _persist_fixture_owner_run

    client = runtime_api_env["client"]
    runtime_context = runtime_api_env["app"].state.runtime_api_ctx
    store = runtime_context.store
    cas_root = runtime_api_env["cas_root"]
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    payload_marker = "batch-default-owner-only-payload"
    ref = store.put_json(
        {"fixture": "batch-default-owner-only", "payload_marker": payload_marker},
        PutOptions(
            kind="fixture.batch_owner_only",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.batch_owner_only", version="1.0"),
        ),
    )
    store.record_artifact_owner(
        ref.artifact_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        writer="artifact-batch-surface-test-default-owner",
    )
    _persist_fixture_owner_run(
        store,
        (ref,),
        runtime_api_env=runtime_api_env,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    scoped_reader = FileSystemCAS(
        cas_root,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    selected_default = scoped_reader.get_manifest(ref.artifact_id)
    selected_profile = artifact_routes.artifact_manifest_profile_sha256(selected_default)
    with pytest.raises(ArtifactOwnershipError):
        scoped_reader.get_manifest_by_profile(ref.artifact_id, selected_profile)

    bounded_profiles = []
    original_bounded_read = artifact_routes.read_core_manifest_profile_bounded
    original_surface_check = artifact_routes._ensure_surface_admission_allowed
    surface_checks = []

    def capture_bounded_read(*args, **kwargs):
        bounded_profiles.append(kwargs.get("manifest_profile_sha256"))
        return original_bounded_read(*args, **kwargs)

    def capture_surface_check(*args, **kwargs):
        surface_checks.append(kwargs.get("artifact_ref_or_route"))
        return original_surface_check(*args, **kwargs)

    monkeypatch.setattr(
        artifact_routes,
        "read_core_manifest_profile_bounded",
        capture_bounded_read,
    )
    monkeypatch.setattr(
        artifact_routes,
        "_ensure_surface_admission_allowed",
        capture_surface_check,
    )
    response = client.post(
        "/api/v1/artifacts/batch",
        json={"artifact_ids": [str(ref.artifact_id)]},
    )

    assert response.status_code == 409, response.text
    body = response.json()
    assert body["code"] == "artifact_batch_manifest_read_usage_unavailable"
    assert body["extensions"]["consumed_source_bytes"] > 0
    assert body["extensions"]["observed_source_bytes"] is None
    assert bounded_profiles == [None, selected_profile]
    assert surface_checks == []
    assert payload_marker not in response.text
    assert "artifacts" not in body
