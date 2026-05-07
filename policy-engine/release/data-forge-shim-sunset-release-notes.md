# Data Forge Shim Sunset Release Notes

- Status: physical removal complete, 2026-05-02
- Owner: team-data-forge
- Rollback: `docs/migration/data_forge_shim_sunset_rollback.md`

Phase 8 physically removes compatibility shims after the migration-shim
registry, import-policy checks, package-boundary checks, release notes,
rollback notes, and targeted tests all agree that old import paths are unused.

External live consumers have been migrated to Data Forge read APIs or Data
Forge-owned CLI entrypoints. The implementation-owner moves are complete and
the old forwarding packages have been physically removed.

## Completed In This Release

- Data Forge legal batch modules now import shared-kernel manifest, runtime,
  and quality helpers directly instead of `polisyos.batch_common`.
- The cloud Lex manifest runner now writes manifests through
  `polisyos.data_forge.kernel.pipeline.manifests`.
- Fabric retrieval policy lookup now reads the Data Forge catalog source
  registry instead of `polisyos.datasets.batch.source_registry`.
- Foundry release acceptance now reads Ukraine release manifests through
  `polisyos.data_forge.read_api.ukraine`.
- Ukraine operational builder tools and the `ukraine-data` console entrypoint
  now target Data Forge Ukraine modules.
- Scientist cross-graph, causal node, agent knowledge, and prior-mining
  consumers now import academic/catalog contracts through
  `polisyos.data_forge.read_api.*`.
- IR analytics alignment and transportability consumers now import catalog
  proxy/alignment contracts through `polisyos.data_forge.read_api.catalog`.
- Foundry literature-prior construction now imports academic SKG access through
  `polisyos.data_forge.read_api.academic`.
- Cloud academic/catalog shell entrypoints now invoke Data Forge-owned CLI
  modules.
- Legal benchmark and Ukraine pre-shard tools now import Legal batch helpers
  through `polisyos.data_forge.read_api.legal`.
- Legal offline batch CLI and corpus preprocessing now live only under
  `polisyos.data_forge.domains.legal`; the old Lex offline entrypoints were
  physically removed.
- Scientist Ukraine real-history backtest metadata now points at a
  Data Forge-owned Ukraine contract marker instead of the old
  `polisyos.ukraine_data` namespace.
- Obsolete import-policy exceptions for Data Forge legal batch to
  `batch_common`, Fabric retrieval to `datasets`, and Foundry release
  acceptance to `ukraine_data` were removed.
- The old Lex batch benchmark-to-Scientist exception was removed with the
  retired Lex batch package.
- The obsolete datasets-to-academic import exception was removed because
  catalog code now reaches academic canonical metadata through
  `polisyos.data_forge.read_api.academic`.
- Phase 8 tests cover the migrated read/API consumers, old shim removal
  readiness notes, deleted shim directories, the
  canonical academic/catalog/legal/Ukraine test import paths, and the
  no-longer-needed exception burn-down.

## polisyos-academic-to-data-forge

External live consumers have been migrated. The implementation-owner move is
complete: OpenAlex, batch, SKG, canonicalization, prompt, and CLI
implementation code now lives under `polisyos.data_forge.domains.academic`.
`src/polisyos/academic` has been removed.

## polisyos-datasets-to-data-forge

External live consumers have been migrated. The implementation-owner move is
complete: batch, Dataset Catalog Graph, proxy-resolution, variable-alignment,
metrics-map, and CLI implementation code now lives under
`polisyos.data_forge.domains.catalog`. `src/polisyos/datasets` has been
removed.

## polisyos-ukraine-data-to-data-forge

The production Ukraine modules have Data Forge owners, external operational
consumers now target Data Forge, and `src/polisyos/ukraine_data` has been
removed.

## polisyos-lex-batch-to-data-forge-legal

External research/ops consumers have been migrated to Data Forge read APIs or
Data Forge-owned CLI entrypoints. The implementation-owner move is complete:
batch stages, CLI, corpus preprocessing, active-version indexes, SPO extraction
payload contracts, QC, benchmark, publish, and cache/resume helpers now live
under `polisyos.data_forge.domains.legal`. `src/polisyos/lex/batch` and
`src/polisyos/lex/corpus` have been removed.

Canonical replacements:

- batch/offline pipeline: `polisyos.data_forge.domains.legal.batch`
- corpus preprocessing: `polisyos.data_forge.domains.legal.corpus`
- runtime-safe corpus reads: `polisyos.data_forge.read_api.legal`
- legal KG runtime reads: `polisyos.lex.knowledge`

## polisyos-batch-common-to-data-forge-kernel

The implementation-owner move is complete for academic, catalog, legal, and
Ukraine domains. `src/polisyos/batch_common` has been removed; shared-kernel
imports now target `polisyos.data_forge.kernel`.

## polisyos-batch-snapshot-to-data-forge-kernel-snapshot

`src/polisyos/batch_snapshot` has been removed. Historical snapshot CLI usage
has been replaced by `python -m polisyos.data_forge.kernel.snapshot.cli`.

## Next Sunset Gates

- Keep removed Data Forge package names out of public surface, package
  boundaries, migration shims, and runtime imports.
- Keep retired Lex offline package names out of runtime imports and public
  surface inventories.
- Re-run import-linter, package-boundary checks, import policy, and
  `tests/unit/data_forge/test_phase8_shim_sunset.py` before deleting any shim path.
