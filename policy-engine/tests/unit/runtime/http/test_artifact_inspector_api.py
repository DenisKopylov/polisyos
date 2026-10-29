from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from _helpers.runtime_http import (
    _put_fixture_authority_envelope,
    _runtime_fixture_authority_boundary,
    build_runtime_api_env_with_fixture_catalog,
    close_runtime_api_env,
)
from polisyos_tests_runtime_http_conftest import (
    _record_fixture_owner,
    _runtime_api_request,
)
from pydantic import ValidationError

import polisyos.runtime.http.routes.artifacts as artifact_routes
from polisyos.core.artifacts import (
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    profile_bound_ref,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactRef,
    InputRef,
    ProducerInfo,
)
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.quality.authority import authority_surface_decision
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAuthoritySurfacePacket,
    EvalSafetyCertificate,
    EvalSafetyMetricsProjection,
    EvalSafetySurfaceDisposition,
    evaluation_safety_metrics_projection_identity,
)


@pytest.fixture
def runtime_api_env(
    tmp_path: Path,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[dict[str, object]]:
    """Use a complete owner-built temporary catalog for artifact-inspector requests."""
    project_root = pytestconfig.rootpath.resolve(strict=True)
    env = build_runtime_api_env_with_fixture_catalog(
        tmp_path,
        include_test_client=True,
        app_kwargs={"repo_root": project_root},
        monkeypatch=monkeypatch,
    )
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def test_artifact_inspector_fixture_reads_its_selected_catalog(runtime_api_env) -> None:
    service = runtime_api_env["app"].state._control_service
    selection = service._catalog_source_selection
    graph = service._retrieval._dataset_catalog
    assert selection is not None
    owner_root = selection.source_owner_root
    assert owner_root is not None
    assert selection.snapshot_root.resolve().is_relative_to(owner_root.resolve())
    assert graph is not None
    database_path = selection.snapshot_root / "datasets" / "graph" / "dataset_catalog.duckdb"
    assert database_path.is_file()
    assert graph.database_path.resolve() == database_path.resolve()
    source_identity = graph.read_source_identity[0]
    assert source_identity.source_path == str(database_path.resolve())
    assert source_identity.byte_size > 0
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
        catalog_serving_source_scope,
    )

    with catalog_serving_source_scope(service._catalog_serving_source):
        registry = build_substrate_registry_from_existing_catalogs(service._repo_root)
    assert any("production_data/manifest.json" in ref for ref in registry.source_catalog_refs)


def test_artifact_inspector_fixture_fails_closed_when_owned_l5_input_is_missing(
    runtime_api_env,
) -> None:
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateRegistryError,
        build_substrate_registry_from_existing_catalogs,
        catalog_serving_source_scope,
        default_substrate_catalog_paths,
    )

    service = runtime_api_env["app"].state._control_service
    selection = service._catalog_source_selection
    assert selection is not None and selection.source_owner_root is not None
    paths = default_substrate_catalog_paths(
        service._repo_root,
        source_owner_root=selection.source_owner_root,
    )
    paths.measurement_registry_path.unlink()
    with (
        catalog_serving_source_scope(service._catalog_serving_source),
        pytest.raises(SubstrateRegistryError, match="substrate_catalog_missing"),
    ):
        build_substrate_registry_from_existing_catalogs(service._repo_root)


def _put_controlled_authority_profile_view(
    store: Any,
    payload: object,
    *,
    boundary_id: str,
    kind: str,
    schema_name: str,
    producer: ProducerInfo,
    tenant_id: str,
    cell_id: str,
    inputs: tuple[InputRef, ...] = (),
) -> tuple[ArtifactRef, ArtifactRef]:
    """Persist one profile view with the existing scoped HTTP fixture producer."""

    payload_bytes = to_canonical_bytes(payload)
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    payload_ref = f"sha256:{payload_sha256}"
    boundary = {
        **_runtime_fixture_authority_boundary(boundary_id=boundary_id),
        "subject_ref": payload_ref,
        "subject_kind": kind,
    }
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        envelope_ref = _put_fixture_authority_envelope(
            store,
            boundary,
            producer_version="profile-qualified-view-v1",
        )
        authority = ArtifactAuthorityInfo(
            authority_envelope_ref=str(envelope_ref.artifact_id),
            authority_envelope_manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
            diagnostic_event_ref=f"event://tests/runtime-api/{boundary_id}",
            manifest_ref=f"cas-manifest://{payload_ref}",
            payload_sha256=payload_sha256,
        )
        ref = store.put_json(
            payload,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version="1"),
                producer=producer,
                inputs=list(inputs),
                authority=authority,
            ),
            return_selected_profile=True,
        )
        assert str(ref.artifact_id) == payload_ref
        return profile_bound_ref(store, ref), envelope_ref


