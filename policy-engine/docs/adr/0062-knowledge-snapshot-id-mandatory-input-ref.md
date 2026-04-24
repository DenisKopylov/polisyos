# ADR-0062: knowledge_snapshot_id + mandatory InputRef for lineage sync

## Status

Proposed

## Date

2026-02-28

## Context

The academic and datasets batch pipelines produce knowledge snapshots that feed
into causal model construction. Without a stable snapshot identifier, downstream
consumers cannot determine whether they are operating on stale data or reproduce
a prior analysis. Additionally, the IR layer's lineage tracking requires every
input to carry an `InputRef` so that provenance chains are complete from raw
source through to decision packet.

## Decision

1. Every knowledge snapshot must carry a `knowledge_snapshot_id` (content-
   addressed hash of the snapshot payload) assigned at creation time.
2. All scientist and foundry nodes that consume knowledge data must accept an
   `InputRef` wrapping the snapshot id; nodes that omit this parameter fail
   schema validation.
3. The `InputRef` is propagated through the IR analytics layer so that causal
   reports, ensemble results, and governance verdicts all reference the
   originating snapshot.
4. Snapshot ids are stored in the SKG store's versioning table for historical
   lookup and diff.

## Consequences

### Positive

- Full provenance from raw academic/dataset source to final decision packet
  becomes automatically traceable via snapshot ids.

- Mandatory `InputRef` prevents accidental use of unversioned data, improving
  reproducibility of causal analyses.

- Snapshot diffing enables incremental pipeline reruns when only a subset of
  knowledge has changed.

### Negative

- Computing content-addressed hashes on large snapshots adds latency to the
  batch pipeline's finalisation step.

- Existing pipeline outputs produced before this ADR lack snapshot ids and
  require a backfill migration or explicit exemption.
