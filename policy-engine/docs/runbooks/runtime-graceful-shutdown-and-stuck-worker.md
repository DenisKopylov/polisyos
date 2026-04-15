# Runtime Graceful Shutdown or Stuck Background Worker

Related reference: [Platform Architecture Diagrams](../reference/operations/platform-architecture-diagrams.md),
[Operations Reference](../reference/operations/index.md).

> Use this runbook when runtime shutdown hangs, long-lived connections do not
> drain, or background workers remain alive after the process should be
> stopping.

## Symptom

- deploy or local stop hangs during shutdown;
- `/ready` stays degraded or never transitions cleanly through stopping/stopped;
- live WebSocket or SSE clients do not disconnect after shutdown begins;
- worker leases or background threads survive after the main service should have
  exited.

## Likely Causes

- blocked background worker or executor task;
- live collaboration hub or stream did not release connections cleanly;
- storage or control-plane close path is stuck in blocking I/O;
- shutdown order regression left a dependency open while its caller was waiting.

## Timeline Capture Expectations

- lifecycle state transitions observed in health;
- active worker count and any known stuck job IDs;
- whether the hang is reproducible only under load or also on idle shutdown;
- last deploy touching lifecycle, workers, streaming, or storage teardown.

## First Triage Steps

1. Capture `/ready` and `/api/v1/health` during shutdown.
2. Check active worker and live-stream state before forcing termination.
3. Record whether the process is blocked in:
   - worker close;
   - review/live connection drain;
   - store shutdown;
   - executor/task cleanup.
4. If possible, preserve logs and thread/task evidence before sending a hard
   kill.

## Rollback / Mitigation

- prefer one controlled restart after evidence capture over repeated kill loops;
- if one stuck job or connection is the trigger, isolate that workload before
  widening the shutdown timeout globally;
- use hard kill only after preserving enough evidence for a regression test;
- treat orphan worker cleanup as an audited operator action if it can affect
  durable state.

## Escalation Owner

- primary: `@runtime-owners`
- supporting: `@platform-owners`

## Follow-up Checklist

- add a regression test or shutdown drill for the reproduced hang;
- confirm no orphan thread, stream, or worker lease remains after recovery;
- update dashboards if lifecycle state failed to reveal the real blocker.

## Blameless Postmortem

### What Went Well

- whether lifecycle state exposed the failing shutdown phase quickly;
- whether graceful drain protected data integrity before force termination.

### What Went Poorly

- whether operators needed OS-level inspection because app-level signals were
  too weak;
- whether one dependency blocked shutdown of the whole runtime.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Add lifecycle or shutdown metric for the reproduced stuck phase | `@platform-owners` | YYYY-MM-DD | open |
| Fix the blocking cleanup path and add a regression test | affected owner | YYYY-MM-DD | open |
