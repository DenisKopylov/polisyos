# ADR-0122: Lakehouse Snapshot Semantics

## Status
Proposed

## Date
2026-04-18

## Context

Data Forge already persists artifacts via CAS (ADR-0010, ADR-0098) and
materialises domain views into DuckDB. Production-grade data platforms add
snapshot semantics on top of CAS: every successful pipeline run produces a
single atomic, immutable snapshot that consumers can read, pin, or time-travel
against. Today:

- Materialisers write in-place and `.partial` sentinels leak into committed
  state.
- Readers cannot pin a specific snapshot beyond a mtime string.
- Rollback requires ad-hoc file juggling.
- Cross-asset consistency (academic SKG + legal DAG + catalog) is not
  guaranteed during reads.

## Decision

Adopt lakehouse-style snapshot semantics for Data Forge and Fabric materialised
views:

1. A snapshot is an immutable record `{snapshot_id, parent_id, merkle_root,
   created_at, producer_version, schema_version, asset_refs[], manifest_sha256}`.
2. `merkle_root` is the root of a Merkle tree over all asset ArtifactRefs the
   snapshot declares (ADR-0123).
3. Snapshot commit is atomic: writers stage artifacts in a temp prefix, create
   a staged manifest, then rename-into-place the snapshot pointer
   (`snapshots/HEAD -> snapshots/<id>.json`). Failed writes leave no partial
   HEAD.
4. Retention is append-only by default. GC only removes snapshots explicitly
   marked `retention_class="ephemeral"` after `retention_days` elapse.
5. Readers pin a `snapshot_id` for the entire request. `read_api` always
   resolves a concrete snapshot before fanning out asset reads, preventing
   torn-read inconsistency.
6. Time-travel is a first-class feature: any committed `snapshot_id` can be
   queried.
7. Schema evolution is governed by ADR-0114: a snapshot declares the
   `schema_version` of each asset and compatibility rules apply.

## Consequences

- Cross-asset consistency becomes a typed contract instead of convention.
- Rollback equals writing a new pointer; no data is mutated.
- GC, audit, and replay all become snapshot-id keyed instead of path-keyed.
- Writers must be rewritten to stage-then-rename; in-place writes are banned.

## Related Decisions

- Extends: ADR-0010 (CAS signing), ADR-0015 (knowledge bundle freshness),
  ADR-0098 (CAS abstraction boundary).
- Depends on: ADR-0123 (ArtifactRef governance), ADR-0114 (schema registry).
- Related: ADR-0113 (asset-centric pipeline model).
