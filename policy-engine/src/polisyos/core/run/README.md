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

`read_runtime_invocation_attempts(store, trace_path, run_id=...)` reads the same
validated owner chain without resuming a terminal run. It returns the existing
immutable `RunInvocationAttempt` views; an empty chain establishes nothing.
Callers making continuation decisions must separately hold the run lock and
any applicable execution fence. An observed outcome is not external authority.
`read_run_owner_snapshot` additionally checks the saved scope against the
supplied active scope and returns the existing typed owner snapshot. Its job,
registry and scope fields are facts to reconcile, not an execution grant.

`read_terminal_run` acquires the run lease and reconciles the selected terminal
manifest with its owner trace. It returns exact transition inputs without
inventing a missing transition or interpreting a consumer's output.

`RunContext.start_child` accepts only the live parent owner, its exact selected
unfinished invocation basis, and the same store. The child receives a separate
run/trace/lease and inherited owner provenance. A failed start after admission
raises `ChildRunStartUnknownError` with its locator; retry and child-dispatch policy
must reconcile that outcome and recheck the parent/fence before doing work.
## Workflow node lifecycle view

Sync and async workflow executors pass ordinary node callbacks a restricted,
`RunContext`-compatible view. It preserves the typed context identity and
read-only run metadata, artifact-store access, ordinary non-Core trace events,
and the existing allowlisted provenance update method. Ordinary views do not
expose the raw trace sink, input/output registration methods, suspension, or
finalization. When a callback is composed over a typed `WorkerRunView` through
the attempt facade, only `add_input` and `add_output` are additionally available;
they remain attempt-gated and stage receipt events on the worker trace. They do
not write the parent manifest. The parent continues to admit those events only
through the existing verified worker receipt path. Generic `emit` refuses every
Core-phase event and every `RUN_*` event. Cached-input preparation and cache-hit
validation receive the same restricted view as node execution.

The workflow finalizer may pass its profile-bound
`scientist.workflow_state_finalization` ref to `RunContext.finalize`. Core writes
that exact ref as the terminal `RUN_FINALIZED` input after its typed output event
and manifest registration. Currentness readers replay this ordered owner trace and
resolve the referenced CAS object. Existing terminal history without this input
remains readable, but cannot establish workflow-finalization currentness. This
is an in-process node API boundary, not an operating-system or Python sandbox.