def test_eval_safety_projection_is_informational_only(runtime_api_env) -> None:
    runtime_context = runtime_api_env["app"].state.runtime_api_ctx
    store = runtime_context.store
    boundary = AuthorityBoundary(
        boundary_id="eval-safety-artifact-inspector-v1",
        authoritative_for=["runtime_closeout_authority", "dashboard_display"],
        may_not_use_for=[
            "attempted_evaluation_admission",
            "promotion",
            "evaluation_execution",
        ],
        source_authority="deterministic_producer",
        posture="advisory",
        rule_version_refs=["policyos.runtime.eval_safety.metrics_projection.v1"],
        evidence_kind="derivation",
        decision_grade="descriptive_only",
        known_limits=["informational_projection_only"],
    )
    denied_uses = (
        "attempted_evaluation_admission",
        "promotion",
        "evaluation_execution",
    )
    packet = EvalSafetyAuthoritySurfacePacket(
        schema_version="policyos.runtime.eval_safety_surface_packet.v1",
        boundary=boundary,
        surfaces={
            surface: EvalSafetySurfaceDisposition(
                surface=surface,
                purpose=(
                    "dashboard_display" if surface == "dashboard" else "runtime_closeout_authority"
                ),
                status="allow",
                authority_result="informational_projection_only",
                consumed_boundary_id="eval-safety-artifact-inspector-v1",
                projection_scope="faithful_eval_safety_projection",
                may_not_use_for=denied_uses,
            )
            for surface in ("run", "artifact", "lineage", "dashboard")
        },
    )
    projection = EvalSafetyMetricsProjection(
        attempt_disposition="passed",
        selected_decision_artifact_refs=(),
        reconciled_decision_artifact_refs=(),
        unreconciled_decision_artifact_refs=(),
        conflicting_decision_artifact_refs=(),
        denominator_decision_ids=(),
        unsafe_attempt_blocked_count=0,
        near_miss_count=0,
        near_miss_classification_status="complete",
        unclassified_blocked_decision_ids=(),
        reconciliation_status="complete",
        generated_at=datetime(2026, 8, 28, 8, 0, tzinfo=UTC),
        source_event_refs=(),
        authority_boundary=boundary,
        authority_surface_packet=packet,
    )
    identity = evaluation_safety_metrics_projection_identity("artifact")
    ref = store.put_json(
        projection.model_dump(mode="json"),
        PutOptions(
            kind=identity.kind,
            media_type="application/json",
            schema=SchemaInfo(
                name=identity.schema_name,
                version=identity.schema_version,
            ),
        ),
    )
    _record_fixture_owner(
        store,
        ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    run_id = "R_eval-safety-artifact-inspector"
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        run = RunContext.start(
            store,
            build_default_registry_bundle(store).bundle_ref,
            producer=ProducerInfo(
                component="polisyos.runtime.http.control.evaluation_safety",
                version="1.0.0",
            ),
            run_dir=runtime_context.core_runs_root / run_id,
            run_id=run_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        )
        run.add_output(ref)
        run.finalize(status="completed")
    runtime_context.run_index.refresh(force=True)

    response = runtime_api_env["client"].get(f"/api/v1/artifacts/{ref.artifact_id}/content")

    assert response.status_code == 200, response.text
    preview = response.json()["artifact"]["preview"]
    assert EvalSafetyMetricsProjection.model_validate(preview) == projection
    denied = _runtime_api_request(
        runtime_api_env,
        authority_surface_decision,
        preview,
        surface="artifact",
        purpose="promotion",
        artifact_store=store,
        artifact_id=ref.artifact_id,
        require_cas_integrity=True,
    )
    assert denied.blocking
    assert "promotion" in projection.authority_boundary.may_not_use_for
    with pytest.raises(ValidationError):
        EvalSafetyCertificate.model_validate(preview)


def test_artifact_manifest_endpoint_returns_canonical_metadata(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]
    response = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert response.status_code == 200

    artifact = response.json()["artifact"]
    assert artifact["artifact_id"] == artifact_id
    assert artifact["kind"] == "scientist.workflow_report"
    assert artifact["schema_name"] == "scientist.workflow_report"


def test_artifact_content_preview_enforces_max_bytes(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["binary_artifact_id"]
    response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{artifact_id}/content?max_bytes=1024",
    )
    assert response.status_code == 200

    preview = response.json()["artifact"]
    assert preview["artifact_id"] == artifact_id
    assert preview["truncated"] is True
    assert preview["max_bytes"] == 1024
    content_with_larger_limit = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{artifact_id}/content",
        params={"max_bytes": 2048},
    )
    raw_content = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{artifact_id}/content",
        headers={"Accept": "application/octet-stream"},
    )
    assert content_with_larger_limit.status_code == 200, content_with_larger_limit.text
    assert raw_content.status_code == 200, raw_content.text
    assert content_with_larger_limit.headers["etag"] != response.headers["etag"]
    assert raw_content.headers["etag"] not in {
        response.headers["etag"],
        content_with_larger_limit.headers["etag"],
    }

    secret = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{runtime_api_env['secret_artifact_id']}/content",
    )
    assert secret.status_code == 409
    secret_decision = secret.json()["extensions"]["authority_surface_decision"]
    assert secret.json()["code"] == "authority_surface_admission_blocked"
    assert secret_decision["reason"] == "secret_pii_surface_blocked"
    assert any(
        contributor["basis"] == "selected_manifest"
        and contributor["authority_boundary_ref"] == "boundary-runtime-api-secret-lineage-refusal"
        and contributor["reason"] == "authority_purpose_forbidden"
        and contributor["visible_downgrade"]
        for contributor in secret_decision["authority_contributors"]
    )


def test_current_inspector_emits_computed_status_for_content_and_schema(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["binary_artifact_id"]

    content = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{artifact_id}/content",
    )
    schema = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{artifact_id}/schema",
    )

    assert content.status_code == 200, content.text
    assert schema.status_code == 200, schema.text
    assert content.json()["artifact"]["canon_read_status"] == "not_applicable"
    assert schema.json()["schema"]["canon_read_status"] == "not_applicable"


def test_artifact_lineage_and_schema_endpoints(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]

    lineage = client.get(f"/api/v1/artifacts/{artifact_id}/lineage")
    assert lineage.status_code == 200
    lineage_payload = lineage.json()["lineage"]
    assert lineage_payload["total_nodes"] >= 1
    assert artifact_id in lineage_payload["root_artifact_ids"]

    schema = client.get(f"/api/v1/artifacts/{artifact_id}/schema")
    assert schema.status_code == 200
    schema_payload = schema.json()["schema"]
    assert schema_payload["schema_name"] == "scientist.workflow_report"


