---
title: Repository SOTA Phase -1 Inventory
status: report
owner: team-polisyos
created: 2026-04-24
last_verified: 2026-05-02
stability: snapshot
---

# Repository SOTA Phase -1 Inventory

This is the refreshed read-only Phase -1 inventory for
`docs/plans/accepted/REPOSITORY_SOTA_PLAN.md`.

The purpose of this report is to rebuild the current repository map before any
topology changes. It records the current branch, dirty worktree, path layout,
import graph, public surface, generated artifacts, tools, docs, frontend, data
paths, and planned structural moves. It does not move, delete, rename, or
rewrite any repository paths.

## Snapshot

| Field | Value |
| ----- | ----- |
| Date | 2026-05-02 |
| Branch | `main` |
| HEAD | `3f7af28e` |
| Previous inventory | 2026-04-24, `057ed6cb` |
| Mode | Full Phase -1 baseline refresh |
| Structural moves performed | None |

The working tree is dirty and must be treated as containing unrelated user work
that later phases must not rewrite or revert. Current status counts:

| Status | Count | Meaning |
| ------ | ----- | ------- |
| ` M` | 180 | modified tracked paths |
| ` D` | 215 | deleted tracked paths |
| `MD` | 1 | modified and deleted tracked path |
| `??` | 62 | untracked paths |

Largest dirty areas by path family:

| Path family | Dirty paths |
| ----------- | ----------- |
| `policy-engine/src` | 274 |
| `policy-engine/tests` | 128 |
| `policy-engine/docs` | 24 |
| `policy-engine/tools` | 12 |
| `policy-engine/architecture` | 8 |
| `policy-engine/schemas` | 6 |
| Other product-root files | 6 |

Observed work-in-progress is concentrated around Data Forge/domain migration:
old `academic`, `datasets`, `lex/batch`, `lex/corpus`, `ukraine_data`,
`batch_common`, and `batch_snapshot` paths are deleted in the worktree while
new `polisyos.data_forge.domains.*` paths and Data Forge tests are untracked or
modified. This report records that state only; it does not accept, reject, or
complete those moves.

## Drift Summary

Drift against the previous Phase -1 inventory:

| Area | 2026-04-24 inventory | 2026-05-02 refresh | Drift |
| ---- | -------------------- | ------------------ | ----- |
| Execution posture | Freeze-only snapshot | Full baseline refresh | Old freeze-only posture retired from this inventory. |
| Repo root entries | 40 | 41 | Root loose-file pressure remains. |
| Product-root entries | 94 | 96 | Product-root loose/local output pressure remains. |
| `src/polisyos/data_forge` | 36 Python files | 240 Python files | Data Forge became a major active package. |
| `src/polisyos/lex` | 95 Python files | 35 Python files | Batch/corpus code is no longer present on disk. |
| Legacy data packages | `academic`, `datasets`, `ukraine_data`, `batch_common`, `batch_snapshot` present | Not present on disk | Deleted in worktree and mirrored by Data Forge domains. |
| New source packages | none noted | `berl`, `ddm_15_7` | New package roots require topology/public-surface review. |
| Import graph | 0 parse errors | 0 parse errors across 2,129 Python files | Import scan remains parse-clean. |
| Deep-import baseline | present | `architecture/baselines/imports/deep_import.json` has 3,299 edges and is modified in worktree | Do not overwrite without explicit refresh command. |
| Public surface | 10 public packages | 10 public packages | Current source has package roots not listed as public. |
| Generated registry | present | 11 families, 19 output paths | 3 mixed-policy outputs missing; 6 new schema files are untracked. |
| Tools | duplicate compatibility wrappers present | wrappers still present, `ops` and `quality` grew | Cleanup remains Phase 3 work. |
| Root `data/` | large Lex and archive lake observed | one visible file: `data/lex_real_doc_smoke_20260321.json` | Large prior root data paths are no longer visible. |
| `policy-engine/production_data` | large runtime artifacts present | includes `lex_current_20260501` at 20G | Local runtime data remains large and ignored/local. |
| Docs lifecycle | active/archive plans present | 10 active plan entries, accepted has only `.gitkeep` | Many top-level docs still need lifecycle classification. |

## Topology Inventory

Machine-readable architecture contracts currently present:

- `architecture/topology.toml`
- `architecture/packages/boundaries.toml`
- `architecture/imports/contracts.toml`
- `architecture/migration_shims.toml`
- `architecture/exceptions/complexity.toml`
- `architecture/generated_artifacts.toml`
- `architecture/public_surface/contract.toml`
- `architecture/public_surface/inventory.json`
- `architecture/baselines/imports/deep_import.json`
- `schemas/topology/*.schema.json`

Topology comparison against `architecture/topology.toml`:

| Scope | Registered path entries | Actual immediate entries | Notes |
| ----- | ----------------------- | ------------------------ | ----- |
| repo root | 19 | 41 | Loose-file allow/deny lists still govern many root files. |
| product root | 47 | 96 | Product root includes canonical paths, legacy wrappers, caches, local outputs, and loose files. |

Repo-root immediate entries include the target gateway paths
`.github/`, `design/`, `data/`, `.polisyos/`, and `policy-engine/`. Root
loose-file pressure remains:

- `.DS_Store`
- `compileall.txt`
- `import_gate.txt`
- `ruff_stats.txt`
- `summary.json`
- `test_collect.txt`
- `stale_sources_missing_paths.txt`
- `topics.csv`
- `filter_topics.py`
- `organize_relevant_topics.py`
- `scm-implementation-spec-v3.md`

Product-root canonical directories are present:

- `architecture/`
- `schemas/`
- `docs/`
- `src/`
- `tests/`
- `tools/`
- `ops/`
- `frontend/`
- `benchmarks/`
- `release/`
- `release-fragments/`
- `data/`
- `.polisyos/`

Product-root transitional and local-output paths are also present:

- legacy wrappers: `.github/`, `cloud_deploy/`, `deploy/`, `docker/`, `gcp/`,
  `scripts/`
- local outputs/caches: `runs/`, `tmp/`, `logs/`, `out/`, `dist/`, `site/`,
  `benchmark-results/`, `.benchmarks/`, `.tmp/`, `.cache/`, `.pytest_cache/`,
  `.ruff_cache/`, `.mypy_cache/`, `.hypothesis/`, `.uv-cache/`
- local envs/scratch: `.venv/`, `.venv_codex/`, `.tmp_c7_venv/`,
  `.tmp_c7_smoke/`
- loose files flagged by topology deny lists: `=2.5.0`, `.DS_Store`,
  `env_example.txt`, `all_1000_policy_topics.csv`,
  `audit_R_recover_*.polisyos-audit.tar.gz`

## Source Package Inventory

Current file counts under `src/polisyos`:

| Package | Python files | Markdown files | Other files |
| ------- | ------------ | -------------- | ----------- |
| `<root files>` | 2 | 0 | 0 |
| `berl` | 31 | 0 | 1 |
| `calibration` | 7 | 0 | 0 |
| `common` | 11 | 2 | 0 |
| `core` | 185 | 12 | 0 |
| `data_forge` | 240 | 8 | 3 |
| `ddm_15_7` | 17 | 2 | 13 |
| `fabric` | 279 | 8 | 2 |
| `foundry` | 505 | 12 | 3 |
| `ir` | 185 | 10 | 2 |
| `lex` | 35 | 5 | 0 |
| `runtime` | 60 | 4 | 0 |
| `scholar` | 25 | 3 | 0 |
| `scientist` | 517 | 16 | 0 |
| `synthetic_world` | 31 | 1 | 4 |

Immediate `src/polisyos` entries not represented as package directories:

- `.DS_Store`
- `__init__.py`
- `__pycache__/`
- `packs/`
- `py.typed`

Deleted package roots from the worktree status, not from this report:

- `src/polisyos/academic`
- `src/polisyos/datasets`
- `src/polisyos/ukraine_data`
- `src/polisyos/batch_common`
- `src/polisyos/batch_snapshot`
- `src/polisyos/lex/batch`
- `src/polisyos/lex/corpus`

## Import Graph Baseline

The AST scan parsed all Python files under `src/polisyos` with zero parse
errors.

| Metric | Value |
| ------ | ----- |
| Python files scanned | 2,129 |
| Parse errors | 0 |
| Existing deep-import baseline file | `architecture/baselines/imports/deep_import.json` |
| Deep-import baseline edges in file | 3,299 |
| Baseline file status | Modified in current worktree; not overwritten by this inventory |

Highest internal-import sources from the fresh scan:

| Source | Internal imports |
| ------ | ---------------- |
| `scientist` | 3,026 |
| `foundry` | 2,115 |
| `fabric` | 1,124 |
| `data_forge` | 686 |
| `ir` | 606 |
| `runtime` | 363 |
| `core` | 292 |
| `lex` | 193 |
| `scholar` | 104 |
| `berl` | 66 |
| `ddm_15_7` | 32 |
| `synthetic_world` | 22 |
| `calibration` | 19 |
| `common` | 5 |

High-volume cross-package edges from the fresh scan:

| Source | Target | Count |
| ------ | ------ | ----- |
| `scientist` | `core` | 719 |
| `foundry` | `ir` | 519 |
| `scientist` | `ir` | 382 |
| `foundry` | `core` | 347 |
| `fabric` | `core` | 254 |
| `fabric` | `ir` | 184 |
| `runtime` | `core` | 157 |
| `scientist` | `foundry` | 105 |
| `scientist` | `common` | 93 |
| `fabric` | `common` | 61 |
| `lex` | `ir` | 57 |
| `lex` | `core` | 56 |
| `data_forge` | `ir` | 54 |
| `data_forge` | `common` | 43 |
| `scholar` | `core` | 38 |
| `core` | `common` | 31 |
| `core` | `ir` | 26 |
| `foundry` | `common` | 25 |
| `data_forge` | `fabric` | 24 |

Top deep-import targets from the fresh scan:

| Target module | Count |
| ------------- | ----- |
| `polisyos.core.artifacts.manifest` | 250 |
| `polisyos.common.logger` | 238 |
| `polisyos.core.canon` | 236 |
| `polisyos.foundry.methods.base` | 201 |
| `polisyos.core.observability.determinism` | 165 |
| `polisyos.core.artifacts.store` | 155 |
| `polisyos.ir.refs` | 138 |
| `polisyos.ir.analytics.causal_graph` | 104 |
| `polisyos.ir.canon` | 93 |
| `polisyos.core.observability` | 88 |
| `polisyos.ir.artifacts` | 86 |
| `polisyos.scientist.engine.state` | 85 |
| `polisyos.core.artifacts.ids` | 76 |
| `polisyos.core.components` | 73 |
| `polisyos.ir.connectors` | 71 |
| `polisyos.scientist.engine.context` | 71 |
| `polisyos.scientist.engine.protocol` | 69 |
| `polisyos.scientist.nodes.builtins.state_keys` | 64 |
| `polisyos.core.contracts.foundry` | 63 |
| `polisyos.ir.analytics.causal` | 61 |
| `polisyos.data_forge.kernel.pipeline.manifests` | 33 |

## Layer Contract Baseline

Layer and forbidden-contract checks are report-only in Phase -1. The counts
below are candidates derived from the fresh AST scan and
`architecture/imports/contracts.toml`; they are not enforcement results.

Layer order from the current import contract:

| Layer index | Package roots |
| ----------- | ------------- |
| 0 | `runtime` |
| 1 | `scientist` |
| 2 | `packs`, `scholar`, `foundry`, `lex`, `data_forge`, `fabric` |
| 3 | `core` |
| 4 | `ir` |
| 5 | `common` |

Candidate layer violations:

| Source | Target | Count | Example |
| ------ | ------ | ----- | ------- |
| `ir` | `foundry` | 13 | `src/polisyos/ir/analytics/strategic.py -> polisyos.foundry.methods.catalog.causal.strategic` |
| `data_forge` | `scientist` | 6 | `src/polisyos/data_forge/domains/academic/batch/benchmark.py -> polisyos.scientist.cross_graph.feedback` |
| `ir` | `scientist` | 6 | `src/polisyos/ir/analytics/alignment_certification.py -> polisyos.scientist.cross_graph.compiler` |
| `foundry` | `scientist` | 5 | `src/polisyos/foundry/calibration/calibrator.py -> polisyos.scientist.autotune.calibration` |
| `core` | `scientist` | 4 | `src/polisyos/core/components/_cli_metric_validation.py -> polisyos.scientist.validation.metrics` |
| `lex` | `scientist` | 4 | `src/polisyos/lex/interventions.py -> polisyos.scientist.policy_design.schema` |
| `ir` | `data_forge` | 3 | `src/polisyos/ir/analytics/alignment_certification.py -> polisyos.data_forge.read_api.catalog` |
| `ir` | `core` | 2 | `src/polisyos/ir/analytics/phase4_dynamics.py -> polisyos.core.contracts.foundry` |
| `scientist` | `runtime` | 2 | `src/polisyos/scientist/replay/verification.py -> polisyos.runtime.replay` |

