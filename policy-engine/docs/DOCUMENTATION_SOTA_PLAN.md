# Documentation SOTA Plan

> Детальный, максимально параллельный план доведения документации PolicyOS
> Policy Engine до SOTA-состояния после большого рефакторинга.
>
> Scope: `policy-engine/`
> Last updated: 2026-04-17

## Зачем этот план

Основной рефакторинг и развитие системы шли не одной линейной задачей, а через
шесть больших remediation-программ:

- `docs/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md`
- `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`
- `docs/FOUNDRY_REMEDIATION_PLAN.md`
- `docs/IR_AUDIT_REMEDIATION_PLAN.md`
- `docs/TOOLS_AUDIT_REMEDIATION_PLAN.md`
- `docs/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`

Поэтому документацию нельзя обновлять как один монолитный rewrite. Ее нужно
обновлять как параллельную программу работ: каждая подсистема получает свой
documentation lane, но все lanes сходятся в общих navigation, ownership,
reference, runbook и CI-gate правилах.

Цель: сделать документацию не красивым приложением к коду, а надежной рабочей
поверхностью для contributor-ов, operator-ов, security/compliance reviewer-ов и
domain/policy reader-ов.

SOTA для этой документации означает:

1. Published docs совпадают с текущим кодом, CLI, схемами, OpenAPI и CI.
2. Каждый public surface имеет owner, reference page, freshness marker и tests
   или validation gate.
3. Tutorials и how-to guides можно пройти на актуальном workspace.
4. Reference docs генерируются из кода или проверяются против кода.
5. Architecture explanations отражают текущие границы после refactor-а.
6. Runbooks содержат last-tested evidence, rollback path и escalation owner.
7. Docs drift блокируется локальными и CI-gates.

## Операционная модель параллельности

### Главный принцип

Работы делятся на независимые lanes по subsystem-ам. Линейно блокирующими
являются только:

1. D0 baseline/inventory, чтобы все работали по одной карте.
2. D1 source-of-truth mapping, чтобы не документировать устаревшие claims.
3. Финальная D6 integration review, чтобы свести все lanes в один docs site.

Все остальные работы должны идти параллельно.

### Parallel lanes

| Lane                       | Scope                                                                    | Primary source plan       | Может стартовать после |
| -------------------------- | ------------------------------------------------------------------------ | ------------------------- | ---------------------- |
| L0 Program / IA            | inventory, nav, archive policy, ownership model                          | this plan                 | сразу                  |
| L1 Core/Common/Runtime     | common, core, runtime, runtime HTTP, CAS, auth, observability            | Core/Common/Runtime plan  | D0                     |
| L2 Fabric                  | connectors, data plane, catalog, lineage, quality, streaming             | Fabric plan               | D0                     |
| L3 Foundry                 | compile/execute, executor, JAX, methods, calibration, reproducibility    | Foundry plan              | D0                     |
| L4 IR                      | canon, registry/linker, schemas, pass manager, transport, public surface | IR plan                   | D0                     |
| L5 Tools                   | CLI, tool runtime, registry, validation, consolidation, telemetry        | Tools plan                | D0                     |
| L6 Scientist               | workflows, agent, search, governance, causal validity, budget, metrics   | Scientist plan            | D0                     |
| L7 Frontend/API consumers  | runtime dashboard, API client, reference shell                           | Core + Scientist + Fabric | D1 API map             |
| L8 Ops/Security/Compliance | runbooks, SLO, audit, FedRAMP evidence, release gates                    | all plans                 | D1                     |
| L9 Automation/Gates        | mkdocs, docs accuracy, docstring, schema, OpenAPI, README freshness      | all plans                 | D1                     |

### Synchronization rules

- Каждый lane ведет свой checklist и не ждет остальные lanes, если не меняет
  global nav или shared terminology.

- Изменения в `mkdocs.yml`, `docs/index.md`, `docs/reference/index.md`,
  `docs/reference/ownership.md` и `docs/reference/quality-gates.md` идут через
  L0/L9 coordination, чтобы избежать merge conflicts.

- Generated reference pages обновляются только из canonical generator-а, если он
  существует.

- Если lane находит stale claim в другом subsystem-е, он добавляет finding в
  inventory, но не переписывает чужой technical content без owner review.

- Финальная интеграция идет волнами: reference first, then how-to/tutorials,
  then explanations/runbooks, then nav and gates.

## Current Repository Reality

Observed on 2026-04-17:

| Area                | Current state                                                                                                                     | SOTA gap                                                                      |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Product entry point | `policy-engine/README.md` exists and covers product root, quickstart, command map, and docs links.                                | Verify every snippet after refactor and keep README as short gateway.         |
| Docs site           | `policy-engine/mkdocs.yml` exists with MkDocs Material, `mkdocstrings`, search, Mermaid, Diataxis nav, runbooks, ADRs, contracts. | Nav is hand-curated and includes active-looking plan docs; reduce drift.      |
| Style rules         | `docs/style-guide.md` exists with docstring, docs accuracy and freshness rules.                                                   | Make the rules enforceable through gates and PR checklists.                   |
| Diataxis structure  | `tutorials`, `how-to`, `reference`, `explanation` exist.                                                                          | Refresh content against six remediation plans.                                |
| ADRs                | `docs/adr` is extensive.                                                                                                          | Add subsystem index, supersession visibility and refactor decision map.       |
| Contracts           | `docs/contracts` contains Trinity, merge semantics and E1/E2 specs.                                                               | Link each contract to schema snapshots, tests, code owner and runtime impact. |
| Operations          | `docs/runbooks` and `docs/reference/operations` exist.                                                                            | Rehearse and add last-tested evidence.                                        |
| Tooling             | Docs accuracy, semantic docstring, MkDocs strict, schema docs and tool docs generators exist.                                     | Compose them into one documented gate.                                        |
| Plan docs           | Multiple root-level `*_PLAN.md` and remediation docs exist.                                                                       | Classify active/closed/superseded/archive.                                    |

