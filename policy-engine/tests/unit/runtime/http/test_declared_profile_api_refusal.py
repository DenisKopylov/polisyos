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
    _runtime_api_tenant_scope,
    _runtime_fixture_authority_boundary,
    build_runtime_api_env,
    close_runtime_api_env,
)

from polisyos.core.artifacts import (
    ArtifactRef,
    PutOptions,
    SchemaInfo,
    artifact_ref_for_manifest,
    profile_bound_ref,
)
from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    CanonInfo,
    ProducerInfo,
    WarningRecord,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope


@pytest.fixture
def runtime_api_env(tmp_path):
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


class _OwnedArtifactUnavailableStore:
    """Simulate disappearance only after the wrapped CAS admits the exact read."""

    def __init__(self, wrapped: Any, ref: ArtifactRef) -> None:
        self._wrapped = wrapped
        self._artifact_id = str(ref.artifact_id)
        self.checked_manifest_profiles: list[str | None] = []
        self.checked_payload_reads = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def _matches(self, selector: object) -> bool:
        return str(getattr(selector, "artifact_id", selector)) == self._artifact_id

    def get_raw_manifest_bytes(
        self, selector: object, *, manifest_profile_sha256: str | None = None
    ) -> bytes:
        if not self._matches(selector):
            return self._wrapped.get_raw_manifest_bytes(
                selector, manifest_profile_sha256=manifest_profile_sha256
            )
        self._wrapped.get_raw_manifest_bytes(
            selector, manifest_profile_sha256=manifest_profile_sha256
        )
        profile = manifest_profile_sha256
        if profile is None:
            profile = getattr(selector, "manifest_profile_sha256", None)
        self.checked_manifest_profiles.append(profile)
        raise FileNotFoundError("fixture simulates loss after the owner-gated read")

    def get_bytes(self, selector: object) -> bytes:
        if not self._matches(selector):
            return self._wrapped.get_bytes(selector)
        self._wrapped.get_bytes(selector)
        self.checked_payload_reads += 1
        raise FileNotFoundError("fixture simulates loss after the owner-gated read")


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
    assert (
        'name="polisyos:canon-read-status" content="declared_bytes_conformant"'
        in (export.json()["content"])
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
    raw_download = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/download",
        params=mismatch_profile,
    )
    assert raw_download.status_code == 200, raw_download.text
    assert raw_download.content == payload_bytes


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
                    canon=selected_manifest.canon.model_copy(update={"forbid_floats": True}),
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


def test_fabric_route_translates_late_source_contract_refusal(
    runtime_api_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    app = runtime_api_env["app"]
    context = app.state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    if run.decision_packet_ref is None:
        pytest.fail("fixture run has no decision packet")
    store = context.store
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selected = store.get_manifest(run.decision_packet_ref)
        payload = store.get_bytes(run.decision_packet_ref)
        if selected.canon is None:
            pytest.fail("fixture packet has no selected canonical profile")
        bad_ref = profile_bound_ref(
            store,
            store.put_bytes(
                payload,
                PutOptions(
                    kind=selected.kind,
                    media_type=selected.media_type,
                    schema=selected.artifact_schema,
                    producer=selected.producer,
                    env=selected.env,
                    inputs=selected.inputs,
                    canon=selected.canon.model_copy(update={"forbid_floats": True}),
                    governance=selected.governance,
                    tenant_context=selected.tenant_context,
                    same_input_closure=selected.same_input_closure,
                    authority=selected.authority,
                    warnings=selected.warnings,
                ),
            ),
        )
    bad_run = replace(run, decision_packet_ref=bad_ref)
    monkeypatch.setattr(context.run_index, "get_run", lambda _run_id: bad_run)
    # Force the route past its earlier quantity read; the later selected-packet
    # source-contract read must still be translated to the same typed HTTP refusal.
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        valid_inventory = context.lineage.build_quantity_inventory_for_run(run)
    monkeypatch.setattr(
        context.lineage,
        "build_quantity_inventory_for_run",
        lambda _run: valid_inventory,
    )
    response = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/fabric-decision-data",
    )
    if response.status_code != 409:
        pytest.fail(
            f"late source-contract refusal returned {response.status_code}: {response.text}"
        )
    if response.json().get("code") != "canon_profile_payload_nonconformant":
        pytest.fail(f"unexpected source-contract refusal body: {response.text}")


