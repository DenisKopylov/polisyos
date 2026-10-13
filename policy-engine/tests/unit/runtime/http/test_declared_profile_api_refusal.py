from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import replace
from typing import Any

import pytest
from _helpers.runtime_http import (
    _put_fixture_authority_envelope,
    _record_fixture_owner,
    _runtime_api_request,
    _runtime_fixture_authority_boundary,
    build_runtime_api_env,
    close_runtime_api_env,
)

from polisyos.core.artifacts import ArtifactRef, PutOptions, SchemaInfo, profile_bound_ref
from polisyos.core.artifacts.manifest import ArtifactAuthorityInfo, CanonInfo, ProducerInfo
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope


@pytest.fixture
def runtime_api_env(tmp_path):
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def test_semantic_views_refuse_selected_profile_mismatch_and_raw_accept_preserves_bytes(
    runtime_api_env,
) -> None:
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    kind = "test.profile_refusal"
    boundary_id = "boundary-profile-refusal-api"
    payload_bytes = to_canonical_bytes(
        {
            **_runtime_fixture_authority_boundary(boundary_id=boundary_id),
            "fraction": 1.5,
        },
        CanonSpec(forbid_floats=False),
    )
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
            producer_version="profile-refusal-v1",
        )
        authority = ArtifactAuthorityInfo(
            authority_envelope_ref=str(envelope_ref.artifact_id),
            authority_envelope_manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
            diagnostic_event_ref=f"event://tests/runtime-api/{boundary_id}",
            manifest_ref=f"cas-manifest://{payload_ref}",
            payload_sha256=payload_sha256,
        )
        producer = ProducerInfo(component="tests.profile_refusal", version="1")
        common_options = {
            "kind": kind,
            "media_type": "application/json",
            "schema": SchemaInfo(name=kind, version="1"),
            "producer": producer,
            "authority": authority,
        }
        conformant = profile_bound_ref(
            store,
            store.put_bytes(
                payload_bytes,
                PutOptions(**common_options, canon=CanonInfo(forbid_floats=False)),
            ),
        )
        mismatched = profile_bound_ref(
            store,
            store.put_bytes(
                payload_bytes,
                PutOptions(**common_options, canon=CanonInfo(forbid_floats=True)),
            ),
        )

    assert conformant.artifact_id == mismatched.artifact_id
    assert conformant.manifest_profile_sha256 != mismatched.manifest_profile_sha256
    _record_fixture_owner(
        store,
        envelope_ref,
        conformant,
        mismatched,
        tenant_id=tenant_id,
        cell_id=cell_id,
        runtime_api_env=runtime_api_env,
    )

    base_path = f"/api/v1/artifacts/{conformant.artifact_id}"
    content = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/content",
        params={"manifest_profile_sha256": conformant.manifest_profile_sha256},
    )
    assert content.status_code == 200, content.text
    assert content.json()["artifact"]["canon_read_status"] == "declared_bytes_conformant"

    schema = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/schema",
        params={"manifest_profile_sha256": conformant.manifest_profile_sha256},
    )
    assert schema.status_code == 200, schema.text
    assert schema.json()["schema"]["canon_read_status"] == "declared_bytes_conformant"

    render = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].post,
        f"{base_path}/render",
        json={
            "genre": "postanova_kmu",
            "manifest_profile_sha256": conformant.manifest_profile_sha256,
        },
    )
    assert render.status_code == 200, render.text
    assert render.json()["document"]["metadata"]["canon_read_status"] == (
        "declared_bytes_conformant"
    )

    export = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/export",
        params={"manifest_profile_sha256": conformant.manifest_profile_sha256},
    )
    assert export.status_code == 200, export.text
    assert export.json()["metadata"]["canon_read_status"] == "declared_bytes_conformant"
    assert 'name="polisyos:canon-read-status" content="declared_bytes_conformant"' in (
        export.json()["content"]
    )

    # Same bytes and content ID, different selected CanonInfo: removing the byte/profile
    # conformance check while retaining status fields would make these semantic reads green.
    mismatch_profile = {"manifest_profile_sha256": mismatched.manifest_profile_sha256}
    semantic = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/content",
        params=mismatch_profile,
    )
    assert semantic.status_code == 409, semantic.text
    assert semantic.json()["code"] == "canon_profile_payload_nonconformant"

    schema_refusal = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/schema",
        params=mismatch_profile,
    )
    assert schema_refusal.status_code == 409, schema_refusal.text
    assert schema_refusal.json()["code"] == "canon_profile_payload_nonconformant"

    render_refusal = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].post,
        f"{base_path}/render",
        json={
            "genre": "postanova_kmu",
            "manifest_profile_sha256": mismatched.manifest_profile_sha256,
        },
    )
    assert render_refusal.status_code == 409, render_refusal.text
    assert render_refusal.json()["code"] == "canon_profile_payload_nonconformant"

    export_refusal = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/export",
        params=mismatch_profile,
    )
    assert export_refusal.status_code == 409, export_refusal.text
    assert export_refusal.json()["code"] == "canon_profile_payload_nonconformant"

    raw = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/content",
        params=mismatch_profile,
        headers={"Accept": "application/octet-stream"},
    )
    assert raw.status_code == 200, raw.text
    assert raw.content == payload_bytes


