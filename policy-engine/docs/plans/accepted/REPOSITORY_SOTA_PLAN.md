---
title: Repository SOTA Plan
status: accepted
owner: team-polisyos
created: 2026-04-18
last_verified: 2026-05-03
stability: stable
---

# Repository SOTA Plan

This plan is the repository-wide contract for turning PolisyOS into a
machine-governed monorepo. It deliberately sits above the Data Forge migration:
Data Forge is one major workstream, but the repository also needs topology,
docs, tools, tests, ops, frontend, generated artifacts, secrets, observability,
and release discipline.

## Preserve

Keep these decisions from the Data Forge plan as written:

1. Build-time Data Forge writes artifacts; runtime packages read stable
   artifacts and facades.
2. Layered ownership: `common -> ir -> core -> fabric/data_forge/lex/foundry/scholar -> scientist -> runtime`.
3. Import anti-edges are acceptance criteria, not style advice.
4. Topology is a machine-checkable contract, not a convention in prose.
5. Phase -1 inventories the current tree before moves.
6. Golden snapshots are captured before each behavioral migration.
7. Pipeline configs are frozen; overrides use typed composition and
   `replace()`-style copies.
8. Completed NPA corpus processing is treated as an input baseline, not as a
   special repository-wide execution mode.

## SOTA Rubric

| Dimension                | Target                                                                      |
| ------------------------ | --------------------------------------------------------------------------- |
| Workspace discipline     | Root is a gateway/control plane; `policy-engine/` is product root           |
| Topology as code         | `architecture/*.toml` plus schemas and CI gates                             |
| Layered architecture     | Import-linter contracts, public-surface snapshots, deptry                   |
| Docs lifecycle           | Diataxis plus ADR-first decisions and active/accepted/archive plans         |
| Schema-first contracts   | `schemas/` is source of truth; generated TS/Py are drift-checked            |
| Hermetic reproducibility | Toolchain, Docker digests, model weights, tokenizer hashes, lockfiles       |
| Ops separation           | `ops/` stores runtime configs; `tools/` stores dev/CI commands              |
| Test topology            | Tests mirror `src/` and separate architecture/contract/property/e2e         |
| Observability as code    | OTel-first telemetry plus Grafana/Prom/SLO config under `ops/observability` |
| Secrets                  | SecretBackend protocol, redaction, gitleaks/trufflehog gates                |
| Generated artifacts      | Registry entry, regen command, owner, freshness, generated header           |
| Migration discipline     | Every shim has target, owner, reason, sunset, and issue                     |
| Repo hygiene             | Loose-file allowlist, module-size gates, OPA repo policies                  |
| Artifact governance      | `license`, `pii_level`, `retention_class`, `owner`, `producer_version`, regeneration command |

## Source-of-Truth Map

| Concern                   | Source of truth                                                    |
| ------------------------- | ------------------------------------------------------------------ |
| Workspace boundary        | ADR-0111 plus `architecture/topology.toml`                         |
| Data Forge migration      | ADR-0112 plus `docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md` |
| Asset-centric pipelines   | ADR-0113 plus Data Forge kernel contracts                          |
| Schema registry           | ADR-0114 plus `schemas/**` and codegen gates                       |
| Layering/imports          | ADR-0115 plus `architecture/import_contracts.toml`                 |
| OTel-first observability  | ADR-0116 plus `ops/observability/**`                               |
| Secrets                   | ADR-0117 plus SecretBackend protocol and security gates            |
| Release/SemVer            | ADR-0118 plus `release/` and `release-fragments/`                  |
| Frontend workspace        | ADR-0119 plus `frontend/` workspace config                         |
| Test topology             | ADR-0120 plus `tests/README.md` and architecture tests             |
| Python workspace strategy | ADR-0121 plus `pyproject.toml` / `uv.lock` policy                  |
| Lakehouse snapshots       | ADR-0122 plus Data Forge snapshot contracts                        |
| Artifact governance       | ADR-0123 plus ArtifactRef schema snapshots                         |
| LLM idempotency           | ADR-0124 plus prompt/cache/DLQ contracts                           |
| Data quality regime       | ADR-0125 plus `kernel/quality/*` contracts                         |
| Docs lifecycle            | ADR-0126 plus `docs/plans/README.md`                               |
| Repo hygiene gates        | ADR-0127 plus architecture/security gate configs                   |
| Hermetic reproducibility  | ADR-0128 plus lockfiles, model hashes, and Docker digests          |

## Execution Posture

