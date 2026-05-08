---
title: Repository Best-In-Class Remediation Master Plan
status: archived
owner: team-polisyos
created: 2026-05-05
last_verified: 2026-05-07
stability: final
related:
  - docs/plans/active/REPOSITORY_STRUCTURE_REMEDIATION_CONCURRENCY.md
  - docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md
  - docs/plans/active/IR_AUDIT_REMEDIATION_PLAN.md
  - docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md
  - docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md
  - docs/plans/active/FRONTEND_SOTA_PLAN.md
  - docs/plans/active/INFRASTRUCTURE_SOTA_PLAN.md
  - docs/plans/active/DOCUMENTATION_SOTA_PLAN.md
  - docs/plans/active/TOOLS_AUDIT_REMEDIATION_PLAN.md
  - docs/plans/active/REPOSITORY_LIFECYCLE_AND_OPS_TAXONOMY_DECISION.md
  - docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md
  - architecture/topology.toml
  - architecture/packages/layout.toml
  - architecture/tests/topology.toml
  - architecture/tests/ratchets.toml
  - architecture/name_registry.toml
  - architecture/policies/cross_cutting_concerns.toml
  - architecture/local_runtime_state.toml
---

# Repository Best-In-Class Remediation Master Plan

This plan is the comprehensive execution roadmap for turning PolicyOS from a
strong but actively remediating repository into a best-in-class, simple to
maintain, simple to extend, and simple to operate codebase.

It consolidates the latest structural, verifiability, maintainability,
extensibility, and operability audit findings into a parallel implementation
program. It intentionally treats repository structure as product architecture:
layout, names, tests, runtime state, generated artifacts, release process, and
operability evidence are all part of the system contract.

## Scope

This plan covers:

- outer repository control plane and `policy-engine/` product root;
- `architecture/**` machine-readable governance;
- `src/polisyos/**` package layout and dependency boundaries;
- compatibility shims and migration sunset policy;
- `tests/**`, `benchmarks/**`, fixtures, golden data, and performance lanes;
- `apps/**`, `packages/**`, and pnpm workspace topology;
- `tools/**`, `ops/**`, release, migration, and generated-artifact workflows;
- `schemas/**` code/data separation;
- `.polisyos/**` local runtime-state schema and retention;
- docs, plans, ADR indexing, runbook mapping, and operational bundles;
- CI quality gates and ratchet policy.

Out of scope:

- large product feature expansion unrelated to repository health;
- semantic rewrites of domain algorithms unless needed to split god modules;
- deleting public APIs without a shim, sunset, and migration window;
- moving GitHub-native control-plane files that must live at repository root.

## Audit Baseline

The plan starts from the following high-confidence observations verified on
2026-05-05:

| Area | Current state | Risk |
| --- | --- | --- |
| Product root | outer git root wraps `policy-engine/`; product topology says `policy-engine` is canonical | tool and CI drift |
| Outer root residue | `_cache/ruff`, `tmp/phase3a_*`, root `renovate.json` | false root signals |
| Package facades | `fabric/` and `ir/` still have many root `.py` implementation modules | policy drift |
| Foundry executor | `_executor_*` and `_execution_posture` live as siblings of executor surfaces | unclear private ownership |
| Foundry methods | `foundry/methods` has 352 Python files and several loose implementation roots | catalog sprawl |
| Scientist | 40+ first-level subpackages with close semantic duplicates | cognitive load |
| Name collisions | governance, contracts, registry, runtime, trace, calibration, discovery, observability, security appear in multiple contexts | unclear canonical contracts |
| Release/generated output | committed release inputs and ignored build outputs are easy to confuse | release SoT drift |
| Test topology | `test_topology.toml` exists but mostly enforces hubs, not mirror ratios or data/helper separation | weak ratchet |
| Fixtures/golden data | fixture helpers, data, and tests are mixed under `tests/fixtures` and `tests/contract` | review noise |
| Benchmarks | `benchmarks/` is source-like with pytest config and runner code | unclear product vs test role |
| JS workspace | apps and libraries are mixed under `frontend/`; `packages/cli` is separate | weak monorepo convention |
| Tool config | `mypy.ini`, `ruff.toml`, and `mkdocs.yml` are large root-level monoliths | hidden maintenance tax |
| Schemas | `schemas/` mixes JSON/YAML contracts with Python code and cache residue | import-path fragility |
| Ops/tools | `tools/ops_runners/**` and `ops/**` share names but not a declared taxonomy | contributor confusion |
| Runtime state | `.polisyos/` is ignored and partially classified but lacks a full schema and CAS nesting | operator confusion |
| Extension points | only two Python entry-point groups exist despite many plugin-like internal catalogs | weak extensibility |
| Examples | `examples/` has only one demo | poor extension author path |
| Operability | SLO and runbook coverage exist for some components only | production ownership gaps |
| Module size | several files exceed 4K lines; one exceeds 10K lines | slow review and refactor risk |
| Repository control plane | root CODEOWNERS and rulesets exist, but root-decision work can stale path prefixes and logical owner coverage | review-routing drift |
| Import boundaries | `package_boundaries.toml` is strong, but boundary drift needs explicit no-regression and deep-import budgets | hidden coupling |
| Versioning policy | current shims handle known versioned packages, but future Python package names, schemas, extension contracts, and release semantics need one policy | ABI confusion |
| Supply chain | SBOM and security scanners exist, but provenance, permissions, required checks, and release identity should be tied to the topology | release trust gaps |
| Directory contract gaps | several high-volume subtrees lack local authoring contracts, and root/subtree policies are scattered across topology, package, docs, and tests contracts | future layout drift |
| Non-product Python package roots | `benchmarks`, `tools`, `tests`, and `schemas` contain `__init__.py` files outside `src/polisyos`; `schemas` is already slated for code/data split, but the others need explicit role contracts | import ambiguity |
| Local residue surfaces | ignored `__pycache__`, `.DS_Store`, egg-info, `_reports`, `node_modules`, local data, and empty fixture/cache directories appear across many subtrees | noisy audits |
| Product fixture assets | committed fixture/domain data lives inside `src/polisyos/data_forge/**/fixtures`, while test fixture data lives under tests | unclear data ownership |
| Frontend subtree contracts | `apps/runtime-dashboard/src/shared/ui`, `src/api`, `src/features`, and `src/test` are large enough to need local ownership and testing topology | UI maintenance drift |

## Target State

### Maintainability

- One product root is visible to people, CI, tools, docs, and generated-artifact
  contracts.
- Every source, generated, cache, runtime, release, and fixture path has one
  owner and one lifecycle.
- Active packages obey a uniform root-facade policy.
- Large packages have internal taxonomies that match domain boundaries.
- God modules are either split or explicitly ratcheted with shrinking budgets.
- Cross-cutting concerns expose canonical interfaces and per-layer adapters.
- Tooling overrides are reviewable, grouped, and automatically checked for
  dead paths.
- Package dependency boundaries and public-surface boundaries are ratcheted,
  not merely documented.
- Ownership and repository rulesets route review to the right people after each
  structural move.
- Every top-level directory and every high-volume subtree has a declared role,
  allowed child kinds, lifecycle, local README/index requirement, and closure
  gate.

### Extensibility

- External contributors can extend Foundry methods, Scientist nodes, Data Forge
  domains, Lex norm packs, Fabric connectors, governance passes, and Runtime
  middleware through versioned entry points.
- Internal builtins are loaded through the same registration pathway as external
  plugins.
- Examples are installable packages and run in CI.
- Extension contracts have version, deprecation, and ABI compatibility metadata.
- Versioned contracts use schema/API/extension metadata, not Python package
  names.

### Operability

- Every public-stable component has an SLO, runbook mapping, alert/dashboard
  mapping, runtime-state contract, and release/deploy ownership.
- `.polisyos/` has a human-readable schema and machine-readable layout.
- Migrations cover DB, runtime-state formats, IR schemas, and API schemas.
- Release promotion has explicit topology and promotion gates.
- Runtime generated artifacts have freshness, retention, and restore rules.
- Release artifacts carry SBOM/provenance expectations and least-privilege CI
  identity rules.

### Verifiability

- Test topology enforces both directory presence and mirror-ratio ratchets.
- Fixtures, helpers, golden data, benchmarks, and product contracts have
  separate review surfaces.
- Non-source Python roots are intentional and documented; accidental importable
  roots are removed.
- Property-test decisions are explicit for every package, with ratchets for
  Fabric, Lex, and Data Forge.
- Architecture gates fail closed after a measured report-only period.
- Required CI checks are mapped to changed path classes, not only global habit.

## Execution Principles

1. Root decision first. Path cleanup before deep code moves.
2. Contracts before physical moves. Every structural move needs a move map,
   import inventory, shim policy, tests, and rollback note.
3. Maximize parallelism by owning disjoint path sets.
4. Serialize shared registries through short patches.
5. Prefer ratchets over impossible big-bang thresholds.
6. Keep public imports stable while internals move.
7. Separate source, generated output, cache, runtime state, and test data.
8. Delete local junk only after retention and ignore policy are explicit.
9. No silent broad rename across semantically different bounded contexts.
10. Exit each wave with executable verification, not just documentation.

## Shared Registry Serialization Queue

These files are cross-program shared registries. They must be edited through
short serialized patches, never long-running parallel branches:

- `architecture/topology.toml`
- `architecture/packages/layout.toml`
- `architecture/packages/boundaries.toml`
- `architecture/public_surface/contract.toml`
- `architecture/public_surface/inventory.json`
- `architecture/imports/contracts.toml`
- `architecture/name_registry.toml`
- `architecture/policies/cross_cutting_concerns.toml`
- `architecture/shims.toml`
- `architecture/generated_artifacts.toml`
- `architecture/imports/dynamic.toml`
- `architecture/tests/topology.toml`
- `architecture/frontend_workspaces.toml`
- `architecture/local_runtime_state.toml`
- `pyproject.toml`
- `pnpm-workspace.yaml`
- `pnpm-lock.yaml`
- `mkdocs.yml`
- `mypy.ini`
- `ruff.toml`
- `.github/CODEOWNERS`
- `.github/repository-rulesets/main.yml`
- `.github/workflows/**`
- `ops/security/**`

Rule: phases may prepare local notes, generated inventories, or draft
snippets, but merge only small registry patches after the owning source move or
contract change is ready.

## External Practice Alignment

This remediation program uses repository-local contracts as the source of truth,
but it should stay aligned with external practices that are stable and broadly
adopted:

- Python package layout follows PyPA guidance: keep importable code under
  `src/` so editable installs and regular installs expose the same intended
  package surface.
- Python plugin discovery should prefer explicit entry-point metadata for
  extension contracts, with namespace packages used only when the namespace
  policy is deliberately documented.
- Pytest topology should keep tests outside application code for large suites,
  prefer installed/editable package testing, and avoid surprising `sys.path`
  behavior.
- Test data and temporary output should use pytest temporary-path semantics or
  explicit committed fixture/golden-data directories, not ad hoc scratch paths.
- GitHub CODEOWNERS and branch/ruleset protections should be treated as the
  enforceable repository control plane for owned review and required checks.
- SLOs should be defined as targets over measured SLIs that users care about,
  not as arbitrary metric inventories.
- OpenTelemetry semantic conventions should drive cross-component telemetry
  naming so logs, metrics, traces, resources, and profiles use common names.
- Ruff and MkDocs split/config work should respect each tool's real config
  discovery and path-resolution rules rather than inventing wrapper semantics
  that behave differently by working directory.
- pnpm workspace work should use a single workspace root, `workspace:` protocol
  for local package links where appropriate, and cycle checks for workspace
  dependencies.
- Supply-chain controls should map to SLSA-style provenance expectations, SBOM
  freshness, signed release artifacts, least-privilege workflow permissions,
  and short-lived machine identity where supported.

Reference inputs:

- PyPA src layout: <https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/>
- PyPA plugin discovery: <https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/>
- PyPA entry points: <https://packaging.python.org/en/latest/specifications/entry-points/>
- pytest good integration practices: <https://docs.pytest.org/en/7.4.x/explanation/goodpractices.html>
- pytest temporary paths: <https://docs.pytest.org/en/7.4.x/how-to/tmp_path.html>
- GitHub CODEOWNERS: <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners>
- GitHub protected branches: <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches>
- Google SRE SLOs: <https://sre.google/sre-book/service-level-objectives/>
- OpenTelemetry semantic conventions: <https://opentelemetry.io/docs/concepts/semantic-conventions/>
- Ruff configuration: <https://docs.astral.sh/ruff/configuration/>
- MkDocs configuration: <https://www.mkdocs.org/user-guide/configuration/>
- pnpm workspaces: <https://pnpm.io/workspaces>
- SLSA security levels: <https://slsa.dev/spec/v1.0/levels>

## Wave Execution Rule

The execution plan is wave-first. Phases inside the same wave are parallel by
default. If two phases cannot safely run in parallel because they share a path
fence, registry queue, lockfile, public facade, or ownership boundary, one of
them moves to the next wave instead of becoming an exception inside the current
wave.

The wave plan in `Detailed Workstreams` is the only execution surface. All
scope, acceptance criteria, and sequencing detail must live inside the relevant
wave phase. Do not add a second reference layer.

## Parallel Safety Model

Actual parallelism is controlled by risk class, path ownership, and
shared-registry queues. The wave rule above decides scheduling; the safety rules
below decide whether a phase belongs in the current wave or must move later.

This section refines the older
`docs/plans/active/REPOSITORY_STRUCTURE_REMEDIATION_CONCURRENCY.md` phase
contract. If that contract and this master plan disagree, use the stricter rule
until a short ADR or plan update resolves the conflict. In particular, any
parallel Scientist/Foundry physical moves require the per-path ownership fences,
shim policy, and shared-registry queues below; otherwise the historical
Scientist-before-Foundry barrier remains the safe default.

### Risk Classes

| Class | Work type | Parallel rule | Examples |
| --- | --- | --- | --- |
| C0 | inventory, metrics, read-only reports | always parallel | module-size inventory, mirror-ratio report, CODEOWNERS coverage report |
| C1 | docs/contracts without shared registries | parallel by path owner | README drafts, package-local AUTHORING docs, runbook drafts |
| C2 | source moves in disjoint packages with stable public imports | parallel with package smoke tests | Fabric facade move and IR facade move |
| C3 | source moves that share public imports, shims, or test helpers | parallel preparation, serialized merge | Scientist taxonomy lanes touching `scientist/api.py`; Foundry registry and methods discovery |
| C4 | shared registries, lockfiles, generated-artifact command maps, workflow/ruleset files | serialized through the matching queue | `architecture/shims.toml`, `pyproject.toml`, `pnpm-lock.yaml`, CODEOWNERS |
| C5 | root topology, workspace root, or default-branch protection changes | singleton merge window | product-root decision, repository ruleset replacement |

Rule: maximize C0-C2 work. Treat C3 as parallel branch preparation with a short
integration patch. Treat C4-C5 as single-writer merge windows.

### Hard And Soft Blockers

| Blocker | Hard-blocks | Does not block |
| --- | --- | --- |
| Phase 1.1 product root decision | physical root/workspace moves, CODEOWNERS path-prefix rewrites, JS app/package relocation | inventories, draft contracts, package-local README work |
| Phase 1.3 architecture report-only contracts | fail-closed gates and source moves that rely on new contracts | report-only baselines, local move maps |
| Phases 3.3-3.4 shim policy | deleting or expiring shims | first-party import inventories and shim-test collapse planning |
| Phase 1.4 test contract | test directory moves and fail-closed mirror-ratio gates | source characterization tests placed in current test topology |
| Phase 2.7 JS workspace move | additional physical `frontend`/`apps`/`packages` moves | frontend subtree inventories and component ownership docs |
| Phase 6.1 import-boundary ratchets | fail-closed deep-import or cycle gates | source moves that preserve public imports and run report-only checks |
| Phase 1.8 directory contracts | fail-closed directory closure gates | local README drafts and residue inventories |

### Ownership Fences

Every implementation branch must declare one primary fence:

- root/control plane: outer root, `.github/**`, root workflows, rulesets;
- architecture/contracts: `architecture/**` machine-readable governance,
  report-only gates, exception registries, and generated contract inventories;
- lifecycle/output: `_build`, `_cache`, `release`, `release-fragments`,
  generated-artifact manifests;
- tools/ops_runners: `tools/**`, `ops/**`, runner paths, operation contracts;
- runtime state: `.polisyos/**`, runtime-state layout and cleanup tools;
- schemas/data contracts: `schemas/**`, schema snapshots, API contracts, and
  schema code/data separation;
- package source: exactly one package family such as `fabric`, `ir`, `foundry`,
  `scientist`, `runtime`, `data_forge`, or `core`;
- tests: one test topology slice such as repo-quality, fixtures/golden,
  package mirror tests, property tests, or benchmarks;