def test_debug_workflow_and_public_verification_refuse_profile_mismatch(
    runtime_api_env, monkeypatch
) -> None:
    context = runtime_api_env["app"].state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    assert run.decision_packet_ref is not None
    store = context.store
    baseline_workflow = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/workflow",
    )
    assert baseline_workflow.status_code == 200, baseline_workflow.text
    baseline_nodes = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/nodes",
    )
    assert baseline_nodes.status_code == 200, baseline_nodes.text
    node_alias = baseline_nodes.json()["nodes"][0]["alias"]

    assert run.workflow_report_ref is not None
    missing_refs = (None, run.workflow_report_ref)
    for missing_ref in missing_refs:
        unavailable_store = None
        if missing_ref is None:
            monkeypatch.setattr(context.debug, "_store", store)
        else:
            unavailable_store = _OwnedArtifactUnavailableStore(store, missing_ref)
            monkeypatch.setattr(context.debug, "_store", unavailable_store)
        missing_run = replace(run, workflow_report_ref=missing_ref)
        monkeypatch.setattr(
            context.run_index,
            "get_run",
            lambda _run_id, missing_run=missing_run: missing_run,
        )
        missing_workflow = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"/api/v1/runs/{run_id}/workflow",
        )
        assert missing_workflow.status_code == 200, missing_workflow.text
        missing_notes = missing_workflow.json()["workflow"]["notes"]
        assert "workflow_report_missing_or_unavailable" in missing_notes
        missing_nodes = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"/api/v1/runs/{run_id}/nodes",
        )
        assert missing_nodes.status_code == 200, missing_nodes.text
        assert "workflow_report_missing_or_unavailable" in missing_nodes.json()["notes"]
        missing_errors = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"/api/v1/debug/runs/{run_id}/errors",
        )
        assert missing_errors.status_code == 200, missing_errors.text
        assert "workflow_report_missing_or_unavailable" in missing_errors.json()["notes"]
        if unavailable_store is not None:
            assert missing_ref.manifest_profile_sha256 is not None
            assert (
                missing_ref.manifest_profile_sha256 in unavailable_store.checked_manifest_profiles
            )
            assert None in unavailable_store.checked_manifest_profiles
            assert unavailable_store.checked_payload_reads >= 1

    monkeypatch.setattr(context.run_index, "get_run", lambda _run_id: run)
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selected_manifest = store.get_manifest(run.decision_packet_ref)
        bad_payload = to_canonical_bytes(
            {"nodes": [], "workflow_id": "debug-profile-test", "fraction": 1.5},
            CanonSpec(forbid_floats=False),
        )
        bad_ref = profile_bound_ref(
            store,
            store.put_bytes(
                bad_payload,
                PutOptions(
                    kind="scientist.workflow_report",
                    media_type="application/json",
                    schema=SchemaInfo(name="test.WorkflowReport", version="1"),
                    canon=CanonInfo(forbid_floats=True),
                    tenant_context=selected_manifest.tenant_context,
                ),
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
    _record_fixture_owner(
        store,
        bad_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )
    monkeypatch.setattr(
        context.run_index,
        "get_run",
        lambda _run_id: replace(
            run, workflow_report_ref=bad_ref, decision_packet_ref=bad_decision_ref
        ),
    )

    original_raw_manifest = store.get_raw_manifest_bytes

    def missing_selected_view(selector, *, manifest_profile_sha256=None):
        selected_id = str(getattr(selector, "artifact_id", selector))
        selected_profile = manifest_profile_sha256 or getattr(
            selector, "manifest_profile_sha256", None
        )
        if (
            selected_id == str(bad_ref.artifact_id)
            and selected_profile == bad_ref.manifest_profile_sha256
        ):
            original_raw_manifest(selector, manifest_profile_sha256=manifest_profile_sha256)
            raise FileNotFoundError("selected profile view is unavailable")
        return original_raw_manifest(
            selector,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    monkeypatch.setattr(store, "get_raw_manifest_bytes", missing_selected_view)
    unavailable_view = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/workflow",
    )
    assert unavailable_view.status_code == 409, unavailable_view.text
    assert unavailable_view.json()["code"] == "canon_profile_selection_unverified"
    monkeypatch.setattr(store, "get_raw_manifest_bytes", original_raw_manifest)

    original_get_bytes = store.get_bytes

    def missing_payload(selector):
        selected_id = str(getattr(selector, "artifact_id", selector))
        if selected_id == str(bad_ref.artifact_id):
            original_get_bytes(selector)
            raise FileNotFoundError("selected payload is unavailable")
        return original_get_bytes(selector)

    monkeypatch.setattr(store, "get_bytes", missing_payload)
    missing_payload_view = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/workflow",
    )
    assert missing_payload_view.status_code == 409, missing_payload_view.text
    assert missing_payload_view.json()["code"] == "canon_profile_payload_unavailable"
    monkeypatch.setattr(store, "get_bytes", original_get_bytes)

    debug_response = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/workflow",
    )
    assert debug_response.status_code == 409, debug_response.text
    assert debug_response.json()["code"] == "canon_profile_payload_nonconformant"

    _remove_one_required_canon_field(
        store,
        str(bad_ref.artifact_id),
        bad_ref.manifest_profile_sha256,
    )
    for sibling_path in (
        f"/api/v1/runs/{run_id}/workflow",
        f"/api/v1/runs/{run_id}/nodes",
        f"/api/v1/debug/runs/{run_id}/nodes/{node_alias}",
        f"/api/v1/debug/runs/{run_id}/errors",
    ):
        sibling = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            sibling_path,
        )
        assert sibling.status_code == 409, sibling.text
        assert sibling.json()["code"] == "canon_profile_incomplete"

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
        pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"),
    ):
        read_core_json_artifact(admin_context.store, bad_decision_ref)
    import json

    with admin_client:
        public_response = admin_client.post(
            f"/api/v1/runs/{run_id}/public-verification-record",
            headers={"Authorization": "Bearer canon-profile-admin"},
        )
        assert public_response.status_code == 409, public_response.text
        assert public_response.json()["code"] == "canon_profile_payload_nonconformant"
        assert public_response.json()["error"] == "conflict"
        assert public_response.json()["detail"] == "canon_profile_payload_nonconformant"
        assert public_response.json()["status"] == 409
        assert (
            admin_client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )

        selected_profile_path = owner_store._manifest_path_for_ref(
            bad_decision_ref.artifact_id,
            bad_decision_ref.manifest_profile_sha256,
        )
        current_sidecar = json.loads(selected_profile_path.read_bytes())
        current_sidecar.pop("canon")
        selected_profile_path.write_text(
            json.dumps(current_sidecar, sort_keys=True), encoding="utf-8"
        )

        profileless_response = admin_client.post(
            f"/api/v1/runs/{run_id}/public-verification-record",
            headers={"Authorization": "Bearer canon-profile-admin"},
        )
        assert profileless_response.status_code == 409, profileless_response.text
        assert profileless_response.json()["code"] == "canon_profile_absent"
        assert profileless_response.json()["error"] == "conflict"
        assert profileless_response.json()["detail"] == "canon_profile_absent"
        assert profileless_response.json()["status"] == 409
        assert (
            admin_client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )


def _remove_one_required_canon_field(
    store,
    artifact_id: str,
    manifest_profile_sha256: str | None = None,
) -> None:
    import json

    from polisyos.core.artifacts import ArtifactID

    path = store._manifest_path_for_ref(
        ArtifactID.model_validate(artifact_id),
        manifest_profile_sha256,
    )
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
    analysis_ref = ArtifactRef.model_validate(analysis.json()["analysis_result_ref"])
    _record_fixture_owner(
        store,
        analysis_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )
    analysis_baseline = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/analysis/{analysis_ref.artifact_id}",
    )
    assert analysis_baseline.status_code == 200, analysis_baseline.text
    _remove_one_required_canon_field(
        store,
        str(analysis_ref.artifact_id),
        analysis_ref.manifest_profile_sha256,
    )
    analysis_read = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/analysis/{analysis_ref.artifact_id}",
    )
    assert analysis_read.status_code == 409, analysis_read.text
    assert analysis_read.headers["content-type"].startswith("application/problem+json")
    assert analysis_read.json()["code"] == "canon_profile_incomplete"

    run_id = runtime_api_env["core_run_id"]
    quantities = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{run_id}/quantities",
    )
    assert quantities.status_code == 200, quantities.text
    quantity = next(
        item for item in quantities.json()["quantities"] if item["metric_id"] == "policy_cost"
    )
    scenario_create = _runtime_api_request(
        runtime_api_env,
        client.post,
        f"/api/v1/runs/{run_id}/scenarios",
        json={
            "id": "scn_canon_profile_api_refusal",
            "policy_question": "What if policy cost is capped?",
            "author": "test-operator",
            "model_family": "operator-specified",
            "interventions": [
                {
                    "field": "policy_cost",
                    "operator": "set",
                    "value": quantity,
                    "baseline_value": quantity,
                    "constraint_ids": [],
                }
            ],
            "assumptions": [
                {
                    "id": "asm_canon_profile_api_refusal",
                    "label": "No behavior change",
                    "status": "operator_assumption",
                    "lineage": {
                        "id": "scenario:canon-profile-api-refusal:assumption",
                        "status": "pending",
                        "freshness": "current",
                        "summary": {"source": "test"},
                    },
                }
            ],
        },
    )
    assert scenario_create.status_code == 200, scenario_create.text
    scenario = scenario_create.json()["scenario"]
    scenario_id = scenario["id"]
    head = context.scenarios.get_persisted_head_or_none(scenario_id)
    assert head is not None
    assert head.baseline_run_id == run_id
    assert head.revision == scenario["revision"]
    assert head.manifest_hash == scenario["manifest_hash"]

    from polisyos.core.artifacts.canonical_profile import read_core_manifest_profile

    scenario_manifest, scenario_declaration = _runtime_api_request(
        runtime_api_env,
        read_core_manifest_profile,
        store,
        head.artifact_ref,
    )
    assert scenario_manifest.kind == "runtime.scenario_manifest"
    assert scenario_manifest.artifact_schema == SchemaInfo(
        name="polisyos.runtime.scenario_manifest",
        version="1",
    )
    assert scenario_declaration.profile == CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    scenario_artifact_ref = artifact_ref_for_manifest(scenario_manifest)
    assert scenario_artifact_ref.manifest_profile_sha256 is not None
    scenario_baseline = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/scenarios/{scenario_id}",
    )
    assert scenario_baseline.status_code == 200, scenario_baseline.text
    assert scenario_baseline.json()["scenario"]["manifest_hash"] == head.manifest_hash
    _remove_one_required_canon_field(
        store,
        str(scenario_artifact_ref.artifact_id),
        scenario_artifact_ref.manifest_profile_sha256,
    )
    scenario_read = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/scenarios/{scenario_id}",
    )
    assert scenario_read.status_code == 409, scenario_read.text
    assert scenario_read.headers["content-type"].startswith("application/problem+json")
    assert scenario_read.json()["code"] == "canon_profile_incomplete"


def test_raw_artifact_responses_keep_exact_bytes_when_profile_is_incomplete(
    runtime_api_env,
    monkeypatch,
) -> None:
    payload = to_canonical_bytes({"raw": "exact bytes"})
    ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.raw_profile_bytes",
        media_type="application/json",
        payload_bytes=payload,
        schema=SchemaInfo(name="test.raw_profile_bytes", version="1"),
        canon=CanonInfo(),
    )
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    params = {"manifest_profile_sha256": ref.manifest_profile_sha256}
    base_path = f"/api/v1/artifacts/{ref.artifact_id}"

    baseline_semantic = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/content",
        params=params,
    )
    assert baseline_semantic.status_code == 200, baseline_semantic.text
    baseline_raw = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/content",
        params=params,
        headers={"accept": "application/octet-stream"},
    )
    assert baseline_raw.status_code == 200, baseline_raw.text
    assert baseline_raw.content == payload
    baseline_download = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/download",
        params=params,
    )
    assert baseline_download.status_code == 200, baseline_download.text
    assert baseline_download.content == payload

    _remove_one_required_canon_field(
        store,
        str(ref.artifact_id),
        ref.manifest_profile_sha256,
    )

    content = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/content",
        params=params,
        headers={"accept": "application/octet-stream"},
    )
    assert content.status_code == 409, content.text
    assert content.headers["content-type"].startswith("application/problem+json")
    assert content.json()["code"] == "canon_profile_incomplete"

    download = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/download",
        params=params,
    )
    assert download.status_code == 409, download.text
    assert download.headers["content-type"].startswith("application/problem+json")
    assert download.json()["code"] == "canon_profile_incomplete"
    assert _runtime_api_request(runtime_api_env, store.get_bytes, ref.artifact_id) == payload

    # Unavailable bounded receipt refuses; the later semantic check restores the reader.
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.runtime.http.routes import artifacts as artifact_routes

    def bounded_manifest_unavailable(*args, **kwargs):
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_unavailable",
            limits=None,
            max_manifest_bytes=1,
            observed_manifest_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            original_exception_type="NotImplementedError",
        )

    with monkeypatch.context() as bounded_patch:
        bounded_patch.setattr(
            artifact_routes,
            "read_core_manifest_profile_bounded",
            bounded_manifest_unavailable,
        )
        fallback_raw = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"{base_path}/content",
            params=params,
            headers={"accept": "application/octet-stream"},
        )
        assert fallback_raw.status_code == 409, fallback_raw.text
        assert fallback_raw.headers["content-type"].startswith("application/problem+json")
        assert fallback_raw.json()["code"] == "canon_profile_bounded_manifest_unavailable"

    semantic = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{base_path}/content",
        params=params,
    )
    assert semantic.status_code == 409, semantic.text
    assert semantic.headers["content-type"].startswith("application/problem+json")
    assert semantic.json()["code"] == "canon_profile_incomplete"


