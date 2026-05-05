# Data Forge

`polisyos.data_forge` is the experimental build-time facade for asset-centric
data preparation and governed artifact publication.

- Last updated: 2026-05-02

## Public Surface

- `polisyos.data_forge`
- `polisyos.data_forge.read_api`

The top-level package lazily exports build-time contracts for asset identity,
`ArtifactRef` governance, schema registry access, snapshot transactions,
quality checks, and golden/differential migration tests. Runtime consumers use
`polisyos.data_forge.read_api` only. `read_api` keeps its domain surfaces lazy,
so importing `polisyos.data_forge.read_api` does not load `domains/` or
`kernel/` internals. Domain internals under `domains/` remain non-public.

## Role

Data Forge owns offline acquisition, normalization, publishing, and stable
runtime-safe read APIs for prepared assets.

Phase 1 shared-kernel cutover has moved reusable batch primitives into
`polisyos.data_forge.kernel`. The legacy `batch_common` and `batch_snapshot`
packages were removed in the Phase 8 shim sunset.

Phase 2 academic completion has moved academic batch asset contracts, schema
contracts, readiness readers, benchmark/QC readers, artifact-hash comparisons,
and read-only SKG inspection behind `polisyos.data_forge.read_api.academic`.
The legacy `polisyos.academic` package was removed in the Phase 8 shim sunset.

Phase 3 catalog completion has moved catalog source registry contracts,
per-source source-module planning, harvest/normalize/observation/publish asset
contracts, catalog schema contracts, readiness readers, benchmark/QC readers,
and publish-artifact differential checks behind
`polisyos.data_forge.read_api.catalog`. The legacy `polisyos.datasets` package
was removed in the Phase 8 shim sunset.

Phase 4 legal cutover moved Lex batch runtime modules into
`polisyos.data_forge.domains.legal.batch`. Phase 8 retired the old Lex batch
and corpus packages; cloud Lex runner imports now target the Data Forge legal
batch runtime directly.

Phase 8 removed the academic, catalog, Ukraine, shared-kernel, snapshot, and
old Lex offline compatibility packages. Release and rollback notes live under
`docs/migration/`.

## Where to Start

- Read the active plan:
  [`docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`](/Users/deniskopylov/polisyos/policy-engine/docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md)

- Review the stable import contract in
  [`architecture/public_surface.toml`](/Users/deniskopylov/polisyos/policy-engine/architecture/public_surface.toml)

- Start runtime-safe consumption from `polisyos.data_forge.read_api`

## Source Of Truth

- Architecture contract:
  [`architecture/public_surface.toml`](/Users/deniskopylov/polisyos/policy-engine/architecture/public_surface.toml)

- Active implementation plan:
  [`docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`](/Users/deniskopylov/polisyos/policy-engine/docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md)