- frontend: one app/package or one feature/shared subtree;
- docs: one lifecycle bucket such as ADR index, active plans, runbooks,
  reference docs, or archive reports;
- directory closure: top-level directory contracts, high-volume subtree
  authoring docs, asset placement, local residue, and non-product import roots.

Branches may touch shared registries only as the final integration patch for
their primary fence. If a branch needs two primary fences, split it unless the
second fence is a tiny test update required for verification.

### Shared Registry Queues

Use separate queues so unrelated work can still move quickly:

| Queue | Files | Merge owner | Notes |
| --- | --- | --- | --- |
| topology queue | `architecture/topology.toml`, root allow-lists, `.gitignore` | team-platform | phases 1.1, 2.1, and 1.8 coordinate here |
| package contract queue | `package_layout`, `package_boundaries`, `public_surface`, `import_contracts`, `name_registry`, `shims` | team-architecture | one package move at a time |
| generated-artifact queue | `architecture/generated_artifacts.toml`, schema/client generation commands | team-devx/team-architecture | coordinate lifecycle, ops, JS, and schema phases |
| test topology queue | `architecture/tests/topology.toml`, test ratchets, pytest root policy | team-quality | coordinate verification phases with package moves |
| JS workspace queue | `pnpm-workspace.yaml`, `pnpm-lock.yaml`, root `package.json` | team-frontend | singleton lockfile updates |
| Python tooling queue | `pyproject.toml`, `mypy.ini`, `ruff.toml`, `pytest.ini` | team-devx | avoid concurrent path override churn |
| docs nav queue | `mkdocs.yml`, generated nav fragments | team-docs | docs moves can prepare in parallel |
| control-plane queue | `.github/CODEOWNERS`, rulesets, workflows | team-platform/team-security | merge after root/path decisions |
| ops security queue | `ops/security/**`, release security gates | team-security | coordinate operability, supply-chain, and compatibility gates |

Queue rule: long-running branches may carry generated snippets, but the queue
owner rebases and merges the shared file patch after the source/destination
paths are final.

### Safe Parallel Lanes

| Lane | Safe parallel units | Serialized points |
| --- | --- | --- |
| Root/platform | product-root decision, lifecycle inventory, runtime-state inventory, ownership coverage report | physical root move, CODEOWNERS/rulesets |
| Lifecycle/ops | release/build cleanup, ops taxonomy, operability bundle drafts | generated-artifact command registry |
| Backend facades | Fabric facade, IR facade, shim test collapse, package README drafts | `shims.toml`, public-surface/import contracts |
| Foundry | executor consolidation, method taxonomy docs, catalog characterization tests, extension contract draft | Foundry registry/discovery, `foundry/api.py`, shared method registry |
| Scientist | feedback/replay/evidence lane, llm/compute/engine lane, governance/validation lane, search/discovery lane, nodes extension lane | `scientist/api.py`, governance pass entry points, shared shims |
| Verification | mirror-ratio reports, fixture inventory, property-test additions, repo-quality tests, benchmark role decision | test topology contract and pytest collection roots |
| Frontend | app/package workspace plan, shared UI docs, API client generated-contract review, feature subtree docs | pnpm lockfile, generated client command paths |
| Docs/examples | ADR index, plan lifecycle cleanup, runbook mapping, installable examples | mkdocs nav and extension-point registry |
| Supply chain | SBOM policy, provenance report, workflow permission audit | repository rulesets and release workflows |
| Directory closure | high-volume subtree docs, residue inventory, non-product import root inventory | directory contract gate and top-level allow-list |

### Do-Not-Parallelize Pairs

These pairs may prepare in parallel, but should not merge physical changes in
parallel:

- Phase 1.1 physical root decision with Phase 2.7 physical JS workspace relocation.
- Phase 2.1 generated-artifact lifecycle edits with Phase 2.2 runner path rewrites that change
  the same generator commands.
- Package moves with Phase 5.5 config split when both rewrite the same
  mypy/ruff per-file paths.
- Phase 4.2 Foundry methods taxonomy with Phase 5.1 Foundry extension registry when both
  touch method discovery or registry code.
- two Scientist taxonomy lanes that both modify `scientist/api.py`,
  governance pass entry points, or the same shim entries.
- Phase 1.4 pytest-root decisions with Phase 2.4 fixture/golden moves.
- Phase 2.7 pnpm workspace moves with any branch that updates `pnpm-lock.yaml`.
- Phase 2.6 docs lifecycle moves with Phase 6.4 docs nav gate conversion.
- Phase 2.8 ruleset/workflow changes with Phase 6.3 release-gate or security workflow changes.
- Phase 6.1 fail-closed boundary gates with active package move branches.
- Phase 6.2 fail-closed directory gates with active top-level path moves.

### PR Shape Rules

- One PR should have one primary phase and one primary path fence.
- Source moves include import rewrites, local tests, and shim smoke tests, but
  shared registry edits should be short and reviewable.
- Report-only gates merge before fail-closed gates.
- A compatibility shim PR should not also do deep package decomposition.
- A lockfile PR should not include unrelated TypeScript source changes.
- A docs nav PR should not include unrelated prose rewrites.
- Large package moves should land as "move + compatibility + characterization"
  before "cleanup + deletion".
- Any PR touching more than one shared queue needs an explicit integration note
  in the PR body.

## Program Control Ledger

This section is the Phase 0.1 control surface. It links active subplans,
normalizes severity and branch naming, publishes the dashboard schema, assigns
queue owners, and declares a primary fence for every phase. It is planning
metadata only: no product code, shared registry, lockfile, workflow, or
generated artifact is changed by Phase 0.1.

### Subplan Index

The following active plans are subplans of this master plan. They keep their
own detailed backlog and acceptance detail, while this master plan owns
cross-program sequencing, fences, queue ownership, dashboards, and closeout.

| Subplan | Master role | Primary fence | Master owner | Master touchpoints |
| --- | --- | --- | --- | --- |
| `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md` | Fabric remediation and SOTA backlog | package source: `fabric` | team-fabric | 3.1, 5.3, 5.7, 6.1 |
| `docs/plans/active/IR_AUDIT_REMEDIATION_PLAN.md` | IR remediation and contract backlog | package source: `ir` | team-ir | 3.2, 5.3, 5.7, 6.1 |
| `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md` | Foundry executor, methods, and extension backlog | package source: `foundry` | team-foundry | 4.1, 4.2, 5.1, 5.4 |
| `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md` | Scientist taxonomy, governance, and node backlog | package source: `scientist` | team-scientist | 4.4, 4.5, 4.6, 4.7, 5.2 |
| `docs/plans/active/FRONTEND_SOTA_PLAN.md` | Runtime dashboard and frontend platform backlog | frontend | team-frontend | 2.7, 4.10, 6.2 |
| `docs/plans/active/INFRASTRUCTURE_SOTA_PLAN.md` | Platform, release, CI, and ownership backlog | root/control plane | team-platform | 1.1, 1.7, 2.8, 5.9, 6.3 |
| `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md` | Documentation, IA, README, ADR, and docs gates backlog | docs | team-docs | 2.6, 4.10, 5.7, 6.4 |
| `docs/plans/active/TOOLS_AUDIT_REMEDIATION_PLAN.md` | Tooling, ops runners, CI output, and tool config backlog | tools/ops_runners | team-devx | 2.2, 3.6, 5.5, 6.2 |

Subplan rule: a subplan may own package-local findings and fixes, but any item
that changes root topology, shared registries, lockfiles, CODEOWNERS, rulesets,
workflows, generated-artifact commands, or cross-package public surface must be
represented in the master ledger below before it merges.

### Severity Labels

| Severity | Definition |
| --- | --- |
| P0 | Ambiguity causing active drift or unsafe operations. |
| P1 | Package boundary or public-surface risk. |
| P2 | Verifiability, extension, or operability risk. |
| P3 | Documentation, naming, and ergonomics debt. |
| P4 | Polish and long-tail cleanup. |

### Branch Naming Patterns

| Pattern | Intended fence | Typical phases |
| --- | --- | --- |
| `codex/root-topology-*` | root/control plane and architecture decisions | 0.2, 1.1, 1.3, 1.7, 2.8 |
| `codex/ops-taxonomy-*` | lifecycle/output, tools/ops_runners, runtime state, release, supply chain | 1.2, 1.6, 2.1, 2.2, 2.3, 5.6, 5.9, 6.3 |
| `codex/fabric-facade-*` | package source: `fabric` | 3.1 |
| `codex/ir-facade-*` | package source: `ir` | 3.2 |
| `codex/foundry-executor-*` | package source: Foundry executor internals | 4.1 |
| `codex/scientist-taxonomy-*` | package source: Scientist taxonomy lanes | 4.4, 4.5, 4.6, 4.7, 5.2 |
| `codex/tests-topology-*` | tests, fixtures, benchmarks, and repo-quality gates | 0.4, 1.4, 2.4, 3.5, 5.3, 6.2 |
| `codex/extension-points-*` | extension, ABI, dynamic import, compatibility, examples | 1.5, 5.1, 5.2, 5.10, 6.4 |
| `codex/directory-closure-*` | docs, directory contracts, asset placement, READMEs, archives | 0.7, 1.8, 2.6, 2.9, 4.10, 5.7, 6.4 |

Branch rule: no long-running branch may use a shared registry, lockfile,
workflow, ruleset, or CODEOWNERS path as its primary work. Those files are
queue-owned integration patches, even when their edits are prepared inside a
package, docs, tests, frontend, ops, or root-topology branch.

### Remediation Dashboard

Phase 0.1 publishes the dashboard contract and assigns metric owners. Wave 0
inventory phases populated the initial baselines on 2026-05-05; later waves
ratchet these values or replace them with generated reports through the same
dashboard rows.

| Metric | Owner | Source report or contract | Baseline producer | Ratchet or closeout gate | Current Phase 0.1 state |
| --- | --- | --- | --- | --- | --- |
| Root policy violations | team-platform | root topology report, `architecture/topology.toml` | 0.2 | 1.1, 2.1, 2.8, 6.2 | Wave 7: 0 fail-closed root policy findings; see [2026-05-06 Wave 7 closeout](../archive/2026-05-06-repository-best-in-class-wave7-closeout.md). |
| Root facade violations | team-architecture | package facade report, public-surface inventory | 0.5 | 3.1, 3.2, 6.1 | Wave 7: 0 root facade findings after registered Python re-export shims are counted through shim policy. |
| Shim count and days to sunset | team-architecture | `architecture/shims.toml`, shim sunset report | 0.3 | 3.3, 3.4, 6.5 | Wave 7: 89 registered shims; next sunset 2026-07-01, 56 days from 2026-05-06. |
| Mirror-test ratios | team-quality | mirror-ratio report, test ratchets | 0.4 | 5.3, 6.2 | Wave 7: ratchets pass with 0 floor regressions, 0 property regressions, and 6 explicit exceptions. |
| Module-size debt | team-architecture | module-size report, budget registry | 0.5 | 4.3, 5.4, 6.1 | Wave 7: 18 active module-size budgets and 0 contract errors; remaining debt is report-only budget work. |
| SLO/runbook coverage | team-ops | runbook coverage and component observability contracts | 0.6 | 4.9, 6.3 | Wave 7: operability gate passes for 14 components, 8 public-stable components, and 46 mapped alerts. |
| Stale override count | team-devx | dead mypy/ruff override report | 0.3 | 3.6, 5.5, 6.5 | Wave 7: 1,045 overrides tracked with 0 stale overrides, 0 missing metadata, and 0 findings. |
| Generated-artifact freshness | team-devx | generated-artifact freshness report | 0.3 | 2.1, 5.10, 6.3 | Wave 7: generated checks have 0 contract errors; compatibility gates track 6 generated families. |
| CODEOWNERS coverage | team-platform | CODEOWNERS/ruleset coverage report | 0.6 | 1.7, 2.8, 6.3 | Wave 7: strict current CODEOWNERS control-plane check passes with 0 blockers and 0 findings. |
| Directory-health coverage | team-docs | directory-contract coverage and residue reports | 0.7 | 1.8, 2.9, 6.2 | Wave 7: directory health passes with 0 findings, 0 contract errors, 0 regressions, 100% high-volume subtree documentation coverage, and 0 undocumented frontend subtrees. |

Dashboard publication rule: every closeout PR must update the metric row it
changes, either with a measured value, a generated report link, or a dated
owner exception.

### Registry Queue Ownership Assignments

These assignments refine the shared registry queues in the Parallel Safety
Model. Queue owners are integration owners, not long-running branch owners.

| Queue | Primary owner | Backup owner | Allowed branch family | Integration rule |
| --- | --- | --- | --- | --- |
| topology queue | team-platform | team-architecture | `codex/root-topology-*` | merge only after root/path decision text is stable |
| package contract queue | team-architecture | affected package owner | `codex/*-facade-*`, `codex/extension-points-*` | one package contract or shim/public-surface patch at a time |
| generated-artifact queue | team-devx | team-architecture | `codex/ops-taxonomy-*` | command-map patches merge after source and generator paths are final |
| test topology queue | team-quality | affected package owner | `codex/tests-topology-*` | report-only before fail-closed; no mixed fixture moves |
| JS workspace queue | team-frontend | team-devx | `codex/root-topology-*` or `codex/directory-closure-*` | singleton lockfile patch, isolated from TS source changes |
| Python tooling queue | team-devx | team-quality | `codex/ops-taxonomy-*` | stale-override report lands before config split |
| docs nav queue | team-docs | team-devx | `codex/directory-closure-*` | generated or small nav fragments only |
| control-plane queue | team-platform | team-security | `codex/root-topology-*` | path-prefix changes merge after physical path moves |
| ops security queue | team-security | team-platform | `codex/ops-taxonomy-*` | serialize release/security workflow and policy changes |

### Phase Fence Ledger

Every phase has exactly one primary fence. Secondary paths are allowed only for
verification, docs, or short queue-owned integration patches.