As of 2026-05-03, Repository SOTA is accepted and implemented as the
machine-checkable topology baseline for the product root. The final public map
for placing files, commands, tests, docs, ops material, local data, and runtime
state is `docs/reference/repository-topology.md`.

The plan now assumes strict migration discipline:

1. Every move has an inventory baseline, owner, shim, rollback path, and
   acceptance evidence.
2. Compatibility wrappers are temporary migration tools, not long-term target
   architecture.
3. Golden, replay, or differential evidence is captured before behavior-changing
   package moves or production entrypoint switches.
4. Gates can start report-only while being introduced, but by Phase 5 each gate
   is either fail-closed or covered by an explicit exception.
5. Temporary freeze-safety artifacts, if present, are retired during Phase 0
   rather than treated as ongoing execution constraints.

Current repository state to account for before execution:

| Area | Current state |
| ---- | ------------- |
| ADRs | ADR-0111 through ADR-0128 are present. |
| Architecture contracts | `architecture/*.toml` and `schemas/topology/*.schema.json` are present. |
| Inventory evidence | Phase -1 and Phase -1.5 historical baselines live under `docs/archive/reports/`; Phase 0-5 accepted evidence lives beside this plan. |
| Data Forge | Additive Data Forge foundation and domain work may exist in the tree; execution must validate and integrate it through the phase sequence below. |
| Compatibility paths | Legacy packages and tool wrappers remain valid only through registered shims and sunset rules. |

## Target Contracts

The first implementation phase validates or creates these machine-readable
contracts:

| File                                      | Purpose                                                             |
| ----------------------------------------- | ------------------------------------------------------------------- |
| `architecture/topology.toml`              | Top-level path allowlist, category, owner, commit policy            |
| `architecture/package_boundaries.toml`    | Package owners, allowed dependencies, public facades                |
| `architecture/import_contracts.toml`      | Import-linter contracts for layers, forbidden imports, independence |
| `architecture/shims.toml`       | Compatibility shims with owner and sunset                           |
| `architecture/complexity_exceptions.toml` | Temporary god-file/module-size exceptions                           |
| `architecture/public_surface.toml`        | Public entrypoints and supported facade modes                       |
| `architecture/generated_artifacts.toml`   | Generated artifact registry with freshness gates                    |
| `schemas/topology/*.schema.json`          | JSON Schema for architecture TOML contracts                         |

Guardrails must delegate to dedicated tools where possible: import-linter for
imports, deptry for dependency hygiene, generated-artifact drift checks for
codegen, and OPA policies for repo-wide allow/deny rules.

## Gates Inventory

Gate behavior is phased. Newly introduced or materially changed gates may begin
as report-only checks to capture baselines and register explicit exceptions.
Phase 5 promotes them to fail-closed CI/pre-commit checks unless an exception is
owned, documented, and time-bounded.

| Gate             | Source                                                                      |
| ---------------- | --------------------------------------------------------------------------- |
| import-linter    | `architecture/import_contracts.toml`                                        |
| deptry           | `pyproject.toml` dependency declarations                                    |
| topology-gate    | `architecture/topology.toml`                                                |
| shim-audit       | `architecture/shims.toml`                                         |
| complexity       | `architecture/complexity_exceptions.toml` plus Ruff caps                    |
| schema-drift     | `schemas/**` and codegen commands                                           |
| generated-header | `architecture/generated_artifacts.toml`                                     |
| gitleaks         | `ops/security/gitleaks.toml`                                                |
| OSV/SBOM         | `ops/security/osv-scanner.toml` and `release-sbom` generated artifact       |
| commitlint       | release-train policy from ADR-0118                                          |
| public-surface   | `architecture/public_surface.toml` and `architecture/public_surface/*.json` |
| docs-freshness   | docs front matter and `docs/plans/README.md`                                |
| loose-file       | `architecture/topology.toml` loose-file allow/deny lists                    |
| pii-redaction    | SecretBackend redaction middleware and manifest/log scans                   |

## Target Repository Topology

Repository root remains a minimal repo control plane after RSR-0130 Phase 2A:

```text
polisyos/
|-- .github/                  # active GitHub workflows/actions/rules
|-- renovate.json
`-- policy-engine/            # canonical product root
```

`policy-engine/` remains the product root:

```text
policy-engine/
|-- architecture/
|-- schemas/
|-- docs/
|-- src/polisyos/
|-- tests/
|-- tools/
|-- ops/
|-- frontend/
|-- benchmarks/
|-- release/
|-- release-fragments/
|-- data/                     # allowlisted committed fixtures plus ignored local lake
|-- design/                   # product-level design material
|-- CODE_OF_CONDUCT.md
|-- SECURITY.md
|-- SUPPORT.md
`-- .polisyos/                # ignored local runtime state
```

