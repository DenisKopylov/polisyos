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

`ChildRuntimeCapability` is a separate child-purpose capability; a worker
receipt does not issue it. Its current factory reconciles an existing Core
child session with the live parent and fixed, source-verified Runtime control
owner. Core records one-use session, scope, and release decisions that the
registered control worker can consume without receiving the parent's execution
grant. This factory does not establish the origin of the earlier custody
appointment or appoint a production child workflow.
For the local SQLite route, Core prepares and syncs the exact release-head bytes
before the final decision. The real job-row transaction and parent liveness fence
then cover the final lease check and atomic replacement; directory durability is
acknowledged afterwards. The lease deadline is checked immediately before the
replacement call, but a delayed operating-system call can cross that deadline.
Production appointment remains blocked.

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
identities, including selected profiles, to match the current manifest. Typed
reference subclasses may decode as the base reference without changing identity.
It is useful when a downstream consumer must
prove a selected output was added through the owner writer; it does not attest an
external producer, policy authority, or deployment identity.
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


## Private child computation

A trusted engine bootstrap may create one parent custody session and separate
child scopes under an existing root run. Candidate handoffs stay private until a
configured typed resolver identifies the final parent projection and selected
closure and the local release head commits. Job-bound sessions require a durable reserved job-owner intent before computation
and an exact release authorization before publication. Fresh readers refuse
without the appointed job owner. Post-commit settlement
errors retain the release receipt. This is a trusted built-in local profile, not
Python or OS isolation, and it does not confer scientific or policy authority.

The first job-bound owner profile bounds each normalized owner snapshot to 256 KiB
and each individual collection to 4096 items. Oversized enrollment, staged
writes or parent effects refuse and revoke the private session; they do not
claim rollback of already-created private bytes. The bound is an availability
restriction, not a measured latency guarantee or a scientific policy limit.

Jobless child computation is unsupported and refuses before child work: its
owning durable authorization decision is not established.

Private invocation-history reads may reuse the canonical reader's detached,
complete parse after rereading every consumed CAS premise and the actual trace.
Active-parent admission applies the ordinary live run/scope/store predicate to
that verified snapshot, without parsing the same owner again. Read-only history
remains available for completed children. A changed owner or invocation tail
refreshes the parse; a changed historical blob refuses. The selected head, a
timestamp, or cache presence alone establishes neither currentness nor admission.

The trusted executor prepares a private child outside the job/resource decision,
then admits its one-use handle under the actual short job and grant owners. Only
a confirmed owner decision may complete the handle and hand the scope to a node.
A failed decision revokes and suspends its private run outside those locks. The
local handle does not establish DB currentness or ongoing resource availability.

For a Runtime-guarded session, the served and private-stage registrations are
rechecked at Core owner decisions, and the appointed service's bindings are
write-once. Changing and restoring a registered proxy,
guard dependency, guard lifecycle, or registry entry invalidates that session;
the short release-head transition is ordered against those changes. A lost
commit acknowledgement remains an unknown settlement, even if a fresh reader
can resolve the committed selected artifact. These checks do not establish the
origin of the Runtime appointment or a production child invocation. They do
not prevent hostile direct Python mutation of internal objects or registries.