| Phase | Primary path fence | Owner | Default branch pattern |
| --- | --- | --- | --- |
| 0.1 Program Ledger And Ownership Fences | docs: active plans | team-polisyos | `codex/root-topology-program-ledger-*` |
| 0.2 Root Topology Inventory | root/control plane | team-platform | `codex/root-topology-inventory-*` |
| 0.3 Architecture Contract Inventory | architecture/contracts | team-architecture | `codex/root-topology-contract-inventory-*` |
| 0.4 Verification Inventory | tests: topology and reports | team-quality | `codex/tests-topology-inventory-*` |
| 0.5 Source Complexity Inventory | package source: cross-package inventory | team-architecture | `codex/directory-closure-source-inventory-*` |
| 0.6 Ops, Runtime, Control-Plane, And Supply-Chain Inventory | tools/ops_runners | team-ops | `codex/ops-taxonomy-inventory-*` |
| 0.7 Docs, Extensions, Directory, And Asset Inventory | docs: lifecycle inventory | team-docs | `codex/directory-closure-inventory-*` |
| 1.1 Product Root Decision | root/control plane | team-platform | `codex/root-topology-decision-*` |
| 1.2 Lifecycle And Ops Taxonomy Decision | lifecycle/output | team-ops | `codex/ops-taxonomy-lifecycle-*` |
| 1.3 Architecture Report-Only Contracts | architecture/contracts | team-architecture | `codex/root-topology-report-contracts-*` |
| 1.4 Test And Benchmark Contracts | tests: topology and benchmarks | team-quality | `codex/tests-topology-contracts-*` |
| 1.5 Extension, ABI, Dynamic Import, And Versioning Contracts | architecture/contracts | team-architecture | `codex/extension-points-contracts-*` |
| 1.6 Operability And Runtime-State Contracts | runtime state | team-ops | `codex/ops-taxonomy-runtime-state-*` |
| 1.7 Control-Plane And Supply-Chain Contracts | root/control plane | team-platform | `codex/root-topology-control-plane-*` |
| 1.8 Directory Closure Contract | directory closure | team-docs | `codex/directory-closure-contract-*` |
| 2.1 Release, Build, Cache, And Retention Cleanup | lifecycle/output | team-ops | `codex/ops-taxonomy-lifecycle-cleanup-*` |
| 2.2 Tools/Ops Runner Relocation | tools/ops_runners | team-devx | `codex/ops-taxonomy-runner-relocation-*` |
| 2.3 Runtime-State Schema And Cleanup | runtime state | team-ops | `codex/ops-taxonomy-runtime-cleanup-*` |
| 2.4 Test Fixture, Helper, Golden, And Data Split | tests: fixtures/golden/data | team-quality | `codex/tests-topology-fixtures-*` |
| 2.5 Schemas Code/Data Separation | schemas/data contracts | team-architecture | `codex/directory-closure-schemas-*` |
| 2.6 Documentation, ADR, Plan, And Archive Lifecycle Cleanup | docs: lifecycle | team-docs | `codex/directory-closure-docs-*` |
| 2.7 JavaScript Workspace Topology Move | frontend | team-frontend | `codex/root-topology-js-workspace-*` |
| 2.8 Control-Plane Path-Prefix Cleanup | root/control plane | team-platform | `codex/root-topology-path-prefix-*` |
| 2.9 Directory Hygiene, Asset Placement, And Residue Cleanup | directory closure | team-docs | `codex/directory-closure-hygiene-*` |
| 3.1 Fabric Root Facade Closeout | package source: `fabric` | team-fabric | `codex/fabric-facade-closeout-*` |
| 3.2 IR Root Facade Closeout | package source: `ir` | team-ir | `codex/ir-facade-closeout-*` |
| 3.3 DDM Compatibility Shim Test Collapse | package source: `ddm` shim | team-architecture | `codex/extension-points-ddm-shim-*` |
| 3.4 Synthetic World Compatibility Shim Test Collapse | package source: `foundry` shim | team-foundry | `codex/extension-points-synthetic-world-shim-*` |
| 3.5 Repo-Quality Test Consolidation | tests: repo-quality | team-quality | `codex/tests-topology-repo-quality-*` |
| 3.6 Dead Override Report-Only Gate | tools/ops_runners | team-devx | `codex/ops-taxonomy-dead-overrides-*` |
| 4.1 Foundry Executor Lane | package source: Foundry executor | team-foundry | `codex/foundry-executor-*` |
| 4.2 Foundry Methods Taxonomy Lane | package source: Foundry methods | team-foundry | `codex/extension-points-foundry-methods-*` |
| 4.3 Characterization Tests And God-Module Budgets | tests: characterization and budgets | team-quality | `codex/tests-topology-god-modules-*` |
| 4.4 Scientist Feedback, Evidence, And Replay Lane | package source: Scientist feedback/evidence/replay | team-scientist | `codex/scientist-taxonomy-feedback-*` |
| 4.5 Scientist Engine, LLM, Compute, And Orchestration Lane | package source: Scientist engine/compute | team-scientist | `codex/scientist-taxonomy-engine-*` |
| 4.6 Scientist Governance And Validation Lane | package source: Scientist governance/validation | team-scientist | `codex/scientist-taxonomy-governance-*` |
| 4.7 Scientist Search, Discovery, Research DAG, And Methods Lane | package source: Scientist search/discovery | team-scientist | `codex/scientist-taxonomy-search-*` |
| 4.8 Cross-Cutting Concern Adapters And Naming Hygiene | architecture/contracts | team-architecture | `codex/extension-points-naming-*` |
| 4.9 Operability Bundle Drafts | tools/ops_runners | team-ops | `codex/ops-taxonomy-operability-*` |
| 4.10 Directory, Frontend, README, And Authoring Docs | docs: package and subtree docs | team-docs | `codex/directory-closure-authoring-*` |
| 5.1 Foundry Extension Registry Integration | package source: Foundry extensions | team-foundry | `codex/extension-points-foundry-*` |
| 5.2 Scientist API And Node Extension Integration | package source: Scientist API/extensions | team-scientist | `codex/scientist-taxonomy-api-*` |
| 5.3 Mirror And Property-Test Expansion | tests: mirror/property | team-quality | `codex/tests-topology-ratchets-*` |
| 5.4 First God-Module Splits | package source: one module owner per branch | owning package team | `codex/directory-closure-god-module-*` |
| 5.5 Tool Config Split | tools/ops_runners | team-devx | `codex/ops-taxonomy-tool-config-*` |
| 5.6 Migrations And Release Topology | tools/ops_runners | team-ops | `codex/ops-taxonomy-release-topology-*` |
| 5.7 Package README Coverage | docs: package docs | team-docs | `codex/directory-closure-readmes-*` |
| 5.8 Per-Package Architecture Files | architecture/contracts | team-architecture | `codex/root-topology-package-contracts-*` |
| 5.9 Supply-Chain Closeout | root/control plane | team-security | `codex/ops-taxonomy-supply-chain-*` |
| 5.10 Compatibility Release Gates | architecture/contracts | team-architecture | `codex/extension-points-compatibility-*` |
| 6.1 Package, Public Surface, And Import Gate Conversion | architecture/contracts | team-architecture | `codex/root-topology-import-gates-*` |
| 6.2 Test, Benchmark, Directory, And Hygiene Gate Conversion | tests: topology and directory gates | team-quality | `codex/tests-topology-fail-closed-*` |
| 6.3 Operability, Release, And Supply-Chain Gate Conversion | tools/ops_runners | team-security | `codex/ops-taxonomy-release-gates-*` |
| 6.4 Documentation, Navigation, ADR, Examples, And README Gate Conversion | docs: nav and examples | team-docs | `codex/directory-closure-doc-gates-*` |
| 6.5 Exception And Sunset Cleanup | architecture/contracts | team-architecture | `codex/extension-points-sunset-cleanup-*` |
| 7.1 Final Verification And Closeout Artifact | docs: closeout evidence | team-polisyos | `codex/directory-closure-closeout-*` |

## Detailed Workstreams

Rule: all phases within a wave are parallel by default. If two phases need the
same path fence, registry queue, lockfile, public facade, workflow/ruleset, or
generated-artifact command map, the conflicting phase moves to the next wave.
Do not solve intra-wave conflict by adding an exception. The wave itself is the
unit of safe parallelism.

Each phase below includes its own scope and acceptance criteria. There is no
separate reference section; the phase text is the source of truth.

### Wave 0 - Inventory And Program Setup

Purpose: make all later work measurable without moving product code. All Wave 0
phases are C0 read-only work and can run in parallel.

#### Phase 0.1 - Program Ledger And Ownership Fences

Implementation note: Phase 0.1 is satisfied by the `Program Control Ledger`,
`Finding Ledger`, dashboard, queue ownership, and phase-fence matrix in this
master plan. Later phases may update measured values, but they must not fork a
second ledger.

Scope:

- Create a single finding ledger with finding ID, source audit, severity, owner,
  primary path fence, dependencies, acceptance criteria, rollback note, target
  wave, and target phase.
- Link existing active plans as subplans of this master plan:
  `FABRIC_AUDIT_REMEDIATION_PLAN.md`, `IR_AUDIT_REMEDIATION_PLAN.md`,
  `FOUNDRY_REMEDIATION_PLAN.md`, `SCIENTIST_AUDIT_REMEDIATION_PLAN.md`,
  `FRONTEND_SOTA_PLAN.md`, `INFRASTRUCTURE_SOTA_PLAN.md`,
  `DOCUMENTATION_SOTA_PLAN.md`, and `TOOLS_AUDIT_REMEDIATION_PLAN.md`.
- Define severity labels:
  - P0: ambiguity causing active drift or unsafe operations;
  - P1: package boundary or public-surface risk;
  - P2: verifiability, extension, or operability risk;
  - P3: documentation, naming, and ergonomics debt;
  - P4: polish and long-tail cleanup.
- Define branch naming patterns:
  - `codex/root-topology-*`;
  - `codex/ops-taxonomy-*`;
  - `codex/fabric-facade-*`;
  - `codex/ir-facade-*`;
  - `codex/foundry-executor-*`;
  - `codex/scientist-taxonomy-*`;
  - `codex/tests-topology-*`;
  - `codex/extension-points-*`;
  - `codex/directory-closure-*`.
- Publish a remediation dashboard with root policy violations, root facade
  violations, shim count and days to sunset, mirror-test ratios, module-size
  debt, SLO/runbook coverage, stale override count, generated-artifact
  freshness, CODEOWNERS coverage, and directory-health coverage.
- Assign owners for the shared registry queues listed in the Parallel Safety
  Model.

Acceptance:

- Every audit finding maps to one or more phases and one acceptance gate.
- Every phase has one primary path fence.
- No long-running branch owns a shared registry file as its main work.

Parallel safety:

- This phase only creates planning metadata, dashboards, and ownership notes.
  It may run with all other Wave 0 phases.

#### Phase 0.2 - Root Topology Inventory

Scope:

- Inventory every tracked file outside `policy-engine`.
- Inventory ignored residue outside `policy-engine`, especially `_cache/ruff`,
  `tmp/phase3a_*`, and any outer-root scratch/build/runtime paths.
- Classify outer-root files as GitHub control plane, editor/local metadata,
  product config that must move, or ignored local residue.
- Inventory product command assumptions, CI working directories, workspace
  doctor assumptions, root README instructions, and automation paths that assume
  either the outer root or `policy-engine`.
- Record current placement and expected future placement for `renovate.json`.

Acceptance:

- Wave 1 has a complete root decision brief with tracked paths, ignored residue,
  command assumptions, and cleanup candidates.
- No physical root move is attempted in this phase.

Artifact:

- Status: completed on 2026-05-05 as inventory-only documentation.
- [Repository Root Topology Decision Brief](REPOSITORY_ROOT_TOPOLOGY_DECISION_BRIEF.md)
  records the Phase 0.2 inventory and Wave 1 decision inputs.

Parallel safety:

- Read-only inventory. It does not touch topology, CI, CODEOWNERS, or cleanup
  scripts.

#### Phase 0.3 - Architecture Contract Inventory

Scope:

- Inventory existing machine-readable governance:
  `architecture/topology.toml`, package layout, package boundaries, public
  surface, import contracts, name registry, shim registry, generated artifacts,
  local runtime state, test topology, exception registries, and gate files.
- Identify contracts that currently require editing 4-5 files for one package
  change and list candidates for per-package architecture files.
- Inventory report-only versus fail-closed gates and their current owners.
- Inventory stale exception risks in mypy, ruff, package-boundary, public
  surface, shims, dynamic imports, generated artifacts, and directory layout.
- Draft the shared registry queue plan for topology, package contracts,
  generated artifacts, test topology, JS workspace, Python tooling, docs nav,
  control plane, and ops/security.

Acceptance:

- Wave 1 can add report-only contracts without guessing where existing rules
  live.
- No fail-closed gate is changed in this phase.

Implementation evidence:

- Status: completed on 2026-05-05 as inventory-only documentation.
- Human report:
  [Repository Best-In-Class Phase 0.3 Architecture Contract Inventory](../../archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_3_ARCHITECTURE_CONTRACT_INVENTORY.md).

Parallel safety:

- Read-only inventory. It may run while source, tests, docs, and ops inventories
  run independently.

#### Phase 0.4 - Verification Inventory

Scope:

- Measure source/test mirror ratios per layer and record baselines for `ir`,
  `core`, `fabric`, `foundry`, `scientist`, `runtime`, `lex`, `scholar`,
  `berl`, `ddm`, `data_forge`, `calibration`, compatibility shims, and any
  package moved during remediation.
- Inventory `tests/fixtures`, `tests/golden`, `tests/contract`, package-local
  fixtures, and pytest-collectable tests under data-like directories.
- Inventory `tests/repo_quality/architecture`, `tests/lint`, `tests/tools`, and
  `tests/contract` to separate product behavior, product contract, and
  repository-quality tests.
- Inventory property-test coverage and missing property-test areas, especially
  Fabric, Lex, Data Forge, and other data-contract-heavy packages.
- Inventory benchmark topology, benchmark pytest configuration, benchmark
  helper implementation, suites, markers, and report directories.
- Inventory pytest roots, conftest layering, import mode, and fixture scope
  ambiguity.

Acceptance:

- Wave 1 has measured baselines for mirror-ratio, property coverage, fixture
  layout, benchmark role, and pytest-root decisions.
- Ratchet proposals start from current baselines, not aspirational targets.

Parallel safety:

- Read-only test inventory. It does not move tests or change pytest config.

Implementation evidence:

- Generator:
  `tools/quality/validation/repository_verification_inventory.py`.
- Machine baseline:
  `architecture/baselines/repository_best_in_class_phase0_4/verification_inventory.json`.
- Human report:
  `docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_4_VERIFICATION_INVENTORY.md`.
- Freshness test: `tests/repo_quality/tools/test_repository_verification_inventory.py`.

#### Phase 0.5 - Source Complexity Inventory

Scope:

- Inventory root-facade violations in Fabric, IR, and any other active package
  that should allow only `__init__.py`, `api.py`, and optional `_api.py` at the
  package root.
- Inventory first-party and documented external imports of `polisyos.ddm_15_7`
  and `polisyos.synthetic_world`.
- Inventory Foundry executor private sibling packages, `executor` versus
  `execute` naming, methods-root loose files, method catalog registration, and
  extension registry entry points.
- Inventory Scientist first-level package count and close semantic pairs:
  `feedback`/`feedback_utils`, `replay`/`replay_backend`,
  `evidence`/`evidence_sources`, `governance`/`continuous_governance`,
  `validation`/`verification`/`policy_verified`, `llm`/`llm_cycle`, and
  `discovery`/`search`/`research_dag`.
- Inventory cross-cutting concern collisions for observability, security,
  registry, discovery, governance, contracts, calibration, runtime, and trace.
- Generate module-size inventory and classify modules above 2,000 lines by
  domain model concentration, mixed IO/business logic, registry/catalog
  assembly, service orchestration, and generated or semi-generated code.
- Start the high-debt module list with:
  - `src/polisyos/foundry/methods/catalog/causal/causal_engine.py`;
  - `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py`;
  - `src/polisyos/foundry/methods/catalog/causal/interference.py`;
  - `src/polisyos/foundry/methods/catalog/causal/id_engine.py`;
  - `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py`;
  - `src/polisyos/data_forge/domains/academic/batch/resolve_extract.py`;
  - `src/polisyos/runtime/http/services/control.py`.

Acceptance:

- Wave 3 and Wave 4 have file-level move maps and characterization-test
  candidates before any physical source move starts.
- Every god-module candidate has owner, risk note, and initial target
  subpackage proposal.

Implementation evidence:

- Status: completed on 2026-05-05 as inventory-only documentation.
- Human report:
  [Repository Best-In-Class Phase 0.5 Source Complexity Inventory](../../archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_5_SOURCE_COMPLEXITY_INVENTORY.md).

Parallel safety:

- Read-only source analysis. It does not rewrite imports or move files.

#### Phase 0.6 - Ops, Runtime, Control-Plane, And Supply-Chain Inventory

Scope:

- Inventory `.polisyos` first-level directories, nested runtime state,
  CAS-related paths, retention assumptions, backup expectations, and promotion
  candidates for committed evidence.
- Inventory `tools/ops_runners/**` versus `ops/**` duplicate names and classify each
  subtree as declarative artifact, runner/script, policy, migration, or
  placeholder.
- Inventory SLO files, missing public-stable packages, runbook coverage, alert
  coverage, dashboard coverage, component-to-runbook mapping, and current
  `ops/observability` organization.
- Inventory migrations across DB SQL, runtime-state formats, API schemas, IR
  schemas, and Python migration helpers.
- Inventory release topology and promotion gates: deployment targets,
  control-plane/data-plane/frontend split, staging-to-production checks, and
  release evidence templates.
- Inventory CODEOWNERS coverage, branch/ruleset protection, workflow
  permissions, OIDC usage, long-lived secrets, dependency update policy, SBOM
  generation, provenance/attestation expectations, signed artifacts, and
  release security gates.

Acceptance:

- Wave 1 has enough data to decide ops taxonomy, runtime-state contract,
  operability bundle shape, and supply-chain controls.
- No ops paths, rulesets, workflows, or secrets are changed in this phase.

Parallel safety:

- Read-only inventory. It may run with root, architecture, source, test, docs,
  and directory inventories.

Implementation evidence:

- Status: completed on 2026-05-05 as inventory-only documentation.
- Human report:
  `docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_6_OPS_RUNTIME_CONTROL_PLANE_SUPPLY_CHAIN_INVENTORY.md`.

#### Phase 0.7 - Docs, Extensions, Directory, And Asset Inventory

Scope:

- Inventory active, accepted, archived, design, migration, ADR, release-note,
  runbook, and architecture-prose documents.
- Inventory ADR metadata and missing machine-readable fields: status, topic,
  package, supersedes, superseded_by, and related.
- Inventory extension-point candidates in Fabric connectors, Scientist
  governance passes, Foundry methods, Scientist nodes, Data Forge domains, Lex
  norm packs, and Runtime middlewares.
- Inventory examples and determine which examples should become installable
  verification assets.
- Inventory top-level directories and local-only roots for a future
  `architecture/policies/directory_contracts.toml`.
- Inventory high-volume subtrees needing README, AUTHORING, or generated index:
  `docs/adr`, `schemas/snapshots/ir`,
  `src/polisyos/foundry/methods/catalog/causal`,
  `src/polisyos/ir/analytics`, `src/polisyos/foundry/methods`,
  `src/polisyos/data_forge/domains/legal/batch`,
  `src/polisyos/data_forge/domains/catalog/batch`,
  `src/polisyos/scientist/agent`, `src/polisyos/scientist/search`,
  `src/polisyos/scientist/orchestration/engine`, `src/polisyos/runtime/http/services`,
  `src/polisyos/fabric/connectors/sources`,
  `apps/runtime-dashboard/src/shared/ui`,
  `apps/runtime-dashboard/src/api`,
  `apps/runtime-dashboard/src/features`,
  `apps/runtime-dashboard/src/test`,
  `tests/unit/foundry/methods/catalog/causal`, `tests/unit/data_forge`,
  `tests/unit/scientist/nodes`, `tests/_data`, `tests/_golden`,
  `tests/_helpers`, and
  `docs/archive/reports`.
