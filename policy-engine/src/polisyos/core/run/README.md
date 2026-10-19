# Core run worker lifecycle boundary

`polisyos.core.run.worker_lifecycle` is the narrow supported Core leaf for
staging child-worker events and admitting a parent-bound receipt. The
`polisyos.core.run` package and `RunContext` remain internal implementation
surfaces.

`WorkerLifecycleCapability.for_parent` binds only the exact active Core run
whose process owns the current lease. It issues a typed dispatch binding from
the current run and owner snapshot. A worker reconstructs its selected owner
inputs, stages typed trace records in memory, and receives a `WorkerRunView`
that refuses finalization and suspension. Ordinary attribute access cannot
reach the raw target, active lease, owner snapshot slot, or private durable-trace
slot. The existing public `trace_path` projection remains readable for execution
and cache consumers, and the view detaches mutable manifest reads. Returning a
path does not sandbox filesystem access through that reference.

The parent admits a receipt only through the existing Core
`RunContext.merge_worker_events` writer. That path rechecks the active owner,
dispatch identity, current owner snapshot, selected-profile artifact bytes,
and replay state before appending markers and applying accepted run operations.
The capability adds no receipt schema, law, calibration, or producer authority.

The boundary covers the selected local/fork/remote worker routes and their
existing serialized receipt. It is not an OS process sandbox: Python
introspection, filesystem permissions, and a worker's access to the CAS remain
separate concerns. No capability is established for other run operations,
external worker transports, or callers that bypass the Core receipt writer.