def test_artifact_inspector_resolves_exact_manifest_profile_for_all_views(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    runtime_context = runtime_api_env["app"].state.runtime_api_ctx
    store = runtime_context.store
    payload = {"same_blob": True}
    producer = ProducerInfo(component="test.profile_inspector", version="1")
    first, first_envelope = _put_controlled_authority_profile_view(
        store,
        payload,
        boundary_id="boundary-profile-inspector-first",
        kind="test.profile_inspector.first",
        schema_name="test.profile_inspector.first",
        producer=producer,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    second, second_envelope = _put_controlled_authority_profile_view(
        store,
        payload,
        boundary_id="boundary-profile-inspector-second",
        kind="test.profile_inspector.second",
        schema_name="test.profile_inspector.second",
        producer=producer,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    assert first.artifact_id == second.artifact_id
    assert first.manifest_profile_sha256 is not None
    assert second.manifest_profile_sha256 is not None
    assert first.manifest_profile_sha256 != second.manifest_profile_sha256
    _record_fixture_owner(
        store,
        first_envelope,
        second_envelope,
        first,
        second,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )

    def selected_url(suffix: str, profile: str) -> str:
        path = f"/api/v1/artifacts/{first.artifact_id}"
        if suffix:
            path = f"{path}/{suffix}"
        return f"{path}?manifest_profile_sha256={profile}"

    first_manifest = _runtime_api_request(
        runtime_api_env, client.get, selected_url("", first.manifest_profile_sha256)
    )
    second_manifest = _runtime_api_request(
        runtime_api_env, client.get, selected_url("", second.manifest_profile_sha256)
    )
    first_preview = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("content", first.manifest_profile_sha256),
    )
    second_preview = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("content", second.manifest_profile_sha256),
    )
    first_schema = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("schema", first.manifest_profile_sha256),
    )
    second_schema = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("schema", second.manifest_profile_sha256),
    )
    first_lineage = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("lineage", first.manifest_profile_sha256),
    )
    second_lineage = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("lineage", second.manifest_profile_sha256),
    )
    first_download = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("download", first.manifest_profile_sha256),
    )
    second_download = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_url("download", second.manifest_profile_sha256),
    )

    assert first_manifest.status_code == second_manifest.status_code == 200
    assert first_manifest.json()["artifact"]["manifest_profile_sha256"] == (
        first.manifest_profile_sha256
    )
    assert first_manifest.json()["artifact"]["kind"] == "test.profile_inspector.first"
    assert second_manifest.json()["artifact"]["manifest_profile_sha256"] == (
        second.manifest_profile_sha256
    )
    assert second_manifest.json()["artifact"]["kind"] == "test.profile_inspector.second"
    assert first_preview.status_code == second_preview.status_code == 200
    assert first_preview.json()["artifact"]["manifest_profile_sha256"] == (
        first.manifest_profile_sha256
    )
    assert second_preview.json()["artifact"]["manifest_profile_sha256"] == (
        second.manifest_profile_sha256
    )
    assert first_preview.json()["artifact"]["preview"] == payload
    assert second_preview.json()["artifact"]["preview"] == payload
    assert first_schema.json()["schema"]["schema_name"] == ("test.profile_inspector.first")
    assert second_schema.json()["schema"]["schema_name"] == ("test.profile_inspector.second")
    assert first_lineage.status_code == second_lineage.status_code == 200
    assert (
        first_lineage.json()["lineage"]["root_artifact_refs"][0]["manifest_profile_sha256"]
        == first.manifest_profile_sha256
    )
    assert (
        second_lineage.json()["lineage"]["root_artifact_refs"][0]["manifest_profile_sha256"]
        == second.manifest_profile_sha256
    )
    assert (
        first_lineage.json()["lineage"]["nodes"][0]["manifest_profile_sha256"]
        == first.manifest_profile_sha256
    )
    assert (
        second_lineage.json()["lineage"]["nodes"][0]["manifest_profile_sha256"]
        == second.manifest_profile_sha256
    )
    assert first_download.status_code == second_download.status_code == 200
    assert first_download.content == second_download.content
    assert first_download.headers["content-type"] == second_download.headers["content-type"]
    assert first_download.headers["etag"] != second_download.headers["etag"]

    default_profile = artifact_manifest_profile_sha256(
        _runtime_api_request(runtime_api_env, store.get_manifest, first.artifact_id)
    )

    def profile_for_relation(response, relation: str) -> str:
        links = response.headers["link"].split(", ")
        selected = next(
            link for link in links if link.rsplit("; rel=", 1)[1].strip('"') == relation
        )
        href = selected.rsplit("; rel=", 1)[0].strip("<>")
        return parse_qs(urlsplit(href).query)["manifest_profile_sha256"][0]

    profile_relations = ("self", "preview", "download", "describedby", "related")
    for relation in profile_relations:
        assert profile_for_relation(first_download, relation) == first.manifest_profile_sha256
        assert profile_for_relation(second_download, relation) == second.manifest_profile_sha256

    default_views = {}
    for suffix in ("", "content", "schema", "lineage", "download"):
        path = f"/api/v1/artifacts/{first.artifact_id}"
        if suffix:
            path = f"{path}/{suffix}"
        view = _runtime_api_request(runtime_api_env, client.get, path)
        assert view.status_code == 200
        default_views[suffix] = (path, view)
        for relation in profile_relations:
            assert profile_for_relation(view, relation) == default_profile

    default_lineage = default_views["lineage"][1]
    default_root_ref = default_lineage.json()["lineage"]["root_artifact_refs"][0]
    assert default_root_ref["manifest_profile_sha256"] == default_profile

    for path, view in default_views.values():
        not_modified = _runtime_api_request(
            runtime_api_env,
            client.get,
            path,
            headers={"If-None-Match": view.headers["etag"]},
        )
        assert not_modified.status_code == 304
        for relation in profile_relations:
            assert profile_for_relation(not_modified, relation) == default_profile

    for suffix, first_view, second_view in (
        ("", first_manifest, second_manifest),
        ("content", first_preview, second_preview),
        ("schema", first_schema, second_schema),
        ("lineage", first_lineage, second_lineage),
        ("download", first_download, second_download),
    ):
        assert first_view.headers["etag"] != second_view.headers["etag"]
        path = f"/api/v1/artifacts/{first.artifact_id}"
        if suffix:
            path = f"{path}/{suffix}"
        other_profile_with_first_etag = _runtime_api_request(
            runtime_api_env,
            client.get,
            path,
            params={"manifest_profile_sha256": second.manifest_profile_sha256},
            headers={"If-None-Match": first_view.headers["etag"]},
        )
        assert other_profile_with_first_etag.status_code == 200
        assert other_profile_with_first_etag.headers["etag"] == (second_view.headers["etag"])

    for suffix in ("content", "download"):
        missing_profile = _runtime_api_request(
            runtime_api_env, client.get, selected_url(suffix, "sha256:" + "f" * 64)
        )
        malformed_profile = _runtime_api_request(
            runtime_api_env, client.get, selected_url(suffix, "invalid")
        )
        assert missing_profile.status_code == 404
        assert missing_profile.json()["code"] == "artifact_manifest_profile_not_found"
        assert malformed_profile.status_code == 422

    for suffix in ("", "content", "schema", "lineage", "download"):
        path = f"/api/v1/artifacts/{first.artifact_id}"
        if suffix:
            path = f"{path}/{suffix}"
        for repeated_profiles in (
            (first.manifest_profile_sha256, second.manifest_profile_sha256),
            (first.manifest_profile_sha256, first.manifest_profile_sha256),
        ):
            response = _runtime_api_request(
                runtime_api_env,
                client.get,
                path,
                params=[
                    ("manifest_profile_sha256", repeated_profiles[0]),
                    ("manifest_profile_sha256", repeated_profiles[1]),
                ],
            )
            assert response.status_code == 400
            assert response.json()["code"] == "ambiguous_manifest_profile_selector"

    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        unbound_first = profile_bound_ref(
            store,
            store.put_json(
                payload,
                PutOptions(
                    kind="test.profile_inspector.unbound.first",
                    media_type="application/json",
                    producer=producer,
                    schema=SchemaInfo(name="test.profile_inspector.unbound.first", version="1"),
                ),
            ),
        )
        unbound_second = profile_bound_ref(
            store,
            store.put_json(
                payload,
                PutOptions(
                    kind="test.profile_inspector.unbound.second",
                    media_type="application/json",
                    producer=producer,
                    schema=SchemaInfo(name="test.profile_inspector.unbound.second", version="1"),
                ),
            ),
        )
    assert unbound_first.artifact_id == unbound_second.artifact_id == first.artifact_id
    assert unbound_first.manifest_profile_sha256 != unbound_second.manifest_profile_sha256
    _record_fixture_owner(
        store,
        unbound_first,
        unbound_second,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )
    for ref in (unbound_first, unbound_second):
        for suffix in ("", "content", "schema", "lineage", "download"):
            path = f"/api/v1/artifacts/{ref.artifact_id}"
            if suffix:
                path = f"{path}/{suffix}"
            refusal = _runtime_api_request(
                runtime_api_env,
                client.get,
                path,
                params={"manifest_profile_sha256": ref.manifest_profile_sha256},
            )
            assert refusal.status_code == 409
            assert refusal.json()["code"] == "authority_surface_admission_blocked"
            assert (
                refusal.json()["extensions"]["authority_surface_decision"]["reason"]
                == "authority_surface_signal_missing"
            )

    for ref, expected_boundary_id in (
        (first, "boundary-profile-inspector-first"),
        (second, "boundary-profile-inspector-second"),
    ):
        scope_control = _runtime_api_request(
            runtime_api_env,
            authority_surface_decision,
            None,
            surface="artifact",
            purpose="claim_authority",
            artifact_store=store,
            artifact_ref=ref,
        )
        selected_contributor = next(
            row for row in scope_control.authority_contributors if row.basis == "selected_manifest"
        )
        assert selected_contributor.authority_boundary_ref == expected_boundary_id
        assert selected_contributor.status == "downgraded"
        assert selected_contributor.reason == "authority_purpose_forbidden"