## Source Remediation Plans To Documentation Impact

| Source plan         | Refactor themes                                                                                                                                                                                      | Documentation surfaces to refresh                                                                                                                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Core/Common/Runtime | fail-closed auth, tenant isolation, write-path hardening, CAS/storage, serialization, signing, lifecycle, observability, SLI/SLO, API maturity                                                       | `README.md`, `src/polisyos/common/README.md`, `src/polisyos/core/README.md`, `src/polisyos/runtime/README.md`, `docs/reference/api/**`, `docs/reference/operations/**`, `docs/explanation/security-model.md`, runtime runbooks |
| Fabric              | connector security, bounded input, provenance, temporal policy, lifecycle, atomic persistence, schema registry, lineage, quality, time travel, streaming, catalog discovery                          | `src/polisyos/fabric/README.md`, `docs/reference/fabric/**`, `docs/connectors/CONTRIBUTING.md`, Fabric runbooks, data-plane architecture docs                                                                                  |
| Foundry             | compile/execute correctness, executor hardening, JAX semantics, numeric stability, reproducibility, methods catalog, UQ/calibration, agent simulation, benchmarks                                    | `src/polisyos/foundry/README.md`, `docs/reference/foundry/**`, `docs/explanation/causal-engine.md`, benchmark docs, reproducibility docs                                                                                       |
| IR                  | canon/CAS, registry/linker, validation, schema evolution, pass manager, estimand/lineage, uncertainty algebra, public surface, transport/interoperability                                            | `src/polisyos/ir/README.md`, `docs/reference/ir/**`, `docs/reference/schemas.md`, `docs/contracts/**`, ADR index                                                                                                               |
| Tools               | unified CLI, shared tooling runtime, packaging/import normalization, dependency graph, docs metadata, CI output, telemetry, consolidation, autofix/rule registry                                     | `tools/README.md`, `docs/reference/tools.md`, `docs/how-to/operate-ci-cd-platform.md`, contributor command map, validation docs                                                                                                |
| Scientist           | async/lifecycle correctness, budget, deterministic state, observability, tests/benchmarks, performance, API simplification, causal validity, governance/fairness/calibration, search/agent reasoning | `src/polisyos/scientist/README.md`, `docs/reference/scientist/**`, Scientist tutorials/how-to, decision/governance artifact docs                                                                                               |

## Work Package Format

Every parallel work package must be small enough to land independently and must
use this definition:

| Field           | Required content                                                         |
| --------------- | ------------------------------------------------------------------------ |
| Source plan     | Which remediation plan and phase/workstream produced the code change.    |
| Code surface    | Paths under `src/`, `tools/`, `frontend/`, `ops/`, `schemas/`, or tests. |
| Docs surface    | Exact docs/README files to update.                                       |
| Source of truth | Generator, schema, OpenAPI, CLI registry, ADR, test, or code owner.      |
| Validation      | Command or manual check proving docs match reality.                      |
| Owner           | Person/team/lane responsible for technical correctness.                  |
| Freshness       | Date and next review trigger.                                            |

## Phase D0 - Baseline, Inventory, Ownership

**Goal:** create a shared map so all lanes can work in parallel without
duplicating or contradicting each other.

**Duration:** 0.5-1 day.

**Hard dependency:** none.

### Parallel work packages

| Package                 | Lane  | Output                                                                                                   | Validation                                                          |
| ----------------------- | ----- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| D0-A Inventory skeleton | L0    | `docs/reference/documentation-inventory.md` with page, owner, status, source-of-truth, validation method | file exists and linked from `docs/reference/index.md`               |
| D0-B Plan status ledger | L0    | status table for all root-level `*_PLAN.md` docs                                                         | every plan has `active`, `closed`, `superseded`, or `archive`       |
| D0-C Baseline checks    | L9    | recorded output of docs QA commands                                                                      | commands run or blockers recorded                                   |
| D0-D Owner map          | L0/L8 | docs owner matrix in `docs/reference/ownership.md`                                                       | every lane has owner and backup                                     |
| D0-E Conflict map       | L0    | list of shared files requiring coordination                                                              | `mkdocs.yml`, home/index pages, ownership, quality gates identified |

### Baseline commands

```bash
cd policy-engine
uv run --extra docs python -m mkdocs build --strict
python3 tools/validation/check_docs_accuracy.py --repo-root .
uv run --extra docs python tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt
uv run polisyos-tools docs --output docs/reference/tools.md
uv run --extra ml polisyos-tools diagnostics gen-schema --check
python3 -m tools.cli workspace ci-parity --skip-browser
```

### Exit criteria

- Inventory page exists.
- Six source remediation plans are linked as canonical context for docs refresh.
- Every lane has a named owner and doc surfaces.
- Current docs QA failures are known and not rediscovered repeatedly.

## Phase D1 - Source-of-Truth Mapping By Remediation Plan

