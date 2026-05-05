# Catalog Batch (`polisyos.data_forge.domains.catalog.batch`)

`polisyos.data_forge.domains.catalog.batch` is the staged pipeline that builds
the dataset catalog and publish-ready artifacts under `snapshot_root/datasets`.

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

## Current State

- Last updated: 2026-05-01
- Data Forge Phase 8 physically removed the old `polisyos.datasets` namespace;
  this package is now the canonical implementation owner.
- `cli.py` accepts `--observation-mode {all,core,backfill}` and forwards it into `DatasetBatchConfig`.
- `benchmark.py` now reads core-ingest context, bulk equivalence manifests, and additional source-preflight / transport metrics.
- `publish.py` gates output on the consumer readiness manifest rather than just file presence.
