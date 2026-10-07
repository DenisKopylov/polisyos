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

The ledger's current snapshot version is `1.2`. Complete valid `1.0` and `1.1`
snapshots migrate explicitly; unknown versions, contracts and coordination modes
are rejected. Version `1.2` requires both settlement receipts and the completion
obligation index in the same atomic snapshot as budget state. Existing receipts
keep their original accounting meaning: migration cannot certify a previously
unknown provider cost. Both indexes remain retained until an owner supplies a
retirement rule.

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
or a guarantee against a later external deletion. Source snapshot ownership and
the held B61 read-handle contract are unchanged.

```bash
uv run pytest tests/unit/scientist/orchestration/engine/test_resume_artifact_requirements.py tests/unit/remediation/test_res_01.py
```

## Last Updated

- Last updated: 2026-10-06
