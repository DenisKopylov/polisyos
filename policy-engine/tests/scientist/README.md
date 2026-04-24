# Scientist Tests

`tests/scientist` covers the orchestration layer: workflow engine, nodes,
governance, search, DOE, agent/LLM helpers, replay, provenance, and decision
artifacts. The slice currently contains `343` `test_*.py` files across many
specialized subdirectories.

## Purpose

- Keep workflow assembly, execution, checkpointing, and replay behavior stable.
- Protect governance passes, search strategies, and node-level contracts.
- Catch regressions in decision artifacts, agent/LLM helpers, and integration
  flows before they reach runtime.

## Where To Start

- [`../../src/polisyos/scientist/README.md`](../../src/polisyos/scientist/README.md)
- [`../../src/polisyos/scientist/engine/README.md`](../../src/polisyos/scientist/engine/README.md)
- [`../../src/polisyos/scientist/governance/README.md`](../../src/polisyos/scientist/governance/README.md)
- `engine/`, `nodes/`, `search/`, and `integration/` depending on the change.

## Public Entrypoints

- `tests/scientist/` root: `73` tests for engine/executor, workflow defaults,
  replay, decision artifacts, and top-level node behavior.

- `tests/scientist/engine/`: `49` tests for runner, checkpoint, lock, and
  executor details.

- `tests/scientist/nodes/`: `42` tests for builtin planning, compile, causal,
  simulate, data, and decision nodes.

- `tests/scientist/search/`: `45` tests for search loops, funnels, and
  strategies.

- `tests/scientist/governance/`: `32` tests for passes and validation pipeline.
- `tests/scientist/agent/`: `25` tests for agent and tool-facing helpers.

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/scientist/README.md`](../../src/polisyos/scientist/README.md)
- [`../../src/polisyos/scientist/engine/README.md`](../../src/polisyos/scientist/engine/README.md)
- [`../../src/polisyos/scientist/governance/README.md`](../../src/polisyos/scientist/governance/README.md)
- `src/polisyos/foundry`, `src/polisyos/fabric`, `src/polisyos/core`,
  `src/polisyos/runtime`

### Depended On By

- [`../runtime/README.md`](../runtime/README.md),
  [`../integration/README.md`](../integration/README.md), and
  [`../performance/README.md`](../performance/README.md)

- Runtime control/debug flows and local stack smoke scenarios

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full scientist slice
uv run pytest tests/scientist -q

# conceptual: focused slices
uv run pytest tests/scientist/governance -q
uv run pytest tests/scientist/search -q

# conceptual: integration slice
POLISYOS_RUN_INTEGRATION=1 uv run pytest tests/scientist/integration -q
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/scientist -q
uv run pytest --collect-only tests/scientist/integration -q
```

## Reference Docs

- [`../../src/polisyos/scientist/README.md`](../../src/polisyos/scientist/README.md)
- [`../../src/polisyos/scientist/engine/README.md`](../../src/polisyos/scientist/engine/README.md)
- [`../../src/polisyos/scientist/governance/README.md`](../../src/polisyos/scientist/governance/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
