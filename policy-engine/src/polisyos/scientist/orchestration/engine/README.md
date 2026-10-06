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

## Cache Recovery and Deadlines

`AsyncWorkflowExecutor` restores trace and checkpoint cache entries through one
shared-executor operation. Recovery builds a worker-private `NodeResultCache`;
the active execution accepts it only after the await returns within its absolute
workflow deadline. A cancelled or superseded recovery cannot publish a late index.
The same deadline covers trace iteration, entry verification, index admission,
and the residual workflow body. Read-budget admission precedes recovery reads;
compute-budget admission applies to a cache miss.
When no owner deadline is configured, recovery, cache reads and cache publication
explicitly select the shared executor's unbounded wait. They do not inherit its
default timeout. Checkpoint publication and already-entered backend operations
retain their separate durability and cancellation contracts.

The synchronous store must support access from the shared executor, matching the
existing async artifact-store adapter contract. Already-entered synchronous
backend I/O can finish after cancellation or expiry. Its private recovery state
stays isolated, and expiry prevents subsequent cache reads and index admission.
This boundary does not establish preemption of arbitrary backend calls or concurrent
reentrant execution on one executor instance.

Successful cache persistence emits `NODE_CACHE_STORE` with the verified immutable
entry reference. A fresh store/context uses that trace reference to recover the
versioned mutation journal and apply only the producer's operations to current
state, including explicit same-value assignments, null and permitted deletions.
Cache verification and replay retain the full `ArtifactRef`, including its selected
manifest profile. Distinct views of the same blob receive independent custody
checks; a verified default view cannot authorize another producer's view.

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
