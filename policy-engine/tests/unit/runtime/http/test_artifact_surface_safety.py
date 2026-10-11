from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.runtime.http.app import create_runtime_api_app
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


def test_default_owner_only_is_not_a_selected_profile_grant_across_surfaces(tmp_path) -> None:
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
    with pytest.raises(ArtifactOwnershipError):
        scoped_reader.get_manifest_by_profile(
            ref.artifact_id,
            artifact_manifest_profile_sha256(default_manifest),
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
            client.get(f"/api/v1/artifacts/{ref.artifact_id}"),
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


def test_default_route_keeps_missing_blob_distinct_from_missing_profile(tmp_path) -> None:
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
    assert response.status_code == 404
    assert response.json()["code"] == "artifact_not_found"
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