Unmapped source roots for the layer contract:

| Source root | Internal imports |
| ----------- | ---------------- |
| `berl` | 66 |
| `ddm_15_7` | 32 |
| `synthetic_world` | 22 |
| `calibration` | 19 |

Candidate forbidden-contract violations:

| Contract | Count | Example |
| -------- | ----- | ------- |
| `IR is a sink contract layer` | 21 | `src/polisyos/ir/analytics/alignment_certification.py -> polisyos.scientist.cross_graph.compiler` |
| `Foundry remains domain neutral` | 6 | `src/polisyos/foundry/agent_sim/wiring/contracts.py -> polisyos.lex.interventions` |
| `core must not depend on runtime or domain packages` | 4 | `src/polisyos/core/components/_cli_metric_validation.py -> polisyos.scientist.validation.metrics` |
| `Lex does not import domain-private siblings` | 4 | `src/polisyos/lex/interventions.py -> polisyos.scientist.policy_design.schema` |

Data Forge domain-independence candidate violations: 0.

## Public Surface Baseline

Public surface source of truth:

- `architecture/public_surface/contract.toml`
- `architecture/public_surface/inventory.json`
- `architecture/public_surface/`

Current `architecture/public_surface/contract.toml` lists 10 public package entries.
`architecture/public_surface/inventory.json` also lists 10 packages and is
modified in the current worktree; this inventory records it but does not
overwrite it.

| Module | Classification | Observed facade mode | Export count | Supported entrypoints |
| ------ | -------------- | -------------------- | ------------ | --------------------- |
| `polisyos.common` | `public_stable` | `lazy_facade` | 7 | `polisyos.common` |
| `polisyos.core` | `public_stable` | `lazy_facade` | 15 | `polisyos.core` |
| `polisyos.ir` | `public_stable` | `lazy_facade` | 273 | `polisyos.ir` |
| `polisyos.fabric` | `public_stable` | `lazy_facade` | 28 | `polisyos.fabric` |
| `polisyos.foundry` | `public_stable` | `lazy_facade` | 3 | `polisyos.foundry` |
| `polisyos.scientist` | `public_stable` | `lazy_facade` | 4 | `polisyos.scientist` |
| `polisyos.runtime` | `public_stable` | `lazy_facade` | 10 | `polisyos.runtime` |
| `polisyos.lex` | `public_stable` | `lazy_facade` | 50 | `polisyos.lex` |
| `polisyos.scholar` | `public_experimental` | `lazy_facade` | 16 | `polisyos.scholar` |
| `polisyos.data_forge` | `public_experimental` | `eager_exports` | 2 | `polisyos.data_forge`, `polisyos.data_forge.read_api` |

Current source roots not listed as public packages:

- `polisyos.berl`
- `polisyos.calibration`
- `polisyos.ddm_15_7`
- `polisyos.synthetic_world`

These roots are internal by default unless Phase 0 explicitly adds them to the
public-surface contract.

## Generated Artifact Inventory

Generated artifact source of truth:

- `architecture/generated_artifacts.toml`
- `docs/reference/generated-artifacts.md`

Registry summary:

| Family | Outputs | Present | Missing | Gate | Commit policy |
| ------ | ------- | ------- | ------- | ---- | ------------- |
| `abi-schema-snapshots` | 4 | 4 | 0 | `automated` | `committed` |
| `fabric-connector-contract-registry` | 1 | 1 | 0 | `automated` | `committed` |
| `runtime-openapi-snapshot` | 1 | 1 | 0 | `automated` | `committed` |
| `runtime-api-client` | 2 | 2 | 0 | `automated` | `committed` |
| `runtime-dashboard-api-types` | 1 | 1 | 0 | `automated` | `committed` |
| `connector-recorded-fixtures` | 1 | 1 | 0 | `manual_review` | `committed` |
| `runtime-dashboard-contract-fixtures` | 1 | 1 | 0 | `manual_review` | `committed` |
| `benchmark-reports-and-bundle-stats` | 2 | 1 | 1 | `manual_review` | `mixed` |
| `audit-and-evidence-artifacts` | 3 | 1 | 2 | `manual_review` | `mixed` |
| `public-surface-inventory` | 2 | 2 | 0 | `automated` | `committed` |
| `release-sbom` | 1 | 1 | 0 | `automated` | `committed` |