- Inventory non-product Python roots outside `src/polisyos`: `benchmarks`,
  `tools`, selected `tests` packages, and `schemas/__init__.py`.
- Inventory product seed assets, test fixtures, golden records/snapshots,
  example assets, frontend test fixtures, empty directories, `.DS_Store`,
  `__pycache__`, egg-info residue, local audit reports, and benchmark reports.

Acceptance:

- Wave 1 has a complete directory-closure, documentation, extension, and asset
  decision brief.
- No docs lifecycle moves, examples, or directory cleanup occur in this phase.

Implementation evidence:

- Generator:
  `tools/quality/validation/repository_best_in_class_phase0_7_inventory.py`.
- Human report:
  [Repository Best-In-Class Phase 0.7 Decision Brief](../../archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_7_DECISION_BRIEF.md).
- Freshness test:
  `tests/repo_quality/tools/test_repository_best_in_class_phase0_7_inventory.py`.

Parallel safety:

- Read-only inventory. It does not touch docs nav, examples, or generated
  indexes.

Wave 0 exit criteria:

- Every finding maps to a future phase.
- Every future phase has one primary path fence.
- Every shared registry has a queue owner.
- No product code has moved.

### Wave 1 - Decisions And Report-Only Contracts

Purpose: decide target structure and land non-breaking contracts. Wave 1 phases
are parallel if they only add decisions, report-only gates, or contract drafts.
Any phase that physically moves files waits for Wave 2 or later.

#### Phase 1.1 - Product Root Decision

Scope:

- Decide the canonical repository/product root.

| Option | Description | Pros | Cons |
| --- | --- | --- | --- |
| A | Move git root to `policy-engine/` | cleanest product mental model | requires repository migration and GitHub control-plane handling |
| B | Keep outer git root but declare an honest wrapper/monorepo | GitHub-native and less disruptive | requires explicit `apps/`, `packages/`, `services/`, and wrapper-root contracts |
| C | Keep the current half-state | no immediate migration | rejected because it preserves drift |

- Preferred decision unless the repository host blocks it: make
  `policy-engine/` the effective product root for all product workflows while
  keeping only unavoidable repository control-plane files at the outer git root.
- Decide `renovate.json` placement under the selected topology.
- Define the outer-root allow-list and rejected path classes.
- Define the cleanup model for outer `_cache/ruff`, `tmp/phase3a_*`, and future
  wrong-root residue.
- Draft root topology gate requirements:
  - no product source outside the selected product root;
  - outer root allow-list limited to control-plane files;
  - no cache/runtime/build paths at the wrong root;
  - all documented product commands run from the selected root.
- Define update requirements for `architecture/topology.toml`, `.gitignore`,
  root README/repository topology reference, CI working directories, workspace
  doctor, and rollback checklist.

Acceptance:

- A decision record exists and selects Option A or B. Option C remains rejected.
- Wave 2 can perform root/lifecycle cleanup without reopening the target.
- Rollback guidance covers only path/workflow changes and explicitly excludes
  bundling source package moves.

Decision output:

- ADR-0146 selects Option B: keep the outer Git root as an explicit repository
  wrapper/GitHub control plane, with `policy-engine/` as the effective product
  root for all product workflows.
- Target Renovate placement is `.github/renovate.json`; the current outer-root
  `renovate.json` is transitional until config-location validation and Wave 2
  control-plane cleanup.
- Outer-root `_cache/ruff/**`, `tmp/phase3a_*`, and future wrong-root residue
  are cleanup candidates and must not be promoted to product state.

Parallel safety:

- This phase may run with other Wave 1 decision phases. It blocks physical root
  moves, CODEOWNERS path-prefix rewrites, and JS workspace relocation.

#### Phase 1.2 - Lifecycle And Ops Taxonomy Decision

Scope:

- Define lifecycle classes:
  - `source_committed`;
  - `generated_committed`;
  - `generated_ignored`;
  - `runtime_ignored`;
  - `scratch_ignored`.
- Decide `release/**` versus `_build/release/**`:
  - `release/**` is committed release input and evidence templates;
  - `_build/release/**` is generated output only;
  - no release source file may live under `_build`.
- Decide `release-fragments/**` versus `_build/release-fragments/**`:
  - `release-fragments/unreleased/**` is committed input;
  - `_build/release-fragments/**` is generated/archive output and ignored.
- Define retention policy:
  - `_build/scratch/<run-id>` default 7 days;
  - `_cache/**` recomputable, default 30 days;
  - `_build/release/**` default 90 days unless promoted to release evidence.
- Define generated-artifact contract fields: lifecycle, generator, verifier,
  owner, promotion target, and stale-output behavior.
- Decide `ops/**` versus runner placement.
- Preferred ops layout:

```text
ops/
  components/
  migrations/
  release/
  security/
  observability/
tools/
  ops_runners/
  devx/
  quality/
  research/
```

- Allowed alternative if teams prefer co-location:

```text
ops/
  declarative/
  runners/
```

- State that `ops/**` owns declarative operational artifacts and production
  contracts, while executable runners live in the selected runner namespace.

Acceptance:

- Wave 2 can clean release/build/cache paths and relocate the legacy ops runner
  tree without
  inventing lifecycle semantics during the move.
- Contributor docs can answer where to change deploy policy versus deploy
  runner.

Implementation evidence:

- Status: completed on 2026-05-05 as decision-only documentation.
- Decision record:
  [Repository Lifecycle And Ops Taxonomy Decision](REPOSITORY_LIFECYCLE_AND_OPS_TAXONOMY_DECISION.md).
- Selected runner namespace: `tools/ops_runners/**`.
- Selected ops contract: `ops/**` owns declarative operational artifacts and
  production contracts; executable runners move to `tools/ops_runners/**` in
  Phase 2.2.

Parallel safety:

- Decision-only. Physical path relocation waits for Wave 2.

#### Phase 1.3 - Architecture Report-Only Contracts

Scope:

- Group `architecture/**` conceptually into `packages`, `imports`,
  `public_surface`, `exceptions`, `policies`, `gates`, and `baselines` without
  requiring a physical move in this phase.
- Draft per-package contract files such as:

```text
architecture/packages/fabric.toml
architecture/packages/foundry.toml
architecture/packages/scientist.toml
```

- Per-package contracts should include package owner, layout status,
  boundaries, public surface classification, test expectations, SLO/runbook
  expectations, allowed name collisions, exceptions, and sunsets.
- Keep aggregate legacy TOML generated or manually mirrored until gates switch.
- Draft `architecture/module_size_budget.toml`:
  - default warning at 1,000 lines;
  - default fail-closed target at 2,500 lines after ratchet period;
  - explicit shrinking budgets for current god modules.
- Draft or expand:
  - `architecture/extension_points.toml`;
  - `architecture/runbook_coverage.toml`;
  - `architecture/component_observability.toml`;
  - `architecture/runtime_state_layout.toml`;
  - `architecture/tests/ratchets.toml`;
  - `architecture/policies/directory_contracts.toml`;
  - generated-artifact contracts;
  - import-boundary and dependency-graph reports;
  - dynamic-import registry;
  - dead mypy/ruff override checks.
- Add all new checks report-only first.

Acceptance:

- Adding a new package has one primary package contract file plus generated
  aggregates, not 4-5 hand-edited files.
- New gates run report-only and have owners before any fail-closed conversion.

Parallel safety:

- Contract drafting is parallel. Shared architecture files merge through the
  package contract and topology queues.

#### Phase 1.4 - Test And Benchmark Contracts

Scope:

- Expand `architecture/tests/topology.toml` or add
  `architecture/tests/ratchets.toml` with per-layer mirror ratio, allowed
  exceptions, integration coverage decisions, property-test decisions, ratchet
  floor, and no-regression rule.
- Start thresholds from measured baselines. Do not set aspirational fail-closed
  thresholds on packages currently below target.
- Define first ratchet behavior:
  - critical packages target 70 percent mirror presence first;
  - small/legacy packages may use explicit exception mode;
  - runtime over-coverage is normalized by mapping tests to modules or declaring
    cross-module behavior tests.
- Decide benchmark role:
  - public product evaluation tools move runner implementation under
    `src/polisyos/benchmarks` and keep suites/data separate; or
  - internal performance checks move under `tests/performance`.
- Preferred public-facing shape:

```text
benchmarks/
  README.md
  suites/
  _data/
src/polisyos/benchmarks/
  runner/
  metrics/
  reporting/
  harness/
```

- Preferred internal shape:

```text
tests/performance/
  suites/
  _runner/
  _data/
```

- Define fixture/golden target roots, repo-quality test grouping, pytest roots,
  marker policy, and duplicate pytest configuration cleanup.

Acceptance:

- CI can report mirror ratio per package without blocking moves.
- Benchmark collection path and fixture scope are predictable.
- No third independent pytest universe remains without an explicit exception.

Parallel safety:

- Decision/report-only only. Physical test moves wait for Wave 2 and Wave 3.

#### Phase 1.5 - Extension, ABI, Dynamic Import, And Versioning Contracts

Scope:

- Add `architecture/extension_points.toml` with entries like:

```toml
[[extension_point]]
name = "polisyos.foundry_methods"
contract = "polisyos.foundry.extensions.api.FoundryMethodPlugin"
contract_version = "1.0"
abi_compatibility = "semver-major"
deprecation_notice_window = "2 minor releases"
owner = "team-foundry"
```

- Define or expand entry-point groups:
  - `polisyos.fabric_connectors`;
  - `polisyos.scientist_governance_passes`;
  - `polisyos.foundry_methods`;
  - `polisyos.scientist_nodes`;
  - `polisyos.data_forge_domains`;
  - `polisyos.lex_normpacks`;
  - `polisyos.runtime_middlewares`.
- Require internal plugin loaders so builtins can use the same discovery path
  as external plugins.
- Tie dynamic imports to extension points:
  - plugin discovery uses entry points or declared builtin loaders;
  - ad hoc string imports require a dynamic-import registry entry;
  - registry entries include owner, target, and verifier.
- Extend ADR-0135 into a general versioning policy:
  - Python package names never carry problem/version numbers;
  - versioned data/API contracts live under schemas, OpenAPI, or explicit
    contract IDs;
  - extension contracts carry `contract_version`;
  - release fragments communicate user-visible change classes.
- Define compatibility categories:
  - Python public API;
  - schema/OpenAPI ABI;
  - extension plugin ABI;
  - runtime-state format;
  - persisted artifact format;
  - JS package API.
- Define deprecation windows for shim packages, renamed public imports,
  extension contract versions, runtime-state migration readers, and generated
  client compatibility.
- Define installable example expectations for each extension point.

Acceptance:

- Every future extension point has owner, contract class, contract version,
  ABI policy, and deprecation window.
- Future versioned concepts do not create packages like `*_15_7`.
- Decomposition work can distinguish public API, schema ABI, plugin ABI,
  runtime-state format, persisted artifact format, and JS package API.

Parallel safety:

- Contract-only. Physical registry consolidation waits for Wave 5 integration.

#### Phase 1.6 - Operability And Runtime-State Contracts

Implementation note: Phase 1.6's contract surface is
`architecture/runtime_state_layout.toml`,
`architecture/runbook_coverage.toml`,
`architecture/component_observability.toml`,
`ops/migrations/migration-contracts.toml`,
`ops/release/deployment-topology.toml`, and
`ops/release/promotion-gates.toml`. Physical `.polisyos/**`,
`ops/components/**`, and classed migration directory creation remain deferred
to later waves.

Scope:

- Define `.polisyos/SCHEMA.md` content: directory purpose, owner, file naming,
  format, retention, backup policy, safe cleanup command, and promotion rules
  for committed evidence.
- Expand `architecture/local_runtime_state.toml` or add
  `architecture/runtime_state_layout.toml` for the complete local runtime-state
  layout.
- Decide CAS normalization:
  - canonical `.polisyos/cas`;
  - cache under `.polisyos/cas/_cache`;
  - readme/check artifacts under `.polisyos/cas/_readme_check` or a tool-owned
    validation directory.
- Define runtime-state migration slots for audit, idempotency, decision
  validity, search registry, provider verification, and future persisted local
  state.
- Add `architecture/runbook_coverage.toml` fields: component, owner, runbooks,
  alerts, dashboards, and escalation.
- Add `architecture/component_observability.toml` fields: component, SLO file,
  Prometheus rules, Grafana dashboard, trace/log context keys, and release gate.
- Define SLO coverage expectations for missing public-stable packages: core,
  ir, foundry, lex, scholar, berl or explicit exception, ddm or explicit
  exception, and calibration or explicit exception.
- Decide ops organization for operability:
  - keep type-cut layout with a machine-readable component index; or
  - invert to `ops/components/<component>/**`.
- Preferred bundle shape:

```text
ops/components/scientist/
  README.md
  slo.yaml
  alerts.yml
  dashboard.json
  runbooks.md
  runtime-contract.toml
  retention-policy.toml
```

- Define migration classes under `ops/migrations/db`, `runtime_state`,
  `api_schemas`, and `ir`.
- Define `ops/release/deployment-topology.toml` and
  `ops/release/promotion-gates.toml`.

Acceptance:

- Wave 2 and Wave 5 can add runtime-state docs, cleanup, operability bundles,
  migrations, release topology, and promotion gates without redesigning shape.
- Every alert will eventually map to at least one runbook or exception.

Parallel safety:

- Contract-only. Physical `.polisyos` and ops changes wait for later waves.

#### Phase 1.7 - Control-Plane And Supply-Chain Contracts

Scope:

- Reconcile CODEOWNERS with the root decision:
  - every critical path has an owner;
  - `.github/**`, CODEOWNERS, rulesets, release workflows, and security config
    are self-protected by repository owners;
  - logical owners in architecture package contracts or ownership docs match
    enforceable CODEOWNERS patterns.
- Draft CODEOWNERS coverage gate:
  - every `architecture/packages/*.toml` owner maps to at least one CODEOWNERS
    pattern or explicit personal-repo exception;
  - no retired paths remain in CODEOWNERS;
  - no active public-stable package lacks owned review.
- Reconcile repository rulesets with quality gate tiers: required review,
  code-owner review, fast PR checks, release-gate checks, and protected branch
  force-push/delete restrictions.
- Define CI permission policy:
  - least-privilege workflow permissions by default;
  - explicit `id-token` only for workflows using OIDC;
  - no long-lived cloud secrets where short-lived identity is supported.
- Define supply-chain release policy:
  - SBOM for release candidates and dependency-lock changes;
  - provenance or attestation target per artifact type;
  - signed release artifacts where release tooling supports it;
  - dependency/security scan gates mapped to release phases;
  - Scorecard/SLSA-style control crosswalk as a reporting artifact.
- Ensure dependency update policy and `renovate.json` placement follow the root
  decision.

Acceptance:

- Control-plane changes after path moves have a concrete target.
- Release candidates have SBOM/provenance expectations tied to generated
  artifact contracts.

Parallel safety:

- Contract-only. CODEOWNERS/ruleset path rewrites wait for Wave 2 path-prefix
  cleanup.

Phase 1.7 contract artifacts:

- `architecture/control_plane_supply_chain.toml` defines target owner mappings,
  CODEOWNERS cleanup targets, ruleset tiers, workflow permission/OIDC policy,
  Renovate placement, release SBOM/provenance/signing expectations, and the
  Scorecard/SLSA-style reporting crosswalk.
- `tools/quality/validation/control_plane_supply_chain_contracts.py` validates
  the contract in report-only mode and keeps current CODEOWNERS cleanup targets
  as advisories until Phase 2.8.
- `docs/reference/merge-governance.md`,
  `docs/how-to/apply-github-governance.md`,
  `docs/reference/quality-gates.md`,
  `docs/reference/security-compliance.md`, and
  `docs/how-to/release-policy.md` describe the repo-tracked target state.

#### Phase 1.8 - Directory Closure Contract

Scope:

- Add `architecture/policies/directory_contracts.toml` or extend topology with a
  top-level contract for every root directory:
  - `architecture`;
  - `benchmarks`;
  - `data`;
  - `design`;
  - `docs`;
  - `examples`;
  - `frontend` or future `apps`;
  - `ops`;
  - `packages`;
  - `release`;
  - `release-fragments`;
  - `schemas`;
  - `src`;
  - `tests`;
  - `tools`;
  - local-only roots such as `_build`, `_cache`, `.polisyos`, `.venv`, and
    `node_modules`.
