---
title: Repository Best-In-Class Last-Mile Remediation Plan
status: superseded
owner: team-polisyos
created: 2026-05-07
last_verified: 2026-05-08
stability: archived
superseded_by: ../archive/2026-05-07-repository-best-in-class-last-mile-closeout.md
related:
  - ../archive/2026-05-07-repository-best-in-class-last-mile-closeout.md
  - ../archive/2026-05-07-repository-best-in-class-final-acceptance.md
  - ../archive/2026-05-07-repository-best-in-class-remediation-master-plan.md
  - ../../reference/repository-topology.md
  - ../../reference/scientist/index.md
  - ../../../architecture/packages/layout.toml
  - ../../../architecture/packages/scientist.toml
  - ../../../architecture/gates/package_import.toml
  - ../../../architecture/policies/directory_contracts.toml
  - ../../../architecture/policies/directory_health.toml
  - ../../../architecture/module_size_budget.toml
  - ../../../architecture/tests/ratchets.toml
  - ../../../architecture/name_registry.toml
  - ../../../architecture/shims.toml
  - ../../../architecture/policies/cross_cutting_concerns.toml
  - ../../../architecture/extension_points.toml
  - ../../../architecture/runbook_coverage.toml
  - ../../../architecture/component_observability.toml
---

# Repository Best-In-Class Last-Mile Remediation Plan

This plan closes the follow-up findings from the 2026-05-07 post-merge review
of the repository best-in-class program. The previous program moved the
repository from active remediation into a strong governed state; this plan
targets the remaining regressions and formal-only structures that still prevent
the repository from being genuinely best-in-class in day-to-day maintenance.

## Scope

This plan covers:

- `src/polisyos/scientist/**` root-facade regression, semantic duplicates, and
  legacy compatibility roots;
- `src/polisyos/fabric/**` and `src/polisyos/ir/**` single-file shell-package
  consolidation;
- `src/polisyos/ir/refs/**` versus `src/polisyos/ir/references/**` naming
  collision;
- completed compatibility shim sunset for the former `polisyos.ddm_15_7` and
  `polisyos.synthetic_world` roots;
- first real decomposition of the largest god modules, with shrinking
  line-count ratchets;
- mirror-ratio and integration-test ratchets that regressed after the package
  reshaping;
- repository hygiene cleanup for known local junk and redirect stubs;
- architecture gate organization so gate contracts do not remain split between
  root-level `architecture/*.toml` files and `architecture/gates/**`;
- cross-package name collisions and cross-cutting concern duplication;
- entry-point example completeness, ADR thematic indexing, operability bundle
  strictness, test-helper contracts, validator module-size budgets, and
  top-level `schemas/**` pure-data closure.

Out of scope:

- public product feature expansion;
- algorithmic rewrites that change causal, ingestion, Scientist, or Runtime
  behavior beyond the minimum needed for safe module splits;
- deleting public imports without a compatibility path, sunset, and smoke test;
- changing the accepted outer root policy or the `apps/` and `packages/`
  JavaScript workspace convention.

## Program Control Ledger

This ledger follows the remediation master-plan format: each finding has one
severity, one primary fence, one owner, one target wave, one rollback posture,
and at least one executable acceptance gate. Any phase that changes shared
registries, public import surfaces, package layout, test ratchets, or gate
contracts must update this ledger or the matching machine-readable contract in
the same change.

### Severity Labels

| Severity | Definition |
| --- | --- |
| P-Critical | Active structural regression, misleading green gate, unsafe public-surface drift, or blocker for best-in-class exit. |
| P-High | Maintainability or verification gap that can accumulate debt quickly if not closed in this program. |
| P-Medium | Important but bounded quality, integration, naming, or ownership gap. |
| P-Low | Cleanup, ergonomics, or local residue with low product risk but high audit noise. |

### Branch Naming Patterns

| Pattern | Intended fence | Typical phases |
| --- | --- | --- |
| `codex/last-mile-inventory-*` | inventories, reports, baselines | 0.1, 0.3 |
| `codex/last-mile-red-gates-*` | failing repo-quality tests and gate design | 0.2, 1.1 |
| `codex/last-mile-name-concerns-*` | name collision and cross-cutting concern inventories/contracts | 0.4, 1.5 |
| `codex/last-mile-scientist-*` | Scientist root facade, duplicates, parallel implementation audit, shims, tests | 1.2, 2.1, 2.2 |
| `codex/last-mile-shim-*` | compatibility shim removal or time-boxing | 2.3 |
| `codex/last-mile-fabric-*` | Fabric semantic grouping and tests | 3.1 |
| `codex/last-mile-ir-*` | IR semantic grouping, refs/references resolution, tests | 3.2, 3.3 |
| `codex/last-mile-*-godmodules-*` | package-owned module decomposition | 4.1, 4.2, 4.3 |
| `codex/last-mile-mirror-*` | mirror-ratio and property-test ratchets | 5.1 |
| `codex/last-mile-integration-*` | cross-layer integration tests and helper contracts | 5.2, 5.4, 5.5 |
| `codex/last-mile-examples-*` | entry-point example completeness | 1.6 |
| `codex/last-mile-architecture-*` | architecture taxonomy, gate lifecycle, and directory contracts | 6.1 |
| `codex/last-mile-schemas-*` | top-level schemas pure-data closure | 6.4 |
| `codex/last-mile-adr-*` | ADR thematic index | 6.5 |
| `codex/last-mile-operability-*` | component bundle completeness and exception expiry | 6.6 |
| `codex/last-mile-validator-budget-*` | validation tooling module-size ratchets | 6.7 |
| `codex/last-mile-stub-*` | redirect stubs, local residue, directory cleanup | 1.3, 1.4, 6.2 |
| `codex/last-mile-closeout-*` | final evidence and plan lifecycle closure | 7.1 |

Branch rule: no long-running branch may own a shared registry, lockfile,
workflow, generated inventory, or public-surface file as its primary work.
Those files are short queue-owned integration patches prepared after the
package-local or test-local change is already green.

### Remediation Dashboard

| Metric | Owner | Source report or contract | Baseline from review | Ratchet or closeout gate |
| --- | --- | --- | --- | --- |
| Scientist root loose `.py` count | team-scientist | last-mile inventory, `architecture/packages/scientist.toml` | 11 | Wave 2: 0 unregistered root implementation files |
| Fabric/IR shell-package count | team-fabric/team-ir | package import gate summary | 40 approximate shell packages | Wave 3: 0 unregistered single-file shell packages |
| IR unresolved sibling collisions | team-ir | `architecture/name_registry.toml` | `refs` plus `references` | Wave 3: 0 unresolved same-level collision findings |
| Cross-package name collisions | team-architecture | `architecture/name_registry.toml`, last-mile name inventory | governance/contracts/registry/calibration/runtime/trace/discovery candidates | Wave 1: every repeated name is scoped-OK, renamed, or merged |
| Cross-cutting concern duplication | team-architecture | `architecture/policies/cross_cutting_concerns.toml` | observability/security/registry/discovery duplicated across layers | Wave 1: canonical home plus adapter contract |
| Scientist parallel implementation pairs | team-scientist | last-mile parallel implementation inventory | workflows/orchestration/orchestrator/research_dag and related pairs | Wave 2: all pairs resolved or shimmed |
| Compatibility shim sunset debt | team-architecture | `architecture/shims.toml` | former `ddm_15_7`, `synthetic_world` | Closed: removed early after zero-noncompat caller audit |
| Shim caller pressure | team-architecture | `_build/.tmp/last-mile/shim_callers.json` | no caller report | Wave 0: every shim has callers list before sunset action |
| God-module shrinkage | owning package teams | `architecture/module_size_budget.toml` | six top modules above 3,900 lines plus validator-tool growth risk | Wave 4 and 6: top modules shrink and validator budgets are added |
| Mirror-test ratios | team-quality | `architecture/tests/ratchets.toml` | Scientist 56%, Fabric 35%, Foundry 67%, IR 52%, Core 40%, Runtime 69%, Data Forge 49%, Common 63%, DDM 41%, Berl 19%, Lex/Scholar 32% | Wave 5: improved floors with meaningful tests or registered exceptions |
| Integration bridge coverage | team-quality | `tests/integration/**`, test ratchets | sparse integration layer | Wave 5: nine cross-layer bridge tests |
| Test helper topology | team-quality | helper contract inventory | helper usage and conftest duplication unmeasured | Wave 5: helpers cannot import from test layers and duplicate conftests are registered |
| Entry-point example coverage | team-devx | `architecture/extension_points.toml`, `examples/extensions/**` | scientist governance pass lacks installable example | Wave 1: every public entry point has example or internal-only exception |
| Local residue | team-devx | directory health report | `_build/phase7-local-junk-20260505T092233Z/` | Wave 1: absent and future recurrence fails |
| Redirect stubs | team-docs/team-frontend | docs lifecycle, directory contracts | `frontend/`, legacy tests architecture redirect | Wave 6: removed or dated sunset |
| Top-level schemas purity | team-architecture | schema-only gate, directory contracts | audit reports Python/cache risk under `schemas/**` | Wave 6: no `.py`, `__init__.py`, or `__pycache__` under top-level `schemas/**` |
| ADR thematic index | team-docs | `docs/adr/index.toml`, `docs/adr/by-topic.md` | thematic navigation incomplete | Wave 6: generated by-topic index is fresh |
| Operability bundle completeness | team-ops | `ops/components/index.toml`, component bundles | exceptions exist and need expiry action | Wave 6: public-stable components have full bundles or non-expired actioned exceptions |
| Architecture taxonomy organization | team-architecture | `architecture/**` taxonomy index | gate TOMLs and concern-prefix TOMLs split across root/subdirs | Wave 6: no root TOML uses a prefix that has a subdir without documented exception |

Dashboard publication rule: every implementation wave updates the metric row it
changes with a measured value, evidence path, or dated owner exception.

