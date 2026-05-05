# Scientist Tests

`tests/unit/scientist` covers the orchestration layer: workflow engine, nodes,
governance, search, DOE, agent/LLM helpers, replay, provenance, and decision
artifacts. The slice currently contains `427` `test_*.py` files across many
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
- `engine/`, `nodes/`, `search/`, `workflows/`, and
  [`../../integration/scientist`](../../integration/scientist) depending on the
  change.

## Public Entrypoints

- `tests/unit/scientist/facade/`: `4` tests for public API, import boundaries,
  public-surface cutover, and remediation status.

- `tests/unit/scientist/engine/`: `55` tests for runner, checkpoint, lock, and
  executor details.

- `tests/unit/scientist/nodes/`: `60` tests for builtin planning, compile, causal,
  simulate, data, and decision nodes.

- `tests/unit/scientist/search/`: `51` tests for search loops, funnels, and
  strategies.

- `tests/unit/scientist/governance/`: `38` tests for passes and validation pipeline.
- `tests/unit/scientist/agent/`: `43` tests for agent and tool-facing helpers.

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
uv run pytest tests/unit/scientist -q

# conceptual: focused slices
uv run pytest tests/unit/scientist/governance -q
uv run pytest tests/unit/scientist/search -q

# conceptual: integration slice
POLISYOS_RUN_INTEGRATION=1 uv run pytest tests/integration/scientist -q
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/scientist -q
uv run pytest --collect-only tests/integration/scientist -q
```

## Reference Docs

- [`../../src/polisyos/scientist/README.md`](../../src/polisyos/scientist/README.md)
- [`../../src/polisyos/scientist/engine/README.md`](../../src/polisyos/scientist/engine/README.md)
- [`../../src/polisyos/scientist/governance/README.md`](../../src/polisyos/scientist/governance/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-05-03
