# Ukraine Data Tests

`tests/unit/data_forge/domains/ukraine` covers the Data Forge-owned Ukraine data domain: adapters,
builders, orchestrator, CLI, demography artifacts, and server surfaces. The
slice currently contains `6` `test_*.py` files.

## Purpose

- Keep Ukraine-specific data ingestion and serving helpers stable.
- Protect the CLI and orchestrator wiring used by the Ukraine data flows.
- Provide a single navigation point for this specialized package test slice.

## Where To Start

- [`../../../../tools/ops_runners/ukraine_data/README.md`](../../../../tools/ops_runners/ukraine_data/README.md)
- `test_orchestrator.py` and `test_server.py` for end-to-end wiring issues.
- `test_cli.py` for command-surface regressions.

## Public Entrypoints

- `tests/unit/data_forge/domains/ukraine/test_adapters.py`
- `tests/unit/data_forge/domains/ukraine/test_builders.py`
- `tests/unit/data_forge/domains/ukraine/test_cli.py`
- `tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py`
- `tests/unit/data_forge/domains/ukraine/test_orchestrator.py`
- `tests/unit/data_forge/domains/ukraine/test_server.py`

## Depends On / Depended On By

### Depends On

- [`../../../../tools/ops_runners/ukraine_data/README.md`](../../../../tools/ops_runners/ukraine_data/README.md)
- `src/polisyos/data_forge/domains/ukraine/adapters.py`
- `src/polisyos/data_forge/domains/ukraine/builders/`
- `src/polisyos/data_forge/domains/ukraine/orchestrator.py`
- `src/polisyos/data_forge/domains/ukraine/server.py`

### Depended On By

- Data tooling and server workflows built around the `ukraine-data` entrypoint
- [`../../../tools/README.md`](../../../tools/README.md) and
  [`../../../README.md`](../../../README.md)
  for local navigation

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: Ukraine data slice
uv run pytest tests/unit/data_forge/domains/ukraine -q

# conceptual: targeted server probe
uv run pytest tests/unit/data_forge/domains/ukraine/test_server.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/data_forge/domains/ukraine -q
```

## Reference Docs

- [`../../../../tools/ops_runners/ukraine_data/README.md`](../../../../tools/ops_runners/ukraine_data/README.md)
- [`../../../TESTING_POLICY.md`](../../../TESTING_POLICY.md)
- [`../../../README.md`](../../../README.md)

## Last Updated

2026-05-02
