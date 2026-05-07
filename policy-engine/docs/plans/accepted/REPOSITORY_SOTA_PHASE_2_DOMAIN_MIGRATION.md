# Repository SOTA Phase 2 Domain And Entrypoint Migration

- Date: 2026-05-02
- Scope: Phase 2 implementation evidence for
  `docs/plans/accepted/REPOSITORY_SOTA_PLAN.md`
- Execution posture: source topology and production entrypoints are accepted
  only with registered path maps and behavior evidence

## Contract

The machine-readable source-to-target map is
`architecture/domain_migration_batches.toml`, validated by
`schemas/topology/domain_migration_batches.schema.json`.

Each batch records:

- source paths and target paths
- owner and risk class
- public facade or production entrypoint
- compatibility status and shim ids, if any
- golden, replay, or differential evidence paths
- acceptance tests and removal criteria

## Migration Batches

| Batch | Source | Target | Compatibility | Evidence |
| --- | --- | --- | --- | --- |
| `academic-to-data-forge` | `src/polisyos/academic` | `data_forge/domains/academic`, `read_api.academic` | removed after shim sunset | non-Lex academic baseline/candidate fixtures |
| `catalog-to-data-forge` | `src/polisyos/datasets` | `data_forge/domains/catalog`, `read_api.catalog` | removed after shim sunset | non-Lex catalog baseline/candidate fixtures |
| `legal-offline-to-data-forge` | `lex/batch`, `lex/corpus` | `data_forge/domains/legal`, `read_api.legal` | removed after shim sunset | legal shadow fixtures and accepted NPA root descriptor |
| `ukraine-to-data-forge` | `src/polisyos/ukraine_data` | `data_forge/domains/ukraine`, `read_api.ukraine` | removed after shim sunset | Ukraine shadow and pre-shard differential fixtures |
| `shared-batch-to-data-forge-kernel` | `batch_common`, `batch_snapshot` | `data_forge/kernel/*` | removed after shim sunset | shared-kernel cutover tests plus release/rollback notes |
| `lex-runtime-public-facade` | runtime Lex internals | `polisyos.lex` | public facade | Lex runtime tests |
| `foundry-public-facade` | compile/execute/method internals | `polisyos.foundry` | public facade | Foundry facade and compile/execute tests |
| `scholar-public-facade` | discover/search/orchestrator internals | `polisyos.scholar` | public facade | Scholar service and evidence-tool tests |
| `scientist-public-facade` | engine/nodes/governance internals | `polisyos.scientist` | public facade | Scientist API and Foundry/Scientist contract tests |

## Entrypoints

| Entrypoint | Target | Evidence |
| --- | --- | --- |
| Legal batch CLI | `python -m polisyos.data_forge.domains.legal.batch` | `tests/unit/data_forge/test_phase4_legal_cutover.py` |
| Cloud Lex runner | `tools/ops/cloud/run_lex_from_manifest.py` importing Data Forge legal batch runtime | `tests/unit/data_forge/test_phase4_legal_cutover.py` |
| Runtime legal jobs | `polisyos.data_forge.read_api.legal` | `tests/unit/data_forge/test_phase4_legal_cutover.py` |
| Ukraine console script | `ukraine-data = polisyos.data_forge.domains.ukraine.cli:main` | `tests/unit/data_forge/test_phase8_shim_sunset.py` |
| Foundry facade | `polisyos.foundry.compile`, `polisyos.foundry.execute` | `tests/contract/test_foundry_facade_contracts.py` |
| Scholar facade | `polisyos.scholar.enrich_topic`, `ScholarService` | `tests/unit/scholar/*` |
| Scientist facade | `polisyos.scientist.run_experiment` | `tests/unit/scientist/facade/test_api.py` |

## Compatibility

The Data Forge compatibility packages for academic, catalog, Ukraine, shared
batch, snapshot, and old Lex offline paths have been removed after sunset.
Release and rollback notes live in:

- `release/data-forge-shim-sunset-release-notes.md`
- `docs/migration/data_forge_shim_sunset_rollback.md`

The remaining active migration shims are governed by
`architecture/shims.toml`; the Phase 2 audit test verifies that each
shim has an owner, source path, target path, sunset date, reason, and issue.

## Acceptance

| Requirement | Status |
| --- | --- |
| Domain migration batches have source/target path maps. | Implemented in `architecture/domain_migration_batches.toml` |
| Production entrypoints switch only with behavior evidence. | Implemented via legal, Ukraine, catalog, academic, and shared-kernel fixtures/tests |
| Direct imports are replaced by public facades or registered shims. | Implemented; source/tools/tests scan has no retired domain imports, and runtime/product packages do not import Data Forge kernel/domain internals |
| Compatibility wrappers have owner, target, sunset, and issue. | Implemented; active shim registry is audited |
| Tests mirror the new source topology while preserving regression coverage. | Implemented through `tests/unit/data_forge/domains/{academic,catalog,ukraine}`, `tests/unit/data_forge/legal_batch`, and Lex/Foundry/Scholar/Scientist focused tests |
