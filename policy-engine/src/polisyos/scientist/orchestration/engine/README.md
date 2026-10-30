# Engine (`polisyos.scientist.orchestration.engine`)

## Purpose

`polisyos.scientist.orchestration.engine` defines the Scientist workflow
runtime: state model, DAG execution, checkpoint/resume, idempotency, retry and
fan-out semantics, runner backends, and trace metadata shared across the
orchestration stack.

## Where to Start

- Stable facade and export map: [`__init__.py`](__init__.py)
- State and workflow contracts: [`state.py`](state.py) and [`workflow_spec.py`](workflow_spec.py)
- Core execution path: [`executor.py`](executor.py) and [`async_executor.py`](async_executor.py)
- Bounded retry and owned-process cleanup: [`retry.py`](retry.py). Its result drains observe
  the current job-interrupt signal and use their own process handle and validated group for
  cleanup; they do not establish termination of arbitrary threads or external providers.
- Checkpointing and idempotency: [`checkpoint.py`](checkpoint.py) and [`idempotency.py`](idempotency.py)
- Remote/distributed runners: [`runner/`](runner/)

## Public Entrypoints

- State and spec contracts in [`state.py`](state.py) and [`workflow_spec.py`](workflow_spec.py): `ExperimentState`, `WorkflowSpec`, and `NodeInvocation`
- Node contracts in [`protocol.py`](protocol.py): `Node`, `NodeSpec`, `NodeOutcome`, `NodeError`, and `NodeStatus`
- Executors in [`executor.py`](executor.py) and [`async_executor.py`](async_executor.py): `WorkflowExecutor` and `AsyncWorkflowExecutor`
- Checkpoint helpers in [`checkpoint.py`](checkpoint.py): `resume_from_checkpoint(...)`, `acquire_run_lock(...)`, and workflow fingerprint utilities
- Idempotency/cache helpers in [`idempotency.py`](idempotency.py)
- Durable budget accounting in [`budget_ledger.py`](budget_ledger.py) and
  [`budget_middleware.py`](budget_middleware.py)
- Runner backends and configuration in [`runner/`](runner/): `WorkflowRunnerConfig`, `WorkflowRunnerBackend`, and `build_workflow_runner(...)`

## Depends On / Depended On By