- Each entry declares role, allowed file kinds, allowed child directory kinds,
  lifecycle class, owner, Python-import policy, generated-output policy,
  committed-data policy, README/index requirement, maximum root loose-file
  policy, ignored-descendant retention, and evidence/generated-artifact
  promotion path.
- Define high-volume subtree threshold:
  - at least 20 tracked files;
  - or more than 10 immediate child directories;
  - or any module above the warning line-count threshold;
  - or any subtree containing committed data, fixtures, or golden files.
- Define local documentation requirement for high-volume subtrees: README,
  AUTHORING, generated index, or explicit owner/sunset exception.
- Define non-product Python root policy:
  - `tools` may remain importable as internal devx tooling if documented;
  - `tests` may use package-style helpers only for pytest import-mode reasons;
  - `benchmarks` follows the Phase 1.4 benchmark decision;
  - `schemas` stops being importable after schema separation.
- Define asset classes and allowed roots:
  - product seed assets under package-owned `assets` or registered product
    `fixtures`;
  - test fixtures under `tests/_data` or package-local test fixture roots;
  - golden records under `tests/_golden` or registered snapshot roots;
  - examples/tutorial assets under installable `examples/<example-name>`.
- Define archive classes: accepted plans, historical plans, release evidence,
  local audit reports, generated benchmark reports, and incident/postmortem
  records.

Acceptance:

- A contributor can answer "what belongs here?" for every top-level directory
  from one machine-readable contract.
- Directory contracts do not contradict topology, generated artifacts,
  local-runtime-state, or data-policy contracts.

Parallel safety:

- Contract-only. Directory cleanup and fail-closed gates wait for Wave 2 and
  Wave 6.

Wave 1 exit criteria:

- No physical source move is waiting on an undecided target.
- Report-only gates can run without breaking CI.
- Every phase that needs a shared registry has a queue slot.

### Wave 2 - Low-Risk Topology And Lifecycle Moves

Purpose: clean lifecycle, docs, test data, schemas, runtime state, and workspace
topology before deep package decomposition. Wave 2 phases are parallel only when
their path fences do not overlap.

#### Phase 2.1 - Release, Build, Cache, And Retention Cleanup

Scope:

- Implement the lifecycle decision for `release/**`, `_build/release/**`,
  `release-fragments/**`, `_build/release-fragments/**`, `_build/scratch/**`,
  `_cache/**`, and wrong-root cache/tmp residue.
- Ensure `release/**` and `release-fragments/unreleased/**` remain committed
  inputs, while `_build/**` remains generated output or ignored scratch.
- Add stale generated-output detection:
  - ignored generated output older than retention emits warning;
  - committed generated output missing a generator entry fails.
- Update `architecture/generated_artifacts.toml` with lifecycle, generator,
  verifier, owner, and promotion target for every committed generated artifact.
- Add cleanup commands that can remove local scratch, outer-root residue, and
  expired ignored generated output without touching source or release inputs.

Acceptance:

- No committed file lives under ignored build/cache umbrellas.
- No release source file lives under `_build`.
- Cleanup is dry-run safe and preserves committed release inputs.

Parallel safety:

- Phase 2.1 owns release/build/cache lifecycle and the generated-artifact
  command entries for those paths. If runner relocation needs the same
  generated-artifact entries, that shared registry patch moves to Wave 3 as a
  short integration patch.
- If Phase 1.1 selected a repository migration window, keep this phase to
  lifecycle cleanup only and move root-migration mechanics to the dedicated
  platform window.

#### Phase 2.2 - Tools/Ops Runner Relocation

Scope:

- Move the legacy ambiguous runner namespace to the selected
  `tools/ops_runners/**` namespace.
- Update dynamic-import inventories, generated-artifact commands, CI, docs,
  workspace doctor, release scripts, and local developer commands.
- Add a gate that forbids new ambiguous legacy runner paths.
- Ensure `ops/**` top-level directories are not placeholders:
  - every top-level ops folder has README, owner, and artifact type;
  - empty placeholder directories are removed or linked to concrete backlog.

Acceptance:

- `tools` and `ops` show a declared taxonomy, not duplicate names.
- A contributor can tell where to change deploy policy versus deploy runner.
- Generated-artifact workflows still run.

Implementation evidence:

- Status: completed on 2026-05-05.
- Runner namespace: executable operational runners live under
  `tools/ops_runners/**`; `ops/**` remains declarative/control-plane source.
- Gate:
  `tests/repo_quality/architecture/test_repository_best_in_class_phase2_2_ops_runner_relocation.py`.
- Updated inventories and commands:
  `architecture/imports/dynamic.toml`, `architecture/generated_artifacts.toml`,
  root `.github/workflows/**`, workspace doctor/verify, release scripts, and
  generated tools reference.

Parallel safety:

- This phase owns `tools/**`/`ops/**` runner paths. Shared generated-artifact
  command edits that overlap Phase 2.1 are out of scope for this phase and move
  to the next wave as a short queue-owned patch.

#### Phase 2.3 - Runtime-State Schema And Cleanup

Scope:

- Add `.polisyos/SCHEMA.md` with purpose, owner, naming, format, retention,
  backup policy, safe cleanup command, and promotion policy for every existing
  `.polisyos` first-level directory.
- Expand local runtime-state architecture contracts to cover every state path.
- Normalize CAS paths under canonical `.polisyos/cas`, with cache under
  `.polisyos/cas/_cache` and readme/check artifacts under
  `.polisyos/cas/_readme_check` or a tool-owned validation directory.
- Add runtime-state migration slots for audit, idempotency, decision validity,
  search registry, provider verification, and future local persisted state.
- Add cleanup tooling with dry-run and summary output.

Acceptance:

- Every existing `.polisyos` first-level directory is registered.
- No new `.polisyos/<name>` can appear without a layout entry.
- Cleanup cannot delete production snapshots without explicit approval.

Parallel safety:

- Owns `.polisyos/**` documentation and cleanup. It can run with tests, docs,
  schemas, and JS moves if generated-artifact queues are untouched.

#### Phase 2.4 - Test Fixture, Helper, Golden, And Data Split

Scope:

- Move JSON/binary scenario data to `tests/_data/**`.
- Move Python fixture helpers to `tests/_helpers/**`, or explicitly redefine
  `tests/fixtures` as helper-code-only if the team rejects the rename.
- Move tests-of-fixtures such as fixture coverage checks to
  `tests/repo_quality/**`.
- Move golden records out of `tests/contract/**` into `tests/_golden/**` or
  `tests/_data/golden/**`.
- Update pytest collection, imports, fixtures, and docs.
- Preserve product API/schema contract tests under `tests/contract/**`.

Acceptance:

- No pytest-collectable `test_*.py` lives under data-only directories.
- Golden data updates produce review diffs separate from test logic changes.
- Test fixtures, test data, golden records, and product contract tests have
  distinct roots.

Parallel safety:

- This phase owns fixture, helper, golden, and data roots only. Pytest-root
  changes and repo-quality consolidation are out of scope and wait for
  Phase 3.5 or later.

#### Phase 2.5 - Schemas Code/Data Separation

Scope:

- Keep top-level `schemas/**` for JSON/YAML/OpenAPI snapshots only.
- Move Python wrappers out of top-level schemas:
  - `schemas/abi_models.py` to `src/polisyos/schemas/abi_models.py` or
    `src/polisyos/contracts/abi_models.py`;
  - remove `schemas/__init__.py`;
  - remove cache residue from local checkout.
- Update import paths, packaging config, generator commands, and any schema
  verification docs.
- Remove any need for ad hoc `sys.path.insert(0, "src")` caused by Python code
  living under top-level `schemas`.

Acceptance:

- `schemas/**` is not a Python package.
- Generated schema snapshots remain committed and verified.
- Codegen imports come from `polisyos.*`.
- `python -c "import schemas"` is not a supported product path.

Parallel safety:

- Owns `schemas/**` and schema imports. It should not merge with config-split
  changes that rewrite the same mypy/ruff paths.

#### Phase 2.6 - Documentation, ADR, Plan, And Archive Lifecycle Cleanup

Scope:

- Unify plan lifecycle:

```text
docs/plans/
  active/
  accepted/
  archive/
```

- Move or archive legacy `docs/archive/plans/**` content into
  `docs/plans/archive/**`.
- Move legacy `design/runtime-redesign/**` content into either
  `docs/plans/active/runtime-redesign.md` or
  `docs/explanation/runtime-redesign/`.
- Audit docs under migration that are actually release notes or changelog design
  notes and relocate them to release docs or changelog design docs.
- Move code currently under docs/archive into `tools/archive/**` if retained.
- Add `docs/adr/index.toml` with ADR id, title, status, topic, package,
  supersedes, superseded_by, and related.
- Generate `docs/adr/index.md`, `docs/adr/by-topic.md`, and a stale ADR link
  report.
- Keep `architecture/**` machine-readable by moving prose-only freeze docs under
  `architecture/policies` or docs with a pointer.
- Define archive/evidence/report classes for `docs/archive/reports` and
  benchmark reports: committed versus ignored, naming, retention, promotion
  criteria, and max size/file count.

Acceptance:

- Every active plan has status and owner.
- Every ADR is indexed by status and topic.
- Archive directories are evidence libraries, not dumping grounds.
- Docs nav changes are deferred to a separate queue or generated in small
  fragments.

Parallel safety:

- Owns docs lifecycle paths. It should not merge with docs-nav gate conversion
  or unrelated prose rewrites.

#### Phase 2.7 - JavaScript Workspace Topology Move

Scope:

- If Phase 1.1 is complete, move JS workspace paths to:

```text
policy-engine/
  apps/
    runtime-dashboard/
    runtime-reference-shell/
  packages/
    runtime-api-client/
    cli/
```

- Move app workspaces from `frontend/*` to `apps/*`.
- Move the legacy runtime API client workspace to `packages/runtime-api-client`.
- Update `pnpm-workspace.yaml`, `pnpm-lock.yaml`, package names, tsconfig
  references, generated client commands, CI, docs, and
  `architecture/frontend_workspaces.toml`.
- Keep redirects or contributor-handoff docs for old paths only if necessary.

Acceptance:

- All apps live under `apps`.
- All publishable JS libraries live under `packages`.
- Generated runtime API client commands still verify against OpenAPI snapshots.

Parallel safety:

- Singleton JS workspace queue. This is the only Wave 2 phase that may update
  `pnpm-lock.yaml`.

#### Phase 2.8 - Control-Plane Path-Prefix Cleanup

Scope:

- If root paths changed, update CODEOWNERS, rulesets, workflows, branch
  protection path assumptions, release workflow paths, security workflow paths,
  and ownership docs to the selected root topology.
- Remove retired path prefixes from CODEOWNERS.
- Ensure `.github/**`, CODEOWNERS, rulesets, release workflows, and security
  configs remain self-protected by repository owners.
- Align fast PR checks and release-gate checks with the new path layout.

Acceptance:

- CODEOWNERS, rulesets, and architecture owners agree after path moves.
- Protected branches require the intended checks and owned reviews.
- No control-plane file points at retired paths.

Parallel safety:

- Runs after Phase 1.1 and any relevant path moves. It should not merge with
  release-gate/security workflow changes from later phases.

#### Phase 2.9 - Directory Hygiene, Asset Placement, And Residue Cleanup

Scope:

- Remove or gate local residue: `.DS_Store`, `__pycache__`, egg-info, empty
  source/cache directories, wrong-root scratch, ignored source-adjacent report
  output, and stale local audit reports.
- Apply asset placement decisions:
  - product seed assets under package-owned `assets` or explicitly registered
    product `fixtures`;
  - test fixtures under `tests/_data` or package-local test fixture roots;
  - golden records under `tests/_golden` or registered snapshot roots;
  - examples/tutorial assets under installable examples.
- Rename product `fixtures` directories to `assets` or `seed_data` unless the
  package contract intentionally defines fixtures as runtime/product inputs.
- Add data-size and file-type budgets for committed product assets.
- Add stale local report cleanup command and promotion rules so local reports do
  not become accidental source of truth.

Acceptance:

- Product data, test data, golden snapshots, examples, local reports, and
  generated benchmark reports are reviewable as distinct classes.
- No committed or local source subtree has ambiguous cache/raw/errors fixture
  folders without a contract.

Parallel safety:

- Can run with docs, tests, schemas, and runtime-state cleanup when paths are
  disjoint. If it touches the same test fixture paths as Phase 2.4, split the
  patch and merge after Phase 2.4.

Wave 2 exit criteria:

- No low-risk move leaves stale generated-artifact commands, lockfile state,
  config overrides, docs references, or path-prefix references.
- Each phase owns a disjoint path fence or has moved to Wave 3.

### Wave 3 - Facade And Shim Closeout

Purpose: finish package-root discipline and compatibility-shim cost reduction
before deep decomposition. Fabric and IR can move in parallel because they own
separate source fences. Shim phases can run in parallel with those moves if they
do not touch the same shared registry patches.

#### Phase 3.1 - Fabric Root Facade Closeout

Scope:

- Create and execute a Fabric move map:
  - ingestion modules into `fabric/ingestion/`;
  - trust modules into `fabric/trust/`;
  - quality and safety into `fabric/quality/` or `fabric/governance/`;
  - registry into a scoped package or `_internal/registry.py`;
  - observability into a package-local adapter over canonical core
    observability;
  - config and compatibility into `_internal` or explicit facades.
- Preserve public imports through `fabric/api.py` and targeted re-export shims.
- Rewrite first-party imports to public Fabric surfaces where possible.
- Add root facade test that permits only `__init__.py`, `api.py`, and optional
  `_api.py` at the Fabric root.
- Update Fabric public-surface and import-contract inventories through the
  package contract queue.

Acceptance:

- `find src/polisyos/fabric -maxdepth 1 -type f -name '*.py'` returns only
  facade files.
- Fabric tests pass through public imports.
- Public-surface and import-contract gates remain green.

Parallel safety:

- Owns `src/polisyos/fabric/**` and Fabric tests. Shared package-contract edits
  merge as a short integration patch.

#### Phase 3.2 - IR Root Facade Closeout

Scope:

- Create and execute an IR move map:
  - canonicalization into `ir/canon/` or `ir/_internal/canon.py`;
  - citations and refs into `ir/references/`;
  - predicate, queries, and types into coherent contract packages;
  - units into `ir/units/`;
  - schema catalog into `ir/schemas/` or `ir/contracts/`;
  - public surface helpers into `ir/api.py`.
- Preserve import stability with targeted shims where public surface requires
  it.
- Rewrite first-party imports to public IR surfaces where possible.
- Add root facade test that permits only `__init__.py`, `api.py`, and optional
  `_api.py` at the IR root.
- Update IR public-surface and import-contract inventories through the package
  contract queue.

Acceptance:

- `find src/polisyos/ir -maxdepth 1 -type f -name '*.py'` returns only facade
  files.
- IR tests pass through public imports.
- Public-surface and import-contract gates remain green.

Parallel safety:

- Owns `src/polisyos/ir/**` and IR tests. Shared package-contract edits merge
  after local moves are stable.

#### Phase 3.3 - DDM Compatibility Shim Test Collapse

Scope:

- Inventory first-party and documented external imports of `polisyos.ddm_15_7`.
- Rewrite first-party source and tests to `polisyos.ddm`.
- Collapse `tests/unit/ddm_15_7/**` to one shim contract smoke test.
- Keep or remove the shim according to the existing 2026-10-01 sunset policy.
- Update docs, examples, shim dashboard, and import-boundary exceptions.

Acceptance:

- `ddm_15_7` is wrapper-only and has only facade smoke coverage.
- No first-party code deep-imports through `ddm_15_7`.
- The shim has owner, target, sunset, and issue/ADR reference.

Phase 3.3 closeout:

- First-party import inventory leaves only
  `tests/unit/ddm_15_7/test_shim.py` importing the root compatibility facade.
- DDM behavior tests moved to `tests/unit/ddm/**` and import `polisyos.ddm`.
- The shim remains until the 2026-10-01 sunset per ADR-RSR-0135 and
  `ddm-15-7-rename`.

Parallel safety:

- Owns DDM shim imports and tests. It does not edit shared shim registry entries
  that are also touched by Phase 3.4; overlapping shim registry cleanup moves to
  Phase 6.5.

#### Phase 3.4 - Synthetic World Compatibility Shim Test Collapse

Scope:

- Inventory first-party and documented external imports of
  `polisyos.synthetic_world`.
- Rewrite first-party source and tests to
  `polisyos.foundry.agent_sim.world`.
- Collapse shim tests to one smoke contract.
- Update docs, examples, shim dashboard, and import-boundary exceptions.
- Keep or remove the shim according to the existing 2026-10-01 sunset policy.

Acceptance:

- `synthetic_world` is wrapper-only and has only facade smoke coverage.
- No first-party code deep-imports through `synthetic_world`.
- The shim has owner, target, sunset, and issue/ADR reference.

Parallel safety:

- Owns Synthetic World shim imports and tests. It does not edit shared shim
  registry entries that are also touched by Phase 3.3; overlapping shim registry
  cleanup moves to Phase 6.5.

#### Phase 3.5 - Repo-Quality Test Consolidation

Scope:

- Consolidate structure, lint, and tool tests under:

```text
tests/repo_quality/
  architecture/
  lint/
  tools/
```

- Keep `tests/contract/**` for product API and schema contracts.
- Update test docs, pytest collection, and test topology contract.
- Preserve package behavior tests under unit/integration/property/e2e roots.

Acceptance:

- A contributor can tell whether a failure is product behavior, product
  contract, or repository quality.
- `tests/repo_quality/architecture`, `tests/lint`, and `tests/tools` ambiguity is removed or
  explicitly redirected.

Parallel safety:

- Runs after Phase 2.4. Fixture/golden moves and pytest-root changes are out of
  scope for this phase.

#### Phase 3.6 - Dead Override Report-Only Gate

Scope:

- Add report-only checks for stale mypy and ruff per-file overrides:
  - every per-file override path exists;
  - every exception has owner and sunset or permanent rationale;
  - moved files produce override cleanup warnings;
  - deleted files cannot leave silent tool-config debt.
- Ensure package moves can run the report without failing while paths are still
  changing.

Acceptance:

- Moving or deleting a file produces visible override debt if config entries are
  stale.
- The gate remains report-only until source paths stabilize.

Parallel safety:

- Owns tooling reports only. It should not split `mypy.ini`, `ruff.toml`, or
  `mkdocs.yml` yet.

Wave 3 exit criteria:

- Fabric and IR obey root-facade policy.
- Wrapper-only shims no longer carry broad unit-test tax.
- Package contract queue has absorbed short public-surface and shim patches.

### Wave 4 - Parallel Deep Decomposition Lanes

Purpose: run large package reorganizations in disjoint source lanes. Wave 4 is
where parallelism matters most. Each phase must avoid shared public facades,
shared registries, lockfiles, and shared shim files. Integration work that
cannot stay disjoint moves to Wave 5.

#### Phase 4.1 - Foundry Executor Lane

Scope:

- Move private executor siblings into one executor/execute ownership zone:
  `_executor_graph`, `_executor_models`, `_executor_ops`,
  `_executor_patching`, `_executor_snapshots`, `_execution_posture`, and
  `_numeric`.
- Preferred target:

```text
src/polisyos/foundry/executor/
  api.py
  _internal/
    graph/
    models/
    ops/
    patching/
    snapshots/
    posture/
    numeric/
```

- If the current canonical package is `execute/`, align naming through an ADR
  before moving. Do not leave `executor` and `execute` as equal roots without a
  public distinction.
- Add targeted re-export shims for public imports only.
- Add import-cycle and dynamic-import verification.
- Do not touch method discovery or Foundry extension registry in this lane.

Acceptance:

- No `_executor_*` sibling packages remain under `foundry`.
- Executor private implementation lives under one owner boundary.
- Foundry executor tests pass without deep-importing old private paths.

Parallel safety:

- Owns executor/execute internals only. Method discovery, registry, and
  `foundry/api.py` integration move to later phases if needed.

#### Phase 4.2 - Foundry Methods Taxonomy Lane

Scope:

- Split `foundry/methods` root into clear subpackages:

```text
foundry/methods/
  api.py
  artifacts/
  bayesian/
  causal/
  compiler/
  components/
  econometrics/
  lifecycle/
  selection/
  catalog/
  equivalence/
  backends/
  _internal/
```

- Move loose implementation files:
  - `_artifacts_*` and `artifacts*.py` into `artifacts/`;
  - `compiler.py`, `hot_reload.py`, and `layout.py` into `compiler/`;
  - `compat.py`, `deprecation.py`, and `lifecycle.py` into `lifecycle/`;
  - `components_bridge.py`, composer helpers, and component helpers into
    `components/`;
  - selection, resolution, and registry helpers into `selection/` or the future
    extension area.
- Keep catalog domain subpackages stable unless a move directly reduces imports.
- Add README/AUTHORING coverage for major method subpackages.
- Exclude extension registry consolidation from this phase.

Acceptance:

- Methods root contains facade and high-level coordination files only.
- New method families have a documented home.
- Method registration path is explicit enough for Wave 5 integration.

Parallel safety:

- Owns `foundry/methods/**` taxonomy only. If a patch needs registry/discovery
  changes, split those changes into Phase 5.1.

#### Phase 4.3 - Characterization Tests And God-Module Budgets

Scope:

- Add characterization tests before extracting high-debt modules.
- Add module-size budget exceptions with current line count, target line count,
  owner, extraction sequence, and risk notes.
- Extract later by cohesive responsibility, not arbitrary line chunks:
  models/contracts, validation, graph transforms, estimand compilation,
  diagnostics, execution adapters, and serialization.
- Initial Foundry focus:
  - `foundry/methods/catalog/causal/causal_engine.py`;
  - `foundry/methods/catalog/causal/interference.py`;
  - `foundry/methods/catalog/causal/id_engine.py`;
  - `foundry/methods/selection.py`;
  - large causal catalog helpers above the module-size threshold.
- Cross-package inventory remains aware of Data Forge, Scientist, and Runtime
  god modules but physical splits wait until appropriate owners are ready.

Acceptance:

- No modified god module grows in line count.
- At least one high-debt module has characterization tests and a shrink plan.
- Extracted modules, when introduced later, have direct tests.

Parallel safety:

- Test and budget work can merge before or alongside Phase 4.1/4.2 if it does
  not rewrite the same source files.

#### Phase 4.4 - Scientist Feedback, Evidence, And Replay Lane

Scope:

- Consolidate close semantic pairs:
  - `feedback` and `feedback_utils`;
  - `replay` and `replay_backend`;
  - `evidence` and `evidence_sources`;
  - related claims and provenance helpers under the chosen evidence boundary.
- Preserve public imports with targeted shims and sunset metadata.
- Add local README/AUTHORING for the new hubs.
- Rewrite first-party imports away from soon-to-be-shimmed old paths.
- Do not touch `scientist/api.py` in this lane except through a later shared
  integration patch.

Acceptance:

- Feedback, replay, and evidence concepts have one obvious home each.
- Tests mirror the new taxonomy.
- Moved public imports have targeted shims and sunset.

Parallel safety:

- Owns only the listed Scientist subtrees and their tests. Shared facade edits
  wait for Phase 5.2.

#### Phase 4.5 - Scientist Engine, LLM, Compute, And Orchestration Lane

Scope:

- Consolidate `llm` and `llm_cycle`.
- Group compute, memory, kernel, frontier runtime, engine, and orchestration
  internals into clear `compute/` and `orchestration/` boundaries.
- Separate domain methods such as causal, DOE, autotune, and backtesting under
  `scientist/methods/` where appropriate.
- Preserve public imports with targeted shims and sunset metadata.
- Do not touch governance entry points or node extension registration.

Acceptance:

- Infrastructure and domain-method code are not mixed at the first level.
- Tests mirror the new taxonomy.
- First-level Scientist package count drops materially without hiding unrelated
  concepts in a vague `_internal`.

Parallel safety:

- Owns LLM/compute/orchestration paths only. Shared API changes move to
  Phase 5.2.

#### Phase 4.6 - Scientist Governance And Validation Lane

Scope:

- Consolidate governance, continuous governance, human review, decision
  validity, validation, verification, and policy verified under clear
  governance and validation boundaries.
- Preserve governance pass behavior and existing public imports through targeted
  shims.
- Update tests and local docs for the new governance/validation hubs.
- Do not change node extension registration in this phase.

Acceptance:

- Governance and validation have explicit homes and no duplicate first-level
  package naming.
- Governance pass behavior remains covered.
- Name-registry backlog for governance/validation is reduced.

Parallel safety:

- Owns governance/validation paths only. Entry-point integration waits for
  Phase 5.2.

#### Phase 4.7 - Scientist Search, Discovery, Research DAG, And Methods Lane

Scope:

- Consolidate discovery, search, research DAG, workflow selection, and related
  strategy subpackages under an orchestration or methods boundary chosen in
  Wave 1.
- Preserve public imports with targeted shims and sunset metadata.
- Update package README/AUTHORING and tests.
- Reduce `name_registry.toml` backlog for runtime/discovery collisions.

Acceptance:

- Search/discovery/research DAG no longer appear as unrelated first-level
  concepts.
- Public imports remain stable or have time-boxed shims.

Parallel safety:

- Owns search/discovery-related Scientist paths only. Shared Scientist API
  changes wait for Phase 5.2.

#### Phase 4.8 - Cross-Cutting Concern Adapters And Naming Hygiene

Scope:

- For each shared concern, decide one of canonical interface plus package
  adapters, intentionally package-local bounded context, or rename to remove
  ambiguity.
- Start with observability, security, registry, discovery, governance,
  contracts, calibration, runtime, and trace.
- Add `cross_cutting_concerns.toml` or extend `name_registry.toml` with
  canonical owner, allowed adapters, import rule, public/private status, and
  sunset for unresolved collisions.
- Add package-local adapters over canonical contracts where a global concept is
  real, such as observability or security.
- Avoid mechanical renames where the same word is semantically correct inside a
  bounded context. Require a documented semantic axis.

Acceptance:

- No unregistered shared package names remain.
- No shared name lacks disambiguation.
- Global concepts have one canonical interface and package-local adapters.

Parallel safety:

- Contract/adapters only. If a change rewrites multiple package facades, split
  it and merge through the package contract queue.

#### Phase 4.9 - Operability Bundle Drafts

Scope:

- Add component SLO/runbook/alert/dashboard bundles that remain valid under old
  and new component aliases.
- Add SLO files or explicit exceptions for missing public-stable packages:
  core, ir, foundry, lex, scholar, berl, ddm, and calibration.
- Add component README/runbook links, escalation, alert mapping, dashboard
  mapping, runtime-contract links, and retention-policy links.
- Keep bundle drafts compatible with the selected ops organization from
  Phase 1.6.

Acceptance:

- Every public-stable component has at least one runbook and one SLO or an
  explicit exception.
- Every alert maps to a runbook.
- Bundle paths are stable enough for Wave 6 gate conversion.

Parallel safety:

- Owns component operability docs/configs. Release/security gates are out of
  scope and wait for Wave 6.

#### Phase 4.10 - Directory, Frontend, README, And Authoring Docs

Scope:

- Add README, AUTHORING, or generated index files for high-volume source, test,
  frontend, schema, and archive subtrees identified in Phase 0.7.
- README/AUTHORING must describe purpose, allowed file categories,
  public/private boundary, local naming convention, test location,
  fixture/data policy, generated-file policy, extension point if any, and
  deprecation/shim policy if any.
- Add package README template fields:
  - purpose;
  - public API;
  - internal layout;
  - extension points;
  - tests;
  - operability links;
  - known shims/deprecations.
- Require README coverage for every public-stable package, every extension
  host, every package with more than 20 Python files, and every package
  containing a module over the warning size threshold.
- Add frontend subtree contracts for app shell, feature modules, shared UI,
  shared charts, API client/hooks, test helpers/fixtures, and generated API
  types.
- Define frontend feature module convention: domain, components, routes, hooks,
  API/generated client boundary, and tests/story fixtures if retained.

Acceptance:

- No high-volume subtree remains undocumented after closeout unless it has an
  owner/sunset exception.
- Frontend structure has the same long-term closure as Python source.
- Future UI work can add features without re-litigating shared UI, generated
  API hooks, and test fixture placement.

Parallel safety:

- Documentation-only and path-local. Docs nav generation waits for Phase 6.4.

Wave 4 exit criteria:

- No two Wave 4 phases modify the same package facade, registry, entry-point
  group, lockfile, shared shim, or generated command map in the same merge
  window.
- Shared API/registry integration that cannot stay disjoint has moved to Wave 5.

### Wave 5 - Integration, Extension, And Ratchet Tightening

Purpose: integrate Wave 4 source lanes and begin tightening report-only gates.
These phases remain parallel by keeping shared queue overlaps out of the phase
scope. If two integration phases need the same shared queue entry, the later
gate wiring moves to Wave 6.

#### Phase 5.1 - Foundry Extension Registry Integration

Scope:

- Create canonical `foundry/extensions/`:

```text
foundry/extensions/
  __init__.py
  api.py
  discovery.py
  registry.py
  _builtin_loader.py
```

- Fold or redirect `foundry/plugins`, `foundry/registry`,
  `foundry/_registry.py`, and implicit catalog discovery.
- Define and wire the `polisyos.foundry_methods` entry point.
- Register builtin methods through the same path as external plugins.
- Update examples and docs for external method authors.

Acceptance:

- External method authors follow one documented interface.
- Builtins and external methods use one registration mental model.
- Old registry paths are shims or removed with sunset.

Parallel safety:

- Singleton Foundry registry/discovery integration. Phase 4.2 must have already
  landed any method taxonomy work that would touch discovery or registry code.

#### Phase 5.2 - Scientist API And Node Extension Integration

Scope:

- Integrate Scientist lanes into the target taxonomy:

```text
scientist/
  api.py
  orchestration/
  methods/
  governance/
  evidence/
  feedback/
  replay/
  llm/
  compute/
  publishing/
  validation/
  nodes/
  _internal/
```

- Update `scientist/api.py`, governance pass entry points, node extension
  registration, public shims, and shared Scientist package contracts after Wave
  4 lanes settle.
- Keep `nodes/` stable while adding extension registration for external nodes.
- Define or wire `polisyos.scientist_nodes` and related governance pass
  discovery.
- Add package README files for new major hubs.

Acceptance:

- First-level Scientist package count drops materially.
- Tests mirror the new taxonomy.
- Every moved public import has targeted shim and sunset.
- Node and governance extension registration are explicit.

Parallel safety:

- Singleton Scientist API/entry-point integration. It waits until conflicting
  Wave 4 Scientist lanes are merged.

#### Phase 5.3 - Mirror And Property-Test Expansion

Scope:

- Add or ratchet property coverage for Fabric, Lex, Data Forge, and other
  data-contract-heavy packages with explicit exceptions.
- Increase mirror coverage package by package from measured baselines.
- Add integration coverage decisions for packages whose behavior is cross-layer
  rather than one-file mirrorable.
- Keep runtime over-coverage normalized through explicit behavior-test mapping.

Acceptance:

- CI reports mirror ratio and property coverage deltas.
- Mirror ratio cannot regress without exception.
- New package moves include characterization or mirror tests before ratchets
  become fail-closed.

Parallel safety:

- Owns test additions and report-only ratchets. Pytest-root and fixture
  directory moves are out of scope for this phase.

#### Phase 5.4 - First God-Module Splits

Scope:

- Execute first extractions from the high-debt module backlog using
  characterization tests from Wave 4.
- Initial priority files:
  - `src/polisyos/foundry/methods/catalog/causal/causal_engine.py`;
  - `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py`;
  - `src/polisyos/foundry/methods/catalog/causal/interference.py`;
  - `src/polisyos/foundry/methods/catalog/causal/id_engine.py`;
  - `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py`;
  - `src/polisyos/data_forge/domains/academic/batch/resolve_extract.py`;
  - `src/polisyos/runtime/http/services/control.py`.
- Extract by cohesive responsibilities: models/contracts, validation, graph
  transforms, estimand compilation, diagnostics, execution adapters,
  serialization, IO adapters, and service orchestration.
- Keep module-size budgets shrinking and update tests directly against new
  modules.

Acceptance:

- No new module over the warning threshold appears without a budget exception.
- No existing high-debt module grows unless its exception budget is updated.
- Each split preserves behavior through characterization tests.

Parallel safety:

- One god-module split per source path fence. Do not combine unrelated domain
  extractions in one PR.

#### Phase 5.5 - Tool Config Split

Scope:

- Split `mypy.ini` into core project config, generated or grouped per-package
  overrides, and exception registry with owner/sunset.
- Split `ruff.toml` into base rules, per-file exceptions under architecture
  exception policy, and generated ignore fragments if supported.
- Split `mkdocs.yml` nav into maintainable fragments or generated nav if the
  selected tooling supports it.
- Wire the dead-override report from Phase 3.6 into the new config structure.

Acceptance:

- Deleting or moving a file cannot leave stale mypy/ruff overrides silently.
- Root config files read as policy, not debt ledgers.
- MkDocs nav changes are generated or reviewable in small fragments.

Implementation:

- Phase 5.5 source fragments live under `architecture/tooling/` and are
  generated with `uv run polisyos-tools workspace tool-configs`.
- `mypy.ini`, `ruff.toml`, and `mkdocs.yml` are root policy stubs; operational
  mypy/Ruff overrides and MkDocs nav are generated into
  `architecture/tooling/**/generated.*`.
- `uv run polisyos-tools workspace tool-configs --check` verifies generated
  config drift and fails if the Phase 3.6 dead-override report finds stale
  mypy/Ruff targets.

