# ADR-0042: DuckDB for SKG Storage

## Status

Proposed

## Date

2026-02-28

## Context

The Scientific Knowledge Graph (SKG) requires analytical query capability for aggregation
across studies, filtering by variable, context, and time period. SQLite was considered but
lacks efficient columnar aggregation. DuckDB aligns with existing `graph_builder.py` patterns
in the academic batch pipeline and provides analytical SQL without requiring a separate server
process.

## Decision

1. DuckDB is the storage backend for the SKG, replacing any prior consideration of SQLite or
   flat-file storage.
2. Columnar storage is used for the `skg_edges`, `skg_articles`, and `skg_variables` tables to
   enable fast aggregation queries (e.g., "all edges where treatment = 'carbon_tax'").
3. The DuckDB file is stored at `data/skg/skg.duckdb` relative to the project root, with a
   companion `_manifest.json` tracking schema version.
4. Read queries use DuckDB's native SQL; write operations go through the `skg_store.py`
   abstraction layer to enforce schema invariants.
5. DuckDB's Parquet export capability is used for snapshot/archival purposes.

## Consequences

### Positive

- Columnar storage provides order-of-magnitude speedup for analytical aggregation queries
  compared to SQLite row-oriented storage.

- No server process required; DuckDB runs in-process like SQLite.
- Natural alignment with the existing batch pipeline's DuckDB usage in `graph_builder.py`.
- Parquet export enables interoperability with external analytical tools.

### Negative

- DuckDB is less battle-tested than SQLite for concurrent write workloads (acceptable since
  SKG writes are batch-only).

- Adds `duckdb` as a required dependency in the academic module.
- Schema migrations must be handled manually via version tracking in `_manifest.json`.
