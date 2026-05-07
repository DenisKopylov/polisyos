# Data Forge Shim Sunset Rollback

- Status: active rollback notes, 2026-05-02
- Owner: team-data-forge
- Release notes: `release/data-forge-shim-sunset-release-notes.md`

The current Phase 8 release physically deletes the Data Forge compatibility
packages for academic, catalog, Ukraine, shared-kernel, snapshot, and old Lex
offline paths. Rollback can restore the removed shim directories from version
control, then re-enable their architecture entries as a temporary compatibility
window.

## Rollback Triggers

- Cloud Lex manifest writing regresses after switching to
  `polisyos.data_forge.kernel.pipeline.manifests`.
- Fabric retrieval source-policy lookup cannot load the Data Forge catalog
  source registry.
- Foundry release acceptance fails to load Ukraine release manifests through
  Data Forge Ukraine.
- A downstream environment still imports one of the removed Data Forge legacy
  packages.
- Historical snapshot CLI usage still expects `polisyos.batch_snapshot.cli`.
- A downstream environment still imports the retired Lex offline batch or
  corpus paths instead of Data Forge legal entrypoints.

## Rollback Steps

1. To restore the removed shim directories from version control for the affected
   package set.
2. Restore the matching `architecture/migration_shims.toml`,
   package-boundary, and public-surface entries from the previous revision.
3. Restore the affected import in the failing consumer only if a temporary
   compatibility release is required.
4. Re-run the focused test or operational dry run that exposed the regression.
5. Re-run import policy, architecture guardrails, and the Phase 8 tests.
6. Record any restored exception with a new owner, reason, and sunset date.

## Exception Restore Map

| Removed exception | Previous source | Previous import root |
| --- | --- | --- |
| `E-2026-05-DATA-FORGE-LEGAL-BATCH-COMMON-001` | `src/polisyos/data_forge/domains/legal/batch/**` | `batch_common` |
| `E-2026-04-LEX-BATCH-SCIENTIST-001` | `src/polisyos/lex/batch/benchmark.py` | `scientist` |
| `E-2026-04-FABRIC-DATASETS-001` | `src/polisyos/fabric/retrieval/service.py` | `datasets` |
| `E-2026-04-FOUNDRY-UKRAINE-DATA-001` | `src/polisyos/foundry/release_acceptance.py` | `ukraine_data` |
| `E-2026-04-DATASETS-ACADEMIC-001` | `src/polisyos/datasets/*` | `academic` |
| `polisyos-lex-batch-to-data-forge-legal` | `src/polisyos/lex/batch`, `src/polisyos/lex/corpus` | Lex offline paths |

## Full Shim Deletion Rollback

Do not roll forward by recreating partial shim modules by hand; restore the
complete deleted package from version control, then resume consumer migration
with a new sunset.