def test_quantity_and_fabric_routes_refuse_the_selected_packet_profile(
    runtime_api_env, monkeypatch
) -> None:
    app = runtime_api_env["app"]
    context = app.state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    assert run.decision_packet_ref is not None
    store = context.store
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selected_manifest = store.get_manifest(run.decision_packet_ref)
        selected_payload = store.get_bytes(run.decision_packet_ref)
        assert selected_manifest.canon is not None
        assert selected_manifest.canon.forbid_floats is False
        mismatch_ref = profile_bound_ref(
            store,
            store.put_bytes(
                selected_payload,
                PutOptions(
                    kind=selected_manifest.kind,
                    media_type=selected_manifest.media_type,
                    schema=selected_manifest.artifact_schema,
                    producer=selected_manifest.producer,
                    env=selected_manifest.env,
                    inputs=selected_manifest.inputs,
                    canon=selected_manifest.canon.model_copy(
                        update={"forbid_floats": True}
                    ),
                    governance=selected_manifest.governance,
                    tenant_context=selected_manifest.tenant_context,
                    same_input_closure=selected_manifest.same_input_closure,
                    authority=selected_manifest.authority,
                    warnings=selected_manifest.warnings,
                ),
            ),
        )
    bad_run = replace(run, decision_packet_ref=mismatch_ref)
    monkeypatch.setattr(context.run_index, "get_run", lambda _run_id: bad_run)

    for suffix in ("quantities", "fabric-decision-data"):
        response = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"/api/v1/runs/{run_id}/{suffix}",
        )
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "canon_profile_payload_nonconformant"