## Required Structural Moves

This table is the structural migration backlog. Each move must carry the
required inventory baseline, owner, compatibility shim when needed, rollback
path, and acceptance evidence before it is merged.

| Area                                      | Required move                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Root loose files                          | Reports to `.polisyos/reports/`; scripts to `tools/research/` or `tools/devx/workspace/`; data artifacts to `data/policy-engine-local/` or registered fixtures |
| `policy-engine/.github`                   | Removed after active workflows moved to root `.github` and templates moved to `ops/ci/templates`                    |
| `cloud_deploy`, `deploy`, `docker`, `gcp` | Removed after consolidation under `ops/cloud`, `ops/deploy`, `ops/docker`, and `ops/observability`                  |
| `tools/*` duplicates                      | Removed from active top-level `tools/`; canonical homes live under `tools/{devx,ops,quality,research}`              |
| `scripts/`                                | Removed after canonical `polisyos-tools` commands existed                                                           |
| `docs/*.md` plans                         | Move active plans to `docs/plans/active`, accepted plans to `docs/plans/accepted`, history to `docs/archive/plans`  |
| `tests/*` old package mirrors             | Move with source topology to `tests/unit` or `tests/unit/data_forge`                                                     |
| Frontend generated outputs                | Keep ignored; register tracked generated clients/types                                                              |

## Ops Target

```text
ops/
|-- ci/
|-- cloud/
|   |-- gcp/
|   |-- terraform/
|   `-- helm/
|-- docker/
|-- observability/
|   |-- grafana/
|   |-- prometheus/
|   |-- otel/
|   `-- slo/
|-- policy/
|-- release/
|-- runtime/
|-- migrations/
`-- security/
```

## Tools Target

`tools/` is the canonical dev/CI command tree. Every command should be reachable
from a command registry, eventually through `polisyos-tools`.

```text
tools/
|-- cli.py
|-- registry.py
|-- _lib/
|-- _deprecated/
|-- architecture/
|-- ci/
|-- devx/
|-- doctor/
|-- workspace/
|-- quality/
|   |-- lint/
|   |-- typecheck/
|   |-- tests/
|   |-- validation/
|   |-- diagnostics/
|   |-- docs/
|   `-- schemas/
|-- data_forge/
|-- ops/
|-- research/
|-- connectors/
|-- foundry/
|-- calibration/
|-- benchmarks/
|-- migrations/
`-- demos/
```

## Tests Target

```text
tests/
|-- architecture/
|-- contract/
|-- property/
|-- unit/
|   `-- <package mirror>
|-- integration/
|-- e2e/
|-- golden/
|-- performance/
|-- tools/
|-- lint/
`-- fixtures/
```

Unit tests mirror `src/polisyos`. Cross-module behavior lives in
`integration/`, full pipeline behavior in `e2e/`, and architecture gates in
`architecture/`.

## Data Lake Target

Product-root `data/` uses allowlisted committed homes plus ignored medallion semantics:

```text
data/
|-- bronze/
|-- silver/
|-- gold/
|-- cache/
|-- releases/
|-- archives/
`-- _index/
```

Product-root `policy-engine/data/` is not a lake:

```text
policy-engine/data/
|-- README.md
|-- fixtures/
|-- gold/
|-- contracts/
|-- manifest_templates/
`-- registry/
```

## Detailed Phases

The phases are ordered so that repository contracts and evidence are refreshed
before large moves, while temporary compatibility remains explicit and
short-lived. Existing evidence files are historical inputs, not a substitute for
refreshing the baseline at the current execution HEAD.

### Phase -1. Baseline Refresh

Goal: rebuild the current repository map before changing topology.

Work:

1. Refresh topology inventory for root, `policy-engine/`, `src/polisyos/`,
   `tests/`, `tools/`, `ops/`, `docs/`, `schemas/`, `frontend/`, and local data
   paths.
2. Refresh import graph and public-surface baseline, including deep imports,
   layer violations, and current facade entrypoints.
3. Refresh generated-artifact inventory: generated headers, regeneration
   commands, owners, freshness signals, and unregistered outputs.
4. Refresh tools and scripts inventory, grouping commands by canonical target
   namespace and duplicate/deprecated status.
5. Refresh docs inventory against the active/accepted/archive lifecycle.
6. Record current worktree and branch state, including unrelated user edits that
   execution must not rewrite.

Deliverables:

- Updated Phase -1 inventory note or regenerated inventory report.
- Import graph, public-surface, generated-artifact, tools, docs, and data-root
  baselines attached to the plan or referenced from it.
- Drift summary against the previous Phase -1 evidence.

Acceptance:

- No structural moves are performed in this phase.
- Every planned move has a source path, target path, owner, risk class, and
  evidence requirement.

Implementation evidence:

- 2026-05-02 refreshed baseline:
  `docs/archive/reports/REPOSITORY_SOTA_PHASE_MINUS_1_INVENTORY.md`.

### Phase -1.5. Amnesty And Classification

Goal: classify loose files and local outputs, then clean only items whose target
or ignore policy is unambiguous.

Work:

1. Classify audit bundles, root reports, accidental files, scratch virtualenvs,
   local outputs, historical specs, topic artifacts, and temporary run products.
2. Extend ignore rules for local-only reports, caches, generated local outputs,
   and runtime state that must stay out of git.
3. Move durable documentation or specs into their lifecycle home instead of
   leaving them as root loose files.
4. Relocate durable fixtures or manifests into committed fixture/contract
   locations; keep bulky or derived data in ignored local data paths.
5. Remove accidental files only after their classification is recorded.

Deliverables:

- Updated loose-file classification.
- Updated ignore rules and local-state notes.
- Archive, fixture, or manifest placements for durable artifacts.

Acceptance:

- Root loose files are either allowed by topology, moved to a canonical home, or
  ignored as local state.
- No active source, fixture, contract, or migration evidence is deleted.

Implementation evidence:

- 2026-05-02 refreshed classification:
  `docs/archive/reports/REPOSITORY_SOTA_PHASE_MINUS_1_5_CLASSIFICATION.md`.

### Phase 0. Contract Normalization

Goal: make repository policy machine-readable before code and path migrations.

Work:

1. Validate ADR-0111 through ADR-0128 against the current target architecture and
   add superseding ADR notes if implementation reality has changed.
2. Validate `architecture/*.toml` against `schemas/topology/*.schema.json`.
3. Normalize topology, package boundaries, import contracts, migration shims,
   complexity exceptions, public surface, generated artifacts, and CODEOWNERS
   coverage.
4. Retire or supersede temporary freeze-safety artifacts so they do not remain
   active execution constraints.
5. Add or update report-only checks for topology, import contracts, public
   surface, generated artifacts, shim audit, docs freshness, and security scans.
6. Define rollback notes and acceptance evidence templates for structural moves.

Deliverables:

- Validated architecture contracts and schemas.
- Updated migration-shim registry and public-surface registry.
- Report-only gate wiring with baseline outputs.
- Phase 0 contract note replacing older temporary execution posture notes.

Acceptance:

- Architecture contracts validate locally.
- Every existing compatibility shim has owner, reason, target, sunset, and issue
  or exception.
- No gate becomes fail-closed before its baseline and exceptions are recorded.

Implementation evidence:

- 2026-05-02 refreshed contract baseline:
  `docs/plans/accepted/REPOSITORY_SOTA_PHASE_0_CONTRACTS.md`.

### Phase 1. Data Forge Foundation

Goal: finish the build-time artifact foundation that other repository moves can
depend on.

Work:

1. Consolidate the `data_forge` public surface around asset kernel contracts,
   ArtifactRef models, schema registry access, snapshot transactions, import
   contracts, quality contracts, and stable read APIs.
2. Keep runtime consumers on stable facades; do not allow runtime code to import
   Data Forge kernel or domain internals.
3. Register artifact metadata: owner, producer version, schema, freshness,
   retention class, PII level, license, and regeneration command.
4. Add golden, replay, or differential baselines for behavior-changing artifact
   migrations.
5. Add focused tests for artifact identity, schema lookup, snapshot semantics,
   import boundaries, and facade compatibility.

Deliverables:

- Data Forge public API and internal package boundary contract.
- ArtifactRef and schema-registry tests.
- Snapshot/read API compatibility evidence.
- Registered generated artifacts and fixture contracts.

Acceptance:

- Build-time artifact producers and runtime readers are separated by tests and
  import contracts.
- Existing consumers continue to pass through compatibility facades.

Implementation evidence:

- Phase 1 foundation note:
  [`REPOSITORY_SOTA_PHASE_1_DATA_FORGE_FOUNDATION.md`](REPOSITORY_SOTA_PHASE_1_DATA_FORGE_FOUNDATION.md)

### Phase 2. Domain And Entrypoint Migration

Goal: move domain code and production entrypoints toward the target topology with
registered compatibility.

Work:

1. Migrate or mirror academic, catalog, legal, Ukraine, Lex, foundry, scholar,
   scientist, and shared-batch boundaries toward the layered package model.
2. Replace direct deep imports with public facades or registered migration
   shims.
3. Switch production entrypoints only after golden, replay, or differential
   evidence confirms equivalent behavior.
4. Keep old import paths as thin wrappers when compatibility is required.
5. Add sunset dates and removal criteria for each wrapper.
6. Update tests to mirror the new source topology while preserving regression
   coverage for legacy entrypoints during the transition.

Deliverables:

- Domain migration batches with source/target path maps.
- Updated migration-shim registry.
- Compatibility tests for old and new import paths.
- Golden/replay/differential evidence for behavior-changing switches.

Acceptance:

- No domain move changes behavior without evidence.
- No compatibility wrapper exists without owner, sunset, and target path.

Implementation evidence:

- Phase 2 domain migration note:
  [`REPOSITORY_SOTA_PHASE_2_DOMAIN_MIGRATION.md`](REPOSITORY_SOTA_PHASE_2_DOMAIN_MIGRATION.md)
- Machine-readable migration batches:
  `architecture/domain_migration_batches.toml`

### Phase 3. Repository Topology Cleanup

Goal: consolidate repository structure after contracts and compatibility are in
place.

Work:

1. Move root loose reports, scripts, data artifacts, and research helpers to
   `tools/`, `.polisyos/`, `data/policy-engine-local/`, registered fixtures, or
   archived docs according to the Phase -1.5 classification.
2. Consolidate active workflows under root `.github/`; move reusable templates
   and CI support material under `ops/ci/`.
3. Consolidate `cloud_deploy`, `deploy`, `docker`, and `gcp` into the `ops/`
   target layout, then remove the product-root legacy directories.
4. Consolidate duplicate `tools/*` namespaces and remove old top-level
   namespaces from the active command surface.
5. Remove `scripts/` after every surviving command has a canonical
   `polisyos-tools` or `tools/*` home.
6. Move docs into active, accepted, archived, reference, or tutorial homes using
   the docs lifecycle.
7. Move tests into architecture, contract, property, unit, integration, e2e,
   golden, performance, tools, lint, or fixtures homes.

Deliverables:

- Updated topology-compliant path layout.
- Retired-shim evidence for removed legacy paths and canonical command coverage.
- Updated docs and tests indexes.
- Rollback notes for non-trivial path moves.

Acceptance:

- Topology gate reports no unclassified paths.
- Canonical commands still work through their new homes.
- Deprecated product-root paths and duplicate top-level tool namespaces are
  absent from the final topology.

Implementation evidence:

- Phase 3 topology cleanup note:
  [`REPOSITORY_SOTA_PHASE_3_TOPOLOGY_CLEANUP.md`](REPOSITORY_SOTA_PHASE_3_TOPOLOGY_CLEANUP.md)
- Report-style topology and wrapper coverage:
  `tests/tools/test_repository_sota_phase3_topology_cleanup.py`

### Phase 4. Generated, Frontend, Data, And Ops Discipline

Goal: close the non-Python governance gaps that make the repository hard to
operate consistently.

Work:

1. Register tracked generated clients, types, reports, schema outputs, and SBOMs
   in `architecture/generated_artifacts.toml`.
2. Add generated-file headers, regeneration commands, owners, and drift checks.
3. Establish `frontend/` workspace ownership, generated-output ignore policy,
   schema-client drift checks, and build/test commands.
4. Establish medallion layout for local ignored data under product-root `data/`
   and keep committed `data/` content limited to fixtures, contracts,
   manifests, registry entries, and tiny gold examples.
5. Document `.polisyos/` local runtime state, cleanup commands, retention
   classes, and garbage-collection policy.
6. Normalize `ops/observability`, `ops/security`, `ops/release`, `ops/runtime`,
   and `ops/migrations` contracts.
7. Add secrets, OTel, SLO, OSV, SBOM, release-fragment, and commit policy
   baselines.

Deliverables:

- Generated-artifact registry with drift checks.
- Frontend workspace contract.
- Data lake and committed-data policy.
- Ops, observability, security, and release baseline configs.

Acceptance:

- Generated artifacts are reproducible or explicitly exempted.
- Local data and runtime state are ignored, documented, and cleanable.
- Release, security, and observability checks have baseline outputs.

Implementation evidence:

- [`REPOSITORY_SOTA_PHASE_4_GENERATED_FRONTEND_DATA_OPS.md`](REPOSITORY_SOTA_PHASE_4_GENERATED_FRONTEND_DATA_OPS.md)
  records the report-only generated/frontend/data/ops discipline implemented
  for this phase.

### Phase 5. Enforcement And Closeout

Goal: turn repository policy from documented intent into enforced practice.

Work:

1. Promote topology, import-linter, public-surface, generated-drift,
   docs-freshness, loose-file, shim-audit, complexity, security, dependency,
   SBOM, and commit-policy gates from report-only to fail-closed.
2. Keep exceptions only when they are owner-approved, time-bounded, and recorded
   in the relevant contract.
3. Remove compatibility wrappers whose sunset criteria have been met.
4. Update ADR indexes, plan indexes, command registry, developer docs, and
   onboarding notes to match the implemented topology.
5. Produce a closeout report with final topology, remaining exceptions, retired
   shims, gate status, and follow-up backlog.

Deliverables:

- Fail-closed CI/pre-commit gate set.
- Final exception and shim registry.
- Updated docs and command registry.
- Repository SOTA closeout report.

Acceptance:

- New paths, imports, generated files, shims, docs, secrets, and local outputs
  are governed by machine-checkable contracts.
- Remaining exceptions are explicit and reviewable.
- The plan can move from `active` to `accepted` or archive with evidence.

Implementation evidence:

- [`REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md`](REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md)
  records final topology, fail-closed gates, remaining exceptions, retired
  shims, CI/pre-commit wiring, and follow-up backlog.
- `uv run polisyos-tools workspace repository-sota-closeout` is the canonical
  closeout command for the implemented policy layer.

## Priority Table

| Rank | Work                                                                           | Effort | Impact |
| ---- | ------------------------------------------------------------------------------ | ------ | ------ |
| P0   | Import-linter contracts                                                        | S      | High   |
| P0   | Migration shim registry                                                        | S      | High   |
| P0   | Phase -1.5 loose-file amnesty                                                  | M      | High   |
| P0   | ADR-0111..0128                                                                 | S      | High   |
| P0   | CODEOWNERS coverage for architecture, schemas, Data Forge, ops, and docs plans | S      | High   |
| P0   | Diataxis plan lifecycle                                                        | M      | High   |
| P1   | Schema registry and drift gate                                                 | M      | High   |
| P1   | Ops seven-bucket topology                                                      | L      | Medium |
| P1   | Tools canonical layout                                                         | L      | Medium |
| P1   | Test topology mirror                                                           | M      | Medium |
| P1   | Module size and complexity gates                                               | S      | Medium |
| P1   | Generated artifact discipline                                                  | M      | Medium |
| P2   | Artifact governance metadata                                                   | M      | High   |
| P2   | SecretBackend protocol and secret scanning                                     | M      | High   |
| P2   | Observability SLO-as-code                                                      | M      | Medium |
| P2   | Hermetic reproducibility                                                       | M      | High   |
| P2   | Release train and SemVer contracts                                             | M      | Medium |
| P2   | Repo hygiene gates: gitleaks, OSV, SBOM, commitlint                            | M      | Medium |
| P2   | ADR template, index, and relation checks                                       | S      | Medium |
| P2   | `.gitattributes` and `.editorconfig` baseline                                  | S      | Low    |
| P3   | Frontend workspace                                                             | L      | Medium |
| P3   | Medallion data naming                                                          | S      | Low    |
| P3   | Unified doctor/bootstrap/clean CLI                                             | M      | Medium |

## Acceptance Criteria

1. A new top-level path cannot appear without `architecture/topology.toml`.
2. A new cross-layer import cannot appear without import-linter approval.
3. A new generated file cannot appear without `architecture/generated_artifacts.toml`.
4. A compatibility shim cannot appear without `architecture/shims.toml`.
5. Active docs cannot live indefinitely in `docs/*.md`.
6. Runtime code cannot import Data Forge kernel/domain internals.
7. Large local outputs remain ignored, hidden, and cleanable.
8. Production entrypoint switches require golden, replay, or differential
   evidence before they are accepted.
9. Report-only gates cannot remain report-only after Phase 5 unless an explicit
   exception exists.
10. Temporary compatibility wrappers must either be removed by their sunset
    criteria or listed as accepted exceptions.