def test_selected_manifest_lineage_preserves_each_input_profile(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    producer = ProducerInfo(component="test.profile_lineage", version="1")

    # Keep the original unlinked parent/child profile siblings as a refusal
    # control: selector identity alone cannot authorize lineage disclosure.
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        parent_first = store.put_json(
            {"parent": "same bytes"},
            PutOptions(
                kind="test.profile_lineage.parent.first",
                media_type="application/json",
                producer=producer,
                schema=SchemaInfo(name="test.profile_lineage.parent.first", version="1"),
            ),
        )
        parent_first = profile_bound_ref(store, parent_first)
        parent_second = store.put_json(
            {"parent": "same bytes"},
            PutOptions(
                kind="test.profile_lineage.parent.second",
                media_type="application/json",
                producer=producer,
                schema=SchemaInfo(name="test.profile_lineage.parent.second", version="1"),
            ),
        )
        parent_second = profile_bound_ref(store, parent_second)
    assert parent_first.artifact_id == parent_second.artifact_id
    assert parent_first.manifest_profile_sha256 != parent_second.manifest_profile_sha256
    _record_fixture_owner(
        store,
        parent_first,
        parent_second,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )

    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        child_first = store.put_json(
            {"child": "same bytes"},
            PutOptions(
                kind="test.profile_lineage.child",
                media_type="application/json",
                producer=producer,
                inputs=[
                    InputRef(
                        artifact_id=parent_first.artifact_id,
                        manifest_profile_sha256=parent_first.manifest_profile_sha256,
                        role="source",
                    )
                ],
            ),
        )
        child_first = profile_bound_ref(store, child_first)
        child_second = store.put_json(
            {"child": "same bytes"},
            PutOptions(
                kind="test.profile_lineage.child",
                media_type="application/json",
                producer=producer,
                inputs=[
                    InputRef(
                        artifact_id=parent_second.artifact_id,
                        manifest_profile_sha256=parent_second.manifest_profile_sha256,
                        role="source",
                    )
                ],
            ),
        )
        child_second = profile_bound_ref(store, child_second)
    assert child_first.artifact_id == child_second.artifact_id
    assert child_first.manifest_profile_sha256 != child_second.manifest_profile_sha256
    _record_fixture_owner(
        store,
        child_first,
        child_second,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )

    for ref in (child_first, child_second):
        refusal = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"/api/v1/artifacts/{ref.artifact_id}/lineage",
            params={"manifest_profile_sha256": ref.manifest_profile_sha256},
        )
        assert refusal.status_code == 409
        assert refusal.json()["code"] == "authority_surface_admission_blocked"
        assert (
            refusal.json()["extensions"]["authority_surface_decision"]["reason"]
            == "authority_surface_signal_missing"
        )

    controlled_parent_first, parent_envelope_first = _put_controlled_authority_profile_view(
        store,
        {"parent": "same bytes"},
        boundary_id="boundary-profile-lineage-parent-first",
        kind="test.profile_lineage.controlled_parent.first",
        schema_name="test.profile_lineage.controlled_parent.first",
        producer=producer,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    controlled_parent_second, parent_envelope_second = _put_controlled_authority_profile_view(
        store,
        {"parent": "same bytes"},
        boundary_id="boundary-profile-lineage-parent-second",
        kind="test.profile_lineage.controlled_parent.second",
        schema_name="test.profile_lineage.controlled_parent.second",
        producer=producer,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    assert controlled_parent_first.artifact_id == controlled_parent_second.artifact_id
    assert (
        controlled_parent_first.manifest_profile_sha256
        != controlled_parent_second.manifest_profile_sha256
    )
    _record_fixture_owner(
        store,
        parent_envelope_first,
        parent_envelope_second,
        controlled_parent_first,
        controlled_parent_second,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )

    controlled_parent_first_source = InputRef(
        artifact_id=controlled_parent_first.artifact_id,
        manifest_profile_sha256=controlled_parent_first.manifest_profile_sha256,
        role="source",
    )
    controlled_parent_second_source = InputRef(
        artifact_id=controlled_parent_second.artifact_id,
        manifest_profile_sha256=controlled_parent_second.manifest_profile_sha256,
        role="source",
    )
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        controlled_child_first, child_envelope_first = _put_controlled_authority_profile_view(
            store,
            {"child": "same bytes"},
            boundary_id="boundary-profile-lineage-child-first",
            kind="test.profile_lineage.controlled_child",
            schema_name="test.profile_lineage.controlled_child",
            producer=producer,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
            inputs=(controlled_parent_first_source,),
        )
        controlled_child_second, child_envelope_second = _put_controlled_authority_profile_view(
            store,
            {"child": "same bytes"},
            boundary_id="boundary-profile-lineage-child-second",
            kind="test.profile_lineage.controlled_child",
            schema_name="test.profile_lineage.controlled_child",
            producer=producer,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
            inputs=(controlled_parent_second_source,),
        )
    assert controlled_child_first.artifact_id == controlled_child_second.artifact_id
    assert (
        controlled_child_first.manifest_profile_sha256
        != controlled_child_second.manifest_profile_sha256
    )
    _record_fixture_owner(
        store,
        child_envelope_first,
        child_envelope_second,
        controlled_child_first,
        controlled_child_second,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )

    def source_input_identity(input_ref: InputRef) -> tuple[str, str | None, str]:
        return (
            str(input_ref.artifact_id),
            input_ref.manifest_profile_sha256,
            input_ref.role,
        )

    def persisted_source_inputs(
        produced_ref: ArtifactRef,
        declared_inputs: tuple[InputRef, ...],
    ) -> tuple[InputRef, ...]:
        verification = _runtime_api_request(runtime_api_env, store.verify, produced_ref)
        assert verification.ok
        manifest = _runtime_api_request(runtime_api_env, store.get_manifest, produced_ref)
        persisted_inputs = tuple(
            input_ref for input_ref in manifest.inputs if input_ref.role == "source"
        )
        assert Counter(map(source_input_identity, persisted_inputs)) == Counter(
            map(source_input_identity, declared_inputs)
        )
        return persisted_inputs

    first_source_inputs = persisted_source_inputs(
        controlled_child_first, (controlled_parent_first_source,)
    )
    second_source_inputs = persisted_source_inputs(
        controlled_child_second, (controlled_parent_second_source,)
    )

    def assert_source_edges_match_persisted_inputs(
        view: dict[str, object],
        produced_ref: ArtifactRef,
        source_inputs: tuple[InputRef, ...],
    ) -> None:
        edges = view["edges"]
        assert isinstance(edges, list)
        actual_source_edges = []
        for edge in edges:
            assert isinstance(edge, dict)
            if (
                edge.get("parent_artifact_id") == str(produced_ref.artifact_id)
                and edge.get("role") == "source"
            ):
                actual_source_edges.append(
                    (
                        edge["parent_artifact_id"],
                        edge["parent_manifest_profile_sha256"],
                        edge["child_artifact_id"],
                        edge["child_manifest_profile_sha256"],
                        edge["role"],
                    )
                )
        expected_source_edges = [
            (
                str(produced_ref.artifact_id),
                produced_ref.manifest_profile_sha256,
                str(input_ref.artifact_id),
                input_ref.manifest_profile_sha256,
                input_ref.role,
            )
            for input_ref in source_inputs
        ]
        assert Counter(actual_source_edges) == Counter(expected_source_edges), (
            "lineage source edges differ from the byte-verified producer inputs"
        )

    def lineage(ref: ArtifactRef) -> dict[str, object]:
        response = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"/api/v1/artifacts/{ref.artifact_id}/lineage",
            params={"manifest_profile_sha256": ref.manifest_profile_sha256},
        )
        assert response.status_code == 200, response.text
        return response.json()["lineage"]

    first_view = lineage(controlled_child_first)
    second_view = lineage(controlled_child_second)

    def parent_profile(view: dict[str, object]) -> str | None:
        nodes = view["nodes"]
        assert isinstance(nodes, list)
        parent_nodes = [
            node
            for node in nodes
            if node["artifact_id"] == str(controlled_parent_first.artifact_id)
        ]
        assert len(parent_nodes) == 1
        return parent_nodes[0]["manifest_profile_sha256"]

    assert parent_profile(first_view) == controlled_parent_first.manifest_profile_sha256
    assert parent_profile(second_view) == controlled_parent_second.manifest_profile_sha256
    assert parent_profile(first_view) != parent_profile(second_view)
    assert_source_edges_match_persisted_inputs(
        first_view, controlled_child_first, first_source_inputs
    )
    assert_source_edges_match_persisted_inputs(
        second_view, controlled_child_second, second_source_inputs
    )

    first_edges = first_view["edges"]
    assert isinstance(first_edges, list)
    assert len(first_source_inputs) == 1
    source_input = first_source_inputs[0]
    valid_source_edge = {
        "parent_artifact_id": str(controlled_child_first.artifact_id),
        "parent_manifest_profile_sha256": controlled_child_first.manifest_profile_sha256,
        "child_artifact_id": str(source_input.artifact_id),
        "child_manifest_profile_sha256": source_input.manifest_profile_sha256,
        "role": "source",
    }
    assert valid_source_edge in first_edges
    wrong_dependency_profile = "sha256:" + "f" * 64
    assert wrong_dependency_profile != source_input.manifest_profile_sha256
    wrong_profile_source_edge = {
        **valid_source_edge,
        "child_manifest_profile_sha256": wrong_dependency_profile,
    }
    divergent_view = {
        **first_view,
        "edges": [*first_edges, wrong_profile_source_edge],
    }
    with pytest.raises(AssertionError, match="lineage source edges differ"):
        assert_source_edges_match_persisted_inputs(
            divergent_view, controlled_child_first, first_source_inputs
        )

    scope_control = _runtime_api_request(
        runtime_api_env,
        authority_surface_decision,
        None,
        surface="lineage",
        purpose="claim_authority",
        artifact_store=store,
        artifact_ref=controlled_child_first,
    )
    selected_contributor = next(
        row for row in scope_control.authority_contributors if row.basis == "selected_manifest"
    )
    assert selected_contributor.status == "downgraded"
    assert selected_contributor.reason == "authority_purpose_forbidden"


def test_unqualified_manifest_view_revalidates_cache_and_304_keeps_resolved_link(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]
    path = f"/api/v1/artifacts/{artifact_id}"

    default_view = _runtime_api_request(runtime_api_env, client.get, path)
    assert default_view.status_code == 200
    assert default_view.headers["cache-control"] == "private, no-cache"
    resolved_profile = default_view.json()["artifact"]["manifest_profile_sha256"]
    assert resolved_profile.startswith("sha256:")

    default_not_modified = _runtime_api_request(
        runtime_api_env,
        client.get,
        path,
        headers={"If-None-Match": default_view.headers["etag"]},
    )
    assert default_not_modified.status_code == 304
    assert default_not_modified.headers["cache-control"] == "private, no-cache"
    link = default_not_modified.headers["link"].split(", ", 1)[0]
    href = link.split(";", 1)[0].strip("<>")
    assert parse_qs(urlsplit(href).query)["manifest_profile_sha256"] == [resolved_profile]

    selected = _runtime_api_request(
        runtime_api_env,
        client.get,
        path,
        params={"manifest_profile_sha256": resolved_profile},
    )
    assert selected.status_code == 200
    assert selected.headers["cache-control"] == "private, max-age=31536000, immutable"


def test_selected_manifest_authority_controls_all_artifact_http_surfaces(
    runtime_api_env,
) -> None:
    runtime_context = runtime_api_env["app"].state.runtime_api_ctx
    store = runtime_context.store
    client = runtime_api_env["client"]
    permitted_purposes = [
        "runtime_closeout_authority",
        "dashboard_display",
        "publication",
    ]
    denied_purposes = list(permitted_purposes)

    def envelope_ref(
        label: str,
        *,
        denied: bool,
        denied_purpose: str | None = None,
        kind: str = "runtime_quality.evidence_authority_envelope",
    ) -> ArtifactRef:
        may_not_use_for = (
            ([denied_purpose] if denied_purpose is not None else denied_purposes)
            if denied
            else ["evaluation_execution"]
        )
        payload = {
            "authority_result": "authority",
            "legacy_path_disposition": "authority_path",
            "authority_boundary": {
                "boundary_id": f"boundary://{label}",
                "source_authority": "runtime_quality",
                "posture": "authority",
                "authoritative_for": permitted_purposes,
                "may_not_use_for": may_not_use_for,
                "rule_version_refs": ["rule://s3-profile-surface-test"],
            },
        }
        return store.put_json(
            payload,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(
                    name="runtime_quality.evidence_authority_envelope",
                    version="1.0.0",
                ),
                producer=ProducerInfo(
                    component="polisyos.tests.s3-profile-authority",
                    version=label,
                ),
            ),
            return_selected_profile=True,
        )

    def authority_link(ref: ArtifactRef) -> ArtifactAuthorityInfo:
        return ArtifactAuthorityInfo(
            authority_envelope_ref=str(ref.artifact_id),
            authority_envelope_manifest_profile_sha256=ref.manifest_profile_sha256,
            diagnostic_event_ref="sha256:" + "2" * 64,
            manifest_ref=f"cas-manifest://{ref.artifact_id}",
            payload_sha256=ref.artifact_id.hex,
        )

    def persist_view_pair(
        label: str,
        *,
        payload_label: str | None = None,
        default_denied: bool,
        selected_denied: bool,
        inline_denied: bool | None = None,
        selected_denied_purpose: str | None = None,
        selected_envelope_kind: str = "runtime_quality.evidence_authority_envelope",
        selected_authority_link: ArtifactAuthorityInfo | None = None,
    ) -> tuple[ArtifactRef, ArtifactRef]:
        payload: dict[str, object] = {
            "run_id": f"R_s3_profile_{payload_label or label}",
            "governance": {},
            "diagnostics_summary": {},
        }
        if inline_denied is not None:
            payload.update(
                {
                    "authority_result": "authority",
                    "legacy_path_disposition": "authority_path",
                    "authority_boundary": {
                        "boundary_id": f"boundary://inline-{label}",
                        "source_authority": "runtime_quality",
                        "posture": "authority",
                        "authoritative_for": permitted_purposes,
                        "may_not_use_for": (
                            denied_purposes if inline_denied else ["evaluation_execution"]
                        ),
                        "rule_version_refs": ["rule://s3-profile-authority-inline-test"],
                    },
                }
            )
        default_envelope = envelope_ref(f"{label}-default", denied=default_denied)
        selected_envelope = envelope_ref(
            f"{label}-selected",
            denied=selected_denied,
            denied_purpose=selected_denied_purpose,
            kind=selected_envelope_kind,
        )

        def write_options(
            ref: ArtifactRef,
            authority_override: ArtifactAuthorityInfo | None = None,
        ) -> PutOptions:
            return PutOptions(
                kind="runtime.test_payload",
                media_type="application/json",
                schema=SchemaInfo(name="runtime.test_payload", version="1.0.0"),
                authority=authority_override or authority_link(ref),
            )

        default_ref = store.put_json(
            payload,
            write_options(default_envelope),
            return_selected_profile=True,
        )
        selected_ref = store.put_json(
            payload,
            write_options(selected_envelope, selected_authority_link),
            return_selected_profile=True,
        )
        assert default_ref.artifact_id == selected_ref.artifact_id
        assert selected_ref.manifest_profile_sha256 is not None
        _record_fixture_owner(
            store,
            default_envelope,
            selected_envelope,
            default_ref,
            selected_ref,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
            runtime_api_env=runtime_api_env,
        )
        return default_ref, selected_ref

    def request_surfaces(
        ref: ArtifactRef,
        *,
        selected: bool,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        artifact_id = str(ref.artifact_id)
        query = {"manifest_profile_sha256": ref.manifest_profile_sha256} if selected else {}
        render_body: dict[str, object] = {"genre": "expert_vysnovok"}
        if selected:
            render_body["manifest_profile_sha256"] = ref.manifest_profile_sha256
        export_query: dict[str, object] = {"format": "html", "genre": "expert_vysnovok"}
        export_query.update(query)
        base = f"/api/v1/artifacts/{artifact_id}"
        return {
            "manifest": _runtime_api_request(
                runtime_api_env, client.get, base, params=query, headers=headers
            ),
            "content": _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{base}/content",
                params=query,
                headers=headers,
            ),
            "content_raw": _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{base}/content",
                params=query,
                headers={"accept": "application/octet-stream", **(headers or {})},
            ),
            "lineage": _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{base}/lineage",
                params=query,
                headers=headers,
            ),
            "schema": _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{base}/schema",
                params=query,
                headers=headers,
            ),
            "download": _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{base}/download",
                params=query,
                headers={"accept": "application/octet-stream", **(headers or {})},
            ),
            "render": _runtime_api_request(
                runtime_api_env,
                client.post,
                f"{base}/render",
                json=render_body,
                headers=headers,
            ),
            "export": _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{base}/export",
                params=export_query,
                headers=headers,
            ),
        }

    cases = (
        (
            persist_view_pair("default-allows", default_denied=False, selected_denied=True),
            True,
            False,
        ),
        (
            persist_view_pair("selected-allows", default_denied=True, selected_denied=False),
            False,
            True,
        ),
    )
    for (default_ref, selected_ref), default_allowed, selected_allowed in cases:
        for ref, selected, allowed in (
            (default_ref, False, default_allowed),
            (selected_ref, True, selected_allowed),
        ):
            expected = 200 if allowed else 409
            for surface, response in request_surfaces(ref, selected=selected).items():
                assert response.status_code == expected, (
                    surface,
                    selected,
                    response.status_code,
                    response.text,
                )
                if not allowed:
                    assert response.json()["code"] == "authority_surface_admission_blocked"

    route_gate_purposes = {
        # Values are the complete effective-purpose set from the ordered route
        # and service checks. `content_raw` is the raw representation branch of
        # GET /content; the JSON preview has an additional dashboard check.
        "manifest": ("runtime_closeout_authority", "dashboard_display"),
        "content": ("runtime_closeout_authority", "dashboard_display"),
        "content_raw": ("runtime_closeout_authority",),
        "lineage": ("runtime_closeout_authority",),
        "schema": ("runtime_closeout_authority", "dashboard_display"),
        "download": ("runtime_closeout_authority",),
        "render": ("dashboard_display",),
        "export": ("publication",),
    }
    denied_routes_by_purpose = {
        purpose: {
            route_name
            for route_name, gate_purposes in route_gate_purposes.items()
            if purpose in gate_purposes
        }
        for purpose in permitted_purposes
    }
    for denied_purpose, denied_routes in denied_routes_by_purpose.items():
        default_ref, selected_ref = persist_view_pair(
            f"purpose-{denied_purpose}",
            default_denied=False,
            selected_denied=True,
            selected_denied_purpose=denied_purpose,
        )
        assert default_ref.artifact_id == selected_ref.artifact_id
        default_responses = request_surfaces(default_ref, selected=False)
        selected_responses = request_surfaces(selected_ref, selected=True)
        assert set(route_gate_purposes) == set(default_responses) == set(selected_responses)
        for route_name, response in default_responses.items():
            assert response.status_code == 200, (
                denied_purpose,
                "default",
                route_name,
                response.status_code,
                response.text,
            )
        for route_name, response in selected_responses.items():
            denied = route_name in denied_routes
            assert response.status_code == (409 if denied else 200), (
                denied_purpose,
                route_name,
                response.status_code,
                response.text,
            )
            if denied:
                decision = response.json()["extensions"]["authority_surface_decision"]
                assert decision["purpose"] == denied_purpose
                assert denied_purpose in decision["may_not_use_for"]
                selected_contributor = next(
                    row
                    for row in decision["authority_contributors"]
                    if row["basis"] == "selected_manifest"
                )
                assert selected_contributor["authority_boundary_ref"] == (
                    f"boundary://purpose-{denied_purpose}-selected"
                )
                assert denied_purpose in selected_contributor["may_not_use_for"]

        conditional_selected_responses = request_surfaces(
            selected_ref,
            selected=True,
            headers={"if-none-match": "*"},
        )
        conditional_routes = {
            "manifest",
            "content",
            "content_raw",
            "lineage",
            "schema",
            "download",
        }
        for route_name, conditional_response in conditional_selected_responses.items():
            denied = route_name in denied_routes
            expected_conditional_status = (
                409 if denied else 304 if route_name in conditional_routes else 200
            )
            assert conditional_response.status_code == expected_conditional_status, (
                denied_purpose,
                "conditional",
                route_name,
                conditional_response.status_code,
                conditional_response.text,
            )
            if denied:
                decision = conditional_response.json()["extensions"]["authority_surface_decision"]
                assert decision["purpose"] == denied_purpose
                assert denied_purpose in decision["may_not_use_for"]

    selected_allows = persist_view_pair(
        "selected-raw-content-allows",
        default_denied=False,
        selected_denied=False,
    )[1]
    selected_allows_path = f"/api/v1/artifacts/{selected_allows.artifact_id}/content"
    selected_allows_query = {"manifest_profile_sha256": selected_allows.manifest_profile_sha256}
    selected_raw = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_allows_path,
        params=selected_allows_query,
        headers={"accept": "application/octet-stream"},
    )
    assert selected_raw.status_code == 200
    selected_raw_304 = _runtime_api_request(
        runtime_api_env,
        client.get,
        selected_allows_path,
        params=selected_allows_query,
        headers={
            "accept": "application/octet-stream",
            "if-none-match": selected_raw.headers["etag"],
        },
    )
    assert selected_raw_304.status_code == 304

    selected_runtime_deny = persist_view_pair(
        "selected-raw-content-denies-runtime",
        default_denied=False,
        selected_denied=True,
        selected_denied_purpose="runtime_closeout_authority",
    )[1]
    selected_raw_deny_304 = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{selected_runtime_deny.artifact_id}/content",
        params={"manifest_profile_sha256": selected_runtime_deny.manifest_profile_sha256},
        headers={
            "accept": "application/octet-stream",
            "if-none-match": "*",
        },
    )
    assert selected_raw_deny_304.status_code == 409
    assert (
        selected_raw_deny_304.json()["extensions"]["authority_surface_decision"]["purpose"]
        == "runtime_closeout_authority"
    )

    _, cached_profile = persist_view_pair(
        "json-cache-rotation-allowed",
        payload_label="json-cache-rotation-shared-content",
        default_denied=False,
        selected_denied=False,
    )
    cached_profile_path = f"/api/v1/artifacts/{cached_profile.artifact_id}/content"
    cached_profile_query = {"manifest_profile_sha256": cached_profile.manifest_profile_sha256}
    cached_profile_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        cached_profile_path,
        params=cached_profile_query,
    )
    assert cached_profile_response.status_code == 200
    cached_profile_304 = _runtime_api_request(
        runtime_api_env,
        client.get,
        cached_profile_path,
        params=cached_profile_query,
        headers={"if-none-match": cached_profile_response.headers["etag"]},
    )
    assert cached_profile_304.status_code == 304

    _, current_denied_profile = persist_view_pair(
        "json-cache-rotation-denied",
        payload_label="json-cache-rotation-shared-content",
        default_denied=False,
        selected_denied=True,
        selected_denied_purpose="dashboard_display",
    )
    assert current_denied_profile.artifact_id == cached_profile.artifact_id
    assert current_denied_profile.manifest_profile_sha256 != (
        cached_profile.manifest_profile_sha256
    )
    current_profile_query = {
        "manifest_profile_sha256": current_denied_profile.manifest_profile_sha256
    }
    for if_none_match in ("*", cached_profile_response.headers["etag"]):
        current_profile_response = _runtime_api_request(
            runtime_api_env,
            client.get,
            cached_profile_path,
            params=current_profile_query,
            headers={"if-none-match": if_none_match},
        )
        assert current_profile_response.status_code == 409
        assert current_profile_response.json()["code"] == ("authority_surface_admission_blocked")
        decision = current_profile_response.json()["extensions"]["authority_surface_decision"]
        assert decision["purpose"] == "dashboard_display"
        selected_contributor = next(
            row for row in decision["authority_contributors"] if row["basis"] == "selected_manifest"
        )
        assert selected_contributor["authority_boundary_ref"] == (
            "boundary://json-cache-rotation-denied-selected"
        )

    malformed_envelope = persist_view_pair(
        "selected-malformed-envelope",
        default_denied=False,
        selected_denied=False,
        inline_denied=False,
        selected_envelope_kind="runtime.not_authority_envelope",
    )[1]
    malformed_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{malformed_envelope.artifact_id}/content",
        params={"manifest_profile_sha256": malformed_envelope.manifest_profile_sha256},
    )
    assert malformed_response.status_code == 409
    malformed_decision = malformed_response.json()["extensions"]["authority_surface_decision"]
    assert malformed_decision["reason"] == "selected_manifest_authority_resolution_failed"
    malformed_contributor = next(
        row
        for row in malformed_decision["authority_contributors"]
        if row["basis"] == "selected_manifest"
    )
    assert malformed_contributor["resolution_error"] == (
        "selected_manifest_authority_resolution_failed"
    )

    missing_envelope_id = "sha256:" + "f" * 64
    missing_envelope_link = ArtifactAuthorityInfo(
        authority_envelope_ref=missing_envelope_id,
        authority_envelope_manifest_profile_sha256=None,
        diagnostic_event_ref="sha256:" + "2" * 64,
        manifest_ref=f"cas-manifest://{missing_envelope_id}",
        payload_sha256="f" * 64,
    )
    missing_envelope = persist_view_pair(
        "selected-missing-envelope",
        default_denied=False,
        selected_denied=False,
        inline_denied=False,
        selected_authority_link=missing_envelope_link,
    )[1]
    missing_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{missing_envelope.artifact_id}/content",
        params={"manifest_profile_sha256": missing_envelope.manifest_profile_sha256},
    )
    assert missing_response.status_code == 409
    missing_decision = missing_response.json()["extensions"]["authority_surface_decision"]
    assert missing_decision["reason"] == "selected_manifest_authority_resolution_failed"
    missing_contributor = next(
        row
        for row in missing_decision["authority_contributors"]
        if row["basis"] == "selected_manifest"
    )
    assert missing_contributor["resolution_error"] == (
        "selected_manifest_authority_resolution_failed"
    )

    inline_permits = persist_view_pair(
        "inline-permits-selected-denies",
        default_denied=False,
        selected_denied=True,
        inline_denied=False,
    )
    inline_denies = persist_view_pair(
        "inline-denies-selected-permits",
        default_denied=True,
        selected_denied=False,
        inline_denied=True,
    )
    default_inline_permit, selected_inline_deny = inline_permits
    default_inline_deny, selected_inline_permit = inline_denies
    assert (
        _runtime_api_request(
            runtime_api_env,
            client.get,
            f"/api/v1/artifacts/{default_inline_permit.artifact_id}/content",
        ).status_code
        == 200
    )
    selected_inline_deny_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{selected_inline_deny.artifact_id}/content",
        params={"manifest_profile_sha256": selected_inline_deny.manifest_profile_sha256},
    )
    assert selected_inline_deny_response.status_code == 409
    selected_inline_decision = selected_inline_deny_response.json()["extensions"][
        "authority_surface_decision"
    ]
    assert selected_inline_decision["authority_boundary_ref"] == (
        "boundary://inline-permits-selected-denies-selected"
    )
    assert "dashboard_display" in selected_inline_decision["may_not_use_for"]
    selected_inline_contributor = next(
        row
        for row in selected_inline_decision["authority_contributors"]
        if row["basis"] == "selected_manifest"
    )
    assert selected_inline_contributor["authority_boundary_ref"] == (
        "boundary://inline-permits-selected-denies-selected"
    )
    default_inline_deny_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{default_inline_deny.artifact_id}/content",
    )
    assert default_inline_deny_response.status_code == 409
    default_inline_decision = default_inline_deny_response.json()["extensions"][
        "authority_surface_decision"
    ]
    assert default_inline_decision["authority_boundary_ref"] == (
        "boundary://inline-denies-selected-permits-default"
    )
    assert "dashboard_display" in default_inline_decision["may_not_use_for"]
    default_inline_contributors = {
        row["basis"]: row for row in default_inline_decision["authority_contributors"]
    }
    assert default_inline_contributors["base_surface"]["authority_boundary_ref"] == (
        "boundary://inline-inline-denies-selected-permits"
    )
    assert default_inline_contributors["selected_manifest"]["authority_boundary_ref"] == (
        "boundary://inline-denies-selected-permits-default"
    )
    upgraded = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{selected_inline_permit.artifact_id}/content",
        params={"manifest_profile_sha256": selected_inline_permit.manifest_profile_sha256},
    )
    assert upgraded.status_code == 409
    assert upgraded.json()["code"] == "authority_surface_admission_blocked"
    upgraded_decision = upgraded.json()["extensions"]["authority_surface_decision"]
    assert upgraded_decision["status"] == "downgraded"
    assert upgraded_decision["reason"] == "authority_purpose_forbidden"
    assert upgraded_decision["authority_boundary_ref"] == (
        "boundary://inline-inline-denies-selected-permits"
    )
    upgraded_contributors = {
        row["basis"]: row for row in upgraded_decision["authority_contributors"]
    }
    assert upgraded_contributors["base_surface"]["status"] == "downgraded"
    assert upgraded_contributors["base_surface"]["authority_boundary_ref"] == (
        "boundary://inline-inline-denies-selected-permits"
    )
    assert "runtime_closeout_authority" in upgraded_contributors["base_surface"]["may_not_use_for"]
    assert upgraded_contributors["selected_manifest"]["status"] == "allowed"
    assert upgraded_contributors["selected_manifest"]["reason"] == (
        "authority_boundary_allows_surface_purpose"
    )
    assert upgraded_contributors["selected_manifest"]["authority_boundary_ref"] == (
        "boundary://inline-denies-selected-permits-selected"
    )
    assert (
        "runtime_closeout_authority"
        not in upgraded_contributors["selected_manifest"]["may_not_use_for"]
    )