def test_debug_workflow_and_public_verification_refuse_profile_mismatch(
    runtime_api_env, monkeypatch
) -> None:
    context = runtime_api_env["app"].state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    assert run.decision_packet_ref is not None
    store = context.store
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selected_manifest = store.get_manifest(run.decision_packet_ref)
        bad_payload = to_canonical_bytes(
            {"nodes": [], "workflow_id": "debug-profile-test", "fraction": 1.5},
            CanonSpec(forbid_floats=False),
        )
        bad_ref = store.put_bytes(
            bad_payload,
            PutOptions(
                kind="scientist.workflow_report",
                media_type="application/json",
                schema=SchemaInfo(name="test.WorkflowReport", version="1"),
                canon=CanonInfo(forbid_floats=True),
                tenant_context=selected_manifest.tenant_context,
            ),
        )
        decision_bytes = store.get_bytes(run.decision_packet_ref)
        bad_decision_ref = profile_bound_ref(
            store,
            store.put_bytes(
                decision_bytes,
                PutOptions(
                kind=selected_manifest.kind,
                media_type=selected_manifest.media_type,
                schema=selected_manifest.artifact_schema,
                producer=selected_manifest.producer,
                env=selected_manifest.env,
                inputs=selected_manifest.inputs,
                canon=selected_manifest.canon.model_copy(update={"forbid_floats": True}),
                governance=selected_manifest.governance,
                tenant_context=selected_manifest.tenant_context,
                same_input_closure=selected_manifest.same_input_closure,
                authority=selected_manifest.authority,
                    warnings=selected_manifest.warnings,
                ),
            ),
        )
    monkeypatch.setattr(
        context.run_index,
        "get_run",
        lambda _run_id: replace(
            run, workflow_report_ref=bad_ref, decision_packet_ref=bad_decision_ref
        ),
    )

    debug_response = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/workflow",
    )
    assert debug_response.status_code == 409, debug_response.text
    assert debug_response.json()["code"] == "canon_profile_payload_nonconformant"

    from polisyos.core.security.identity import PolicyOSRole
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
    )

    admin_client, cell, provider = _build_secure_client(
        runtime_api_env, opa_client=_AllowOPA(), claims_by_token={}
    )
    provider.put_claim(
        "canon-profile-admin",
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="canon-profile-admin",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    admin_context = admin_client.app.state.runtime_api_ctx
    monkeypatch.setattr(
        admin_context.run_index,
        "get_run",
        lambda _run_id: replace(
            run, workflow_report_ref=bad_ref, decision_packet_ref=bad_decision_ref
        ),
    )
    from polisyos.core.artifacts import FileSystemCAS

    owner_store = FileSystemCAS(runtime_api_env["cas_root"])
    _record_fixture_owner(
        owner_store,
        bad_ref,
        bad_decision_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
    )
    from polisyos.common.canonical_profile import (
        CanonicalProfileRefusalError,
    )
    from polisyos.core.artifacts.canonical_profile import read_core_json_artifact

    with (
        tenant_scope(None, tenant_id=runtime_api_env["tenant_a"], cell_id=cell.cell_id),
        pytest.raises(
            CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"
        ),
    ):
        read_core_json_artifact(admin_context.store, bad_decision_ref)
    with admin_client:
        public_response = admin_client.post(
            f"/api/v1/runs/{run_id}/public-verification-record",
            headers={"Authorization": "Bearer canon-profile-admin"},
        )
    assert public_response.status_code == 409, public_response.text
    assert public_response.json()["code"] == "canon_profile_payload_nonconformant"
    assert (
        admin_client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
        == ()
    )

    import json

    selected_profile_path = admin_context.store._manifest_path_for_ref(
        bad_decision_ref.artifact_id,
        bad_decision_ref.manifest_profile_sha256,
    )
    current_sidecar = json.loads(selected_profile_path.read_bytes())
    current_sidecar.pop("canon")
    selected_profile_path.write_text(json.dumps(current_sidecar, sort_keys=True), encoding="utf-8")
    with admin_client:
        profileless_response = admin_client.post(
            f"/api/v1/runs/{run_id}/public-verification-record",
            headers={"Authorization": "Bearer canon-profile-admin"},
        )
    assert profileless_response.status_code == 409, profileless_response.text
    assert profileless_response.json()["code"] == "canon_profile_absent"
    assert (
        admin_client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
        == ()
    )



def _remove_one_required_canon_field(store, artifact_id: str) -> None:
    import json

    from polisyos.core.artifacts import ArtifactID

    path = store._manifest_path_for_ref(ArtifactID.model_validate(artifact_id), None)
    manifest = json.loads(path.read_bytes())
    manifest["canon"].pop("separators")
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_analysis_and_scenario_semantic_gets_refuse_malformed_present_profiles(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    context = runtime_api_env["app"].state.runtime_api_ctx
    store = context.store

    analysis = _runtime_api_request(
        runtime_api_env,
        client.post,
        "/api/v1/analysis/attractors",
        json={
            "variable_ids": ["income", "wealth"],
            "trajectory": [[1.0, 2.0] for _ in range(12)],
            "tolerance": 1.0e-8,
            "rtol": 0.0,
            "persist_artifact": True,
        },
    )
    assert analysis.status_code == 200, analysis.text
    analysis_ref = analysis.json()["analysis_result_ref"]
    _remove_one_required_canon_field(store, analysis_ref["artifact_id"])
    analysis_read = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/analysis/{analysis_ref['artifact_id']}",
    )
    assert analysis_read.status_code == 409, analysis_read.text
    assert analysis_read.headers["content-type"].startswith("application/problem+json")
    assert analysis_read.json()["code"] == "canon_profile_incomplete"

    run_id = runtime_api_env["core_run_id"]
    listed = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{run_id}/scenarios",
    )
    assert listed.status_code == 200, listed.text
    scenario = listed.json()["scenarios"][0]
    scenario_artifact_ref = context.scenarios._artifact_by_id[scenario["id"]]
    _remove_one_required_canon_field(store, scenario_artifact_ref)
    scenario_read = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/scenarios/{scenario['id']}",
    )
    assert scenario_read.status_code == 409, scenario_read.text
    assert scenario_read.headers["content-type"].startswith("application/problem+json")
    assert scenario_read.json()["code"] == "canon_profile_incomplete"