def test_raw_routes_refuse_oversized_selected_manifest_before_payload_read(
    runtime_api_env, monkeypatch
) -> None:
    from polisyos.runtime.http.services.artifact_inspector import INSPECTOR_MANIFEST_MAX_BYTES

    oversized = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.oversized_selected_manifest",
        media_type="application/json",
        payload_bytes=to_canonical_bytes({"raw": "small payload"}),
        schema=SchemaInfo(name="test.oversized_selected_manifest", version="1"),
        canon=CanonInfo(),
        include_authority=False,
        warnings=[
            WarningRecord(
                code="test.large_manifest_warning",
                msg="x" * (INSPECTOR_MANIFEST_MAX_BYTES + 1024),
            )
        ],
    )
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    selected_manifest_path = store._manifest_path_for_ref(
        oversized.artifact_id, oversized.manifest_profile_sha256
    )
    assert selected_manifest_path.stat().st_size > INSPECTOR_MANIFEST_MAX_BYTES

    payload_reads: list[object] = []
    original_get_bytes = store.get_bytes

    def observe_payload_read(selector: object) -> bytes:
        payload_reads.append(selector)
        return original_get_bytes(selector)

    monkeypatch.setattr(store, "get_bytes", observe_payload_read)
    base_path = f"/api/v1/artifacts/{oversized.artifact_id}"
    params = {"manifest_profile_sha256": oversized.manifest_profile_sha256}
    for suffix, headers in (
        ("content", {"Accept": "application/octet-stream"}),
        ("download", {}),
        ("schema", {}),
    ):
        response = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"{base_path}/{suffix}",
            params=params,
            headers=headers,
        )
        assert response.status_code == 409, response.text
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "canon_profile_bounded_manifest_bytes_exceeded"
    assert payload_reads == []


def test_raw_routes_do_not_fallback_when_bounded_manifest_reader_is_unavailable(
    runtime_api_env, monkeypatch
) -> None:
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.runtime.http.routes import artifacts as artifact_routes
    from polisyos.runtime.http.services.artifact_inspector import INSPECTOR_MANIFEST_MAX_BYTES

    oversized = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.unavailable_bounded_manifest_reader",
        media_type="application/json",
        payload_bytes=to_canonical_bytes({"raw": "small payload"}),
        schema=SchemaInfo(name="test.unavailable_bounded_manifest_reader", version="1"),
        canon=CanonInfo(),
        include_authority=False,
        warnings=[
            WarningRecord(
                code="test.large_manifest_warning",
                msg="x" * (INSPECTOR_MANIFEST_MAX_BYTES + 1024),
            )
        ],
    )
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    selected_manifest_path = store._manifest_path_for_ref(
        oversized.artifact_id, oversized.manifest_profile_sha256
    )
    assert selected_manifest_path.stat().st_size > INSPECTOR_MANIFEST_MAX_BYTES

    def bounded_reader_unavailable(*args: object, **kwargs: object) -> None:
        raise CoreJsonReadBoundsRefusalError(
            "canon_profile_bounded_manifest_unavailable",
            limits=None,
            max_manifest_bytes=INSPECTOR_MANIFEST_MAX_BYTES,
            observed_manifest_bytes=0,
            observed_bytes=0,
            observed_depth=0,
            observed_elements=0,
            original_exception_type="NotImplementedError",
        )

    unbounded_reads: list[object] = []
    original_unbounded_reader = artifact_routes.read_core_manifest_profile

    def observe_unbounded_reader(*args: object, **kwargs: object):
        unbounded_reads.append((args, kwargs))
        return original_unbounded_reader(*args, **kwargs)

    monkeypatch.setattr(
        artifact_routes, "read_core_manifest_profile_bounded", bounded_reader_unavailable
    )
    monkeypatch.setattr(artifact_routes, "read_core_manifest_profile", observe_unbounded_reader)
    payload_reads: list[object] = []
    original_get_bytes = store.get_bytes

    def observe_payload_read(selector: object) -> bytes:
        payload_reads.append(selector)
        return original_get_bytes(selector)

    monkeypatch.setattr(store, "get_bytes", observe_payload_read)
    base_path = f"/api/v1/artifacts/{oversized.artifact_id}"
    params = {"manifest_profile_sha256": oversized.manifest_profile_sha256}
    for suffix, headers in (
        ("content", {"Accept": "application/octet-stream"}),
        ("download", {}),
        ("schema", {}),
    ):
        response = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"{base_path}/{suffix}",
            params=params,
            headers=headers,
        )
        assert response.status_code == 409, response.text
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "canon_profile_bounded_manifest_unavailable"
    assert unbounded_reads == []
    assert payload_reads == []


