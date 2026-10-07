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

## Reference Docs

- Scientist workflow reference: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Builtin node reference: [`../../../../docs/reference/scientist/nodes.md`](../../../../docs/reference/scientist/nodes.md)
- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Cross-package navigation: [`../workflows/README.md`](../workflows/README.md), [`../nodes/README.md`](../nodes/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-04-17

## Canonical B1.2 completion profile

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
