# Documentation Inventory

Freshness: 2026-04-17

Owner: `@docs-owners`
Source of truth: `docs/DOCUMENTATION_SOTA_PLAN.md`, `mkdocs.yml`, and the command outputs recorded in the QA ledger below

Program owner: `@platform-owners`

This page started as the Phase D0 baseline map for the documentation SOTA
refresh. It now doubles as the current docs control ledger: source plans,
documentation surfaces, fresh QA evidence, owners, and shared files that still
require coordination.

## D0 Exit Snapshot

| Exit criterion | Status | Evidence |
|---|---|---|
| Inventory page exists | active | This page is the D0 inventory skeleton. |
| Six source remediation plans are linked | active | See [Canonical Source Plans](#canonical-source-plans). |
| Every lane has owner and doc surfaces | active | See [Ownership](ownership.md#documentation-sota-lane-owners). |
| Current docs QA status is recorded | active | See [Current QA Ledger](#current-qa-ledger). |
| Shared coordination files are identified | active | See [Conflict Map](#conflict-map). |

## Canonical Source Plans

These six remediation plans are the canonical context for the docs refresh.
Parallel lanes should treat them as input evidence, then verify claims against
current code, generators, schemas, tests, and CI gates before rewriting docs.

| Lane | Source plan | Primary docs impact |
|---|---|---|
| L1 Core/Common/Runtime | `docs/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md` | `README.md`, runtime API reference, operations reference, security model, runtime runbooks, `src/polisyos/{common,core,runtime}/README.md` |
| L2 Fabric | `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md` | Fabric reference, connectors guide, data-plane docs, data source how-to, Fabric runbooks |
| L3 Foundry | `docs/FOUNDRY_REMEDIATION_PLAN.md` | Foundry reference, methods catalog, causal-engine explanation, benchmark and reproducibility docs |
| L4 IR | `docs/IR_AUDIT_REMEDIATION_PLAN.md` | IR reference, schema catalog, contracts, ADR index, interoperability docs |
| L5 Tools | `docs/TOOLS_AUDIT_REMEDIATION_PLAN.md` | Tools reference, CI/CD how-to, contributor command map, validation docs |
| L6 Scientist | `docs/SCIENTIST_AUDIT_REMEDIATION_PLAN.md` | Scientist reference, workflows/nodes/governance docs, reliability scorecard, Scientist how-to/tutorial surfaces |

## Documentation Surface Inventory

Status values here describe the current publication-readiness state after the
D0-D6 documentation SOTA closeout. `active` means the surface is current for
published docs or local navigation; generated pages remain governed by their
canonical regeneration command.

| Page or surface | Owner | Status | Source of truth | Validation method |
|---|---|---|---|---|
| `policy-engine/README.md` | `@docs-owners` | active gateway | product root, public-surface inventory, command registry | docs accuracy check, quickstart command smoke tests |
| `docs/reference/index.md` | `@docs-owners` | active shared nav | `mkdocs.yml`, this inventory | MkDocs strict build |
| `docs/reference/documentation-inventory.md` | `@docs-owners` | active D0 baseline | `docs/DOCUMENTATION_SOTA_PLAN.md` Phase D0 | linked from reference index and nav |
| `docs/reference/ownership.md` | `@platform-owners` | active D0 owner map | logical owner groups documented in `docs/reference/ownership.md` | every L0-L9 lane has primary and backup owner |
| `docs/reference/quality-gates.md` | `@platform-owners` | active D6 gate map | validation tools, CI workflows, merge governance | docs drift gate, docs accuracy, CI parity |
| `docs/reference/api/**` | `@runtime-owners` | active reference | Runtime OpenAPI export, runtime tests | OpenAPI contract check, API tests |
| `docs/reference/fabric/**` | `@fabric-owners` | active reference | Fabric plan, connector registry, data-plane tests | connector registry tests, schema compatibility gates |
| `docs/reference/foundry/**` | `@foundry-owners` | active reference | Foundry plan, methods catalog, benchmarks | Foundry tests, benchmark gates, reproducibility checks |
| `docs/reference/ir/**` | `@ir-owners` | active/generated reference | IR schemas, schema snapshots, IR tests | schema generation check, property/fuzz tests where available |
| `docs/reference/scientist/**` | `@scientist-owners` | active reference | Scientist plan, workflow/node registries, phase gates | Scientist phase gates, docs accuracy, MkDocs link checks |
| `docs/reference/tools.md` | `@tools-owners` | regenerated in D0 | `tools.registry` command metadata | `uv run polisyos-tools docs --output docs/reference/tools.md` |
| `docs/reference/schemas.md` | `@ir-owners` | active/generated reference | generated schema inventory | schema generation check |
| `docs/reference/operations/**` | `@platform-owners` | active operations reference | runbooks, SLO docs, operational checks | CI parity, runbook rehearsal evidence |
| `docs/runbooks/**` | `@platform-owners` | active rehearsed runbooks | incident procedures, release gates | last-tested evidence and rollback validation |
| `docs/how-to/**` | `@docs-owners` | active task guidance | current CLI, API, code paths | walkthrough smoke tests |
| `docs/tutorials/**` | `@docs-owners` | active tutorial path | product quickstart and example fixtures | tutorial smoke tests |
| `docs/explanation/**` | `@docs-owners` | active explanations | ADRs, architecture boundaries, source plans | docs accuracy and owner review |
| `docs/contracts/**` | `@platform-owners` | active contract reference | contracts, schemas, ABI snapshots | schema/ABI contract gates |
| `docs/adr/**` | `@platform-owners` | active decision history | accepted ADRs and supersession notes | MkDocs strict, ADR owner review |

## Root-Level Plan Status Ledger

All root-level `docs/*_PLAN.md` files have an explicit D0 status. `active`
means the plan is still valid planning context; it does not mean all phases are
complete. Root-level plans are planning-only surfaces and stay out of the
published site via `mkdocs.yml`; this ledger is the source of truth for their
status. Archived plans under `docs/archive/plans/` are outside this root-level
ledger and retain archive status by path.

| Plan | Status | Owner lane | D0 classification note |
|---|---|---|---|
| `docs/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md` | active | L1 | Canonical source remediation plan for Core/Common/Runtime docs refresh. |
| `docs/DATA_FORGE_CONSOLIDATION_PLAN.md` | active | L2/L5 | Adjacent data-pipeline consolidation plan; use as context for Fabric/Tools docs only after owner review. |
| `docs/DOCUMENTATION_SOTA_PLAN.md` | active | L0 | Program plan for this docs refresh; excluded from published docs site by `mkdocs.yml`. |
| `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md` | active | L2 | Canonical source remediation plan for Fabric docs refresh. |
| `docs/FOUNDRY_REMEDIATION_PLAN.md` | active | L3 | Canonical source remediation plan for Foundry docs refresh; file marks active implementation and release-gate hardening. |
| `docs/FRONTEND_SOTA_PLAN.md` | active | L7 | Frontend/API-consumer plan; planning-only surface excluded from the published site by `mkdocs.yml`. |
| `docs/INFRASTRUCTURE_SOTA_PLAN.md` | active | L8/L9 | Infrastructure/platform plan; useful for ownership, gates, and release governance surfaces. |
| `docs/IR_AUDIT_REMEDIATION_PLAN.md` | active | L4 | Canonical source remediation plan for IR docs refresh. |
| `docs/SCIENTIST_AUDIT_REMEDIATION_PLAN.md` | active | L6 | Canonical source remediation plan for Scientist docs refresh. |
| `docs/TOOLS_AUDIT_REMEDIATION_PLAN.md` | active | L5 | Canonical source remediation plan for Tools docs refresh. |
| `docs/UKRAINE_FUNDING_INTELLIGENCE_PLAN.md` | active | L2/L6 | Domain/data plan; use as context for Ukraine funding surfaces and data-source docs. |

## Current QA Ledger

Commands were run from `policy-engine/` on 2026-04-17 after the D6 docs-gate,
import-policy, connector-contract, and semantic-docstring closeout. This ledger
records current status, not the older D0 baseline failures.

| Command | Status | Recorded output |
|---|---|---|
| `uv run polisyos-tools architecture guardrails sync` | pass | Architecture guardrail inventories updated; generated reference inventories are in sync with the current repo state. |
| `uv run polisyos-tools docs --output docs/reference/tools.md` | pass | Wrote `docs/reference/tools.md`. |
| `uv run polisyos-tools validation check-docs-gate --repo-root .` | pass | Full D6 docs gate passed on the current dirty worktree (`540` changed files): generated tools reference stayed current, public-surface/README guardrails passed, ABI schema snapshots passed (`84` models), Runtime API OpenAPI plus generated client drift passed, docs accuracy reported `0` violations across `275` published docs files, strict MkDocs built successfully, and scoped semantic public-surface docstrings reported `97.9%` coverage with `0` placeholder violations. |
| `PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py` | pass | Generated ABI schema snapshots for 84 models (`0` file updates, `scan_mode=full`). |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .` | pass | Docs accuracy report: `0` violations across `275` published docs files. Workflow inventory now resolves both repository-root and product-root workflow files, including `abi.yml`, `ci.yml`, `docs-pages.yml`, `core-runtime-release-gate.yml`, `arch.yml`, `docs.yml`, `foundry-release-gate.yml`, `perf.yml`, `replay.yml`, and `signatures.yml`. The checker also blocks planning/remediation pages from the published MkDocs nav. |
| `uv run polisyos-tools architecture guardrails check` | pass | Architecture guardrail check passed. |
| `PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py --check` | pass | ABI schema snapshot check passed (84 models, `scan_mode=full`). |
| `uv run --extra docs python -m mkdocs build --strict` | pass | Documentation built successfully after plan-only docs were excluded from the published site and the D6 docs gate wiring was added. No project-content strict warnings or errors remained. The only extra terminal banner comes from the installed Material for MkDocs package and is suppressible with `NO_MKDOCS_2_WARNING=true`. |
| `uv run polisyos-tools validation check-docstring-quality --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt --coverage-scope public-surface --minimum-coverage 85` | pass | Inspected `6758` public symbols. Semantic coverage: `4774/6758` all subjects (`70.6%`), `3787/3823` public surface (`99.1%`), with `0` placeholder violations. Remaining second-pass packages are tracked as semantic-depth debt, not gate failures. |
| `uv run python tools/lint/lint_imports.py --policy import_policy.toml --exceptions import_exceptions.toml --output-format json` | pass | Import policy passed after adding `ukraine_data` to the known internal roots and recording newly surfaced boundary crossings as expiring import exceptions. Current result: `0` violations, `53` allowed exceptions, `1` non-enforced package-level cycle warning. |
| `uv run python tools/diagnostics/check_state_reads.py` | pass | `state_reads contract check passed` after Scientist built-in nodes declared the broad `artifacts_index`/`reports_index` and exact `run_id` reads their `execute` paths already performed. |
| `python3 tools/connectors/check_contracts.py --check` | pass | Connector contract snapshot passed after regenerating `schemas/snapshots/connectors/contracts.json`; the snapshot now includes the connector approval metadata shape emitted by the current registry contracts. |
| `uv run pytest tests/performance/test_benchmark_runtime_pipeline.py` | pass | `3 passed`; the legacy `benchmarks.run_parallel` import path now exposes the canonical parallel benchmark scheduler for the runtime-pipeline tests. |
| `python3 -m tools.cli workspace ci-parity --skip-browser` | blocked outside docs closeout | The run now passes doctor, import policy, Foundry ban list, `state_reads`, Scholar imports, connector contracts, ABI schema freshness, Runtime API contract, and frontend contract fixtures before reaching the broad backend pytest gate. Backend pytest then fails with `186 failed, 8895 passed, 54 skipped, 110 deselected` in `38:09`; dominant clusters are missing local data/catalog fixtures, legacy academic/dataset script exports, and pre-existing Foundry/IR/Scientist backend contract failures. This is no longer the D6 documentation-gate/import/docstring blocker; it is recorded as separate backend test debt. |

## Conflict Map

These files are shared coordination surfaces. Parallel lanes should update them
through L0/L9 review, or add a finding here and leave content changes to the
owning lane.

| Shared file or surface | Coordination owner | Why it conflicts | D0 rule |
|---|---|---|---|
| `mkdocs.yml` | L0/L9 | Global nav, exclusions, plugin behavior, and strict-mode failures affect every lane. | One lane edits nav at a time; keep generated pages in nav or explicitly excluded. |
| `docs/index.md` | L0 | Published home page frames product state and current entry points. | Update only after source-plan mapping confirms current claims. |
| `docs/reference/index.md` | L0 | Reference landing page links all subsystem docs. | Add only canonical D0/D1 coordination links until lane pages are refreshed. |
| `docs/reference/documentation-inventory.md` | L0 | Shared ledger for plan status, QA blockers, and conflicts. | Add findings here before rewriting another lane's technical content. |
| `docs/reference/ownership.md` | L0/L8 | Owner routing drives reviews and escalation. | Every new lane or shared surface needs primary and backup owner. |
| `docs/reference/quality-gates.md` | L9/L8 | Gate language must match CI and local validation commands. | Update together with command evidence or CI workflow changes. |
| `docs/reference/tools.md` | L5/L9 | Generated from command registry; manual edits drift quickly. | Regenerate through `polisyos-tools docs`. |
| `docs/reference/schemas.md`, `docs/reference/ir/schema-catalog.md` | L4/L9 | Generated/reference schema surfaces are currently out of date. | Regenerate or record drift; do not hand-edit generated schema truth. |
| `schemas/**`, `docs/reference/api/**`, frontend runtime client docs | L1/L7/L9 | OpenAPI and generated client drift impacts runtime consumers. | Treat contract generation and docs update as one coordinated change. |
| root-level `docs/*_PLAN.md` | L0 | Published-looking plans can conflict with current source-of-truth docs. | Keep status in this ledger; archive/supersede through L0 when closed. |
| `.github/workflows/**` and workflow references | L8/L9 | Docs accuracy checks validate workflow names. | Update workflow docs and checks together. |
| `README.md` and subsystem `README.md` files | owning lane + L0 | Entry points are read before reference docs and can contradict lane pages. | Refresh after D1 source-of-truth mapping, not during D0. |

## D1 Status Snapshot

Audit date: 2026-04-17

This snapshot checks the concrete D1 exit criteria from
`docs/DOCUMENTATION_SOTA_PLAN.md` against the current repository state.

### Required Output Coverage

All required D1 output files currently exist.

| Lane | Required outputs present | Evidence anchor | Status |
|---|---|---|---|
| L1 Core/Common/Runtime | 19/19 | `docs/reference/api/**`, `docs/reference/operations/**`, security/runbooks, `src/polisyos/{common,core,runtime}/README.md` | complete on file coverage |
| L2 Fabric | 15/15 | `docs/reference/fabric/**`, Fabric how-to/runbooks, `src/polisyos/fabric/**/README.md` | complete on file coverage |
| L3 Foundry | 16/16 | `docs/reference/foundry/**`, benchmark/how-to pages, `src/polisyos/foundry/**/README.md` | complete on file coverage |
| L4 IR | 18/18 plus `docs/contracts/E1_*.md` and `docs/contracts/E2_*.md` families | `docs/reference/ir/**`, shared reference pages, IR package READMEs, contract set | complete on file coverage |
| L5 Tools | 12/12 | `docs/reference/tools.md`, tooling READMEs, CI/release/how-to pages | complete on file coverage |
| L6 Scientist | 17/17 | `docs/reference/scientist/**`, Scientist how-to/tutorial pages, `src/polisyos/scientist/**/README.md` | complete on file coverage |

Total required file coverage: `97/97`.

### Lane Closure Readiness

| Lane | Source-of-truth map | Validation command/test linkage | Missing-page backlog discipline | Verdict |
|---|---|---|---|---|
| L1 Core/Common/Runtime | present | present | present | `docs/reference/api/index.md` now provides the lane-level D1-L1 source map, exact outputs, validation anchors, and explicit no-gap backlog status. |
| L2 Fabric | present | present | present | `docs/reference/fabric/index.md` now carries exact-file impact coverage plus explicit D1/no-gap backlog tracking. |
| L3 Foundry | present | present | present | `docs/reference/foundry/index.md` now combines phase mapping, exact outputs, validation commands, and explicit backlog status. |
| L4 IR | present | present | present | `docs/reference/ir/index.md` now lists exact D1 outputs, source-of-truth surfaces, validation anchors, and backlog status. |
| L5 Tools | present | present | present | The generated tools reference and tooling READMEs now cover exact D1 outputs, validation contract, and explicit backlog/no-gap status. |
| L6 Scientist | present | present | present | `docs/reference/scientist/index.md` already carried the strongest D1 closure structure and now includes the exact file set too. |

### Exit-Criteria Check

| D1 exit criterion | Status | Evidence |
|---|---|---|
| Each source remediation plan has a docs impact table | complete | All six canonical remediation plans now carry a `## D1 Docs Impact Table` section with exact-file coverage, source-of-truth surfaces, validation commands, and backlog/no-gap status. |
| Each lane has exact files, source of truth and validation command | complete | L1-L6 lane reference pages list the exact D1 outputs, source-of-truth surfaces, and validation anchors. |
| Missing pages are recorded as backlog with priority | complete | Required D1 pages are all present. Lane pages and remediation plans now record explicit `none` status for required gaps and keep optional D2 follow-ups prioritized. |

### Current Audit Notes

- `python3 tools/validation/check_docs_accuracy.py --repo-root .` was rerun on
  2026-04-17 during this audit after fixing Scientist workflow path references.
- D1 formal closure is now recorded directly in lane reference pages and in the
  six canonical remediation plans.

## D5 Status Snapshot

Audit date: 2026-04-17

This snapshot checks the D5 acceptance criteria from
`docs/DOCUMENTATION_SOTA_PLAN.md` against the current published documentation
surface.

### Architecture Explanation Coverage

| Package | Required docs | Status | Evidence |
|---|---|---|---|
| System context | `docs/explanation/architecture.md`, `docs/index.md` diagram | complete | Both pages link operations diagrams, ADRs, contracts, generated artifacts, and platform acceptance evidence. |
| Contract architecture | `docs/explanation/trinity.md`, `docs/explanation/ir-design.md`, contracts | complete | Trinity and IR pages link TRINITY, merge semantics, E1/E2 contracts, IR references, and ADR-0104 through ADR-0109. |
| Runtime platform | `docs/explanation/security-model.md`, API reference, operations docs | complete | Security model links auth/tenant, error semantics, security compliance, runtime runbooks, and ADR-0097 through ADR-0102. |
| Data architecture | `docs/explanation/data-fabric.md`, Fabric reference | complete | Data Fabric links Fabric references, contracts, schema/lineage evidence, and Fabric runbooks. |
| Scientific architecture | `docs/explanation/causal-engine.md`, Scientist/Foundry references | complete | Causal engine links Foundry, Scientist, contracts, ADRs, benchmark triage, and non-default frontier acceptance pages. |
| Legal/NormPack architecture | `docs/explanation/lex-pipeline.md`, Lex references | complete | Lex pipeline links Lex references, E2.8/E2.9/E2.10 contracts, ADRs, and Lex test evidence. |
| Governance architecture | `docs/explanation/governance-model.md`, governance pass refs | complete | Governance model links Scientist governance references, ADRs, workflow/governance tests, and non-default rollout pages. |
| Observation contracts | `docs/explanation/observation-contracts.md`, IR observation refs | complete | Observation contracts link IR observation, Fabric quality, Scientist causal validity, ADRs, and observation tests. |
| Freeze/ratchet model | `docs/explanation/freeze-policy.md`, ratchet/merge governance | complete | Freeze policy links quality gates, ratchet policy, ADRs, import policy, and docs/architecture gate commands. |

### Diagram Coverage

| Required diagram | Current location | Status |
|---|---|---|
| System context | `docs/index.md#system-context` | complete |
| Container view | `docs/explanation/architecture.md#container-view`; `docs/reference/operations/platform-architecture-diagrams.md#c4-container-view` | complete |
| Runtime HTTP request flow | `docs/reference/operations/platform-architecture-diagrams.md#runtime-http-request-flow`; `docs/explanation/security-model.md#auth-and-request-flow` | complete |
| Auth/tenant isolation flow | `docs/reference/operations/platform-architecture-diagrams.md#auth-and-tenant-isolation-flow`; `docs/explanation/security-model.md#auth-and-tenant-isolation` | complete |
| CAS/artifact lifecycle | `docs/reference/operations/platform-architecture-diagrams.md#cas-signing-and-integrity-flow` | complete |
| Generated artifact lifecycle | `docs/explanation/architecture.md#generated-artifact-lifecycle` | complete |
| Fabric connector ingestion flow | `docs/explanation/data-fabric.md#connector-ingestion-flow` | complete |
| Fabric lineage and schema compatibility flow | `docs/explanation/data-fabric.md#lineage-and-schema-compatibility-flow` | complete |
| Foundry compile/execute flow | `docs/explanation/causal-engine.md#foundry-compile-and-execute-flow` | complete |
| IR schema evolution flow | `docs/explanation/ir-design.md#schema-evolution-flow` | complete |
| Scientist workflow execution flow | `docs/explanation/governance-model.md#scientist-workflow-execution-flow` | complete |
| Scientist governance artifact flow | `docs/explanation/governance-model.md#governance-artifact-flow` | complete |
| CI/docs quality gate flow | `docs/explanation/freeze-policy.md#ci-and-docs-quality-gate-flow` | complete |

### Runbook And Compliance Coverage

| Package | Required scope | Status | Evidence |
|---|---|---|---|
| Runtime incidents | runtime outage, stuck worker, idempotency, CAS/OPA runbooks | complete | `docs/runbooks/runtime-api-outage.md`, `runtime-graceful-shutdown-and-stuck-worker.md`, `idempotency-incident.md`, `cas-opa-outage.md`. |
| Artifact and schema incidents | artifact corruption, signing/SBOM, broken contract generation, retained artifact recovery | complete | `artifact-corruption-recovery.md`, `artifact-signing-sbom-failure.md`, `broken-contract-generation.md`, `retained-artifact-recovery.md`. |
| Fabric incidents | cache rebuild storm, connector quarantine/DLQ, data-plane recovery | complete | `cache-rebuild-storm.md` plus `fabric-quarantine-dlq-and-data-plane-recovery.md`. |
| Release and CI | dependency upgrade regression, docs publication failure, canary rollback, benchmark regression | complete | `dependency-upgrade-regression.md`, `docs-publication-failure.md`, `canary-rollback-or-promotion-failure.md`, `benchmark-regression-triage.md`. |
| Security/compliance | key rotation, security compliance ref, FedRAMP gap, evidence map | complete | `key-rotation.md`, `docs/reference/security-compliance.md`, `docs/fedramp/gap-analysis.md`, `docs/reference/compliance-evidence-map.md`. |

### D5 Acceptance Check

| Acceptance criterion | Status | Notes |
|---|---|---|
| All explanation pages link back to ADRs, contracts, or reference docs | complete | Every file under `docs/explanation/*.md` has an ADR, contract, reference, or evidence backlink. |
| Every runbook has owner, last-tested date, evidence path, and rollback path | complete | All published runbook pages, including the runbook index, declare the required metadata. |
| SOTA claims are evidence-backed or clearly marked as future work | complete | Published explanation and runbook surfaces use evidence lines, ADR/contract links, generated-reference commands, or explicit non-default/future-state notes. ADRs are treated as evidence records; generated references are governed by their canonical regeneration commands. |

## D6 Status Snapshot

Audit date: 2026-04-17

| D6 criterion | Status | Evidence |
|---|---|---|
| Local docs gate has one documented command | complete | `uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main` is documented in [Quality Gates](quality-gates.md). |
| CI fails on docs drift with actionable messages | complete | Repository-root `.github/workflows/abi.yml` runs `check-docs-gate` in the `Fast PR / Docs quality` job for pull requests and pushes. |
| Published nav excludes closed/planning docs | complete | `mkdocs.yml` excludes active planning/remediation docs and `check-docs-accuracy` blocks planning docs in published nav. |
| Generated references are current | complete | Tools, public-surface/generated-artifacts, schema, Runtime API, and frontend contract checks are part of `check-docs-gate`. |
| Semantic public-surface docstrings pass | complete | Global public-surface docstring check passes with `0` placeholder violations. |
| Import-policy baseline is known | complete | `ukraine_data` is now in `import_policy.toml`; newly exposed crossings are recorded in `import_exceptions.toml` and `import_exceptions_registry.md` with 2026-07-01 expiry. |
| Broader local CI parity status is explicit | blocked outside docs closeout | `ci-parity --skip-browser` reaches backend pytest after all docs/contract/import/state-read layers pass, then fails on the existing broad backend test suite (`186 failed`, `8895 passed`). |

## Publication Readiness Notes

- D1-D6 documentation closeout is complete on the published docs surface and
  the dedicated docs/contract/import/state-read gates listed above pass.
- Any new stale claims or cross-lane conflicts should be added to this page
  before rewriting another lane's technical content without owner review.
- Import exceptions added during this closeout expire on 2026-07-01 and should
  be retired through facade extraction or boundary cleanup, not renewed by
  default.
- The broad `ci-parity --skip-browser` backend pytest failures remain outside
  the documentation closeout and need a separate backend stabilization pass
  before the full local CI parity command can be marked green.
