# Scientist (`polisyos.scientist`)

## Purpose

`polisyos.scientist` is the orchestration layer that turns an
`ExperimentState` into a routed workflow run, executes builtin nodes, applies
governance, and publishes replayable decision artifacts across the `ir`,
`foundry`, `fabric`, `lex`, `scholar`, and `core` stacks.

## Where to Start

- Stable facade and top-level entrypoint: [`__init__.py`](__init__.py) and [`api.py`](api.py)
- Workflow assembly and routing: [`workflows/README.md`](workflows/README.md) and [`workflows/builder.py`](workflows/builder.py)
- DAG execution semantics: [`engine/README.md`](engine/README.md)
- Builtin runtime nodes: [`nodes/README.md`](nodes/README.md)
- Governance, calibration, and accountability: [`governance/README.md`](governance/README.md)

## Public Entrypoints

- `run_experiment(...)` in [`api.py`](api.py): top-level execution entrypoint used by the package facade
- `ExperimentState` in [`engine/state.py`](engine/state.py): boundary model passed across nodes and checkpoints
- Workflow launchers in [`workflows/builder.py`](workflows/builder.py): `run_default_workflow(...)`, `run_causal_full_workflow(...)`, `run_policy_verified_workflow(...)`, `run_policy_design_workflow(...)`, and `run_discovery_workflow(...)`
- Workflow specs in [`workflows/`](workflows/): inspect builtin DAG layouts before changing routing or nodes
- Governance helpers in [`governance/preflight.py`](governance/preflight.py) and [`governance/postflight.py`](governance/postflight.py): pre/post-flight validation surfaces
- `builtin_nodes()` in [`nodes/__init__.py`](nodes/__init__.py): canonical builtin node inventory used by workflow builders

## Depends On / Depended On By

- Depends on: [`../core/README.md`](../core/README.md), [`../ir/README.md`](../ir/README.md), [`../foundry/README.md`](../foundry/README.md), [`../fabric/README.md`](../fabric/README.md), [`../lex/README.md`](../lex/README.md), and [`../scholar/README.md`](../scholar/README.md)
- Depended on by: runtime/control flows, policy-design entrypoints, and the Scientist verification surface in [`../../../tests/unit/scientist/README.md`](../../../tests/unit/scientist/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist import ExperimentState, run_experiment; print(ExperimentState.__name__, callable(run_experiment))"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/workflows/test_workflow_selection.py tests/unit/scientist/governance/test_reliability_scorecard.py -q
```

## Reference Docs

- Reference index: [`../../../docs/reference/scientist/index.md`](../../../docs/reference/scientist/index.md)
- Workflow catalog: [`../../../docs/reference/scientist/workflows.md`](../../../docs/reference/scientist/workflows.md)
- Builtin node reference: [`../../../docs/reference/scientist/nodes.md`](../../../docs/reference/scientist/nodes.md)
- Reliability and release gates: [`../../../docs/reference/scientist/reliability-scorecard.md`](../../../docs/reference/scientist/reliability-scorecard.md)
- Lane source plan: [`../../../docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`](../../../docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md)

## Last Updated

- Last updated: 2026-04-17