## Review Baseline

Verified strengths from the prior program remain accepted and must not regress:

| Area | Baseline to preserve |
| --- | --- |
| Outer root | only Git/GitHub control plane plus `policy-engine/`; no root `renovate.json` |
| Static-analysis config | `mypy.ini`, `ruff.toml`, and `mkdocs.yml` stay thin wrappers over generated/tooling contracts |
| JavaScript workspace | active apps under `apps/`, shared packages under `packages/`, `frontend/` only as a dated redirect stub |
| Ops taxonomy | declarative operations under `ops/**`, executable runners under `tools/ops_runners/**` |
| Extension examples | six installable examples under `examples/extensions/**` stay green |
| Component operability | `ops/components/<component>/` bundle pattern stays the public-stable component model |
| Schemas | top-level `schemas/**` remains schema-only; Python wrappers live under `src/polisyos/schemas/**` |
| Tests data split | `tests/_data`, `tests/_golden`, and `tests/_helpers` remain separate review surfaces |

## Finding Ledger

Open regressions and debts from the post-merge review:

| ID | Severity | Finding | Primary fence | Owner | Target wave |
| --- | --- | --- | --- | --- | --- |
| LM-001 | P-Critical | `scientist/` root has 11 loose `.py` modules despite resolved root-facade status. | package source: Scientist | team-scientist | 2 |
| LM-002 | P-Critical | Fabric and IR contain many single-file shell packages that satisfy facade policy only formally. | package source: Fabric/IR | team-fabric, team-ir | 3 |
| LM-003 | P-Critical | `ir/refs` and `ir/references` are near-duplicate first-level names. | package source: IR | team-ir | 3 |
| LM-004 | P-High | `scientist/orchestrator` and `scientist/orchestration` coexist. | package source: Scientist | team-scientist | 2 |
| LM-005 | P-High | Scientist package/file semantic duplicates remain: `publishing`/`publisher.py`, `evidence`/`evidence_sources.py`, `feedback`/`feedback_utils.py`, `replay`/`replay_backend.py`, `llm`/`llm_cycle.py`. | package source: Scientist | team-scientist | 2 |
| LM-006 | Closed | Former `ddm_15_7` and `synthetic_world` wrappers were removed after zero-noncompat caller audit. | compatibility shims | team-architecture | closed |
| LM-007 | P-Critical | Large modules are ratcheted but not materially decomposed. | package source: Foundry/Data Forge/Scientist/Runtime | owning package teams | 4 |
| LM-008 | P-High | Mirror coverage regressed for Scientist, Fabric, Foundry, IR, and Core; Berl/Lex/Scholar remain low. | tests: mirror/property/integration | team-quality | 5 |
| LM-009 | P-Low | `_build/phase7-local-junk-20260505T092233Z/` remains as local residue. | lifecycle/output | team-devx | 1 |
| LM-010 | P-Low | Legacy tests architecture redirect is a redirect-only half-state. | tests: repo-quality | team-quality | 6 |
| LM-011 | P-Medium | `tests/integration/` does not cover cross-layer package bridges. | tests: integration | team-quality | 5 |
| LM-012 | P-Low | `frontend/` redirect stub lacks a sunset date. | frontend | team-frontend | 6 |
| LM-013 | P-Medium | `architecture/` still has gate files split across root-level TOML and `architecture/gates/**`. | architecture/contracts | team-architecture | 6 |
| LM-014 | P-Low | `data/policy-engine-local/` naming is odd after single-root closure and needs a role decision. | directory closure | team-data-forge | 6 |
| LM-015 | P-High | Cross-cutting concerns such as observability, security, registry, and discovery are duplicated without a canonical-home/adapters contract. | architecture/contracts | team-architecture | 1 |
| LM-016 | P-High | Scientist grew sharply and needs a full old/new parallel implementation audit beyond the known duplicate pairs. | package source: Scientist | team-scientist | 2 |
| LM-017 | P-High | Name registry needs a comprehensive audit for governance, contracts, registry, calibration, runtime, trace, discovery, and similar repeated names. | architecture/contracts | team-architecture | 0 |
| LM-018 | P-Medium | Public entry-point groups are not all backed by installable examples; Scientist governance pass lacks an example. | examples/extensions | team-devx | 1 |
| LM-019 | P-Low | ADR set needs a thematic index generated from `docs/adr/index.toml`. | docs: ADR lifecycle | team-docs | 6 |
| LM-020 | P-Medium | Public-stable operability bundles need full-file completeness and exception expiry action gates. | ops/components | team-ops | 6 |
| LM-021 | P-Medium | New validation tools can become god modules unless `tools/quality/validation/**` enters module-size budgets. | tools/quality | team-devx | 6 |
| LM-022 | P-High | Top-level `schemas/**` must be physically pure data and reject Python/cache residue. | schemas/data contracts | team-architecture | 6 |
| LM-023 | P-Medium | `tests/_helpers/**` and layer-local `conftest.py` files need a contract to prevent helper duplication and reverse imports. | tests: helpers | team-quality | 5 |
| LM-024 | P-High | Shim sunset policy lacks caller reports, so sunset dates can become formal rather than actionable. | compatibility shims | team-architecture | 0 |
| LM-025 | P-Low | Stale frontend path sweeps must cover the full repo, not only docs/tools/tests subsets. | frontend | team-frontend | 6 |
| LM-026 | P-Medium | Architecture taxonomy closure must cover all concern-prefixed TOML files, not only gate files. | architecture/contracts | team-architecture | 6 |

## Target State

### Maintainability

- Scientist root contains only root facade files and registered time-boxed
  compatibility shims; implementation lives under semantic subpackages.
- Fabric and IR first-level packages represent real semantic groups, not one
  package per old loose file.
- Ambiguous sibling names are either removed, aliased through dated shims, or
  documented as intentionally different bounded contexts.
- Architecture gates are discoverable under one gate lifecycle/index.
- Redirect stubs and compatibility wrappers have sunset dates and low-cost
  tests or are removed.

### Verifiability

- New gates catch single-file shell packages, loose root implementation modules,
  duplicate semantic package/file pairs, and undocumented redirect stubs.
- Mirror-ratio ratchets improve from the post-merge baseline instead of only
  preventing future collapse.
- Integration tests exercise real cross-layer behavior for Fabric, IR, Foundry,
  Scientist, Runtime, Core, Lex, Scholar, Berl, and Data Forge.
- God-module budgets prove actual shrinkage with characterization tests before
  and after every split.

### Extensibility

- Public import paths remain stable through explicit compatibility modules,
  re-export facades, or release-note deprecation windows.
- Extension examples keep using public registries, not private moved modules.
- Fabric and IR grouped packages expose coherent authoring docs, owner files,
  and package-local tests.

## Wave Execution Rule

The plan is wave-first. Waves are sequential. Phases inside the same wave are
parallel by default. If two phases need the same path fence, public facade,
shared registry, generated inventory, lockfile, or test helper, move one phase
to the next wave rather than adding an exception inside the current wave.

Each phase below contains scope, files, acceptance, and verification. This plan
is the execution surface; stable decisions must be copied into ADRs, reference
docs, and machine contracts before the plan closes.

## Parallel Safety Model

| Class | Work type | Parallel rule | Examples |
| --- | --- | --- | --- |
| C0 | inventory and metric capture | always parallel | shell-package inventory, mirror-ratio report |
| C1 | docs or contract-only changes | parallel by path owner | redirect sunset docs, gate TOML draft |
| C2 | source moves in one package with stable public imports | parallel with package smoke tests | Scientist `publisher.py` move, Fabric `trust` grouping |
| C3 | source moves sharing package `api.py`, `__init__.py`, shims, or public-surface inventory | parallel preparation, serialized merge | Scientist root facade closeout |
| C4 | shared registries and generated inventories | serialized queue | `architecture/shims.toml`, `architecture/name_registry.toml` |
| C5 | default branch, root policy, or workspace topology | singleton | not expected in this plan |

## Shared Registry Queues

| Queue | Files | Owner | Rule |
| --- | --- | --- | --- |
| package layout queue | `architecture/packages/layout.toml`, `architecture/packages/*.toml` | team-architecture | Short patches after package-local source moves. |
| shim queue | `architecture/shims.toml`, shim smoke tests, release notes | team-architecture | One shim family per patch. |
| name registry queue | `architecture/name_registry.toml`, collision docs | team-architecture | Collisions must be resolved or explicitly bounded. |
| cross-cutting concern queue | `architecture/policies/cross_cutting_concerns.toml`, layer adapter docs | team-architecture | Canonical-home changes merge before package-local adapters. |
| import/public surface queue | `architecture/imports/contracts.toml`, `architecture/public_surface*`, package `api.py` | team-architecture | Regenerate inventory once per wave. |
| test ratchet queue | `architecture/tests/ratchets.toml`, test topology reports | team-quality | Update baselines only with measured improvement or dated exception. |
| module budget queue | `architecture/module_size_budget.toml`, characterization reports | team-architecture | Every split lowers `current_lines` and `report_only_limit_lines`. |
| directory/gate queue | `architecture/policies/directory_contracts.toml`, `architecture/policies/directory_health.toml`, `architecture/gates/**` | team-architecture | Gate organization and new anti-pattern checks merge in small patches. |
| extension example queue | `architecture/extension_points.toml`, `pyproject.toml`, `examples/extensions/**` | team-devx | Example coverage patches must not mix with core package moves. |
| operability bundle queue | `ops/components/index.toml`, `ops/components/**` | team-ops | Bundle exception changes merge separately from release workflow changes. |
| architecture taxonomy queue | `architecture/**` path moves and taxonomy index | team-architecture | One subdir family per patch; update all path references in the same patch. |
| docs nav queue | `mkdocs.yml`, plan indexes, reference docs | team-docs | Navigation changes happen after source/doc paths exist. |

## Phase Fence Matrix