**Goal:** translate each remediation plan into a documentation impact map.

**Duration:** 1-2 days.

**Hard dependency:** D0 inventory skeleton.

**Parallelism:** all six subsystem lanes can run at the same time.

### D1-L1 Core/Common/Runtime mapping

Map source plan phases:

- Phase 0: fail-closed auth, runtime write path, crypto/integrity/redaction,
  race/cache/lifecycle hotfixes.

- Phase 1: error semantics, static analysis, property/mutation/fuzz/integration,
  observability and auditability.

- Phase 2: storage/serialization/immutability, runtime scalability, DI/config,
  API maturity.

- Phase 3: ADRs, diagrams, runbooks, security/compliance, CI ratchets.

Docs outputs:

- `docs/reference/api/index.md`
- `docs/reference/api/runs.md`
- `docs/reference/api/control.md`
- `docs/reference/api/artifacts.md`
- `docs/reference/api/versioning.md`
- `docs/reference/api/migration-guide.md`
- `docs/reference/operations/slo-error-budget.md`
- `docs/reference/operations/observability-topology.md`
- `docs/reference/security-compliance.md`
- `docs/explanation/security-model.md`
- `docs/runbooks/runtime-api-outage.md`
- `docs/runbooks/idempotency-incident.md`
- `docs/runbooks/key-rotation.md`
- `docs/runbooks/cas-opa-outage.md`
- `docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md`
- `src/polisyos/common/README.md`
- `src/polisyos/core/README.md`
- `src/polisyos/runtime/README.md`
- `src/polisyos/runtime/http/README.md`

Validation:

- Runtime OpenAPI contract check.
- Auth/tenant middleware tests linked from docs.
- Acceptance audit references current runtime gates.

### D1-L2 Fabric mapping

Map source plan phases:

- Phase 0: query/filter injection, bounded input, serialization/provenance,
  UTC temporal policy.

- Phase 1: deterministic lifecycle, atomic persistence, contention resilience,
  mutable state, bounded memory.

- Phase 2: schema merge, numeric quality bounds, units, canonical IDs,
  transform correctness.

- Phase 3: observability/SLO, lineage, schema compatibility, access control,
  retention.

- Phase 4: quality profiling, materialization, time travel.
- Phase 5: DLQ/quarantine, connector ecosystem, streaming/CDC, scale-out.
- Phase 6: semantic catalog, natural-language discovery, entity resolution.

Docs outputs:

- `docs/reference/fabric/index.md`
- `docs/reference/fabric/connectors.md`
- `docs/reference/fabric/profiles.md`
- `docs/reference/fabric/data-plane.md`
- `docs/connectors/CONTRIBUTING.md`
- `docs/how-to/add-data-source.md`
- `docs/how-to/manage-generated-artifacts.md`
- `docs/runbooks/cache-rebuild-storm.md`
- `docs/runbooks/retained-artifact-recovery.md`
- `docs/runbooks/artifact-corruption-recovery.md`
- `src/polisyos/fabric/README.md`
- `src/polisyos/fabric/connectors/README.md`
- `src/polisyos/fabric/data_plane/README.md`
- `src/polisyos/fabric/retrieval/README.md`
- `src/polisyos/fabric/world/README.md`

Validation:

- Connector registry tests linked from docs.
- Schema compatibility gate documented.
- Fabric quality/lineage examples point to current artifacts.

### D1-L3 Foundry mapping

Map source plan phases:

- Phase 0: program freeze and backlog normalization.
- Phase 1: correctness emergency train.
- Phase 2: execution kernel hardening.
- Phase 3: numerical stability and JAX semantics.
- Phase 4: performance, concurrency and reproducibility.
- Phase 5: Bayesian, UQ and calibration frontier.
- Phase 6: causal, ML, agent-sim and policy frontier.

Docs outputs:

- `docs/reference/foundry/index.md`
- `docs/reference/foundry/compile-execute.md`
- `docs/reference/foundry/calibration.md`
- `docs/reference/foundry/methods-catalog.md`
- `docs/reference/foundry/frontier-methods.md`
- `docs/reference/foundry/observability-reproducibility.md`
- `docs/reference/foundry/agent-sim.md`
- `docs/reference/foundry/state.md`
- `docs/explanation/causal-engine.md`
- `docs/how-to/run-causal-analysis.md`
- `docs/how-to/run-benchmarks.md`
- `docs/benchmarks/confidential-computing-overhead.md`
- `src/polisyos/foundry/README.md`
- `src/polisyos/foundry/methods/README.md`
- `src/polisyos/foundry/calibration/README.md`
- `src/polisyos/foundry/agent_sim/README.md`

Validation:

- Compile/execute quickstart runs or is clearly marked conceptual.
- Benchmark docs point to current benchmark commands.
- Numeric/JAX claims link to tests or ADRs.

### D1-L4 IR mapping

Map source plan phases:

- Phase 0: canon/CAS, registry/linker, silent failure containment.
- Phase 1: cross-model invariants, validator cleanup, schema compatibility.
- Phase 2: pass manager, analyses, estimand normalization, lineage graph,
  uncertainty algebra.

- Phase 3: public surface cleanup, hot-path optimization, property/fuzz/algebra
  verification.

- Phase 4: reflection API, schema catalog, incremental/binary/streaming
  transport, ecosystem bridges.

- Phase 5: governance and causal frontier contracts.

Docs outputs:

- `docs/reference/ir/index.md`
- `docs/reference/ir/public-surface.md`
- `docs/reference/ir/schema-catalog.md`
- `docs/reference/ir/compiler-pipeline.md`
- `docs/reference/ir/interoperability.md`
- `docs/reference/ir/governance.md`
- `docs/reference/ir/analytics.md`
- `docs/reference/ir/observation.md`
- `docs/reference/ir/problem-framing.md`
- `docs/reference/schemas.md`
- `docs/reference/public-surface.md`
- `docs/contracts/TRINITY.md`
- `docs/contracts/MERGE_SEMANTICS.md`
- `docs/contracts/E1_*.md`
- `docs/contracts/E2_*.md`
- `src/polisyos/ir/README.md`
- `src/polisyos/ir/trinity/README.md`
- `src/polisyos/ir/analytics/README.md`
- `src/polisyos/ir/observation/README.md`
- `src/polisyos/ir/governance/README.md`

Validation:

- Schema generation check.
- Public surface regeneration.
- Contract docs cross-link to tests/snapshots.

### D1-L5 Tools mapping

Map source plan phases:

- Phase 0: SQL/shell injection, shell safety, destructive operation guardrails.
- Phase 1: atomicity, rollback, resource/I/O validation, explicit degraded
  mode, legacy quarantine.

- Phase 2: unified CLI entry point, shared runtime, packaging/import
  normalization, dependency graph, docs metadata.

- Phase 3: critical tool test program, structured CI output, timing telemetry.
- Phase 4: cloud/scripts/benchmarks consolidation, deprecated cleanup.
- Phase 5: incremental execution, cache, autofix/rule registry, hot-path
  maintainability.

Docs outputs:

- `docs/reference/tools.md`
- `tools/README.md`
- `tools/validation/README.md`
- `tools/devx/workspace/README.md`
- `tools/devx/architecture/README.md`
- `docs/how-to/operate-ci-cd-platform.md`
- `docs/how-to/manage-generated-artifacts.md`
- `docs/how-to/release-policy.md`
- `docs/reference/quality-gates.md`
- `docs/reference/dependency-platform.md`
- `docs/reference/merge-governance.md`
- `docs/reference/ratchet-policy.md`

Validation:

- `uv run polisyos-tools docs --output docs/reference/tools.md`
- CI parity command includes docs checks.
- Deprecated tool wrappers have documented status.

### D1-L6 Scientist mapping

Map source plan phases:

- Phase 0: async/locking/lifecycle, budget/request/security/scientific hotfixes.
- Phase 1: error semantics, atomic state mutation, deterministic execution,
  observability, tests and benchmarks.

- Phase 2: hot-path memory, algorithmic complexity, API simplification,
  decomposition, type safety.

- Phase 3: causal validity, governance, fairness, calibration,
  accountability, search, optimization, agent reasoning.

- Phase 4: distributed safety and frontier research backlog.

Docs outputs:

- `docs/reference/scientist/index.md`
- `docs/reference/scientist/workflows.md`
- `docs/reference/scientist/governance-passes.md`
- `docs/reference/scientist/nodes.md`
- `docs/reference/scientist/causal.md`
- `docs/reference/scientist/calibration-governance.md`
- `docs/reference/scientist/reliability-scorecard.md`
- `docs/reference/scientist/frontier-runtime.md`
- `docs/reference/scientist/remediation-status.md`
- `docs/how-to/write-governance-pass.md`
- `docs/tutorials/creating-governance-pass.md`
- `src/polisyos/scientist/README.md`
- `src/polisyos/scientist/agent/README.md`
- `src/polisyos/scientist/search/README.md`
- `src/polisyos/scientist/governance/README.md`
- `src/polisyos/scientist/nodes/README.md`
- `src/polisyos/scientist/workflows/README.md`

Validation:

- Scientist phase gate tools/tests are linked.
- Governance and causal claims map to artifacts or tests.
- Benchmark requirements are documented before SOTA claims.

### D1 exit criteria

- Each source remediation plan has a docs impact table.
- Each lane has exact files, source of truth and validation command.
- Missing pages are recorded as backlog with priority.

## Phase D2 - Reference Reconstruction

**Goal:** rebuild factual reference docs from code and generated artifacts.

**Duration:** 2-4 days.

**Hard dependency:** D1 mappings.

**Parallelism:** all L1-L6 lanes run concurrently; L9 works on generators and
checks in parallel.

### D2 shared outputs

| Output                                  | Owner lane | Notes                                                |
| --------------------------------------- | ---------- | ---------------------------------------------------- |
| `docs/reference/index.md` refresh       | L0         | High-level map, no deep subsystem claims.            |
| `docs/reference/public-surface.md`      | L4/L9      | Generated or verified from public surface inventory. |
| `docs/reference/generated-artifacts.md` | L4/L5/L9   | Generated-artifact lifecycle and owners.             |
| `docs/reference/tools.md`               | L5/L9      | Generated from tool registry.                        |
| `docs/reference/schemas.md`             | L4/L9      | Generated/checked from schema diagnostics.           |
| `docs/reference/quality-gates.md`       | L5/L9      | Single source for all local/CI gates.                |

### D2 subsystem reference work

