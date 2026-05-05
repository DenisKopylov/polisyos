# Cache Rebuild Storm

Related reference: [Observability Topology](../reference/operations/observability-topology.md),
[Platform Architecture Diagrams](../reference/operations/platform-architecture-diagrams.md),
[Fabric Data Plane](../reference/fabric/data-plane.md).

> Use this runbook when runtime cache/index services repeatedly rebuild, causing
> sustained CPU, I/O, or latency spikes.

Owner: `@runtime-owners`
Last tested: `2026-04-17` against current cache, streaming, and lineage regression coverage.
Evidence path: `docs/reference/operations/observability-topology.md`; `docs/archive/reports/core-runtime-closeout.md`; `tests/unit/fabric/data_plane/test_streaming_runtime.py`
Rollback path: reduce rebuild pressure or roll back the invalidation change, preserve one failing cache snapshot, and only then clear or rebuild state.

Freshness: 2026-04-17.

## Symptom

- elevated latency on run list, timeline, or lineage endpoints;
- elevated latency on Fabric connector fetches, retrieval previews, world
  queries, or materialization refreshes;

- repeated cache/index rebuild log entries within a short window;
- CPU or filesystem I/O saturation without matching request throughput growth;
- cache-hit rate drops while rebuild duration rises.

## Likely Causes

- invalidation loop after a manifest/index contract change;
- repeated cold-start behavior due to lifecycle churn or failed startup;
- unbounded tenant or artifact scan triggered by one pathological workload;
- cache corruption or incompatible on-disk state forcing repeated fallback.
- Fabric connector schema/profile changes repeatedly invalidating capability or
  schema-aware caches;

- streaming/CDC replay or cursor recovery replaying the same source window and
  rebuilding dependent materialization indexes.

## Timeline Capture Expectations

- affected endpoint family;
- request volume versus rebuild volume;
- cache hit rate, rebuild duration, item count, and eviction signals;
- last deploy/config change touching runtime index, timeline, or lineage logic.
- connector id, dataset id, profile id, schema id/version, and CAS artifact ids
  if the storm is Fabric-scoped;

- whether quarantine or CDC artifacts increased at the same time.

## First Triage Steps

1. Identify which cache is storming:

   - run index;
   - timeline index;
   - lineage graph;
   - telemetry aggregation cache;
   - Fabric connector cache;
   - Fabric capability/schema cache;
   - Fabric retrieval local index or promotion queue;
   - world materialization/projection state.
2. Check whether rebuilds are:

   - incremental but too frequent;
   - full scan fallbacks;
   - startup-only loops after repeated restarts;
   - schema/profile invalidation loops;
   - streaming replay loops from cursor/checkpoint state.
3. Correlate the first spike with deployment, runtime restart, or one large
   tenant workload.
4. Capture representative request IDs and resource IDs before clearing cache
   state.
5. For Fabric, run targeted cache and data-plane regressions before destructive
   cleanup:

```bash
uv run pytest tests/unit/fabric/connectors/test_cache_system.py tests/unit/fabric/connectors/test_schema_aware_cache.py -q
uv run pytest tests/unit/fabric/data_plane/test_cursor_store.py tests/unit/fabric/data_plane/test_streaming_runtime.py -q
uv run pytest tests/unit/fabric/test_lineage.py tests/unit/fabric/test_world_materialization.py -q
```

## Rollback / Mitigation

- prefer reducing rebuild concurrency or isolating the triggering workload over
  deleting all cache state immediately;

- if a recent deploy changed invalidation behavior, rollback that deploy before
  widening resource budgets;

- if one tenant or endpoint is the trigger, rate-limit or temporarily isolate
  that path rather than degrading the whole runtime;

- if cache state must be cleared, preserve one failing snapshot first so the
  rebuild trigger can be reproduced.

- for Fabric connector cache storms, prefer disabling prefetch or reducing
  source concurrency through the profile before deleting CAS-backed evidence;

- for schema-aware cache storms, verify the Fabric schema governance gate before
  accepting new snapshots.

## Escalation Owner

- primary: `@runtime-owners`
- supporting: `@platform-owners`
- Fabric-scoped storm: `@fabric-owners`

## Follow-up Checklist

- record whether the storm came from invalidation logic, startup churn, or one
  pathological workload;

- add a benchmark or regression test for the reproduced trigger;
- verify dashboards expose the exact cache that stormed.
- if Fabric schema/profile invalidation was involved, record the contract id,
  profile id, and schema-governance evidence artifact.

## Blameless Postmortem

### What Went Well

- whether incremental refresh contained the blast radius compared with a full
  rebuild scan;

- which metric made the storm obvious before clients escalated.

### What Went Poorly

- whether one cache family was indistinguishable from another in dashboards;
- whether operators had to infer storm behavior from raw logs only.

### Action Items

| Action item                                                        | Owner              | Due date   | Status |
| ------------------------------------------------------------------ | ------------------ | ---------- | ------ |
| Add missing cache metric or alert for the storm pattern            | `@platform-owners` | YYYY-MM-DD | open   |
| Close the invalidation or bounded-memory gap that caused the storm | affected owner     | YYYY-MM-DD | open   |
