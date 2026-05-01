---
title: Repository SOTA Plan
status: active
owner: team-polisyos
created: 2026-04-18
last_verified: 2026-04-29
stability: draft
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
8. The active Lex NPA corpus run is a launch gate for this plan, not a reason to
   keep the plan conservative after execution begins.

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
| Artifact governance      | `license`, `pii_level`, `retention_class`, `owner`, `producer_version`      |

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

## Pre-Execution Hold

As of 2026-04-29, the Lex NPA corpus processing is nearing completion but is not
yet complete. This document is now the full repository SOTA execution plan, not
a conservative implementation overlay. Execution remains on hold until the user
explicitly confirms that the NPA processing run has completed.

During the hold, do not execute repository moves, gate flips, cutovers, cleanup,
or production-path rewrites from this plan. Plan edits, evidence review, and
read-only verification are allowed.

The hold ends only after all of the following are true:

1. The user confirms that NPA processing is complete.
2. Queue 2 `shard_4` and Queue 3 Waves 1 through 5 have completed.
3. Shard merge, QC, and publication checks have passed.
4. A cutover readiness note records the production source revision, artifact
   roots, manifest schemas, output layouts, and merge/QC evidence.
5. The working tree is reviewed so repository-SOTA execution starts from an
   understood baseline, with unrelated parallel work either merged, staged
   separately, or explicitly excluded.
6. Golden snapshots or differential baselines are captured for behavior that
   will be affected by package moves, cloud runner cutovers, or Data Forge
   publication changes.

Current repository state to account for before execution:

| Area | Current state |
| ---- | ------------- |
| ADRs | ADR-0111 through ADR-0128 are present. |
| Architecture contracts | `architecture/*.toml` and `schemas/topology/*.schema.json` are present. |
| Inventory evidence | Phase -1 inventory, Phase -1.5 classification, and Phase 0 contract notes exist and should be refreshed if stale before execution. |
| Lex/cloud paths | Existing Lex batch, shared-batch, cloud runner, and compatibility wrapper paths remain the production compatibility surface until cutover readiness is recorded. |
| Data Forge | Additive Data Forge foundation work may exist in the tree, but execution of this plan must validate and integrate it through the strict phase sequence below. |
| Hold contract | `architecture/conservative_overlay.toml` is a temporary hold contract. Close or supersede it during Phase 0 after the cutover readiness gate passes. |

Once the hold is released, the plan executes in strict mode:

1. Structural moves are allowed when their phase preconditions and shims are in
   place.
2. Compatibility wrappers are temporary migration tools, not long-term target
   architecture.
3. Gates move from report-only to fail-closed on the schedule below.
4. Lex legal and shared-batch cutovers require replay, golden, or differential
   evidence before production entrypoints switch.
5. Report-only exceptions after Phase 5 require explicit entries in
   `architecture/guardrail_exceptions.toml` or the relevant architecture
   contract.

## Target Contracts

The first implementation phase creates these machine-readable contracts:

| File                                      | Purpose                                                             |
| ----------------------------------------- | ------------------------------------------------------------------- |
| `architecture/topology.toml`              | Top-level path allowlist, category, owner, commit policy            |
| `architecture/package_boundaries.toml`    | Package owners, allowed dependencies, public facades                |
| `architecture/import_contracts.toml`      | Import-linter contracts for layers, forbidden imports, independence |
| `architecture/migration_shims.toml`       | Compatibility shims with owner and sunset                           |
| `architecture/complexity_exceptions.toml` | Temporary god-file/module-size exceptions                           |
| `architecture/public_surface.toml`        | Public entrypoints and supported facade modes                       |
| `architecture/generated_artifacts.toml`   | Generated artifact registry with freshness gates                    |
| `schemas/topology/*.schema.json`          | JSON Schema for architecture TOML contracts                         |

Guardrails must delegate to dedicated tools where possible: import-linter for
imports, deptry for dependency hygiene, generated-artifact drift checks for
codegen, and OPA policies for repo-wide allow/deny rules.

## Gates Inventory

Before the pre-execution hold ends, gate behavior must not be tightened as part
of this plan. After execution begins, Phase 5 turns these gates from report-only
or allowlisted checks into fail-closed CI/pre-commit checks:

| Gate             | Source                                                                      |
| ---------------- | --------------------------------------------------------------------------- |
| import-linter    | `architecture/import_contracts.toml`                                        |
| deptry           | `pyproject.toml` dependency declarations                                    |
| topology-gate    | `architecture/topology.toml`                                                |
| shim-audit       | `architecture/migration_shims.toml`                                         |
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

Repository root remains fortified option C:

