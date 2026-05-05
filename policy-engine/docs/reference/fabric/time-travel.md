# Fabric Time Travel

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-04-26.
Owner: `@fabric-owners`
Source plan: `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/world/store/snapshots.py`, `src/polisyos/fabric/world/materialize/duckdb.py`, `src/polisyos/fabric/world_query.py`, `tests/unit/fabric/test_world_time_travel.py`, `tests/unit/fabric/test_world_materialization.py`
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)

Fabric time travel combines bitemporal query predicates with retained world
snapshots, governed branches, and append-only correction/revocation metadata.

## Current Query Semantics

`query_world_table()`, `query_claims()`, `query_events()`, and
`execute_world_query()` support point-in-time reads through:

| Input                                      | Meaning                                              |
| ------------------------------------------ | ---------------------------------------------------- |
| `as_of_tx_time`                            | Transaction-time cutoff                              |
| `as_of_valid_time`                         | Valid-time cutoff                                    |
| `snapshot_root` / `snapshot_id` / `branch` | Retained snapshot context for projection-table reads |

Current guardrail: as-of queries for projection tables require retained
snapshot context. The request is rejected if callers ask for projection-table
time travel without `snapshot_root`, `snapshot_id`, or `branch`.

`tests/unit/fabric/test_world_time_travel.py` confirms bitemporal reads over
`world_nodes` without rebuilding projections: the same node returns no label,
then a late-arriving label, then a corrected label as transaction time moves
forward while valid time stays fixed.

## Snapshot And Branch Surface

<!-- markdownlint-disable MD060 -->

| API                                | Purpose                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------ |
| `create_world_snapshot()`          | Copy a file-backed DuckDB world into a retained snapshot and record tx/valid cutoffs |
| `register_world_snapshot_record()` | Register metadata-only external snapshots                                            |
| `create_world_branch()`            | Create a governed observed or scenario branch rooted at one snapshot                 |
| `update_world_branch_head()`       | Move a branch head with actor/reason/audit evidence                                  |
| `resolve_world_snapshot()`         | Resolve snapshot id or branch head, optionally with tx/valid cutoffs                 |
| `gc_world_snapshots()`             | Retain/delete snapshot metadata and local artifacts according to policy              |
| `merge_world_branch()`             | Merge a branch head back into a target branch using deterministic conflict rules     |
| `delete_world_branch()`            | Mark a branch deleted while retaining governance evidence                            |
| `export_world_branch_governance()` | Export branch governance evidence for review/audit                                  |

Branch metadata follows `schemas/fabric/world_branch.schema.json`. Scenario
branches additionally follow `schemas/fabric/scenario_branch.schema.json` and
carry `observed_state=simulated`; they do not satisfy observed-world queries
unless a caller explicitly selects the scenario branch/scope.

## Mutation Semantics

World facts remain append-only. Runtime tables are not updated in place to
correct history. Instead, emit helpers can attach parseable mutation metadata
to fact provenance notes:

| Mutation kind         | Meaning                                                               |
| --------------------- | --------------------------------------------------------------------- |
| `assertion`           | Ordinary observed fact assertion                                      |
| `correction`          | Late or revised source fact that points at `corrects_fact_ref`        |
| `revocation`          | Explicit withdrawal that points at `revokes_fact_ref`                 |
| `branch_assertion`    | Assertion scoped to a non-base branch                                 |
| `scenario_assertion`  | Simulated counterfactual assertion scoped to a scenario branch        |

Corrections require actor, reason, source evidence refs, lineage ref, and the
fact being corrected. Revocations require actor, reason, source evidence refs,
and the revoked fact. The same `valid_at` with different `tx_at` therefore
replays late-arriving correction behavior without overwriting older facts.

## Adapter Support

| Adapter                   | Current state             | Notes                                                                                  |
| ------------------------- | ------------------------- | -------------------------------------------------------------------------------------- |
| `duckdb_native_file_copy` | Fully supported           | Can create snapshots, query them read-only, and merge branches                         |
| `iceberg_table`           | Metadata-only future path | Can be registered as external metadata, but local create/read/merge is not implemented |
| `delta_table`             | Metadata-only future path | Same current limitation as `iceberg_table`                                             |

The adapter behavior is not aspirational in docs: tests verify that external
Iceberg/Delta metadata can be registered and garbage-collected, while local
query or snapshot creation against those adapters still fails closed.

## Governance And Retention

| Behavior                                              | Current evidence                                                                                            |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Snapshot governance metadata is preserved             | External snapshot records retain classification, retention scope, and encryption key references             |
| Confidential snapshots fail closed without encryption | `create_world_snapshot()` raises when confidential snapshots do not satisfy at-rest encryption requirements |
| Tagged audit/legal snapshots survive GC               | `gc_world_snapshots()` keeps audit/legal-hold snapshots and active branch heads even when older snapshots are deleted |
| Legal-hold snapshots require encryption metadata      | Snapshots tagged `legal_hold` require verified encryption metadata and an encryption key reference           |
| Remote URIs are not deleted by local GC               | External metadata can be removed without touching the remote `s3://` or `abfss://` path                     |
| Branch governance is exportable                       | Branch create/head/merge/delete events retain actor, reason, strategy, conflicts, and audit refs            |

<!-- markdownlint-enable MD060 -->

## Merge Policies

| Policy             | Current behavior                                                                         |
| ------------------ | ---------------------------------------------------------------------------------------- |
| `fail_on_conflict` | Raises on conflicting immutable world facts such as `world.kind`                         |
| `branch_wins`      | Branch head values become the merged branch head without mutating the live base database |
| `target_wins`      | Target branch keeps the winning value and records one resolved conflict                  |

Merge conflicts are typed as `WorldBranchMergeConflictError`, exportable for
review, and summarized in branch governance evidence. `tests/unit/fabric/test_world_time_travel.py`
and `tests/unit/fabric/test_world_branch_governance.py` cover all three policies,
plus the fact that branch snapshot queries do not contaminate the live base
database.

## Temporal Capabilities And Indexes

`GET /api/v1/temporal/capabilities` reports:

- supported world tables;
- unsupported runtime surfaces;
- valid/tx ranges and nearest event points;
- branch, snapshot, and explicit-only scenario branch support;
- DuckDB temporal indexes and slow-query gates;
- `graph_temporal_scope=partial` for Kuzu until full bitemporal graph traversal
  is proven in research track R3.

DuckDB uses paired `(tx_time, valid_time)` and `(valid_time, tx_time)` indexes
on `world.world_facts` and `world.world_edges`. Kuzu exports carry edge
`tx_time` and `valid_time`, but graph temporal traversal remains labelled
partial by capability responses.

## Materialization Link

Time travel depends on the current world materialization surface being
transactional and idempotent:

- `tests/unit/fabric/test_world_materialization.py` covers deterministic segment
  application, idempotent re-apply, projection planning, and stale-on-error
  preservation.

- Snapshot retention is layered on top of those materialized DuckDB tables,
  not on raw connector payloads.

## Validation Anchors

```bash
uv run pytest tests/unit/fabric/test_world_materialization.py -q
uv run pytest tests/unit/fabric/test_world_time_travel.py -q
uv run pytest tests/unit/fabric/test_world_branch_governance.py -q
uv run pytest tests/unit/fabric/test_world_temporal_capabilities.py -q
```
