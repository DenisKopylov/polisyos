# Fabric Time Travel

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-04-17.
Owner: `@fabric-owners`
Source plan: `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/world/store/snapshots.py`, `src/polisyos/fabric/world/materialize/duckdb.py`, `src/polisyos/fabric/world_query.py`, `tests/fabric/test_world_time_travel.py`, `tests/fabric/test_world_materialization.py`

Fabric time travel currently combines bitemporal query predicates with retained
world snapshots.

## Current Query Semantics

`query_world_table()`, `query_claims()`, `query_events()`, and
`execute_world_query()` support point-in-time reads through:

| Input | Meaning |
|---|---|
| `as_of_tx_time` | Transaction-time cutoff |
| `as_of_valid_time` | Valid-time cutoff |
| `snapshot_root` / `snapshot_id` / `branch` | Retained snapshot context for projection-table reads |

Current guardrail: as-of queries for projection tables require retained
snapshot context. The request is rejected if callers ask for projection-table
time travel without `snapshot_root`, `snapshot_id`, or `branch`.

`tests/fabric/test_world_time_travel.py` confirms bitemporal reads over
`world_nodes` without rebuilding projections: the same node returns no label,
then a late-arriving label, then a corrected label as transaction time moves
forward while valid time stays fixed.

## Snapshot And Branch Surface

| API | Purpose |
|---|---|
| `create_world_snapshot()` | Copy a file-backed DuckDB world into a retained snapshot and record tx/valid cutoffs |
| `register_world_snapshot_record()` | Register metadata-only external snapshots |
| `create_world_branch()` | Create a logical branch rooted at one snapshot |
| `resolve_world_snapshot()` | Resolve snapshot id or branch head, optionally with tx/valid cutoffs |
| `gc_world_snapshots()` | Retain/delete snapshot metadata and local artifacts according to policy |
| `merge_world_branch()` | Merge a branch head back into a target branch using deterministic conflict rules |

## Adapter Support

| Adapter | Current state | Notes |
|---|---|---|
| `duckdb_native_file_copy` | Fully supported | Can create snapshots, query them read-only, and merge branches |
| `iceberg_table` | Metadata-only future path | Can be registered as external metadata, but local create/read/merge is not implemented |
| `delta_table` | Metadata-only future path | Same current limitation as `iceberg_table` |

The adapter behavior is not aspirational in docs: tests verify that external
Iceberg/Delta metadata can be registered and garbage-collected, while local
query or snapshot creation against those adapters still fails closed.

## Governance And Retention

| Behavior | Current evidence |
|---|---|
| Snapshot governance metadata is preserved | External snapshot records retain classification, retention scope, and encryption key references |
| Confidential snapshots fail closed without encryption | `create_world_snapshot()` raises when confidential snapshots do not satisfy at-rest encryption requirements |
| Tagged audit snapshots survive GC | `gc_world_snapshots()` keeps tagged snapshots even when older snapshots are deleted |
| Remote URIs are not deleted by local GC | External metadata can be removed without touching the remote `s3://` or `abfss://` path |

## Merge Policies

| Policy | Current behavior |
|---|---|
| `fail_on_conflict` | Raises on conflicting immutable world facts such as `world.kind` |
| `branch_wins` | Branch head values become the merged branch head without mutating the live base database |
| `target_wins` | Target branch keeps the winning value and records one resolved conflict |

`tests/fabric/test_world_time_travel.py` covers all three cases, plus the fact
that branch snapshot queries do not contaminate the live base database.

## Materialization Link

Time travel depends on the current world materialization surface being
transactional and idempotent:

- `tests/fabric/test_world_materialization.py` covers deterministic segment
  application, idempotent re-apply, projection planning, and stale-on-error
  preservation.
- Snapshot retention is layered on top of those materialized DuckDB tables,
  not on raw connector payloads.

## Validation Anchors

```bash
uv run pytest tests/fabric/test_world_materialization.py -q
uv run pytest tests/fabric/test_world_time_travel.py -q
```