```text
polisyos/
|-- .github/                  # active GitHub workflows/actions/rules
|-- README.md
|-- CODE_OF_CONDUCT.md
|-- SECURITY.md
|-- SUPPORT.md
|-- lefthook.yml
|-- renovate.json
|-- design/                   # non-product design material
|-- data/                     # ignored local lake
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
|-- data/                     # tiny committed fixtures/contracts only
`-- .polisyos/                # ignored local runtime state
```

## Required Structural Moves

Before the pre-execution hold ends, this table is planning-only. After execution
begins, it becomes the structural migration backlog and each move must carry the
required shim, owner, rollback path, and acceptance evidence.

| Area                                      | Required move                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Root loose files                          | Reports to `.polisyos/reports/`; scripts to `tools/research/` or `tools/workspace/`; data artifacts to root `data/` |
| `policy-engine/.github`                   | Move active workflows to root `.github`; templates to `ops/ci/templates`                                            |
| `cloud_deploy`, `deploy`, `docker`, `gcp` | Consolidate under `ops/cloud`, `ops/docker`, `ops/release`, `ops/observability`                                     |
| `tools/*` duplicates                      | Pick canonical namespace, move old homes to `_deprecated` wrappers with shim entries                                |
| `scripts/`                                | Wrapper-only or removed                                                                                             |
| `docs/*.md` plans                         | Move active plans to `docs/plans/active`, accepted plans to `docs/plans/accepted`, history to `docs/archive/plans`  |
| `tests/*` old package mirrors             | Move with source topology to `tests/unit` or `tests/data_forge`                                                     |
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
|-- data/
|-- scripts/
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

Local root `data/` uses medallion semantics:

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

## Phases

| Phase | Name                              | Deliverables                                                                         |
| ----- | --------------------------------- | ------------------------------------------------------------------------------------ |
| -1    | Inventory                         | Topology inventory, import graph, duplicate tool inventory, data-root inventory      |
| -1.5  | Loose-file amnesty                | Move/delete reports, audit bundles, accidental files, duplicate venvs, local outputs |
| 0     | Contracts and ADRs                | ADR-0111..0120, `architecture/*.toml`, topology schemas, public surface entries      |
| 1     | Data Forge foundation             | Asset-centric kernel, schema registry, snapshot transactions, read_api rules         |
| 2     | Repo topology cleanup             | Tools/ops/docs/tests consolidation with shims                                        |
| 3     | Generated and frontend discipline | Frontend workspace plan, generated artifact freshness, schema drift gates            |
| 4     | Data lake and retention           | Medallion data layout, `.polisyos/README`, retention/GC policy                       |
| 5     | Enforcement                       | CI/pre-commit gates for import-linter, topology, generated drift, docs freshness     |

### Strict Execution Rules

| Phase | Execution rule |
| ----- | -------------- |
| -1 | Refresh the read-only inventory and record any drift since the 2026-04-24 snapshot before moving files. |
| -1.5 | Perform actual amnesty cleanup: remove, archive, or relocate loose files and local outputs after confirming no active Lex/cloud dependency. |
| 0 | Validate ADR and architecture contract coverage, then close or supersede the temporary hold contract. |
| 1 | Complete Data Forge foundation as the strict build-time artifact producer; runtime consumers use stable read APIs only. |
| 2 | Execute topology cleanup with registered shims, rollback notes, and compatibility tests. |
| 3 | Enforce generated/frontend discipline with registry entries and drift checks. |
| 4 | Establish medallion data layout, retention classes, `.polisyos/README`, and GC policy. |
| 5 | Turn architecture, import, generated-artifact, docs, security, and hygiene gates fail-closed unless an explicit exception exists. |

Pre-execution evidence already captured:

- Phase -1 inventory:
  `docs/plans/active/REPOSITORY_SOTA_PHASE_MINUS_1_INVENTORY.md`.
- Phase -1.5 classification:
  `docs/plans/active/REPOSITORY_SOTA_PHASE_MINUS_1_5_CLASSIFICATION.md`.
- Phase 0 contract note:
  `docs/plans/active/REPOSITORY_SOTA_PHASE_0_CONTRACTS.md`.

These evidence files were captured while the run was still active. Refresh them
after the hold is released if the tree has drifted.

### Phase -1.5 Acceptance

| Item             | Done when                                                                                                                                                |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Audit bundles    | `audit_R_recover_*.tar.gz` are removed or moved under `.polisyos/audits/`                                                                                |
| Root reports     | `compileall.txt`, `ruff_stats.txt`, `import_gate.txt`, `summary.json`, `test_collect.txt`, and stale-source reports are ignored local reports            |
| Accidental files | `=2.5.0` and `.DS_Store` are removed                                                                                                                     |
| Virtualenvs      | `.venv_codex`, `.tmp_c7_venv`, and other scratch venvs are removed or ignored in favor of one `.venv`                                                    |
| Local outputs    | `output/`, `runs/`, `tmp/`, `logs/`, `out/`, `dist/`, `site/`, and `benchmark-results/` are local-only                                                   |
| Historical specs | `scm-implementation-spec-v3.md` is archived under `docs/archive/specs/` or replaced by an ADR/reference doc                                              |
| Topic artifacts  | `topics.csv`, `all_1000_policy_topics.csv`, and `relevant_topics_domain_files/` are classified as fixture, ignored local data, or manifest-backed source |

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
4. A compatibility shim cannot appear without `architecture/migration_shims.toml`.
5. Active docs cannot live indefinitely in `docs/*.md`.
6. Runtime code cannot import Data Forge kernel/domain internals.
7. Large local outputs remain ignored, hidden, and cleanable.
8. The pre-execution hold cannot be released without a cutover readiness note.
9. Report-only gates cannot remain report-only after Phase 5 unless an explicit
   exception exists.
10. Legal and shared-batch production cutovers require golden, replay, or
    differential evidence before entrypoints switch.
