from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.storage.tenant_cas import TenantSidecarScope
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy

_TENANT_A = "00000000-0000-0000-0000-00000000000a"
_TENANT_B = "00000000-0000-0000-0000-00000000000b"
_PATH_TENANT = "00000000-0000-0000-0000-0000000000ff"


def test_cursor_sidecars_do_not_alias_for_tenants_on_path_with_tenants_component(
    tmp_path: Path,
) -> None:
    base_root = tmp_path / "policy" / "tenants" / _PATH_TENANT / "cas"
    artifact_store = FileSystemCAS(base_root)
    scope_a = TenantSidecarScope.for_base_root(base_root, _TENANT_A)
    scope_b = TenantSidecarScope.for_base_root(base_root, _TENANT_B)
    cursors_a = CursorStore(artifact_store, index_root=scope_a.cursor_index_root)
    cursors_b = CursorStore(artifact_store, index_root=scope_b.cursor_index_root)

    def save(cursor_store: CursorStore, value: str) -> None:
        cursor_store.save_cursor(
            CursorState(
                cursor_id="connector:dataset",
                connector_id="connector",
                dataset_id="dataset",
                watermark_type=WatermarkType.OFFSET,
                watermark_value=value,
                created_at=datetime(2026, 9, 28, tzinfo=UTC),
            )
        )

    save(cursors_a, "a1")
    save(cursors_b, "b1")
    save(cursors_a, "a2")

    assert cursors_a._index_path != cursors_b._index_path
    assert cursors_a.find_latest_cursor("connector", "dataset").watermark_value == "a2"
    assert cursors_b.find_latest_cursor("connector", "dataset").watermark_value == "b1"


def test_connector_cache_indexes_are_isolated_and_tenant_identity_is_explicit(
    tmp_path: Path,
) -> None:
    base_root = tmp_path / "policy" / "tenants" / _PATH_TENANT / "cas"
    artifact_store = FileSystemCAS(base_root)
    scope_a = TenantSidecarScope.for_base_root(base_root, _TENANT_A)
    scope_b = TenantSidecarScope.for_base_root(base_root, _TENANT_B)
    policy = TTLPolicy(ttl=timedelta(hours=1))
    cache_a = ConnectorCacheStore(
        artifact_store,
        policy,
        namespace=scope_a.cache_namespace("connector_cache"),
        tenant_id=scope_a.tenant_id,
    )
    cache_b = ConnectorCacheStore(
        artifact_store,
        policy,
        namespace=scope_b.cache_namespace("connector_cache"),
        tenant_id=scope_b.tenant_id,
    )
    request = FetchRequest(dataset_id="tenant-scope-test")
    now = datetime(2026, 9, 28, tzinfo=UTC)

    def result(value: str) -> FetchResult:
        digest = "sha256:" + hashlib.sha256(value.encode()).hexdigest()
        return FetchResult(
            data=[{"value": value}],
            row_count=1,
            schema_id="tenant-scope-test",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=digest,
                timestamp=now,
                content_hash=digest,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
        )

    try:
        cache_a.put(request, result("a"), connector_id="connector")
        cache_b.put(request, result("b"), connector_id="connector")

        assert cache_a._tenant_id == _TENANT_A
        assert cache_b._tenant_id == _TENANT_B
        assert cache_a._cache_root != cache_b._cache_root
        assert cache_a.get(request, connector_id="connector").result.data[0]["value"] == "a"
        assert cache_b.get(request, connector_id="connector").result.data[0]["value"] == "b"

        assert cache_a.hard_delete(connector_id="connector", dataset_id="tenant-scope-test") == 1
        assert cache_b.get(request, connector_id="connector") is not None
    finally:
        cache_a.close()
        cache_b.close()
