"""Exercise the explicit technical-inspection proof across the HTTP boundary."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from _helpers.runtime_http import (
    _record_fixture_owner,
    _runtime_api_request,
    build_runtime_api_env_with_fixture_catalog,
    close_runtime_api_env,
)

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    input_ref_from_artifact_ref,
)
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    clear_tenant_context,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.foundry.execute import read_method_artifact_output_bounded
from polisyos.runtime.quality.authority import authority_surface_decision
from polisyos.runtime.quality.technical_inspection_evidence import (
    create_technical_inspection_evidence,
    verify_technical_inspection_evidence,
)
from tests._helpers.method_artifact_writer import (
    capture_fixture,
    local_store,
    produce,
    selected_ref,
)


def _import_selected_closure(source: FileSystemCAS, target: Any, ref: ArtifactRef) -> None:
    """Transfer exact source views; the target transaction grants its actual owner."""
    manifest = source.get_manifest(ref)
    for edge in manifest.inputs:
        child = source.get_manifest_by_profile(edge.artifact_id, edge.manifest_profile_sha256)
        child_ref = ArtifactRef(
            artifact_id=edge.artifact_id,
            kind=child.kind,
            media_type=child.media_type,
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        _import_selected_closure(source, target, child_ref)
    imported = target.import_exact_view(
        source.get_bytes(ref), source.get_raw_manifest_bytes(ref), artifact_id=ref
    )
    assert imported == ref
    assert target.get_raw_manifest_bytes(ref) == source.get_raw_manifest_bytes(ref)
    assert target.get_bytes(ref) == source.get_bytes(ref)


@pytest.fixture
def runtime_env(tmp_path: Path, pytestconfig: pytest.Config) -> Iterator[dict[str, Any]]:
    env = build_runtime_api_env_with_fixture_catalog(
        tmp_path, include_test_client=True, app_kwargs={"repo_root": pytestconfig.rootpath}
    )
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def test_fresh_http_previews_require_exact_current_inspection_evidence(
    runtime_env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = runtime_env["app"].state.runtime_api_ctx.store
    producer_store = local_store(tmp_path / "producer")
    tenant, cell = runtime_env["tenant_a"], runtime_env["cell_a"]
    scope = AccessScope.for_service(
        tenant_id=tenant, cell_id=cell, spiffe_id="spiffe://test/inspector"
    )
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        token = set_current_access_scope(scope)
        try:
            capture, occurrence = capture_fixture(producer_store)
            produced = selected_ref(
                produce(producer_store, capture, occurrence, {"sidecar": {"answer": 2}})
            )
            source = ArtifactRef.model_validate(produced.model_dump(mode="python"))
            _import_selected_closure(producer_store, store, source)
            evidence = create_technical_inspection_evidence(store, source)
            manifest = store.get_manifest(source)
            alternate_input = store.put_json(
                {"fixture": "alternate-program-graph"},
                PutOptions(kind="foundry.program_graph", media_type="application/json"),
                return_selected_profile=True,
            )
            alternate_inputs = [
                input_ref_from_artifact_ref(alternate_input, role=manifest.inputs[0].role),
                *manifest.inputs[1:],
            ]
            other = store.put_bytes(
                store.get_bytes(source),
                PutOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    canon=manifest.canon,
                    producer=manifest.producer,
                    inputs=alternate_inputs,
                ),
                return_selected_profile=True,
            )
            assert other.artifact_id == source.artifact_id
            assert other.manifest_profile_sha256 != source.manifest_profile_sha256
            # This alternate is independently admitted by the .3 source owner.
            # A changed schema would refuse earlier and mask evidence binding.
            other_read = read_method_artifact_output_bounded(store, other)
            assert other_read.value["payload"] == {"answer": 2}
            other_evidence = create_technical_inspection_evidence(store, other)
            with pytest.raises(ValueError, match="technical_inspection_evidence_profile_invalid"):
                verify_technical_inspection_evidence(store, other, evidence)
            for purpose in ("runtime_closeout_authority", "publication", "claim_authority"):
                decision = authority_surface_decision(
                    {},
                    surface="artifact",
                    purpose=purpose,
                    artifact_store=store,
                    artifact_ref=source,
                    technical_inspection_evidence_ref=evidence,
                    require_cas_integrity=True,
                )
                assert decision.blocking or decision.visible_downgrade
        finally:
            reset_current_access_scope(token)
    _record_fixture_owner(
        store, source, other, tenant_id=tenant, cell_id=cell, runtime_api_env=runtime_env
    )
    client = runtime_env["client"]
    params = {
        "manifest_profile_sha256": source.manifest_profile_sha256,
        "technical_inspection_evidence_id": str(evidence.artifact_id),
        "technical_inspection_evidence_profile_sha256": evidence.manifest_profile_sha256,
    }
    for suffix in ("content", "schema"):
        url = f"/api/v1/artifacts/{source.artifact_id}/{suffix}"
        audit = runtime_env["app"].state.runtime_container.runtime_access_audit

        def request_and_assert_audit(
            headers: dict[str, str], *, audit: Any = audit, url: str = url, suffix: str = suffix
        ) -> Any:
            before = len(audit.scan_read_only().entries)
            result = _runtime_api_request(
                runtime_env, client.get, url, params=params, headers=headers
            )
            assert result.status_code == 200, result.text
            entries = audit.scan_read_only().entries[before:]
            matching = [
                entry
                for entry in entries
                if entry.get("resource_kind") == f"runtime.artifact_{suffix}"
                and entry.get("resource_id") == str(source.artifact_id)
            ]
            assert len(matching) == 1
            assert matching[0]["metadata"]["technical_inspection_subject"] == source.model_dump(
                mode="json"
            )
            assert matching[0]["metadata"]["technical_inspection_evidence"] == evidence.model_dump(
                mode="json"
            )
            return result

        response = request_and_assert_audit({})
        assert response.headers["cache-control"] == "private, no-cache"
        request_and_assert_audit({"If-None-Match": response.headers["etag"]})
        request_and_assert_audit({"If-Modified-Since": response.headers["last-modified"]})
        body = response.json()
        if suffix == "content":
            assert body["artifact"]["preview"]["payload"] == {"answer": 2}
        else:
            assert "payload" in body["schema"]["top_level_keys"]
        missing = _runtime_api_request(
            runtime_env,
            client.get,
            url,
            params={"manifest_profile_sha256": source.manifest_profile_sha256},
        )
        assert missing.status_code == 409
        borrowed = _runtime_api_request(
            runtime_env,
            client.get,
            url,
            params={**params, "manifest_profile_sha256": other.manifest_profile_sha256},
        )
        assert borrowed.status_code == 409
        assert borrowed.json()["extensions"]["authority_surface_decision"]["reason"] == (
            "technical_inspection_evidence_invalid"
        )
        qualified_other = _runtime_api_request(
            runtime_env,
            client.get,
            url,
            params={
                **params,
                "manifest_profile_sha256": other.manifest_profile_sha256,
                "technical_inspection_evidence_id": str(other_evidence.artifact_id),
                "technical_inspection_evidence_profile_sha256": other_evidence.manifest_profile_sha256,
            },
        )
        assert qualified_other.status_code == 200, qualified_other.text
        absent = _runtime_api_request(
            runtime_env,
            client.get,
            url,
            params={**params, "technical_inspection_evidence_id": "sha256:" + "f" * 64},
        )
        assert absent.status_code == 409
        wrong_profile = _runtime_api_request(
            runtime_env,
            client.get,
            url,
            params={**params, "technical_inspection_evidence_profile_sha256": "sha256:" + "f" * 64},
        )
        assert wrong_profile.status_code == 409
        incomplete = _runtime_api_request(
            runtime_env,
            client.get,
            url,
            params={"technical_inspection_evidence_id": str(evidence.artifact_id)},
        )
        assert incomplete.status_code == 400
        duplicate = _runtime_api_request(
            runtime_env,
            client.get,
            url,
            params=[
                *params.items(),
                ("technical_inspection_evidence_id", str(evidence.artifact_id)),
            ],
        )
        assert duplicate.status_code == 400
    raw = _runtime_api_request(
        runtime_env,
        client.get,
        f"/api/v1/artifacts/{source.artifact_id}/content",
        params=params,
        headers={"accept": "application/octet-stream"},
    )
    assert raw.status_code == 400
    with clear_tenant_context():
        decision = authority_surface_decision(
            {},
            surface="artifact",
            purpose="technical_artifact_inspection",
            artifact_store=store,
            artifact_ref=source,
            technical_inspection_evidence_ref=evidence,
            require_cas_integrity=True,
        )
        assert decision.blocking or decision.visible_downgrade
