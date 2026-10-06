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

The ledger's current snapshot version is `1.1`. Version `1.0` has an explicit
migration; unknown versions, contracts and coordination modes are rejected.
Version `1.1` requires the settlement receipt index as part of the same atomic
snapshot as budget state. The index is retained without eviction until an owner
supplies a retirement rule.

`BudgetMiddleware.settle_spend_safe(...)` records an exact producer event under
the ledger lock and returns its immutable `BudgetLedgerSpendReceipt`. Retrying
the same event and payload charges once; reusing its identity with a different
payload refuses. `resolve_spend_safe(event_id)` reads the persisted receipt after
an uncertain acknowledgement. A missing receipt means unknown settlement;
filesystem failure raises `BudgetLedgerSettlementOutcomeUnknownError` rather
than reporting zero spend. This contract acknowledges local ledger accounting;
an external provider needs its own receipt or status/idempotency contract.

## Reference Docs

- Scientist workflow reference: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Builtin node reference: [`../../../../docs/reference/scientist/nodes.md`](../../../../docs/reference/scientist/nodes.md)
- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Cross-package navigation: [`../workflows/README.md`](../workflows/README.md), [`../nodes/README.md`](../nodes/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-04-17
