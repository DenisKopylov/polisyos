from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from _helpers.runtime_http import _record_fixture_owner
from pydantic import ValidationError

from polisyos.core.artifacts import PutOptions, SchemaInfo, profile_bound_ref
from polisyos.core.contracts.runtime import LineageGraphView
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)


@pytest.fixture
def runtime_api_env(tmp_path):
    from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def test_run_fabric_quantity_profile_reaches_the_batch_graph_and_temporal_consumer(
    runtime_api_env: dict[str, Any],
) -> None:
    app = runtime_api_env["app"]
    context = app.state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        selected = context.lineage.selected_decision_packet_ref_for_run(run)
        assert selected is not None
        selected_ref, provenance = selected
        producer_profile = context.lineage.selected_decision_packet_ref_for_run(
            replace(run, decision_packet_ref=selected_ref)
        )
        assert producer_profile == (selected_ref, "run_output_ref")
        legacy_ref = run.decision_packet_ref
        assert legacy_ref is not None
        legacy_profile = context.lineage.selected_decision_packet_ref_for_run(
            replace(
                run,
                decision_packet_ref=legacy_ref.model_copy(update={"manifest_profile_sha256": None}),
            )
        )
        assert legacy_profile == (selected_ref, "reader_materialized")
    bearer = _fixture_bearer("fabric-profile-lineage")
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
            jti="jwt-fabric-profile-lineage",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    _record_fixture_owner(
        context.store,
        selected_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        runtime_api_env=runtime_api_env,
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }

    with client:
        fabric_response = client.get(
            f"/api/v1/runs/{run_id}/fabric-decision-data",
            headers=headers,
        )
        assert fabric_response.status_code == 200, fabric_response.text
        decision_rows = fabric_response.json()["decision_data"]
        quantity = next(
            row
            for row in decision_rows
            if row.get("kind") == "quantity"
            and isinstance(row.get("lineage", {}).get("artifact_ref"), dict)
        )
        fabric_lineage = quantity["lineage"]
        assert fabric_lineage["artifact_ref"] == selected_ref.model_dump(mode="json")
        assert fabric_lineage["artifact_ref_provenance"] == provenance
        assert fabric_lineage["source_run_id"] == run_id

        lineage_response = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            params={"branch": "main"},
            json={
                "lineage_ids": [fabric_lineage["id"]],
                "selected_artifact_refs": [fabric_lineage["artifact_ref"]],
                "run_id": run_id,
            },
        )

    assert lineage_response.status_code == 200, lineage_response.text
    payload = lineage_response.json()
    graph = payload["lineages"][0]
    assert payload["temporal_scope"]["branch"] == "main"
    assert graph["selected_artifact_ref"] == fabric_lineage["artifact_ref"]
    assert graph["profile_binding_status"] == "verified"
    assert graph["artifact_ref_provenance"] == provenance
    assert graph["source_run_id"] == run_id
    assert graph["trust_metadata"]["temporal_scope"] == payload["temporal_scope"]
    assert graph["trust_metadata"]["verified_by"] is None
    assert graph["root_artifact_refs"] == [fabric_lineage["artifact_ref"]]
    root_node = next(node for node in graph["nodes"] if node["id"] == str(selected_ref.artifact_id))
    assert root_node["media_type"] == selected_ref.media_type
    assert root_node["manifest_profile_sha256"] == selected_ref.manifest_profile_sha256


def test_same_bytes_with_sibling_profiles_do_not_share_batch_graph_identity(
    runtime_api_env: dict[str, Any],
) -> None:
    app = runtime_api_env["app"]
    context = app.state.runtime_api_ctx
    run = context.run_index.get_run(runtime_api_env["core_run_id"])
    assert run.decision_packet_ref is not None
    store = context.store
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        manifest = store.get_manifest(run.decision_packet_ref)
        payload_bytes = store.get_bytes(run.decision_packet_ref)
        assert manifest.artifact_schema is not None
        assert manifest.canon is not None
        refs = [
            profile_bound_ref(
                store,
                store.put_bytes(
                    payload_bytes,
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=SchemaInfo(
                            name=manifest.artifact_schema.name,
                            version=f"e02-sibling-{version}",
                        ),
                        producer=manifest.producer,
                        env=manifest.env,
                        inputs=manifest.inputs,
                        canon=manifest.canon,
                        governance=manifest.governance,
                        tenant_context=manifest.tenant_context,
                        same_input_closure=manifest.same_input_closure,
                        authority=manifest.authority,
                        warnings=manifest.warnings,
                    ),
                ),
            )
            for version in ("a", "b")
        ]
    first, second = refs
    assert first.artifact_id == second.artifact_id
    assert first.manifest_profile_sha256 != second.manifest_profile_sha256
    bearer = _fixture_bearer("lineage-sibling-profiles")
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
            jti="jwt-lineage-sibling-profiles",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    _record_fixture_owner(
        store,
        first,
        second,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        runtime_api_env=runtime_api_env,
    )
    canonical_id = f"artifact:{first.artifact_id}"
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    with client:
        response = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [canonical_id, canonical_id],
                "selected_artifact_refs": [
                    first.model_dump(mode="json"),
                    second.model_dump(mode="json"),
                ],
            },
        )
    assert response.status_code == 200, response.text
    graphs = response.json()["lineages"]
    assert [graph["selected_artifact_ref"] for graph in graphs] == [
        first.model_dump(mode="json"),
        second.model_dump(mode="json"),
    ]
    assert [graph["profile_binding_status"] for graph in graphs] == [
        "verified",
        "verified",
    ]