| Lane            | Reference work                                                                                                    | Can be merged independently when             |
| --------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| L1 Core/Runtime | Runtime API pages, error semantics, auth/tenant model, CAS/storage reference, config/env registry                 | OpenAPI/routes/tests match docs.             |
| L2 Fabric       | Connector protocol, source profiles, data-plane, schema compatibility, lineage, quality and time travel reference | Connector and data-plane tests cited.        |
| L3 Foundry      | Compile/execute, executor state, JAX/numeric policy, methods catalog, calibration/UQ, reproducibility             | Examples and benchmark commands are current. |
| L4 IR           | IR schema catalog, public surface, contracts, pass manager, transport, uncertainty, observation/problem framing   | Schema/public-surface checks pass.           |
| L5 Tools        | CLI reference, workspace commands, validation tools, deprecated wrappers, tool dependency graph                   | Tool reference regenerated.                  |
| L6 Scientist    | Workflow engine, nodes, governance passes, causal validity, search/agent, reliability scorecard                   | Phase gates/tests linked.                    |

### D2 acceptance

- Reference pages do not describe planned behavior as current behavior.
- Every generated reference page has a regeneration command.
- Every manually maintained reference page has owner and source-of-truth note.
- `mkdocs build --strict` passes or failures are explicitly tracked.

## Phase D3 - README And Local Navigation Refresh

**Goal:** make repository navigation usable without opening the docs site.

**Duration:** 2-3 days.

**Hard dependency:** D1 mappings; D2 can continue in parallel.

**Parallelism:** one README batch per lane.

### README template

Each major README should include:

1. Purpose.
2. Where to start.
3. Public entrypoints.
4. Depends on / depended on by.
5. Common commands.
6. Test/verification commands.
7. Reference docs.
8. Last updated date.

### README batches

| Batch         | Files                                                                                                                                               | Lane                    |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| Core platform | `src/polisyos/common/README.md`, `src/polisyos/core/README.md`, `src/polisyos/runtime/README.md`, `src/polisyos/runtime/http/README.md`             | L1                      |
| Fabric        | `src/polisyos/fabric/README.md`, `connectors`, `data_plane`, `retrieval`, `world`, `claims`, `docs` READMEs                                         | L2                      |
| Foundry       | `src/polisyos/foundry/README.md`, `methods`, `calibration`, `agent_sim`, `contracts`, `plugins` READMEs                                             | L3                      |
| IR            | `src/polisyos/ir/README.md`, `trinity`, `analytics`, `observation`, `governance`, `kernel`, `migrations` READMEs                                    | L4                      |
| Tools/Ops     | `tools/README.md`, `tools/validation/README.md`, `tools/devx/**/README.md`, `ops/README.md`                                                         | L5/L8                   |
| Scientist     | `src/polisyos/scientist/README.md`, `agent`, `search`, `governance`, `nodes`, `workflows`, `engine`, `compute` READMEs                              | L6                      |
| Frontend      | `frontend/README.md`, `frontend/runtime-dashboard/README.md`, `frontend/runtime-api-client/README.md`, `frontend/runtime-reference-shell/README.md` | L7                      |
| Tests         | `tests/README.md`, subsystem test READMEs                                                                                                           | L9 with subsystem lanes |

### D3 acceptance

- Every top-level subsystem README has freshness marker.
- README links resolve.
- README commands are smoke-tested or labeled as conceptual.

## Phase D4 - Tutorials, How-to Guides, And Migration Paths

**Goal:** update task-oriented docs so people can work quickly after the
refactor.

**Duration:** 3-5 days.

**Hard dependency:** D2 reference pages for the same subsystem should be at
least drafted.

**Parallelism:** split by persona and workflow.

### Persona lanes

| Persona              | Docs to refresh/add                                                                                           | Depends on                     |
| -------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| New contributor      | `tutorials/getting-started.md`, `how-to/install.md`, `reference/contributor-start-here.md`                    | workspace commands, env matrix |
| Backend engineer     | `how-to/onboarding/backend-engineer.md`, runtime route guide, public facade guide, schema-backed type guide   | L1/L4/L5                       |
| Frontend engineer    | `how-to/onboarding/frontend-engineer.md`, runtime dashboard guide, API client update guide                    | L1/L7                          |
| Platform/Ops         | `how-to/onboarding/platform-ops-engineer.md`, deploy runtime, CI/CD platform, release policy, rollback/replay | L1/L5/L8                       |
| Security/Compliance  | `how-to/onboarding/security-compliance-reviewer.md`, security compliance reference, evidence map              | L1/L8                          |
| Domain/Policy reader | `how-to/onboarding/domain-policy-reader.md`, first policy analysis, Lex/Scientist overview                    | L3/L4/L6                       |

### Workflow docs

| Workflow                  | Docs                                                                                               |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| First run                 | `tutorials/getting-started.md`, `how-to/install.md`                                                |
| First policy analysis     | `tutorials/first-policy-analysis.md`, Foundry/Scientist/IR references                              |
| Connector authoring       | `tutorials/writing-a-connector.md`, `how-to/add-data-source.md`, `docs/connectors/CONTRIBUTING.md` |
| Governance pass authoring | `tutorials/creating-governance-pass.md`, `how-to/write-governance-pass.md`                         |
| Runtime operation         | `how-to/deploy-runtime.md`, `how-to/use-control-plane.md`, runtime API docs                        |
| Debugging                 | `how-to/debug-failed-run.md`, runbooks, trace/logging docs                                         |
| Generated artifacts       | `how-to/manage-generated-artifacts.md`, generated artifacts reference                              |
| Schema work               | `how-to/manage-schemas.md`, schema catalog, IR docs                                                |
| Benchmarks                | `how-to/run-benchmarks.md`, Foundry/Scientist benchmark docs                                       |

