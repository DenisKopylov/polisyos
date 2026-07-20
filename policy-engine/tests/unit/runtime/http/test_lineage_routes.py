from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.identity import PolicyOSRole
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)


def test_lineage_batch_lookup_uses_compact_batch_adapter(runtime_api_env) -> None:
    bearer = _fixture_bearer("lineage-compact-batch")
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
            jti="jwt-lineage-compact-batch",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    primary_id = runtime_api_env["decision_packet_artifact_id"]
    secondary_id = runtime_api_env["decision_packet_artifact_id_secondary"]
    store = FileSystemCAS(runtime_api_env["cas_root"])
    for artifact_id in (primary_id, secondary_id):
        store.record_artifact_owner(
            artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.runtime_http.lineage_batch",
        )
    lineage_ids = [
        f"artifact:{primary_id}",
        f"artifact:{secondary_id}",
        f"artifact:{primary_id}",
    ]

    with client:
        response = client.post(
            "/api/v1/lineage/batch",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            params={"valid_at": "2026-04-15T12:00:00Z", "branch": "main"},
            json={"lineage_ids": lineage_ids},
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["lineages"]] == lineage_ids
    assert payload["temporal_scope"]["branch"] == "main"
    assert all(
        item["trust_metadata"]["temporal_scope"]["branch"] == "main" for item in payload["lineages"]
    )
    assert all(
        item["status"] in {"verified", "disputed"} for item in payload["lineages"]
    )


def test_compact_lineage_batch_local_benchmark_meets_phase6_budget(runtime_api_env) -> None:
    container = runtime_api_env["app"].state.runtime_container
    service = container.runtime_api_context.lineage

    report = service.benchmark_compact_lineage_batch(
        [f"lin_unknown_{index}" for index in range(50)]
    )

    assert report["count"] == 50
    assert report["unique_count"] == 50
    assert report["p95_ms"] <= 150.0
    assert report["status_counts"]["untraced"] == 50


def test_full_lineage_graph_local_benchmark_meets_phase6_budget(runtime_api_env) -> None:
    container = runtime_api_env["app"].state.runtime_container
    service = container.runtime_api_context.lineage
    artifact_id = runtime_api_env["decision_packet_artifact_id"]

    report = service.benchmark_full_lineage_graph([artifact_id])

    assert report["root_count"] == 1
    assert report["node_count"] >= 1
    assert report["p95_ms"] <= 500.0
    assert report["is_complete"] is True
