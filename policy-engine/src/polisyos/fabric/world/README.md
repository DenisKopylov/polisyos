# World (`polisyos.fabric.world`)

`polisyos.fabric.world` is the append-only fact store and materialization layer
that turns Fabric segments, claims, events, quality reports, and provenance
into queryable world state.

Last updated: 2026-04-17.

## Purpose

Use this package when you need the write path for world facts and events, the
materialization path into DuckDB or Kuzu, or the retained snapshot and branch
mechanics behind time travel and recovery workflows.

## Where to Start

- Read [__init__.py](./__init__.py) for the package facade used by
  `fabric.docs`, `fabric.claims`, and `fabric.world_query`.

- Read [store/__init__.py](./store/__init__.py),
  [store/persist.py](./store/persist.py), and
  [store/segments.py](./store/segments.py) for the append-only write path.

- Read [store/snapshots.py](./store/snapshots.py),
  [materialize/duckdb.py](./materialize/duckdb.py), and
  [materialize/rules.py](./materialize/rules.py) for materialization and time
  travel behavior.

- Follow downstream links to [../docs/README.md](../docs/README.md),
  [../claims/README.md](../claims/README.md), and
  [../../../../tests/unit/fabric/README.md](../../../../tests/unit/fabric/README.md) for
  pipeline and validation context.

## Public Entrypoints

| Entrypoint                                                                 | Description                                                        |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `write_world_fact_segment()`                                               | Persist a validated fact segment into the world store.             |
| `persist_world_event()`                                                    | Persist a deterministic world event artifact.                      |
| `persist_doc_meta()` / `persist_claim()` / `persist_conflict_set()`        | Write typed world objects and supporting artifacts.                |
| `validate_world_facts()` and ID validators                                 | Fail closed on ABI and identifier mismatches before persistence.   |
| `ensure_world_schema()` / `apply_world_segment()`                          | Ensure schema and apply one segment transactionally.               |
| `ensure_world_materialized()` / `materialize_world_duckdb_from_fact_log()` | Materialize a fact-log root into DuckDB projections.               |
| `materialize_world_kuzu_from_duckdb()`                                     | Optional graph-export path for Kuzu.                               |
| `MergeStrategy` / `WorldMergeConflict`                                     | Conflict model for repeated materialization and branch merges.     |
| `polisyos.fabric.world.store.create_world_snapshot()` and related helpers  | Snapshot, branch, GC, and merge helpers used by time-travel flows. |

## Depends On / Depended On By

- Depends on: `polisyos.ir.world`, CAS artifact storage, DuckDB and optional
  Kuzu materializers, and `polisyos.fabric.data_plane.quarantine`.

- Depended on by: `polisyos.fabric.docs`, `polisyos.fabric.claims`,
  `polisyos.fabric.world.query`, `polisyos.lex`, `polisyos.scholar`, and
  runtime consumers reading materialized world tables.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg -n "write_world_fact_segment|persist_world_event|ensure_world_materialized" src/polisyos/fabric/world`
  Jump to the world write and materialization facade. Smoke-tested on
  2026-04-17.

- `rg --files src/polisyos/fabric/world/store src/polisyos/fabric/world/materialize | sort`
  Survey the store and materialize subpackages. Smoke-tested on 2026-04-17.

- `rg -n "create_world_snapshot|merge_world_branch|resolve_world_snapshot" src/polisyos/fabric/world src/polisyos/fabric/world_query.py`
  Jump to time-travel and branch-management helpers. Smoke-tested on
  2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/test_world_store.py tests/unit/fabric/test_world_materialization.py -q`
  World write-path and materialization smoke suite. Smoke-tested on
  2026-04-17.

- `uv run pytest tests/unit/fabric/test_world_time_travel.py tests/unit/fabric/test_world_query_multibackend.py -q`
  Time-travel and query smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/test_lineage.py tests/unit/fabric/test_access_control.py -q`
  Lineage and access-control coverage for world consumers. Conceptual in this
  README refresh; not run in this pass.

## Reference Docs

- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Fabric lineage reference](../../../../docs/reference/fabric/lineage.md)
- [Fabric time-travel reference](../../../../docs/reference/fabric/time-travel.md)
- [E2.2 World store contract](../../../../docs/contracts/E2_2_FABRIC_WORLD_STORE_EMIT_FACTS_WORLD_EVENT.md)
- [E2.3 DuckDB materialization contract](../../../../docs/contracts/E2_3_FABRIC_WORLD_DUCKDB_MATERIALIZATION_V1_0.md)
- [Fabric tests map](../../../../tests/unit/fabric/README.md)