def _put_inspector_profile_fixture(
    runtime_api_env: dict[str, Any],
    *,
    kind: str,
    media_type: str,
    payload_bytes: bytes,
    schema: SchemaInfo,
    canon: CanonInfo | None,
    include_authority: bool = True,
    return_selected_profile: bool = False,
    warnings: list[WarningRecord] | None = None,
) -> ArtifactRef:
    """Persist one locally owned API fixture with the requested exact profile state."""
    store = runtime_api_env["app"].state.runtime_api_ctx.store
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    envelope_ref: ArtifactRef | None = None
    authority: ArtifactAuthorityInfo | None = None
    if include_authority:
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
                store, boundary, producer_version="inspector-profile-r4"
            )
            authority = ArtifactAuthorityInfo(
                authority_envelope_ref=str(envelope_ref.artifact_id),
                authority_envelope_manifest_profile_sha256=(envelope_ref.manifest_profile_sha256),
                diagnostic_event_ref=f"event://tests/runtime-api/{boundary_id}",
                manifest_ref=f"cas-manifest://{payload_ref}",
                payload_sha256=payload_sha256,
            )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        options: dict[str, Any] = {
            "kind": kind,
            "media_type": media_type,
            "schema": schema,
            "producer": ProducerInfo(component="tests.inspector_profile", version="1"),
        }
        if authority is not None:
            options["authority"] = authority
        if canon is not None:
            options["canon"] = canon
        if warnings is not None:
            options["warnings"] = warnings
        selected = profile_bound_ref(
            store,
            store.put_bytes(
                payload_bytes,
                PutOptions(**options),
                return_selected_profile=return_selected_profile,
            ),
        )
    owner_refs = ((envelope_ref,) if envelope_ref is not None else ()) + (selected,)
    _record_fixture_owner(
        store,
        *owner_refs,
        tenant_id=tenant_id,
        cell_id=cell_id,
        runtime_api_env=runtime_api_env,
    )
    return selected


