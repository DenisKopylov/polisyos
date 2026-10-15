# Ukraine Data Tests

`tests/unit/data_forge/domains/ukraine` covers the Data Forge-owned Ukraine data domain: adapters,
builders, orchestrator, CLI, demography artifacts, and server surfaces. Its
tracked `test_*.py` files are the source inventory; file counts are not counts
of tests collected or executed.

## Purpose

- Keep Ukraine-specific data ingestion and serving helpers stable.
- Protect the CLI and orchestrator wiring used by the Ukraine data flows.
- Provide a single navigation point for this specialized package test slice.

## Where To Start

- `tools/ops_runners/ukraine_data/README.md`
- `test_orchestrator.py` and `test_server.py` for end-to-end wiring issues.
- `test_cli.py` for command-surface regressions.

## Test Module Inventory

The canonical inventory is the tracked `test_*.py` files under this directory.
From `policy-engine/`, list those source files with:

```bash
git ls-files tests/unit/data_forge/domains/ukraine | rg '(^|/)test_[^/]+\.py$'
```

This lists test modules; it does not collect or execute test cases.

## Depends On / Depended On By

### Depends On

- `tools/ops_runners/ukraine_data/README.md`
- `src/polisyos/data_forge/domains/ukraine/adapters.py`
- `src/polisyos/data_forge/domains/ukraine/builders/`
- `src/polisyos/data_forge/domains/ukraine/orchestrator.py`
- `src/polisyos/data_forge/domains/ukraine/server.py`

### Depended On By

- Data tooling and server workflows built around the `ukraine-data` entrypoint
- `tools/README.md` and `tests/README.md` for local navigation

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: Ukraine data slice
uv run pytest tests/unit/data_forge/domains/ukraine -q

# conceptual: targeted server probe
uv run pytest tests/unit/data_forge/domains/ukraine/test_server.py -q
```

## Test And Verification Commands

The collect-only command below is a historical receipt dated `2026-04-17`; it
was not rerun for this documentation correction.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/data_forge/domains/ukraine -q
```

## Reference Docs

- `tools/ops_runners/ukraine_data/README.md`
- `tests/TESTING_POLICY.md`
- `tests/README.md`

## Last Updated

2026-10-14
