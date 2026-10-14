from __future__ import annotations

import json

from _helpers.runtime_http import _runtime_api_request
from polisyos_tests_runtime_http_conftest import build_runtime_api_env

from polisyos.core.artifacts.canonical_profile import artifact_ref_for_manifest
from polisyos.core.artifacts.manifest import ArtifactRef


def _persist_analysis_and_basin_refs(env) -> tuple[str, ArtifactRef, ArtifactRef]:
    response = _runtime_api_request(
        env,
        env["client"].post,
        "/api/v1/analysis/attractors",
        json={
            "variable_ids": ["income"],
            "trajectories": [
                [[0.0] for _ in range(12)],
                [[1.0] for _ in range(12)],
            ],
            "initial_states": [{"income": 0.0}, {"income": 1.0}],
            "seeds": [17, 23],
            "tolerance": 1.0e-8,
            "rtol": 0.0,
            "persist_artifact": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    analysis_ref = ArtifactRef.model_validate(payload["analysis_result_ref"])
    derived = {
        item["role"]: ArtifactRef.model_validate(item["ref"]) for item in payload["derived_refs"]
    }
    return (
        str(analysis_ref.artifact_id),
        analysis_ref,
        derived["basin_map"],
    )


def _persist_continuation_branch_ref(env) -> ArtifactRef:
    response = _runtime_api_request(
        env,
        env["client"].post,
        "/api/v1/analysis/continuation",
        json={
            "branch_id": "branch_selected_profile",
            "analysis_id": "analysis_selected_profile",
            "branch_kind": "equilibrium",
            "parameters": ["tax_rate"],
            "points": [
                {
                    "point_id": "point_1",
                    "parameter_values": {"tax_rate": 0.2},
                    "state": {"income": 1.5},
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    return ArtifactRef.model_validate(response.json())


def _selected_profile(env, store, ref: ArtifactRef) -> ArtifactRef:
    manifest = _runtime_api_request(env, store.get_manifest, ref)
    selected = artifact_ref_for_manifest(manifest)
    assert selected.manifest_profile_sha256 is not None
    return selected


def _remove_required_canon_field(store, selected_ref: ArtifactRef) -> None:
    profile_path = store._manifest_path_for_ref(
        selected_ref.artifact_id,
        selected_ref.manifest_profile_sha256,
    )
    manifest = json.loads(profile_path.read_bytes())
    canon = manifest.get("canon")
    assert isinstance(canon, dict)
    assert "separators" in canon
    canon.pop("separators")
    profile_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_all_attractor_semantic_gets_consume_selected_profiles_and_refuse_malformed_ones(
    tmp_path, monkeypatch
) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"allow_unscoped_artifacts": True},
    )
    client = env["client"]
    store = env["app"].state.runtime_api_ctx.store
    analysis_id, analysis_ref, basin_ref = _persist_analysis_and_basin_refs(env)
    branch_ref = _persist_continuation_branch_ref(env)
    get_urls = (
        (analysis_ref, f"/api/v1/analysis/{analysis_id}"),
        (basin_ref, f"/api/v1/analysis/{analysis_id}/basin/{basin_ref.artifact_id}"),
        (
            branch_ref,
            f"/api/v1/analysis/analysis_selected_profile/branch/{branch_ref.artifact_id}",
        ),
    )
    consumed_refs: list[object] = []
    original_get_bytes = store.get_bytes

    def record_get_bytes(artifact_id):
        consumed_refs.append(artifact_id)
        return original_get_bytes(artifact_id)

    monkeypatch.setattr(store, "get_bytes", record_get_bytes)
    for ref, url in get_urls:
        selected_ref = _selected_profile(env, store, ref)
        consumed_refs.clear()
        baseline = _runtime_api_request(env, client.get, url)
        assert baseline.status_code == 200, baseline.text
        assert any(
            isinstance(consumed, ArtifactRef)
            and consumed.artifact_id == selected_ref.artifact_id
            and consumed.kind == selected_ref.kind
            and consumed.media_type == selected_ref.media_type
            and consumed.manifest_profile_sha256 == selected_ref.manifest_profile_sha256
            for consumed in consumed_refs
        )

        _remove_required_canon_field(store, selected_ref)
        response = _runtime_api_request(env, client.get, url)

        assert response.status_code == 409, response.text
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "canon_profile_incomplete"

    malformed_id = _runtime_api_request(env, client.get, "/api/v1/analysis/not-a-sha256-id")
    assert malformed_id.status_code == 400, malformed_id.text
    assert malformed_id.headers["content-type"].startswith("application/problem+json")