Generated ownership, regeneration, freshness, and header-signal baseline:

| Family | Owner | Regen commands | Checked output files | Header-signal files | Freshness signal |
| ------ | ----- | -------------- | -------------------- | ------------------- | ---------------- |
| `abi-schema-snapshots` | `team-polisyos` | 1 | 23 | 2 | ABI-visible IR or Fabric contracts change. |
| `fabric-connector-contract-registry` | `team-polisyos` | 1 | 1 | 0 | Source connector contracts or governance metadata change. |
| `runtime-openapi-snapshot` | `team-polisyos` | 1 | 1 | 0 | Runtime routes, DTOs, or OpenAPI examples change. |
| `runtime-api-client` | `team-polisyos` | 1 | 2 | 2 | Runtime OpenAPI snapshot changes. |
| `runtime-dashboard-api-types` | `team-polisyos` | 1 | 1 | 1 | Runtime OpenAPI changes affect dashboard-facing types. |
| `connector-recorded-fixtures` | `team-polisyos` | 3 | 9 | 0 | Connector contracts, source profiles, or upstream response shapes change. |
| `runtime-dashboard-contract-fixtures` | `team-polisyos` | 1 | 20 | 19 | Dashboard contract fixtures are intentionally updated. |
| `benchmark-reports-and-bundle-stats` | `team-polisyos` | 2 | 20 | 0 | Benchmark evidence packs or bundle baselines are intentionally reviewed. |
| `audit-and-evidence-artifacts` | `team-polisyos` | 1 | 20 | 16 | Audit outputs are intentionally reviewed as evidence packs. |
| `public-surface-inventory` | `team-architecture` | 1 | 3 | 1 | Supported public entrypoints, `__all__`, or signatures change. |
| `release-sbom` | `team-security` | 1 | 1 | 1 | Release candidate or dependency-lock changes enter a release branch. |

Primary regeneration commands are recorded in
`architecture/generated_artifacts.toml`; this table records their current
presence and header/freshness baseline without running regeneration.

Missing mixed-policy outputs:

- `apps/runtime-dashboard/dist/bundle-stats.json`
- `apps/runtime-dashboard/npm-audit-report.json`
- `apps/runtime-dashboard/npm-audit-summary.md`

Untracked schema candidates observed in the worktree:

- `schemas/artifacts/data_forge_artifact_ref_v1.schema.json`
- `schemas/artifacts/data_forge_artifact_trace_metadata_v1.schema.json`
- `schemas/artifacts/data_forge_domain_artifact_v1.schema.json`
- `schemas/manifests/data_forge_publish_manifest_v1.schema.json`
- `schemas/manifests/data_forge_raw_manifest_v1.schema.json`
- `schemas/manifests/data_forge_stage_manifest_v1.schema.json`

These need Phase 0/Phase 4 registration decisions before generated-artifact
gates become fail-closed.

## Tests Inventory

Current file counts under `tests/`:

| Test area | Files |
| --------- | ----- |
| `scientist` | 469 |
| `foundry` | 442 |
| `fabric` | 112 |
| `data_forge` | 101 |
| `ir` | 101 |
| `core` | 76 |
| `tools` | 54 |
| `runtime` | 44 |
| `academic` | 39 |
| `fixtures` | 37 |
| `datasets` | 23 |
| `contract` | 22 |
| `performance` | 12 |
| `lex` | 11 |
| `common` | 8 |
| `scholar` | 8 |
| `ukraine_data` | 7 |
| `berl` | 5 |
| `calibration` | 5 |
| `ddm_15_7` | 5 |
| `integration` | 4 |
| Other root files/areas | 17 |

Legacy package mirrors remain in tests even when their old source package roots
are deleted in the worktree. Phase 3 must decide whether each test area moves
to `tests/data_forge`, `tests/unit`, `tests/integration`, or stays as a
compatibility suite.

## Tools And Scripts Inventory

`tools/registry.py` defines the zoned command model:

| Zone | Categories |
| ---- | ---------- |
| `devx` | `workspace`, `architecture`, `connectors`, `foundry` |
| `quality` | `lint`, `diagnostics`, `validation`, `testing`, `ci` |
| `ops` | `cloud`, `release`, `migrations`, `runtime`, `data`, `ukraine_data`, `calibration` |
| `research` | `benchmarks`, `demos` |