- Depends on: core artifacts, observability, tenant/security helpers, and node contracts consumed by workflow execution
- Depended on by: [`../api.py`](../api.py), [`../workflows/README.md`](../workflows/README.md), [`../nodes/README.md`](../nodes/README.md), and the Scientist engine test surface in [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.orchestration.engine import ExperimentState, WorkflowExecutor, WorkflowSpec; print(ExperimentState.__name__, WorkflowExecutor.__name__, WorkflowSpec.__name__)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/orchestration/engine -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/orchestration/engine/test_condition.py tests/unit/scientist/orchestration/engine/test_retry.py tests/unit/scientist/orchestration/engine/test_state_merge.py -q
```

## Persisted Budget Admission

`FileBudgetLedger` requires an explicit `load_or_bootstrap(initial_state)` before
public mutation of a missing ledger. An explicit `BudgetState()` bootstrap
remains unlimited; an empty, malformed, or sparse existing file raises instead
of acquiring constructor defaults. Persisted non-nullable writer fields are
required before normalization, including nested state and mutation records.
Legally omitted nullable fields remain accepted.

`BudgetMiddleware` bootstraps with its configured state, reloads the ledger for
checks and mutations, and preserves exhaustion on reopen. Real-process tests
exercise these consumers, duplicate CAS publication, and byte-preserving
rejection. The independent wire oracle names mandatory fields separately from
the production schema traversal. Its explicit `E02_B_PROPERTY_REMOVAL=budget-wire`
control removes only required-field admission inside the child process; the
same consumer tests must then fail. These witnesses do not establish power-loss
or multi-host filesystem guarantees.

The ledger writer's current snapshot version is `1.5`; complete valid `1.0` through
`1.4` snapshots remain readable. Unknown versions, contracts and coordination modes
are rejected. Version `1.2` introduced producer settlement records; `1.3` added
server-issued run binding, `1.4` added attempt attribution, and `1.5` adds an optional
`BudgetLedgerCacheReuseAdmission`. Existing receipts keep their original accounting
meaning: migration cannot certify a previously unknown provider cost.

Cross-run reuse requires the exact live Core response proof at the new write. The
ledger freezes its authorizer scope/epoch and content digest, recomputes the internal
cache key and both event payloads, and requires matching tenant/cell/profile with the
exact original physical source. The receiver retains its own key/run binding and a
separate zero event; the source is never copied or reissued under the receiver run.
A matching string-shaped origin without that admission still refuses. Reopen and the
runtime budget consumer share `BudgetLedgerProducerRecord.validate_reuse_origin`.
This is local accounting admission, not institutional permission or provider billing
attestation. The runtime budget gate continues to require a known physical source cost.

`BudgetMiddleware.settle_spend_safe(...)` records an exact producer event under
the ledger lock and returns its immutable `BudgetLedgerSpendReceipt`. Retrying
the same event and payload charges once; reusing its identity with a different
payload refuses. `resolve_spend_safe(event_id)` reads the persisted receipt after
an uncertain acknowledgement. A missing receipt means unknown settlement;
filesystem failure raises `BudgetLedgerSettlementOutcomeUnknownError` rather
than reporting zero spend. This contract acknowledges local ledger accounting;
an external provider needs its own receipt or status/idempotency contract.

Before external provider work, `admit_provider_intent_safe(...)` atomically
reserves every configured budget key and persists a `provider_in_flight` record
under the stable ledger lock. This record describes an admitted request; it does
not assert provider completion or a charge. The configured adapter supplies the
actual nonempty run identity. A new process or newly constructed owner cannot
reuse a previous owner's unresolved attempt. The same live owner may admit
concurrent requests while it still owns their physical work.

Observed unknown cost, unknown ledger acknowledgement and unfinished protected
audit have separate completion phases. They refuse intersecting `pre_check` and
reservation admission; unrelated keys remain independent. A failed phase write
retains uncertainty in one shared live-owner object before releasing the lock,
while fresh owners discover the durable original intent. Retrying an older
record with the same ID cannot acknowledge a newer unresolved digest.

`with_completion_resolver(...)` binds a trusted owner at construction. Completing
an obligation requires its exact retained body/digest and actual per-key ledger
receipts; protected audit also needs the bound owner's verification. A boolean,
diagnostic reference or caller-selected epoch cannot establish completion. Abort
is limited to the original live owner and verified work that never entered the
provider. These are internal module contracts; they add no stable facade exports.
They preserve
local filesystem/process custody and do not supply external billing authority,
automatic crash reconciliation, power-loss or multi-host guarantees.

The runtime control store admits worker writes in one database transaction.
It checks the current job owner, attempt and live lease on the locked row before
publication and commit. Lease renewal in that transaction remains valid; a
stale bound worker cannot mutate through a sibling public method or raw SQL.
Administrative mutations use a separate unbound store. Terminal continuation
requires the immediately verified lifecycle transition, rather than a caller's
claim that the job is terminal. See the
[control-store contract](../../../runtime/http/services/README.md).

## Reference Docs

- Scientist workflow reference: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Builtin node reference: [`../../../../docs/reference/scientist/nodes.md`](../../../../docs/reference/scientist/nodes.md)
- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Cross-package navigation: [`../workflows/README.md`](../workflows/README.md), [`../nodes/README.md`](../nodes/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Retained SKG replay input

An explicit `ExperimentState.inputs["skg_source_snapshot"]` is resolved by one
shared workflow-intake helper before local sync/async execution, the serialized
node worker's async retry, or public dead-letter retry. The helper verifies the
profile-bound CAS descriptor and chunk closure, materializes the exact source
under the run, and records the selected ref once in the run manifest. The worker
rebinds that typed state ref at node intake but leaves run-level recording to the
workflow owner, avoiding duplicate events across node attempts. It reopens local
CAS bytes and does not serialize a DuckDB connection. A malformed selected ref fails
closed; only an absent selector keeps the legacy live-source path. This is local
replay, not issuer authenticity or production-currentness.

## Cache Recovery and Deadlines

`AsyncWorkflowExecutor` restores trace and checkpoint cache entries through one
shared-executor operation. Recovery builds a worker-private `NodeResultCache`;
the active execution accepts it only after the await returns within its absolute
workflow deadline. A cancelled or superseded recovery cannot publish a late index.
The same deadline covers trace iteration, entry verification, index admission,
and the residual workflow body. Read-budget admission precedes recovery reads;
compute-budget admission applies to a cache miss.
One original monotonic deadline covers admission, recovery, cache reads, artifact
I/O, checkpoint publication and finalization. A per-operation minimum timeout
cannot renew an expired workflow budget. The executor also retains its original
caller cancellation state across these boundaries; a hook that suppresses
cancellation cannot authorize a later successful workflow publication.
When no owner deadline is configured, shared-executor operations explicitly
select an unbounded wait and do not inherit the helper's default timeout.

`NodeResultCache` registers each provider-backed read, write, and recovery before
it queues behind the serialized provider lane. Its live-operation registry holds
only queued or active tokens and is cleaned in `finally`; `discard`, `clear`, and
index eviction revoke affected tokens before they can return or admit a current
reference. Writers still recheck the original deadline before index admission.
Immutable CAS objects already written by a refused call may remain, so this fence
covers current cache references and owner events, not strict no-late-persistence
across the artifact-store API.

Checkpoint publication carries an invocation-local `CheckpointPublicationBudget`
through artifact creation, atomic head publication and history GC. It captures
the original caller, cancellation baseline and ownership token. The additive
`BudgetedAsyncCheckpointHook` is `public_experimental`; fixed-signature legacy
hooks retain their existing calls and can delegate to the canonical CAS hook
through the publication context. Explicit adapter timeouts join the remaining
owner budget; implicit helper defaults cannot shorten or renew that budget.
Opaque native async stores retain their own policies.

Cancellation closes queued worker admission and preserves `CancelledError` with
the publication operation and `not_admitted` or `unknown` execution state.
The canonical writer checks the original budget before artifact admission and
again after temporary-file fsync, before replacing the head. Once replacement
enters, it finishes directory sync and required history so fresh readers can
resolve the committed generation. Expiry prevents acknowledgement, later GC and
workflow finalization; it does not roll back an entered filesystem operation.

The synchronous store must support access from the shared executor, matching the
existing async artifact-store adapter contract. Already-entered synchronous
backend I/O can finish after cancellation or expiry. Its private recovery state
stays isolated, and expiry prevents subsequent reads and admission. A checkpoint
or finalizer already entered may still publish: timeout reports an unknown
execution outcome instead of promising rollback. This boundary does not establish
preemption of arbitrary backend calls or concurrent reentrant execution on one
executor instance.

Successful cache persistence emits `NODE_CACHE_STORE` with the verified immutable
entry reference. A fresh store/context uses that trace reference to recover the
versioned mutation journal and apply only the producer's operations to current
state, including explicit same-value assignments, null and permitted deletions.
Cache verification and replay retain the full `ArtifactRef`, including its selected
manifest profile. Distinct views of the same blob receive independent custody
checks; a verified default view cannot authorize another producer's view.

The current journal algorithm is `1.2`. It records operations against the live
finite JSON graph, including held references after list insertion, removal or
reparenting. Shared targets carry an operation group with one encoded intent so
replay applies it once per current target while preserving current neighboring
values. Ordinary producer
mutations require their declared `state_writes`; nested branches can narrow that
grant. Local synchronous, asynchronous and remote worker entries enforce the same
scope. After settlement, the executor returns a detached editable completed state;
the original producer view retains its guard.

The same live-path grant covers ordinary mutable Pydantic `BaseModel` and
`RootModel` fields, including typed artifact references, nested model children
and shallow-copy aliases. Producer `model_copy(update=...)` checks the original
grant before making a copy; it cannot replace an undeclared state field. Copy,
deepcopy and completion preserve field membership and rebind tracked children
to their actual current parents. Frozen models retain their frozen assignment
and copy contracts. Neutral public consumers keep the existing editable model
behavior.

Producer admission walks the complete state graph before snapshots or
isolation can invoke copy callbacks. It admits exact builtin `dict`, `list` and
`tuple` containers with string dictionary keys, finite canonical scalar values,
and recursively checked ordinary `BaseModel` / `RootModel` fields, including
typed artifact refs. Native `Enum` / `StrEnum` fields are admitted only when
their scalar mixin and all copy, reduction, attribute and scalar-protocol hooks
resolve to standard Enum/builtin implementations; their internal value must be
an exact finite scalar and their member storage must have the standard shape.
These members remain the original enum singletons. The producer profile treats
them as read-only atomic candidates, but Python does not enforce that assumption:
direct mutation of a member's `_value_` or added attributes can bypass the state
journal and affect every alias. This residual is not covered by the finite-data
admission guarantee and must not carry a protected or published claim without a
separate ownership decision. Internal tracked containers use builtin iteration
during this walk. Unknown leaves, custom container/scalar subclasses, non-finite
numbers, and graphs beyond the canonical depth bound are refused before copy
or attachment. Depth accounting uses the same `max_depth` as canonical state
persistence, including the dumped state root and the actual nested mapping,
model and sequence costs; later tracked attachments account for their live
parent path as well. Sequential admission refusal raises the typed error;
asynchronous admission returns a failed node report with
`execution_state=not_admitted`, without producer or state/cache publication.
Internal installation into an admitted isolated model shell bypasses external
producer setters. It does not broaden an ordinary nested branch's grant.

Assignment validation supports field normalization only. Models configured with
`validate_assignment=True` and model-level validators are refused before copy
or invocation. Field validators run once against a detached complete model graph;
the offered value uses the same clone memo, retaining actual aliases. Every
sibling field, physical membership and alias is compared before accepting the
normalized field. Sibling edits, alias splits, unsupported results and validator
exceptions leave the live model, producer/base state and journal unchanged.
External Python effects or mutation of objects captured in validator closures
are outside this finite data-graph guarantee. ArtifactRef and BudgetState retain
their existing admission and mutation contracts.

A detached model copy checks the original grant but contributes no effect to
the live-state journal until it is attached. Completed state and artifact values
project tracked models to their original canonical model classes with a shared
memo. Remote workers use that neutral representation and the existing closed
wire model set; dynamic tracking classes are never transport identities. The
original provider-held view stays guarded after completion.

Outcome wire v2 always wraps the encoded outcome once. A mutation sidecar is
added only when the guarded state subtree contains a real journal owner; a
journal-shaped value in an error or another outcome field cannot select it.
The root state journal wins, then an exact stored legacy owner takes priority
over tracked owners. Repeated tracked references to one journal are collected
once; absent a higher-priority owner, distinct tracked journals refuse.
Descriptor-only owners are not read.
Sidecar operations retain the closed `StateMutation` model wrapper. Typed Core
and IR artifact-reference values use an untagged mapping with a canonical
`artifact_id`, `kind`, `media_type`, and any present manifest profile; an
absent profile stays omitted. Decoding reconstructs a journal from its
operations and does not preserve the producer process journal identity or
isolation metadata. Validated `ExperimentState` construction admits Core refs
and the supported IR `ArtifactRefModel` family in both `inputs` and
`artifacts_index`, projecting them to Core `ArtifactRef` values while retaining
the selected kind, media type, and profile. The branch mutation owner also
normalizes genuine IR refs written to `artifacts_index` before recording them.
Reads through branched `inputs` and `artifacts_index` mappings are registered
tracked views; `_owned_wire_model_origin` identifies the Core `ArtifactRef` and
nested Core `ArtifactID` behind each view. Tests should assert those owner
projections rather than concrete wrapper classes. Journal values follow the
write input: the producer test assigns the constructor's plain Core `inputs`
value, while an assignment from an already tracked branch read can retain its
registered model view; the `artifacts_index` owner normalizes a genuine IR ref
to Core before recording. Both forms in this journal sidecar emit the same
untagged canonical reference mapping; the outcome state keeps its typed Core
model wire projection.
Producer tests therefore start from validated typed state; synthetic
`StateMutation` codec tests are explicitly separate and do not imply that
`params` or `causal_method_params` admit references, since those fields remain
JSON-valued.

This profile admits declared ordinary model fields and their finite container
graph. Custom mutation/copy/construction hooks (including post-init), private or
extra runtime model state, new undeclared model attributes, unsupported runtime
objects, and cyclic attachments are refused before snapshots can copy them.
Model-field deletion is refused because the replay consumer does not support
it. This does not claim custody of explicit base-class mutators, reflection,
direct enum-member mutation, or external effects from assignment validators,
and it does not reconstruct
arbitrary model classes from cache JSON.

Legacy `1.0` and `1.1` cache journals admit only direct primitive model or mapping
set/delete operations. Nested or container intents become cache misses, allowing
the producer to execute against current state. This compatibility boundary does
not promise persisted Python object identity or a sandbox for arbitrary Python
objects and explicit base-class mutators.

Run the real storage consumer checks from the repository root:

```bash
uv run pytest tests/unit/scientist/orchestration/engine/test_async_cache_recovery.py tests/unit/scientist/orchestration/engine/test_cache_reference_custody.py
```

## Resume Required Artifact Admission

Before executing a remaining node, resume checks its existing declared reads
that overlap writes of a completed producer. A present typed `ArtifactRef` in
that state path must verify and permit reading through the current store using
its complete selected manifest identity. Missing or corrupt external bytes do
not become available merely because their reference is in a valid checkpoint.
The default strategy refuses before dependent node effects. Explicit
`allow_replay` restores the original execution plan so a producer can repair its
required result; its existing cache-hit validator still decides whether a cached
result is admissible. Replaying cannot guarantee repair of an arbitrary backend.

This extends the established completed-writer/remaining-reader guard. It does
not infer artifacts from arbitrary JSON objects or make every optional read a
required input. Reads without a completed writer retain their current behavior.
Availability is checked at resume admission; it is not a filesystem reservation
or a guarantee against a later external deletion. Operational source replay below
is separate from source issuer authenticity or scientific output dependence.

```bash
uv run pytest tests/unit/scientist/orchestration/engine/test_resume_artifact_requirements.py tests/unit/remediation/test_res_01.py
```

## Retained SKG Operational Source Replay

The existing untimed sequential `CacheInputPreparer` owner prepares and closes
one real DuckDB read transaction. A successful bound SELECT/WITH can retain its
exact stable database bytes as verified FileSystemCAS chunks and a
`scientist.skg_source_snapshot` descriptor before cache publication. The cache
origin records the full selected descriptor ref, its schema and the original
source reference. Cache hits verify that descriptor and retain it without
copying the source again. The selector epoch is
`prepared-read-retained-source-v5`; old v4 origins cannot claim retained replay.

Default workflow execution continues to select the current live database.
Recording a retained descriptor as a run input and outcome artifact does not
populate the replay inlet or freeze future live lookup. Default capture failure
or an unsupported generic artifact store leaves the live result uncached and
does not publish retained-source proof.

Replay is an explicit `ExperimentState.inputs["skg_source_snapshot"]` full
`ArtifactRef`. Before initial-state persistence, node branching and cache-key
construction, the workflow verifies the descriptor and all selected CAS chunks,
then binds the effective database under
`RunContext.trace_path.parent / "skg-snapshots"`. The directory is a local
materialization of the selected CAS source, not authority supplied by a caller's
previous path. Missing run path, non-FileSystemCAS store, missing or corrupt
descriptor/chunks and corrupt materialization refuse this explicit request;
they never delegate to a current live database. Untimed sequential prepared
nodes use the canonical reader over this verified source and retain the same
selected full ref rather than reconciling its old logical URI against the new
physical path.

The existing timed custom-invocation prepared/cache bypass remains. Timed and
asynchronous explicit replay can read the verified materialized database path;
this does not introduce an asynchronous prepared-reader ABI or retained
cache-proof profile. Asynchronous materialization uses the original invocation
deadline and cancellation owner: queued work is not admitted after loss of that
owner, while already-entered filesystem work may finish with an unknown result.
No physical rollback or uncooperative I/O preemption is promised.

This is a bounded DuckDB operational replay contract. Source issuer
authenticity, K_ref authority, external search-index reproduction, arbitrary
backend support, hash-to-MVCC correspondence beyond the existing filesystem/WAL
checks and causal dependence of an output on queried rows remain unestablished.
The saved source can reconstruct a lost local materialization from CAS; it is
not a new source resolver authority.

```bash
uv run pytest tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py tests/integration/scientist/orchestration/engine/test_skg_prepared_read_cache.py
```

## Bounded Node Timeout Workers

On macOS, a timed synchronous node uses a spawned process only when its node is
the canonical `ResolveParametersNode` and its execution context can be encoded
by the strict filesystem-CAS, run-owner-snapshot, AccessScope, and tenant wire
(profile v2). The producer and child both verify the selected owner snapshot in
CAS and recompute its persisted scope digest; the child installs the admitted
scope for node execution. Scope absence is encoded explicitly. The worker also
receives an absolute monotonic deadline plus the parent's revocable attempt
authority. The parent owns timeout reporting and process-group cleanup. A delayed
canonical-node control proves that CAS output can be written while authority is
live and that the same write is refused after parent revocation. This covers the
named context-owned write boundary; it is not a sandbox for arbitrary Python
effects or raw filesystem access.

Other custom nodes and contexts are refused before node entry with
`node.timeout_worker_unsupported`; workflow reports preserve that admission
code without attaching an elapsed-time threshold. macOS does not fall back to a
thread that cannot be physically stopped. This narrows the former arbitrary-node
timed behavior. Callers that accept unbounded execution may omit the timeout. A
bounded custom node needs its own admitted canonical task and strict context
profile before it can join the spawn allowlist. Linux continues to use the
existing owned fork supervisor. Platforms without one of the supported process
methods refuse bounded execution rather than claiming a thread is a killable
worker. These profiles do not establish a generic timeout capability for all
nodes or stores.

## Canonical node-cache mutation comparison

The synchronous and asynchronous executors share one cache reader. Before a
cache hit is replayed, the current live journal and the persisted entry are
compared as the complete ordered StateMutation sequence using the journal's
canonical JSON codec. This makes typed ArtifactRef values compare with their
CAS-loaded mapping form while retaining path, operation, operation group,
field-presence, boolean/integer, and typed-float distinctions. Tuples and lists
share JSON array semantics at this persistence boundary.

Current journal version 1.2 requires every mutation field to be present in both
the in-memory and persisted operation. Legacy 1.0 and 1.1 keep their existing
narrow primitive replay rule. Unsupported or malformed operations remain cache
misses; proof, run/key, source, scope, and currentness checks are unchanged.
Journaled state models compare by the locked Pydantic 2.12.5 value relation
while recursively comparing the admitted model and container graph. Generic
specializations use their generic origin; non-generic models retain their
concrete class; and `RootModel` additionally requires the same root annotation.
Tracked wrapper classes are constructed through the source model's Pydantic
metaclass with a separate copy of its complete generic metadata mapping. For a
bare generic with `origin=None` and nonempty parameters, the wrapper copy sets
its effective origin to the original class while preserving `args` and
`parameters`; the original metadata is unchanged. This matches Pydantic's native
`origin or class` rule and keeps equality symmetric when either operand is a
tracked sibling. `RootModel` retains its separate root-annotation comparison.
The metadata copy does not relax hook-identity admission: custom generic hooks
remain refused.
The comparator includes private/extra slots and declared field values, ignores
`model_fields_set` and non-field `__dict__` entries, and treats the tracking
containers by their built-in contents. Nested model values recurse through the
same rule; finite scalar leaves use ordinary Python equality, including
`True == 1` in an `Any` value. Both internal `model_construct` boundaries preserve
the admitted runtime-slot shape exactly: `None` remains `None`, and an exact
empty built-in `dict` remains an empty `dict`. The comparator does not normalize
those states. Copy-on-write and wrapper installation still preserve
`model_fields_set` as provenance, and a producer field assignment still marks
the field present. That presence is observable state, but it is not part of
model value equality. Tracked model assignments are recorded in both scoped and
unscoped journals: scope enforcement controls authorization, while capture stays
active whenever a tracked view exists. Unknown attributes and model-field
deletion are rejected because the journal represents declared-field assignments,
not private or extra state changes.

The cache persists typed operation records and canonicalizes them for replay
validation; it does not use wrapper equality to validate an entry. The
ArtifactRef `manifest_profile_sha256` field excludes None from its wire form, so
the explicit-None `model_fields_set` bit is not restored after CAS readback. The
cache test binds that normalization, checks the restored value remains equal by
Pydantic value semantics, and verifies a repeated entry read remains valid; it
does not claim field-set provenance survives that existing wire projection. No
cache schema or replay-version change is proposed. Non-empty or non-canonical
private/extra runtime state remains refused at admission. The candidate continues
the bounded input-compatibility change introduced by R9: original models that
define custom `__eq__` or `__ne__` hooks are refused by the ordinary-hook
admission check. A generic Pydantic specialization is admitted only when its
effective `__init_subclass__` hook is the exact `typing.Generic` implementation;
generic names, origins, and parameter metadata do not authorize a custom hook.
Custom generic hooks remain refused. Callers that relied on journaling models
with custom equality or subclass hooks must migrate to models with ordinary
Pydantic behavior or keep those values outside journaled state branches. The
existing typed `TypeError` admission refusal applies; no cache schema or
journal-version migration is involved. These internal behaviors do not establish
source authenticity or scientific output validity.

## Last Updated

- Last updated: 2026-10-13

## Cross-package Budget Runtime Facade

Runtime consumers import the existing budget contracts through the `polisyos.scientist.orchestration.engine` facade: `BudgetLimit`, `BudgetMiddleware`, `FileBudgetLedger`, `BudgetLedgerProducerRecord`, and `BudgetLedgerProducerRunBinding`. These are same-object exports from the budget owners; run binding and persisted producer records still determine attribution and settlement semantics.

## Runtime candidate source basis

The synchronous and asynchronous executors persist the selected-profile
workflow and input state before each uncached attempt, then append its
engine-observed outcome. The shared policy-candidate resolver and Phase 3
resolver use the matching owner-linked attempt: they fresh-read the owner chain
and CAS, check the workflow-node binding, compare every source-selecting field,
and recompute the canonical source branch. Ordinary
`RUNTIME_PARAMETER_SELECTED` trace events cannot replace that basis. Phase 3
keeps its typed refusal behavior when a selected value is malformed or unreadable.

The existing cache-key declarations for output-bundle construction, policy
translation, translator compliance, and the blueprint runtime now include the
selector fields those resolvers read: inline schema, artifact ref, candidate ID,
and Trinity inputs. A change from candidate A to B therefore misses the old
cache entry; repeating B can still reuse its cached result. A cache hit remains
cache reuse and creates no new invocation basis. Cancelled and timed-out attempts
retain their persisted input but have an `unknown` outcome, so they do not satisfy
a successful-completion check.

On the public bundle-builder path, the accepted output bundle and its twelve
related builder artifacts each retain one typed `InputRef(role="candidate")`
with the complete selected candidate ref, including the manifest profile. This
is producer-declared artifact lineage; it does not prove the heterogeneous
outputs semantically used that candidate. The output-subject join remains
`not_established`. Histories without an owner-linked attempt also remain
`not_established`; no historical data is rewritten.

These bindings show the candidate source branch observed by the engine. They do
not prove who authored state before dispatch, candidate trustworthiness or
admissibility, authority, currentness, publication, or external custody. A node
running arbitrary in-process Python can call private methods, so this mechanism
is not a sandbox or external custody boundary.

Public dead-letter replay now requires the exact selected-profile `RunInvocationStarted` basis
from the existing run-owner chain. It resolves the associated `WorkflowSpec`, checks the selected
alias/component, binds its original invocation params to the replay node, and refuses schema 1.0 or
unbound records. It never substitutes mutable state params. `run_node_in_worker(...)` remains
`not_established` for source origin when no engine-owned workflow invocation binding is available;
trace labels and worker dispatch identifiers alone do not supply that basis.
## Currentness of engine-produced reports

Governance reports and verified policy reports are current decision evidence only when the exact successful builtin producer attempt emitted the selected report and its complete declared source projection still matches the consumer state. The engine captures a selected in-process implementation identity before the attempt; comparison checks the exact callable, code object, bound node state, component spec, and source bytes against that captured owner. This is a same-process implementation check, not a deployment, transitive-plugin, or release attestation. Dynamically selected governance validation-pass implementations remain outside that identity claim.

Configured child-composition members additionally retain their actual bootstrap-selected registration and bound parameter/state snapshot. The private configured-identity mechanism reconciles only the exact bind-result object it retained, together with instance attribute dispatch, class descriptors and code; a different object with equal fields is not that bind result. It does not construct a default node or expand the fixed protected-producer registry. This identity is only an input to the independently appointed admission/release owner. It does not by itself grant child computation, publication, process isolation, or transitive deployment authenticity.

The synchronous and asynchronous workflow finalizers persist a `scientist.workflow_state_finalization` artifact. It binds the selected workflow-spec input, the exact pre-finalization and final state artifacts, and every terminal report or optional research-DAG state reference written by that finalizer. The reader checks the run-owned input/output links, schema and workflow identity, ref bytes, final-state equality, and recomputed state delta. It then compares the report source projection with the persisted pre-finalization state. This handles complete map reads without silently ignoring a named key: a later node or caller mutation remains in the source projection and makes the report stale. Older runs without this receipt are not promoted to current by inference.

The source basis is intentionally complete for the actual consumer boundary. RunGovernance exposes the full `inputs`, `artifacts_index`, `reports_index`, and `params` maps to its selected validation passes and also reads `run_id`, `execution_profile`, and the selected policy projection/report refs. The verified-policy builder uses the same complete maps plus its request, option-set, source-verification, and selected-report refs. A cache hit is reusable only if the report remains selected and its exact successful producer and source basis still match. A changed or removed input clears the cached current ref before rebuilding or skipping. `current` means source-current for this selected in-process producer; it does not establish law, issuer authority, scientific adequacy, permission, or external custody.


## Current stopping observations and producer budgets

`ConvergenceDetector.check_candidate_observation(...)` consumes one content-bound
current candidate assessment: actual response bytes, caller request, semantic problem,
pass number, producer event, model and version must agree. A skipped/failed pass,
response reuse, replayed event, unknown version or incompatible measurement
cannot renew an old comparison window. Unknown embedding identity may retain a
raw cosine diagnostic; it does not establish comparable current measurements.

`ConvergenceState.should_stop` and `stop_kind` separate a resource ceiling from
heuristic candidate stability. `scientific_converged` is always false. The old
`converged` flag retains its terminal meaning for scalar compatibility; consumers
that distinguish convergence from exhaustion must use the new fields. An
explicit resource ceiling may occur before a comparison window exists.

`producer_budget.ProducerBudgetObserver` consolidates the existing Control NL
reconciler over `BudgetMiddleware.snapshot_safe()`. Every admission reopens the
canonical ledger snapshot, selects the exact run binding/key, validates committed
amounts and reuse origins, and reconciles the same runtime `BudgetState`. Unknown
or pending positive-cap spend never becomes zero. A configured zero cap refuses
independently without inventing a spend result. Cap or settlement-owner drift is
a typed refusal; repeated reads of an unchanged selected basis retain its digest.

The observation's unit is USD. Its runtime allocation includes existing stage
estimates and is explicitly distinct from measured N5 cost. Native N5 records
actual physical invocation units separately, reads this owner before every
physical seed, and reuses role projections without additional work events. These
work observations establish neither a USD price nor scientific producer
authenticity. A serialized observation is an audit view, never a reusable permit.

The observation also retains the existing Core producer request digest as
`producer_request_ref`. The caller-input hash names another quantity and is not
a claim to recompute Core's tenant/sanitizer/caching contract. The canonical Core
producer remains the owner of that request/event binding.

N6 binds the exact expected observer and invocation budget-state identity at one
canonical N5 intake, covering both default and supplied canonical ports. A
foreign or absent observer refuses before work; object type alone is not the
run-owner binding. The same intake is rechecked at the run/generic-consumer path.
Custom contract-testing ports retain their explicit non-canonical scope.
