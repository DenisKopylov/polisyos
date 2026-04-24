# Ukraine Data Tests

`tests/ukraine_data` covers the focused Ukraine data package: adapters,
builders, orchestrator, CLI, and server surfaces. The slice currently contains
`5` `test_*.py` files.

## Purpose

- Keep Ukraine-specific data ingestion and serving helpers stable.
- Protect the CLI and orchestrator wiring used by the Ukraine data flows.
- Provide a single navigation point for this specialized package test slice.

## Where To Start

- [`../../tools/ukraine_data/README.md`](../../tools/ukraine_data/README.md)
- `test_orchestrator.py` and `test_server.py` for end-to-end wiring issues.
- `test_cli.py` for command-surface regressions.

## Public Entrypoints

- `tests/ukraine_data/test_adapters.py`
- `tests/ukraine_data/test_builders.py`
- `tests/ukraine_data/test_cli.py`
- `tests/ukraine_data/test_orchestrator.py`
- `tests/ukraine_data/test_server.py`

## Depends On / Depended On By

### Depends On

- [`../../tools/ukraine_data/README.md`](../../tools/ukraine_data/README.md)
- `src/polisyos/ukraine_data/adapters.py`
- `src/polisyos/ukraine_data/builders.py`
- `src/polisyos/ukraine_data/orchestrator.py`
- `src/polisyos/ukraine_data/server.py`

### Depended On By

- Data tooling and server workflows built around the `ukraine-data` entrypoint
- [`../tools/README.md`](../tools/README.md) and [`../README.md`](../README.md)
  for local navigation

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: Ukraine data slice
uv run pytest tests/ukraine_data -q

# conceptual: targeted server probe
uv run pytest tests/ukraine_data/test_server.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/ukraine_data -q
```

## Reference Docs

- [`../../tools/ukraine_data/README.md`](../../tools/ukraine_data/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- [`../README.md`](../README.md)

## Last Updated

2026-04-17