| Phase | Primary fence | Owner | Branch pattern |
| --- | --- | --- | --- |
| 0.1 Last-mile inventory | architecture/contracts | team-architecture | `codex/last-mile-inventory-*` |
| 0.2 Red gate design | architecture/contracts | team-quality | `codex/last-mile-red-gates-*` |
| 0.3 Import compatibility map | package source | team-architecture | `codex/last-mile-import-map-*` |
| 0.4 Cross-package name and concern audit | architecture/contracts | team-architecture | `codex/last-mile-name-concerns-*` |
| 1.1 Shell-package gate | architecture/contracts | team-architecture | `codex/last-mile-shell-package-gate-*` |
| 1.2 Scientist root gate | package source: Scientist | team-scientist | `codex/last-mile-scientist-root-gate-*` |
| 1.3 Hygiene cleanup | lifecycle/output | team-devx | `codex/last-mile-hygiene-*` |
| 1.4 Redirect-stub contract | directory closure | team-docs | `codex/last-mile-redirect-stubs-*` |
| 1.5 Cross-cutting concern canonical-home contract | architecture/contracts | team-architecture | `codex/last-mile-name-concerns-*` |
| 1.6 Entry-point example coverage gate | examples/extensions | team-devx | `codex/last-mile-examples-*` |
| 2.1 Scientist root facade moves | package source: Scientist | team-scientist | `codex/last-mile-scientist-facade-*` |
| 2.2 Scientist duplicate package/file resolution | package source: Scientist | team-scientist | `codex/last-mile-scientist-duplicates-*` |
| 2.3 Shim sunset execution | compatibility shims | team-architecture | `codex/last-mile-shim-sunset-*` |
| 3.1 Fabric semantic grouping | package source: Fabric | team-fabric | `codex/last-mile-fabric-grouping-*` |
| 3.2 IR semantic grouping | package source: IR | team-ir | `codex/last-mile-ir-grouping-*` |
| 3.3 IR refs/references resolution | package source: IR | team-ir | `codex/last-mile-ir-refs-*` |
| 4.1 Foundry god-module split | package source: Foundry | team-foundry | `codex/last-mile-foundry-godmodules-*` |
| 4.2 Data Forge god-module split | package source: Data Forge | team-data-forge | `codex/last-mile-data-forge-godmodules-*` |
| 4.3 Scientist/Runtime god-module split | package source: Scientist/Runtime | team-scientist/team-runtime | `codex/last-mile-runtime-scientist-godmodules-*` |
| 5.1 Mirror ratchet expansion | tests: mirror | team-quality | `codex/last-mile-mirror-ratchets-*` |
| 5.2 Integration bridge tests | tests: integration | team-quality | `codex/last-mile-integration-bridges-*` |
| 5.3 Shell-package move regression tests | tests: package coverage | team-fabric/team-ir | `codex/last-mile-low-coverage-*` |
| 5.4 Berl, Scholar, and Calibration bridge tests | tests: integration | team-quality | `codex/last-mile-integration-bridges-*` |
| 5.5 Test helper and conftest contract | tests: helpers | team-quality | `codex/last-mile-integration-bridges-*` |
| 6.1 Architecture taxonomy and gate re-home | architecture/contracts | team-architecture | `codex/last-mile-architecture-gates-*` |
| 6.2 Redirect and empty-stub cleanup | directory closure | team-docs | `codex/last-mile-stub-cleanup-*` |
| 6.3 Data root naming decision | directory closure | team-data-forge | `codex/last-mile-data-root-*` |
| 6.4 Schemas pure-data closure | schemas/data contracts | team-architecture | `codex/last-mile-schemas-*` |
| 6.5 ADR thematic index | docs: ADR lifecycle | team-docs | `codex/last-mile-adr-*` |
| 6.6 Operability bundle completeness gate | ops/components | team-ops | `codex/last-mile-operability-*` |
| 6.7 Validation tooling size budget | tools/quality | team-devx | `codex/last-mile-validator-budget-*` |
| 6.8 CI wiring for last-mile gates | CI/control plane | team-devx | `codex/last-mile-ci-wiring-*` |
| 7.1 Final verification | docs: closeout evidence | team-polisyos | `codex/last-mile-closeout-*` |

## Detailed Workstreams

### Wave 0 - Regression Inventory And Failing Contracts

Purpose: make the review findings executable before moving code. All phases are
C0/C1 and can run in parallel.

#### Phase 0.1 - Last-Mile Regression Inventory

Scope:

- Add or refresh an inventory command that reports:
  - package-root loose `.py` files by package;
  - first-level single-file shell packages;
  - semantic duplicate pairs such as `publishing` plus `publisher.py`;
  - near-duplicate sibling packages such as `refs` and `references`;
  - repeated cross-package first-level names and cross-cutting concern files;
  - Scientist parallel old/new package families;
  - top-level `schemas/**` Python/cache residue;
  - redirect-only directories and their sunset metadata;
  - local ignored residue matching known junk names.
- Persist a reviewed baseline under
  `architecture/baselines/repository_best_in_class_last_mile/`.

Files:

- Create:
  `tools/quality/validation/repository_last_mile_inventory.py`
- Create:
  `architecture/baselines/repository_best_in_class_last_mile/README.md`
- Create:
  `architecture/baselines/repository_best_in_class_last_mile/inventory.json`
- Test:
  `tests/repo_quality/tools/test_repository_last_mile_inventory.py`

Acceptance:

- Inventory reports LM-001 through LM-026 with path lists and counts.
- Inventory has zero false positives for generated/ignored directories.
- Inventory output includes enough machine-readable fields for later gates:
  `path`, `kind`, `owner`, `package`, `finding_id`, `suggested_target`,
  `current_status`, and `sunset` when applicable.

Verification:

```bash
uv run python tools/quality/validation/repository_last_mile_inventory.py --json-output _build/.tmp/last-mile/inventory.json
uv run pytest tests/repo_quality/tools/test_repository_last_mile_inventory.py -q
```

#### Phase 0.2 - Red Tests For New Anti-Patterns

Scope:

- Add failing repo-quality tests for each new gate before implementation:
  - undocumented loose root `.py` in Scientist fails;
  - single-file shell package fails unless it is an allowed facade or dated
    exception;
  - `ir/refs` plus `ir/references` fails as an unresolved collision;
  - redirect stub without `sunset_date` fails;
  - legacy tests architecture redirect without removal date fails;
  - known `_build/phase7-local-junk-*` residue fails hygiene checks.

Files:

- Modify:
  `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py`
- Modify:
  `tests/repo_quality/tools/test_directory_health.py`
- Modify:
  `tests/repo_quality/tools/test_docs_lifecycle.py`
- Modify:
  `tools/quality/validation/check_package_import_gates.py`
- Modify:
  `tools/quality/validation/directory_health.py`

Acceptance:

- Red tests fail against a synthetic temp repo that reproduces each problem.
- Current repository may still pass through registered exceptions until Waves
  2-3 remove the debt; new debt must fail immediately.

Verification:

```bash
uv run pytest tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py -q
uv run pytest tests/repo_quality/tools/test_directory_health.py -q
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py -q
```

#### Phase 0.3 - Public Import Compatibility Map

Scope:

- Build an import map for all planned source moves:
  - Fabric shell packages to be grouped;
  - IR shell packages to be grouped.
- Decide for each path whether it is removed, moved with a re-export shim, or
  retained with a dated exception.
- Generate `_build/.tmp/last-mile/shim_callers.json` with a per-shim list of
  first-party callers discovered through AST import scanning and text fallback
  for dynamic import strings.

Files:

- Modify:
  `architecture/shims.toml`
- Modify:
  `architecture/name_registry.toml`
- Modify:
  `architecture/public_surface/contract.toml`
- Modify:
  `architecture/imports/contracts.toml`
- Create:
  `tools/quality/validation/repository_last_mile_shim_callers.py`
- Create:
  `docs/archive/reports/REPOSITORY_BEST_IN_CLASS_LAST_MILE_IMPORT_MAP.md`
- Create:
  `_build/.tmp/last-mile/shim_callers.json`
- Test:
  `tests/repo_quality/architecture/test_last_mile_import_map.py`

Acceptance:

- Every planned move has one public compatibility decision.
- Every retained compatibility path has owner, reason, test, release note, and
  sunset.
- Every compatibility shim has a caller report with importer path, import kind,
  and migration target.
- Phase 2.3 may remove a shim only when caller count is zero or all remaining
  callers are examples/tests intentionally exercising compatibility.
- No package source move in Waves 2-4 starts without this map.

Verification:

```bash
uv run python tools/quality/validation/repository_last_mile_shim_callers.py --json-output _build/.tmp/last-mile/shim_callers.json --check
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/repo_quality/architecture/test_last_mile_import_map.py -q
uv run pytest tests/unit/scientist/methods/test_import_shims.py tests/unit/fabric/test_root_facade.py tests/unit/ir/test_root_facade_closeout.py -q
```

#### Phase 0.4 - Cross-Package Name And Concern Audit

Scope:

- Inventory all repeated first-level package names across `src/polisyos/**`,
  including governance, contracts, registry, calibration, runtime, trace,
  discovery, validation, observability, security, and extension names.
- Inventory cross-cutting concerns and all implementation locations for:
  observability, security, registry, discovery, configuration, tracing,
  telemetry, and calibration.
- Inventory Scientist parallel old/new implementation families beyond the
  known file/package pairs, especially:
  - `workflows` versus `orchestration` versus `orchestrator` versus
    `research_dag`;
  - `methods` versus legacy search/discovery/research roots;
  - `extensions` versus other package extension registries;
  - `governance`, `validation`, `verification`, and `policy_verified`.
- Classify each repeated name as `scoped_ok`, `rename`, `merge`,
  `canonical_home_with_adapters`, or `sunset_shim`.

Files:

- Create:
  `architecture/baselines/repository_best_in_class_last_mile/name_collisions.json`
