from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from polisyos.core.observability import get_metrics
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.quota_enforcer import QuotaExceededError
from polisyos.core.security.tenant_quota import TenantQuotaLimits
from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy
from polisyos.fabric.data_plane.orchestrator import (
    IngestionPartition,
    IngestionResult,
    build_partitioned_ingestion_plan,
    run_partitioned_ingestion,
)
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.storage.tenant_cas import TenantScopedCAS
from polisyos.fabric.world.materialize import plan_world_materialization_shards
from polisyos.fabric.world.store import (
    append_world_segment_index,
    emit_world_node_facts,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy
from polisyos.ir.fact_log import FactSegmentManifest
from polisyos.ir.world.abi import NodeKind


def test_tenant_scoped_cas_isolates_artifacts_and_enforces_quota(tmp_path: Path):
    tenant_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    tenant_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    store_a = TenantScopedCAS(tmp_path / ".polisyos", tenant_id=tenant_a)
    store_b = TenantScopedCAS(tmp_path / ".polisyos", tenant_id=tenant_b)

    ref = store_a.put_json(
        {"rows": [{"value": 1}]},
        PutOptions(
            kind="fabric.test_payload",
            media_type="application/json",
            schema=SchemaInfo(name="test.payload", version="1.0"),
        ),
    )

    assert store_a.has(ref.artifact_id) is True
    assert store_b.has(ref.artifact_id) is False
    with pytest.raises(FileNotFoundError):
        store_b.get_bytes(ref.artifact_id)

    quota_store = TenantScopedCAS(
        tmp_path / ".quota",
        tenant_id=tenant_a,
        quota_limits=TenantQuotaLimits(max_storage_bytes=128),
    )
    with pytest.raises(QuotaExceededError):
        quota_store.put_bytes(
            b"x" * 1_024,
            PutOptions(
                kind="fabric.large_blob",
                media_type="application/octet-stream",
                schema=SchemaInfo(name="test.blob", version="1.0"),
            ),
        )

    exported = store_a.artifact_store_config()
    assert exported.backend == "filesystem"
    assert exported.root == str(store_a.root)


def test_tenant_scoped_connector_cache_isolated_and_metrics_labeled(tmp_path: Path):
    tenant_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    tenant_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    cache_a = ConnectorCacheStore(
        TenantScopedCAS(tmp_path / ".polisyos", tenant_id=tenant_a),
        TTLPolicy(ttl=timedelta(hours=1)),
    )
    cache_b = ConnectorCacheStore(
        TenantScopedCAS(tmp_path / ".polisyos", tenant_id=tenant_b),
        TTLPolicy(ttl=timedelta(hours=1)),
    )

    request = FetchRequest(dataset_id="events")
    now = datetime.now(timezone.utc)
    cache_a.put(
        request,
        FetchResult(
            data={"tenant": "a"},
            row_count=1,
            schema_id="test.schema",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value="a",
                timestamp=now,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
        ),
        connector_id="stream.jsonl",
    )
    cache_b.put(
        request,
        FetchResult(
            data={"tenant": "b"},
            row_count=1,
            schema_id="test.schema",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value="b",
                timestamp=now,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
        ),
        connector_id="stream.jsonl",
    )

    assert cache_a.get(request, connector_id="stream.jsonl").result.data == {"tenant": "a"}
    assert cache_b.get(request, connector_id="stream.jsonl").result.data == {"tenant": "b"}

    metrics = get_metrics()
    assert metrics.connector_cache_entries_total is not None
    gauge_keys = list(metrics.connector_cache_entries_total._values.keys())
    assert any(("tenant_id", tenant_a) in key for key in gauge_keys)
    assert any(("tenant_id", tenant_b) in key for key in gauge_keys)


def test_world_segment_metrics_are_tenant_scoped(tmp_path: Path):
    provenance = stable_world_provenance_v1()
    facts = emit_world_node_facts(
        node_id="doc.source",
        kind=NodeKind.DOC_SOURCE,
        label="Doc",
        artifact_id=None,
        props_ref=None,
        provenance=provenance,
    )
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="tenant-world",
    ).model_copy(
        update={"stats": {"tenant_id": "tenant-a", "dataset_id": "world"}}
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)

    metrics = get_metrics()
    assert metrics.fabric_segment_count is not None
    gauge_keys = list(metrics.fabric_segment_count._values.keys())
    assert any(("tenant_id", "tenant-a") in key for key in gauge_keys)


def test_run_partitioned_ingestion_resumes_failed_partitions_independently(tmp_path: Path):
    plan = build_partitioned_ingestion_plan(
        connector_id="stream.jsonl",
        dataset_id="events",
        partition_key="region",
        partitions=[
            {"partition_id": "p0", "bounds": {"region": "ua"}},
            {"partition_id": "p1", "bounds": {"region": "pl"}},
        ],
    )
    attempts = {"p1": 0}

    def handler(partition: IngestionPartition) -> IngestionResult:
        if partition.partition_id == "p1" and attempts["p1"] == 0:
            attempts["p1"] += 1
            raise RuntimeError("simulated partition failure")
        return IngestionResult(
            datasets_fetched=1,
            cursor_ref=f"cursor:{partition.partition_id}",
        )

    first = run_partitioned_ingestion(
        plan=plan,
        connector_manifest={"datasets": []},
        source="test",
        license_name="open",
        cas_root=tmp_path / ".polisyos",
        partition_handler=handler,
    )
    assert {result.partition_id: result.status for result in first} == {
        "p0": "succeeded",
        "p1": "failed",
    }

    second = run_partitioned_ingestion(
        plan=plan,
        connector_manifest={"datasets": []},
        source="test",
        license_name="open",
        cas_root=tmp_path / ".polisyos",
        partition_handler=handler,
    )
    assert {result.partition_id: result.status for result in second} == {
        "p0": "skipped",
        "p1": "succeeded",
    }

    cursor_store = CursorStore(FileSystemCAS(tmp_path / ".polisyos"))
    states = cursor_store.list_partition_states(plan_id=plan.plan_id)
    assert {state.partition_id: state.status for state in states} == {
        "p0": "succeeded",
        "p1": "succeeded",
    }


def test_plan_world_materialization_shards_groups_by_tenant_dataset_and_time():
    manifests = [
        FactSegmentManifest(
            segment_id="seg.a",
            path="/tmp/seg.a.parquet",
            row_count=10,
            sha256="a" * 64,
            time_end="2024-06-15T00:00:00+00:00",
            stats={"tenant_id": "tenant-a", "dataset_id": "world"},
        ),
        FactSegmentManifest(
            segment_id="seg.b",
            path="/tmp/seg.b.parquet",
            row_count=12,
            sha256="b" * 64,
            time_end="2024-06-20T00:00:00+00:00",
            stats={"tenant_id": "tenant-a", "dataset_id": "world"},
        ),
        FactSegmentManifest(
            segment_id="seg.c",
            path="/tmp/seg.c.parquet",
            row_count=8,
            sha256="c" * 64,
            time_end="2024-07-01T00:00:00+00:00",
            stats={"tenant_id": "tenant-b", "dataset_id": "claims"},
        ),
    ]

    shards = plan_world_materialization_shards(manifests)
    assert [(shard.tenant_id, shard.dataset_id, shard.time_partition) for shard in shards] == [
        ("tenant-a", "world", "2024-06"),
        ("tenant-b", "claims", "2024-07"),
    ]
    assert shards[0].segment_ids == ("seg.a", "seg.b")