def test_inspector_refusal_family_preserves_raw_and_non_json_semantics(
    runtime_api_env, monkeypatch
) -> None:
    """Exercise typed refusal and representation behavior through the actual API routes."""
    app = runtime_api_env["app"]
    client = runtime_api_env["client"]
    store = runtime_api_env["app"].state.runtime_api_ctx.store
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
    base_view = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="ir.backtest_report",
        media_type="application/json",
        payload_bytes=report_bytes,
        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        canon=CanonInfo(),
        include_authority=False,
    )
    supported = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="ir.backtest_report",
        media_type="application/json",
        payload_bytes=report_bytes,
        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        canon=CanonInfo(),
        return_selected_profile=True,
    )
    assert base_view.artifact_id == supported.artifact_id
    assert base_view.manifest_profile_sha256 != supported.manifest_profile_sha256

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
        expected_bytes = (
            report_bytes
            if ref is absent
            else to_canonical_bytes({"schema_version": "1.0", "marker": "unknown"})
        )
        assert raw.content == expected_bytes

        raw_download = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"{base_path}/download",
            params=params,
        )
        assert raw_download.status_code == 200, raw_download.text
        assert raw_download.content == expected_bytes

    container = app.state.runtime_container
    candidate_context = replace(
        container.runtime_api_context,
        allow_candidate_predictive_diagnostic_surface=True,
    )
    monkeypatch.setattr(container, "runtime_api_context", candidate_context)
    monkeypatch.setattr(app.state, "runtime_api_ctx", candidate_context)

    reader_candidate_diagnostic = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{base_view.artifact_id}/predictive-coverage-diagnostic",
        params={"manifest_profile_sha256": base_view.manifest_profile_sha256},
    )
    assert reader_candidate_diagnostic.status_code == 200, reader_candidate_diagnostic.text
    candidate_projection = reader_candidate_diagnostic.json()
    assert candidate_projection["measurement_status"] == "invalid_source"
    assert candidate_projection["reason_code"] == "predictive_scope_not_established"
    assert candidate_projection["source_materialization"] == "reader_materialized"
    assert candidate_projection["producer_attestation_status"] == "not_established"

    # A candidate diagnostic must not inherit the source manifest's authority.
    authority_bearing_diagnostic = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{supported.artifact_id}/predictive-coverage-diagnostic",
        params={"manifest_profile_sha256": supported.manifest_profile_sha256},
    )
    assert authority_bearing_diagnostic.status_code == 409, authority_bearing_diagnostic.text
    assert authority_bearing_diagnostic.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert authority_bearing_diagnostic.json()["code"] == "authority_surface_admission_blocked"

    diagnostic = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{unknown.artifact_id}/predictive-coverage-diagnostic",
        params={"manifest_profile_sha256": unknown.manifest_profile_sha256},
    )
    assert diagnostic.status_code == 409, diagnostic.text
    assert diagnostic.headers["content-type"].startswith("application/problem+json")
    assert diagnostic.json()["code"] == "canon_profile_not_verified"

    binary_payload = b"\x00\xff\x10opaque-binary"
    binary = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.opaque_binary_preview",
        media_type="application/octet-stream",
        payload_bytes=binary_payload,
        schema=SchemaInfo(name="test.opaque_binary_preview", version="1"),
        canon=None,
    )
    assert binary.manifest_profile_sha256 is not None
    assert _runtime_api_request(runtime_api_env, store.get_manifest, binary).canon is None
    base_path = f"/api/v1/artifacts/{binary.artifact_id}"
    for params in ({}, {"manifest_profile_sha256": binary.manifest_profile_sha256}):
        manifest_view = _runtime_api_request(runtime_api_env, client.get, base_path, params=params)
        assert manifest_view.status_code == 200, manifest_view.text
        assert manifest_view.json()["artifact"]["manifest_profile_sha256"] == (
            binary.manifest_profile_sha256
        )

        binary_view = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"{base_path}/content",
            params=params,
        )
        schema_view = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"{base_path}/schema",
            params=params,
        )
        assert binary_view.status_code == 200, binary_view.text
        assert schema_view.status_code == 200, schema_view.text
        binary_artifact = binary_view.json()["artifact"]
        assert binary_artifact["mode"] == "binary"
        assert binary_artifact["manifest_profile_sha256"] == binary.manifest_profile_sha256
        assert binary_artifact["canon_read_status"] == "not_applicable"
        assert binary_artifact["preview"] == binary_payload.hex()
        assert schema_view.json()["schema"]["manifest_profile_sha256"] == (
            binary.manifest_profile_sha256
        )
        assert schema_view.json()["schema"]["canon_read_status"] == "not_applicable"
        assert schema_view.json()["schema"]["top_level_keys"] == []

    json_looking_bytes = b'{"valid_utf8":"still_binary"}'
    json_looking_binary = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.opaque_json_looking_binary_preview",
        media_type="application/octet-stream",
        payload_bytes=json_looking_bytes,
        schema=SchemaInfo(name="test.opaque_json_looking_binary_preview", version="1"),
        canon=None,
    )
    json_looking_view = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/artifacts/{json_looking_binary.artifact_id}/content",
        params={"manifest_profile_sha256": json_looking_binary.manifest_profile_sha256},
    )
    assert json_looking_view.status_code == 200, json_looking_view.text
    json_looking_artifact = json_looking_view.json()["artifact"]
    assert json_looking_artifact["mode"] == "text"
    assert json_looking_artifact["canon_read_status"] == "not_applicable"
    assert json_looking_artifact["preview"] == json_looking_bytes.decode("utf-8")
    assert isinstance(json_looking_artifact["preview"], str)

    json_suffix = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.profileless_vendor_json",
        media_type="application/vnd.policyos.fixture+json",
        payload_bytes=to_canonical_bytes({"profile": "required"}),
        schema=SchemaInfo(name="test.profileless_vendor_json", version="1"),
        canon=None,
    )
    assert json_suffix.manifest_profile_sha256 is not None
    suffix_path = f"/api/v1/artifacts/{json_suffix.artifact_id}"
    for params in (
        {},
        {"manifest_profile_sha256": json_suffix.manifest_profile_sha256},
    ):
        for suffix in ("", "/content", "/schema"):
            response = _runtime_api_request(
                runtime_api_env,
                client.get,
                f"{suffix_path}{suffix}",
                params=params,
            )
            assert response.status_code == 409, response.text
            assert response.json()["code"] == "canon_profile_absent"

    malformed = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.malformed_selected_profile",
        media_type="application/json",
        payload_bytes=to_canonical_bytes({"malformed": "present"}),
        schema=SchemaInfo(name="test.malformed_selected_profile", version="1"),
        canon=CanonInfo(),
    )
    assert malformed.manifest_profile_sha256 is not None
    _remove_one_required_canon_field(
        store,
        str(malformed.artifact_id),
        malformed.manifest_profile_sha256,
    )
    for suffix in ("content", "schema"):
        response = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"/api/v1/artifacts/{malformed.artifact_id}/{suffix}",
            params={"manifest_profile_sha256": malformed.manifest_profile_sha256},
        )
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "canon_profile_incomplete"

    text_payload = b"ordinary UTF-8 text"
    text_ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.text_preview",
        media_type="text/plain",
        payload_bytes=text_payload,
        schema=SchemaInfo(name="test.text_preview", version="1"),
        canon=None,
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


def test_predictive_diagnostic_caps_actual_selected_bytes_before_codec(
    runtime_api_env, monkeypatch
) -> None:
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
        """Preserve the selected profile and blob while understating its size hint."""

        def __init__(self, wrapped):
            self._wrapped = wrapped
            self.payload_reads = 0
            self.bounded_member_attempts = []

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
            raw = json.dumps(
                manifest.model_dump(mode="json", by_alias=True), sort_keys=True
            ).encode("utf-8")
            return raw

        def get_bytes(self, selector):
            self.payload_reads += 1
            return self._wrapped.get_bytes(selector)

        def open_member_bounded(self, *args, **kwargs):
            attempt = self._wrapped.open_member_bounded(*args, **kwargs)
            self.bounded_member_attempts.append(attempt)
            return attempt

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
    assert bounded_store.payload_reads == 0
    assert len(bounded_store.bounded_member_attempts) == 1
    owner_usage = bounded_store.bounded_member_attempts[0].usage
    assert owner_usage.observed_payload_size == len(payload)
    assert owner_usage.observed_payload_bytes == 0
    assert owner_usage.payload_integrity_verified is False
    assert owner_usage.observed_source_bytes is not None
    assert len(payload) == _MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES + 1