def test_raw_artifact_responses_keep_exact_bytes_when_profile_is_incomplete(
    runtime_api_env,
) -> None:
    from polisyos.core.artifacts import CanonInfo, PutOptions
    from polisyos.core.canon.canon_json import to_canonical_bytes

    client = runtime_api_env["client"]
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    payload = to_canonical_bytes({"raw": "exact bytes"})
    ref = store.put_bytes(
        payload,
        PutOptions(
            kind="test.raw_profile_bytes",
            media_type="application/json",
            canon=CanonInfo(),
        ),
    )
    _remove_one_required_canon_field(store, str(ref.artifact_id))

    content = client.get(
        f"/api/v1/artifacts/{ref.artifact_id}/content",
        headers={"accept": "application/octet-stream"},
    )
    assert content.status_code == 200, content.text
    assert content.content == payload
    assert content.headers["content-type"].startswith("application/json")

    download = client.get(f"/api/v1/artifacts/{ref.artifact_id}/download")
    assert download.status_code == 200, download.text
    assert download.content == payload

    semantic = client.get(f"/api/v1/artifacts/{ref.artifact_id}/content")
    assert semantic.status_code == 409, semantic.text
    assert semantic.headers["content-type"].startswith("application/problem+json")
    assert semantic.json()["code"] == "canon_profile_incomplete"


def _put_inspector_profile_fixture(
    runtime_api_env: dict[str, Any],
    *,
    kind: str,
    media_type: str,
    payload_bytes: bytes,
    schema: SchemaInfo,
    canon: CanonInfo | None,
) -> ArtifactRef:
    """Persist one locally owned API fixture with the requested exact profile state."""
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    payload_ref = f"sha256:{payload_sha256}"
    boundary_id = f"boundary-{kind.replace('.', '-')}-{payload_sha256[:8]}"
    boundary = {
        **_runtime_fixture_authority_boundary(boundary_id=boundary_id),
        "subject_ref": payload_ref,
        "subject_kind": kind,
    }

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        envelope_ref = _put_fixture_authority_envelope(
            store,
            boundary,
            producer_version="inspector-profile-r4",
        )
        authority = ArtifactAuthorityInfo(
            authority_envelope_ref=str(envelope_ref.artifact_id),
            authority_envelope_manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
            diagnostic_event_ref=f"event://tests/runtime-api/{boundary_id}",
            manifest_ref=f"cas-manifest://{payload_ref}",
            payload_sha256=payload_sha256,
        )
        options: dict[str, Any] = {
            "kind": kind,
            "media_type": media_type,
            "schema": schema,
            "producer": ProducerInfo(component="tests.inspector_profile", version="1"),
            "authority": authority,
        }
        if canon is not None:
            options["canon"] = canon
        selected = profile_bound_ref(
            store,
            store.put_bytes(payload_bytes, PutOptions(**options)),
        )

    _record_fixture_owner(
        store,
        envelope_ref,
        selected,
        tenant_id=tenant_id,
        cell_id=cell_id,
        runtime_api_env=runtime_api_env,
    )
    return selected


