# Data Forge

`polisyos.data_forge` is the experimental build-time facade for asset-centric
data preparation.

- Last updated: 2026-04-23

## Public Surface

- `polisyos.data_forge`
- `polisyos.data_forge.read_api`

The package exposes `read_api` as the stable runtime entrypoint. `read_api`
keeps its domain surfaces lazy, so importing `polisyos.data_forge.read_api`
does not load `domains/` or `kernel/` internals. Domain internals under
`domains/` remain non-public.

## Role

Data Forge owns offline acquisition, normalization, publishing, and stable
runtime-safe read APIs for prepared assets.

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