def test_predictive_diagnostic_does_not_suppress_unmeasured_byte_refusal(
    runtime_api_env, monkeypatch
) -> None:
    """A matching code/stage cannot replace complete selected-owner measurements."""
    import polisyos.runtime.http.services.artifact_inspector as artifact_inspector
    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonReadBoundsRefusalError,
        CoreJsonReadLimits,
    )
    from polisyos.runtime.http.services.artifact_inspector import (
        _MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES,
        INSPECTOR_MANIFEST_MAX_BYTES,
    )

    ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="ir.backtest_report",
        media_type="application/json",
        payload_bytes=to_canonical_bytes({"schema_version": "1.0"}),
        schema=SchemaInfo(name="ir.backtest_report", version="1.0"),
        canon=CanonInfo(),
    )
    context = runtime_api_env["app"].state.runtime_api_ctx
    refusal = CoreJsonReadBoundsRefusalError(
        "canon_profile_bounded_bytes_exceeded",
        limits=CoreJsonReadLimits(
            max_bytes=_MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES,
            max_depth=128,
            max_elements=100_000,
            max_manifest_bytes=INSPECTOR_MANIFEST_MAX_BYTES,
        ),
        max_manifest_bytes=INSPECTOR_MANIFEST_MAX_BYTES,
        observed_manifest_bytes=1,
        observed_manifest_selection_bytes=1,
        observed_manifest_verification_bytes=1,
        observed_bytes=0,
        observed_payload_size=_MAX_PREDICTIVE_COVERAGE_SOURCE_BYTES + 1,
        observed_depth=0,
        observed_elements=0,
        limit_name="max_bytes",
        source_usage_complete=False,
        failure_stage="bounded_payload_read",
    )

    def unmeasured_refusal(*_args, **_kwargs):
        raise refusal

    monkeypatch.setattr(artifact_inspector, "_read_inspector_semantic_json", unmeasured_refusal)
    with (
        tenant_scope(
            None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
        ),
        pytest.raises(CoreJsonReadBoundsRefusalError) as caught,
    ):
        context.artifacts.get_predictive_coverage_diagnostic(ref.artifact_id)

    assert caught.value is refusal


def test_predictive_diagnostic_decodes_actual_bytes_below_source_cap(
    runtime_api_env, monkeypatch
) -> None:
    """The capped path retains a conformant in-limit decode and round trip."""
    from polisyos.core.artifacts import canonical_profile as core_profile

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
        manifest = context.store.get_manifest(ref)

    decode = core_profile.from_canonical_bytes
    encode = core_profile._encode_core_canonical_bytes_raw
    decode_calls: list[int] = []
    encode_calls: list[int] = []

    def observe_decode(raw, *args, **kwargs):
        decode_calls.append(len(raw))
        return decode(raw, *args, **kwargs)

    def observe_encode(value, *args, **kwargs):
        encode_calls.append(1)
        return encode(value, *args, **kwargs)

    monkeypatch.setattr(core_profile, "from_canonical_bytes", observe_decode)
    monkeypatch.setattr(core_profile, "_encode_core_canonical_bytes_raw", observe_encode)
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        preview = context.artifacts.get_predictive_coverage_diagnostic(
            ref.artifact_id,
            manifest=manifest,
        )

    assert preview is not None
    assert preview.measurement_status == "invalid_source"
    assert preview.producer_attestation_status == "not_established"
    assert decode_calls == [len(payload)]
    assert encode_calls == [1]


def test_inspector_json_content_and_schema_use_bounded_owner_reads(
    runtime_api_env,
) -> None:
    """Selected JSON is materialized only after exact bounded-owner verification."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.runtime.http.services.artifact_inspector import ArtifactInspectorService

    limit = 1024
    payload = to_canonical_bytes({"large": "x" * 1_200})
    ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.bounded_json_preview",
        media_type="application/json",
        payload_bytes=payload,
        schema=SchemaInfo(name="test.bounded_json_preview", version="1"),
        canon=CanonInfo(),
        return_selected_profile=True,
    )
    context = runtime_api_env["app"].state.runtime_api_ctx
    wrapped = context.artifacts._store

    class BoundedReadSpy:
        def __init__(self, target):
            self._target = target
            self.bounded_opens = 0
            self.get_bytes_calls = 0

        def __getattr__(self, name):
            return getattr(self._target, name)

        def open_member_bounded(self, *args, **kwargs):
            self.bounded_opens += 1
            return self._target.open_member_bounded(*args, **kwargs)

        def get_bytes(self, selector):
            self.get_bytes_calls += 1
            return self._target.get_bytes(selector)

    spy = BoundedReadSpy(wrapped)
    service = ArtifactInspectorService(
        store=spy,
        lineage_service=context.lineage,
        default_max_preview_bytes=limit,
    )
    with _runtime_api_tenant_scope(runtime_api_env):
        manifest = spy.get_manifest_by_profile(
            ref.artifact_id,
            ref.manifest_profile_sha256,
        )

        with pytest.raises(CoreJsonReadBoundsRefusalError) as content_refusal:
            service.get_content_preview(
                ref.artifact_id,
                max_bytes=limit,
                manifest=manifest,
            )
        assert content_refusal.value.code == "canon_profile_bounded_bytes_exceeded"
        assert content_refusal.value.limit_name == "max_bytes"
        assert content_refusal.value.observed_payload_bytes == 0
        assert content_refusal.value.observed_payload_size == len(payload)
        assert content_refusal.value.payload_integrity_verified is False

        with pytest.raises(CanonicalProfileRefusalError) as schema_refusal:
            service.get_schema_view(ref.artifact_id, manifest=manifest)
        assert schema_refusal.value.code == "canon_profile_bounded_bytes_exceeded"

    assert spy.bounded_opens == 2
    assert spy.get_bytes_calls == 0


def test_inspector_refuses_without_bounded_member_owner_instead_of_falling_back(
    runtime_api_env,
) -> None:
    """A backend without the bounded member port never falls back to full get_bytes."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.runtime.http.services.artifact_inspector import ArtifactInspectorService

    payload = to_canonical_bytes({"value": "selected"})
    ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.bounded_member_unavailable",
        media_type="application/json",
        payload_bytes=payload,
        schema=SchemaInfo(name="test.bounded_member_unavailable", version="1"),
        canon=CanonInfo(),
        return_selected_profile=True,
    )
    context = runtime_api_env["app"].state.runtime_api_ctx
    wrapped = context.artifacts._store

    class NoBoundedMemberStore:
        def __init__(self, target):
            self._target = target
            self.get_bytes_calls = 0

        def __getattr__(self, name):
            if name == "open_member_bounded":
                raise AttributeError(name)
            return getattr(self._target, name)

        def get_bytes(self, selector):
            self.get_bytes_calls += 1
            return self._target.get_bytes(selector)

    unavailable = NoBoundedMemberStore(wrapped)
    service = ArtifactInspectorService(
        store=unavailable,
        lineage_service=context.lineage,
    )
    with _runtime_api_tenant_scope(runtime_api_env):
        manifest = unavailable.get_manifest_by_profile(
            ref.artifact_id,
            ref.manifest_profile_sha256,
        )

        with pytest.raises(CanonicalProfileRefusalError) as refusal:
            service.get_content_preview(ref.artifact_id, manifest=manifest)

        assert refusal.value.code == "canon_profile_bounded_stream_unavailable"
        assert unavailable.get_bytes_calls == 0


