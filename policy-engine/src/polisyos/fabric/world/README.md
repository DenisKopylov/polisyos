# World (`polisyos.fabric.world`)

`world` - append-only fact store and materialization layer that turns Fabric
segments into queryable world state.

## Role in System

- **Depends on:** `polisyos.fabric.world.store`, `polisyos.fabric.world.materialize`
- **Used by:** `fabric.docs`, `fabric.claims`, `fabric.world_query`, retrieval and runtime consumers
- Keeps world facts, events and projections consistent across DuckDB and optional export targets.

## Key Concepts

- **Segment store** - writes and validates append-only fact segments.
- **Materialization** - applies segments into DuckDB projections and optional Kuzu export.
- **Merge strategy** - explicit conflict semantics for repeated materialization.
- **Schema management** - DDL and online schema updates are part of the world layer.

## Public API

| Type/Function | Description |
|---|---|
| `write_world_fact_segment()` | Writes a fact segment to the world store. |
| `persist_world_event()` | Persists a deterministic world event. |
| `ensure_world_schema()` | Ensures the DuckDB world schema exists. |
| `apply_world_segment()` | Applies one world segment transactionally. |
| `ensure_world_materialized()` | Materializes a batch of segments. |
| `materialize_world_duckdb_from_fact_log()` | Materializes the world from a fact log root. |
| `materialize_world_kuzu_from_duckdb()` | Optional Kuzu export path. |
| `MergeStrategy` | Merge policy for repeated materialization. |
| `WorldMergeConflict` | Raised when merge semantics conflict. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 18 Python files
- Exports: 35