def test_default_json_content_and_schema_carry_one_bounded_manifest_selection(
    runtime_api_env, monkeypatch
) -> None:
    artifact_id = runtime_api_env["workflow_report_artifact_id"]
    client = runtime_api_env["client"]
    expected_selector = ArtifactID.model_validate(artifact_id)
    original_reader = artifact_routes.read_core_manifest_profile_bounded
    calls: list[dict[str, object]] = []

    def observe_bounded_selection(store, selector, **kwargs):
        assert selector == expected_selector
        calls.append(dict(kwargs))
        return original_reader(store, selector, **kwargs)

    def forbidden_legacy_resolution(*_args, **_kwargs):
        raise AssertionError("HTTP default JSON inspection must use the bounded selector")

    monkeypatch.setattr(
        artifact_routes, "read_core_manifest_profile_bounded", observe_bounded_selection
    )
    monkeypatch.setattr(
        artifact_routes, "_resolve_raw_artifact_manifest", forbidden_legacy_resolution
    )
    monkeypatch.setattr(artifact_routes, "_resolve_artifact_manifest", forbidden_legacy_resolution)

    content = client.get(f"/api/v1/artifacts/{artifact_id}/content")
    schema = client.get(f"/api/v1/artifacts/{artifact_id}/schema")
    assert content.status_code == 200, content.text
    assert schema.status_code == 200, schema.text
    assert calls == [
        {
            "max_manifest_bytes": artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES,
            "manifest_profile_sha256": None,
            "allow_profile_absent": True,
        },
        {
            "max_manifest_bytes": artifact_routes.INSPECTOR_MANIFEST_MAX_BYTES,
            "manifest_profile_sha256": None,
            "allow_profile_absent": True,
        },
    ]
