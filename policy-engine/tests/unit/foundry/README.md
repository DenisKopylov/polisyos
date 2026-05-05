# Foundry Tests

`tests/unit/foundry` covers the compute layer: compile/execute, methods catalogs,
calibration, uncertainty, runtime batches, plugins, and agent-simulation
support. The slice currently contains `374` `test_*.py` files.

## Purpose

- Keep compile/execute contracts, determinism, and numerical invariants stable.
- Protect the methods registry and large catalog surface from protocol drift.
- Catch calibration, uncertainty, and agent-simulation regressions before they
  propagate into scientist workflows.

## Where To Start

- [`../../src/polisyos/foundry/README.md`](../../src/polisyos/foundry/README.md)
- [`../../src/polisyos/foundry/methods/README.md`](../../src/polisyos/foundry/methods/README.md)
- `methods/`, `calibration/`, `runtime/`, and `uncertainty/` depending on the
  part of Foundry you touched.

## Public Entrypoints

- `tests/unit/foundry/facade/`: `4` tests for compile/execute facades,
  quickstart behavior, and public modules.

- `tests/unit/foundry/methods/`: `241` tests for registry, protocol/compiler
  plumbing, backends, and catalog coverage.

- `tests/unit/foundry/agent_sim/`: `21` tests for simulation and monitoring paths.
- `tests/unit/foundry/calibration/`: `18` tests for calibration behavior.
- `tests/unit/foundry/runtime/`: `19` tests for runtime-adjacent execution behavior.
- `tests/unit/foundry/uncertainty/`: `13` tests for uncertainty interfaces and
  propagation.

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/foundry/README.md`](../../src/polisyos/foundry/README.md)
- [`../../src/polisyos/foundry/methods/README.md`](../../src/polisyos/foundry/methods/README.md)
- `src/polisyos/core`
- `src/polisyos/ir`

### Depended On By

- [`../scientist/README.md`](../scientist/README.md),
  [`../runtime/README.md`](../runtime/README.md), and
  [`../performance/README.md`](../performance/README.md)

- Demo and benchmark flows that rely on stable compile/execute behavior

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full foundry slice
uv run pytest tests/unit/foundry -q

# conceptual: methods-heavy slice
uv run pytest tests/unit/foundry/methods -q

# conceptual: targeted hot checks
uv run pytest tests/unit/foundry/runtime/test_execute_input_bindings.py -q
uv run pytest tests/unit/foundry/calibration/test_calibrator_mvp.py -q
uv run pytest tests/unit/foundry/analysis/test_merge_determinism.py -q
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/foundry -q
uv run pytest --collect-only tests/unit/foundry/methods -q
```

## Reference Docs

- [`../../src/polisyos/foundry/README.md`](../../src/polisyos/foundry/README.md)
- [`../../src/polisyos/foundry/methods/README.md`](../../src/polisyos/foundry/methods/README.md)
- [`../../docs/how-to/run-benchmarks.md`](../../docs/how-to/run-benchmarks.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-05-03
