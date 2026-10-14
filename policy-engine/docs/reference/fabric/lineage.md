# Fabric Lineage

Related explanation: [Data Fabric](../../explanation/data-fabric.md). Related
runtime boundary: [data plane](data-plane.md).

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Source of truth: `policy-engine/src/polisyos/fabric/provenance/lineage.py`,
  `policy-engine/src/polisyos/fabric/ingestion/ingestion.py`,
  `policy-engine/src/polisyos/fabric/connectors/transform/`, and the tests
  named below.
Evidence level: source and focused unit-test behavior inspected at the
source pin. The tests establish graph operations and the specifically named
instrumentation/ingestion paths; they do not establish automatic full-chain
capture.
Test status: tests were inspected but not run in this documentation pass.

`FabricLineageTracker` is a graph builder over `ProvenanceCoreGraph`. There is
one bounded runtime capture path: with CAS configured, when connector ingestion
applies a transform pipeline, it registers the source dataset and fields, the
transform pipeline records its stages, and ingestion merges that graph into its
connector provenance graph before persisting the graph and referencing it from
an `EvidenceBundle`. The captured graph covers the source and transform
relationships that this path records.

The tracker also provides methods for materialized columns, claim fields, world
facts, and query-result fields. Those methods allow a caller to build a larger
graph, but they are not wired by the inspected Fabric world materializer,
claim producer, or query helper. Graph capability therefore does not show that
those producers and consumers automatically contribute to one shared lineage
record.

`policy-engine/docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md` keeps the
broader target of lineage that answers origin and impact across
ingestion, materialization, and query. The current implementation evidence
below separates that target from the bounded graph capture and manually
assembled examples that exist at this pin.

## Graph kinds the helper can represent

| Kind | Builder method | Scope at this pin |
| --- | --- | --- |
| `source_dataset`, `source_field` | `register_source_dataset()` | Called by connector ingestion when it sets up a transform tracker. |
| `evidence_bundle` | `attach_evidence_bundle()` | Available to callers and can be reached from transform recording when evidence refs are supplied; this is not a universal evidence-bundle attachment. |
| `transform_field` | `record_transform_stage()` | Called by transform instrumentation when a tracker is passed in `TransformContext`. |
| `materialized_column` | `record_materialized_column()` | Builder method; no runtime producer callsite was found in the inspected Fabric paths. |
| `claim_field` | `record_claim_field()` | Builder method; no runtime producer callsite was found in the inspected Fabric paths. |
| `world_fact` | `record_world_fact()` | Builder method; no runtime producer callsite was found in the inspected Fabric paths. |
| `world_event`, `fact_segment` | Internal tracker helpers used by related record methods | Nodes are created when a caller invokes methods that bind those event or segment references. |
| `query_result_field` | `record_query_result_field()` | Builder method; no runtime query-helper callsite was found in the inspected Fabric paths. |

The helper methods are defined in
`policy-engine/src/polisyos/fabric/provenance/lineage.py`. In connector
ingestion, `policy-engine/src/polisyos/fabric/ingestion/ingestion.py` creates a
tracker only when a transform pipeline can be applied, and
`policy-engine/src/polisyos/fabric/connectors/transform/_common.py` records
transform stages through the supplied context. Ingestion then merges that
graph into the fetch provenance graph, persists it as `fabric.provenance_graph`,
and stores the reference in the evidence bundle. A pipeline-free connector run
does not create these transform-stage nodes.

## Graph operations

| API | Operation |
| --- | --- |
| `trace_value_origin()` | Walk upstream from a field or node to recorded source inputs. |
| `trace_column_lineage()` | Resolve graph lineage for a materialized column when such a node is present. |
| `trace_claim_origin()` | Resolve graph lineage for a claim field when such a node is present. |
| `impact_analysis()` | Walk downstream through graph edges that were recorded for a source field. |
| `export_openlineage_json()` | Serialize the supplied graph as an OpenLineage-shaped view. |
| `export_visualization_graph()` | Project the supplied graph into a visualization payload. |

These functions operate on the graph they receive. They cannot discover
relationships absent from that graph. The visualization projection fills
`verification.status` and `verification.freshness` with `verified` and
`current` when those metadata values are absent. Those defaults describe the
projection payload; they do not verify producer coverage, source truth, or
operational freshness.

## Tested behavior and its limits

| Test | What it demonstrates | What it does not demonstrate |
| --- | --- | --- |
| `policy-engine/tests/unit/fabric/test_lineage.py::test_lineage_trace_and_impact_analysis_cover_source_to_query` | The test manually calls the tracker methods to build a source → transform → materialized column/claim/world fact/query graph, then checks traces, impact results, and export payloads. | Automatic capture of those downstream nodes from the operational materializer, claim producer, world emitter, or query helper. |
| `policy-engine/tests/unit/fabric/connectors/test_ingestion_fetch_activity_contract.py::test_provenance_graph_merges_transform_lineage_graphs` | The connector provenance builder merges a transform graph supplied by the test. | A fetch-to-world-materialization or fetch-to-query lineage run; the test manually constructs the transform graph and calls the builder. |
| `policy-engine/tests/unit/fabric/test_fabric_observability.py::test_transform_pipeline_emits_fabric_stage_span_and_lineage_metrics` | A transform pipeline given a tracker in its context records transform lineage and emits the tested span and graph-size metrics. | Persistence of the graph or automatic lineage capture for world facts, claims, materialized columns, or query outputs. |

The resulting capability states are:

- **Connector fetch and configured transforms to a persisted provenance graph:**
  implemented with CAS configured in
  `policy-engine/src/polisyos/fabric/ingestion/ingestion.py`; transform nodes
  are conditional on an applicable configured pipeline.
- **Generic connector-result-to-world-fact bridge:** `bridge_missing`;
  document and claim producers emit their own world facts and segments, as
  described in the [data-plane reference](data-plane.md).
- **Automatic source-to-query lineage across connector ingestion, world
  materialization, claims, and query:** `semantic_test_missing`; the all-node
  test assembles the graph by calling tracker methods directly.
- **Source truth and operational freshness inferred from exported lineage:**
  `not_established`; graph edges and projection defaults establish only what
  their recorded inputs and metadata say.

## API Reference

::: polisyos.fabric.provenance.lineage
