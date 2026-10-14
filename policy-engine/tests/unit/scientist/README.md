# Scientist Tests

`tests/unit/scientist` covers the orchestration layer: workflow engine, nodes,
governance, methods/search, DOE, agent/LLM helpers, replay, provenance, and decision
artifacts. The live test tree is the inventory for this slice; this page
describes its scope without duplicating a file or collected-test count.

## Purpose

- Keep workflow assembly, execution, checkpointing, and replay behavior stable.
- Protect governance passes, method/search strategies, and node-level contracts.
- Catch regressions in decision artifacts, agent/LLM helpers, and integration
  flows before they reach runtime.

## Where To Start

- `src/polisyos/scientist/README.md`
- `src/polisyos/scientist/orchestration/engine/README.md`
- `src/polisyos/scientist/governance/README.md`
- `engine/`, `nodes/`, `methods/`, `search/` compatibility shims, `workflows/`, and
  `tests/integration/scientist/` depending on the change.

## Public Entrypoints

- `tests/unit/scientist/facade/`: tests for public API, import boundaries,
  public-surface cutover, and remediation status.

- `tests/unit/scientist/orchestration/engine/`: tests for runner, checkpoint, lock, and
  executor details.

- `tests/unit/scientist/nodes/`: tests for builtin planning, compile, causal,
  simulate, data, and decision nodes.

- `tests/unit/scientist/methods/`: canonical method lane import and shim
  contract tests.

- `tests/unit/scientist/search/`: compatibility-era tests for search loops,
  funnels, and strategies.

- `tests/unit/scientist/governance/`: tests for passes and validation pipeline.
- `tests/unit/scientist/agent/`: tests for agent and tool-facing helpers.

## Depends On / Depended On By

### Depends On

- `src/polisyos/scientist/README.md`
- `src/polisyos/scientist/orchestration/engine/README.md`
- `src/polisyos/scientist/governance/README.md`
- `src/polisyos/foundry`, `src/polisyos/fabric`, `src/polisyos/core`,
  `src/polisyos/runtime`

### Depended On By

- `tests/unit/runtime/README.md`, `tests/integration/scientist/`, and
  `tests/performance/`

- Runtime control/debug flows and local stack smoke scenarios

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full scientist slice
uv run pytest tests/unit/scientist -q

# conceptual: focused slices
uv run pytest tests/unit/scientist/governance -q
uv run pytest tests/unit/scientist/methods -q
uv run pytest tests/unit/scientist/search -q

# conceptual: integration slice
POLISYOS_RUN_INTEGRATION=1 uv run pytest tests/integration/scientist -q
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`; this is a
historical receipt, not a verification result from this refresh.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/scientist -q
uv run pytest --collect-only tests/integration/scientist -q
```

## Reference Docs

- `src/polisyos/scientist/README.md`
- `src/polisyos/scientist/orchestration/engine/README.md`
- `src/polisyos/scientist/governance/README.md`
- `tests/TESTING_POLICY.md`

## Last Updated

2026-10-14
