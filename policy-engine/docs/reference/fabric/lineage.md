# Fabric Lineage

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-04-26.
Owner: `@fabric-owners`
Source plan: `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/provenance/lineage.py`, `src/polisyos/fabric/observability.py`, `tests/fabric/test_lineage.py`, `tests/fabric/test_fabric_observability.py`
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)

Fabric lineage is currently a provenance-graph layer built around
`FabricLineageTracker`. It records how source datasets and fields flow through
transforms, evidence bundles, materialized columns, claims, world facts, and
query outputs.

## Current Node Kinds

| Kind                  | Emitted by                              | Meaning                                                            |
| --------------------- | --------------------------------------- | ------------------------------------------------------------------ |
| `source_dataset`      | `register_source_dataset()`             | One connector dataset input                                        |
| `source_field`        | `register_source_dataset()`             | One input field inside that dataset                                |
| `evidence_bundle`     | `attach_evidence_bundle()`              | CAS evidence bundle attached to lineage                            |
| `transform_field`     | `record_transform_stage()`              | Output field produced by one transform activity                    |
| `materialized_column` | `record_materialized_column()`          | Column persisted into a world/materialized table                   |
| `claim_field`         | `record_claim_field()`                  | Claim payload field produced from upstream evidence                |
| `world_fact`          | `record_world_fact()`                   | Fact node emitted into the world store                             |
| `world_event`         | internal world-event attachment helpers | Event node linked to facts/claims/materializations                 |
| `fact_segment`        | internal segment attachment helpers     | Segment node connecting materialized outputs to stored world facts |
| `query_result_field`  | `record_query_result_field()`           | Output field returned by one world/query surface                   |

## Trace And Export APIs

| API                            | Purpose                                                                                 |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| `trace_value_origin()`         | Walk upstream from a field/node id to its source inputs                                 |
| `trace_column_lineage()`       | Resolve lineage for a materialized column                                               |
| `trace_claim_origin()`         | Resolve upstream lineage for a claim field                                              |
| `impact_analysis()`            | Walk downstream from one source field to claims, facts, query outputs, and world events |
| `export_openlineage_json()`    | Emit an OpenLineage-shaped JSON view                                                    |
| `export_visualization_graph()` | Emit a graph payload for UI/diagnostic visualization                                    |

## Tested End-To-End Example

`tests/fabric/test_lineage.py` is the factual example that the current docs
should follow:

| Stage           | Test value                                                             |
| --------------- | ---------------------------------------------------------------------- |
| Source dataset  | connector `worldbank.wdi`, dataset `NY.GDP.MKTP.CD`, field `gdp_local` |
| Transform stage | `normalize` mapping `gdp_local -> gdp_usd`                             |
| Materialization | table `world_gdp`, column `gdp_usd`, segment `seg-1`                   |
| Claim output    | claim `claim-1`, field `value`                                         |
| World output    | fact `fact-1`, event `event-1`                                         |
| Query output    | query `query-1`, field `gdp`                                           |

The assertions in that test confirm that one lineage graph can produce:

- upstream traces from claim and query outputs back to `source_field`;
- downstream impact sets for materialized columns, claims, facts, and queries;
- OpenLineage JSON with graph id `graph.lineage.test`;
- visualization graph payloads with populated node and edge lists.

## Observability Hooks

Lineage is also part of the current Fabric observability surface:

| Signal               | Current evidence                                                                                                                       |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Transform-stage span | `tests/fabric/test_fabric_observability.py` checks the `transform_stage` span name and `transform.stage_name` attributes               |
| Graph size metrics   | The same test checks `fabric_lineage_graph_nodes` and `fabric_lineage_graph_edges` counters after a normalized transform               |
| Health snapshot      | `build_fabric_health_snapshot()` reports Fabric component health and emits connector/cache alerts separately from lineage graph export |

## Validation Anchors

```bash
uv run pytest tests/fabric/test_lineage.py -q
uv run pytest tests/fabric/test_fabric_observability.py -q
```

## API Reference

::: polisyos.fabric.provenance.lineage
