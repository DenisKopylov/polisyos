# Datasets Tests

`tests/unit/data_forge/domains/catalog` covers the Data Forge-owned catalog stack: staged catalog
build, knowledge-layer lookup, proxy alignment, and dataset publication
helpers. For the current test-file inventory, inspect
`tests/unit/data_forge/domains/catalog/`; this guide describes test areas rather
than maintaining a file count.

## Purpose

- Keep dataset ingest, normalization, dedup, QC, and publication behavior
  stable.

- Validate dataset knowledge registries and variable-alignment helpers.
- Protect transportability-oriented dataset selection logic from drift.

## Where To Start

- `src/polisyos/data_forge/README.md`
- `batch/` for catalog build, source ingest, and publish issues.
- `knowledge/` for registry, store, and variable-alignment issues.

## Test Areas

- `tests/unit/data_forge/domains/catalog/batch/`: CKAN curation, ingest, dedup,
  normalization, harvesting, QC, publish, and CLI smoke.

- `tests/unit/data_forge/domains/catalog/knowledge/`: registry, store, proxy penalties,
  proxy resolver, types, and variable alignment.

## Depends On / Depended On By

### Depends On

- `src/polisyos/data_forge/README.md`
- `src/polisyos/data_forge/domains/catalog/batch`
- `src/polisyos/data_forge/domains/catalog/knowledge`

### Depended On By

- `tests/unit/scientist/README.md` and `tests/unit/fabric/README.md` when dataset
  knowledge feeds search and transportability logic

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

From the repository root, the collect-only command below was smoke-checked on
`2026-04-17`. This is a historical receipt; the 2026-10-14 documentation
revision did not rerun it.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/data_forge/domains/catalog -q
```

## Reference Docs

- `src/polisyos/data_forge/README.md`
- `docs/adr/0055-dataset-graph-on-datasets-module.md`
- `tests/TESTING_POLICY.md`

## Editorial Revision

2026-10-14 (documentation only; no test execution)
