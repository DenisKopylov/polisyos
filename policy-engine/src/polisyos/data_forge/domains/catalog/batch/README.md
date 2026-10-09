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
- **Content-bound receipts** - benchmark, QC, and publish receipts bind the
  selected source/config/database/report inputs to required output bytes.
  `run_content_stage_with_receipt()` dispatches the canonical producer and
  refuses to record a receipt if inputs change during execution.
- **Material input currentness** - one producer basis binds the canonical source
  registry, metrics map, actual core seed locator, proxy alignment policy, both
  WVS registry readers, and the selected WVS local XLSX metadata fallback.
  Internal `material_inputs.py` snapshots path, current bytes, presence and
  selection. The same snapshots key proxy and WVS reader caches, including the
  derived harvest catalog, so warm readers consume current policy.
  The existing normalized legacy-serial selector and covered singleton
  SourceProfileRegistry connection/execution settings share this basis.
  Covered same-ID or file-byte edits invalidate saved stage receipts before
  reuse; mtime-only edits preserve reuse. Registry, metrics and seed absence
  refuse recomputation. Proxy/WVS policy and selected XLSX absence retain their
  existing empty/static fallback and bind absence distinctly from empty files.
  XLSX is unselected while valid nonempty WVS YAML supplies the catalog; it is
  then neither read nor required. Other file-read errors refuse recomputation.
  Existing malformed WVS YAML fallback remains explicit and its bytes remain
  bound; malformed proxy policy retains its parsing failure.
  The full singleton profile denominator is conservative: presentation-only
  and unselected profile edits also invalidate. ALL header policy, including
  non-secret content negotiation, credentials and environment auth overlays are
  excluded. No header revision or classifier is established, so complete
  effective-policy currentness remains limited pending owner invalidation or a
  non-secret revision. Raw observation corpus and remote response/version
  identity are outside this finite local configuration/assets basis.
  A separately injected RetrievalService profile registry is not bound here;
  this batch material basis does not infer a serving CatalogRunProfile.
  Serving retrieval takes the profile from `DataResolveRequest.catalog_run_profile`
  or explicit runtime configuration. Missing scope refuses catalog-backed
  resolution, and a request/runtime conflict is a named 422; neither path
  silently selects `prod_full`.
- **Embedding-generation currentness** - the embed producer projects each
  dataset through the versioned Catalog projection and binds the selected
  material basis and loaded encoder assets into the immutable generation.
  Fresh Catalog query readers recompute that same material basis and compare
  the actual query encoder's assets, model, device, and dimension with the
  selected generation before vector reuse. Refusals carry a named reason and
  preserve typed text-only results; selectorless legacy vector files require
  regeneration through the producer before vector admission.
- **Observation transport ownership** - loaders resolve their split-module
  transformer and API dependencies through the existing compatibility context.
  The connector/session cache remains owned by `core_sources/writers.py`; the
  observation API owns closing that cache after successful or failed ingestion.
  DuckDB relations separate values from identifiers without narrowing native
  integer year bounds. WVS still resolves current policy once per bulk operation.
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
- [`material_inputs.py`](material_inputs.py) provides immutable current-file snapshots
  shared by the producer basis and the canonical proxy/WVS policy readers.
- [`pipeline.py`](pipeline.py) coordinates harvest, normalize, merge/dedup,
  graph, ingest, embed, benchmark, QC, and publish stages.
- The canonical reviewed source seed is
  [`../source_registry.yaml`](../source_registry.yaml). Batch runtime uses its
  canonical parser and selection policy; the batch-local
  [`source_registry.yaml`](source_registry.yaml) remains a compatibility copy.
  Keep generated harvests and run outputs outside the source tree.
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