### New high-value docs to add

- `docs/how-to/post-refactor-migration.md`
- `docs/how-to/add-runtime-route.md`
- `docs/how-to/add-public-facade.md`
- `docs/how-to/add-schema-backed-ir-type.md`
- `docs/how-to/update-runtime-dashboard-api-client.md`
- `docs/reference/frontend/index.md`
- `docs/reference/documentation-inventory.md`
- `docs/reference/compliance-evidence-map.md`

### D4 acceptance

- Each tutorial has "verified with" date and environment.
- Each how-to has input, output, commands, rollback/troubleshooting when
  relevant.

- First-policy-analysis aligns with current Trinity / IR / Foundry / Scientist
  flow.

## Phase D5 - Architecture, Runbooks, Compliance, And SOTA Claims

**Goal:** refresh higher-level explanations and operational docs to match the
new system.

**Duration:** 3-5 days.

**Hard dependency:** D1 source maps; can run in parallel with D2-D4 once a lane
has enough facts.

### Architecture explanation packages

| Package                     | Docs                                                                      | Inputs                   |
| --------------------------- | ------------------------------------------------------------------------- | ------------------------ |
| System context              | `docs/explanation/architecture.md`, `docs/index.md` diagram               | all plans                |
| Contract architecture       | `docs/explanation/trinity.md`, `docs/explanation/ir-design.md`, contracts | IR + Foundry + Scientist |
| Runtime platform            | `docs/explanation/security-model.md`, API reference, operations docs      | Core/Common/Runtime      |
| Data architecture           | `docs/explanation/data-fabric.md`, Fabric reference                       | Fabric                   |
| Scientific architecture     | `docs/explanation/causal-engine.md`, Scientist/Foundry references         | Foundry + Scientist      |
| Legal/NormPack architecture | `docs/explanation/lex-pipeline.md`, Lex references                        | Lex + Scientist          |
| Governance architecture     | `docs/explanation/governance-model.md`, governance pass refs              | Scientist + Core         |
| Observation contracts       | `docs/explanation/observation-contracts.md`, IR observation refs          | IR + Foundry             |
| Freeze/ratchet model        | `docs/explanation/freeze-policy.md`, ratchet/merge governance             | Tools + IR               |

### Diagrams to add or refresh

- System context.
- Container view.
- Runtime HTTP request flow.
- Auth/tenant isolation flow.
- CAS/artifact lifecycle.
- Generated artifact lifecycle.
- Fabric connector ingestion flow.
- Fabric lineage and schema compatibility flow.
- Foundry compile/execute flow.
- IR schema evolution flow.
- Scientist workflow execution flow.
- Scientist governance artifact flow.
- CI/docs quality gate flow.

### Runbook/compliance packages

| Package                       | Docs                                                                                           | Inputs              |
| ----------------------------- | ---------------------------------------------------------------------------------------------- | ------------------- |
| Runtime incidents             | runtime outage, stuck worker, idempotency, CAS/OPA runbooks                                    | Core/Common/Runtime |
| Artifact and schema incidents | artifact corruption, signing/SBOM, broken contract generation, retained artifact recovery      | Core + IR + Tools   |
| Fabric incidents              | cache rebuild storm, connector quarantine/DLQ, data-plane recovery                             | Fabric              |
| Release and CI                | dependency upgrade regression, docs publication failure, canary rollback, benchmark regression | Tools + Ops         |
| Security/compliance           | key rotation, security compliance ref, FedRAMP gap, evidence map                               | Core + Ops          |

### SOTA claim policy

Any page that uses words like `SOTA`, `frontier`, `production-grade`,
`secure`, `reliable`, `auditable`, `deterministic`, `calibrated`, `fair`, or
`reproducible` must link to at least one of:

- test suite;
- benchmark result;
- generated artifact;
- acceptance audit evidence;
- ADR/contract;
- runbook rehearsal evidence;
- explicit roadmap note saying it is not yet default/current behavior.

### D5 acceptance

- All explanation pages link back to ADRs, contracts or reference docs.
- Every runbook has owner, last-tested date, evidence path and rollback path.
- SOTA claims are evidence-backed or clearly marked as future work.

## Phase D6 - Automation, CI Gates, And Publication

**Goal:** make drift hard to reintroduce.

**Duration:** 2-4 days.

**Hard dependency:** D2 generated/reference commands known.

**Parallelism:** checks can be implemented independently by artifact type.

### Gate packages

| Gate                | Trigger                             | Command / mechanism                                             | Owner lane |
| ------------------- | ----------------------------------- | --------------------------------------------------------------- | ---------- |
| Strict docs build   | any docs change                     | `uv run --extra docs python -m mkdocs build --strict`           | L9         |
| Docs accuracy       | README/docs changes                 | `python3 tools/validation/check_docs_accuracy.py --repo-root .` | L9         |
| Semantic docstrings | public API/reference changes        | `check_docstring_quality.py`                                    | L9         |
| Public surface      | package facade changes              | architecture guardrail / public surface generator               | L4/L9      |
| Schema docs         | `schemas/**`, IR models             | schema diagnostics generator/check                              | L4/L9      |
| Tools reference     | `tools/**` registry/CLI changes     | `uv run polisyos-tools docs --output docs/reference/tools.md`   | L5/L9      |
| Runtime API         | `runtime/http/**` changes           | OpenAPI contract check                                          | L1/L9      |
| Frontend API client | runtime API or API client changes   | frontend API client tests/e2e docs check                        | L7         |
| README freshness    | subsystem public entrypoint changes | freshness checker or review checklist                           | L0/L9      |
| Runbook evidence    | ops/security behavior changes       | acceptance audit / manual rehearsal ledger                      | L8         |

