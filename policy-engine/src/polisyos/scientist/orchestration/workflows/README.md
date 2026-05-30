# Workflows (`polisyos.scientist.orchestration.workflows`)

## Purpose

`polisyos.scientist.orchestration.workflows` defines and launches the canonical
Scientist DAG specs, builds execution context, assembles node registries, and
hands the final `WorkflowSpec` to the engine runtime.

## Where to Start

- Root facade and lazy export map: [`__init__.py`](__init__.py)
- Workflow builder and launchers: [`builder.py`](builder.py)
- Route selection: [`selection.py`](selection.py)
- Builtin workflow specs: [`default.py`](default.py), [`discovery.py`](discovery.py), [`causal_full.py`](causal_full.py), [`policy_verified.py`](policy_verified.py), and [`policy_design.py`](policy_design.py)
- Engine adapters: [`engine_base.py`](engine_base.py), [`engine_simple.py`](engine_simple.py), and [`engine_langgraph.py`](engine_langgraph.py)

## Public Entrypoints

- Workflow routing in [`selection.py`](selection.py): `resolve_workflow_id(...)`
- Runtime assembly in [`builder.py`](builder.py): `build_execution_context(...)`, `build_default_registry(...)`, and `build_registry_with_builtin_nodes(...)`
- Launchers in [`builder.py`](builder.py): `run_default_workflow(...)`, `run_causal_full_workflow(...)`, `run_policy_verified_workflow(...)`, `run_policy_design_workflow(...)`, `run_discovery_workflow(...)`, and `run_selected_workflow(...)`
- Builtin DAG specs in [`default.py`](default.py), [`discovery.py`](discovery.py), [`causal_full.py`](causal_full.py), [`policy_verified.py`](policy_verified.py), and [`policy_design.py`](policy_design.py)
- Engine adapters in [`engine_simple.py`](engine_simple.py) and [`engine_langgraph.py`](engine_langgraph.py): choose between the simple loop and legacy LangGraph bridge

## Depends On / Depended On By

- Depends on: [`../engine/README.md`](../engine/README.md), [`../nodes/README.md`](../nodes/README.md), governance helpers, adapters, and shared core runtime services
- Depended on by: [`../api.py`](../api.py), routed `run_experiment(...)` calls, policy-design/discovery launchers, and workflow integration tests

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.orchestration.workflows import default_workflow_spec, resolve_workflow_id; print(default_workflow_spec().workflow_id, callable(resolve_workflow_id))"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/orchestration/workflows -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/orchestration/workflows/test_workflow_specs.py tests/unit/scientist/orchestration/workflows/test_builder_pinning.py tests/unit/scientist/orchestration/workflows/test_workflow_selection.py -q
```

## Reference Docs

- Workflow reference: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Reliability scorecard: [`../../../../docs/reference/scientist/reliability-scorecard.md`](../../../../docs/reference/scientist/reliability-scorecard.md)
- Cross-package navigation: [`../engine/README.md`](../engine/README.md), [`../nodes/README.md`](../nodes/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-04-17
