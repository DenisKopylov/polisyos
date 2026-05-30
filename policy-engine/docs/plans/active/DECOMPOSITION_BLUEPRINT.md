---
title: Decomposition Blueprint
status: accepted
adr: ADR-0143
owner: team-scientist/team-foundry
created: 2026-05-03
last_verified: 2026-05-03
stability: phase-3a-baseline
---

# Decomposition Blueprint

This is the accepted Phase 3A plan-first artifact for scientist/foundry decomposition.
It authorizes no physical `.py` moves in `src/polisyos/scientist/` or
`src/polisyos/foundry/`; it only freezes contracts for Phase 5/6.

## ADR-0143 Decision

- Phase 5/6 may start only after all Phase 3A gates are green.
- Current audited counts are 12 Scientist non-facade root modules and 28 Foundry
  non-facade root modules. These counts supersede older draft text that mentioned
  17/22 modules.
- Every old source FQN gets a targeted Python re-export shim; star imports in shims
  are forbidden by ADR-0144.
- Shim sunset arithmetic: max(60 days, 2 x max workflow lifetime) = 1170 days.
  Draft sunset date for Phase 5/6 shims: created + 1170 days.

## Move Map

| Source FQN | Target FQN | Type | Reasoning |
| --- | --- | --- | --- |
| `polisyos.foundry._quickstart` | `polisyos.foundry._internal.quickstart` | internal | Default internal bucket. |
| `polisyos.foundry._registry` | `polisyos.foundry._internal.registry` | internal | Default internal bucket. |

## External Importers

### `polisyos.foundry._quickstart`
- `src/polisyos/foundry/README.md:97` (literal_fqn)
- `tests/repo_quality/tools/test_docs_gate.py:202` (literal_fqn)
- `tests/unit/foundry/facade/test_quickstart.py:8` (literal_fqn)
- `tests/unit/foundry/runtime/test_execute_feedback.py:25` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py:774` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py:1380` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_grand_tournament_v2.py:1627` (literal_fqn)

### `polisyos.foundry._registry`
- `src/polisyos/foundry/calibration/pure_executor.py:23` (literal_fqn)
- `src/polisyos/foundry/compile/_lowering.py:17` (literal_fqn)
- `src/polisyos/foundry/execute/_internal/graph/__init__.py:35` (literal_fqn)
- `src/polisyos/foundry/execute/api.py:50` (literal_fqn)
- `src/polisyos/foundry/extensions/registry.py:147` (literal_fqn)
- `src/polisyos/foundry/methods/catalog/mechanism/runtime.py:131` (literal_fqn)
- `tests/unit/foundry/methods/test_foundry_v2_unified_runtime.py:4` (literal_fqn)
- `tools/research/demos/run_mechanism_design.py:34` (literal_fqn)

## Planned Re-export Shims

| Shim FQN | Target FQN | Shape | Draft sunset |
| --- | --- | --- | --- |
| `polisyos.foundry._quickstart` | `polisyos.foundry._internal.quickstart` | targeted names only | created + 1170 days |
| `polisyos.foundry._registry` | `polisyos.foundry._internal.registry` | targeted names only | created + 1170 days |

## Pydantic Models And Runtime API Schema Usage

No Pydantic models were found in planned move files.

## JAX/Pydantic Top-level Registrations

- No JAX/Pydantic top-level registrations were found in planned move files.

## Pickle And Checkpoint Inventory

- Call sites: 21
- Live artifacts: 2
- Canonical fixtures: `tests/_data/checkpoint_compat`

## Dynamic Imports

- Registered dynamic import patterns: 180
- Registry: `architecture/imports/dynamic.toml`

## Import Cycles

- Modules in scientist/foundry graph: 1173
- Edges in graph: 3423
- Pre-existing lazy SCCs: 14
- Allowed lazy cycles are frozen in `architecture/imports/lazy.toml`.
- The baseline graph records the collector mode; this workspace uses the internal
  deterministic AST graph because `pydeps`/`import-linter` are not required dev
  dependencies here.

## Baselines

- `architecture/baselines/structure_remediation/import_graph_pre_decomp.json`
- `architecture/baselines/structure_remediation/import_time_pre_decomp.json`
- `architecture/baselines/structure_remediation/pickle_checkpoint_inventory.json`
- `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`
- `architecture/baselines/structure_remediation/schema_diff_pre_decomp.json`
- `architecture/baselines/structure_remediation/tests_baseline.txt`

`tests_baseline.txt` intentionally records a deferred full-suite baseline:
the local `pytest tests/unit tests/integration tests/property tests/contract tests/repo_quality -q`
run was not completed because of thermal load on the laptop. The full baseline
must be run in cloud infrastructure during the final Phase 7 closeout; it is
not a local Phase 3A prerequisite.

## Phase 5/6 Entry Criteria

- `dynamic_imports_gate` green.
- `pickle_compat_gate` green.
- `public_surface_snapshot_gate` green.
- `import_cycles_gate` green.
- `import_time_regression_gate` green in live CI mode.
- `reexport_shim_shape_gate` green.
- Full-suite baseline remains explicitly deferred to the Phase 7 cloud closeout.
- No `.py` files in `src/polisyos/scientist/` or `src/polisyos/foundry/` moved during Phase 3A.
