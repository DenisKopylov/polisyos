# Catalog Batch (`polisyos.data_forge.domains.catalog.batch`)

`polisyos.data_forge.domains.catalog.batch` is the staged pipeline that builds
the dataset catalog and publish-ready artifacts under `snapshot_root/datasets`.

## Purpose

Use this package for offline dataset catalog builds that harvest source
metadata, normalize records, publish searchable snapshots, and emit readiness
evidence consumed by downstream catalog/search, transportability, and policy
analysis flows.

## Role in System

- **Depends on:** `data_forge.kernel`, `fabric.connectors`,
  `data_forge.domains.catalog.knowledge`, and the Data Forge source registry.
- **Used by:** dataset discovery/search consumers, transportability checks, and downstream readiness flows.
- **Boundary function:** owns source-module contracts and read APIs in Data
  Forge.

## Key Concepts

- **Staged pipeline** - harvest, normalize, merge/dedup, graph load/index, core source ingest, embed, benchmark, QC, publish.
- **Observation mode** - `observation_mode` controls whether runs build core, backfill, or all observations.
- **Benchmarking** - the benchmark stage now folds in core-ingest context and bulk-equivalence metrics.
- **Readiness gating** - QC and publish use the benchmark/readiness outputs to decide whether the snapshot is consumer-ready.
- **Transportability ingest** - source-module contracts live in
  `polisyos.data_forge.read_api.catalog` and split source registry,
  harvest, normalize, observation, and publish contracts by source.

## Public API

- config: `DatasetBatchConfig`, `ALL_STAGES`, `DEFAULT_RUN_STAGES`
- CLI commands: `run`, `harvest`, `normalize`, `merge-dedup`, `graph-load`, `graph-index`, `core-sources-ingest`, `embed`, `benchmark`, `qc`, `publish`, `stats`, `search`
- stage modules: `benchmark.py`, `core_sources_ingest.py`, `pipeline.py`, `publish.py`, `qc.py`

## Internal Layout

- [`config.py`](config.py) owns `DatasetBatchConfig`, stage constants, and
  observation-mode wiring.
- [`cli.py`](cli.py) is the operator/dev entrypoint for staged catalog batch
  runs.
- [`pipeline.py`](pipeline.py) coordinates harvest, normalize, merge/dedup,
  graph, ingest, embed, benchmark, QC, and publish stages.
- [`source_registry.yaml`](source_registry.yaml) is a reviewed product seed
  input. Keep generated harvests and run outputs outside the source tree.
- [`core_sources_ingest.py`](core_sources_ingest.py) is the current
  high-complexity ingestion owner tracked in `architecture/module_size_budget.toml`.

## Extension Points

- External Data Forge domains use the `polisyos.data_forge_domains` entry-point
  group declared in
  [architecture/extension_points.toml](../../../../../../architecture/extension_points.toml).
- This subtree is the builtin catalog batch implementation. New source modules
  should land through reviewed registry metadata, deterministic tests, and
  Data Forge domain authoring rules in [AUTHORING.md](AUTHORING.md).

## Tests

Run from the repository root:

```bash
uv run pytest tests/unit/data_forge/domains/catalog/batch -q
uv run pytest tests/unit/data_forge/test_phase3_catalog_completion.py -q
```

Package-local test ownership lives under
[tests/unit/data_forge/domains/catalog/batch/](../../../../../../tests/unit/data_forge/domains/catalog/batch/).

## Operability Links

- [Data Forge component SLO](../../../../../../ops/components/data_forge/slo.yaml)
- [Data Forge component runbooks](../../../../../../ops/components/data_forge/runbooks.md)
- [Manage generated artifacts](../../../../../../docs/how-to/manage-generated-artifacts.md)
- [Retained artifact recovery runbook](../../../../../../docs/runbooks/retained-artifact-recovery.md)
- [Data Forge consolidation plan](../../../../../../docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md)

## Known Shims/Deprecations

- The old `polisyos.datasets` namespace was physically removed during Data
  Forge Phase 8; this package is now the canonical catalog batch owner.
- `core_sources_ingest.py` remains a budgeted high-complexity module in
  [architecture/module_size_budget.toml](../../../../../../architecture/module_size_budget.toml)
  with owner `team-data-forge` and sunset `2026-12-31`.
- Renaming source-registry fields or batch commands requires migration notes,
  fixture updates, and compatibility tests before old names are removed.

## Current State

- Last updated: 2026-05-06
- Data Forge Phase 8 physically removed the old `polisyos.datasets` namespace;
  this package is now the canonical implementation owner.
- `cli.py` accepts `--observation-mode {all,core,backfill}` and forwards it into `DatasetBatchConfig`.
- `benchmark.py` now reads core-ingest context, bulk equivalence manifests, and additional source-preflight / transport metrics.
- `publish.py` gates output on the consumer readiness manifest rather than just file presence.