def test_run_profile_context_and_malformed_or_wrong_typed_profiles_fail_closed(
    runtime_api_env: dict[str, Any],
) -> None:
    app = runtime_api_env["app"]
    context = app.state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        selected = context.lineage.selected_decision_packet_ref_for_run(run)
    assert selected is not None
    selected_ref, _provenance = selected
    store = context.store
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        manifest = store.get_manifest(selected_ref)
        payload_bytes = store.get_bytes(selected_ref)
        assert manifest.artifact_schema is not None
        assert manifest.canon is not None
        sibling_ref = profile_bound_ref(
            store,
            store.put_bytes(
                payload_bytes,
                PutOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=SchemaInfo(
                        name=manifest.artifact_schema.name,
                        version="e02-run-context-sibling",
                    ),
                    producer=manifest.producer,
                    env=manifest.env,
                    inputs=manifest.inputs,
                    canon=manifest.canon,
                    governance=manifest.governance,
                    tenant_context=manifest.tenant_context,
                    same_input_closure=manifest.same_input_closure,
                    authority=manifest.authority,
                    warnings=manifest.warnings,
                ),
            ),
        )
    bearer = _fixture_bearer("lineage-profile-refusal")
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
            jti="jwt-lineage-profile-refusal",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    _record_fixture_owner(
        store,
        selected_ref,
        sibling_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        runtime_api_env=runtime_api_env,
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    lineage_id = f"artifact:{selected_ref.artifact_id}"
    with client:
        context_mismatch = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [lineage_id],
                "selected_artifact_refs": [sibling_ref.model_dump(mode="json")],
                "run_id": run_id,
            },
        )
        wrong_kind = selected_ref.model_copy(update={"kind": "forged.decision_packet"})
        kind_refusal = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [lineage_id],
                "selected_artifact_refs": [wrong_kind.model_dump(mode="json")],
            },
        )
        wrong_media = selected_ref.model_copy(update={"media_type": "text/plain"})
        media_refusal = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [lineage_id],
                "selected_artifact_refs": [wrong_media.model_dump(mode="json")],
            },
        )
        malformed = selected_ref.model_dump(mode="json")
        malformed["manifest_profile_sha256"] = "sha256:not-a-profile"
        malformed_refusal = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [lineage_id],
                "selected_artifact_refs": [malformed],
            },
        )
        legacy = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={"lineage_ids": [lineage_id]},
        )

    assert context_mismatch.status_code == 403, context_mismatch.text
    assert context_mismatch.json()["code"] == "authorization_binding_profile_context_mismatch"
    assert kind_refusal.status_code == 409, kind_refusal.text
    assert kind_refusal.json()["code"] == "canon_profile_selection_unverified"
    assert media_refusal.status_code == 409, media_refusal.text
    assert media_refusal.json()["code"] == "canon_profile_selection_unverified"
    assert malformed_refusal.status_code in {400, 422}, malformed_refusal.text
    assert legacy.status_code == 200, legacy.text
    legacy_graph = legacy.json()["lineages"][0]
    assert legacy_graph["profile_binding_status"] == "not_established"
    assert legacy_graph["selected_artifact_ref"] is None
    assert legacy_graph["trust_metadata"] is None