def test_api_json_inspection_refuses_over_preview_limit(runtime_api_env) -> None:
    context = runtime_api_env["app"].state.runtime_api_ctx
    limit = min(max(context.max_preview_bytes, 1024), 2_000_000)
    payload = to_canonical_bytes({"large": "x" * limit})
    ref = _put_inspector_profile_fixture(
        runtime_api_env,
        kind="test.api_bounded_json_preview",
        media_type="application/json",
        payload_bytes=payload,
        schema=SchemaInfo(name="test.api_bounded_json_preview", version="1"),
        canon=CanonInfo(),
        return_selected_profile=True,
    )
    path = f"/api/v1/artifacts/{ref.artifact_id}"
    selected = {"manifest_profile_sha256": ref.manifest_profile_sha256}

    content = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{path}/content",
        params={**selected, "max_bytes": limit},
    )
    schema = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"{path}/schema",
        params=selected,
    )

    assert content.status_code == 409, content.text
    assert content.json()["code"] == "canon_profile_bounded_bytes_exceeded"
    assert schema.status_code == 409, schema.text
    assert schema.json()["code"] == "canon_profile_bounded_bytes_exceeded"


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


def test_nodes_and_errors_expose_only_genuine_timeline_fallback(
    runtime_api_env, monkeypatch
) -> None:
    context = runtime_api_env["app"].state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    assert run.decision_packet_ref is not None
    store = context.store

    assert run.workflow_report_ref is not None
    missing_refs = (None, run.workflow_report_ref)
    for missing_ref in missing_refs:
        unavailable_store = None
        if missing_ref is None:
            monkeypatch.setattr(context.debug, "_store", store)
        else:
            unavailable_store = _OwnedArtifactUnavailableStore(store, missing_ref)
            monkeypatch.setattr(context.debug, "_store", unavailable_store)
        missing_run = replace(run, workflow_report_ref=missing_ref)
        monkeypatch.setattr(
            context.run_index,
            "get_run",
            lambda _run_id, missing_run=missing_run: missing_run,
        )
        nodes = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"/api/v1/runs/{run_id}/nodes",
        )
        assert nodes.status_code == 200, nodes.text
        assert nodes.json()["nodes"]
        assert "workflow_report_missing_or_unavailable" in nodes.json()["notes"]
        node_alias = nodes.json()["nodes"][0]["alias"]
        node_debug = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"/api/v1/debug/runs/{run_id}/nodes/{node_alias}",
        )
        assert node_debug.status_code == 200, node_debug.text
        assert "workflow_report_missing_or_unavailable" in node_debug.json()["debug"]["notes"]

        errors = _runtime_api_request(
            runtime_api_env,
            runtime_api_env["client"].get,
            f"/api/v1/debug/runs/{run_id}/errors",
        )
        assert errors.status_code == 200, errors.text
        assert "workflow_report_missing_or_unavailable" in errors.json()["notes"]
        node_errors = [
            item for item in errors.json()["errors"] if item.get("node_alias") is not None
        ]
        assert node_errors
        assert all(item["source"] == "trace" for item in node_errors)
        if unavailable_store is not None:
            assert missing_ref.manifest_profile_sha256 is not None
            assert (
                missing_ref.manifest_profile_sha256 in unavailable_store.checked_manifest_profiles
            )
            assert None in unavailable_store.checked_manifest_profiles
            assert unavailable_store.checked_payload_reads >= 1

    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        selected_manifest = store.get_manifest(run.decision_packet_ref)
    empty_payload = to_canonical_bytes({"nodes": [], "run_id": run_id})
    with tenant_scope(
        None, tenant_id=runtime_api_env["tenant_a"], cell_id=runtime_api_env["cell_a"]
    ):
        empty_ref = profile_bound_ref(
            store,
            store.put_bytes(
                empty_payload,
                PutOptions(
                    kind="scientist.workflow_report",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.orchestration.engine.WorkflowReport",
                        version="1.0",
                    ),
                    producer=ProducerInfo(component="tests.workflow_report", version="1"),
                    canon=CanonInfo(),
                    tenant_context=selected_manifest.tenant_context,
                ),
            ),
        )
    _record_fixture_owner(
        store,
        empty_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )
    empty_run = replace(run, workflow_report_ref=empty_ref)
    monkeypatch.setattr(
        context.run_index,
        "get_run",
        lambda _run_id: empty_run,
    )
    present_empty = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/runs/{run_id}/nodes",
    )
    assert present_empty.status_code == 200, present_empty.text
    assert present_empty.json()["nodes"] == []
    assert "workflow_report_missing_or_unavailable" not in present_empty.json()["notes"]
