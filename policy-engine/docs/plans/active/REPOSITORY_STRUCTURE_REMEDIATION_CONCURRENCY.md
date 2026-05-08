---
title: Repository Structure Remediation Concurrency Contract
status: active
owner: team-polisyos
created: 2026-05-03
last_verified: 2026-05-03
stability: draft
---

# Repository Structure Remediation Concurrency Contract

This document is the Phase 0 handoff for parallel implementation of
`docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md`.

## Execution Model

| Execution slot | Phases                  | Parallelism                            | Merge rule                                                   |
| -------------- | ----------------------- | -------------------------------------- | ------------------------------------------------------------ |
| First barrier  | Phase 0                 | Singleton                              | Inventory, contracts, ADR skeletons, report-only gates first |
| Wave 1         | 1A, 1B, 1C, 1D, 1E, 1F  | Fully parallel after Phase 0           | All Wave 1 work merged before Phase 2A                       |
| Path barrier   | 2A -> 2B                | Sequential                             | Workspace boundary before `_build/` / `_cache/`              |
| Wave 2         | 3A, 3B                  | Parallel                               | 3A safety net and 3B planning only                           |
| Wave 3         | 4A, 4B                  | Parallel                               | Backend package moves and frontend workspace/output          |
| Decomp barrier | 5 -> 6                  | Sequential                             | Scientist before Foundry                                     |
| Final barrier  | Phase 7                 | Singleton                              | Fail-closed gates and closeout                               |

## Ownership Fences

| Phase | Primary owner | Owns | Must not touch in parallel |
| ----- | ------------- | ---- | -------------------------- |
| 1A | team-architecture / team-data-forge | `foundry/methods/`, loose data/runtime artifacts, `architecture/generated_artifacts.toml` | `pyproject.toml`, `tools/quality/validation/`, frontend source |
| 1B | team-devx / team-architecture | `pyproject.toml`, split config files, `architecture/imports/`, `architecture/policies/` | `tests/`, frontend, package source moves |
| 1C | team-architecture | `architecture/name_registry.toml`, `architecture/packages/layout.toml`, name ADRs | Physical moves in `scientist/` or `foundry/` |
| 1D | team-devx | `tools/{devx,ops,quality,research,ci}`, tool shims, CI references | `tools/devx/refactor/move_module.py`, new Phase 3A validation gates |
| 1E | team-quality | `tests/`, `architecture/tests/topology.toml` | Source package moves |
| 1F | team-frontend | `apps/runtime-dashboard/src/**` duplicate cleanup | Lockfiles, workspace manager, `_build/` paths |
| 2A | team-platform | Workspace root layout, `.venv`, lockfile placement, topology paths | Safety net baselines |
| 2B | team-devx | `_build/`, `_cache/`, `.gitignore`, tool cache dirs | Source package moves |
| 3A | team-architecture | `DECOMPOSITION_BLUEPRINT.md`, safety gates, codemod, baselines | Any `.py` moves in `scientist/` or `foundry/` |
| 3B | team-architecture | `SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md`, ADR-RSR-0138/0139 decisions | Actual package moves |
| 4A | package owners | `ddm`, `packs`, `synthetic_world`, `agent_sim`, `calibration`, `berl` | Frontend workspace |
| 4B | team-frontend | Frontend workspace manager, frontend build outputs | Backend package source |
| 5 | team-scientist | `src/polisyos/scientist/**`, scientist tests/contracts | `src/polisyos/foundry/**` except accepted shared shims |
| 6 | team-foundry | `src/polisyos/foundry/**`, foundry tests/contracts | Scientist moves |

## Shared Registry Rule

The following files are shared registries and must be updated through short
serialized patches, not long-running parallel branches:

- `architecture/shims.toml`
- `architecture/public_surface/contract.toml`
- `architecture/packages/boundaries.toml`
- `architecture/imports/contracts.toml`
- `architecture/topology.toml`
- `docs/adr/index.md`

## Defect Ownership Map

| Section 0 defect | Owner | Primary phase | Target contract(s) |
| ---------------- | ----- | ------------- | ------------------ |
| 1. Empty `foundry/methods/` namespace placeholders | team-architecture | 1A | ADR-RSR-0129, ADR-RSR-0136, `architecture/packages/layout.toml`, `empty_namespace_gate` |
| 2. Double workspace and duplicated caches/venv | team-platform | 2A | ADR-RSR-0130, ADR-RSR-0131, `architecture/topology.toml`, `cache_dir_gate` |
| 3. Oversized `scientist/` and `foundry/` packages with loose root modules | team-scientist / team-foundry | 3A, 5, 6 | ADR-RSR-0133, `architecture/packages/layout.toml`, `loose_files_gate`, `DECOMPOSITION_BLUEPRINT.md` |
| 4. Cross-package directory-name collisions | team-architecture | 1C | ADR-RSR-0134, `architecture/name_registry.toml`, `name_collision_gate` |
| 5. Weak/versioned/placeholder packages and ambiguous canonical homes | team-architecture | 3B, 4A | ADR-RSR-0135, ADR-RSR-0137, ADR-RSR-0138, ADR-RSR-0139, `architecture/packages/layout.toml`, `architecture/name_registry.toml` |
| 6. Oversized `pyproject.toml` | team-devx | 1B | ADR-RSR-0132, `pyproject_size_gate`, split config files |
| 7. Build-output/cache/governance path chaos | team-devx / team-architecture | 1B, 2B | ADR-RSR-0131, ADR-RSR-0132, `architecture/generated_artifacts.toml`, `architecture/topology.toml`, `build_output_gate` |

The same mapping is mirrored in
`architecture/gates/structure_remediation.toml` for machine-readable Phase 7
closeout checks.

## Wave 1 Start Checklist

Before any Wave 1 phase starts:

- Phase 0 inventory snapshot exists.
- ADR-RSR-0129..ADR-RSR-0139 skeletons exist.
- `architecture/name_registry.toml`, `architecture/packages/layout.toml`, and
  `architecture/tests/topology.toml` exist.
- Report-only gates run without failing the command.
- Each Wave 1 branch declares its primary owner and owned path set.

## Wave 1 Closeout Checklist

Phase 2A starts only after:

- Phase 1A quick wins are merged or explicitly deferred.
- Phase 1B config/governance split is merged.
- Phase 1C name registry decisions are merged.
- Phase 1D tools topology is merged.
- Phase 1E tests topology is merged.
- Phase 1F frontend source duplicate cleanup is merged.

## Phase 3A Baseline Rule

Do not take Phase 3A baselines until tests, tools, config, workspace paths, and
cache/build paths are stable. Otherwise baseline drift will hide real
regressions during Phase 5 and Phase 6.