def test_null_selected_refs_do_not_claim_the_request_run_as_a_lineage_source(
    runtime_api_env: dict[str, Any],
) -> None:
    app = runtime_api_env["app"]
    context = app.state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    unrelated_run_id = runtime_api_env["core_run_id_secondary"]
    run = context.run_index.get_run(run_id)
    unrelated_run = context.run_index.get_run(unrelated_run_id)
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        selected = context.lineage.selected_decision_packet_ref_for_run(run)
        unrelated = context.lineage.selected_decision_packet_ref_for_run(unrelated_run)
    assert selected is not None
    assert unrelated is not None
    selected_ref, _provenance = selected
    unrelated_ref, _unrelated_provenance = unrelated
    assert unrelated_run_id != run_id
    assert unrelated_ref != selected_ref
    _record_fixture_owner(
        context.store,
        selected_ref,
        unrelated_ref,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        runtime_api_env=runtime_api_env,
    )

    scenario = (
        runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/scenarios").json()["scenarios"][0]
    )
    scenario_lineage_id = scenario["model_lineage"]["id"]
    bearer = _fixture_bearer("lineage-null-profile-source-run")
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
            jti="jwt-lineage-null-profile-source-run",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    unrelated_lineage_id = f"artifact:{unrelated_ref.artifact_id}"

    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        null_service_graph = context.lineage.build_runtime_lineage_batch(
            [unrelated_lineage_id],
            selected_artifact_refs=[None],
            run_id=run_id,
        )[0]
        wrong_run_service_graph = context.lineage.build_runtime_lineage_batch(
            [f"artifact:{selected_ref.artifact_id}"],
            selected_artifact_refs=[selected_ref],
            run_id=unrelated_run_id,
        )[0]
    assert null_service_graph.profile_binding_status == "not_established"
    assert null_service_graph.source_run_id is None
    assert null_service_graph.artifact_ref_provenance is None
    assert null_service_graph.trust_metadata is None
    assert wrong_run_service_graph.profile_binding_status == "not_established"
    assert wrong_run_service_graph.selected_artifact_ref == selected_ref
    assert wrong_run_service_graph.source_run_id is None
    assert wrong_run_service_graph.artifact_ref_provenance is None
    assert wrong_run_service_graph.trust_metadata is None

    with client:
        all_null = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [unrelated_lineage_id],
                "selected_artifact_refs": [None],
                "run_id": run_id,
            },
        )
        mixed = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [
                    f"artifact:{selected_ref.artifact_id}",
                    unrelated_lineage_id,
                ],
                "selected_artifact_refs": [selected_ref.model_dump(mode="json"), None],
                "run_id": run_id,
            },
        )
        scenario_response = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [
                    scenario_lineage_id,
                    f"artifact:{selected_ref.artifact_id}",
                ],
                "selected_artifact_refs": [
                    None,
                    selected_ref.model_dump(mode="json"),
                ],
                "run_id": run_id,
            },
        )
        scenario_wrong_run_response = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={
                "lineage_ids": [scenario_lineage_id],
                "selected_artifact_refs": [None],
                "run_id": unrelated_run_id,
            },
        )

    assert all_null.status_code == 200, all_null.text
    all_null_graph = all_null.json()["lineages"][0]
    assert all_null_graph["profile_binding_status"] == "not_established"
    assert all_null_graph.get("source_run_id") is None
    assert all_null_graph.get("trust_metadata") is None

    assert mixed.status_code == 200, mixed.text
    matching_graph, null_graph = mixed.json()["lineages"]
    assert matching_graph["profile_binding_status"] == "verified"
    assert matching_graph["source_run_id"] == run_id
    assert matching_graph["selected_artifact_ref"] == selected_ref.model_dump(mode="json")
    assert matching_graph["trust_metadata"] is not None
    assert null_graph["profile_binding_status"] == "not_established"
    assert null_graph.get("source_run_id") is None
    assert null_graph.get("trust_metadata") is None

    assert scenario_response.status_code == 200, scenario_response.text
    scenario_graph, profile_graph = scenario_response.json()["lineages"]
    assert scenario_graph["profile_binding_status"] == "not_established"
    assert scenario_graph.get("source_run_id") is None
    assert scenario_graph.get("trust_metadata") is None
    assert profile_graph["profile_binding_status"] == "verified"
    assert profile_graph["source_run_id"] == run_id
    assert profile_graph["selected_artifact_ref"] == selected_ref.model_dump(mode="json")
    assert profile_graph["trust_metadata"] is not None

    assert scenario_wrong_run_response.status_code == 200, scenario_wrong_run_response.text
    scenario_wrong_run_graph = scenario_wrong_run_response.json()["lineages"][0]
    assert scenario_wrong_run_graph["profile_binding_status"] == "not_established"
    assert scenario_wrong_run_graph.get("selected_artifact_ref") is None
    assert scenario_wrong_run_graph.get("artifact_ref_provenance") is None
    assert scenario_wrong_run_graph.get("source_run_id") is None
    assert scenario_wrong_run_graph.get("trust_metadata") is None

    with pytest.raises(ValidationError, match="source_run_id requires a selected artifact profile"):
        LineageGraphView.model_validate({**matching_graph, "selected_artifact_ref": None})
    with pytest.raises(ValidationError, match="source_run_id requires verified profile binding"):
        LineageGraphView.model_validate(
            {**matching_graph, "profile_binding_status": "not_established"}
        )