def test_inspector_refusal_family_preserves_raw_and_non_json_semantics(runtime_api_env) -> None:
    """Exercise typed refusal and representation behavior through the actual API routes."""
    app = runtime_api_env["app"]
    context = app.state.runtime_api_ctx
    client = runtime_api_env["client"]
    report_bytes = to_canonical_bytes({"schema_version": "1.0"})
    absent = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="ir.backtest_report",
        media_type="application/json",
        payload_bytes=report_bytes,
        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        canon=None,
    )
    unknown = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="ir.backtest_report",
        media_type="application/json",
        payload_bytes=to_canonical_bytes({"schema_version": "1.0", "marker": "unknown"}),
        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        canon=CanonInfo(version="0.3.0"),
    )

    for ref, expected_code in (
        (absent, "canon_profile_absent"),
        (unknown, "canon_profile_not_verified"),
    ):
        params = {"manifest_profile_sha256": ref.manifest_profile_sha256}
        base_path = f"/api/v1/artifacts/{ref.artifact_id}"
        for suffix in ("content", "schema"):
            response = _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{base_path}/{suffix}",
                params=params,
            )
            assert response.status_code == 409, response.text
            assert response.headers["content-type"].startswith("application/problem+json")
            assert response.json()["code"] == expected_code

        raw = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"{base_path}/content",
            params=params,
            headers={"Accept": "application/octet-stream"},
        )
        assert raw.status_code == 200, raw.text
        assert raw.content == (
            report_bytes if ref is absent else to_canonical_bytes(
                {"schema_version": "1.0", "marker": "unknown"}
            )
        )

    app.state.runtime_api_ctx = replace(
        context,
        allow_candidate_predictive_diagnostic_surface=True,
    )
    diagnostic = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{unknown.artifact_id}/predictive-coverage-diagnostic",
        params={"manifest_profile_sha256": unknown.manifest_profile_sha256},
    )
    assert diagnostic.status_code == 409, diagnostic.text
    assert diagnostic.headers["content-type"].startswith("application/problem+json")
    assert diagnostic.json()["code"] == "canon_profile_not_verified"

    binary_payload = b'{"valid_utf8":"still_binary"}'
    binary = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.opaque_binary_preview",
        media_type="application/octet-stream",
        payload_bytes=binary_payload,
        schema=SchemaInfo(name="test.opaque_binary_preview", version="1"),
        canon=CanonInfo(),
    )
    binary_view = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{binary.artifact_id}/content",
        params={"manifest_profile_sha256": binary.manifest_profile_sha256},
    )
    assert binary_view.status_code == 200, binary_view.text
    binary_artifact = binary_view.json()["artifact"]
    assert binary_artifact["mode"] == "binary"
    assert binary_artifact["canon_read_status"] == "not_applicable"
    assert binary_artifact["preview"] == binary_payload.hex()

    text_payload = b"ordinary UTF-8 text"
    text_ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.text_preview",
        media_type="text/plain",
        payload_bytes=text_payload,
        schema=SchemaInfo(name="test.text_preview", version="1"),
        canon=CanonInfo(),
    )
    text_view = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{text_ref.artifact_id}/content",
        params={"manifest_profile_sha256": text_ref.manifest_profile_sha256},
    )
    assert text_view.status_code == 200, text_view.text
    text_artifact = text_view.json()["artifact"]
    assert text_artifact["mode"] == "text"
    assert text_artifact["canon_read_status"] == "not_applicable"
    assert text_artifact["preview"] == text_payload.decode("utf-8")


def test_predictive_diagnostic_caps_actual_selected_bytes_before_codec(runtime_api_env, monkeypatch) -> None:
    """The cap checks exact payload bytes before Core canonical decoding."""
    import json

    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.core.artifacts import canonical_profile as core_profile
    from polisyos.runtime.http.services.artifact_inspector import (
        _MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES,
    )

    payload = b" " * (_MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES + 1)
    ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="ir.backtest_report",
        media_type="application/json",
        payload_bytes=payload,
        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        canon=CanonInfo(),
    )
    context = runtime_api_env["app"].state.runtime_api_ctx
    base_store = context.artifacts._store

    class SmallManifestHintStore:
        """Preserve the selected profile and exact blob while understating size metadata."""

        def __init__(self, wrapped):
            self._wrapped = wrapped
            self.payload_reads = 0

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

        @staticmethod
        def _small(manifest):
            return manifest.model_copy(update={"byte_size": 1})

        def get_manifest(self, selector):
            return self._small(self._wrapped.get_manifest(selector))

        def get_manifest_by_profile(self, artifact_id, manifest_profile_sha256):
            resolver = getattr(self._wrapped, "get_manifest_by_profile", None)
            if callable(resolver):
                manifest = resolver(artifact_id, manifest_profile_sha256)
            else:
                manifest = self._wrapped.get_manifest(artifact_id)
            selected = self._small(manifest)
            if artifact_manifest_profile_sha256(selected) != manifest_profile_sha256:
                raise FileNotFoundError("selected profile is unavailable")
            return selected

        def get_raw_manifest_bytes(self, selector, *, manifest_profile_sha256=None):
            artifact_id = getattr(selector, "artifact_id", selector)
            if manifest_profile_sha256 is None:
                manifest = self.get_manifest(artifact_id)
            else:
                manifest = self.get_manifest_by_profile(artifact_id, manifest_profile_sha256)
            raw = json.dumps(manifest.model_dump(mode="json", by_alias=True), sort_keys=True).encode("utf-8")
            return raw

        def get_bytes(self, selector):
            self.payload_reads += 1
            return self._wrapped.get_bytes(selector)

    bounded_store = SmallManifestHintStore(base_store)
    monkeypatch.setattr(context.artifacts, "_store", bounded_store)

    def decoder_must_not_run(*_args, **_kwargs):
        raise AssertionError("oversized selected payload entered the canonical decoder")

    monkeypatch.setattr(core_profile, "from_canonical_bytes", decoder_must_not_run)
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        preview = context.artifacts.get_predictive_coverage_diagnostic(ref.artifact_id)

    assert preview is None
    assert bounded_store.payload_reads == 1
    assert len(payload) == _MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES + 1


