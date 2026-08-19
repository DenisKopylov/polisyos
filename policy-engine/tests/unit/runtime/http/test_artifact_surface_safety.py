from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.runtime.http.app import create_runtime_api_app

FIXTURE_SECRET = "sk-routefixture1234567890"  # noqa: S105
FIXTURE_EMAIL = "policy.fixture@example.org"
FIXTURE_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FIXTURE_CELL_ID = "cell-a"


def test_raw_and_manifest_artifact_surfaces_block_secret_pii(tmp_path) -> None:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
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
    for artifact_id in (
        clean_ref.artifact_id,
        raw_secret_ref.artifact_id,
        manifest_secret_ref.artifact_id,
    ):
        store.record_artifact_owner(
            artifact_id,
            tenant_id=FIXTURE_TENANT_ID,
            cell_id=FIXTURE_CELL_ID,
            writer="artifact-surface-safety-test",
        )

    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_response_compression=False,
        enable_security_middlewares=False,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
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
    ref, app = _app_with_surface_payload(
        tmp_path,
        {
            **_authority_payload(),
            "fixture": "stale-watermark-bypass",
            "time_source_projection": {
                "projection_kind": "time_source_consistency_audit_projection",
                "producer_ref": (
                    "polisyos.runtime.http.services.temporal."
                    "build_time_source_consistency_audit_projection"
                ),
                "projection_scope": "catalog_source_runtime_time_role_consistency",
                "mismatch_disposition": "inconsistent",
            },
        },
    )

    with TestClient(app, raise_server_exceptions=False) as client:
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

    with TestClient(app, raise_server_exceptions=False) as client:
        raw = client.get(
            f"/api/v1/artifacts/{ref}/content",
            headers={"Accept": "application/octet-stream"},
        )
        export = client.get(f"/api/v1/artifacts/{ref}/export")

    assert raw.status_code == 409
    assert export.status_code == 409


def _app_with_surface_payload(
    tmp_path,
    payload: dict[str, object],
) -> tuple[str, object]:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
    ref = store.put_json(
        payload,
        PutOptions(
            kind="surface.composed_admission_payload",
            media_type="application/json",
            schema=SchemaInfo(name="surface.composed_admission_payload", version="1.0"),
        ),
    )
    store.record_artifact_owner(
        ref.artifact_id,
        tenant_id=FIXTURE_TENANT_ID,
        cell_id=FIXTURE_CELL_ID,
        writer="artifact-surface-safety-test",
    )
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
