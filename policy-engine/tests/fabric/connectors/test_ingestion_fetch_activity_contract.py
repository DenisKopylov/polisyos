from __future__ import annotations

from datetime import datetime, timezone

from polisyos.fabric.ingestion import _build_connector_provenance_graph


def test_provenance_graph_includes_normalized_fetch_activity_fields() -> None:
    started_at = datetime.now(timezone.utc)
    ended_at = datetime.now(timezone.utc)
    datasets = [
        {
            "connector_id": "worldbank.wdi",
            "dataset_id": "NY.GDP.MKTP.CD",
            "fetched_at": started_at.isoformat(),
            "source_updated_at": started_at.isoformat(),
            "fetch_duration_ms": "12.5",
            "cache_key": "sha256:test-cache-key",
            "row_count": 123,
            "completeness": "0.95",
            "schema_id": "worldbank.wdi.generic",
            "schema_version": "1.0.0",
            "version_strategy": "etag",
            "version_value": '"etag-1"',
            "content_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "quality_flags": ["freshness:source_timestamp_missing"],
            "data_artifact_id": "artifact-123",
        }
    ]

    graph = _build_connector_provenance_graph(
        datasets=datasets,
        source="test-source",
        license_name="test-license",
        started_at=started_at,
        ended_at=ended_at,
        manifest_hash="sha256:test-manifest",
    )

    entity = graph.get_entity("dataset.worldbank.wdi.NY.GDP.MKTP.CD")
    assert entity is not None
    attributes = entity.attributes

    assert attributes["version_strategy"] == "etag"
    assert attributes["version_value"] == '"etag-1"'
    assert attributes["source_updated_at"] == started_at.isoformat()
    assert attributes["fetch_duration_ms"] == "12.5"
    assert attributes["quality_flags"] == "freshness:source_timestamp_missing"