Top-level tool file counts:

| Path under `tools/` | Files |
| ------------------- | ----- |
| `ops` | 90 |
| `quality` | 74 |
| `devx` | 42 |
| `cloud` | 40 |
| `ci` | 33 |
| `research` | 32 |
| `benchmarks` | 21 |
| `workspace` | 21 |
| `diagnostics` | 16 |
| `design` | 14 |
| `lint` | 13 |
| `ukraine_data` | 12 |
| `_lib` | 11 |
| `architecture` | 11 |
| `validation` | 11 |
| `demos` | 8 |
| `release` | 8 |
| `runtime` | 8 |
| `data` | 6 |
| `testing` | 6 |
| `connectors` | 4 |
| `foundry` | 4 |
| `migrations` | 4 |
| `calibration` | 3 |
| `_deprecated` | 2 |

Compatibility/duplicate surfaces still present:

- `tools/ops/cloud/*` mirrors `tools/ops/cloud/*`.
- `tools/ops/ukraine_data/*` mirrors `tools/ops/ukraine_data/*`.
- `tools/ops/data/*` mirrors `tools/ops/data/*`.
- `tools/devx/workspace/*` mirrors `tools/devx/workspace/*`.
- `tools/research/benchmarks/*` mirrors `tools/research/benchmarks/*`.
- `tools/quality/lint`, `tools/quality/diagnostics`, `tools/quality/validation`, `tools/quality/testing`, and
  `tools/ci` mirror `tools/quality/*`.

Legacy root-level command surfaces still present:

- `scripts/`
- `cloud_deploy/`
- `deploy/`
- `docker/`
- `gcp/`

These are Phase 3 topology-cleanup candidates, not Phase -1 moves.

## Docs Inventory

Docs lifecycle counts:

| Area | Files |
| ---- | ----- |
| `docs/adr` | 140 |
| `docs/reference` | 125 |
| `docs/archive` | 31 |
| `docs/how-to` | 27 |
| `docs/brand` | 19 |
| `docs/migration` | 18 |
| `docs/runbooks` | 18 |
| `docs/contracts` | 15 |
| `docs/explanation` | 11 |
| `docs/plans/active` | 10 |
| `docs/tutorials` | 5 |
| `docs/fedramp` | 3 |
| `docs/quality` | 3 |
| Other docs files/areas | 9 |

Active plan entries:

- `docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`
- `docs/plans/active/DATA_FORGE_CUTOVER_READINESS.md`
- `docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md`
- `release/design-wave1-release-notes.md`
- `docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md`
- `docs/plans/accepted/REPOSITORY_SOTA_PHASE_0_CONTRACTS.md`
- `docs/archive/reports/REPOSITORY_SOTA_PHASE_MINUS_1_5_CLASSIFICATION.md`
- `docs/archive/reports/REPOSITORY_SOTA_PHASE_MINUS_1_INVENTORY.md`
- `docs/plans/accepted/REPOSITORY_SOTA_PLAN.md`
- `docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md`

Accepted plans currently contain only `.gitkeep`.

Top-level `docs/*.md` still contains many plan/audit/architecture files that
need lifecycle classification in later phases, including:

- `docs/plans/archive/DATA_FORGE_CONSOLIDATION_PLAN_ROOT_LEGACY.md`
- `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
- `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`
- `docs/plans/active/UKRAINE_FUNDING_INTELLIGENCE_PLAN.md`
- `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`
- `docs/plans/active/TOOLS_AUDIT_REMEDIATION_PLAN.md`
- `docs/plans/active/FRONTEND_SOTA_PLAN.md`
- `docs/plans/active/INFRASTRUCTURE_SOTA_PLAN.md`

## Schemas Inventory

Current file counts under `schemas/`:

| Area | Files |
| ---- | ----- |
| `snapshots` | 111 |
| `topology` | 9 |
| `fabric` | 6 |
| `artifacts` | 4 |
| `manifests` | 4 |
| `ops` | 2 |
| `api` | 1 |
| `codegen` | 1 |
| `events` | 1 |
| root schema files | 3 |

The six untracked Data Forge schema files listed in the generated-artifact
inventory should be classified before schema drift checks are tightened.

## Frontend Inventory

Current file counts under `frontend/`:

| Entry | Files |
| ----- | ----- |
| `runtime-dashboard` | 1,034 |
| `runtime-api-client` | 9 |
| `runtime-reference-shell` | 9 |
| `README.md` | 1 |

Observed local/generated frontend outputs:

- `runtime-dashboard/node_modules/`
- `runtime-dashboard/dist/`
- `runtime-dashboard/coverage/`
- `runtime-dashboard/playwright-report/`
- `runtime-dashboard/test-results/`
- `runtime-dashboard/storybook-static/`
- `runtime-dashboard/output/`
- `runtime-dashboard/.tmp/`

Tracked/generated frontend artifacts already registered:

- `packages/runtime-api-client/runtimeApiClient.ts`
- `packages/runtime-api-client/runtimeApiClient.js`
- `apps/runtime-dashboard/src/api/types.ts`

## Ops Inventory

Current file counts under `ops/`:

| Area | Files |
| ---- | ----- |
| `helm` | 39 |
| `opa` | 15 |
| `grafana` | 9 |
| `prometheus` | 9 |
| `observability` | 8 |
| `migrations` | 6 |
| `security` | 5 |
| `terraform` | 2 |
| root ops files | 3 |

Target subtrees for later cleanup remain `ops/cloud`, `ops/docker`,
`ops/release`, `ops/runtime`, `ops/data`, and `ops/security`; some equivalent
material still lives in legacy root-level `cloud_deploy/`, `deploy/`, `docker/`,
and `gcp/`.

## Data And Local State Inventory

Root `data/` currently has one visible entry:

| Entry | Dirs | Files | Size |
| ----- | ---- | ----- | ---- |
| `data/lex_real_doc_smoke_20260321.json` | 0 | 1 | 16K |

Product-root `policy-engine/data/`:

| Entry | Dirs | Files | Size |
| ----- | ---- | ----- | ---- |
| `policy-engine/data/README.md` | 0 | 1 | 24K |
| `policy-engine/data/academic_gold` | 1 | 4 | 28K |
| `policy-engine/data/curated` | 1 | 11 | 44K |
| `policy-engine/data/databases` | 1 | 8 | 16M |
| `policy-engine/data/dataset_catalog` | 1 | 4 | 172K |
| `policy-engine/data/raw` | 1 | 4 | 20K |

Product-root `policy-engine/production_data/` contains local runtime data and
must remain local/ignored unless explicitly promoted:

| Entry | Dirs | Files | Size |
| ----- | ---- | ----- | ---- |
| `policy-engine/production_data/all_records.jsonl` | 0 | 1 | 725M |
| `policy-engine/production_data/benchmark_report.json` | 0 | 1 | 104K |
| `policy-engine/production_data/consumer_readiness.json` | 0 | 1 | 4.0K |
| `policy-engine/production_data/dataset_catalog.duckdb` | 0 | 1 | 1.2G |
| `policy-engine/production_data/ds_dataset_embeddings.npz` | 0 | 1 | 539M |
| `policy-engine/production_data/ds_dataset_index.hnsw` | 0 | 1 | 555M |
| `policy-engine/production_data/duplicates_report.csv` | 0 | 1 | 980K |
| `policy-engine/production_data/lex_current_20260501` | 4 | 9 | 20G |
| `policy-engine/production_data/manifest.json` | 0 | 1 | 8.0K |
| `policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z` | 6 | 21 | 3.2G |
| `policy-engine/production_data/qc_report.json` | 0 | 1 | 16K |
| `policy-engine/production_data/ukraine_agent_simulation_baseline_20260410` | 11 | 41 | 1.3G |

## Planned Move Baseline

Every later structural move needs a source path, target path, owner, risk class,
and acceptance evidence. This table records the Phase -1 baseline only.

| Move family | Source path | Target path | Owner | Risk | Evidence requirement |
| ----------- | ----------- | ----------- | ----- | ---- | -------------------- |
| Root reports | `compileall.txt`, `ruff_stats.txt`, `import_gate.txt`, `summary.json`, `test_collect.txt`, `stale_sources_missing_paths.txt` | `.polisyos/reports/` or ignored local report policy | `team-devx` | Low | Loose-file classification plus topology gate baseline. |
| Root research helpers | `filter_topics.py`, `organize_relevant_topics.py` | `tools/research/` or archived with topic data manifest | `team-research` | Medium | Command inventory, import smoke check, and rollback note. |
| Root topic artifacts | `topics.csv`, `relevant_topics_domain_files/` | root `data/`, `policy-engine/data/fixtures`, or ignored local data | `team-data-forge` | Medium | Fixture/data classification and manifest decision. |
| Historical root spec | `scm-implementation-spec-v3.md` | `docs/archive/specs/` or reference docs | `team-docs` | Low | Docs lifecycle classification and link check. |
| Product audit bundles | `policy-engine/audit_R_recover_*.polisyos-audit.tar.gz` | `.polisyos/audits/` or ignored local audit policy | `team-quality` | Low | Audit classification and ignore-rule evidence. |
| Product accidental loose files | `policy-engine/=2.5.0`, `policy-engine/.DS_Store`, `policy-engine/env_example.txt` | removal or canonical `.env.example` policy | `team-devx` | Low | Loose-file classification and topology gate baseline. |
| Workflows | `policy-engine/.github` | repo-root `.github` plus `ops/ci/templates` | `team-platform` | Medium | Workflow diff, CI dry-run evidence, rollback note. |
| Cloud/deploy wrappers | `policy-engine/cloud_deploy`, `policy-engine/deploy`, `policy-engine/docker`, `policy-engine/gcp` | `policy-engine/ops/cloud`, `policy-engine/ops/docker`, `policy-engine/ops/release`, `policy-engine/ops/observability` | `team-ops` | High | Wrapper registry, command smoke checks, deployment dry-run evidence. |
| Tool compatibility packages | `tools/ops/cloud`, `tools/ops/ukraine_data`, `tools/ops/data`, `tools/devx/workspace`, `tools/research/benchmarks`, `tools/quality/lint`, `tools/quality/diagnostics`, `tools/quality/validation`, `tools/quality/testing`, `tools/ci` | `tools/ops/*`, `tools/devx/*`, `tools/research/*`, `tools/quality/*` | `team-devx` | Medium | Command registry diff, compatibility aliases, tool tests. |
| Root scripts | `policy-engine/scripts` | `policy-engine/tools` | `team-devx` | Medium | Alias coverage, command smoke checks, wrapper sunset entries. |
| Top-level docs | `policy-engine/docs/*.md` | `docs/plans/*`, `docs/archive/*`, `docs/reference/*`, `docs/how-to/*`, or `docs/explanation/*` | `team-docs` | Low | Docs lifecycle classification, link check, docs freshness baseline. |
| Legacy test mirrors | `tests/academic`, `tests/datasets`, `tests/ukraine_data`, legacy `tests/unit/lex` paths | `tests/data_forge`, `tests/unit`, `tests/integration`, or compatibility suites | `team-quality` | Medium | Test collection baseline, mapping to source package, compatibility coverage. |
| Data Forge domain sources | deleted legacy source roots and new `src/polisyos/data_forge/domains/*` | target domain layout under `data_forge` | `team-data-forge` | High | Golden/replay/differential evidence, import graph baseline, rollback notes. |
| Generated frontend outputs | `apps/runtime-dashboard/dist`, `coverage`, `storybook-static`, `playwright-report`, `test-results`, `output`, `.tmp` | ignored generated-output policy or registered generated artifacts | `team-frontend` | Medium | Generated-artifact registry decision and drift check. |
| Production data | `policy-engine/production_data/*` | ignored local runtime data or explicit release artifact registry | `team-data-forge` | High | Retention class, artifact manifest, size/PII classification, rollback note. |

## Acceptance Evidence

Phase -1 acceptance status:

1. No structural moves were performed.
2. Topology inventory was refreshed for repo root, product root,
   `src/polisyos`, tests, tools, ops, docs, schemas, frontend, and local data
   paths.
3. Import graph, deep-import, layer-violation, and public-surface baselines were
   refreshed in this report.
4. Generated-artifact registry status and untracked schema candidates were
   recorded, including owners, regeneration commands, freshness signals, and
   header-signal counts.
5. Tools and scripts were grouped by canonical target namespace and
   compatibility status.
6. Docs were inventoried against active/accepted/archive lifecycle pressure.
7. Current branch, HEAD, dirty worktree counts, and unrelated user edits were
   recorded.
8. Every planned move family now has source path, target path, owner, risk
   class, and evidence requirement.

This report is safe to use as the baseline for Phase -1.5 and Phase 0, but
those phases should refresh any volatile counts again if the worktree changes
materially before execution.