- Create:
  `architecture/baselines/repository_best_in_class_last_mile/cross_cutting_concerns.json`
- Create:
  `architecture/baselines/repository_best_in_class_last_mile/scientist_parallel_implementations.json`
- Modify:
  `architecture/name_registry.toml`
- Modify:
  `architecture/policies/cross_cutting_concerns.toml`
- Test:
  `tests/repo_quality/architecture/test_last_mile_name_and_concern_inventory.py`

Acceptance:

- Every repeated first-level name has an explicit decision in
  `architecture/name_registry.toml` or a generated finding.
- Every cross-cutting concern has one proposed canonical home and adapter
  policy before Wave 1.5.
- Every Scientist parallel implementation candidate maps to Wave 2 move,
  merge, shim, or explicit non-overlap rationale.

Verification:

```bash
uv run python tools/quality/validation/repository_last_mile_inventory.py --json-output _build/.tmp/last-mile/inventory.json
uv run pytest tests/repo_quality/architecture/test_last_mile_name_and_concern_inventory.py -q
```

### Wave 1 - Guardrails, Hygiene, And Isolated Example Coverage

Purpose: install guardrails that prevent the same regression from returning
while product source moves are prepared. Phase 1.6 is intentionally included in
this wave because `examples/extensions/**` is an isolated extension-author fence
and its example-coverage gate must exist before source packages change. Phases
are parallel except shared registry patches.

#### Phase 1.1 - Shell-Package Anti-Pattern Gate

Scope:

- Extend package import gates with a semantic package rule:
  - first-level package directories with exactly one non-test implementation
    module must either be an allowed facade package, contain a local README that
    explains why the single module is intentional, or have a dated exception;
  - packages created only to wrap a formerly loose file are not allowed after
    Wave 3;
  - exceptions require owner, rationale, sunset, migration target, and smoke
    import test.
- Add configuration to `architecture/policies/directory_contracts.toml` and
  `architecture/gates/package_import.toml`.

Files:

- Modify:
  `tools/quality/validation/check_package_import_gates.py`
- Modify:
  `architecture/policies/directory_contracts.toml`
- Modify:
  `architecture/gates/package_import.toml`
- Test:
  `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py`

Acceptance:

- New single-file shell packages fail closed by default.
- Current Fabric/IR shell packages are either removed by Wave 3 or listed in a
  short exception table with sunset no later than 2026-07-31.
- Gate summary includes `single_file_shell_packages.finding_count`.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py -q
```

#### Phase 1.2 - Scientist Root-Facade Regression Gate

Scope:

- Update Scientist package contract so `resolved_root_facade` means the root
  contains only `__init__.py`, `api.py`, `_api.py`, registered shims, and dated
  package metadata exceptions.
- Add a Scientist-specific gate summary that reports:
  - root loose `.py` count;
  - canonical first-level root count;
  - compatibility shim root count;
  - duplicate package/file pair count.

Files:

- Modify:
  `architecture/packages/scientist.toml`
- Modify:
  `architecture/packages/layout.toml`
- Modify:
  `tools/quality/validation/check_package_import_gates.py`
- Test:
  `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py`

Acceptance:

- New Scientist root implementation files fail.
- Existing 11 files are listed as Wave 2 debt, not as permanent exceptions.
- `architecture/packages/scientist.toml` no longer overstates root-facade
  closure while those files remain.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
```

#### Phase 1.3 - Local Residue And Build Hygiene Cleanup

Scope:

- Delete local ignored junk matching `_build/phase7-local-junk-*` after
  verifying no committed evidence lives inside it.
- Add a hygiene gate that fails when known phase-junk roots exist.
- Keep committed evidence under `docs/archive/reports/**` and
  `architecture/baselines/**`; do not delete reviewed reports.

Files:

- Modify:
  `tools/devx/workspace/clean_local_reports.py`
- Modify:
  `tools/quality/validation/directory_health.py`
- Modify:
  `architecture/policies/directory_health.toml`
- Test:
  `tests/repo_quality/tools/test_directory_health.py`

Acceptance:

- `_build/phase7-local-junk-20260505T092233Z/` is absent locally.
- Directory health fails if a future `_build/phase*-local-junk-*` directory
  appears outside an explicitly ignored scratch policy.

Verification:

```bash
uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/last-mile/directory-health.json --markdown-output _build/.tmp/last-mile/directory-health.md --fail-on-regression
test ! -d _build/phase7-local-junk-20260505T092233Z
```

#### Phase 1.4 - Redirect Stub Sunset Contract

Scope:

- Require redirect-only directories to declare:
  - `sunset_date`;
  - owner;
  - target path;
  - reason;
  - removal gate.
- Apply the rule to `frontend/README.md` and legacy tests architecture README
  if either remains as a redirect stub during Wave 6.
- Use one sunset policy for redirect stubs: no redirect-only directory may live
  longer than 90 days from stub creation unless an ADR declares a longer
  compatibility window.

Files:

- Modify:
  `tools/quality/validation/check_docs_lifecycle.py`
- Modify:
  `architecture/policies/directory_contracts.toml`
- Modify:
  `frontend/README.md`
- Modify:
  legacy tests architecture README
- Test:
  `tests/repo_quality/tools/test_docs_lifecycle.py`

Acceptance:

- Redirect stubs without dates fail.
- `frontend/` and the legacy tests architecture redirect use the same 90-day sunset window or
  are removed in Wave 6.

Verification:

```bash
uv run python tools/quality/validation/check_docs_lifecycle.py --repo-root .
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py -q
```

#### Phase 1.5 - Cross-Cutting Concern Canonical-Home Contract

Scope:

- Define canonical homes for cross-cutting concerns:
  - observability and telemetry under `polisyos.core.observability` or
    `polisyos.common` if the inventory proves they are runtime-agnostic;
  - security under `polisyos.core.security`;
  - registry contracts under a canonical registry interface, with per-package
    registries documented as domain registries;
  - discovery under a canonical discovery interface or package-scoped names
    that avoid generic top-level duplication.
- Define the layer adapter contract:
  `<package>/_adapters/<concern>.py` may adapt package data to the canonical
  interface, but must import from the canonical home and must not define a
  competing top-level concern API.
- Add a gate that blocks new top-level loose files or first-level packages
  named after cross-cutting concerns outside the canonical home. The same gate
  also blocks group-level concern files such as
  `<package>/<group>/observability.py` unless they live under
  `<package>/_adapters/<concern>.py` or have an explicit scoped exception in
  `architecture/policies/cross_cutting_concerns.toml`.
- Record the canonical-home decision in an ADR before any package applies the
  adapter pattern.

Files:

- Modify:
  `architecture/policies/cross_cutting_concerns.toml`
- Modify:
  `architecture/name_registry.toml`
- Create:
  `docs/adr/repository-structure-0148-cross-cutting-concern-canonical-homes.md`
- Modify:
  `docs/adr/index.toml`
- Modify:
  `tools/quality/validation/check_package_import_gates.py`
- Test:
  `tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py`

Acceptance:

- Observability, security, registry, discovery, configuration, tracing, and
  calibration have canonical-home or scoped-OK decisions.
- ADR-0148 records the canonical-home decision and is indexed before package
  moves depend on it.
- New non-canonical `<concern>.py` root files and duplicate concern packages
  fail without an owner, rationale, and sunset.
- New group-level cross-cutting concern files outside
  `<package>/_adapters/**` fail unless explicitly scoped.
