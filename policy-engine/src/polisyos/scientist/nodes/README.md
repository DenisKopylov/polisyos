# Nodes (`polisyos.scientist.nodes`)

## Purpose

`polisyos.scientist.nodes` contains the builtin Scientist nodes that the engine
registers and executes inside workflow DAGs. This is the practical runtime
surface for the `data`, `planning`, `compile`, `causal`, `simulate`,
`governance`, and `decide` stages.

## Where to Start

- Stable root export: [`__init__.py`](__init__.py)
- Builtin registry assembly: [`builtins/__init__.py`](builtins/__init__.py)
- Canonical state aliases: [`builtins/state_keys.py`](builtins/state_keys.py)
- Shared validation, tracing, guards, and error helpers: [`builtins/validation.py`](builtins/validation.py), [`builtins/tracing.py`](builtins/tracing.py), [`builtins/guards.py`](builtins/guards.py), and [`builtins/errors.py`](builtins/errors.py)
- Family implementations: [`builtins/data/`](builtins/data/), [`builtins/planning/`](builtins/planning/), [`builtins/compile/`](builtins/compile/), [`builtins/causal/`](builtins/causal/), [`builtins/simulate/`](builtins/simulate/), [`builtins/governance/`](builtins/governance/), and [`builtins/decide/`](builtins/decide/)

## Public Entrypoints

- `builtin_nodes()` in [`__init__.py`](__init__.py): canonical builtin node inventory
- `NodeSpec`, `NodeOutcome`, `NodeError`, and `NodeEvent` in [`../engine/protocol.py`](../engine/protocol.py): contracts every builtin node must honor
- State alias registry in [`builtins/state_keys.py`](builtins/state_keys.py): canonical input/artifact/report keys reused by workflows and decision outputs
- Family-specific node implementations in [`builtins/`](builtins/): import concrete node classes directly from their family modules when editing behavior

## Depends On / Depended On By

- Depends on: [`../engine/README.md`](../engine/README.md), [`../compute/README.md`](../compute/README.md), [`../governance/README.md`](../governance/README.md), `adapters`, `kernel`, and cross-layer IR/Fabric/Foundry/Lex surfaces
- Depended on by: workflow builders and specs in [`../workflows/README.md`](../workflows/README.md), plus integration and node-contract tests in [`../../../../tests/scientist/README.md`](../../../../tests/scientist/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested registry check: `uv run python -c "from polisyos.scientist.nodes import builtin_nodes; print(len(builtin_nodes()))"`
- Conceptual full-slice test run: `uv run pytest tests/scientist/nodes -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/scientist/nodes/builtins/test_state_builtins.py tests/scientist/nodes/test_build_policy_output_bundle.py tests/scientist/test_causal_evaluation_node.py -q
```

## Reference Docs

- Builtin node reference: [`../../../../docs/reference/scientist/nodes.md`](../../../../docs/reference/scientist/nodes.md)
- Workflow catalog: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Cross-package navigation: [`../workflows/README.md`](../workflows/README.md), [`../engine/README.md`](../engine/README.md), and [`../../../../tests/scientist/README.md`](../../../../tests/scientist/README.md)

## Last Updated

- Last updated: 2026-04-17
