# Compute (`polisyos.scientist.compute`)

## Purpose

`polisyos.scientist.compute` encapsulates execution of Scientist jobs on top of
the Foundry runtime: legacy program execution, method-based dispatch, and the
C7 advanced-suite path used by causal and simulation-oriented workflow nodes.

The supported namespace is governed by `architecture/public_surface/contract.toml`.
`polisyos.scientist.compute` is a supported Scientist entrypoint. Its declared
`__all__` exports are part of that facade; the method-metric helpers are
bounded execution/readback tools, not source or publication authority.

## Where to Start

- Supported package exports: [`__init__.py`](__init__.py)
- Job contracts: [`job_spec.py`](job_spec.py)
- Runtime backend and dispatch path: [`runner.py`](runner.py)
- Advanced method suite: [`advanced_methods.py`](advanced_methods.py)
- Downstream method/runtime context: [`../../foundry/methods/README.md`](../../foundry/methods/README.md)

## Package Exports

- Job contracts in [`job_spec.py`](job_spec.py): `JobSpec`, `JobKey`, and `JobResult`
- Runtime execution in [`runner.py`](runner.py): `run_job(...)` and `MethodBackend`
- Advanced suite in [`advanced_methods.py`](advanced_methods.py): `C7AdvancedInputs`, `C7AdvancedSuiteResult`, `C7PersistedArtifact`, and `run_c7_advanced_suite(...)`

`MethodBackend` uses the one process-wide `polisyos.common.async_tools` executor.
Runtime composition can pin its candidate capacity with
`process_worker_capacity` and `process_worker_profile_revision`; absent settings
keep the legacy host-derived candidate fallback. This is a process-local
execution bound, not a deployment profile or a cross-process quota.

The legacy `run(...)` entrypoint retains its dispatch-only slot boundary. The
qualified `submit_method_execution_work(MethodExecutionWork)` route snapshots
the leased job identity and full selected source/intent refs before FIFO
admission. Its single physical worker resolves the current Runtime admission,
verifies the pinned method registration, reads the selected manifest under its
byte limit and the JSON payload under its byte/depth/element limits,
persists the content-admitted intent, fingerprints at dispatch, writes result
and evidence, and returns only full-profile refs plus bounded scalar metadata.
The worker frame owns decoded arrays through persistence and cleanup. Queue
backpressure and wait timeouts distinguish queued cancellation from a running
worker whose physical slot remains occupied.

The selected manifest and JSON payload limits apply to this input admission read.
They do not bound Core owner control-index or transaction-intent records and do
not impose a whole-request RSS ceiling. This bridge therefore claims a bounded
process worker queue and selected-read limits, not a total-memory bound.

When a Bayesian method result includes a content-bound native posterior-draw
payload, the post-evidence path persists candidate-only v1.1 summaries for both
supported point roles. `JobResult.posterior_summary_refs` exposes those typed
refs by role; the exact method-result and method-evidence views remain in CAS
lineage. This does not select a point role for a consumer or make the summaries
gate-eligible.

The graph workflow can also submit a `MethodMetricProjectionWork` after its
result, execution bundle, and compiled binding set have been persisted and its
producer buffers have been released. The worker resolves a server-configured
store, verifies that exact full-profile source tuple through the existing
method-metric admission helper, and returns its bounded typed outcome. A verified
admission token remains candidate evidence until Runtime binds it to the current
job/run/attempt fence; missing verification does not invalidate the raw graph
result. This route shares the same process executor and does not create a child
pool.

Legacy `run_job(...)` keeps `SimulationResults@0.1.0` as its payload contract and
adds full-profile manifest edges for the actual `ExecuteArtifacts` method-execution
bundle and metric-binding-set refs when the producer emitted them. The bounded
`read_job_result_method_execution_capture(...)` consumer resolves those roles from
`JobResult.simulation_results_ref` and exposes typed `available`, `partial`, or
`unavailable` provenance on `JobResult.method_execution_capture`. `available` means
the two exact role refs resolve; it does not establish Foundry graph admission,
method validity, or policy authority. The consumer requires an explicit manifest
byte limit; the legacy path uses a 256 KiB operational metadata bound, not a payload
quota or process-memory guarantee. Missing or malformed refs remain unavailable or
fail closed and are never inferred from artifact labels. Refs emitted with a
producer failure or partial status remain diagnostic; this availability field does
not establish successful execution.

## Depends On / Depended On By

- Depends on: Foundry executor and method registries, artifact storage, and a small set of IR validation helpers used during execution
- Depended on by: causal and simulation builtin nodes, advanced policy-design execution helpers, and related verification tests under [`../../../../tests/unit/scientist/compute`](../../../../tests/unit/scientist/compute)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.compute import JobSpec, MethodBackend, run_c7_advanced_suite; print(JobSpec.__name__, MethodBackend.__name__, callable(run_c7_advanced_suite))"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/compute -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/compute/test_runner_polyglot.py tests/unit/scientist/compute/test_advanced_methods_c7.py -q
```

## Reference Docs

- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Workflow catalog: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Cross-package navigation: [`../nodes/README.md`](../nodes/README.md), [`../workflows/README.md`](../workflows/README.md), [`../../foundry/methods/README.md`](../../foundry/methods/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-10-21 (qualified execution and legacy capture lineage routes)

For first-party Runtime composition, this facade also resolves the existing
method-metric selected-source reader, transfer budget, restricted call witness,
and selected-ref/bounded-read helpers. They remain owned by the Scientist
method-metric execution path. Their availability does not admit a source,
establish complete inputs, or grant publication or producer authority.
