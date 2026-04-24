from __future__ import annotations

from datetime import UTC, datetime

from polisyos.fabric.ingestion import _build_connector_provenance_graph
from polisyos.fabric.provenance.lineage import FabricLineageTracker


def test_provenance_graph_includes_normalized_fetch_activity_fields() -> None:
    started_at = datetime.now(UTC)
    ended_at = datetime.now(UTC)
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


def test_provenance_graph_merges_transform_lineage_graphs() -> None:
    started_at = datetime.now(UTC)
    ended_at = datetime.now(UTC)
    tracker = FabricLineageTracker("transform-lineage")
    tracker.register_source_dataset(
        connector_id="worldbank.wdi",
        dataset_id="NY.GDP.MKTP.CD",
        fields=["gdp"],
        schema_id="worldbank.wdi.generic",
    )
    tracker.record_transform_stage(
        stage_name="normalize",
        started_at=started_at,
        completed_at=ended_at,
        input_columns=["gdp"],
        output_columns=["gdp_usd"],
        parameters={"field_mappings": {"gdp": "gdp_usd"}},
        evidence_refs=["evidence.bundle.test"],
    )

    graph = _build_connector_provenance_graph(
        datasets=[
            {
                "connector_id": "worldbank.wdi",
                "dataset_id": "NY.GDP.MKTP.CD",
                "fetched_at": started_at.isoformat(),
                "source_updated_at": started_at.isoformat(),
                "fetch_duration_ms": "12.5",
                "cache_key": "sha256:test-cache-key",
                "row_count": 1,
                "completeness": "1.0",
                "schema_id": "worldbank.wdi.generic",
                "schema_version": "1.0.0",
                "version_strategy": "etag",
                "version_value": '"etag-1"',
                "content_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "quality_flags": [],
                "data_artifact_id": "artifact-123",
            }
        ],
        source="test-source",
        license_name="test-license",
        started_at=started_at,
        ended_at=ended_at,
        manifest_hash="sha256:test-manifest",
        transform_lineage_graphs=[tracker.graph],
    )

    assert any(
        activity.parameters.get("stage_name") == "normalize"
        for activity in graph.activities.values()
    )
    assert any(
        entity.attributes.get("lineage_kind") == "transform_field"
        and entity.attributes.get("field") == "gdp_usd"
        for entity in graph.entities.values()
    )
