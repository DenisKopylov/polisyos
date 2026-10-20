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

`RunContext.read_runtime_owner_output_refs()` replays the persisted Core run-start
record and owner-snapshot chain, then requires the full ordered input/output event
refs to match the current manifest. It is useful when a downstream consumer must
prove a selected output was added through the owner writer; it does not attest an
external producer, policy authority, or deployment identity.
## Workflow node lifecycle view

Sync and async workflow executors pass ordinary node callbacks a restricted,
`RunContext`-compatible view. It preserves the typed context identity and
read-only run metadata, artifact-store access, ordinary non-Core trace events,
and the existing allowlisted provenance update method. It does not expose the
raw trace sink, input/output registration methods, suspension, or finalization.
Generic `emit` refuses every Core-phase event and every `RUN_*` event; the
engine continues to use the typed Core writers and the existing verified worker
receipt path. Cached-input preparation and cache-hit validation receive the same
restricted view as node execution.

The workflow finalizer may pass its profile-bound
`scientist.workflow_state_finalization` ref to `RunContext.finalize`. Core writes
that exact ref as the terminal `RUN_FINALIZED` input after its typed output event
and manifest registration. Currentness readers replay this ordered owner trace and
resolve the referenced CAS object. Existing terminal history without this input
remains readable, but cannot establish workflow-finalization currentness. This
is an in-process node API boundary, not an operating-system or Python sandbox.