def test_predictive_diagnostic_decodes_actual_bytes_below_source_cap(runtime_api_env, monkeypatch) -> None:
    """The capped path retains a conformant in-limit decode and round trip."""
    from polisyos.core.artifacts import canonical_profile as core_profile

    decode = core_profile.from_canonical_bytes
    encode = core_profile.to_canonical_bytes
    decode_calls: list[int] = []
    encode_calls: list[int] = []

    def observe_decode(raw, *args, **kwargs):
        decode_calls.append(len(raw))
        return decode(raw, *args, **kwargs)

    def observe_encode(value, *args, **kwargs):
        encode_calls.append(1)
        return encode(value, *args, **kwargs)

    monkeypatch.setattr(core_profile, "from_canonical_bytes", observe_decode)
    monkeypatch.setattr(core_profile, "to_canonical_bytes", observe_encode)
    payload = to_canonical_bytes({"schema_version": "1.0"})
    ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="ir.backtest_report",
        media_type="application/json",
        payload_bytes=payload,
        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        canon=CanonInfo(),
    )
    context = runtime_api_env["app"].state.runtime_api_ctx
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        preview = context.artifacts.get_predictive_coverage_diagnostic(ref.artifact_id)

    assert preview is not None
    assert decode_calls == [len(payload)]
    assert encode_calls