Parallel safety:

- Runs after major path moves stabilize. It should not merge with package moves
  that rewrite the same mypy/ruff paths.

#### Phase 5.6 - Migrations And Release Topology

Scope:

- Expand migrations to:

```text
ops/migrations/
  db/
  runtime_state/
  api_schemas/
  ir/
```

- Connect Python migration helpers to operational migration contracts.
- Add `ops/release/deployment-topology.toml` for control-plane, data-plane,
  frontend, CLI, and package artifacts.
- Add `ops/release/promotion-gates.toml` for staging-to-production checks.
- Ensure migration/runbook docs exist before release promotion for breaking
  runtime-state, schema, IR, or persisted artifact changes.

Acceptance:

- Operator guidance covers DB schema, runtime-state schema, API schema, and IR
  schema migrations.
- Release promotion has declared topology and gates.

Parallel safety:

- Owns ops migration and release topology contracts. Supply-chain workflow
  changes that touch the same release files are out of scope here and move to
  Phase 6.3.

#### Phase 5.7 - Package README Coverage

Scope:

- Fill README/AUTHORING gaps for public-stable and high-complexity packages.
- Start with `foundry/methods/catalog/causal`, `foundry/methods`,
  `scientist/nodes`, `data_forge/domains/catalog/batch`,
  `runtime/http/services`, and Fabric/IR after facade cleanup.
- Link package READMEs to public API, internal layout, extension points, tests,
  operability docs, and known shims/deprecations.

Acceptance:

- README coverage report passes for public-stable and high-complexity packages
  or lists explicit owner/sunset exceptions.

Parallel safety:

- Documentation-only. It can run with most Wave 5 phases if docs nav is not
  changed.

#### Phase 5.8 - Per-Package Architecture Files

Scope:

- Introduce or generate per-package architecture contracts after path moves are
  stable.
- Ensure each file carries owner, layout status, boundaries, public surface,
  test expectations, SLO/runbook expectations, allowed name collisions,
  exceptions, sunsets, and extension host status.
- Keep aggregate legacy TOML generated or mirrored until fail-closed gates
  switch to the new source of truth.

Acceptance:

- Adding or changing a package requires one primary package contract file.
- Aggregated contracts and per-package contracts agree.

Parallel safety:

- Package contract queue only. Avoid concurrent edits to the same package
  contract.

#### Phase 5.9 - Supply-Chain Closeout

Scope:

- Add SBOM generation policy for release candidates and dependency-lock changes.
- Add provenance/attestation targets per artifact type and signed release
  artifact expectations where tooling supports it.
- Harden workflow permissions to least privilege and require explicit `id-token`
  only for OIDC workflows.
- Map dependency/security scan gates to release phases.
- Add external Scorecard/SLSA-style control crosswalk as a reporting artifact.

Acceptance:

- Release candidates have SBOM/provenance expectations tied to generated
  artifact contracts.
- Workflow permissions are explicit and least-privilege by default.

Artifact:

- Status: completed on 2026-05-06.
- `architecture/control_plane_supply_chain.toml` defines the Phase 5.9
  SBOM/provenance/signing, scan-gate, exact OIDC, and workflow write-permission
  contract.
- `docs/archive/reports/supply-chain-control-crosswalk.json` is the generated
  Scorecard/SLSA-style reporting crosswalk.

Parallel safety:

- Owns supply-chain policy and security workflows. Serialize with release
  topology and control-plane changes.

#### Phase 5.10 - Compatibility Release Gates

Scope:

- Add compatibility metadata to extension points, generated schema manifests,
  runtime-state migrations, release templates, and package public-surface
  contracts.
- Add release promotion checks:
  - every breaking compatibility class has a release fragment;
  - migration/runbook docs exist before release;
  - public-surface inventory is regenerated and reviewed;
  - generated client compatibility is declared.
- Ensure deprecation windows cover shim packages, renamed public imports,
  extension contract versions, runtime-state migration readers, and generated
  client compatibility.

Acceptance:

- Every compatibility promise has a version owner and deprecation window.
- Release notes can be generated from structured compatibility changes.

Parallel safety:

- Owns compatibility metadata and report-only release checks. If implementation
  needs the same release gate files as Phase 5.6 or Phase 5.9, that gate wiring
  moves to Phase 6.3.

Wave 5 exit criteria:

- All integration points from Wave 4 are merged.
- Report-only gates have at least one stable green run.
- No ratchet becomes fail-closed before its owned paths stabilize.

### Wave 6 - Fail-Closed Gate Conversion

Purpose: convert stable report-only checks into durable guardrails. Wave 6
phases are parallel when they convert disjoint gate families. Any gate that
touches an active source-move area waits.

#### Phase 6.1 - Package, Public Surface, And Import Gate Conversion

Scope:

- Convert root-facade gates for active packages after Fabric, IR, Foundry, and
  Scientist moves hold green.
- Convert package-boundary, public-surface, deep-import, dynamic-import,
  import-cycle, package layout, name-collision, and shim-expiry gates.
- Enforce:
  - every first-party import from another package targets that package's public
    API unless registered;
  - deep imports into implementation subpackages require owner, reason, and
    sunset;
  - no new forbidden edges;
  - no new unregistered dynamic imports;
  - no new import cycles;
  - re-export shims count toward shim debt.

Acceptance:

- Import-boundary gate reports package-level deltas, not only pass/fail.
- Public-surface inventory and import contracts agree after facade moves.
- No decomposition PR can increase hidden coupling without explicit exception.

Artifact:

- Status: completed on 2026-05-06.
- `architecture/gates/package_import.toml` defines the fail-closed Phase 6.1
  conversion contract and converted package/import gate set.
- `polisyos-tools validation check-package-import-gates --fail-closed`
  validates package-level import-boundary deltas, public-surface/import-contract
  agreement, package-boundary forbidden edges, dynamic imports, import cycles,
  package layout, name collisions, and shim expiry.
- `.github/workflows/abi.yml` runs the Phase 6.1 gate after the import policy
  lint and before package-level quality checks.

Parallel safety:

- Do not run fail-closed package gates while active package move branches are
  still merging.

#### Phase 6.2 - Test, Benchmark, Directory, And Hygiene Gate Conversion

Scope:

- Convert mirror-ratio, no-regression, property-test, fixture/golden,
  repo-quality, pytest-root, and benchmark-role gates.
- Convert directory closure gates:
  - no new top-level directory without a contract;
  - no new top-level loose file outside allow-list;
  - no committed file under a directory whose lifecycle forbids it;
  - no local ignored residue in source/docs/schemas/test paths during
    repo-quality checks;
  - no new `__init__.py` outside allowed non-product roots;
  - product code may not import from tests or benchmarks without exception;
  - no data-only directory contains pytest-collectable tests;
  - no test fixture directories under frontend `src` unless registered;
  - no generated API client/types outside registered generated paths;
  - no empty UI component directories;
  - no feature module over threshold without owner.
- Add directory health dashboard metrics:
  - top-level directory contract coverage;
  - high-volume subtree documentation coverage;
  - non-product Python root inventory;
  - local residue count by class;
  - empty directory count outside ignored roots;
  - product asset/test fixture/golden/example counts;
  - undocumented frontend subtree count;
  - archive/report promotion backlog;
  - maximum directory depth by root;
  - largest subtrees by tracked file count.

Acceptance:

- Directory health can regress only through explicit exception.
- Every future structural PR can be reviewed against stable directory contracts.
- Benchmark, fixture, golden, and repo-quality tests have durable roots.

Artifact:

- Status: completed on 2026-05-06.
- `architecture/policies/directory_health.toml` is fail-closed with top-level path moves
  inactive and the top-level directory contract gate enabled.
- `polisyos-tools validation directory-health --fail-on-regression` fails on
  contract errors, metric regressions, and fail-closed closure findings.

Parallel safety:

- Do not enable fail-closed directory gates while top-level path moves are still
  active.

#### Phase 6.3 - Operability, Release, And Supply-Chain Gate Conversion

Scope:

- Convert SLO/runbook coverage, component observability, alert-to-runbook,
  migration class, release topology, promotion gate, SBOM, provenance,
  workflow-permission, OIDC, and release security checks.
- Require every public-stable component to have SLO/runbook coverage or explicit
  exception.
- Require release promotion to verify deployment topology, migration docs,
  compatibility metadata, release fragments, SBOM/provenance, and security
  gates.

Acceptance:

- Every alert maps to a runbook.
- Release promotion has declared topology and gates.
- Release candidates satisfy supply-chain expectations or have explicit
  exception.

Artifact:

- Status: completed on 2026-05-06.
- `architecture/gates/operability_release_supply_chain.toml` defines the
  fail-closed Phase 6.3 conversion contract and source-contract set.
- `polisyos-tools release check-operability-release-gates --fail-closed`
  validates SLO/runbook coverage, component observability, alert-to-runbook
  mappings, migration classes, release topology, promotion gates, compatibility
  release metadata, release fragments, workflow permissions, OIDC, SBOM,
  provenance, and release security gates.
- `.github/workflows/release.yml` runs the Phase 6.3 gate before build,
  supply-chain, signing, attestation, and publish jobs.

Parallel safety:

- Operability gates can run with docs/test gates if workflow and release files
  are disjoint. Security workflow edits serialize through the ops security
  queue.

#### Phase 6.4 - Documentation, Navigation, ADR, Examples, And README Gate Conversion

Scope:

- Convert ADR index, docs lifecycle, docs nav, stale ADR link, active-plan
  status/owner, archive/report promotion, example installability, extension
  example discovery, and README/AUTHORING coverage gates.
- Ensure installable examples exist for:
  - custom Fabric connector;
  - custom Foundry method;
  - custom Scientist node;
  - custom Data Forge domain;
  - custom Lex norm pack;
  - custom Runtime middleware.
- Add CI smoke tests that install each example in editable mode and verify
  discovery.

Acceptance:

- Examples are executable verification assets, not static snippets.
- Every ADR is indexed by status and topic.
- Docs nav changes are generated or small and reviewable.
- README coverage gate checks public-stable and high-complexity packages.

Artifact:

- Status: completed on 2026-05-06.
- `polisyos-tools validation check-docs-lifecycle` validates ADR indexing,
  docs nav tokens, active-plan metadata, archive/report promotion, and
  README/AUTHORING coverage.
- `polisyos-tools validation check-extension-examples` installs all six
  extension examples in editable mode and verifies entry-point discovery.

Parallel safety:

- Docs nav queue only. Do not combine generated nav changes with unrelated
  prose rewrites.

#### Phase 6.5 - Exception And Sunset Cleanup

Scope:

- Close expired exceptions across shims, package boundaries, public surface,
  dynamic imports, module-size budgets, docs coverage, SLO/runbook coverage,
  directory contracts, tool overrides, and generated-artifact contracts.
- Remove retired shim references and stale import redirects whose sunset has
  passed.
- Keep only dated exceptions with owner, rationale, target removal date, and
  issue/ADR reference.
- Fail closed on expired shims unless an exception has a new owner and ADR.

Acceptance:

- No expired exception remains without owner-approved renewal.
- Wrapper-only shims are either removed or explicitly time-boxed.
- Exception registries are smaller and reviewable.

Artifact:

- Status: completed on 2026-05-06.
- `architecture/wave6_gate_green_runs.toml` records the Wave 6 two-green-run
  ledger and confirms no active source move waits on a report-only gate.
- Existing shim, boundary, directory, docs, tooling, and generated-artifact
  exception registries are covered by the Wave 6 fail-closed checks and the
  repository SOTA closeout command.

Parallel safety:

- Exception cleanup serializes per registry. Do not close exceptions for an area
  whose physical moves are still active.

Wave 6 exit criteria:

- Every converted gate has two consecutive green runs or an explicit owner/date
  exception.
- No active source move waits on a report-only version of the same gate.

Artifact:

- Status: completed on 2026-05-06.
- `architecture/wave6_gate_green_runs.toml` is the closeout ledger for Wave 6
  exit criteria.

### Wave 7 - Final Closeout

Purpose: one final integration window after all parallel lanes are done.

#### Phase 7.1 - Final Verification And Closeout Artifact

Scope:

- Run final verification commands and any generated reports listed below.
- Update plan statuses and subplan links.
- Publish before/after metrics:
  - root policy violations;
  - root facade violations;
  - shim count and days to sunset;
  - mirror-test ratios;
  - module-size debt;
  - SLO/runbook coverage;
  - stale override count;
  - generated-artifact freshness;
  - CODEOWNERS coverage;
  - directory-health coverage.
- List unresolved exceptions with owner, rationale, and sunset.
- Archive or accept the closeout report under the final docs lifecycle.

Acceptance:

- The repository has no unresolved structural ambiguity outside explicitly owned
  exceptions.
- Future work can focus on product logic rather than layout remediation.

Parallel safety:

- Final singleton integration window after all active remediation branches
  settle.

Artifact:

- Status: accepted final closeout on 2026-05-06.
- Closeout archive:
  [2026-05-06 Repository Best-In-Class Wave 7 Closeout](../archive/2026-05-06-repository-best-in-class-wave7-closeout.md).
- Evidence directory: `_build/.tmp/wave7-closeout/`.
- Final program acceptance is fully closed for repository-layout remediation:
  Scientist repo-quality gates target the canonical topology, directory-health
  coverage is fully documented, acceptance audit manual evidence has 0 pending
  checks, and the phase PR ledger is recorded in the closeout archive.

## Finding Ledger

This is the single master ledger for repository-level remediation. Detailed
child findings inside subplans inherit their subplan row until they cross a
master-owned fence, shared registry queue, public-surface boundary, or release
gate; crossing findings must receive a specific master row before merge.

