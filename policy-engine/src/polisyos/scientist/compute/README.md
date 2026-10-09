# Compute (`polisyos.scientist.compute`)

## Purpose

`polisyos.scientist.compute` encapsulates execution of Scientist jobs on top of
the Foundry runtime: legacy program execution, method-based dispatch, and the
C7 advanced-suite path used by causal and simulation-oriented workflow nodes.

## Where to Start

- Stable package facade: [`__init__.py`](__init__.py)
- Job contracts: [`job_spec.py`](job_spec.py)
- Runtime backend and dispatch path: [`runner.py`](runner.py)
- Advanced method suite: [`advanced_methods.py`](advanced_methods.py)
- Downstream method/runtime context: [`../../foundry/methods/README.md`](../../foundry/methods/README.md)

## Public Entrypoints

- Job contracts in [`job_spec.py`](job_spec.py): `JobSpec`, `JobKey`, and `JobResult`
- Runtime execution in [`runner.py`](runner.py): `run_job(...)` and `MethodBackend`
- Advanced suite in [`advanced_methods.py`](advanced_methods.py): `C7AdvancedInputs`, `C7AdvancedSuiteResult`, `C7PersistedArtifact`, and `run_c7_advanced_suite(...)`

`MethodBackend` submits the actual Foundry dispatcher call through the one
process-wide `polisyos.common.async_tools` executor. Runtime composition can pin
its candidate capacity with `process_worker_capacity` and
`process_worker_profile_revision`; absent settings keep the legacy host-derived
candidate fallback. This is a process-local execution bound, not a deployment
profile or a cross-process quota. Method result and evidence writes remain after
the dispatch slot is released.

When a Bayesian method result includes a content-bound native posterior-draw
payload, the post-evidence path persists candidate-only v1.1 summaries for both
supported point roles. `JobResult.posterior_summary_refs` exposes those typed
refs by role; the exact method-result and method-evidence views remain in CAS
lineage. This does not select a point role for a consumer or make the summaries
gate-eligible.

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

- Last updated: 2026-10-09