def test_content_preview_caps_actual_selected_bytes_before_codec(runtime_api_env, monkeypatch) -> None:
    """Actual truncated bytes never reach the shared decoder or encoder."""
    import json

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.core.artifacts import canonical_profile as core_profile

    limit = 1024
    prefix = b'{"large":"'
    suffix = b'"}'
    large_payload = prefix + b"x" * (limit + 1 - len(prefix) - len(suffix)) + suffix
    assert len(large_payload) == limit + 1
    small_payload = to_canonical_bytes({"small": "selected bytes"})
    large_ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.preview_cap_large",
        media_type="application/json",
        payload_bytes=large_payload,
        schema=SchemaInfo(name="test.preview_cap_large", version="1"),
        canon=CanonInfo(),
    )
    small_ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.preview_cap_small",
        media_type="application/json",
        payload_bytes=small_payload,
        schema=SchemaInfo(name="test.preview_cap_small", version="1"),
        canon=CanonInfo(),
    )
    unknown_ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.preview_cap_unknown",
        media_type="application/json",
        payload_bytes=large_payload,
        schema=SchemaInfo(name="test.preview_cap_unknown", version="1"),
        canon=CanonInfo(version="0.3.0"),
    )

    context = runtime_api_env["app"].state.runtime_api_ctx
    service = context.artifacts
    wrapped_store = service._store

    class UnderreportedManifestStore:
        """Keep the selected sidecar profile while falsifying only its size hint."""

        def __init__(self, wrapped):
            self._wrapped = wrapped
            self.payload_reads: dict[str, int] = {}

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

        @staticmethod
        def _underreport(manifest):
            return manifest.model_copy(update={"byte_size": 1})

        def get_manifest(self, selector):
            return self._underreport(self._wrapped.get_manifest(selector))

        def get_manifest_by_profile(self, artifact_id, manifest_profile_sha256):
            resolver = getattr(self._wrapped, "get_manifest_by_profile", None)
            manifest = (
                resolver(artifact_id, manifest_profile_sha256)
                if callable(resolver)
                else self._wrapped.get_manifest(artifact_id)
            )
            selected = self._underreport(manifest)
            if artifact_manifest_profile_sha256(selected) != manifest_profile_sha256:
                raise FileNotFoundError("selected profile is unavailable")
            return selected

        def get_raw_manifest_bytes(self, selector, *, manifest_profile_sha256=None):
            artifact_id = getattr(selector, "artifact_id", selector)
            manifest = (
                self.get_manifest(artifact_id)
                if manifest_profile_sha256 is None
                else self.get_manifest_by_profile(artifact_id, manifest_profile_sha256)
            )
            return json.dumps(
                manifest.model_dump(mode="json", by_alias=True),
                sort_keys=True,
            ).encode("utf-8")

        def get_bytes(self, selector):
            artifact_id = str(getattr(selector, "artifact_id", selector))
            self.payload_reads[artifact_id] = self.payload_reads.get(artifact_id, 0) + 1
            return self._wrapped.get_bytes(selector)

    bounded_store = UnderreportedManifestStore(wrapped_store)
    monkeypatch.setattr(service, "_store", bounded_store)
    monkeypatch.setattr(service, "_assert_surface_admission_allowed", lambda *_args, **_kwargs: None)

    core_decode = core_profile.from_canonical_bytes
    core_encode = core_profile.to_canonical_bytes

    def codec_must_not_run(*_args, **_kwargs):
        raise AssertionError("over-limit content preview entered Core canonical codec")

    monkeypatch.setattr(core_profile, "from_canonical_bytes", codec_must_not_run)
    monkeypatch.setattr(core_profile, "to_canonical_bytes", codec_must_not_run)
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selected_large_manifest = bounded_store.get_manifest(large_ref.artifact_id)
        assert selected_large_manifest.byte_size == 1
        large_preview = service.get_content_preview(
            large_ref.artifact_id,
            max_bytes=limit,
            manifest=selected_large_manifest,
        )

        selected_unknown_manifest = bounded_store.get_manifest(unknown_ref.artifact_id)
        with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
            service.get_content_preview(
                unknown_ref.artifact_id,
                max_bytes=limit,
                manifest=selected_unknown_manifest,
            )

    assert large_preview.truncated is True
    assert large_preview.size_bytes == limit + 1
    assert large_preview.max_bytes == limit
    assert large_preview.mode == "binary"
    assert large_preview.canon_read_status == "not_evaluated"
    assert large_preview.preview == large_payload[:limit].hex()
    assert bounded_store.payload_reads[str(large_ref.artifact_id)] == 1
    assert bounded_store.payload_reads[str(unknown_ref.artifact_id)] == 1

    decode_calls: list[int] = []
    encode_calls: list[int] = []

    def observe_decode(raw, *args, **kwargs):
        decode_calls.append(len(raw))
        return core_decode(raw, *args, **kwargs)

    def observe_encode(value, *args, **kwargs):
        encode_calls.append(1)
        return core_encode(value, *args, **kwargs)

    monkeypatch.setattr(core_profile, "from_canonical_bytes", observe_decode)
    monkeypatch.setattr(core_profile, "to_canonical_bytes", observe_encode)
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selected_small_manifest = bounded_store.get_manifest(small_ref.artifact_id)
        small_preview = service.get_content_preview(
            small_ref.artifact_id,
            max_bytes=limit,
            manifest=selected_small_manifest,
        )

    assert small_preview.truncated is False
    assert small_preview.mode == "json"
    assert small_preview.preview == {"small": "selected bytes"}
    assert small_preview.canon_read_status == "declared_bytes_conformant"
    assert decode_calls == [len(small_payload)]
    assert encode_calls
    assert bounded_store.payload_reads[str(small_ref.artifact_id)] == 1


def test_action_selection_receipt_guard_survives_python_optimized_mode() -> None:
    """The persisted receipt-type refusal remains active under python -O."""
    command = (
        "from polisyos.runtime.http.services.control.run_lifecycle import "
        "_require_action_selection_phase_receipt\n"
        "try:\n"
        "    _require_action_selection_phase_receipt(object())\n"
        "except ValueError as exc:\n"
        "    raise SystemExit(0 if str(exc) == "
        "'acquisition_action_selection_replay_conflict' else 2)\n"
        "raise SystemExit(3)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-O", "-c", command],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