- Fabric and IR Wave 3 moves cannot introduce new cross-cutting concern roots.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py -q
```

#### Phase 1.6 - Entry-Point Example Coverage Gate

Scope:

- Require every public entry-point group declared in `pyproject.toml` and
  `architecture/extension_points.toml` to have one installable example under
  `examples/extensions/**` or an explicit `internal_only = true` exception.
- Add the missing Scientist governance pass example:
  `examples/extensions/scientist_governance_pass/`.
- Keep existing examples green:
  Fabric connector, Foundry method, Scientist node, Data Forge domain, Lex
  normpack, and Runtime middleware.

Files:

- Modify:
  `tools/quality/validation/check_extension_examples.py`
- Modify:
  `architecture/extension_points.toml`
- Create:
  `examples/extensions/scientist_governance_pass/pyproject.toml`
- Create:
  `examples/extensions/scientist_governance_pass/src/**`
- Create:
  `examples/extensions/scientist_governance_pass/tests/**`
- Test:
  `tests/repo_quality/tools/test_check_extension_examples.py`

Acceptance:

- Every public entry-point group has an installable example or a documented
  internal-only exception with owner and review date.
- `check_extension_examples.py` fails when a new public entry point lacks an
  example.

Verification:

```bash
uv run python tools/quality/validation/check_extension_examples.py
uv run pytest tests/repo_quality/tools/test_check_extension_examples.py -q
```

### Wave 2 - Scientist Root Facade And Shim Closure

Purpose: remove the Scientist root-facade regression and resolve Scientist
duplicate semantics. Phases can prepare in parallel but merge through the
package layout, shim, and public surface queues.

#### Phase 2.1 - Move Scientist Root Implementation Modules

Scope:

- Move root modules into semantic packages:
  - `decision_validity.py` -> `validation/decision_validity.py`;
  - `error_semantics.py` -> `orchestration/engine/error_semantics.py` or
    `validation/error_semantics.py` according to the import map;
  - `evidence_sources.py` -> `evidence/sources.py`;
  - `feedback_utils.py` -> `feedback/utils.py`;
  - `frontier_runtime.py` -> `orchestration/engine/frontier_runtime.py`;
  - `latent_separation.py` -> `methods/causal/latent_separation.py`;
  - `llm_cycle.py` -> `orchestration/llm/cycle.py`;
  - `publisher.py` -> `publishing/publisher.py`;
  - `reliability_scorecard.py` -> `validation/reliability_scorecard.py`;
  - `remediation_status.py` -> `governance/remediation_status.py`;
  - `replay_backend.py` -> `replay/backend.py`.
- Keep old import paths only as registered re-export shims if the import map
  requires compatibility.
- If any moved module needs observability, security, registry, discovery,
  tracing, configuration, telemetry, or calibration integration, use
  `scientist/_adapters/<concern>.py` and the Phase 1.5 canonical interface
  rather than introducing group-level concern files.

Files:

- Move:
  `src/polisyos/scientist/*.py` listed above
- Modify:
  `src/polisyos/scientist/api.py`
- Modify:
  `src/polisyos/scientist/__init__.py`
- Modify:
  `architecture/packages/scientist.toml`
- Modify:
  `architecture/packages/layout.toml`
- Test:
  `tests/unit/scientist/**`

Acceptance:

- Scientist root loose `.py` count is zero except allowed facade files and
  registered shims.
- Public imports identified in the import map still import successfully.
- No new Scientist package group contains cross-cutting concern implementation
  files outside `scientist/_adapters/**`.
- `architecture/packages/scientist.toml` can truthfully keep
  `layout.status = "resolved_root_facade"`.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/unit/scientist tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py -q
```

#### Phase 2.2 - Resolve Scientist Semantic Duplicate Roots

Scope:

- Remove or shim duplicate first-level roots:
  - `orchestrator/` -> `orchestration/orchestrator/`;
  - `continuous_governance/` -> `governance/continuous/`;
  - `human_review/` -> `governance/human_review/`;
  - `policy_verified/` -> `validation/policy_verified/`;
  - `verification/` -> `validation/verification/`;
  - `search/`, `discovery/`, and `research_dag/` -> `methods/search`,
    `methods/discovery`, and `methods/research_dag` with clear public
    compatibility decisions.
- Use the Phase 0.4 Scientist parallel implementation inventory to audit every
  first-level Scientist subpackage and close near-name pairs, triples, and
  quadruples before declaring the taxonomy done. At minimum, resolve or
  explicitly scope `workflows` versus `orchestration` versus `orchestrator`
  versus `research_dag`.
- Update Scientist docs so canonical groups and shim roots are visually and
  mechanically separate.

Files:

- Modify:
  `architecture/packages/scientist.toml`
- Modify:
  `architecture/shims.toml`
- Modify:
  `architecture/name_registry.toml`
- Modify:
  `docs/reference/scientist/index.md`
- Test:
  `tests/unit/scientist/methods/test_import_shims.py`

Acceptance:

- Scientist canonical first-level roots stay at or below 18.
- Compatibility roots are registered, sunset-dated, and smoke-tested.
- `orchestrator` and `orchestration` no longer coexist as active
  implementation roots.
- Every Scientist first-level old/new parallel implementation candidate from
  the Phase 0.4 inventory is resolved by move, merge, removal, sunset-dated
  shim, or scoped-OK decision with owner and non-overlap rationale.
- Classification-only entries fail closeout.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/unit/scientist/methods/test_import_shims.py tests/unit/scientist/orchestration -q
```

#### Phase 2.3 - Execute Or Tighten Compatibility Shim Sunsets

Scope:

Status: completed early; the former `polisyos.ddm_15_7` and
`polisyos.synthetic_world` root facades were removed after the caller report
showed no non-compatibility callers.

- Decide the release action for removed roots:
  - former `src/polisyos/ddm_15_7/__init__.py`;
  - former `src/polisyos/synthetic_world/__init__.py`.
- Remove a shim if no first-party imports remain and compatibility policy
  allows removal.
- Use `_build/.tmp/last-mile/shim_callers.json` as a precondition: a shim may
  be removed only when `callers` is empty or the remaining callers are examples
  and tests that intentionally verify compatibility.
- Otherwise, keep it only with:
  - owner;
  - sunset no later than 2026-07-31;
  - release note;
  - import smoke test;
  - migration target.

Files:

- Modify:
  `architecture/shims.toml`
- Modify:
  `docs/adr/repository-structure-0135-versioning-out-of-package-names.md`
- Modify:
  `docs/adr/repository-structure-0138-synthetic-world-agent-sim.md`
- Modify or delete:
  `src/polisyos/ddm_15_7/__init__.py`
- Modify or delete:
  `src/polisyos/synthetic_world/__init__.py`
- Test:
  `tests/unit/ddm/**`
- Test:
  `tests/unit/foundry/agent_sim/**`

Acceptance:

- No expired or undated compatibility shim remains.
- First-party imports use canonical packages.
- Shim caller reports are attached to the closeout evidence and every remaining
  caller has an owner and migration target.
- Release docs describe any still-supported compatibility import.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/unit/ddm tests/unit/foundry/agent_sim -q
```

### Wave 3 - Fabric And IR Semantic Package Consolidation

Purpose: replace formal shell packages with domain-shaped packages while
preserving public import compatibility.

#### Phase 3.1 - Fabric Semantic Grouping

Scope:

- Consolidate single-file shell packages into semantic groups:
  - `fabric/ingestion/{ingestion.py, ingestion_providers.py}`;
  - `fabric/connectors/ingestion/{connectors_ingestion.py}` so connector
    ingestion stays with the existing connector bounded context;
  - `fabric/trust/{trust.py, adapter.py}`;
  - `fabric/quality/{quality.py, fitness_report.py, processing_guarantees.py}`;
  - `fabric/evidence/{evidence.py, fact_writer.py, decision_data.py}`;
  - `fabric/identity/{manifest.py, segment_manifest.py}`;
  - `fabric/numerics/{finite.py}` only for numerical-stability helpers;
  - `fabric/data_plane/{tabular.py, temporal.py}` for shape/time semantics;
  - `fabric/config/{config.py}` only if the package has real config
    expansion or a dated single-module exception.
- Remove shell directories whose only purpose is wrapping an old loose file.
- Keep compatibility imports through documented re-export modules only when
  needed.
- Do not introduce group-level cross-cutting concern implementation files such
  as `fabric/<group>/observability.py`; Fabric adapters must live under
  `fabric/_adapters/<concern>.py` and import the canonical interface.

Files:

- Move:
  `src/polisyos/fabric/**`
- Modify:
  `src/polisyos/fabric/api.py`
- Modify:
  `architecture/packages/fabric.toml`
- Modify:
  `architecture/packages/layout.toml`
- Modify:
  `architecture/shims.toml`
- Test:
  `tests/unit/fabric/**`

Acceptance:

- Fabric has no unregistered single-file shell packages.
- Fabric root still contains only facade files.
- Fabric semantic groups contain no cross-cutting concern implementation files
  outside `fabric/_adapters/**`.
- Fabric package docs describe the semantic groups.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/unit/fabric tests/property/fabric tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py -q
```

#### Phase 3.2 - IR Semantic Grouping

Scope:

- Consolidate IR shell packages into semantic groups:
  - `ir/registry/{registry_fragments.py, refs.py, public_surface.py}`;
  - `ir/model_layer/{model_spec.py, canon.py, predicate.py, queries.py, types.py, units.py}`;
  - `ir/loading/{loaders.py, citations.py, migration_report.py, schema_catalog.py, fact_log.py, norm_pack.py, portfolio.py}`;
  - `ir/analytics/**` remains the analytics package;
  - `ir/schemas/**` remains schema wrapper code.
- Avoid creating `ir/contracts/**` unless `architecture/name_registry.toml`
  explicitly records `contracts` as a scoped-OK repeated package name with
  IR-specific semantics. Prefer `model_layer` to avoid overloading
  `core/contracts`, `foundry/contracts`, `ddm/contracts`, and `berl/contracts`.
- Remove shell directories whose only purpose is wrapping a single old module.
- Do not introduce group-level cross-cutting concern implementation files such
  as `ir/<group>/registry.py` or `ir/<group>/observability.py`; IR adapters
  must live under `ir/_adapters/<concern>.py` and import the canonical
  interface.

Files:

- Move:
  `src/polisyos/ir/**`
- Modify:
  `src/polisyos/ir/api.py`
- Modify:
  `architecture/packages/ir.toml`
- Modify:
  `architecture/packages/layout.toml`
- Modify:
  `architecture/shims.toml`
- Test:
  `tests/unit/ir/**`

Acceptance:

- IR has no unregistered single-file shell packages.
- IR root still contains only facade files.
- IR semantic groups contain no cross-cutting concern implementation files
  outside `ir/_adapters/**`.
- IR grouped package docs explain model layer, loading, registry, analytics, and
  schemas.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/unit/ir tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py -q
```

#### Phase 3.3 - Resolve `ir/refs` Versus `ir/references`

Scope:

- Choose one canonical concept:
  - `refs` for internal stable identifiers and edge references;
  - `references` only if it means bibliographic or external source references.
- If both concepts are real, place them under different semantic groups with
  explicit names such as `registry/refs.py` and `loading/citations.py`.
- If one concept is redundant, remove or shim it. `polisyos.ir.references` is
  retired and must not return as a physical semantic-group implementation file.

Files:

- Modify:
  `architecture/name_registry.toml`
- Modify:
  `architecture/packages/ir.toml`
- Move or remove:
  `src/polisyos/ir/refs/**`
- Move or remove:
  `src/polisyos/ir/references/**`
- Test:
  `tests/unit/ir/**`

Acceptance:

- No same-level `refs` and `references` collision remains.
- Name registry either has no entry for the collision or has a bounded,
  owner-approved explanation with no ambiguity.

Verification:

```bash
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run pytest tests/unit/ir -q
```

### Wave 4 - Material God-Module Decomposition

Purpose: turn module-size budgets into real smaller modules. Phases are
parallel by owning package because each phase touches different packages.

#### Phase 4.1 - Foundry Causal God-Module Splits

Scope:

- Split `foundry/methods/catalog/causal/causal_engine.py` into:
  - `causal_engine/discovery.py`;
  - `causal_engine/identification.py`;
  - `causal_engine/estimation.py`;
  - `causal_engine/sensitivity.py`;
  - `causal_engine/artifacts.py`;
  - `causal_engine/api.py`.
- Split `interference.py` and `id_engine.py` only along already characterized
  contracts from `_interference_contracts.py` and `_id_contracts.py`.
- Preserve the old public module imports through re-export modules until the
  shim window closes.

Files:

- Modify or move:
  `src/polisyos/foundry/methods/catalog/causal/causal_engine.py`
- Modify or move:
  `src/polisyos/foundry/methods/catalog/causal/interference.py`
- Modify or move:
  `src/polisyos/foundry/methods/catalog/causal/id_engine.py`
- Modify:
  `architecture/module_size_budget.toml`
- Test:
  `tests/unit/foundry/methods/catalog/causal/**`

Acceptance:

- `causal_engine.py` drops below 7,500 lines in the first split.
- `interference.py` drops below 3,500 lines.
- `id_engine.py` drops below 3,000 lines.
- No documented-blocker escape hatch is accepted for these two targets; if a
  full split is unsafe, split one crucial characterized path deeply enough to
  meet the target while preserving behavior.
- `module_size_budget.toml` lowers `current_lines`,
  `report_only_limit_lines`, and `next_ratchet_lines`.

Verification:

```bash
uv run pytest tests/unit/foundry/methods/catalog/causal -q
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
```

#### Phase 4.2 - Data Forge Ingest God-Module Splits

Scope:

- Split `data_forge/domains/catalog/batch/core_sources_ingest.py` into:
  - `core_sources/loaders.py`;
  - `core_sources/validators.py`;
  - `core_sources/transformers.py`;
  - `core_sources/registry.py`;
  - `core_sources/writers.py`;
  - `core_sources/api.py`.
- Split `academic/batch/resolve_extract.py` along the existing
  `_resolve_extract_contracts.py` boundary.

Files:

- Modify or move:
  `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py`
- Modify or move:
  `src/polisyos/data_forge/domains/academic/batch/resolve_extract.py`
- Modify:
  `architecture/module_size_budget.toml`
- Test:
  `tests/unit/data_forge/domains/catalog/batch/**`
- Test:
  `tests/unit/data_forge/domains/academic/batch/**`

Acceptance:

- `core_sources_ingest.py` drops below 6,000 lines.
- `resolve_extract.py` drops below 3,500 lines.
- Existing catalog and academic fixtures remain stable.

Verification:

```bash
uv run pytest tests/unit/data_forge tests/property/data_forge -q
uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/last-mile/test-ratchets.json --fail-on-regression
```

#### Phase 4.3 - Scientist Decision Packet And Runtime Control Splits

Scope:

- Split `scientist/nodes/builtins/decide/build_decision_packet.py` into:
  - `decision_packet/builder.py`;
  - `decision_packet/enrichment.py`;
  - `decision_packet/validation.py`;
  - `decision_packet/serialization.py`;
  - `decision_packet/api.py`.
- Split `runtime/http/services/control.py` into:
  - `control/admission.py`;
  - `control/run_lifecycle.py`;
  - `control/response_shapes.py`;
  - `control/artifacts.py`;
  - `control/api.py`.

Files:

- Modify or move:
  `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py`
- Modify or move:
  `src/polisyos/runtime/http/services/control.py`
- Modify:
  `architecture/module_size_budget.toml`
- Test:
  `tests/unit/scientist/nodes/builtins/decide/**`
- Test:
  `tests/unit/runtime/http/services/**`

Acceptance:

- `build_decision_packet.py` drops below 3,500 lines.
- `runtime/http/services/control.py` drops below 3,000 lines.
- Runtime OpenAPI and generated clients remain fresh.

Verification:

```bash
uv run pytest tests/unit/scientist/nodes/builtins/decide tests/unit/runtime/http/services -q
uv run python -m tools.devx.workspace.doctor
```

### Wave 5 - Test Mirror And Integration Uplift

Purpose: convert structural moves into real verification coverage. Phases can
run in parallel by package/test layer.

#### Phase 5.1 - Mirror-Ratio Ratchet Expansion

Scope:

- Raise measured mirror floors from the post-merge baseline:
  - Scientist: 56% -> at least 75% in this plan;
  - Fabric: 35% -> at least 50%;
  - Foundry: 67% -> at least 72%;
  - IR: 52% -> at least 60%;
  - Core: 40% -> at least 50%;
  - Runtime: 69% -> at least 75%;
  - Data Forge: 49% -> at least 60%;
  - Common: 63% -> at least 75%;
  - DDM: 41% -> at least 60%;
  - Berl: 19% -> at least 35% in this plan, with a 50% follow-up target;
  - Lex and Scholar: 32% -> at least 45% in this plan, with a 50% follow-up
    target.
- If a target cannot be reached in this plan, register a dated exception in
  `architecture/tests/ratchets.toml` with owner, affected paths, current ratio,
  added tests, and the next ratchet date.
- Do not raise a floor above measured reality; add tests first, then update
  `architecture/tests/ratchets.toml`.

Files:

- Modify:
  `architecture/tests/ratchets.toml`
- Add tests under:
  `tests/unit/{scientist,fabric,foundry,ir,core,runtime,data_forge,common,ddm,berl,lex,scholar}/**`

Acceptance:

- `report_test_ratchets.py --fail-on-regression` passes.
- Every raised package has at least one meaningful behavior or contract test,
  not only import smoke tests.

Verification:

```bash
uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/last-mile/test-ratchets.json --fail-on-regression
uv run pytest tests/unit/scientist tests/unit/fabric tests/unit/foundry tests/unit/ir tests/unit/core tests/unit/runtime tests/unit/data_forge tests/unit/common tests/unit/ddm tests/unit/berl tests/unit/lex tests/unit/scholar -q
```

#### Phase 5.2 - Cross-Layer Integration Tests

Scope:

- Add integration tests for real package bridges:
  - Fabric connector -> IR observation/schema surface;
  - Data Forge catalog fixture -> Fabric source contract -> Runtime API;
  - Foundry method registry -> Scientist node execution;
  - Runtime control service -> generated runtime API client fixture;
  - Lex normpack -> IR fact log -> Foundry method input;
  - Core security/config -> Runtime/Fabric service startup.

Files:

- Create:
  `tests/integration/fabric_ir/test_connector_observation_bridge.py`
- Create:
  `tests/integration/data_forge_runtime/test_catalog_to_runtime_bridge.py`
- Create:
  `tests/integration/foundry_scientist/test_method_node_bridge.py`
- Create:
  `tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py`
- Create:
  `tests/integration/lex_ir_foundry/test_normpack_factlog_method_bridge.py`
- Create:
  `tests/integration/core_runtime/test_config_security_startup_bridge.py`

Acceptance:

- Phase 5.2 contributes six real cross-layer scenarios.
- Together with Phase 5.4, the integration layer covers at least nine
  cross-layer scenarios including Berl, Scholar, and Calibration.
- Tests use `tests/_data`, `tests/_golden`, and `tests/_helpers` according to
  the fixture/golden/helper split.

Verification:

```bash
uv run pytest tests/integration -q
```

#### Phase 5.3 - Shell-Package Move Regression Tests

Scope:

- Add focused import and behavior tests for every Fabric and IR semantic group
  created in Wave 3.
- Add tests that old public paths either import with a deprecation warning or
  fail with a documented release removal, depending on the import map.

Files:

- Add:
  `tests/unit/fabric/test_semantic_group_imports.py`
- Add:
  `tests/unit/ir/test_semantic_group_imports.py`
- Modify:
  `tests/unit/fabric/test_root_facade.py`
- Modify:
  `tests/unit/ir/test_root_facade_closeout.py`

Acceptance:

- No Fabric/IR semantic group is testless.
- Compatibility behavior is explicit for every moved public path.

Verification:

```bash
uv run pytest tests/unit/fabric/test_semantic_group_imports.py tests/unit/ir/test_semantic_group_imports.py -q
```

#### Phase 5.4 - Berl, Scholar, And Calibration Bridges

Scope:

- Add integration tests for gaps not covered by Phase 5.2:
  - Scientist explanation reliability -> Berl validation;
  - Scholar search/discovery -> Scientist orchestration or research planning;
  - Foundry method output -> Calibration diagnostics.
- Keep each bridge small and deterministic. Use tiny fixtures from
  `tests/_data/**` and reusable helpers from `tests/_helpers/**`.

Files:

- Create:
  `tests/integration/scientist_berl/test_explanation_reliability_bridge.py`
- Create:
  `tests/integration/scholar_scientist/test_search_orchestration_bridge.py`
- Create:
  `tests/integration/foundry_calibration/test_method_calibration_bridge.py`
- Modify:
  `architecture/tests/ratchets.toml`

Acceptance:

- Berl, Scholar, and Calibration each have at least one real cross-layer
  integration bridge.
- Added tests fail if the bridge only imports modules without exercising a
  behavior or contract boundary.

Verification:

```bash
uv run pytest tests/integration/scientist_berl tests/integration/scholar_scientist tests/integration/foundry_calibration -q
```

#### Phase 5.5 - Test Helper And Conftest Contract

Scope:

- Inventory `tests/_helpers/**` and all layer-local `conftest.py` files.
- Persist a ratchet baseline with counts for shared helper files, layer-local
  `conftest.py` files, duplicated fixture factories, unused helpers, and
  forbidden reverse imports.
- Define what belongs in shared helpers versus layer-local fixtures:
  - `tests/_helpers/**` may import product code and standard test libraries;
  - `tests/_helpers/**` must not import from `tests/unit`, `tests/integration`,
    `tests/property`, `tests/contract`, or `tests/repo_quality`;
  - layer-local `conftest.py` files may import shared helpers but must not copy
    identical fixture factories without a local rationale.
- Add a gate that reports unused helpers, duplicated helper definitions, and
  forbidden reverse imports.

Files:

- Create:
  `architecture/baselines/repository_best_in_class_last_mile/test_helper_topology.json`
- Modify:
  `architecture/tests/ratchets.toml`
- Modify:
  `tools/quality/testing/report_test_ratchets.py`
- Create:
  `tests/repo_quality/tools/test_test_helper_contracts.py`

Acceptance:

- Shared helper contract is machine-checkable.
- Helper/conftest baseline counts are checked into the architecture baseline
  and future growth must be explained by a ratchet update.
- Duplicate conftest helpers are removed or registered with owner and reason.
- `tests/_helpers/**` has no reverse imports from concrete test layers.

Verification:

```bash
uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/last-mile/test-ratchets.json --fail-on-regression
uv run pytest tests/repo_quality/tools/test_test_helper_contracts.py -q
```

### Wave 6 - Repository Polish, Gate Organization, And Stub Cleanup

Purpose: remove half-states that are not core product source moves but still
weaken repository clarity.

#### Phase 6.1 - Architecture Taxonomy And Gate Re-Home

Scope:

- Move gate-specific root-level TOML files into `architecture/gates/**` or
  document why they remain top-level source contracts:
  - `repository_sota_gates.toml`;
  - `package_import_gates.toml`;
  - `compatibility_release_gates.toml`;
  - `operability_release_supply_chain_gates.toml`;
  - `structure_remediation_gates.toml`.
- Close the full architecture subdir taxonomy, not only gates:
  - package contracts under `architecture/packages/**`;
  - import contracts under `architecture/imports/**`;
  - public-surface contracts under `architecture/public_surface/**` or a
    documented top-level exception;
  - test contracts under `architecture/tests/**` if they outgrow a single
    top-level contract;
  - baselines under `architecture/baselines/**`;
  - tooling under `architecture/tooling/**`;
  - exceptions under `architecture/exceptions/**`;
  - policies under `architecture/policies/**`.
- Add a taxonomy rule: no top-level TOML file may use a prefix that already has
  a matching subdirectory unless the file is the canonical root contract for
  that domain and the exception is listed in the architecture index.
- Add `architecture/gates/README.md` and an index TOML that maps gate IDs to
  source contracts and commands.
- Keep top-level contracts only when they define repository-wide source of
  truth rather than a subdir family.

Files:

- Move or modify:
  `architecture/*gates*.toml`
- Move or modify:
  `architecture/{package_*,import_*,public_surface*,test_*,ops_baselines,cross_cutting_concerns,directory_*}.toml`
- Modify:
  `architecture/gates/README.md`
- Create or modify:
  `architecture/gates/index.toml`
- Create:
  `tests/repo_quality/architecture/test_architecture_taxonomy_closure.py`
- Modify:
  tools and tests that reference moved paths.

Acceptance:

- `architecture/` root-level TOML count is lower than the post-merge baseline.
- No gate source contract is referenced through a stale path.
- No top-level TOML file uses a prefix that has a same-named subdirectory
  without an explicit index exception.
- `polisyos-tools workspace tool-configs --check` remains green.

Verification:

```bash
uv run polisyos-tools workspace tool-configs --check
uv run pytest tests/repo_quality/architecture/test_architecture_taxonomy_closure.py tests/repo_quality -q
```

#### Phase 6.2 - Redirect And Empty Stub Cleanup

Scope:

- Remove the legacy tests architecture redirect if all references point to
  `tests/repo_quality/architecture/`.
- If `frontend/` remains as a redirect, keep only README and a dated sunset.
- Add search gates that fail stale direct references to removed stub paths.

Files:

- Delete or modify:
  legacy tests architecture README
- Modify:
  `frontend/README.md`
- Modify:
  `tools/quality/validation/check_docs_lifecycle.py`
- Test:
  `tests/repo_quality/tools/test_docs_lifecycle.py`

Acceptance:

- No empty redirect-only source/test directory remains without sunset.
- Stale references to the legacy tests architecture path and old frontend workspaces fail.

Verification:

```bash
uv run python tools/quality/validation/check_docs_lifecycle.py --repo-root .
cd /Users/deniskopylov/polisyos
legacy_tests="tests"/"architecture"
legacy_dashboard="frontend"/"runtime-dashboard"
legacy_client="frontend"/"runtime-api-client"
rg -n "${legacy_tests}|${legacy_dashboard}|${legacy_client}" --glob '!policy-engine/pnpm-lock.yaml' --glob '!policy-engine/**/package-lock.json' --glob '!policy-engine/**/node_modules/**' --glob '!policy-engine/docs/plans/active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md' . && exit 1 || true
```

#### Phase 6.3 - Data Root Naming Decision

Scope:

- Decide whether `data/policy-engine-local/` should be renamed, removed, or
  explicitly documented as a local-data legacy path.
- Update data placement contracts so the name does not contradict the
  single-root product policy.

Files:

- Modify:
  `architecture/policies/directory_contracts.toml`
- Modify:
  `architecture/asset_placement.toml`
- Modify or move:
  `data/policy-engine-local/**`
- Add:
  `docs/adr/repository-structure-0147-data-root-local-state-naming.md` if the
  path remains.

Acceptance:

- Data root naming is either canonical or has an ADR-backed exception.
- No source or fixture code assumes the confusing path name without a contract.

Verification:

```bash
uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/last-mile/directory-health.json --markdown-output _build/.tmp/last-mile/directory-health.md --fail-on-regression
```

#### Phase 6.4 - Schemas Pure-Data Closure

Scope:

- Ensure top-level `schemas/**` contains only JSON Schema, OpenAPI, YAML/TOML
  manifests, generated schema snapshots, and schema documentation.
- Remove any `schemas/__init__.py`, `schemas/*.py`, or `schemas/**/__pycache__`
  residue if present locally.
- Keep Python schema wrappers only under `src/polisyos/schemas/**`.
- Tighten the schema-only gate so future `.py`, `__init__.py`, `__pycache__`,
  or product imports under top-level `schemas/**` fail closed.

Files:

- Modify:
  `architecture/policies/directory_contracts.toml`
- Modify:
  `architecture/topology.toml`
- Modify:
  `tools/quality/validation/check_package_import_gates.py`
- Modify:
  `tools/quality/validation/directory_health.py`
- Delete if present:
  `schemas/__init__.py`
- Delete if present:
  `schemas/abi_models.py`
- Delete if present:
  `schemas/**/__pycache__`
- Test:
  `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py`

Acceptance:

- `find schemas -name '*.py' -o -name '__pycache__'` returns no paths.
- Top-level schemas gate fails for any Python code or cache residue.
- `src/polisyos/schemas/abi_models.py` remains the Python wrapper location.

Verification:

```bash
find schemas \( -name '*.py' -o -name '__pycache__' \) -print | tee _build/.tmp/last-mile/schemas-python-residue.txt
test ! -s _build/.tmp/last-mile/schemas-python-residue.txt
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
```

#### Phase 6.5 - ADR Thematic Index

Scope:

- Generate `docs/adr/by-topic.md` from `docs/adr/index.toml`.
- Group ADRs into stable topics such as repository structure, observation,
  security, runtime state, schemas, testing, release, frontend, and product
  domain.
- Add a freshness test that fails when `docs/adr/index.toml` and
  `docs/adr/by-topic.md` disagree.

Files:

- Modify:
  `tools/quality/validation/generate_adr_index.py`
- Modify:
  `docs/adr/index.toml`
- Create or refresh:
  `docs/adr/by-topic.md`
- Test:
  `tests/repo_quality/tools/test_generate_adr_index.py`

Acceptance:

- ADR thematic index is generated, linked from ADR README/index, and fresh.
- New ADRs without topic classification fail the generator or docs lifecycle
  gate.

Verification:

```bash
uv run python tools/quality/validation/generate_adr_index.py --check
uv run pytest tests/repo_quality/tools/test_generate_adr_index.py -q
```

#### Phase 6.6 - Operability Bundle Completeness Gate

Scope:

- Require every `public_stable` component in `ops/components/index.toml` to
  have a complete bundle:
  `README.md`, `alerts.yml`, `dashboard.json`, `retention-policy.toml`,
  `runbooks.md`, `runtime-contract.toml`, and `slo.yaml`.
- Track exceptions with owner, reason, expiration date, and action plan.
- Fail expired exceptions and public-stable components missing required files.

Files:

- Modify:
  `architecture/runbook_coverage.toml`
- Modify:
  `architecture/component_observability.toml`
- Modify:
  `tools/ops_runners/release/check_operability_release_gates.py`
- Modify:
  `ops/components/index.toml`
- Test:
  `tests/repo_quality/tools/test_operability_release_gates.py`

Acceptance:

- Public-stable component bundles are complete or have non-expired, actioned
  exceptions.
- Every existing exception expires at least 90 days after the plan completion
  target or has an explicit action plan due inside the plan window.
- `slo_status = "exception"` cannot persist past its expiration without a
  failing gate.

Verification:

```bash
uv run python tools/ops_runners/release/check_operability_release_gates.py --json-output _build/.tmp/last-mile/operability-release-gates.json --fail-closed
uv run pytest tests/repo_quality/tools/test_operability_release_gates.py -q
```

#### Phase 6.7 - Validation Tooling Size Budget

Scope:

- Add `tools/quality/validation/**` and related report generators to
  `architecture/module_size_budget.toml` before they become new god modules.
- Set warning and fail-closed ratchets for:
  - `check_package_import_gates.py`;
  - `directory_health.py`;
  - `check_docs_lifecycle.py`;
  - `repository_last_mile_inventory.py`;
  - `check_extension_examples.py`;
  - `architecture_report_only_contracts.py`.
- Default thresholds are warning at 1,000 logical code lines and fail-closed at
  2,000 logical code lines. Files already above the warning threshold must use
  a pinned baseline, may not grow, and must carry an extraction sequence with
  owner and target date.
- Require new validation scripts above the threshold to declare extraction
  sequence and owner before merge.

Files:

- Modify:
  `architecture/module_size_budget.toml`
- Modify:
  `tools/quality/validation/architecture_report_only_contracts.py`
- Test:
  `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py`

Acceptance:

- Validation tooling has module-size ratchets.
- Each listed validator has either a `warning = 1000` / `fail_closed = 2000`
  budget or a pinned per-file baseline with a no-growth ratchet.
- No new validation script above the configured threshold can grow silently.

Verification:

```bash
uv run python tools/quality/validation/architecture_report_only_contracts.py --report module-size --json-output _build/.tmp/last-mile/module-size.json --fail-on-contract-errors
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
```

#### Phase 6.8 - CI Wiring For Last-Mile Gates

Scope:

- Wire every new last-mile validator into the contributor and PR paths:
  `repository_last_mile_inventory.py`, `check_extension_examples.py`,
  `generate_adr_index.py`, `architecture_report_only_contracts.py`, schema
  purity checks, operability bundle checks, shell-package checks, helper
  topology checks, and cross-cutting/name-collision gates.
- Add the gates to the correct level:
  - lightweight fail-fast checks in `workspace verify`;
  - broad repository policy checks in `workspace ci-parity`;
  - release/operability checks in acceptance or release workflows;
  - authored-file hooks in `.pre-commit-config.yaml` only when they are fast
    and deterministic.
- Prove CI parity: any gate required for final acceptance is either called from
  `.github/workflows/**` directly or reachable through a documented
  `polisyos-tools workspace verify`, `ci-parity`, or `repository-sota-closeout`
  path that the workflow invokes.

Files:

- Modify from workspace root:
  `.github/workflows/**`
- Modify:
  `.pre-commit-config.yaml`
- Modify:
  `tools/devx/workspace/verify.py`
- Modify:
  `tools/devx/workspace/ci_parity.py`
- Modify:
  `tools/devx/workspace/repository_sota_closeout.py`
- Modify:
  `docs/reference/quality-gates.md`
- Test:
  `tests/repo_quality/tools/test_workspace_ci_parity.py`

Acceptance:

- Every new last-mile gate has one explicit CI or CLI owner.
- `polisyos-tools workspace verify` and `polisyos-tools workspace ci-parity`
  document which last-mile gates they run.
- No final-acceptance-only validator exists solely in Phase 7.1 without CI,
  CLI, or pre-commit coverage.

Verification:

```bash
uv run polisyos-tools workspace verify --backend-only --skip-doctor
uv run polisyos-tools workspace ci-parity --skip-browser
uv run pytest tests/repo_quality/tools/test_workspace_ci_parity.py -q
```

### Wave 7 - Final Verification And Program Close

Purpose: prove the last-mile work is closed in committed state, not only by
green local commands.

#### Phase 7.1 - Final Last-Mile Acceptance Evidence

Scope:

- Create an archive report with:
  - Scientist root facade final inventory;
  - Fabric/IR semantic group inventory;
  - shell-package gate result;
  - cross-package name and cross-cutting concern decision table;
  - Scientist parallel implementation audit closeout;
  - collision resolution table;
  - shim caller report and sunset/removal table;
  - god-module line-count before/after table;
  - mirror-ratio before/after table;
  - integration-test bridge inventory;
  - test-helper/conftest contract evidence;
  - schemas pure-data evidence;
  - entry-point example coverage table;
  - ADR thematic index freshness;
  - operability bundle completeness table;
  - architecture taxonomy and gate organization inventory;
  - local hygiene evidence.
- Move this plan to archive or accepted according to docs lifecycle rules after
  implementation is complete.

Files:

- Create:
  `docs/plans/archive/2026-05-07-repository-best-in-class-last-mile-closeout.md`
- Modify:
  `docs/plans/active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md`
  only to archive or supersede it through the lifecycle.

Acceptance:

- Worktree is clean after commits.
- No new acceptance-owned file is untracked.
- All gates below pass in fail-closed or contract-error mode.

Verification:

```bash
uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json
uv run python tools/quality/validation/repository_last_mile_inventory.py --json-output _build/.tmp/last-mile/inventory.json
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/last-mile/directory-health.json --markdown-output _build/.tmp/last-mile/directory-health.md --fail-on-regression
uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/last-mile/test-ratchets.json --fail-on-regression
uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/last-mile/dead-overrides.json
uv run python tools/quality/validation/check_extension_examples.py
uv run python tools/quality/validation/generate_adr_index.py --check
uv run python tools/quality/validation/architecture_report_only_contracts.py --report module-size --json-output _build/.tmp/last-mile/module-size.json --fail-on-contract-errors
uv run python tools/ops_runners/release/check_operability_release_gates.py --json-output _build/.tmp/last-mile/operability-release-gates.json --fail-closed
uv run python tools/ops_runners/release/check_compatibility_release_gates.py --json-output _build/.tmp/last-mile/compatibility-release-gates.json --fail-on-contract-errors
uv run polisyos-tools workspace acceptance-audit --json-output _build/.tmp/last-mile/platform-acceptance.json --summary _build/.tmp/last-mile/platform-acceptance.md
uv run python -m tools.devx.workspace.doctor
uv run pytest tests/contract -q
uv run pytest tests/repo_quality -q
uv run pytest tests/integration -q
corepack pnpm install --frozen-lockfile
corepack pnpm -r --workspace-concurrency=1 --if-present run build
corepack pnpm -r --workspace-concurrency=1 --if-present run test
```

Schema purity check from `/Users/deniskopylov/polisyos/policy-engine`:

```bash
find schemas \( -name '*.py' -o -name '__pycache__' \) -print | tee _build/.tmp/last-mile/schemas-python-residue.txt
test ! -s _build/.tmp/last-mile/schemas-python-residue.txt
```

Final root checks from `/Users/deniskopylov/polisyos`:

The only committed outer-root paths allowed are `.github/**`, `.gitignore`,
`.gitattributes`, `.editorconfig`, and `policy-engine/**`. Local directories
such as `.git/`, `.cursor/`, and `.claude/` may exist on disk, but they must not
be represented as committed repository paths.

```bash
test ! -f renovate.json
test -f .github/renovate.json
git ls-files | awk '!/^policy-engine\// && !/^\.github\// && $0 !~ /^\.(editorconfig|gitattributes|gitignore)$/ {print; bad=1} END {exit bad}'
git ls-files policy-engine | rg '(^|/)(_build|_cache|__pycache__|node_modules|\.venv|\.polisyos|tmp)/|\.pyc$|\.DS_Store$|egg-info' && exit 1 || true
git status --porcelain=v1
```

## Final Acceptance Criteria

The last-mile program exits only when:

- Scientist root facade policy is true in source and contract, with zero
  unregistered root implementation modules.
- Scientist duplicate package/file pairs are removed, merged, or registered as
  sunset-dated compatibility shims.
- `scientist/orchestrator` and `scientist/orchestration` do not coexist as
  active implementation roots.
- The Scientist +55% growth concern is closed by a comprehensive old/new
  implementation audit; every close-named pair/triple/quadruple is resolved,
  scoped, or sunset-dated.
- Fabric and IR have no unregistered single-file shell packages.
- `ir/refs` and `ir/references` are resolved into one canonical concept or
  separated under clearly named semantic groups.
- Cross-package name collisions for governance, contracts, registry,
  calibration, runtime, trace, discovery, observability, and security are
  either scoped-OK in `architecture/name_registry.toml` or renamed/merged.
- Cross-cutting concerns have canonical homes and per-layer adapter contracts;
  non-canonical duplicate concern roots fail gates.
- No package group introduces group-level cross-cutting concern files outside
  `<package>/_adapters/**` or an explicit scoped exception.
- Former `polisyos.ddm_15_7` and `polisyos.synthetic_world` roots are removed.
- Every remaining shim has a caller report; sunset dates are backed by caller
  migration evidence.
- The top seven god modules have material line-count reductions and lowered
  ratchets; no god module can grow silently.
- Validation tooling has module-size budgets so new gates do not become
  unbounded god modules.
- Validation tooling budgets use warning/fail-closed thresholds or pinned
  no-growth baselines with extraction owners.
- Mirror-ratio baselines improve for Scientist, Fabric, Foundry, IR, Core,
  Runtime, Data Forge, Common, DDM, Berl, Lex, and Scholar according to Wave 5
  or carry dated exceptions in `architecture/tests/ratchets.toml`.
- `tests/integration/` contains real cross-layer bridge tests, not only a
  placeholder layer, including Scientist-Berl, Scholar-Scientist, and
  Foundry-Calibration bridges.
- `tests/_helpers/**` and layer-local `conftest.py` files obey a helper
  contract and have no reverse imports from concrete test layers.
- Known local junk under `_build/phase7-local-junk-*` is absent and future
  recurrence fails hygiene gates.
- Redirect-only stubs such as `frontend/` and the legacy tests architecture redirect are removed
  or carry the shared 90-day sunset metadata.
- Top-level `schemas/**` contains schemas and manifests only; no `.py`,
  `__init__.py`, `__pycache__`, or product imports remain there.
- Every public entry-point group has an installable example or an explicit
  internal-only exception.
- ADRs have a generated thematic index that is fresh against
  `docs/adr/index.toml`.
- Public-stable operability component bundles are complete or have
  non-expired, actioned exceptions.
- Existing operability exceptions expire at least 90 days after the plan
  completion target or have an action plan due inside the plan window.
- Gate contracts and architecture TOML families have one discoverable
  lifecycle/index under the architecture taxonomy or a documented exception.
- Every new last-mile validator is wired into CI, `workspace verify`,
  `workspace ci-parity`, `repository-sota-closeout`, or a fast pre-commit hook.
- Every remaining report-only item has owner, rationale, evidence path, and
  target fail-closed date.
- Final close evidence is committed, and the worktree has no acceptance-owned
  untracked or unstaged changes.
