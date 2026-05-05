# Academic Tests

`tests/unit/data_forge/domains/academic` covers the Data Forge-owned offline academic knowledge-graph
stack: OpenAlex/topic selection, staged extraction, graph build, trust scoring,
and knowledge-layer lookups. The slice currently contains `35` `test_*.py`
files.

## Purpose

- Keep academic batch pipelines reproducible and snapshot-safe.
- Protect SKG graph construction, trust scoring, and topic selection behavior.
- Validate read-only knowledge helpers used by downstream evidence workflows.

## Where To Start

- [`../../../../src/polisyos/data_forge/README.md`](../../../../src/polisyos/data_forge/README.md)
- `batch/` for harvest, extraction, graph-build, and publication issues.
- `knowledge/` for canonical resolution and runtime lookup issues.

## Public Entrypoints

- `tests/unit/data_forge/domains/academic/batch/`: `30` tests for extraction, manifests, graph build,
  benchmarking, trust, QC, and CLI smoke paths.

- `tests/unit/data_forge/domains/academic/knowledge/`: `5` tests for canonical resolver, parameter
  selector, SKG query, and helper types.

## Depends On / Depended On By

### Depends On

- [`../../../../src/polisyos/data_forge/README.md`](../../../../src/polisyos/data_forge/README.md)
- `src/polisyos/data_forge/domains/academic/batch`
- `src/polisyos/data_forge/domains/academic/knowledge`

### Depended On By

- [`../../../scientist/README.md`](../../../scientist/README.md) and
  [`../../../fabric/README.md`](../../../fabric/README.md) when academic evidence feeds
  policy workflows

- Batch tooling and snapshot curation flows

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full academic slice
uv run pytest tests/unit/data_forge/domains/academic -q

# conceptual: focused slices
uv run pytest tests/unit/data_forge/domains/academic/batch -q
uv run pytest tests/unit/data_forge/domains/academic/knowledge -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/data_forge/domains/academic -q
```

## Reference Docs

- [`../../../../src/polisyos/data_forge/README.md`](../../../../src/polisyos/data_forge/README.md)
- [`../../../../docs/adr/0054-skg-on-academic-module.md`](../../../../docs/adr/0054-skg-on-academic-module.md)
- [`../../../TESTING_POLICY.md`](../../../TESTING_POLICY.md)

## Last Updated

2026-05-02
