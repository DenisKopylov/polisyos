# Nodes (`polisyos.scientist.nodes`)

## Purpose

`polisyos.scientist.nodes` contains the builtin Scientist nodes that the engine
registers and executes inside workflow DAGs. This is the practical runtime
surface for the `data`, `planning`, `compile`, `causal`, `simulate`,
`governance`, and `decide` stages.

## Where to Start

- Stable root export: [`__init__.py`](__init__.py)
- Component-provider declarations: [`components.py`](components.py)
- Builtin registry assembly: [`builtins/__init__.py`](builtins/__init__.py)
- Canonical state aliases: [`builtins/state_keys.py`](builtins/state_keys.py)
- Shared validation, tracing, guards, and error helpers: [`builtins/validation.py`](builtins/validation.py), [`builtins/tracing.py`](builtins/tracing.py), [`builtins/guards.py`](builtins/guards.py), and [`builtins/errors.py`](builtins/errors.py)
- Family implementations: [`builtins/data/`](builtins/data/), [`builtins/planning/`](builtins/planning/), [`builtins/compile/`](builtins/compile/), [`builtins/causal/`](builtins/causal/), [`builtins/simulate/`](builtins/simulate/), [`builtins/governance/`](builtins/governance/), and [`builtins/decide/`](builtins/decide/)

## Public API

- `builtin_nodes()` in [`__init__.py`](__init__.py): canonical builtin node inventory
- `builtin_node_components()` in [`components.py`](components.py): builtin nodes as `ComponentProvider` instances loaded through the same discovery path as external nodes
- `discover_scientist_nodes()` in [`__init__.py`](__init__.py): explicit node discovery for builtin and `polisyos.scientist_nodes` providers
- `NodeSpec`, `NodeOutcome`, `NodeError`, and `NodeEvent` in [`../orchestration/engine/protocol.py`](../orchestration/engine/protocol.py): contracts every builtin node must honor
- State alias registry in [`builtins/state_keys.py`](builtins/state_keys.py): canonical input/artifact/report keys reused by workflows and decision outputs
- Family-specific node implementations in [`builtins/`](builtins/): import concrete node classes directly from their family modules when editing behavior

## Internal Layout

- [`__init__.py`](__init__.py) exposes the builtin inventory and extension discovery helpers.
- [`components.py`](components.py) wraps builtin nodes in component providers for
  registry bootstrap and `polisyos.scientist_nodes` parity.
- [`builtins/__init__.py`](builtins/__init__.py) assembles the builtin registry
  consumed by workflow builders.
- [`builtins/state_keys.py`](builtins/state_keys.py) owns canonical state and
  artifact aliases shared across nodes and decision outputs.
- [`builtins/validation.py`](builtins/validation.py),
  [`builtins/tracing.py`](builtins/tracing.py),
  [`builtins/guards.py`](builtins/guards.py), and
  [`builtins/errors.py`](builtins/errors.py) are shared node-runtime helpers.
- Family directories under `builtins/` own one workflow stage each:
  `data`, `planning`, `compile`, `causal`, `simulate`, `governance`, and
  `decide`.

## Extension Points

- External nodes use the `polisyos.scientist_nodes` entry-point group declared
  in
  [`architecture/extension_points.toml`](../../../../architecture/extension_points.toml).
- Builtin nodes remain package-owned and must register through
  [`components.py`](components.py) while honoring
  [`../orchestration/engine/protocol.py`](../orchestration/engine/protocol.py).
- Use [AUTHORING.md](AUTHORING.md) before adding or renaming node families.

## Depends On / Depended On By

- Depends on: [`../orchestration/engine/README.md`](../orchestration/engine/README.md), [`../compute/README.md`](../compute/README.md), [`../governance/README.md`](../governance/README.md), `adapters`, `kernel`, and cross-layer IR/Fabric/Foundry/Lex surfaces
- Depended on by: workflow builders and specs in [`../orchestration/workflows/README.md`](../orchestration/workflows/README.md), plus integration and node-contract tests in [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested registry check: `uv run python -c "from polisyos.scientist.nodes import discover_scientist_nodes; registry, report = discover_scientist_nodes(include_dev_scan=False); print(len(registry.list()), report.errors)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/nodes -q`

## Tests

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/nodes/builtins/test_state_builtins.py tests/unit/scientist/nodes/test_build_policy_output_bundle.py tests/unit/scientist/causal/test_causal_evaluation_node.py -q
```

Full node coverage is organized under
[`tests/unit/scientist/nodes/`](../../../../tests/unit/scientist/nodes/). Run
the broader Scientist workflow tests when a node changes state keys, workflow
routing, or decision artifact shape.

## Operability Links

- [Scientist component SLO](../../../../ops/components/scientist/slo.yaml)
- [Scientist component runbooks](../../../../ops/components/scientist/runbooks.md)
- [Scientist workflow catalog](../../../../docs/reference/scientist/workflows.md)
- [Scientist reliability scorecard](../../../../docs/reference/scientist/reliability-scorecard.md)
- [Runtime API outage runbook](../../../../docs/runbooks/runtime-api-outage.md)

## Known Shims/Deprecations

- There are no active package-local shims for `polisyos.scientist.nodes` in
  `architecture/shims.toml` as of 2026-05-06.
- Node IDs, state aliases, and output artifact names are workflow contracts.
  Deprecate them through workflow migration notes and compatibility tests
  before removal.
- The high-complexity decision-packet node is tracked in
  [`architecture/module_size_budget.toml`](../../../../architecture/module_size_budget.toml)
  with owner `team-scientist` and sunset `2026-12-31`.

## Reference Docs

- Builtin node reference: [`../../../../docs/reference/scientist/nodes.md`](../../../../docs/reference/scientist/nodes.md)
- Workflow catalog: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Cross-package navigation: [`../orchestration/workflows/README.md`](../orchestration/workflows/README.md), [`../orchestration/engine/README.md`](../orchestration/engine/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-05-06
