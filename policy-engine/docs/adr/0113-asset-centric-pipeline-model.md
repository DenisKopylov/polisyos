# ADR-0113: Asset-Centric Pipeline Model

## Status

Proposed

## Date

2026-04-18

## Context

The original Data Forge plan used stage contracts with input and output
artifacts. That is close to modern pipeline systems, but it still makes stages
primary. For lineage, partial recomputation, cross-domain reuse, and snapshot
identity, the primary object should be the asset.

## Decision

Data Forge pipelines are asset-centric:

1. `AssetKey` names a logical output.
2. `AssetSpec` declares schema, partitions, freshness, retention, owner, and
   dependencies.
3. Materializers are implementation functions that produce one or more assets.
4. Pipelines are asset graphs, not manually ordered stage lists.

## Consequences

- Lineage is derived from declared asset dependencies.
- Partial materialization and downstream recomputation are natural operations.
- Domain pipelines can depend on stable assets from other domains without
  knowing their stage implementations.