### Required change-detection rules

- If `src/polisyos/runtime/http/**` changes, runtime API docs or OpenAPI diff
  evidence must change.

- If `src/polisyos/ir/**` or `schemas/**` changes, schema and IR reference
  checks must run.

- If `tools/**` command metadata changes, `docs/reference/tools.md` must be
  regenerated.

- If package `__init__.py` facades change, public-surface docs must be
  regenerated.

- If `src/polisyos/fabric/connectors/**` changes, connector docs or impact note
  must be present.

- If `src/polisyos/scientist/**` changes in workflows/governance/causal paths,
  Scientist reference or SOTA evidence docs must be checked.

- If `src/polisyos/foundry/**` changes in compile/execute/methods/calibration,
  Foundry reference or benchmark docs must be checked.

- If frontend API client or dashboard API usage changes, frontend docs must be
  checked.

- If security, auth, tenant, signing, audit or compliance code changes,
  security/compliance docs and runbooks must be checked.

### Publication package

- Ensure `mkdocs.yml` nav only exposes current product guidance.
- Exclude archived plans and reports from published navigation.
- Add docs publication failure rollback path to release checklist.
- Run docs site locally and record final evidence.

### D6 acceptance

- Local docs gate has one documented command.
- CI fails with actionable messages on docs drift.
- Published nav is current and does not present closed remediation plans as
  active guidance.

## Suggested Maximum-Parallel Execution Board

This board is designed so 6-10 people/agents can work simultaneously.

### Day 0-1: launch

| Slot | Worker | Task                                                      |
| ---- | ------ | --------------------------------------------------------- |
| A    | L0     | Create inventory, plan status ledger, ownership skeleton. |
| B    | L9     | Run baseline gates and collect failures.                  |
| C    | L1     | Map Core/Common/Runtime plan to docs outputs.             |
| D    | L2     | Map Fabric plan to docs outputs.                          |
| E    | L3     | Map Foundry plan to docs outputs.                         |
| F    | L4     | Map IR plan to docs outputs.                              |
| G    | L5     | Map Tools plan to docs outputs.                           |
| H    | L6     | Map Scientist plan to docs outputs.                       |

### Day 1-3: reference sprint

| Slot | Worker | Task                                                           |
| ---- | ------ | -------------------------------------------------------------- |
| A    | L4/L9  | Regenerate schema, IR and public-surface references.           |
| B    | L5/L9  | Regenerate tools reference and document tool gates.            |
| C    | L1     | Refresh runtime API and operations reference.                  |
| D    | L2     | Refresh Fabric connector/data-plane reference.                 |
| E    | L3     | Refresh Foundry compile/execute/methods/calibration reference. |
| F    | L6     | Refresh Scientist workflows/nodes/governance/causal reference. |
| G    | L7     | Draft frontend/API consumer docs.                              |
| H    | L0     | Adjust reference index and nav after reference pages land.     |

### Day 3-5: workflow sprint

| Slot | Worker | Task                                                           |
| ---- | ------ | -------------------------------------------------------------- |
| A    | L0     | Refresh docs homepage and contributor start path.              |
| B    | L1/L8  | Runtime deploy/control/debug how-to and runbooks.              |
| C    | L2     | Connector tutorial and data-source how-to.                     |
| D    | L3/L6  | First policy analysis and causal analysis flow.                |
| E    | L4     | Schema/IR type and public facade how-to.                       |
| F    | L5     | CI/CD, release, generated artifacts and tool operation guides. |
| G    | L7     | Frontend onboarding and API client update guide.               |
| H    | L8     | Security/compliance evidence map.                              |

### Day 5-7: architecture and gates sprint

| Slot | Worker | Task                                                               |
| ---- | ------ | ------------------------------------------------------------------ |
| A    | L0     | Final mkdocs nav cleanup.                                          |
| B    | L1/L8  | Security model, runtime flow diagrams, runtime runbook evidence.   |
| C    | L2     | Data fabric explanation and ingestion/lineage diagrams.            |
| D    | L3     | Foundry/JAX/reproducibility explanation and benchmark references.  |
| E    | L4     | IR/trinity/schema evolution explanations and contract cross-links. |
| F    | L5/L9  | CI gate wiring and docs quality gate docs.                         |
| G    | L6     | Scientist SOTA claim evidence and governance diagrams.             |
| H    | L9     | Full docs QA, strict build and final failure list.                 |

### Final integration

| Step | Owner     | Output                                              |
| ---- | --------- | --------------------------------------------------- |
| 1    | L0        | nav and index pages merged cleanly                  |
| 2    | L9        | generated docs are up to date                       |
| 3    | L8        | runbook/security/compliance evidence complete       |
| 4    | all lanes | owner review of subsystem pages                     |
| 5    | L0/L9     | final docs QA report and publication readiness note |

## Detailed Backlog

