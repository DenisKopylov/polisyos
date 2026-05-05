# Datasets Tests

`tests/unit/data_forge/domains/catalog` covers the Data Forge-owned catalog stack: staged catalog
build, knowledge-layer lookup, proxy alignment, and dataset publication
helpers. The slice currently contains `19` `test_*.py` files.

## Purpose

- Keep dataset ingest, normalization, dedup, QC, and publication behavior
  stable.

- Validate dataset knowledge registries and variable-alignment helpers.
- Protect transportability-oriented dataset selection logic from drift.

## Where To Start

- [`../../../../src/polisyos/data_forge/README.md`](../../../../src/polisyos/data_forge/README.md)
- `batch/` for catalog build, source ingest, and publish issues.
- `knowledge/` for registry, store, and variable-alignment issues.

## Public Entrypoints

- `tests/unit/data_forge/domains/catalog/batch/`: `13` tests for CKAN curation, ingest, dedup,
  normalization, harvesting, QC, publish, and CLI smoke.

- `tests/unit/data_forge/domains/catalog/knowledge/`: `6` tests for registry, store, proxy penalties,
  proxy resolver, types, and variable alignment.

## Depends On / Depended On By

### Depends On

- [`../../../../src/polisyos/data_forge/README.md`](../../../../src/polisyos/data_forge/README.md)
- `src/polisyos/data_forge/domains/catalog/batch`
- `src/polisyos/data_forge/domains/catalog/knowledge`

### Depended On By

- [`../../../scientist/README.md`](../../../scientist/README.md) and
  [`../../../fabric/README.md`](../../../fabric/README.md) when dataset knowledge feeds
  search and transportability logic

- Data curation and benchmark preparation flows

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full datasets slice
uv run pytest tests/unit/data_forge/domains/catalog -q

# conceptual: focused slices
uv run pytest tests/unit/data_forge/domains/catalog/batch -q
uv run pytest tests/unit/data_forge/domains/catalog/knowledge -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/data_forge/domains/catalog -q
```

## Reference Docs

- [`../../../../src/polisyos/data_forge/README.md`](../../../../src/polisyos/data_forge/README.md)
- [`../../../../docs/adr/0055-dataset-graph-on-datasets-module.md`](../../../../docs/adr/0055-dataset-graph-on-datasets-module.md)
- [`../../../TESTING_POLICY.md`](../../../TESTING_POLICY.md)

## Last Updated

2026-05-02
