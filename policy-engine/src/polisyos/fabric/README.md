# Fabric (`polisyos.fabric`)

`polisyos.fabric` - data-fabric layer PolicyOS: ingestion, document/claim pipelines,
world materialization, retrieval and connector orchestration.

## Role in System

- **Depends on:** `polisyos.ir`, `polisyos.core`, `polisyos.common`
- **Used by:** `polisyos.scientist`, `polisyos.scholar`, `polisyos.lex`
- Bridges external data sources into CAS artifacts, claims, provenance and queryable world state.

## Key Concepts

- **Connectors** - external source integration with registry, cache, resilience and profile-driven execution.
- **Docs and claims** - document ingestion, normalization, extraction and conflict resolution.
- **World** - append-only facts/materialization layer over DuckDB with optional export paths.
- **Retrieval** - resolve+execute flow from metric intent to fetch plan and promotion.
- **Data plane** - record/replay, streaming and snapshot orchestration for ingestion runs.
- **Provenance** - evidence, trust and fact writer helpers keep lineage explicit.

## Public API

| Type/Function | Description |
|---|---|
| `run_connectors_ingestion()` | Main ingestion entrypoint for connector runs. |
| `fabric_get_data()` | Sync bridge for upper layers. |
| `execute_world_query()` | Query API for materialized world state. |
| `query_world_table()` | Convenience world table query helper. |
| `query_claims()` | Query claims from the world layer. |
| `query_events()` | Query world events from the world layer. |
| `WorldQueryRequest` | Request model for world queries. |
| `WorldQueryError` | Error raised by query helpers. |
| `world` | Lazy module entrypoint for `polisyos.fabric.world`. |

→ Full reference: [docs/reference/fabric/index.md](../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 228 Python files
- Exports: 9