| Finding ID | Finding | Source audit | Severity | Owner | Primary path fence | Dependencies | Target wave | Target phase(s) | Acceptance gate | Rollback note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REP-001 | Product root half-state can make tools, docs, and CI disagree. | Audit Baseline 2026-05-05 | P0 | team-platform | root/control plane | none | W0-W2 | 0.2, 1.1, 2.1, 2.8 | Product root decision exists and wrong-root residue is either allowed, moved, or cleaned. | Revert root contract/path-prefix patches; no package source move is bundled. |
| REP-002 | Outer-root cache/tmp residue creates false root signals. | Audit Baseline 2026-05-05 | P3 | team-platform | lifecycle/output | REP-001 | W0-W2 | 0.2, 2.1, 2.9 | Root residue report is empty or lists owned ignored paths with retention. | Revert cleanup command or ignore rule patch; committed source is untouched. |
| REP-003 | Release inputs and ignored generated outputs are easy to confuse. | Audit Baseline 2026-05-05 | P0 | team-ops | lifecycle/output | 1.2 decision | W1-W6 | 1.2, 2.1, 5.10, 6.3 | Generated-artifact freshness gate distinguishes committed release input from generated output. | Revert lifecycle contract and generated-artifact queue patch. |
| REP-004 | Fabric package root has implementation files instead of facade-only layout. | Audit Baseline 2026-05-05; Fabric subplan | P1 | team-fabric | package source: `fabric` | 0.5 inventory | W3-W6 | 3.1, 6.1 | Fabric root facade gate permits only facade files and Fabric tests pass through public imports. | Restore moved files through Fabric move map and keep public shims. |
| REP-005 | IR package root has implementation files instead of facade-only layout. | Audit Baseline 2026-05-05; IR subplan | P1 | team-ir | package source: `ir` | 0.5 inventory | W3-W6 | 3.2, 6.1 | IR root facade gate permits only facade files and IR tests pass through public imports. | Restore moved files through IR move map and keep public shims. |
| REP-006 | Foundry executor private siblings blur ownership. | Audit Baseline 2026-05-05; Foundry subplan | P1 | team-foundry | package source: Foundry executor | 0.5 inventory | W4 | 4.1 | No `_executor_*` sibling packages remain and executor tests avoid old private paths. | Revert executor move map and leave targeted re-export shims. |
| REP-007 | Foundry methods root is too broad and catalog discovery risks sprawl. | Audit Baseline 2026-05-05; Foundry subplan | P2 | team-foundry | package source: Foundry methods | 0.5 inventory | W4-W5 | 4.2, 5.1 | Methods root has documented taxonomy and one extension registration mental model. | Revert taxonomy-only moves separately from registry integration. |
| REP-008 | Scientist first-level package count and duplicate names create cognitive load. | Audit Baseline 2026-05-05; Scientist subplan | P2 | team-scientist | package source: `scientist` | 0.5 inventory | W4-W5 | 4.4, 4.5, 4.6, 4.7, 5.2 | Scientist taxonomy is grouped and public imports have targeted shims with sunset. | Revert the affected lane only; shared `scientist/api.py` changes are isolated. |
| REP-009 | Cross-cutting names such as governance, contracts, runtime, and trace lack canonical ownership. | Audit Baseline 2026-05-05 | P2 | team-architecture | architecture/contracts | 0.3 inventory | W1-W6 | 1.3, 4.8, 6.1 | Name registry or concern contract names canonical owner, adapters, and allowed collisions. | Revert naming contract/adapters; no broad mechanical rename is bundled. |
| REP-010 | Test topology enforces presence but not mirror ratios or helper/data separation. | Audit Baseline 2026-05-05 | P2 | team-quality | tests: topology and reports | 0.4 baseline | W0-W6 | 0.4, 1.4, 5.3, 6.2 | Mirror-ratio and no-regression reports are green or carry dated exceptions. | Revert ratchet threshold patch; test additions remain if still valid. |
| REP-011 | Fixtures, golden data, helpers, and contract tests are mixed. | Audit Baseline 2026-05-05 | P2 | team-quality | tests: fixtures/golden/data | 1.4 contract | W2-W6 | 2.4, 6.2 | Data-only roots contain no pytest-collectable tests and golden diffs are separated. | Revert path move map and preserve product contract test roots. |
| REP-012 | Benchmarks look source-like and have ambiguous pytest role. | Audit Baseline 2026-05-05 | P2 | team-quality | tests: topology and benchmarks | 0.4 baseline | W1-W6 | 1.4, 6.2 | Benchmark role is declared and collection roots match the selected shape. | Revert benchmark topology contract; no product code move is bundled. |
| REP-013 | JS apps and libraries are mixed under `frontend`. | Audit Baseline 2026-05-05; Frontend subplan | P2 | team-frontend | frontend | 1.1 root decision | W2-W6 | 2.7, 4.10, 6.2 | Apps live under apps and publishable libraries under packages, or an explicit exception exists. | Revert JS move with lockfile queue owner and preserve generated client commands. |
| REP-014 | Mypy, Ruff, and MkDocs configs are monolithic debt ledgers. | Audit Baseline 2026-05-05; Tools subplan | P3 | team-devx | tools/ops_runners | 3.6 report | W3-W6 | 3.6, 5.5, 6.5 | Dead override report is green and config files read as policy plus owned exceptions. | Revert config split; leave report-only stale override check if green. |
| REP-015 | Top-level `schemas` mixes schema data with Python code. | Audit Baseline 2026-05-05 | P1 | team-architecture | schemas/data contracts | 1.8 directory policy | W2-W6 | 2.5, 6.2 | `schemas/**` is not importable Python and schema snapshots remain verified. | Revert import rewrites with schema code/data move map. |
| REP-016 | `tools/ops_runners/**` and `ops/**` duplicate names without taxonomy. | Audit Baseline 2026-05-05; Tools subplan | P2 | team-devx | tools/ops_runners | 1.2 taxonomy | W1-W2 | 1.2, 2.2 | Tools and ops have declared runner versus operational artifact homes. | Revert runner relocation and restore command aliases. |
| REP-017 | `.polisyos` lacks full runtime-state schema, retention, and CAS layout. | Audit Baseline 2026-05-05 | P2 | team-ops | runtime state | 0.6 inventory | W1-W2 | 1.6, 2.3 | Every `.polisyos` first-level directory is registered with cleanup and promotion rules. | Revert runtime-state docs/cleanup patch; local data is not deleted by rollback. |
| REP-018 | Extension points are under-declared for plugin-like catalogs. | Audit Baseline 2026-05-05 | P2 | team-architecture | architecture/contracts | 0.7 inventory | W1-W6 | 1.5, 5.1, 5.2, 6.4 | Each extension point has owner, contract class, version, ABI policy, and example expectation. | Revert extension contract/entry-point wiring separately from package moves. |
| REP-019 | Examples are too weak to verify extension author paths. | Audit Baseline 2026-05-05 | P3 | team-docs | docs: examples | 1.5 contract | W1-W6 | 1.5, 4.10, 6.4 | Installable examples exist or have explicit owner exceptions for each extension host. | Revert example addition; keep docs links behind extension gate. |
| REP-020 | SLO and runbook coverage is partial for public-stable components. | Audit Baseline 2026-05-05; Infrastructure subplan | P2 | team-ops | tools/ops_runners | 0.6 inventory | W1-W6 | 1.6, 4.9, 6.3 | Every public-stable component has SLO/runbook coverage or an exception. | Revert bundle draft; no workflow gate is enabled until report-only is green. |
| REP-021 | Module-size debt slows review and hides mixed responsibilities. | Audit Baseline 2026-05-05 | P2 | team-architecture | package source: one module owner | 0.5 inventory | W0-W6 | 0.5, 4.3, 5.4, 6.1 | God-module budget report is green and modified debt modules do not grow silently. | Revert extraction by module move map; characterization tests can remain. |
| REP-022 | CODEOWNERS and rulesets can drift after root/path changes. | Audit Baseline 2026-05-05; Infrastructure subplan | P1 | team-platform | root/control plane | 1.1 root decision | W1-W6 | 1.7, 2.8, 6.3 | CODEOWNERS, rulesets, and architecture owners agree for active paths. | Revert control-plane queue patch; root/path moves are not bundled. |
| REP-023 | Package-boundary, public-surface, and deep-import budgets need explicit no-regression. | Audit Baseline 2026-05-05 | P1 | team-architecture | architecture/contracts | 0.3 inventory | W1-W6 | 1.3, 4.8, 6.1 | Import-boundary and public-surface gates report deltas and prevent hidden coupling growth. | Revert fail-closed conversion to report-only. |
| REP-024 | Versioning policy does not yet cover future package names, schemas, extensions, and release semantics uniformly. | Audit Baseline 2026-05-05 | P2 | team-architecture | architecture/contracts | 1.5 contract | W1-W6 | 1.5, 5.10, 6.3 | Compatibility metadata has owner, version, deprecation window, and release note class. | Revert compatibility gate wiring; keep contract text if still accurate. |
| REP-025 | Supply-chain provenance, permissions, SBOM, and release identity are not tied to topology. | Audit Baseline 2026-05-05; Infrastructure subplan | P2 | team-security | root/control plane | 1.7 contract | W1-W6 | 1.7, 5.9, 6.3 | Release candidates have SBOM/provenance expectations and least-privilege CI identity. | Revert security workflow/policy patch through ops security queue. |
| REP-026 | Directory contract gaps leave high-volume subtrees without local authoring rules. | Audit Baseline 2026-05-05; Documentation subplan | P3 | team-docs | directory closure | 0.7 inventory | W0-W6 | 0.7, 1.8, 4.10, 6.2 | Directory contracts cover top-level and high-volume subtrees or list owned exceptions. | Revert README/contract patch for affected subtree only. |
| REP-027 | Non-product Python roots outside `src/polisyos` create import ambiguity. | Audit Baseline 2026-05-05 | P2 | team-architecture | directory closure | 0.7 inventory | W1-W6 | 1.8, 2.5, 6.2 | Every importable non-product root is intentional or removed from import surface. | Revert import policy or code/data move map. |
| REP-028 | Local residue, empty directories, and source-adjacent reports create noisy audits. | Audit Baseline 2026-05-05 | P4 | team-docs | directory closure | 1.8 contract | W2-W6 | 2.9, 6.2 | Residue report is empty or lists ignored retained paths with owner and retention. | Revert cleanup/ignore patch; source files are not deleted. |
| REP-029 | Product seed assets, test fixtures, golden records, examples, and reports have unclear placement. | Audit Baseline 2026-05-05 | P2 | team-quality | directory closure | 1.8 contract | W1-W6 | 1.8, 2.4, 2.9, 6.2 | Asset placement gate separates product data, test data, golden snapshots, examples, and reports. | Revert asset move map and preserve data provenance. |
| REP-030 | Large frontend subtrees need ownership and test topology. | Audit Baseline 2026-05-05; Frontend subplan | P3 | team-frontend | frontend | 2.7 workspace decision | W2-W6 | 2.7, 4.10, 6.2 | Frontend subtree contracts cover shared UI, API, features, tests, fixtures, and generated types. | Revert frontend docs/contracts; do not mix with lockfile rollback. |
| REP-031 | Docs, ADR, active plan, archive, and local report lifecycle is scattered. | Audit Baseline 2026-05-05; Documentation subplan | P3 | team-docs | docs: lifecycle | 0.7 inventory | W2-W6 | 2.6, 6.4 | Active plans have status/owner and ADRs are indexed by status/topic. | Revert docs lifecycle move map; nav changes stay queue-owned. |
| REP-032 | Migration coverage is DB-heavy and does not cover runtime state, API schemas, and IR schemas. | Audit Baseline 2026-05-05; Infrastructure subplan | P2 | team-ops | tools/ops_runners | 1.6 contract | W5-W6 | 5.6, 6.3 | Migration contract covers DB, runtime-state, API schema, and IR schema classes. | Revert migration topology patch; release gates remain report-only. |
| REP-033 | Release topology and promotion gates are incomplete. | Audit Baseline 2026-05-05; Infrastructure subplan | P2 | team-ops | tools/ops_runners | 1.6 contract | W5-W6 | 5.6, 5.10, 6.3 | Release promotion verifies topology, migration docs, compatibility metadata, and release fragments. | Revert release topology/gate patch through ops queue. |
| SUB-FAB-001 | Fabric subplan contains safety, concurrency, lifecycle, data-integrity, and SOTA backlog that can cross repo fences. | Fabric audit remediation plan | P1 | team-fabric | package source: `fabric` | Phase 0.1 subplan link | W3-W6 | 3.1, 5.3, 5.7, 6.1 | Fabric findings that touch shared registries or public surface have master IDs before merge. | Revert only Fabric-local patches unless a queue-owned integration patch landed. |
| SUB-IR-001 | IR subplan contains canon, registry, linker, API, performance, and verification backlog that can cross repo fences. | IR audit remediation plan | P1 | team-ir | package source: `ir` | Phase 0.1 subplan link | W3-W6 | 3.2, 5.3, 5.7, 6.1 | IR findings that touch public surface, schemas, or package contracts have master IDs before merge. | Revert only IR-local patches unless a queue-owned integration patch landed. |
| SUB-FOU-001 | Foundry subplan contains executor, methods, registry, reproducibility, and frontier backlog that can cross repo fences. | Foundry remediation plan | P1 | team-foundry | package source: `foundry` | Phase 0.1 subplan link | W4-W5 | 4.1, 4.2, 5.1, 5.4 | Foundry registry/discovery work is serialized and subplan findings crossing shared queues get master IDs. | Revert Foundry lane patch; extension registry patches are isolated. |
| SUB-SCI-001 | Scientist subplan contains taxonomy, governance, search, orchestration, and node backlog that can cross repo fences. | Scientist audit remediation plan | P1 | team-scientist | package source: `scientist` | Phase 0.1 subplan link | W4-W5 | 4.4, 4.5, 4.6, 4.7, 5.2 | Scientist API and extension work is serialized after lane merges. | Revert one Scientist lane; shared API/entry-point patch is separate. |
| SUB-FE-001 | Frontend subplan contains runtime-dashboard, design-system, accessibility, performance, and workspace backlog. | Frontend SOTA plan | P2 | team-frontend | frontend | Phase 0.1 subplan link | W2-W6 | 2.7, 4.10, 6.2 | Frontend workspace and generated-client changes are covered by JS workspace queue and subtree contracts. | Revert frontend path/docs patch separately from lockfile patch. |
| SUB-INF-001 | Infrastructure subplan contains root, CI, release, dependency, ownership, and supply-chain backlog. | Infrastructure SOTA plan | P0 | team-platform | root/control plane | Phase 0.1 subplan link | W1-W6 | 1.1, 1.7, 2.8, 5.9, 6.3 | Infrastructure findings that touch workflows/rulesets/CODEOWNERS are queue-owned integration patches. | Revert control-plane patch; product source moves are out of scope. |
| SUB-DOC-001 | Documentation subplan contains IA, plan lifecycle, README, ADR, runbook, and docs-gate backlog. | Documentation SOTA plan | P3 | team-docs | docs | Phase 0.1 subplan link | W2-W6 | 2.6, 4.10, 5.7, 6.4 | Docs findings that touch nav or gates use docs nav queue and keep active plan owner/status. | Revert docs move/nav fragment and keep source claims unchanged. |
| SUB-TOOLS-001 | Tools subplan contains CLI, tool runtime, CI output, telemetry, security, and config backlog. | Tools audit remediation plan | P1 | team-devx | tools/ops_runners | Phase 0.1 subplan link | W2-W6 | 2.2, 3.6, 5.5, 6.2 | Tool findings that touch root configs or generated reports use Python tooling queue. | Revert tooling patch; shared config changes remain isolated. |

## Verification Commands

The exact commands should be updated as phases land, but closeout should
include at least:

```bash
uv run pytest tests/repo_quality -q
uv run pytest tests/contract -q
uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json
uv run python tools/quality/validation/decomposition_preflight.py gate --output-json _build/.tmp/wave7-closeout/decomposition-preflight.json
uv run python -m tools.devx.workspace.doctor
corepack pnpm install --frozen-lockfile
corepack pnpm -r --workspace-concurrency=1 --if-present run build
corepack pnpm -r --workspace-concurrency=1 --if-present run test
uv run python tools/quality/validation/architecture_report_only_contracts.py --report all --json-output _build/.tmp/wave7-closeout/architecture-contracts-all.json --fail-on-contract-errors
uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/wave7-closeout/test-ratchets.json --fail-on-regression
uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/wave7-closeout/dead-overrides.json
uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/wave7-closeout/directory-health.json --markdown-output _build/.tmp/wave7-closeout/directory-health.md --fail-on-regression
uv run polisyos-tools workspace repository-sota-closeout --skip-generated-checks --output-json _build/.tmp/wave7-closeout/repository-sota-closeout-skip-generated.json
uv run polisyos-tools workspace acceptance-audit --json-output _build/.tmp/wave7-closeout/platform-acceptance.json --summary _build/.tmp/wave7-closeout/platform-acceptance.md
uv run python tools/quality/validation/check_docs_lifecycle.py --repo-root .
```

Additional generated reports:

- root topology report;
- package facade report;
- shim sunset report;
- test mirror-ratio report;
- module-size report;
- SLO/runbook coverage report;
- extension-point discovery report;
- stale config override report;
- generated-artifact freshness report;
- CODEOWNERS/ruleset coverage report;
- import-boundary delta report;
- compatibility-class and ABI report;
- release SBOM/provenance report;
- directory-contract coverage report;
- non-product Python root inventory;
- local residue and empty-directory report;
- product asset/test fixture/golden/example placement report.

## Final Acceptance Criteria

The repository exits this program only when:

- product root policy has no ambiguous half-state;
- no product implementation lives in the wrong root;
- no committed generated/source confusion remains under build or cache paths;
- every active top-level Python package obeys root facade policy or has a
  documented exception with sunset;
- compatibility shims are expired, removed, or time-boxed with low-cost tests;
- Foundry executor internals have one ownership boundary;
- Foundry methods have a documented taxonomy and extension registry;
- Scientist first-level package count is reduced and semantically grouped;
- cross-cutting concerns are either canonicalized or explicitly scoped;
- tests have mirror-ratio and property-test ratchets;
- fixtures, helpers, golden data, and contracts are separated;
- benchmark role is explicit;
- JS workspace uses a clear apps/packages convention;
- tool configs have dead override protection;
- top-level schemas contain schemas, not Python package code;
- docs plans and ADRs have one lifecycle/index;
- extension points are versioned and exercised by examples;
- every public-stable component has SLO/runbook coverage or an exception;
- runtime state has schema, retention, and migration policy;
- CODEOWNERS, repository rulesets, and architecture ownership agree;
- import-boundary and public-surface ratchets prevent hidden coupling growth;
- versioning policy keeps Python package names stable and puts version metadata
  in schemas, APIs, extension contracts, runtime-state formats, and release
  records;
- release artifacts have SBOM/provenance expectations and least-privilege CI
  identity policy;
- every top-level directory has a contract, and every high-volume subtree has a
  local README/AUTHORING/index or an owned exception;
- every importable Python root outside `src/polisyos` is intentional and
  documented;
- product seed assets, test fixtures, golden records, examples, archives, and
  local reports have distinct placement and promotion rules;
- local residue and empty source/cache directories are covered by hygiene gates;
- large frontend subtrees have the same ownership and authoring closure as
  backend packages;
- no god module can grow silently;
- all new gates are either fail-closed or have a dated report-only transition.

## Closeout Artifact

The final PR for this program must add a closeout document under
`docs/plans/accepted/` or `docs/plans/archive/` that includes:

- final state summary;
- unresolved exceptions with sunset dates;
- before/after metrics;
- migration notes for contributors;
- operator notes for `.polisyos`, ops bundles, and release promotion;
- owner/reviewer changes for CODEOWNERS and rulesets;
- compatibility and deprecation notes for public APIs, schemas, extensions,
  runtime state, and generated clients;
- directory-contract and asset-placement exceptions;
- links to all merged phase PRs;
- commands used for final verification.
