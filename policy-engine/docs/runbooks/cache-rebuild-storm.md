# Cache Rebuild Storm

Related reference: [Observability Topology](../reference/operations/observability-topology.md),
[Platform Architecture Diagrams](../reference/operations/platform-architecture-diagrams.md).

> Use this runbook when runtime cache/index services repeatedly rebuild, causing
> sustained CPU, I/O, or latency spikes.

## Symptom

- elevated latency on run list, timeline, or lineage endpoints;
- repeated cache/index rebuild log entries within a short window;
- CPU or filesystem I/O saturation without matching request throughput growth;
- cache-hit rate drops while rebuild duration rises.

## Likely Causes

- invalidation loop after a manifest/index contract change;
- repeated cold-start behavior due to lifecycle churn or failed startup;
- unbounded tenant or artifact scan triggered by one pathological workload;
- cache corruption or incompatible on-disk state forcing repeated fallback.

## Timeline Capture Expectations

- affected endpoint family;
- request volume versus rebuild volume;
- cache hit rate, rebuild duration, item count, and eviction signals;
- last deploy/config change touching runtime index, timeline, or lineage logic.

## First Triage Steps

1. Identify which cache is storming:
   - run index;
   - timeline index;
   - lineage graph;
   - telemetry aggregation cache.
2. Check whether rebuilds are:
   - incremental but too frequent;
   - full scan fallbacks;
   - startup-only loops after repeated restarts.
3. Correlate the first spike with deployment, runtime restart, or one large
   tenant workload.
4. Capture representative request IDs and resource IDs before clearing cache
   state.

## Rollback / Mitigation

- prefer reducing rebuild concurrency or isolating the triggering workload over
  deleting all cache state immediately;
- if a recent deploy changed invalidation behavior, rollback that deploy before
  widening resource budgets;
- if one tenant or endpoint is the trigger, rate-limit or temporarily isolate
  that path rather than degrading the whole runtime;
- if cache state must be cleared, preserve one failing snapshot first so the
  rebuild trigger can be reproduced.

## Escalation Owner

- primary: `@runtime-owners`
- supporting: `@platform-owners`

## Follow-up Checklist

- record whether the storm came from invalidation logic, startup churn, or one
  pathological workload;
- add a benchmark or regression test for the reproduced trigger;
- verify dashboards expose the exact cache that stormed.

## Blameless Postmortem

### What Went Well

- whether incremental refresh contained the blast radius compared with a full
  rebuild scan;
- which metric made the storm obvious before clients escalated.

### What Went Poorly

- whether one cache family was indistinguishable from another in dashboards;
- whether operators had to infer storm behavior from raw logs only.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Add missing cache metric or alert for the storm pattern | `@platform-owners` | YYYY-MM-DD | open |
| Close the invalidation or bounded-memory gap that caused the storm | affected owner | YYYY-MM-DD | open |
