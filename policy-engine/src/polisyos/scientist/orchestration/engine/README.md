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

Both executors publish `NODE_CACHE_STORE` after a successful cache-entry write.
A fresh executor in the same run restores exact entry refs from this trace or
checkpoint refs, then verifies the stored replay operations before applying
them to current state. An underlying CAS write that finishes after cancellation
is not admitted to the trace as a successful cached attempt.

Async cold recovery reads both trace and checkpoint entry refs through the same
bounded shared worker as ordinary cache I/O, with the caller's context and one
absolute workflow deadline. Recovery checks the read budget first and admits
its private cache only after a successful, unexpired await. Cancellation or a
bounded read timeout can leave a physical read running, but that worker cannot
publish into the executor's current cache. Without a configured workflow
deadline the shared helper's default 30-second read wait remains a cache bypass
limit, not a workflow deadline. Workflow execution receives the time remaining
after startup. Synchronous stores must support the existing shared-worker
ownership model; this path does not add support for thread-affine connections.

## Depends On / Depended On By

- Depends on: core artifacts, observability, tenant/security helpers, and node contracts consumed by workflow execution
- Depended on by: [`../api.py`](../api.py), [`../workflows/README.md`](../workflows/README.md), [`../nodes/README.md`](../nodes/README.md), and the Scientist engine test surface in [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Retry timeout lifecycle

[`retry.py`](retry.py) runs timed synchronous nodes in a fork worker when that
launch method is available. On Linux, a disposable supervisor becomes a
process-local child subreaper, owns the compute child, and kills and reaps its
descendants before the caller accepts a result or finishes cancellation. The
caller's subreaper flag is unchanged. Cleanup follows the kernel parent
relationship, including descendants that started another process group.

Computation and result delivery have separate bounds. The caller drains the
result queue while the worker sends it, so a result larger than the pipe buffer
does not wait for a join that depends on delivery. Startup, serialization and
supervisor cleanup failures cannot publish a successful outcome.

Worker errors carry their original retry category and explicit error code
alongside the diagnostic message. The parent uses those fields rather than
interpreting message text or reconstructing arbitrary exception classes.
Permanent and validation failures therefore retain their retry count across
the fork boundary, and custom codes still obey `retry_on`. A provider's own
`TimeoutError` is a transient node error; expiration of the wrapper's wait
raises `NodeTimeoutError`. Thread and async wrappers decide completion before
reading the result so these two cases remain distinct.

The timed async-to-thread fallback retains the underlying concurrent future.
On timeout or caller cancellation it cancels that future before returning,
preventing an unstarted job from executing when the pool later has capacity.
Cancellation of an asyncio wrapper alone forwards in a deferred callback and
cannot establish this boundary. Already running threads remain cooperative;
genuine async tasks retain the revocable-authority behavior described above.

This contract is process ownership rather than a sandbox for hostile node
code. It does not undo completed filesystem or remote effects. Linux requires
`prctl`, fork and readable `/proc` process metadata. Other fork platforms retain
the existing process-group cleanup path; their descendant reaping needs a
platform-specific acceptance check. Python warns when fork starts in a
multithreaded caller. When fork is unavailable, the shared-thread fallback and
genuine async nodes use revocable attempt authority and cooperative
cancellation, which cannot forcibly terminate arbitrary external work.

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

- Last updated: 2026-10-05
