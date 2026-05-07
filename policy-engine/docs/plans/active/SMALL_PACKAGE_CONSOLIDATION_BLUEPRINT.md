---
title: Small Package Consolidation Blueprint
status: accepted-for-phase-4a
owner: team-architecture
created: 2026-05-03
last_verified: 2026-05-03
stability: draft
---

# Small Package Consolidation Blueprint

This is the Phase 3B planning deliverable for section 13 of
`docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md`.

Phase 3B authorizes zero physical source moves under `src/polisyos/`. It fixes
the ADR decisions, target owners, move maps, compatibility shims, tests,
rollback paths, and manifest updates that Phase 4A must implement.

## Phase 3B Decisions

| Weak package | Decision | Phase 4A action | Owner | Sunset |
| --- | --- | --- | --- | --- |
| `polisyos.ddm_15_7` | Rename to unversioned `polisyos.ddm`. | Copy package to `src/polisyos/ddm`, rewrite internal imports, leave wrapper-only `ddm_15_7` facade. | team-scientist, team-architecture | 2026-10-01 |
| `polisyos.packs` | Sunset, not formalize as an extension namespace. | Delete empty `packs/`, `packs/econ/`, and `packs/roads/`; remove architecture references. | team-architecture | none |
| `polisyos.synthetic_world` | Merge into Foundry agent simulation world namespace. | Move to `src/polisyos/foundry/agent_sim/world`; keep `synthetic_world` wrapper-only facade until sunset. | team-foundry | 2026-10-01 |
| `polisyos.calibration` | Keep as the canonical shared calibration diagnostics home. | Clarify shared API ownership; keep Foundry calibration as Foundry-specific parameter calibration; no package move. | team-scientist, team-foundry | none |
| `polisyos.berl` | Active Scientist support package, not legacy. | Document active role and keep only Scientist as an active consumer. | team-scientist | none |

Phase 4A touches `foundry/`, `agent_sim`, and shared `calibration`, so Phase 4A
must close before Phase 5/6 decomposition begins.

## Manifest Update Set

Phase 4A must update these architecture contracts in the same implementation
change as the source moves:

- `architecture/package_boundaries.toml`
- `architecture/import_contracts.toml`
- `architecture/public_surface.toml`
- `architecture/name_registry.toml`
- `architecture/shims.toml`
- generated public-surface reference docs and inventories

Phase 3B intentionally does not edit those manifests. They still describe the
pre-move tree until Phase 4A lands the source changes.

## Required Field Coverage

The detailed sections below cover every field required by Phase 3B:

| Weak package | Source path/FQN | Target path/FQN | Public surface impact | Dynamic import impact | Tests | Shim | Sunset | Rollback | Target owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ddm_15_7` | `src/polisyos/ddm_15_7`, `polisyos.ddm_15_7` | `src/polisyos/ddm`, `polisyos.ddm` | replace internal package entry with `polisyos.ddm`; keep compatibility facade | no direct dynamic target found | `tests/unit/ddm_15_7`, facade smoke, architecture | `ddm-15-7-rename` | 2026-10-01 | remove `ddm`, restore `ddm_15_7`, revert manifests | team-scientist |
| `packs` | `src/polisyos/packs`, `polisyos.packs` | none | remove architecture/import-contract references | no dynamic target found | architecture empty-placeholder checks | none | none | only with new extension ADR | team-architecture |
| `synthetic_world` | `src/polisyos/synthetic_world`, `polisyos.synthetic_world` | `src/polisyos/foundry/agent_sim/world`, `polisyos.foundry.agent_sim.world` | top-level package becomes compatibility facade; target is Foundry sub-surface | no direct dynamic target found | synthetic-world, agent-sim, integration, architecture | `synthetic-world-to-agent-sim-world` | 2026-10-01 | remove target, restore source implementation, revert manifests | team-foundry |
| `foundry/agent_sim` | `src/polisyos/foundry/agent_sim`, `polisyos.foundry.agent_sim` | unchanged; gains `world` child | remains ABM/RL facade; does not absorb all world exports at root | no direct dynamic target found | agent-sim, integration, architecture | none | none | remove `world` child if ADR-RSR-0138 is reopened | team-foundry |
| `calibration` | `src/polisyos/calibration`, `polisyos.calibration` | unchanged | canonical shared diagnostics API; Foundry calibration stays bounded-context | one Scientist dynamic import, unaffected | calibration, Foundry calibration, Scientist calibration-related, architecture | none | none | manifest/name-registry revert | team-scientist |
| `berl` | `src/polisyos/berl`, `polisyos.berl` | unchanged | active public-experimental Scientist support package | no dynamic target found | BERL, Scientist validation, architecture | none | none | open legacy ADR with migration target | team-scientist |

## `ddm_15_7` To `ddm`

ADR: `docs/adr/repository-structure-0135-versioning-out-of-package-names.md`

### Decision

`src/polisyos/ddm_15_7` becomes `src/polisyos/ddm`. The Python package name
must not carry the problem/version number. Schema IDs, YAML contract IDs, and
policy IDs containing `ddm_15_7` are compatibility identifiers rather than
Python package FQNs; Phase 4A should not rewrite them unless a separate ABI
migration is opened.

### Move Map

| Source path | Source FQN | Target path | Target FQN |
| --- | --- | --- | --- |
| `src/polisyos/ddm_15_7/README.md` | n/a | `src/polisyos/ddm/README.md` | n/a |
| `src/polisyos/ddm_15_7/__init__.py` | `polisyos.ddm_15_7` | `src/polisyos/ddm/__init__.py` | `polisyos.ddm` |
| `src/polisyos/ddm_15_7/calibration/` | `polisyos.ddm_15_7.calibration` | `src/polisyos/ddm/calibration/` | `polisyos.ddm.calibration` |
| `src/polisyos/ddm_15_7/contracts/` | resources under `polisyos.ddm_15_7.contracts` | `src/polisyos/ddm/contracts/` | resources under `polisyos.ddm.contracts` |
| `src/polisyos/ddm_15_7/detectors/` | `polisyos.ddm_15_7.detectors` | `src/polisyos/ddm/detectors/` | `polisyos.ddm.detectors` |
| `src/polisyos/ddm_15_7/integration/` | `polisyos.ddm_15_7.integration` | `src/polisyos/ddm/integration/` | `polisyos.ddm.integration` |
| `src/polisyos/ddm_15_7/readiness/` | `polisyos.ddm_15_7.readiness` | `src/polisyos/ddm/readiness/` | `polisyos.ddm.readiness` |

Phase 4A must rewrite all in-package imports from `polisyos.ddm_15_7.*` to
`polisyos.ddm.*`. Public support is the root facade only; deep
`polisyos.ddm_15_7.*` imports are internal and should migrate in tests and
first-party code.

### Public Surface Impact

`public_surface.toml` changes from:

- old: `polisyos.ddm_15_7`, `classification = "internal"`

to:

- new: `polisyos.ddm`, `classification = "internal"`
- compatibility: `polisyos.ddm_15_7`, wrapper-only shim until 2026-10-01

### Dynamic Import Impact

The Phase 3B grep audit found no dynamic import target for
`polisyos.ddm_15_7`. Phase 4A should still add `polisyos.ddm` and the shim FQN
to the Phase 3A dynamic-import registry if that registry exists by then.

### Shim

```toml
[[shim]]
id = "ddm-15-7-rename"
source_path = "src/polisyos/ddm_15_7"
target_path = "src/polisyos/ddm"
type = "wrapper_only"
reason = "Remove version/problem number from the Python package name."
owner = "team-architecture"
created = "2026-05-03"
sunset_date = "2026-10-01"
issue = "docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#ddm_15_7-to-ddm"
```

### Tests

Phase 4A/Phase 3.3 update:

- DDM behavior tests live under `tests/unit/ddm/**` and import `polisyos.ddm.*`
- package facade smoke tests to cover `import polisyos.ddm`
- `tests/unit/ddm_15_7/**` is collapsed to one shim smoke test for
  `import polisyos.ddm_15_7`
- architecture tests that still list `ddm_15_7` as an accepted package root

Suggested focused verification:

```bash
pytest tests/unit/ddm tests/unit/ddm_15_7 tests/repo_quality/architecture -q
```

### Rollback

Rollback is file-level: remove the new `src/polisyos/ddm/` copy, restore the
pre-Phase 4A `src/polisyos/ddm_15_7/` implementation from git, revert the
manifest replacements from `polisyos.ddm` to `polisyos.ddm_15_7`, and reopen
ADR-RSR-0135.

## `packs/` Sunset

ADR basis: ADR-RSR-0129 Empty Placeholder Package Policy

### Decision

`src/polisyos/packs/`, `src/polisyos/packs/econ/`, and
`src/polisyos/packs/roads/` are empty source namespaces. The only discovered
files are stale `__pycache__` artifacts. No first-party imports reference
`polisyos.packs`, and there is no extension contract defining how external
packs would register components.

Phase 3B chooses deletion over formalizing a user-contributed extension
namespace.

### Move Map

| Source path | Source FQN | Target path | Target FQN |
| --- | --- | --- | --- |
| `src/polisyos/packs/` | `polisyos.packs` namespace placeholder | none | none |
| `src/polisyos/packs/econ/` | `polisyos.packs.econ` namespace placeholder | none | none |
| `src/polisyos/packs/roads/` | `polisyos.packs.roads` namespace placeholder | none | none |

### Public Surface Impact

No `public_surface.toml` package entry exists for `polisyos.packs`. Phase 4A
must remove `polisyos.packs` from `package_boundaries.toml` and
`import_contracts.toml`.

### Dynamic Import Impact

The Phase 3B grep audit found no dynamic import target for `polisyos.packs`,
`polisyos.packs.econ`, or `polisyos.packs.roads`.

### Shim

No shim. A wrapper would keep an otherwise unused placeholder namespace alive
and would violate ADR-RSR-0129.

### Tests

Phase 4A must update architecture tests that list `packs` as an accepted
top-level package. It should add or extend an empty-placeholder test proving
there are zero source files under `src/polisyos/packs*` because the directories
are gone.

Suggested focused verification:

```bash
pytest tests/repo_quality/architecture -q
```

### Rollback

Recreate `src/polisyos/packs/{econ,roads}/` only if a real extension ADR is
accepted. Rollback must include an extension contract and tests; empty
directory restoration is not allowed.

## `synthetic_world` Into `foundry.agent_sim.world`

ADR: `docs/adr/repository-structure-0138-synthetic-world-agent-sim.md`

### Decision

Use Option A from the remediation plan: `polisyos.synthetic_world` migrates
under `polisyos.foundry.agent_sim.world`, and the top-level
`synthetic_world` package is freed after sunset.

Rationale:

- `foundry/agent_sim` is already the larger ABM/RL runtime owner.
- Legacy Foundry imports of `polisyos.synthetic_world` created a boundary smell;
  the Phase 3.4 collapse keeps first-party imports on the Foundry world target.
- Moving the smaller truth-centric world-generation package into the Foundry
  simulation owner creates one simulation/world responsibility instead of two
  competing top-level package roots.

### Move Map

| Source path | Source FQN | Target path | Target FQN |
| --- | --- | --- | --- |
| `src/polisyos/synthetic_world/README.md` | n/a | `src/polisyos/foundry/agent_sim/world/README.md` | n/a |
| `src/polisyos/synthetic_world/__init__.py` | `polisyos.synthetic_world` | `src/polisyos/foundry/agent_sim/world/__init__.py` | `polisyos.foundry.agent_sim.world` |
| `src/polisyos/synthetic_world/models.py` | `polisyos.synthetic_world.models` | `src/polisyos/foundry/agent_sim/world/models.py` | `polisyos.foundry.agent_sim.world.models` |
| `src/polisyos/synthetic_world/world.py` | `polisyos.synthetic_world.world` | `src/polisyos/foundry/agent_sim/world/world.py` | `polisyos.foundry.agent_sim.world.world` |
| `src/polisyos/synthetic_world/configs/` | resources under `polisyos.synthetic_world.configs` | `src/polisyos/foundry/agent_sim/world/configs/` | resources under `polisyos.foundry.agent_sim.world.configs` |
| `src/polisyos/synthetic_world/core/` | `polisyos.synthetic_world.core` | `src/polisyos/foundry/agent_sim/world/core/` | `polisyos.foundry.agent_sim.world.core` |
| `src/polisyos/synthetic_world/evaluators/` | `polisyos.synthetic_world.evaluators` | `src/polisyos/foundry/agent_sim/world/evaluators/` | `polisyos.foundry.agent_sim.world.evaluators` |
| `src/polisyos/synthetic_world/operators/` | `polisyos.synthetic_world.operators` | `src/polisyos/foundry/agent_sim/world/operators/` | `polisyos.foundry.agent_sim.world.operators` |
| `src/polisyos/synthetic_world/targets/` | `polisyos.synthetic_world.targets` | `src/polisyos/foundry/agent_sim/world/targets/` | `polisyos.foundry.agent_sim.world.targets` |
| `src/polisyos/synthetic_world/templates/` | `polisyos.synthetic_world.templates` | `src/polisyos/foundry/agent_sim/world/templates/` | `polisyos.foundry.agent_sim.world.templates` |
| `src/polisyos/foundry/agent_sim/` | `polisyos.foundry.agent_sim` | unchanged; gains `world/` child | `polisyos.foundry.agent_sim` plus `polisyos.foundry.agent_sim.world` |

Phase 3.4 verifies that first-party source and tests do not deep-import through
`polisyos.synthetic_world.*`; implementation imports use
`polisyos.foundry.agent_sim.world.*`.

### Public Surface Impact

`public_surface.toml` changes from:

- old: `polisyos.synthetic_world`, `classification = "public_experimental"`

to:

- new: `polisyos.foundry.agent_sim.world` as an experimental sub-surface under
  the Foundry package
- compatibility: `polisyos.synthetic_world`, wrapper-only shim until
  2026-10-01

The existing `polisyos.foundry.agent_sim` facade remains the low-level ABM/RL
runtime facade. It should not eagerly re-export every world symbol; the new
world surface is addressable as `polisyos.foundry.agent_sim.world`.

### Dynamic Import Impact

The Phase 3B grep audit found no dynamic import target for
`polisyos.synthetic_world` or `polisyos.foundry.agent_sim`. Static import
updates are required in first-party source, tests, benchmark docs, and reference
docs. Benchmark suite IDs such as `synthetic_world_seed` are not Python FQNs and
can remain stable unless a separate benchmark taxonomy migration is opened.

### Shim

```toml
[[shim]]
id = "synthetic-world-to-agent-sim-world"
source_path = "src/polisyos/synthetic_world"
target_path = "src/polisyos/foundry/agent_sim/world"
type = "wrapper_only"
reason = "Consolidate truth-centric world generation under the Foundry agent simulation owner."
owner = "team-foundry"
created = "2026-05-03"
sunset_date = "2026-10-01"
issue = "docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#synthetic_world-into-foundryagentsimworld"
```

The shim must preserve `import polisyos.synthetic_world` and root-facade
exports. Deep `polisyos.synthetic_world.*` imports are not stable public
surface; first-party tests and docs must migrate to the target FQNs.

### Tests

Phase 3.4 collapses compatibility coverage and keeps behavioral coverage on the
canonical Foundry path:

- `tests/unit/synthetic_world/test_shim.py` is the only compatibility smoke contract
- `tests/unit/foundry/agent_sim/world/test_seed_worlds.py` owns seed-world behavior
- `tests/performance/test_synthetic_world_seed_benchmark.py` only where Python
  import FQNs change
- `tests/integration/test_c7_synthetic_full_pipeline.py`
- first-party `foundry` validation imports that currently use
  `polisyos.synthetic_world`
- architecture tests and public-surface inventory snapshots

Suggested focused verification:

```bash
pytest tests/unit/synthetic_world tests/unit/foundry/agent_sim/world \
  tests/integration/test_c7_synthetic_full_pipeline.py tests/repo_quality/architecture -q
```

### Rollback

Rollback removes `src/polisyos/foundry/agent_sim/world/`, restores
`src/polisyos/synthetic_world/` as the implementation package, reverts manifest
updates, and reopens ADR-RSR-0138. No partial rollback may leave both
implementation packages active.

## Calibration Canonical Home

ADR: `docs/adr/repository-structure-0139-calibration-canonical-home.md`

### Decision

`polisyos.calibration` remains the canonical shared home for generic
calibration diagnostics, scoring, recalibration, and validation-report
adapters.

`polisyos.foundry.calibration` remains a Foundry-specific bounded context for
model-parameter calibration, measurement-aware loss, Hessian/UQ, robust-set
selection, and Foundry calibration artifacts. It may import shared generic
diagnostics from `polisyos.calibration`, but it must not duplicate or re-own the
generic diagnostics API.

There is no `src/polisyos/scientist/calibration/` package in the inspected
tree. Scientist calibration code currently lives in bounded modules such as
`scientist/autotune/calibration.py`, `scientist/backtesting/calibration_curve.py`,
`scientist/governance/calibration*.py`, and
`scientist/search/*calibration*.py`. Those modules remain Scientist-specific and
may import `polisyos.calibration` for generic diagnostics.

`polisyos.ddm_15_7.calibration` is handled by the `ddm` rename and becomes
`polisyos.ddm.calibration`; it is not part of the shared calibration API.

### Move Map

| Source path | Source FQN | Target path | Target FQN |
| --- | --- | --- | --- |
| `src/polisyos/calibration/` | `polisyos.calibration` | unchanged | `polisyos.calibration` |
| `src/polisyos/foundry/calibration/` | `polisyos.foundry.calibration` | unchanged | `polisyos.foundry.calibration` |
| `src/polisyos/scientist/calibration/` | absent | none | none |
| `src/polisyos/ddm_15_7/calibration/` | `polisyos.ddm_15_7.calibration` | `src/polisyos/ddm/calibration/` | `polisyos.ddm.calibration` |

### Public Surface Impact

`public_surface.toml` keeps `polisyos.calibration` as
`public_experimental`, with owner `team-scientist` and an explicit note that it
is the shared diagnostics/recalibration API.

`polisyos.foundry.calibration` remains documented under Foundry reference docs,
not as a new top-level public package. The shared directory name `calibration`
must be registered in `architecture/name_registry.toml` as an intentional
bounded-context name with:

- shared diagnostics owner: `polisyos.calibration`
- Foundry parameter-calibration owner: `polisyos.foundry.calibration`
- DDM drift-monitor calibration owner: `polisyos.ddm.calibration`
- Scientist orchestration calibration modules: package-specific, no package root

### Dynamic Import Impact

The Phase 3B grep audit found one dynamic import involving calibration:

- `importlib.import_module("polisyos.scientist.search.calibration_report")`

This target is Scientist-specific and is unaffected by the shared calibration
decision.

### Shim

No shim for `polisyos.calibration`; it does not move. The DDM calibration shim
is covered by `ddm-15-7-rename`.

### Tests

Phase 4A must keep these focused tests green:

- `tests/unit/calibration/**`
- `tests/unit/foundry/calibration/**`
- `tests/unit/scientist/**` calibration-related tests
- `tests/repo_quality/architecture/**` name-registry and public-surface checks

Suggested focused verification:

```bash
pytest tests/unit/calibration tests/unit/foundry/calibration \
  tests/unit/scientist/governance tests/unit/scientist/search tests/repo_quality/architecture -q
```

### Rollback

Because the shared package does not move, rollback is manifest-only: revert the
Phase 4A `public_surface.toml`, `package_boundaries.toml`, and
`name_registry.toml` calibration edits and reopen ADR-RSR-0139.

## `berl` Active Role

### Decision

`polisyos.berl` is active, not legacy. Its role is the Bounded Explanation
Reliability Layer for Scientist validation and explanation reliability:
contracts, adapters, metrics, perturbations, and orchestration. Scientist Phase
5 preflight imports it directly, and `tests/unit/berl/**` covers the package.

### Move Map

| Source path | Source FQN | Target path | Target FQN |
| --- | --- | --- | --- |
| `src/polisyos/berl/` | `polisyos.berl` | unchanged | `polisyos.berl` |

### Public Surface Impact

Keep `polisyos.berl` as `public_experimental` with owner `team-scientist`.
Phase 4A must clarify the active role in `src/polisyos/berl/README.md` and
public-surface notes. Do not set `legacy = true`, `frozen = true`, or
`migration_target`.

### Dynamic Import Impact

The Phase 3B grep audit found no dynamic import target for `polisyos.berl`.

### Shim

No shim; the package does not move.

### Tests

Phase 4A must keep:

- `tests/unit/berl/**`
- Scientist preflight tests that cover BERL validation
- package-boundary tests proving Scientist is the active consumer

Suggested focused verification:

```bash
pytest tests/unit/berl tests/unit/scientist/validation tests/repo_quality/architecture -q
```

### Rollback

If BERL is later reclassified as legacy, open a new ADR with a concrete
`migration_target`, set `legacy = true` and `frozen = true` in
`package_boundaries.toml`, add a shim if the target FQN changes, and migrate
Scientist preflight first.

## Phase 4A Execution Order

1. Apply the `ddm` rename and update DDM tests.
2. Delete `packs/` placeholders and remove manifest references.
3. Move `synthetic_world` into `foundry.agent_sim.world` and update Foundry
   imports/tests/docs.
4. Apply calibration manifest/name-registry clarifications.
5. Apply BERL active-role README/public-surface clarification.
6. Regenerate public-surface inventories and architecture baselines.
7. Run the focused verification commands above plus the Phase 3A safety gates
   if those gates exist in the branch.

## Phase 3B Completion Checklist

- [x] Blueprint exists and authorizes zero source moves.
- [x] `ddm_15_7` has exact target `ddm`, shim metadata, and facade-only smoke
  coverage.
- [x] `packs/` decision is deletion, not extension namespace.
- [x] `synthetic_world` has one chosen direction into
  `foundry.agent_sim.world`.
- [x] `calibration` has a canonical shared home.
- [x] `berl` is classified as active, not legacy.
- [x] Rollback and verification are specified per package.

## Phase 3B Verification Evidence

Phase 3B verification is documentation-only. Do not run Phase 4A migration
tests until the implementation phase moves source files.

Checks run on 2026-05-03:

```bash
rg -n "[ \t]+$" \
  docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md \
  docs/adr/repository-structure-0135-versioning-out-of-package-names.md \
  docs/adr/repository-structure-0138-synthetic-world-agent-sim.md \
  docs/adr/repository-structure-0139-calibration-canonical-home.md \
  docs/adr/index.md

git diff --check -- docs/adr/index.md

test ! -e src/polisyos/ddm
test ! -e src/polisyos/foundry/agent_sim/world
```

Observed result: no trailing whitespace, no diff-check errors in the touched
index, and no Phase 4A target source directories exist.