| ID      | Lane  | Task                                             | Output                                                             | Priority |
| ------- | ----- | ------------------------------------------------ | ------------------------------------------------------------------ | -------- |
| DOC-001 | L0    | Create documentation inventory and owner ledger. | `docs/reference/documentation-inventory.md`                        | P0       |
| DOC-002 | L0    | Classify root-level plans and remediation docs.  | plan status table + archive actions                                | P0       |
| DOC-003 | L9    | Record current docs QA baseline.                 | inventory evidence section                                         | P0       |
| DOC-004 | L1    | Refresh Core/Common/Runtime docs impact map.     | inventory lane section                                             | P0       |
| DOC-005 | L2    | Refresh Fabric docs impact map.                  | inventory lane section                                             | P0       |
| DOC-006 | L3    | Refresh Foundry docs impact map.                 | inventory lane section                                             | P0       |
| DOC-007 | L4    | Refresh IR docs impact map.                      | inventory lane section                                             | P0       |
| DOC-008 | L5    | Refresh Tools docs impact map.                   | inventory lane section                                             | P0       |
| DOC-009 | L6    | Refresh Scientist docs impact map.               | inventory lane section                                             | P0       |
| DOC-010 | L4/L9 | Regenerate public surface docs.                  | `docs/reference/public-surface.md`                                 | P1       |
| DOC-011 | L4/L9 | Regenerate schema and IR catalog docs.           | `docs/reference/schemas.md`, `docs/reference/ir/schema-catalog.md` | P1       |
| DOC-012 | L5/L9 | Regenerate tools reference.                      | `docs/reference/tools.md`                                          | P1       |
| DOC-013 | L1    | Refresh runtime API reference.                   | `docs/reference/api/**`                                            | P1       |
| DOC-014 | L2    | Refresh Fabric reference.                        | `docs/reference/fabric/**`                                         | P1       |
| DOC-015 | L3    | Refresh Foundry reference.                       | `docs/reference/foundry/**`                                        | P1       |
| DOC-016 | L6    | Refresh Scientist reference.                     | `docs/reference/scientist/**`                                      | P1       |
| DOC-017 | L1-L7 | Refresh major subsystem READMEs.                 | README batches                                                     | P1       |
| DOC-018 | L0    | Add post-refactor migration guide.               | `docs/how-to/post-refactor-migration.md`                           | P1       |
| DOC-019 | L7    | Add frontend reference path.                     | `docs/reference/frontend/index.md`                                 | P2       |
| DOC-020 | L8    | Add compliance evidence map.                     | `docs/reference/compliance-evidence-map.md`                        | P2       |
| DOC-021 | L8    | Rehearse runbooks and add last-tested evidence.  | `docs/runbooks/**`                                                 | P2       |
| DOC-022 | L0/L8 | Refresh architecture explanations and diagrams.  | `docs/explanation/**`                                              | P2       |
| DOC-023 | L9    | Add/verify docs drift gates in CI.               | CI + `quality-gates.md`                                            | P2       |
| DOC-024 | L9    | Add README freshness enforcement.                | checker or PR checklist                                            | P2       |
| DOC-025 | L0/L9 | Final publication readiness pass.                | final docs QA report                                               | P3       |

## Definition Of Done

Documentation reaches SOTA when all criteria below are true:

| Gate                     | Target                                                                                                                              |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| Strict docs build        | `mkdocs build --strict` passes.                                                                                                     |
| Docs accuracy            | No broken local links, stale workflow references, repo placeholders, invalid site URLs or local filesystem links in published docs. |
| Source-plan traceability | Each of the six remediation plans has an impact map and docs outputs.                                                               |
| Public API docs          | Public package facades and reference pages match current code.                                                                      |
| Semantic docstrings      | Reference-visible public symbols have semantic docstrings or justified allowlist entries.                                           |
| Schema docs              | Schema catalog and IR reference are generated or verified from current code.                                                        |
| Runtime API docs         | OpenAPI/routes/tests and runtime API reference agree.                                                                               |
| CLI docs                 | Tool reference is generated from current registry/commands.                                                                         |
| Package READMEs          | Major subsystem READMEs have owner, start path, public entrypoints, tests, docs link and last updated date.                         |
| Tutorials                | Golden-path tutorials are smoke-tested in the current workspace.                                                                    |
| Runbooks                 | Each runbook has owner, last-tested date, evidence location and rollback path.                                                      |
| SOTA claims              | Claims are backed by tests, benchmarks, artifacts, ADRs, contracts or explicit roadmap status.                                      |
| Plan hygiene             | Active plans are current; closed/superseded plans are archived or clearly marked.                                                   |
| Ownership                | Docs ownership is visible and reviewed.                                                                                             |
| CI enforcement           | Behavior-changing PRs cannot pass without required docs evidence or explicit exemption.                                             |

## Non-goals

- Do not rewrite ADR history. Supersede instead.
- Do not publish speculative roadmap content as current behavior.
- Do not hand-maintain generated reference pages when a generator exists.
- Do not document private helpers as supported API unless intentionally promoted.
- Do not block one subsystem lane on another unless shared navigation,
  terminology, generated artifacts or publication gates are affected.

## First Command Set

Run this from `policy-engine/` before starting the first implementation pass:

```bash
uv run --extra docs python -m mkdocs build --strict
python3 tools/validation/check_docs_accuracy.py --repo-root .
uv run --extra docs python tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt
uv run polisyos-tools docs --output docs/reference/tools.md
uv run --extra ml polisyos-tools diagnostics gen-schema --check
python3 -m tools.cli workspace ci-parity --skip-browser
```

Record results in `docs/reference/documentation-inventory.md`, then execute
lanes in parallel using the D0-D6 phase gates above.
