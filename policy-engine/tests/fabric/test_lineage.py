from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polisyos.fabric.provenance.lineage import (
    FabricLineageTracker,
    export_openlineage_json,
    export_visualization_graph,
    impact_analysis,
    trace_claim_origin,
    trace_value_origin,
)


def test_lineage_trace_and_impact_analysis_cover_source_to_query() -> None:
    tracker = FabricLineageTracker("graph.lineage.test")
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(seconds=5)

    tracker.register_source_dataset(
        connector_id="worldbank.wdi",
        dataset_id="NY.GDP.MKTP.CD",
        fields=["gdp_local"],
        schema_id="schema.gdp",
        evidence_ref="evidence.bundle.test",
    )
    _activity_id, outputs = tracker.record_transform_stage(
        stage_name="normalize",
        started_at=started_at,
        completed_at=completed_at,
        input_columns=["gdp_local"],
        output_columns=["gdp_usd"],
        parameters={"field_mappings": {"gdp_local": "gdp_usd"}},
        evidence_refs=["evidence.bundle.test"],
    )
    materialized_node = tracker.record_materialized_column(
        table_name="world_gdp",
        column_name="gdp_usd",
        source_columns=["gdp_usd"],
        segment_id="seg-1",
        evidence_ref="evidence.bundle.test",
    )
    claim_node = tracker.record_claim_field(
        claim_id="claim-1",
        field_name="value",
        source_columns=["gdp_usd"],
        evidence_ref="evidence.bundle.test",
        world_event_id="event-1",
    )
    world_fact_node = tracker.record_world_fact(
        fact_id="fact-1",
        source_nodes=[claim_node, materialized_node],
        segment_id="seg-1",
        world_event_id="event-1",
    )
    query_node = tracker.record_query_result_field(
        query_id="query-1",
        field_name="gdp",
        source_nodes=[materialized_node, world_fact_node],
        query_hash="query-hash-1",
    )

    claim_trace = trace_claim_origin(tracker.graph, "claim-1", field="value")
    query_trace = trace_value_origin(tracker.graph, query_node)
    downstream = impact_analysis(tracker.graph, "schema.gdp", "gdp_local")
    openlineage = export_openlineage_json(tracker.graph)
    visualization = export_visualization_graph(tracker.graph)

    assert outputs["gdp_usd"].startswith("field.transform.")
    assert any(node.kind == "source_field" for node in claim_trace.nodes)
    assert any(node.kind == "evidence_bundle" for node in claim_trace.nodes)
    assert any(node.kind == "source_field" for node in query_trace.nodes)
    assert materialized_node in downstream.materialized_columns
    assert claim_node in downstream.claim_fields
    assert world_fact_node in downstream.world_facts
    assert query_node in downstream.query_result_fields
    assert openlineage["run"]["facets"]["polisyosProvenance"]["graphId"] == "graph.lineage.test"
    assert openlineage["inputs"]
    assert openlineage["outputs"]
    assert visualization["graph_id"] == "graph.lineage.test"
    assert visualization["nodes"]
    assert visualization["edges"]
