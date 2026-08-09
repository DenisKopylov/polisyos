---
plan_id: atlas-ds5-enforcement-waist
title: "DS5 - Enforcement Waist: Lints, Audience Mapping, Cache Discipline, Flags"
type: slice-plan
status: execution_authorized - C01 architecture re-cut approved
created: 2026-08-01
revised: 2026-08-02
last_verified: 2026-08-02
stability: measured_execution_plan
slice: DS5
baseline_commit: 5e648230204d5972d7d159aaffd50cb427ba3e81
execution_base_commit: 5e648230204d5972d7d159aaffd50cb427ba3e81
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
ds1_plan: ./DS1-live-application-audit.md
ds1_report: ../../../reference/frontend/atlas-live-application-audit.md
ds4_plan: ./DS4-status-grammar-rebinding.md
ds4_journal: ./DS4-status-grammar-rebinding-journal.md
ds4_closure: ./DS4-status-grammar-rebinding-closure.md
ds20_closure: ./DS20-server-authz-enforcement-closure.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
status_inventory: ../../../../architecture/atlas_surfaces/status-retirement-inventory.json
waist_debt_register: ../../../../architecture/atlas_surfaces/ds4-waist-debt-register.json
baseline_debt_manifest: ../../../../architecture/atlas_surfaces/frontend-baseline-debt-manifest.json
readiness_ledger: ../../../../architecture/atlas_surfaces/live-application-readiness-ledger.json
journal: ./DS5-enforcement-waist-journal.md
closure: ./DS5-enforcement-waist-closure.md
audiences: [PUBLIC, REVIEWER, EXPERT, MACHINE]
owner: team-frontend
architecture_owner: team-architecture
depends_on:
  - ./DS1-live-application-audit.md
  - ./DS4-status-grammar-rebinding.md
  - ./DS20-server-authz-enforcement-closure.md
  - ../../../reference/policy-design-case-failure-patterns.md
---

# DS5 - Enforcement Waist: Lints, Audience Mapping, Cache Discipline, Flags

**Goal:** Turn Atlas laws 8, 9, 10, 12 and the audience half of law 11 into
mechanical, fail-closed enforcement. DS5 makes DS4's zero-violation state
durable; it does not create a second authority source in the browser.

**Architecture:** Illegal authority states are made unrepresentable at the
waist. Generated owner DTOs enter module-private issuers; branded values occupy
authority-bearing props; `tsc` enforces assignability; a bounded AST lint bans
the enumerated escape hatches on authority paths; issuer tests prove runtime
novelty becomes explicit `unrecognized`. Other checks enforce only decidable
local properties: module-graph edges, direct transport calls/imports, governed
construction sites, strict registries and runtime denial. The cache path is
`owner as_of + query observation + tenant/user/expiry -> explicit posture`.
No timestamp heuristic, cached presence, client aggregate, flag, fixture
identity, or checker manufactures authority.

**Tech stack:** Python 3.14, Pydantic 2, FastAPI/OpenAPI, generated TypeScript,
React 19, TanStack Query, TypeScript 5 compiler API, pnpm 10.33.2, Vite,
Vitest, Playwright, ESLint, dependency-cruiser, JSON Schema, and repository
architecture guardrails.

## Binding fence and no-merge posture

- Worktree: `.worktrees/atlas-ds5`; branch:
  `codex/atlas-ds5-enforcement-waist`; exact current-`main` base and execution
  base: `5e648230204d5972d7d159aaffd50cb427ba3e81`.
- Writable: `apps/runtime-dashboard/**`, `packages/atlas-ui/**`, generated output
  only in `packages/runtime-api-client/**`, `architecture/atlas_surfaces/**`,
  DS5 plan/journal/closure files, `docs/reference/frontend/**`, and the narrow
  runtime HTTP/schema owner surface under `src/polisyos/runtime/http/**`.
- Read-only: `design/atlas-v15/**`, the frozen
  `apps/runtime-dashboard/src/shared/i18n/locales/ru.json`, CI configuration,
  and every backend path outside `src/polisyos/runtime/http/**`. In particular,
  DS5 never edits `foundry`, `fabric`, `scientist`, or `data_forge`.
- Fence authorization `29ab2fc56` admits
  `schemas/runtime_api_v1.openapi.json` exclusively through the registered
  exporter in `architecture/generated_artifacts.toml`, and exactly these five
  existing mirrored test files:
  `test_authorization_audience_denials.py`,
  `test_runtime_permission_vocabulary.py`,
  `test_governed_projection_api.py`,
  `test_governed_projection_service.py`, and
  `test_runtime_api_contract_hardening.py`. C06/C07 may change the snapshot
  only through that exporter and may edit those tests only
  for the DS5 HTTP/schema contract, in the same commits as HTTP models,
  generated clients and governed re-anchors. Any hand-authored or other
  `schemas/**` diff or any other backend-test path remains a STOP.
- No merge, push, rebase onto `main`, CI edit, baseline suppression, skip,
  quarantine, timeout increase, or tolerance widening. Closure is an
  architect-review handoff.
- One scoped commit per cluster after red-first evidence and independent review.
  No partial family, unpaired register transition, or uncommitted tail crosses
  a cluster boundary.

### Authority-order conflicts resolved openly

1. The execution base predates the master correction. The authoritative master
   at the ruling records DS5 as the critical-path Phase-B lane while DS6 is
   independently unblocked. DS6 may run in parallel, but none of its parity,
   frozen-set or contrast work is available to DS5.
2. The historical DS4 plan still describes a partial re-cut, but the earlier
   governing master closure note and the DS4 closure report record DS4 closed
   and merged. DS5 consumes the realized 27 package / 41 rebind / 18 use-as-is /
   3 retire split, not the superseded pre-ruling split.
3. The execution base also predates the synchronized D4 line in the master.
   The authoritative ruling and ratification at `7b6933770` control: `uk`
   primary, `en` baseline and fallback, `ru` `legacy_continuity_frozen`—not
   active, not deleted.
4. Six narrow cache rows in the older disposition seed name DS14, DS8, or DS9
   as owner, while the higher master and this mission assign tenant/user/expiry
   cache discipline to DS5. DS5 owns only that cross-cutting storage-discipline
   sublayer and its live migrations; the domain capabilities and their root
   rows remain with the named slices. C14a-C17b-R1 attach isolation evidence without
   falsely claiming those domain features rebound. The stale review-attention
   row receives DS4 deletion evidence and a fresh census, not a resurrected
   implementation.
5. The prompt inherited wording says “one of 9 typed labels”; the governing
   register defines ten usable capability labels. This plan uses the labels by
   name and makes no numerical claim.
6. Law 11 is the broader human-accountability law. DS5 mechanizes only its
   audience/permission enforcement half; it does not claim the whole law closed.
7. C01's original open-estate TypeScript analysis was stopped after three
   independent NO-GO reviews exposed three distinct bypass classes. Architect
   ruling `636645bec` withdraws that mechanism as an optimistic completeness
   envelope. C01 is continuously re-cut as C01a/C01b/C01c. The committed
   `b67084dd6` remains as honest history; a forward C01a commit removes its
   rejected analyzer and retains its sound core. It is not a base for another analyzer.

## DS5-C00: measured entry contract and stop gate

The measured plan landed at clean C00 commit `d6b38294e`. The snapshot/test
fence conflict was then resolved by `29ab2fc56`; implementation is authorized.
The C01 mechanism stop is resolved by `636645bec` and the measured C01a/C01b/
C01c re-cut below. The original base remains recorded; there is no rebase.

The installed-workspace precondition is satisfied: `corepack pnpm install
--frozen-lockfile` completed with pnpm 10.33.2 and the dashboard's
`node_modules/@polisyos/{atlas-ui,runtime-api-client}` entries resolve to the
workspace packages. Status-scanner reds observed without those links are not
evidence and must be discarded.

Three conditions still stop the slice at a clean, committed boundary:

- a canonical vocabulary symbol or governed field changes while C06 expects
  only accounted per-symbol/per-field generated line drift;
- a new owner gap requires code outside `runtime/http` or attempts to close an
  opaque terminal/evidence extension;
- a boundary remeasurement exceeds the recorded cap. The response is a
  continuously numbered re-cut, never a larger cluster or weaker gate.

### Measured baseline receipt

All source denominators below were measured at
`5e648230204d5972d7d159aaffd50cb427ba3e81` after the frozen install and before
the first repository edit.

| Gate | Command | Receipt |
| --- | --- | --- |
| clean base | `git status --short`; `git rev-parse HEAD`; `git branch --show-current` | PASS; clean; exact SHA above; expected branch |
| install/link proof | `corepack pnpm install --frozen-lockfile`; `readlink apps/runtime-dashboard/node_modules/@polisyos/{atlas-ui,runtime-api-client}` | PASS; two workspace links resolve |
| dashboard typecheck | `cd apps/runtime-dashboard && corepack pnpm run typecheck` | PASS |
| dashboard production build | `cd apps/runtime-dashboard && corepack pnpm run build` | PASS; 3,885 modules; PWA precache 108 entries |
| dashboard lint | `cd apps/runtime-dashboard && corepack pnpm run lint` | PASS; parseable exit 0; no diagnostics |
| dashboard architecture | `cd apps/runtime-dashboard && corepack pnpm run check:architecture` | PASS; custom engine 0; dependency-cruiser 0 across 1,019 modules / 4,150 dependencies |
| dashboard components | `cd apps/runtime-dashboard && corepack pnpm run test:components -- --reporter=default --maxWorkers=1` | BASELINE RED; 311/312 files and 890/893 tests pass in 362.99 s; only the three DS6-owned `panels.agentPipeline.overBudget` en/uk/ru parity identities fail |
| prior timeout isolation | `cd apps/runtime-dashboard && corepack pnpm exec vitest run src/shared/ui/compounds/decisionGradePresentation.test.ts src/features/evidence/components/DataIntelligencePanel.test.tsx src/features/runs/components/readinessScientificContainment.test.ts --maxWorkers=1 --reporter=default` | PASS; 3/3 files, 12/12 tests in 19.76 s; the earlier resource-contention timeouts are not baseline identities |
| Atlas UI | `cd packages/atlas-ui && corepack pnpm run typecheck && corepack pnpm run lint && corepack pnpm run check:architecture && corepack pnpm run test` | PASS; architecture 36 source files; 18/18 files and 86/86 tests |
| disposition checker | `python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes` | PASS; 261 roots, 13 supplemental findings, 23 seeded negatives, 8 censuses; corruption probes PASS |
| status checker | `python3 architecture/atlas_surfaces/check_status_retirement_inventory.py --check --corruption-probes` | PASS; 47 DS1 rows, 15 current authored statuses, 55 exemptions, 0 retirement debt, 3 waist debts; corruption probes PASS |
| governance unittest battery | `python3 -m unittest architecture.atlas_surfaces.test_frontend_baseline_debt_manifest architecture.atlas_surfaces.test_frontend_disposition_register architecture.atlas_surfaces.test_status_retirement_inventory` | PASS; 98/98 in 490.049 s |
| focused auth/audience HTTP | `uv run --extra runtime --extra ml pytest tests/unit/runtime/http/test_authorization_audience_denials.py tests/unit/runtime/http/test_runtime_permission_vocabulary.py tests/unit/runtime/http/test_auth_api.py -q` | PASS; 13/13 |

Two intentionally inherited closure reds are not C00 blockers: the three DS6
locale-parity failures and the DS8 `run detail A4 print` visual identity. The
frozen parity test, frozen `ru` catalog, and print expectation remain
byte-unmodified. Any new identity is red.

### Measured estate and cluster-sizing census

| Surface | Exact current denominator | Consequence |
| --- | ---: | --- |
| dashboard source | 942 TS/TSX/JS/JSX files; 574 production files in the C01a TypeScript program | broad gates derive source; C01a's bounded census uses production declarations only |
| Atlas UI source | 36 TS/TSX/JS/JSX files | status and architecture recurrence include the package sibling |
| registered presentation-prop census | 610 production files = 36 Atlas + 574 dashboard; 19 source-reviewed prop groups / 35 uses; 2 branded props / 6 uses; 12 unbranded authority props / 21 uses / 10 declaration files; 5 benign props / 8 uses | C01a content-binds the explicit declaration registry as branded, typed debt or benign; the ten-name scan is its preflight seed, not a semantic-completeness algorithm |
| direct `Badge` census | 163 real sites / 52 production files = 161/50 dashboard + 2/2 Atlas issuer internals; 2 branded Atlas sites, 58 authority-bearing debt sites / 27 source-bound groups, 103 benign dashboard sites; 0 unclassified | all 163 current sites are source-bound in the C01a governed census; the 107-site/43-file heuristic is retained only as a preflight receipt, never as the governed denominator |
| branded authority paths | 15 issuer/current-branded-sink-import/test/story files; 32 assertions, 0 `any`, 0 `@ts-ignore`, 7 `@ts-expect-error`, 15 `satisfies` sites | C01b checks only this bounded set; safe generated conformance is distinct from an unsafe brand-targeting `satisfies`; unbranded sinks remain C01a debt |
| branded issuers | 2 issuer modules, 3 private brands, 5 exported owner-specific factories | C01c binds closed generated inputs exhaustively and tests runtime novelty |
| runtime HTTP | 87 Python files | only the named C06/C07 files are writable |
| DS4 status estate | 47 rows; 15 current authored; 0 retirement debt | C01a retains exact generated provenance and the status-inventory bridge; it does not claim whole-program value analysis |
| architecture | 1,019 modules / 4,150 dependencies / 0 violations | C02 injects real violations into both engines |
| DS4 waist debts | exactly 3 | one C06 regeneration and three singular swap modules |
| generated governed receipts | 15 anchored rows / 10 distinct export symbols / 13 fields | C06 requires each symbol/field tuple to occur once, remain unchanged, and have an accounted baseline-to-generated line delta; two client hashes refresh |
| CGF owner disposition | 70 owner rows; 3 values (`USE_AS_IS`, `REWORK_TO_FIT`, `DELETE`); 0 production consumers of its current adapter | keep owner values closed but presentation neutral |
| decision grade | 4 owner values; adapter has 10 call sites in 8 production consumer files | swap only the adapter, not the consumers |
| cache-age adapter | one adapter; one `TimeSemanticsLabel`; 2 live render sites | source freshness remains orthogonal |
| raw `fetch()` | historical DS1 9/5; live 5 calls / 3 production files | DS19 deleted four collaboration calls; preserve both receipts |
| all raw transport constructors | 7 calls / 5 production files | adds one `EventSource` and one `WebSocket` |
| flags | 12 keys; 8 consumed; 4 `consumer_missing` | wire 3, retire collaboration; auth pseudo-flag is separate |
| permissions | 33/33 unique server/OpenAPI values | dashboard local list has 15: 12 overlap, 3 unsupported collaboration strings, 21 omitted |
| governed projection audiences | entry 13 definitions: 5 EXPERT, 8 MACHINE, 0 PUBLIC, 0 REVIEWER | C06 adds one source-bound EXPERT G4 definition, producing the C07 entry denominator 14 = 6 EXPERT + 8 MACHINE; C07 enforces all four classes without relabeling the 13 existing definitions |
| N010 client exposure | 11 default-allow expressions across 6 production consumers | no fixture/previous-user authority while loading or failed |
| capability discovery | 14 hardcoded fallback feature records | 43 fixed-chrome surfaces and 19 nonempty capability gates are benign controls |
| locales | 2 ratified active locales but 3 currently exposed; 2,449 leaves in each en/uk/ru catalog | C05a-R1 removes active `ru` exposure without touching catalogs/parity; C05b-D2 records the deferred semantic-copy issuer/panel consumer without claiming human review complete |
| query cache | 66 `useQuery`/`queryOptions` syntax sites in 40 production files; 42 `queryFn` definitions / 39 files | only 1 producer carries owner `as_of`; C11a-C11b-R1 prove that consumer, C12a-C12b-R1 register/enforce the remaining policy without inventing source time |
| IndexedDB | 1 DB / 2 stores; queue has exactly 2 kinds | promotion approve/reject barred; composer drafts enveloped |
| authority-like local state | historical 6 units; current 4 live | WhatIf deleted by DS19; review-attention source absent; lint prevents resurrection; C14a-C17b-R1 migrate the live units plus composer |
| persisted status census | 5 direct write constructions / 4 modules / 4 families; 6 status field paths | C13a deletes two offline-queue writes; C15a excludes Clerk `runStatus`, `structured.verdict`, and `structured.statusChips[]`; C16a-R1-C16b-R1 exclude causal `edges[].status` and keep dispute `status` explicitly interaction-only |
| persistence API census | 41 symbol-resolved lifecycle/construction calls / 14 production files: 23 Web Storage, 5 Zustand, 13 IndexedDB | C17b-R1 content-binds every current site as registered authority-like or fingerprint-bound benign; earlier clusters migrate only their named families |
| DS5 disposition ownership | 17 current roots | readiness ledger retains 21 historical DS5 rows; closure distinguishes them |

The historical 9/5 fetch and six-store denominators remain provenance facts,
not current implementation counts. DS5 does not relabel the 7/5 transport or
4/6 live-store measurements merely to match old prose.

### Reproducible census command ledger

The plan does not infer its denominators from prose. These are the exact
commands used for source and construction-site counts; checker
commands and their receipts are in the baseline table above.

| Denominator | Reproducible command |
| --- | --- |
| 942 dashboard / 36 Atlas UI / 87 runtime HTTP source files | `rg --files apps/runtime-dashboard/src \| rg '\\.[jt]sx?$' \| wc -l`; repeat for `packages/atlas-ui/src`; `rg --files src/polisyos/runtime/http \| rg '\\.py$' \| wc -l` |
| 610 production program files (574 dashboard + 36 Atlas) and 19/35/17/20 named-prop preflight | literal installed-TypeScript `authority_prop_census` command below; it loads dashboard + Atlas tsconfigs, excludes tests/stories, and resolves the explicit current JSX component/prop declarations; C01a governs the resulting reviewed descriptors, not the name regex |
| 2 branded/6 uses; 12 unbranded/21 uses/10 declaration files; 5 benign/8 uses | declaration-level adjudication table and exact source locations recorded by the same C01a census command; entry register query reports 0 `authority_presentation_debt` rows |
| 163 direct `Badge` sites / 52 files; 2 branded / 58 authority debt / 103 benign / 0 unclassified | literal installed-TypeScript `badge_candidate_census` command below supplies the complete Atlas+dashboard direct-site universe; its dashboard subset is 161/50, independently adjudicated as 92 = 28/64 and 69 = 30/39; the two Atlas issuer-internal sites are branded |
| 15 branded paths; 32 assertions / 0 any / 0 ignore / 7 expect / 15 satisfies | TypeScript AST importer census over issuer modules and every current importer of a branded sink, including focused tests/stories; count `AsExpression`, `AnyKeyword`, `SatisfiesExpression` and directive comments per file |
| 2,739-line existing semantic scanner | `wc -l architecture/atlas_surfaces/status_retirement_scan.mjs` |
| 15 generated anchors / 10 symbols / 13 field-bearing anchors | `jq '[.. \| objects \| select(has("export_symbol"))] \| {rows:length, symbols:([.[].export_symbol]\|unique\|length), fields:([.[]\|select(has("field"))]\|length)}' architecture/atlas_surfaces/status-retirement-inventory.json` |
| three waist debts and singular swap paths | `jq '.entries \| {count:length, swaps:[.[].swap_module], symbols:[.[].generated_client_anchor.symbol]}' architecture/atlas_surfaces/ds4-waist-debt-register.json` |
| 70 CGF rows / three values / zero adapter consumers | `jq '.source_reconciliation \| {total_owner_entries, disposition_counts}' architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json`; `rg -n 'presentCgfDisposition\|cgfDispositionPresentation' apps/runtime-dashboard/src --glob '!**/*.test.*' --glob '!**/*.stories.*'` returns only its declaration module |
| four decision grades / 10 calls / eight consumer files | literal `authority_and_store_census` command below; recorded owner values and source-derived calls/files |
| one cache-age adapter / one label / two renders | `rg -n 'TimeSemanticsLabel\|cacheAgePresentation\|cacheAgeLabel' apps/runtime-dashboard/src --glob '!**/*.test.*' --glob '!**/*.stories.*'` |
| 5 `fetch` / 3 files; 7 raw transports / 5 files | `rg -n --glob '!**/*.test.*' --glob '!**/*.stories.*' '\\bfetch\\s*\\(' apps/runtime-dashboard/src`; repeat with `\\b(fetch\\s*\\(\|new EventSource\\s*\\(\|new WebSocket\\s*\\()'` and use `rg -l` for file counts |
| 12 flag keys / 8 referenced outside owner / four named missing consumers | literal `flag_consumer_census` command and per-key output below |
| 33 server and generated permission values | literal `authority_and_store_census` command below; recorded `server=33`, `generated=33`, `equal=True` |
| entry 13 projection definitions / 5 EXPERT / 8 MACHINE | `sed -n '/^_DEFINITIONS:/,/^_DEFINITION_BY_ID/p' src/polisyos/runtime/http/services/governed_projections.py \| rg -c '_ProjectionDefinition\\('`; repeat the bounded scan with `rg -c 'AudienceClass.EXPERT'` and `rg -c 'AudienceClass.MACHINE'`; C06 must re-run it and record 14/6/8 |
| G4 owner shape: 8 fields; owner projection refs: PUBLIC/REVIEWER/EXPERT/MACHINE | `jq -c '{fields:(keys\|sort)}' architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json` returns `blocker_refs, issue_codes, limitation_refs, produced_by, promotion_scope, promotion_state, status, weakest_boundary_reason`; `jq -c '{audiences,EXPERT:(.EXPERT\|keys\|sort),MACHINE:(.MACHINE\|keys\|sort),PUBLIC:(.PUBLIC\|keys\|sort),REVIEWER:(.REVIEWER\|keys\|sort)}' architecture/policy_design_case/layer3_g4_public_export_projection_refs.json` records all four source-owned audience projections and their distinct field classes |
| 11 N010 expressions / 6 production consumers | literal `authority_and_store_census` command below; its per-path output is 1/2/1/1/2/4 |
| 14 fallback capability records | `sed -n '/features: \\[/,/^  \\],/p' apps/runtime-dashboard/src/shared/lib/capabilities.ts \| rg -c '^      key:'`; `rg -n 'FALLBACK_CAPABILITY_MANIFEST\|capabilitiesQuery.isLoading'` locates the two production bypass consumers |
| 43 fixed surfaces / 19 nonempty capability requirements | literal TypeScript-AST `surface_census` command below; recorded components are workspace 6/4, run 8/4, panel 29/11 |
| 2 ratified active of 3 currently exposed locales; 2,449 leaves each | `jq '[paths(scalars)] \| length' apps/runtime-dashboard/src/shared/i18n/locales/{en,uk,ru}.json`; `rg -n 'SUPPORTED_LOCALES\|DEFAULT_LOCALE' apps/runtime-dashboard/src/shared/i18n/locale.ts` records the current `en/uk/ru` + `en` default drift C05a-R1 must close |
| 18 explicit frozen-compatible locale functions / 9 modules | literal installed-TypeScript `frozen_locale_compatibility_census` command below; product persistence/resolution functions are excluded from this compatibility denominator |
| 1 `may_not_use_for` production consumer / 0 semantic-review receipt owners | `rg -l 'packet\.may_not_use_for' apps/runtime-dashboard/src --glob '!**/*.test.*' --glob '!**/*.stories.*' --glob '!**/test/**'` returns exactly `RunExplainabilityPanel.tsx`; a separate `rg -l 'AuthoritySemanticCopy\|authority-semantic-copy\|semantic_review_receipt\|competent_reviewer' apps/runtime-dashboard/src packages/atlas-ui/src architecture/atlas_surfaces` returns exit 1 with no output, recorded honestly as the zero entry census rather than piped through a success exit |
| 66 query syntax / 40 files; 42 producers / 39 files | `rg -n --glob '!**/*.test.*' --glob '!**/*.stories.*' --glob '!**/types.ts' '\\b(useQuery\|queryOptions)(<[^>]+>)?\\s*\\(' apps/runtime-dashboard/src`; repeat with `rg -l`; repeat both for `\\bqueryFn\\s*:` |
| 43 query-key constructors | `rg -c '^  [A-Za-z][A-Za-z0-9_]*:' apps/runtime-dashboard/src/api/queryKeys.ts`; C12a re-derives it from the real exported owner rather than pinning this number |
| 1 IndexedDB / 2 stores / 2 queue kinds | `rg -n 'openDB\|createObjectStore\|OfflineQueueItemKind' apps/runtime-dashboard/src/app/offline/{db.ts,offlineQueueRepository.ts}` |
| 6 historical / 4 live authority-store units / 8 living physical families | literal `authority_and_store_census` and `physical_store_census` commands below; both names and existence are recorded |
| 5 persisted-status writes / 4 modules / 6 field paths | `rg -n 'database\.put\(OFFLINE_MUTATION_QUEUE_STORE|localStorage\.setItem|persist\s*\(' apps/runtime-dashboard/src/app/offline/offlineQueueRepository.ts apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx apps/runtime-dashboard/src/features/runs/domain/disputes.ts apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts`; bounded source inspection records queue `status`, causal `graph.edges[].status`, dispute `disputes[].status`, and Clerk `sessions[].messages[].{runStatus,structured.verdict,structured.statusChips[]}` |
| 41 persistence API calls / 14 files | literal installed-TypeScript `persistence_api_census` command below resolves `Storage`, Zustand middleware, `openDB`, `IDBPDatabase` and `IDBPObjectStore` declarations; recorded families are Web Storage 23, Zustand 5, IndexedDB 13 |
| 261 roots / 17 current DS5 roots / 21 historical readiness rows | `jq '[.. \| objects \| select(.owner_slice? == "DS5")] \| length' architecture/atlas_surfaces/frontend-disposition-register.json`; `jq '[.entries[] \| select(.owning_slice == "DS5")] \| length' architecture/atlas_surfaces/live-application-readiness-ledger.json`; the disposition checker supplies the 261-root denominator |

`frozen_locale_compatibility_census` was run literally from the dashboard
workspace:

```bash
node - <<'NODE'
const fs=require('node:fs'),ts=require('typescript');
const files=[
  'src/shared/i18n/locale.ts',
  'src/shared/i18n/formatters/shared.ts',
  'src/shared/i18n/formatters/number.ts',
  'src/shared/i18n/formatters/currency.ts',
  'src/shared/i18n/formatters/date.ts',
  'src/shared/i18n/messages/icu-messages.ts',
  'src/shared/i18n/typography/typography.ts',
  'src/shared/i18n/typography/quoteMarks.ts',
  'src/shared/i18n/typography/nonBreakingSpaces.ts',
];
const rows=[];
for(const file of files){
  const sf=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true);
  for(const node of sf.statements){
    if(!ts.isFunctionDeclaration(node)||!node.name||!node.modifiers?.some(m=>m.kind===ts.SyntaxKind.ExportKeyword))continue;
    const compatibility=node.name.text==='toIntlLocale'||(file!=='src/shared/i18n/locale.ts'&&node.parameters.some(p=>p.type?.getText(sf).includes('Locale')));
    if(compatibility)rows.push(`${file}#${node.name.text}`);
  }
}
console.log(JSON.stringify({modules:new Set(rows.map(row=>row.split('#')[0])).size,functions:rows.length,rows},null,2));
NODE
```

Recorded output: 18 functions / 9 modules, from `toIntlLocale` through the 17
explicit formatter, ICU and typography entry points listed by the command.

`authority_prop_census` was run literally from product root:

```bash
cd apps/runtime-dashboard && node - <<'NODE'
const path=require('node:path'),ts=require('typescript');
const root=path.resolve('../..'),rel=p=>path.relative(root,p).replaceAll('\\','/');
function parse(c){const p=path.join(root,c),x=ts.readConfigFile(p,ts.sys.readFile);return ts.parseJsonConfigFileContent(x.config,ts.sys,path.dirname(p))}
const a=parse('apps/runtime-dashboard/tsconfig.app.json'),b=parse('packages/atlas-ui/tsconfig.json');
const program=ts.createProgram({rootNames:[...new Set([...a.fileNames,...b.fileNames])],options:a.options}),checker=program.getTypeChecker();
const prod=p=>(p.startsWith('packages/atlas-ui/src/')||p.startsWith('apps/runtime-dashboard/src/'))&&!/[.](test|spec|stories)[.]/.test(p)&&!p.includes('/test/');
function sym(n){let s=checker.getSymbolAtLocation(n);if(s&&(s.flags&ts.SymbolFlags.Alias))s=checker.getAliasedSymbol(s);return s}
function line(n){const s=n.getSourceFile();return rel(s.fileName)+':'+(s.getLineAndCharacterOfPosition(n.getStart(s)).line+1)}
function props(tag){const t=checker.getTypeAtLocation(tag);for(const sig of checker.getSignaturesOfType(t,ts.SignatureKind.Call)){const p=sig.getParameters()[0];if(p)return checker.getTypeOfSymbolAtLocation(p,tag)}return null}
const names=/^(authorityPurpose|presentation|status|freshness|verdict|confidence|tone|readiness|verification|severity)$/;
const rows=new Map();
for(const sf of program.getSourceFiles()){if(!prod(rel(sf.fileName)))continue;const visit=n=>{if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)){const cs=sym(n.tagName),cd=(cs?.declarations||[]).find(d=>prod(rel(d.getSourceFile().fileName)));if(cd){const pt=props(n.tagName);for(const at of n.attributes.properties){if(!ts.isJsxAttribute(at)||!names.test(at.name.text))continue;const ps=checker.getPropertyOfType(pt,at.name.text),pd=ps?.declarations?.[0],key=[String(cs.name),line(cd),at.name.text,pd?line(pd):'?'].join('|');if(!rows.has(key))rows.set(key,{component:String(cs.name),componentDecl:line(cd),prop:at.name.text,propDecl:pd?line(pd):'?',propType:ps?checker.typeToString(checker.getTypeOfSymbolAtLocation(ps,n.tagName)):'?',uses:[]});rows.get(key).uses.push(line(at))}}}ts.forEachChild(n,visit)};visit(sf)}
const data=[...rows.values()].sort((x,y)=>(x.propDecl+x.component).localeCompare(y.propDecl+y.component));
console.log(JSON.stringify({productionFiles:program.getSourceFiles().map(x=>rel(x.fileName)).filter(prod).length,propGroups:data.length,useSites:data.reduce((n,x)=>n+x.uses.length,0),declarationFiles:new Set(data.map(x=>x.propDecl.split(':')[0])).size,consumerFiles:new Set(data.flatMap(x=>x.uses.map(y=>y.split(':')[0]))).size,data},null,2));
NODE
```

Recorded output: 610 production files (574 dashboard + 36 Atlas) and 19 prop groups / 35 uses / 17
declaration files / 20 consumer files. The 2 branded / 12 debt / 5 benign
split is the recorded declaration-level adjudication of those 19 rows.
The regex produced a reproducible preflight set; it is not the gate. The gate
resolves the 19 exact registered component/prop declaration identities and
their current uses, while the complete direct-`Badge` census below separately
accounts `Badge.kind` and every terminal Badge site. DS5 therefore claims this
finite reviewed current inventory, not automatic semantic discovery from prop
names or a complete theorem over non-Badge styling expressions.

`badge_candidate_census` was run literally with the same installed compiler:

```bash
cd apps/runtime-dashboard && node - <<'NODE'
const path=require('node:path'),ts=require('typescript');
const root=path.resolve('../..'),rel=p=>path.relative(root,p).replaceAll('\\','/');
function parse(c){const p=path.join(root,c),x=ts.readConfigFile(p,ts.sys.readFile);return ts.parseJsonConfigFileContent(x.config,ts.sys,path.dirname(p))}
const a=parse('apps/runtime-dashboard/tsconfig.app.json'),b=parse('packages/atlas-ui/tsconfig.json');
const program=ts.createProgram({rootNames:[...new Set([...a.fileNames,...b.fileNames])],options:a.options}),checker=program.getTypeChecker();
function sym(n){let s=checker.getSymbolAtLocation(n);if(s&&(s.flags&ts.SymbolFlags.Alias))s=checker.getAliasedSymbol(s);return s}
const semantic=/(status|state|authority|readiness|decision|quality|severity|trust|freshness|verification|verdict|grade|dispute|approval|block|reject|fail|warn|stale|publish|admissib|evidence|confidence|available|eligible|loaded|ready|valid|overridable|provenance|lineage|risk)/i;
let allSites=0;const allFiles=new Set(),candidates=new Map();
for(const sf of program.getSourceFiles()){const rp=rel(sf.fileName);if(!(rp.startsWith('apps/runtime-dashboard/src/')||rp.startsWith('packages/atlas-ui/src/'))||/[.](test|spec|stories)[.]/.test(rp)||rp.includes('/test/'))continue;const visit=n=>{if(ts.isJsxElement(n)||ts.isJsxSelfClosingElement(n)){const op=ts.isJsxElement(n)?n.openingElement:n,s=sym(op.tagName);if((s?.declarations||[]).some(d=>rel(d.getSourceFile().fileName)==='packages/atlas-ui/src/primitives/Badge.tsx')){allSites++;allFiles.add(rp);const kind=op.attributes.properties.find(x=>ts.isJsxAttribute(x)&&x.name.text==='kind'),k=kind?.initializer?.getText(sf)||'<default>',attrs=op.attributes.getText(sf),kids=ts.isJsxElement(n)?n.children.map(c=>c.getText(sf).trim()).filter(Boolean).join(' '):'';if(k.startsWith('{')||semantic.test(kids)||(semantic.test(attrs)&&/^"(?:ok|warn|fail|info)"$/.test(k))){if(!candidates.has(rp))candidates.set(rp,[]);candidates.get(rp).push(sf.getLineAndCharacterOfPosition(op.getStart(sf)).line+1)}}}ts.forEachChild(n,visit)};visit(sf)}
console.log(JSON.stringify({allSites,allFiles:allFiles.size,candidateSites:[...candidates.values()].flat().length,candidateFiles:candidates.size,locations:Object.fromEntries([...candidates].sort())},null,2));
NODE
```

Recorded output: 163 real sites / 52 files and 107 heuristic candidates / 43
files. The dashboard subreceipt remains 161/50 and 105/41.
The candidate subset is only a preflight heuristic; it is never an authority
or recurrence claim. Two source reviews then adjudicated the complete 161-site
dashboard subset: first half 92 = 28 authority debt + 64 benign; second half 69 = 23
clear authority debt + 39 benign + 7 conservative boundary calls. C01a records
all seven boundary calls as debt. The two Atlas issuer-internal sites are
already branded, so the governed result is 2 branded + 58 authority debt + 103
benign + 0 unclassified.

The 27 source-bound direct-`Badge` debt groups are the measured C01a receipt.
Each group becomes an `authority_presentation_debt` descriptor with the exact
consumer path/site fingerprints, owner slice, capability states and executable
closure signal. The table is accounting, not value-flow inference:

| Direct-`Badge` debt group | Sites | Owner | Capability states | Executable closure signal |
| --- | ---: | --- | --- | --- |
| review-required aggregate | 1 | DS9 | `consumer_missing`, `semantic_test_missing` | generated boolean -> private issuer; missing/deny cannot allow; aggregate veto test |
| bureaucratic legal review | 1 | DS9 | `consumer_missing`, `verification_missing`, `semantic_test_missing` | exhaustive generated-union issuer; novel -> `unrecognized` |
| preflight readiness | 3 | DS7 | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | typed preflight/diagnostic DTOs; mixed fail/warn veto; no raw preview clothing |
| artifact/pipeline decision grade | 2 | DS5 | `producer_missing`, `consumer_missing`, `verification_missing`, `semantic_test_missing` | C06 generated `DecisionGrade`; private exhaustive issuer; runtime novelty |
| control approval quality | 11 | DS9 | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | generated approval/calibration/gate DTOs; weakest-boundary mixed outcome test |
| promotion candidate status | 1 | DS15 | `consumer_missing`, `verification_missing`, `semantic_test_missing` | generated promotion union; private issuer; novel -> `unrecognized` |
| evidence source freshness | 3 | DS8 | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | owner `source_as_of`/freshness contract; oldest-input veto; no local SLA authority |
| comparability | 1 | DS16 | `consumer_missing`, `semantic_test_missing` | generated comparability union; incomparable veto and novelty tests |
| provenance drift | 1 | DS16 | `consumer_missing`, `verification_missing`, `semantic_test_missing` | private invalidation-posture issuer; any load-bearing change vetoes |
| run-deck authority summary | 4 | DS7 | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | live typed run-deck contract; reject `fixture_only`; no local synthesis |
| compound decision grade | 4 | DS5 | `bridge_missing`, `surface_missing` | C06 generated union + private exhaustive issuer + raw-slot typecheck negative |
| governance issue severity | 2 | DS9 | `bridge_missing`, `semantic_test_missing` | generated owner severity field; branded issuer; runtime novelty |
| public-packet authority framing | 3 | DS12 | `producer_missing`, `artifact_missing`, `bridge_missing`, `semantic_test_missing` | generated packet authority/confidence/rights fields; rights-bar mixed-veto test |
| governed projection availability | 2 | DS7 | `bridge_missing`, `semantic_test_missing` | exhaustive generated availability issuer; novel -> `unrecognized` |
| governed projection rights bar | 1 | DS5 | `bridge_missing`, `semantic_test_missing` | generated `may_not_use_for` item; branded veto presentation |
| governed source validation | 1 | DS7 | `bridge_missing`, `semantic_test_missing` | generated validation status; exhaustive issuer and novelty test |
| uncertainty dispute | 1 | DS16 | `bridge_missing`, `semantic_test_missing` | owner uncertainty artifact; disputed remains a mixed-case veto/warn |
| operator blocker overridability | 1 | DS14 | `bridge_missing`, `semantic_test_missing` | generated decision/bool issuer owns clothing; raw-slot typecheck negative |
| candidate declared authority purpose | 1 | DS8 | `bridge_missing`, `semantic_test_missing` | candidate-purpose issuer cannot grant governed authority |
| projection source freshness | 2 | DS18 | `bridge_missing`, `semantic_test_missing` | generated `ProjectionFreshness.state`; absence/novel explicit; no cache-age inference |
| decision confidence | 1 | DS16 | `artifact_missing`, `bridge_missing`, `semantic_test_missing` | typed quantity/uncertainty artifact; arbitrary `ReactNode` rejected |
| explainability governance counts | 3 | DS9 | `bridge_missing`, `semantic_test_missing` | typed governance summary; counts cannot synthesize composed authority |
| negative-certificate blocker | 1 | DS8 | `bridge_missing`, `semantic_test_missing` | generated blocker issuer; non-blocker cannot occupy slot |
| public integrity result | 3 | DS12 | `bridge_missing`, `semantic_test_missing` | verifier-private integrity presentation; explicitly not closeout authority |
| public anti-authority role | 1 | DS12 | `bridge_missing`, `semantic_test_missing` | branded refusal from generated packet role; cannot upgrade to authority |
| threshold unavailable | 1 | DS16 | `artifact_missing`, `bridge_missing`, `semantic_test_missing` | typed unavailable/refusal artifact; no static caller-owned authority token |
| candidate/refusal markers | 2 | DS8 | `bridge_missing`, `semantic_test_missing` | typed candidate/refusal posture; cannot be presented as governed output |

The 103 benign sites are also content-bound, not silently ignored: 64 in the
first 25 files and 39 in the second 25 files. Their typed classes are
interaction/editor state, transport or runtime health, workflow/lifecycle
display without terminality inference, layout/counts, and opaque metadata or
taxonomy. A source fingerprint moving between benign and authority debt is a
register corruption, and a new direct `Badge` site is unclassified/red until
adjudicated. This is a finite current-estate census; it does not discover
semantic authority in arbitrary future expressions.

The separate real-prop census contributes 12 unbranded declaration groups/21
uses: `ControlApprovalPanel.readiness` (DS14),
`DecisionGradeBadge.presentation` (DS5; closure signal C06),
`DataFreshnessBadge.freshness` (DS18), `DecisionCard.verdict` (DS5; C06),
`DecisionCard.confidence` (DS17), `ExplainabilityCard.verdict` (DS5; C06),
`CounterfactualBadge.status` (DS8), `StatusCue.status` and
`FreshnessCue.freshness` (DS16), `TimeSemanticsLabel.freshness` (DS18),
`DisputeBadge.status` (DS11), and `VerificationStatus`/`StatusIcon.tone`
(DS11). They receive typed debt descriptors independently of their inner Badge
site so both the public prop boundary and the current render site are governed.

`authority_and_store_census` was run literally from product root:

```bash
python3 - <<'PY'
from pathlib import Path
import re

owner = Path("src/polisyos/pdc/_impl/layer2_readiness.py").read_text()
grade_block = re.search(r"DecisionGrade = Literal\[(.*?)\n\]", owner, re.S)
assert grade_block is not None
grade_values = re.findall(r'"([^"]+)"', grade_block.group(1))
grade_calls: dict[str, int] = {}
dashboard = Path("apps/runtime-dashboard/src")
for path in [*dashboard.rglob("*.ts"), *dashboard.rglob("*.tsx")]:
    if ".test." in path.name or ".stories." in path.name or path.name == "decisionGradePresentation.ts":
        continue
    count = len(re.findall(r"presentDecisionGradeLabel\s*\(", path.read_text()))
    if count:
        grade_calls[str(path)] = count
print("decision_grade", {"values": grade_values, "calls": sum(grade_calls.values()), "files": len(grade_calls)})

from polisyos.runtime.http.permissions import RuntimePermission
server_permissions = {permission.value for permission in RuntimePermission}
generated_types = Path("packages/runtime-api-client/types.ts").read_text()
permission_match = re.search(r'RuntimePermission: ([^;]+);', generated_types)
assert permission_match is not None
generated_permissions = set(re.findall(r'"([^"]+)"', permission_match.group(1)))
print("permissions", {"server": len(server_permissions), "generated": len(generated_permissions), "equal": server_permissions == generated_permissions})

n010_paths = [
    Path("apps/runtime-dashboard/src/app/routes/WorkspaceBoundary.tsx"),
    Path("apps/runtime-dashboard/src/app/layout/Sidebar.tsx"),
    Path("apps/runtime-dashboard/src/app/layout/Header.tsx"),
    Path("apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx"),
    Path("apps/runtime-dashboard/src/features/commandPalette/CommandPalette.tsx"),
    Path("apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx"),
]
n010_patterns = (
    re.compile(r"authz\s*\?\s*authz\.(?:can|isWorkspaceAllowed)\([^)]*\)\s*:\s*true"),
    re.compile(r"authz\?\.can\([^)]*\)\s*\?\?\s*true"),
)
n010_counts = {
    str(path): sum(len(pattern.findall(path.read_text())) for pattern in n010_patterns)
    for path in n010_paths
}
print("n010", {"counts": n010_counts, "expressions": sum(n010_counts.values()), "files": sum(value > 0 for value in n010_counts.values())})

n015_line = Path("docs/reference/frontend/atlas-live-application-audit.md").read_text().splitlines()[826]
n015_payload = n015_line.split("Persist ", 1)[1].split("; switch", 1)[0].replace(", and ", ", ")
historical_names = [name.strip() for name in n015_payload.split(", ")]
historical_paths = {
    "clerk": "apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts",
    "whatif": "apps/runtime-dashboard/src/features/whatif/state/useWhatIfStore.ts",
    "causal": "apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx",
    "dispute": "apps/runtime-dashboard/src/features/runs/domain/disputes.ts",
    "review_attention": "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts",
    "operator": "apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts",
}
living_names = sorted(name for name, path in historical_paths.items() if Path(path).is_file())
print("stores", {"historical": len(historical_names), "historical_names": historical_names, "living": len(living_names), "living_names": living_names})
PY
```

Recorded output: decision grades
`unsupported/descriptive_only/advisory_admissible/decision_admissible`, 10
calls, 8 files; permissions `33/33/equal=True`; N010 path counts
`1/2/1/1/2/4`, total 11/6; stores 6 historical
(`Clerk`, WhatIf, causal, dispute, review attention, operator craft), 4 living
(`clerk`, `causal`, `dispute`, `operator`).

`flag_consumer_census` was run literally under `zsh`:

```bash
sed -n '/FEATURE_FLAG_KEYS = \[/,/\] as const/p' apps/runtime-dashboard/src/shared/lib/featureFlags.ts | sed -n 's/^  "\([^"]*\)",$/\1/p' | while IFS= read -r ds5_flag_key; do
  ds5_flag_files=$(rg -l --glob '!**/*.test.*' --glob '!**/*.stories.*' --glob '!**/featureFlags.ts' --glob '!**/test/**' "$ds5_flag_key" apps/runtime-dashboard/src | wc -l | tr -d ' ')
  print -r -- "$ds5_flag_key $ds5_flag_files"
done
```

Recorded output: `enableAtlasV2=4`, `enableClerkMode=1`, and each of dark,
Lex, narrative, platform, runs and composer `=1`; causal, collaboration,
command palette and WhatIf `=0`—12 keys, 8 consumers, 4 missing.

`surface_census` was run literally from `apps/runtime-dashboard` against the
installed TypeScript compiler:

```bash
node - <<'NODE'
const fs = require("node:fs");
const ts = require("typescript");

function source(path) {
  return ts.createSourceFile(path, fs.readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true);
}
function unwrap(node) {
  while (ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node)) node = node.expression;
  return node;
}
function variable(sf, name) {
  let found;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name) found = unwrap(node.initializer);
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return found;
}
function requiredCount(objects) {
  return objects.filter((object) => {
    const property = object.properties.find((item) => ts.isPropertyAssignment(item) && item.name.getText() === "requiredCapabilities");
    return property && ts.isArrayLiteralExpression(unwrap(property.initializer)) && unwrap(property.initializer).elements.length > 0;
  }).length;
}

const registry = source("src/app/surfaces/surfaceRegistry.ts");
const workspaces = source("src/app/workspaces.ts");
const run = unwrap(variable(registry, "RUN_DETAIL_SURFACES")).elements.map(unwrap);
const panels = unwrap(variable(registry, "PANEL_SURFACES")).elements.map(unwrap);
const workspaceObjects = unwrap(variable(workspaces, "WORKSPACES")).properties
  .filter(ts.isPropertyAssignment)
  .map((property) => unwrap(property.initializer));
const counts = {
  workspace: [workspaceObjects.length, requiredCount(workspaceObjects)],
  run: [run.length, requiredCount(run)],
  panel: [panels.length, requiredCount(panels)],
};
console.log(JSON.stringify({
  components: counts,
  surfaces: Object.values(counts).reduce((sum, value) => sum + value[0], 0),
  gated: Object.values(counts).reduce((sum, value) => sum + value[1], 0),
}));
NODE
```

Recorded output:
`{"components":{"workspace":[6,4],"run":[8,4],"panel":[29,11]},"surfaces":43,"gated":19}`.

`physical_store_census` was run literally from product root:

```bash
rg -n 'name: "polisyos-clerk-chat"|^export const COMPOSER_DRAFTS_STORE|^const (THRESHOLD_STORAGE_KEY|ANNOTATION_STORAGE_PREFIX|EVIDENCE_WALLET_STORAGE_KEY|ONBOARDING_STORAGE_PREFIX)|^export function disputeStorageKey|^function causalDraftStorageKey' apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx apps/runtime-dashboard/src/features/runs/domain/disputes.ts apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts apps/runtime-dashboard/src/app/offline/db.ts | wc -l
```

Recorded output: `8` living authority-like physical families: Clerk, composer,
causal, dispute, and four operator-craft keys.

`persistence_api_census` was run literally from product root with the installed
compiler. It resolves declarations/types, so aliased `Storage` receivers and
IDB lifecycle methods are included rather than guessed from callee text:

```bash
node - <<'NODE'
const path=require('node:path'),ts=require('./apps/runtime-dashboard/node_modules/typescript');
const root=process.cwd(),cfg=path.join(root,'apps/runtime-dashboard/tsconfig.app.json');
const read=ts.readConfigFile(cfg,ts.sys.readFile),parsed=ts.parseJsonConfigFileContent(read.config,ts.sys,path.dirname(cfg));
const program=ts.createProgram({rootNames:parsed.fileNames,options:parsed.options}),checker=program.getTypeChecker();
const rel=p=>path.relative(root,p).replaceAll('\\','/');
const prod=p=>p.startsWith('apps/runtime-dashboard/src/')&&!/[.](test|spec|stories)[.]/.test(p)&&!p.includes('/test/');
const rows=[];
function sym(n){let s=checker.getSymbolAtLocation(n);if(s&&(s.flags&ts.SymbolFlags.Alias))s=checker.getAliasedSymbol(s);return s}
for(const sf of program.getSourceFiles()){const rp=rel(sf.fileName);if(!prod(rp))continue;const visit=n=>{
  if(ts.isCallExpression(n)){let family=null,op=null,decl='';
    if(ts.isPropertyAccessExpression(n.expression)){op=n.expression.name.text;const recv=checker.getTypeAtLocation(n.expression.expression),rt=checker.typeToString(recv),s=sym(n.expression.name);decl=(s?.declarations||[]).map(d=>rel(d.getSourceFile().fileName)).join(',');
      if(['getItem','setItem','removeItem'].includes(op)&&(rt==='Storage'||decl.includes('lib.dom.d.ts')))family='web-storage';
      if(['get','put','delete','clear','createObjectStore'].includes(op)&&rt.includes('IDBPDatabase'))family='idb-database';
      if(op==='createIndex'&&rt.includes('IDBPObjectStore'))family='idb-store';
    }else if(ts.isIdentifier(n.expression)){op=n.expression.text;const s=sym(n.expression);decl=(s?.declarations||[]).map(d=>rel(d.getSourceFile().fileName)).join(',');
      if(['persist','createJSONStorage'].includes(op)&&decl.includes('zustand'))family='zustand';
      if(op==='openDB'&&decl.includes('idb'))family='idb-root';
    }
    if(family)rows.push({path:rp,line:sf.getLineAndCharacterOfPosition(n.getStart(sf)).line+1,family,op});
  }ts.forEachChild(n,visit)};visit(sf)}
const bucket=name=>rows.filter(r=>r.family.startsWith(name)).length;
console.log(JSON.stringify({sites:rows.length,files:new Set(rows.map(r=>r.path)).size,families:{webStorage:bucket('web-storage'),zustand:bucket('zustand'),indexedDb:bucket('idb-')},rows:rows.sort((a,b)=>(a.path+a.line).localeCompare(b.path+b.line))},null,2));
NODE
```

Recorded output: `41` sites / `14` files; Web Storage `23`, Zustand `5`,
IndexedDB `13`. C17b-R1 governs this exact declaration-resolved API set and
remeasures it at its clean entry after C13a-C16b-R1; it does not infer payload
semantics from method or field names.

The surface and store commands are bounded structural censuses, not future lint
implementations. C01a records its measured declaration set; C12a and C17b-R1 replace
their entry receipts with direct construction-site registries. None becomes a
claim about arbitrary program behavior.

## Pattern pass and capability truth

Relevant repair rows are P01 (contract-only capability), P03 (hidden internal
richness), P04 (status lattice), P05 (authority boundary leak), P06 (shim
drift), P07/P08 (replay/time roles), P09 (warning lifecycle), P10 (semantic
adequacy), P13 (governance gravity), P15 (speculation laundering), P25/P26
(audience/authorization), P27/P28 (owner bypass/unstrangled legacy), P29
(marker-only proof), and P31-P34 (instance patching, trust by form, probe
teaching, dishonest exclusion).

The target correct pattern is:

```text
owner contract + producer + persisted artifact/event + generated bridge
  -> private issuer + branded slot checked by tsc
  -> bounded construction-site/escape check + runtime novelty witness
  -> API/dashboard/audit surface or explicit surface_out_of_scope
```

At entry, each waist row is `bridge_missing + surface_missing`; the requested
lint battery is `verification_missing`; audience mapping is `bridge_missing`;
N010 is `consumer_missing`; cache isolation is `contract_only` or
`verification_missing`; the four flag rows are `consumer_missing`; the review
WebSocket authentication remainder stays `bridge_missing` and is not closed by
a transport exemption. No cluster may upgrade a label unless producer, bridge,
consumer, negative, and surface evidence actually exist.

The enforcement battery is verification infrastructure, never authority. Its
claim is deliberately three-part and no broader: compile-time assignability
protects branded slots; a syntactic rule rejects the enumerated escape hatches
on the measured authority paths outside typed exemptions; issuers reject
fixture/unlisted input and render runtime-novel owner values as explicit
`unrecognized`. Sinks not yet branded remain typed debt. A checker cannot make
a status admissible, a flag cannot grant permission, and a presentation
adapter cannot turn a TypeScript union into runtime owner proof.

## Universal cluster protocol

Every implementation cluster follows this order:

1. Record clean status, HEAD, exact preflight file set, current register rows,
   and inherited baseline identities.
2. Add the named negative first. Run it and journal the exact expected failure
   reason; a timeout or lost output is a non-receipt.
3. Make the smallest wire/extend/consolidate change. Never hand-edit generated
   output or copy a canonical vocabulary.
4. Move every touched register row with successor and consumer evidence, or
   keep it pending with a typed capability label and executable closure signal.
   Any edit to `frontend-disposition-register.json` regenerates
   `docs/reference/frontend/atlas-frontend-disposition-register.md` in the same
   commit; the checker treats report drift as red, so C20 never carries that
   tail for an earlier cluster.
5. Run affected tests, typecheck, production build, scoped lint, both
   architecture engines where relevant, governed checkers, and corruption
   probes. False positives are defects and each lint carries a benign control.
   `tsc` is the authority-slot enforcement engine; AST rules remain bounded to
   direct syntax or construction sites and state that residual in their output.
6. At wave boundaries run full gates and compare inherited identities by hash;
   removals shrink debt, additions fail.
7. Request independent review. Important/Critical findings are repaired
   red-first and the cluster commit is amended before continuing.
8. Record exact denominators in the journal and leave one clean scoped commit.

A cluster measured above its cap stops at the preceding clean commit and is
re-cut with the next continuous number. No cap is enlarged after entry.

**Content-binding sizing law (P31 class fix):** A cluster that writes a
content-bound governed artifact also owns every induced re-anchor of a receipt
that pins it. The induced path counts against the cap. This replaces the
instance-by-instance report accounting with one structural rule for every
disposition-register writer; the induced status-inventory receipt is not an
optional tail or a later-cluster cost.

### Deferral verification cap

A deferral or debt row's closure signal conforms to the register's established idiom—a named command plus a declared condition—and its verification bar is capped there. A review may not require a debt row to carry a stronger verification mechanism than the register schema and its existing rows carry. A stronger closure mechanism, if genuinely wanted, is its own cluster.

**Measured receipt (P35 correction):** complete enumeration of all 46 `closure_signal` values finds 42 simple `<command> exact ids exits 0 after condition` rows, 2 embedded `python3 -c ...` rows, and 2 prose-only rows; `closure_signal` remains only `nonEmptyString`.

**Binding ratchet (P36 review-standard adjacency):** measure a deferral against the register's established 42-row simple idiom, never its predecessor. Predecessor adjacency raised checker/test deltas +58/+33, +90/+78, then +183/+125 until the deferral failed.

**Desynchronization lesson:** a JSON command string plus a separately declared helper signature can drift silently; prefer a self-contained command that names the exact test IDs.

**P37 rationale:** a debt row asserts absence and promotes/adopts nothing; a custody-grade closure predicate was not established.

### Binding review bars

- **Closure signals:** the governing bar is the schema's `nonEmptyString` plus the register's simple sibling rows, never a prior deferral.
- **AST rules:** the governing bar is direct syntax or construction sites; their output states the indirect-flow residual rather than claiming to close it. `tsc` is the authority-slot enforcement engine.
- **Sizing:** stop for a new bespoke mechanism at any line count. N instances of an established mechanism scale linearly and are measured per mechanism, not rejected by their aggregate line count.
- Every review finding cites the schema, plan, or landed sibling that sets its bar. If a plan law conflicts with architect guidance, stop and ask; do not select the more restrictive reading.

### Sizing-law re-cuts after the architecture ruling

The C00 caps remain binding. The earlier re-cuts counted a disposition report
but omitted the induced `architecture/atlas_surfaces/status-retirement-inventory.json`
receipt re-anchor. The complete writer census below applies the sizing law to
every remaining disposition-register writer. Original rows are stopped
historical evidence, never enlarged clusters; each no-fit row receives its
first continuously numbered `-R1` successor.

| Original cluster | Declared cap | Corrected unique paths (includes induced status-inventory re-anchor) | Fit | Execution successor |
| --- | ---: | ---: | --- | --- |
| C03a | 6 | 7 | no-fit | C03a-R1 / 7 |
| C03b | 12 | 13 | no-fit | C03b-R1 / 13 |
| C04a | 10 | 11 | no-fit | C04a-R1 / 11 |
| C05a | 10 | 11 | no-fit | C05a-R1 / 11 |
| C05b | 6 | 7 | record-only | C05b-D2 / 7 |
| C06 | 26 | 24 | FIT | C06 / 26 (already fit) |
| C07 | 26 | 25 | FIT | C07 / 26 (already fit) |
| C08b | 10 | 11 | no-fit | C08b-R1 / 11 |
| C09a | 10 | 11 | no-fit | C09a-R1 / 11 |
| C09b | 7 | 8 | no-fit | C09b-R1 / 8 |
| C10 | 7 | 8 | no-fit | C10-R1 / 8 (DEFERRED) |
| C11b | 9 | 10 | no-fit | C11b-R1 / 10 |
| C12b | 9 | 10 | no-fit | C12b-R1 / 10 |
| C13a | 18 | 18 | FIT | C13a / 18 (already fit) |
| C13b | 9 | 10 | no-fit | C13b-R1 / 10 |
| C14b | 7 | 8 | no-fit | C14b-R1 / 8 |
| C15b | 5 | 6 | no-fit | C15b-R1 / 6 |
| C16a | 5 | 6 | no-fit | C16a-R1 / 6 |
| C16b | 7 | 8 | no-fit | C16b-R1 / 8 |
| C17a | 9 | 10 | no-fit | C17a-R1 / 10 |
| C17b | 9 | 10 | no-fit | C17b-R1 / 10 |
| C18b | 5 | 6 | no-fit | C18b-R1 / 6 |
| C19 | 13 | 14 | no-fit | C19-R1 / 14 |

The audited writer set is exactly these 23 rows; C20 is not a writer. C01a/
C01b/C01c are the separately authorized `636645bec` re-cut. C06, C07 and
C13a retain their IDs and caps because their corrected sets already fit.

### Register transition map

| Authority row(s) | Boundary | Planned transition / proof |
| --- | --- | --- |
| 47 status rows + authority presentation census | C01a-C01c | preserve 15/0 estate and exact generated provenance; account 2 branded props/6 uses plus 2 branded direct sites, 39 typed debt descriptors (12 prop boundaries + 27 direct-`Badge` groups), 5 benign prop groups and all 103 benign direct sites; forbid enumerated escape syntax only on branded paths; prove issuer exhaustiveness/novelty |
| architecture baseline/recurrence receipts | C02 | zero remains zero; real custom and dependency-cruiser violations fail even with marker bytes intact |
| `raw-fetch-auth-refresh`, `raw-fetch-auth-initial`, `raw-fetch-auth-replay` | C03b-R1 | bounded `use_as_is` inside the typed auth transport owner plus symbol-bound exemption and corrupt sibling negative |
| `raw-fetch-flag-manifest` | C03b-R1 | bounded `use_as_is` inside the strict registry adapter; C18a-C18b-R1 supply the consumer semantics |
| `transport-ws-review` | C03b-R1 | remains `bridge_missing`; typed constructor classification does not close N018 authentication/degradation |
| DS1 raw-transport historical receipt | C03a-R1 | add typed drift row: DS1 9 fetches/5 files versus live 5 fetches/3 files and 7 raw constructors/5 files; close only when the executable direct-call census matches |
| hardcoded capability fallback / `cache-query-memory` | C04a-R1-C04b then C11a-C12b-R1 | fallback removed in C04a-R1 and its construction sites guarded in C04b; root transitions only after cacheable/never-cache/operational/debt classes are derived and enforced |
| `route-app-layout::ru-ui-catalog` | C05a-R1 | stays `frozen_legacy_continuity`; active exposure negative proves it is not a product locale |
| `semantic-copy-issuer-panel-consumer-deferral` | C05b-D2 then C05b-R3 | C05b-R3 lands only the private issuer/generated `may_not_use_for` guard; it remains `rebind_pending/open_debt` for the panel/direct-Badge bridge, consumer, verification and semantic test while DS6 accepted human-review receipts remain 0 |
| three `ds4-waist-debt-register` rows | C06 | close only after runtime model, generated union, singular adapter, consumer, corruption and novel-value proof |
| audience enforcement supplemental/readiness evidence | C07 | four-class deny matrix over all 33 enum-owned permission values and the 14-definition/6-EXPERT/8-MACHINE post-C06 census; G4 is EXPERT with exact `mode.analyst`; no client substitute |
| `route-login`, `feature-auth`, `api-op-get-auth-me` | C08a-C09b-R1 | test support is isolated first; core identity then six downstream surfaces rebound to verified live identity or explicit unknown; loading/error/401/cross-tenant remain fail-closed |
| composed/recomputed status verification | C06 then C10-R1-C12b-R1 | C06 projects the existing G4 owner artifact as a complete generated packet; deferred C10-R1 retains its nominal request-scoped boundary contract; C11a-C12b-R1 own the one migrated query's cache revalidation and the source-bound debt ratchet, and no cluster makes a source-wide arithmetic claim |
| `cache-query-memory` | C12a-C12b-R1 | rebound only for the governed builder, one C11a-C11b-R1 consumer and a source-derived debt ratchet; 65 direct constructions and 41 producers remain fingerprint-bound typed debt unless independently proven operational; every authority-like producer debt names owner field, contract and owner slice, never timestamp inference |
| `offline-queue-promotion-decision`, `cache-service-worker-static` | C13a-C13b-R1 | promotion row retired/strangled from the queue; SW remains use-as-is with behavioral no-API/authority-cache proof |
| `cache-local-storage-state`, `offline-draft-composer`; six named cache units | C14a-C17b-R1 | composer + 4 live historic units enveloped; WhatIf deletion preserved; review-attention gets a fresh deletion census; domain feature ownership not claimed |
| four flag disposition rows | C18a-C19-R1 | strict registry then provider wiring; causal/palette/what-if rebound to real whole-surface gates; collaboration retired and absent |
| 21 historical DS5 readiness rows vs 17 live DS5 roots | C20 | update only supported chain fields; deleted/handoff rows stay honest; no denominator collapse |

### Wave boundaries

- **W0 — C00:** plan, install/link proof, measured baseline, clean plan commit.
- **W1 — C01a-C05b-R1:** branded authority slots, escape syntax, issuer novelty,
  status, architecture, transport, capability, and semantic-ID
  enforcement. Full dashboard/Atlas gates plus governed corruption probes.
- **W2 — C06-C10-R1:** generated waist, audience denial, N010, and composition.
  Full runtime contract, focused HTTP, generated-client, dashboard, and scanner
  gates.
- **W3 — C11a-C17b-R1:** query cache, offline action, and four bounded local-state
  families.
  Full dashboard suite, browser cache/offline tests, architecture, and zero-new
  baseline comparison.
- **W4 — C18a-C20:** flags, ledgers, final receipts, closure and fence proof.
  Full closeout battery including Storybook/a11y/visual, with only the exact
  inherited DS6/DS8 identities allowed.

## Pre-sized execution clusters

### DS5-C01a — authority-sink census and brand/debt boundary

**Architecture re-cut:** architect ruling `636645bec` replaces C01. The current
commit `b67084dd6` remains as honest history; C01a removes its abandoned
whole-program analysis machinery and tests written only for it. Retain only exact
generated provenance driven by governed paths/hashes, the status-inventory
bridge, declaration-derived Atlas prop census, and the DS5-only compiler-
diagnostics gate.

**Measured set:** exactly 14 paths; cap 15: the current eight C01a paths
(`status_retirement_scan.mjs`, status checker/test/inventory, DS5 checker/test,
the dashboard compile witness, journal), this plan, and the disposition
register/schema/checker/test plus its generated reference report. The production census is 610 files, 19 semantic
prop groups/35 uses: 2 already branded/6 uses; 12 unbranded authority props/21
uses/10 declaration files; 5 benign/8 uses. The complete direct-`Badge` census
is 163 sites/52 files: 2 branded Atlas issuer-internal sites, 58 authority-
bearing dashboard sites in 27 source-bound groups, 103 benign dashboard sites,
and 0 unclassified. C01a adds 39 typed debt descriptors—27 direct-site groups
plus 12 public prop boundaries. Entry authority-presentation debt is zero rows.
No consumer migration occurs in this census cluster.

**Red first:** `test_every_authority_presentation_prop_is_branded_or_typed_debt`.
Remove one declaration, one owner slice or one executable closure signal from
the census receipt and require failure. A generated-looking structural object
must not satisfy a nominal slot. `SegmentedControl.tone`, form accent tone,
numeric confidence capture, responsive layout and interaction presence are
benign declarations that must remain classified without becoming authority.
Delete a direct-`Badge` site descriptor, move a recorded source fingerprint,
or reclassify an authority site as benign while retaining its surrounding
markers; each corruption must fail. Add one new direct `Badge` use and require
an unclassified-site diagnostic until a typed adjudication is recorded.
Restamp one pre-existing supplemental row to `2026-08-02`, or give one new
authority descriptor the inherited `2026-07-17` date; both corruptions fail.
`test_ui_local_closed_status_declaration_is_not_generated_owner` adds a local
enum/union at a measured authority declaration and fails exact declaration-
provenance validation without making a whole-program use claim.

**Acceptance:** every measured declaration/use is either a private-issued
brand, an `authority_presentation_debt` row with owner slice, capability state
and executable closure signal, or an explicit benign class. C01a records the 12
unbranded props and all 58 direct authority sites as typed debt; all 103 direct
benign sites are explicit source-bound controls, and both Atlas direct sites are
content-bound to the existing private brands. The 107-site heuristic has no
enforcement role. The register adds a typed authority-sink descriptor plus
owner states/closure command/test and content-bound consumer fingerprints; it
does not claim semantic discovery for arbitrary future expressions. The status
estate remains 47/15/0. The reduced commit is substantially smaller and the
diagnostics gate rejects type-invalid fixtures. Every new authority descriptor
owns exact `decision_date: 2026-08-02`; the existing global
`DECISION_DATE = 2026-07-17` history and every pre-existing supplemental row's
date bytes remain unchanged. The surgical writer is run twice and the second
run is byte-identical; an unrelated restamp is red.

**Expected forward commit:** `DS5-C01a census branded authority sinks`.

### DS5-C01b — bounded authority escape-hatch lint

**Measured input:** exactly 15 branded-authority-path files: three issuer
modules, one package re-export, nine symbol importers, and the two explicit
governance collections (`EVIDENCE_FAMILIES`, `EXPECTED_RUNTIME_EXPORTS`). The
12 unbranded sink groups remain C01a debt and are not falsely covered by this
assignability escape rule. The post-C01a AST census finds 35 assertions, 0
`any`, 0 `@ts-ignore`, 8 `@ts-expect-error`, and 15 `satisfies` sites. C01a's
type witnesses account exactly for the prior receipt's +3 assertions and +1
`@ts-expect-error`. This is a local syntax property, not a data analysis.

The exact bounded input is: `AuthorityBadge.tsx`, `EnvelopeChip.tsx`,
`evidenceTypes.ts`, Atlas UI `index.ts`, `AuthorityBadge.test.tsx`,
`EnvelopeChip.test.tsx`, `evidencePrimitives.a11y.test.tsx`,
`oneOwner.test.ts`, `publicSurface.test.ts`, dashboard
`RunExplainabilityPanel.tsx`, `OperatorDiagnosticPanel.tsx`,
`DecisionCard.tsx`, `DecisionCard.test.tsx`,
`EvidencePrimitives.stories.tsx`, and
`fixtureOnlyAuthority.compile.test.tsx`. The recorded AST command parses those
15 files with the installed TypeScript compiler, counts `AsExpression` /
`TypeAssertionExpression`, `AnyKeyword`, `SatisfiesExpression`, and the two
directive comments, and returned `15 / 35 / 0 / 0 / 8 / 15`.

```bash
node - <<'NODE'
const fs=require('node:fs'),ts=require('./apps/runtime-dashboard/node_modules/typescript');
const files=`apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx
apps/runtime-dashboard/src/shared/ui/OperatorDiagnosticPanel.tsx
apps/runtime-dashboard/src/shared/ui/compounds/DecisionCard.test.tsx
apps/runtime-dashboard/src/shared/ui/compounds/DecisionCard.tsx
apps/runtime-dashboard/src/shared/ui/evidence/EvidencePrimitives.stories.tsx
apps/runtime-dashboard/src/shared/ui/evidence/fixtureOnlyAuthority.compile.test.tsx
packages/atlas-ui/src/index.ts
packages/atlas-ui/src/primitives/AuthorityBadge.tsx
packages/atlas-ui/src/primitives/EnvelopeChip.tsx
packages/atlas-ui/src/primitives/evidenceTypes.ts
packages/atlas-ui/tests/AuthorityBadge.test.tsx
packages/atlas-ui/tests/EnvelopeChip.test.tsx
packages/atlas-ui/tests/evidencePrimitives.a11y.test.tsx
packages/atlas-ui/tests/oneOwner.test.ts
packages/atlas-ui/tests/publicSurface.test.ts`.split('\n');
const count={assertions:0,any:0,ignore:0,expect:0,satisfies:0};
for(const file of files){const text=fs.readFileSync(file,'utf8'),sf=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,file.endsWith('x')?ts.ScriptKind.TSX:ts.ScriptKind.TS);count.ignore+=(text.match(/@ts-ignore/g)||[]).length;count.expect+=(text.match(/@ts-expect-error/g)||[]).length;const visit=node=>{if(ts.isAsExpression(node)||ts.isTypeAssertionExpression(node))count.assertions++;if(node.kind===ts.SyntaxKind.AnyKeyword)count.any++;if(ts.isSatisfiesExpression(node))count.satisfies++;ts.forEachChild(node,visit)};visit(sf)}
console.log(JSON.stringify({files:files.length,...count}));
NODE
```

**Measured edit set:** 11 paths; cap 13: the scanner/DS5 checker/test;
`AuthorityBadge.tsx`, `evidenceTypes.ts`; AuthorityBadge, EnvelopeChip and
DecisionCard tests; the compile-negative fixture; this section; and journal.
Typed exemptions live with the lint as exact path/line/column/construct/target/
AST-hash records carrying owner and reason. This avoids an unpaired disposition
register write and its mandatory DS19 receipt refresh. Inline expected-error
tests move to the DS5 diagnostics harness.

**Red first:** `test_authority_paths_reject_unregistered_type_escape_hatches`.
Separate corruptions add `as`, double assertion, explicit `any`,
`@ts-ignore`, `@ts-expect-error`, and a `satisfies` target that contains the
brand or widens to `any`/`unknown`. A generated DTO conformance check and the
exhaustive `satisfies Record<generated-union, BadgeTone>` map are benign.

**Acceptance:** all measured branded authority paths are derived from imports and
issuer declarations; each forbidden construct fails unless its exact typed
exemption remains current. Unknown, stale, moved or reasonless exemptions fail.
The lint reports only this bounded syntactic guarantee.

**Expected commit:** `DS5-C01b forbid authority escape hatches`.

### DS5-C01c — issuer exhaustiveness and runtime novelty

**Entry re-derivation:** this is a construction-site/type property plus existing
runtime behavior, not value-flow analysis. The scanner derives issuer facts from
private unique-symbol declarations, branded factory return types and generated
parameter declaration locations; `tsc` remains the exhaustiveness engine and
the existing Vitest negatives execute the real issuers.

**Measured set:** exactly 12 paths; cap 13: `AuthorityBadge.tsx`,
`evidenceTypes.ts`, `AuthorityBadge.test.tsx`, scanner/DS5 checker/test,
disposition checker/test/register/reference, status inventory, this section, and journal. Entry has 2 issuer modules, 3 private brands, 5 exported branded
factories, 3 issuance stores, 4 freezes and 10 throw sites. Exact generated
bindings are 2 projection parity parameters, a 12-state exhaustive tone map, a
2-value owner-authority union, one fixture literal, one available-packet
literal, and open owner-list membership. The 39 C01a debt rows do not transition;
editing the disposition register would create no truthful state change and
would force an unrelated DS19 receipt refresh.

**Red first:** `test_authority_issuer_requires_generated_exhaustiveness_and_runtime_novelty`.
Corrupt a generated union literal or exhaustive map; export a brand/constructor;
clone a branded object; pass `fixture_only`, a label absent from its owner list,
or a runtime-novel generated value. A genuinely open owner extension remains
visible and neutral.

**Acceptance:** the construction-site fact packet requires every closed-input
issuer to use compile-time exhaustiveness against the exact generated
declaration; brands and constructors remain module private; issued values are
frozen and identity-checked; fixture/unlisted values throw; runtime novelty
returns explicit `unrecognized`; no issuer exports a value-level vocabulary
constant. DS5 claims compile-time nominal protection, bounded escape syntax and
runtime issuer behavior—nothing broader.

**Frozen outcome:** round-2 NO-GO is recorded by the two
`authority-issuer-*` producer-binding debt rows; C01c does not claim closure.

### DS5-C02 — architecture recurrence in both engines

**Ruling re-derivation:** this property is the decidable module graph over real
resolved imports. The custom checker and dependency-cruiser execute that graph;
neither attempts to infer values or presentation semantics.

**Measured set:** exactly 6 paths including journal; cap 7: dashboard custom
architecture script and dependency-cruiser config, Atlas UI architecture
script, the two existing Atlas governance checker/test surfaces, and journal.
The inherited DS4 “both engines” claim means the dashboard custom checker plus
dependency-cruiser; Atlas UI's checker is an additional package sibling, not a
third origin of the 36->0 denominator.

**Red first:** `test_real_illegal_edges_fail_custom_and_dependency_engines`.
Inject resolvable `shared -> app/api` and `app-state -> provider` imports for the
custom engine, and a forbidden import plus a real cycle for dependency-cruiser;
execute both engines. A package boundary injection exercises the sibling
checker. Removing the illegal imports while retaining rule text must go green. A
public barrel, shared->shared import, numeric error-budget width and three-way
responsive layout are benign controls.

**Acceptance:** the DS4 36->0 class is executable in both engines, future source
files are discovered from the module graph, and `lint:enforcement` cannot remain
green if either engine is bypassed. C02 claims only the decidable import-graph
property; it makes no status, presentation, numeric or control semantics claim.

**Expected commit:** `DS5-C02 make architecture zero recurrent`.

### DS5-C03a-R1 — record the raw-transport denominator drift

**Measured set:** exactly 6 governed artifact paths plus journal = 7; cap 7:
frontend disposition register/schema/checker/test, its generated reference
report, `architecture/atlas_surfaces/status-retirement-inventory.json`, and
journal. The typed receipt preserves both measurements: DS1 9 raw
fetches/5 files; current 5 fetches/3 files and 7 raw constructors/5 files.

**Red first:** `test_raw_transport_drift_row_binds_historical_and_live_census`.
Changing either denominator, dropping the DS19 collaboration-deletion evidence,
or omitting owner/capability states/executable closure fails. The surgical
writer must be byte-preserving and idempotent.

**Acceptance:** the historical number can no longer circulate as a live lint
denominator; the row stays open until the direct source census and typed owner
classification agree. No transport implementation changes in C03a-R1.

**Expected commit:** `DS5-C03a-R1 record raw transport drift`.

### DS5-C03b-R2 — direct authority-transport construction lint

**Ruling re-derivation:** the guarantee is only the bounded syntactic census of
direct imported/callee transport constructions. Typed purpose owners make the
sanctioned paths explicit; C03b-R2 makes no claim about arbitrary indirect call
flow.

**Measured set:** exactly 16 implementation/governed paths plus journal = 17;
cap 17: the shared C01a scanner/checker/test, one canonical typed raw-transport
purpose module, the five production owner files, frontend disposition register
and generated report, `architecture/atlas_surfaces/status-retirement-inventory.json`,
and journal. C01a already wires `lint:enforcement`; C03b-R2
does not retouch `package.json`. Current targets are 7 constructors / 5
production files: auth 3, flags 1, telemetry 1, SSE 1, WebSocket 1.

**Red first:** `test_direct_authority_transport_requires_typed_purpose_factory`.
Corruptions use each direct `fetch`, `new EventSource`, and `new WebSocket`
construction with an authority endpoint outside the typed owner, or import a
lookalike factory from the wrong declaration. The exemption is a real imported
typed purpose (`auth`, `flag_exposure`, `telemetry`, `governed_channel`) and the
primitive must match its purpose. File/path/name-only allowlists fail. A local
injected function named `fetch` and generated-client `fetchImpl` are benign.

**Acceptance:** the AST rule enumerates direct constructors and their direct
callee/import declaration over the measured production set; all seven live
constructors use typed owners and a new direct construction fails. It does not
analyze indirect calls. Historical deleted collaboration calls are not
grandfathered; telemetry remains DS12-limited; review WS remains N018
`bridge_missing`. Register transitions and generated report land with the five
owner migrations.

**Expected commit:** `DS5-C03b-R2 type raw authority transports`.

### DS5-C03b-D1 — record-only deferral after the two-fix freeze

**Status:** C03b implementation is **Not yet**. C03b-R1 was undermeasured and
recut as C03b-R2 / cap 17; R2 exhausted two fix rounds and is deferred through
the existing typed `raw-transport-denominator-drift` row, not repaired here.

**Measured set:** exactly the 7 permitted record paths: disposition checker and
test, register and report, induced DS19 status-hash receipt, this plan, and the
journal; cap 7. No transport/product/scanner implementation is in scope.

**Acceptance:** the open row preserves its 9/5 historical and 5/3 plus 7/5 live
receipts, and its closure runs both named C03b tests; it remains nonzero until
both pass. No claim that C03b landed.

**Expected commit:** `DS5-C03b-D1 record raw-transport deferral`.

### DS5-C04a-R1 — strangle the live capability fallback

**Measured set:** exactly 10 implementation/governed paths plus journal = 11;
cap 11: `shared/lib/capabilities.ts` + test,
`api/hooks/useCapabilities.ts`, `api/hooks/controlQueries.test.tsx`,
`runDetailSurfaces.test.tsx`, `CommandPalette.tsx` + test, frontend disposition
register + generated report, `architecture/atlas_surfaces/status-retirement-inventory.json`,
and journal. The violation is 14 fallback feature
records in two production consumers; CommandPalette currently treats loading
as allow. The 43 fixed surfaces and 19 capability gates are benign chrome.

**Red first:** `test_capability_discovery_accepts_only_issued_owner_manifest`.
Loading/offline/error and a locally authored fallback are unavailable; a fixed
workspace tab and typed `requiredCapabilities` gate are positive controls.

**Acceptance:** a module-private brand issues
`available(ownerManifest) | unavailable(reason)`; both live consumers accept
only that value; no fallback inventory survives; loading cannot invent a
feature. Consumer and disposition/report evidence land together.

**Expected commit:** `DS5-C04a-R1 strangle capability fallback`.

### DS5-C04b — make capability discovery recurrent

**Status:** C04b-R2 recovers the bounded direct-syntax mechanism from checkpoint
`32598d1094c75391bfd02e719236de7398cb5de9` as a forward ten-path commit.
The former D1 debt is removed in the same governed transition; its rejected
checkpoint and forward revert remain history, not a verification bar.

**Measured set:** exactly 10 paths; cap 10: scanner/checker/test, disposition
checker/test/register/report, DS19 pin, plan, and journal.

**Red first:** `test_authored_capability_discovery_construction_fails`.
An inline feature array, helper-authored `CapabilityFeatureInfo`, loading-as-
enabled branch and local generated lookalike fail at the bounded issuer/direct-
literal construction site. Runtime-fetched `.features`, fixed chrome and typed
availability gates are benign.

**Acceptance:** the AST rule guards only issuer construction and direct authored
`CapabilityFeatureInfo` literals. It does not infer menu behavior or ban fixed
chrome; C04a-R1's behavioral tests own the live consumer claim. Indirect
enclosure identity, including nested same-name functions, is a stated residual
outside this direct-syntax/construction-site rule; `tsc` owns authority slots.

**Expected commit:** `DS5-C04b-R2 lint authored capability discovery`.

### DS5-C04b-D1 — record-only deferral after the two-fix freeze

**Status:** superseded by C04b-R2. The original record-only D1 closure used a
stronger enclosure-identity claim than this plan's direct-syntax bar, so its
row and helper are removed with the landed mechanism.

### DS5-C05a-R1 — D4 active-locale and frozen-continuity boundary

**Measured set:** exactly 10 implementation/governed paths plus journal = 11;
cap 11: `locale.ts`, `LocaleProvider.tsx` + test; typography `typography.ts` +
test, `quoteMarks.ts`, `nonBreakingSpaces.ts`; frontend disposition register +
generated report; `architecture/atlas_surfaces/status-retirement-inventory.json`;
and journal. Each en/uk/ru catalog has 2,449 leaves; no
catalog or parity file is edited. The unedited, source-measured compatibility
surface is 18 explicit-locale functions across 9 modules: the locale owner;
formatter `shared`, `number`, `currency`, and `date`; ICU messages; and the
three typography modules. Seventeen are exported formatter/ICU/typography
entry points and `toIntlLocale` is the locale-owner conversion.

**Red first:** `test_ru_cannot_reenter_active_product_locale` and
`test_uk_is_primary_and_en_is_fallback`. A corruption passes `ru` through
provider, storage, default resolution or catalog selection; the existing
explicit-input formatter/ICU/typography functions are the bounded frozen
compatibility controls. A separate
`test_frozen_ru_formatters_require_explicit_legacy_locale_and_never_become_product_state`
proves their omitted locale defaults through product resolution and that an
explicit `ru` argument cannot enter provider state.

Locale types split product exposure from frozen continuity: `ProductLocale` is
`uk | en`, default `uk`; `LegacyContinuityLocale` is `ru`; compatibility
`Locale` is their union only for the 18 enumerated explicit-locale functions.
Product resolution, storage, provider state, catalog selection and all omitted
formatter defaults accept/return only `ProductLocale`. Explicit legacy input
may format caller-supplied continuity text but cannot enter `LocaleProvider`,
storage, active catalog selection or default resolution. This is a finite
compatibility classification, not a claim that `ru` is an active locale.

**Acceptance:** active locales are exactly `uk` and `en`; `uk` is primary and
default, `en` explicit baseline/fallback; the `ru` catalog, parity test and
formatting expectation remain byte-unmodified; all 18 compatibility entry
points remain explicit-input-only and the disposition/report record
`legacy_continuity_frozen`, never active support. The three DS6 parity failures
remain exact.

**Expected commit:** `DS5-C05a-R1 separate product and frozen locales`.

### DS5-C05b-R1 — INT-R6 semantic IDs and static authority copy

**Ruling re-derivation:** canonical ID plus content-bound review issuance is a
private nominal construction boundary. The checker guards that registry/issuer
site and same-ID uniqueness; it neither compares prose for semantic meaning nor
traces arbitrary copy values through the program.

**Measured set:** exactly 11 implementation/governed paths plus journal = 12;
cap 12: `RunExplainabilityPanel.tsx` + its governed-projection test; new
`AuthoritySemanticCopy.ts` + test; new semantic-copy registry/schema; DS5
checker/test; frontend disposition register + generated report;
`architecture/atlas_surfaces/status-retirement-inventory.json`; and journal.
The one current real authority-copy consumer is `packet.may_not_use_for`;
accepted human-review receipts are 0 at entry.

**Red first:**

- `test_limited_semantic_id_cannot_upgrade_strength` mutates the structured
  semantic class while keeping plausible copy;
- `test_may_not_use_for_cannot_become_optional_recommendation`;
- `test_authority_copy_requires_branded_semantic_receipt`;
- `test_semantic_id_has_one_active_copy_per_locale_and_scope`.

The private branded issuer binds a canonical ID, source token, reviewed output,
reviewer identity/version/scope and content hash; it freezes issuance and keeps
identity in a private `WeakSet`. Canonical IDs are the generated contract+field
identity for open `may_not_use_for` values and the catalog key
`phase34.harm.risk.limited` for the closed example—never a string-equivalence
guess. Localized authority copy is issued only with a content-bound competent
external-review receipt. With 0 accepted receipts, the honest presentation is
the English baseline or owner token plus `verification_missing` DS6 debt. A
plausible text edit without a matching receipt fails. The checker validates
identity/hash/reviewer fields; it does not claim to understand Ukrainian.
Two conflicting active copies for the same semantic ID/locale/scope fail even
when both are fluent; identical visible words under two different canonical
IDs are a benign control and are never treated as duplicates by string match.

**Acceptance:** authority copy is issued by canonical semantic identity and
unreviewed localized copy falls back honestly;
the `may_not_use_for` consumer accepts only the branded presentation; the two
strength-upgrade corruptions and the same-ID copy collision fail while the
same-word/different-ID control passes. C05b-R1 claims the mechanical
receipt/issuer gate, not completed human semantic review.

**Expected commit:** `DS5-C05b-R1 anchor authority copy by semantic ID`.

### DS5-C05b-D2 — record-only semantic-copy issuer/panel deferral

**Status:** C05b implementation is **Not yet** and deferred. D2 records only the
typed DS5 `producer_binding_debt`; it does not implement the private issuer,
generated `AvailableGovernedProjectionPacket.may_not_use_for` declaration/runtime
guard, RunExplainabilityPanel consumer, direct-Badge census transition, or DS6 review.

**Measured set:** exactly 7 record paths: disposition checker/test, register/report,
induced DS19 status-hash pin, this plan, and journal. No product, schema, panel,
enforcement, scanner, catalog, DS6, or backend path is in scope.

**Acceptance:** the descriptor-derived row remains `rebind_pending/open_debt` with
the five named missing states; its simple two-test command is nonzero until both
future issuer and panel/census tests execute and pass. Accepted DS6 review receipts
remain 0. **Expected subject:** `DS5-C05b-D2 record semantic-copy deferral`.

### DS5-C05b-R3 — issuer-only recovery from the R2 checkpoint

**Status:** recover the reviewed `ac24327c3` issuer/semantic-ID mechanism as a
forward 13-path cluster. Its earlier breaker was a receipt shorthand naming a
nonexistent closure path, not a mechanism finding. This is established-mechanism
linear sizing, not a bespoke-mechanism cap issue.

**Acceptance:** `AtlasEnforcementTests.test_authority_semantic_copy_registry_rejects_identity_bound_corruptions`
proves the private branded issuer and generated `may_not_use_for` declaration/runtime
guard. The supplemental finding removes only `producer_missing`; it retains
bridge/consumer/verification/semantic-test debt, closes by the future panel-only
direct-Badge census test, and claims neither a panel consumer nor DS6 human review
(accepted receipts remain 0). **Expected subject:** `DS5-C05b-R3 recover semantic-copy issuer guard`.

### DS5 producer-existence entry audit — root finding

DS5 was sequenced as though enforcement could precede its producers. The landed
`a` clusters largely have owner emissions, while `b` clusters and C06 expose
missing producers. This entry audit is the P31 structural repair: enumerate the
whole producer set once before admitting a cluster, rather than stopping one
cluster at a time. P35 applies to every absence/count: it is supported by a
complete command, not a sampled file. A `blocked-on-another-*` verdict may not
be entered; `debt-only` may only register typed debt. `Waits on` names the exact
cluster or external owner-plan that must move before a blocked row is reconsidered.

| Cluster | Deliverable | Producer today | Evidence | Verdict | Waits on |
| --- | --- | --- | --- | --- | --- |
| C07 | audience-permission relation | `intended_audience` projection and all 33 `/auth/me` permissions emit; the mapping is the relation over those owners | `src/polisyos/runtime/http/services/governed_projections.py:36-41,1014-1031,1109-1114`; `src/polisyos/runtime/http/routes/auth.py:59-82`; `src/polisyos/runtime/http/permissions.py:16-51,211-216`; `schemas/runtime_api_v1.openapi.json:/api/v1/auth/me` | executable | none |
| C08a | test-only identity fixture | verified `/auth/me` producer exists; only test fallback import must be isolated | `src/polisyos/runtime/http/routes/auth.py:59-82`; `apps/runtime-dashboard/src/test/render.tsx:7,28` | executable | none |
| C08b-R1 | fail-closed `/auth/me` consumption | runtime response exists and client query consumes it | `src/polisyos/runtime/http/routes/auth.py:59-82`; `apps/runtime-dashboard/src/api/hooks/useAuthMe.ts:42-82` | executable | none |
| C08b-R1 | auth-session revision partition | no relevant identity revision producer in OpenAPI/apps/packages/runtime HTTP | complete absence: `rg -n -i -e 'auth_session_revision' -e 'auth.*session.*revision' -e 'session.*revision.*auth' -e 'identity.*revision' -e 'revision.*identity' schemas/runtime_api_v1.openapi.json apps/runtime-dashboard packages/runtime-api-client src/polisyos/runtime/http --glob '*.{json,ts,tsx,py}'` (0) | debt-only | none |
| C09a-R1 | chrome default deny | requires C08b verified Authz decision; current defaults still allow | `apps/runtime-dashboard/src/app/routes/WorkspaceBoundary.tsx:48-75`; `apps/runtime-dashboard/src/app/layout/Sidebar.tsx:39-46`; `apps/runtime-dashboard/src/app/layout/Header.tsx:1-8`; C08b-R1 table row | blocked-on-another-cluster | C08b-R1 |
| C09b-R1 | mode/run default deny | requires C08b verified Authz decision; current defaults still allow | `apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx:43-99`; `apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx:834`; C08b-R1 table row | blocked-on-another-cluster | C08b-R1 |
| C10-R1 | weakest-boundary presentation | no routed complete G4 producer; C05b implementation debt also remains | `docs/reference/frontend/atlas-frontend-disposition-register.md:221`; C05b-D2 above | blocked-on-another-plan | `team-runtime-quality` G4 projection owner plan |
| C11a | cache-posture observation | the packet supplies `as_of`; live TanStack query lifecycle supplies data/fetch state | `apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts:103-119`; `apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx:399,453` | executable | none |
| C11b-R1 | visible cache posture | depends on C11a typed `CachePosture` artifact | C11a table row; `DS5-C11b-R1` acceptance | blocked-on-another-cluster | C11a |
| C12a | query construction/producer census | 42 current query producers are real census subjects; the register is the new enforcement artifact | complete census: `rg -n --glob '!**/*.test.*' --glob '!**/*.stories.*' --glob '!**/types.ts' '\\bqueryFn\\s*:' apps/runtime-dashboard/src` (42); `DS5-C12a` measured denominator | executable | none |
| C12b-R1 | governed query wrapper/policy | depends on C12a source-bound register and policy classification | C12a table row; `DS5-C12b-R1` acceptance | blocked-on-another-cluster | C12a |
| C13a | delete authority replay | queue writer/replay emits authority mutations today and is deletable | `apps/runtime-dashboard/src/app/offline/offlineQueueRepository.ts:39-61`; `apps/runtime-dashboard/src/app/providers/OfflineQueueProvider.tsx:158-246` | executable | none |
| C13b-R1 | SW sync/flush authority bridge | worker and provider bridge exist today | `apps/runtime-dashboard/src/sw.ts:13-45`; `apps/runtime-dashboard/src/app/providers/OfflineQueueProvider.tsx:114-153` | executable | none |
| C13b-R1 | composer-only typed closure | composer closure needs C14a envelope | `apps/runtime-dashboard/src/app/offline/offlineQueueRepository.ts:39-61`; C14a table row | blocked-on-another-cluster | C14a |
| C14a | nominal envelope owner | no `PersistedEnvelope<StoreClass>` or `authorityLocalState` producer exists | complete absence: `rg -n -e 'PersistedEnvelope' -e 'authorityLocalState' apps/runtime-dashboard packages architecture --glob '*.{ts,tsx,json,toml}'` (0) | debt-only | none |
| C14b-R1 | scoped composer consumer | raw composer record has neither scope nor TTL and needs C14a | `apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts:15-37`; `apps/runtime-dashboard/src/app/offline/offlineQueueRepository.ts:80-85`; C14a table row | blocked-on-another-cluster | C14a |
| C15a | raw Clerk run-status partition | SSE writes `messages[].runStatus`; store persists sessions | `apps/runtime-dashboard/src/features/clerk/hooks/useClerkNlRun.ts:80-101`; `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts:223-228` | executable | none |
| C15a | structured verdict/status-chip partition | no live structured producer exists; DS1 records it as dormant producer-missing substrate | `docs/reference/frontend/atlas-live-application-audit.md:623,868,896` | blocked-on-another-plan | structured verdict/status-chip producer owner plan |
| C15a | identity hydration API | requires verified identity and envelope ownership | C08b-R1 and C14a table rows | blocked-on-another-cluster | C08b-R1, C14a |
| C15b-R1 | mounted Clerk identity bridge | requires C15a codec and C08b verified identity | C15a and C08b-R1 table rows | blocked-on-another-cluster | C15a, C08b-R1 |
| C16a-R1 | causal-draft partition | live raw local-storage writer exists; DS8 semantics are untouched | `apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx:301-310,444` | executable | none |
| C16b-R1 | dispute-interaction partition | live raw local-storage writer exists; DS9 semantics are untouched | `apps/runtime-dashboard/src/features/runs/domain/disputes.ts:109-130`; `apps/runtime-dashboard/src/features/runs/components/DisputeRegistryPanel.tsx:90-103` | executable | none |
| C17a-R1 | storage-family partition | four typed raw-local-storage families emit today | `apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts:444-490,504-570,647-657,735-816` | executable | none |
| C17a-R1 | root disposition transition | DS14 plan versus DS9 register ownership conflict remains | `DS5-C17a-R1` acceptance; `docs/reference/frontend/atlas-frontend-disposition-register.md:536,539-542` | blocked-on-another-plan | DS14/DS9 owner-resolution plan |
| C17b-R1 | persistence construction census | real persistence construction calls emit bytes; lint/census governs them | `apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts:488,570-573,652-655,689,775,814`; `DS5-C17b-R1` measured denominator | executable | none |
| C18a | strict exposure registry | `resolveFeatureFlags` and defaults emit typed `FeatureFlags`, though permissively | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts:97-110,290-297` | executable | none |
| C18b-R1 | contextual flag source binding | provider emits merged flags and cached manifest today | `apps/runtime-dashboard/src/app/providers/FeatureFlagProvider.tsx:37-55,68-131` | executable | none |
| C19-R1 | three flag gates and collaboration retirement | flag producers and scenario-capability route/hooks exist; causal graph, palette, WhatIf, and retirement are executable subrows | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts:97-110,290-297`; `apps/runtime-dashboard/src/app/providers/FeatureFlagProvider.tsx:37-145`; `apps/runtime-dashboard/src/features/runs/route.tsx:184-236` | executable | none |
| C20 | generated frontend reference | registered frontend reference writer exists today | `architecture/atlas_surfaces/check_frontend_disposition_register.py:6656-6657`; `docs/reference/frontend/atlas-frontend-disposition-register.md` | executable | none |
| C20 | final ledger/corruption/architect receipt | requires closure of executable/debt clusters first | `DS5-C20` acceptance; all preceding blocked/debt rows | blocked-on-another-cluster | all preceding executable/debt clusters |

### DS5-C06 — three waist contracts, one regeneration, one re-anchor

**C06-D1 disposition: debt-only, seven paths.** The entry audit proved there
is no executable generated-waist remainder: CGF has a private validator set
but no public typed owner; `DecisionGrade` is assigned to C14 in the DS4 waist
register; and client cache posture belongs to C11a/C11b QueryObserver lifecycle,
not source-observation `ProjectionFreshness`. C06-D1 adds three independent
descriptor-derived producer debts, their report, the induced DS19 hash-only
re-anchor, compact corruption witnesses, this section, and the journal. It
does not regenerate, edit an adapter, publish G4, or transition the existing
DS4 bridge/surface rows.

**Red first:** `ProducerBindingDebtTests.test_c06_waist_owner_debts_bind_three_independent_planes`
fails while each descriptor row is absent, then proves corrupt, remove, and
reclassify mutations fail independently while an existing descriptor remains
benign. Each successor uses the established named-unittest-plus-condition
closure idiom and is nonzero until its absent future test exists.

**Acceptance:** exactly three supplemental producer debts:
`c06-cgf-public-vocabulary-producer-debt` (unresolved canonical owner),
`c06-decision-grade-generated-contract-debt` (C14), and
`c06-queryobserver-cache-posture-artifact-debt` (C11a/C11b). Their capability
states and successor contracts state the missing plane without claiming that
the DS4 rows, G4 projection, runtime contract, generated client, or cache
artifact exists. The current measured 24-path implementation narrative below
is superseded historical planning, not C06-D1 scope.

**Expected forward commit:** `DS5-C06-D1 record waist producer debts`.

**Measured set:** exactly 23 implementation/governed paths plus journal = 24;
cap 26:
`services/governed_projections.py` and
`services/governed_projection_validation_worker.py`; the mirrored governed-projection service and
runtime-contract-hardening tests; generated OpenAPI snapshot; package
`types.ts`, `runtimeApiClient.{ts,js}` and
`canonicalRuntimeApiClient.{ts,js}`; dashboard `src/api/types.ts`; three swap
modules + three tests; the waist
register; and status inventory/checker/test plus disposition register and its
generated report. The generic disposition checker/probes and the package's
hand-authored type test are reused byte-unmodified. Alongside the three waist unions, this cluster projects
the existing canonical
`architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json`
owner artifact as one typed governed-projection packet. No owner computation,
waist schema copy or decision-grade consumer is edited.

The new complete G4 packet is explicitly `EXPERT`. Its owner public-export
reference admits rich internal references for EXPERT and MACHINE, while its
PUBLIC/REVIEWER projections are reduced; the complete artifact carries
`produced_by` input hashes/reducer provenance and `promotion_scope` that C06
must not silently strip or expose as a reduced projection. The first consumer
is the human expert run surface, so MACHINE is not selected by default. This
source/use-bound choice changes the post-C06 definition census to
14 = 6 EXPERT + 8 MACHINE, with 0 PUBLIC and 0 REVIEWER definitions.

**Red first:**

- `test_generated_cgf_disposition_union_rejects_renamed_or_reordered_owner_values`;
- `test_generated_decision_grade_union_tracks_pdc_owner`;
- `test_generated_cache_age_union_keeps_source_freshness_orthogonal`;
- `test_generated_g4_packet_preserves_owner_weakest_boundary_and_veto`;
- `test_g4_projection_audience_is_source_bound_and_census_exact`;
- the existing novel-owner and no-value-export negatives for all three adapters;
- `test_reanchor_stops_on_changed_symbol_or_field`.

**Acceptance:** the owner contracts produce closed unions through OpenAPI and
the generated client; adapters use exhaustive generated-type-bound switches
and return explicit `unrecognized` for runtime novel labels without exporting
constants. The G4 packet is validated by the existing isolated owner-validation
worker, content-bound to the canonical artifact, and carries the complete
owner-composed weakest-boundary/veto result; the browser receives no rank or
meet function. Type erasure is not presented as runtime validation. Terminal kinds
and evidence classes remain opaque. Every governed `export_symbol` still occurs
once and every symbol/field tuple is unchanged. Generated aliases sort
alphabetically, so each tuple requires its own accounted baseline-to-generated
line delta; any unaccounted drift stops the cluster. Two client hashes refresh,
surgical JSON diffs preserve unrelated bytes, and both corruption batteries pass.
The definition census is re-derived from `_DEFINITIONS` and must be exactly
14/6/8 after the addition; a different audience or a second unmeasured
definition is red.

The snapshot is produced only by the registered `runtime-openapi-snapshot`
`regenerate_commands` entry. Package output then comes only from
`corepack pnpm --dir packages/runtime-api-client run generate`, and dashboard
API types from their registered generator. No generated-client package file is
hand-edited.

**Expected commit:** `DS5-C06 bridge the three canonical waist unions`.

### DS5-C07 — one server audience-permission mapping

**Measured set:** exactly 24 implementation/governed paths plus journal = 25;
cap 26: four HTTP source files (new
`audience_permissions.py`, `authorization.py`, governed service and route);
the five fence-listed HTTP/contract tests; generated OpenAPI snapshot; package
`types.ts`, `runtimeApiClient.{ts,js}` and
`canonicalRuntimeApiClient.{ts,js}` plus dashboard `src/api/types.ts`; and eight
governed receipt/re-anchor files
(waist register; status inventory/checker/test; disposition
register/checker/test plus its generated report). Audience schema, generated client, mapping, route
enforcement, consumer contract and re-anchors land together; no contract-only
cluster boundary is allowed. The single authored direction is
`RuntimePermission -> frozenset[AudienceClass]`; the inverse is derived. Every
one of the 33 values appears exactly once. Current inverse counts are PUBLIC 0,
REVIEWER 20, EXPERT 28, MACHINE 22.

| Eligible audiences | Exact server-owned permissions |
| --- | --- |
| REVIEWER, EXPERT, MACHINE | `artifacts.batch.read`, `artifacts.render`, `evidence.view`, `fabric.quality.read`, `fabric.trust.read`, `knowledge.search`, `knowledge.view`, `lineage.batch.read`, `platform.view`, `runs.batch.read`, `runs.view` |
| REVIEWER, EXPERT | `dashboard.view`, `evidence.acquire`, `evidence.review`, `runs.review` |
| EXPERT, MACHINE | `analysis.execute`, `evidence.discover`, `evidence.preview`, `evidence.resolve`, `evidence.sae.analyze`, `fabric.impact.analyze`, `knowledge.trigger`, `mobility.analyze`, `platform.admin`, `runs.feedback.evaluate`, `runs.launch` |
| REVIEWER | `decisions.validity.publish`, `evidence.promotions.approve`, `evidence.promotions.reject`, `runs.production_approval.create`, `runs.reissue` |
| EXPERT | `mode.analyst`, `scenarios.create` |
| PUBLIC | no privileged permission; this does not create an anonymous route |

At C07 entry the audience census is 6 EXPERT projections, including G4, and 8
MACHINE projections. C07 assigns exact `mode.analyst` to all 6 EXPERT
definitions and exact `platform.view` to all 8 MACHINE definitions.
`AudienceClass` gains PUBLIC in this
cluster. PUBLIC and REVIEWER construction and deny behavior are exercised
through the same real dependency, but no current producer projection is
relabeled merely to populate those classes and PUBLIC does not enter the
anonymous allowlist.

**Red first:**
`test_each_nonpublic_projection_requirement_denies_all_other_32_permissions`
and `test_public_audience_denies_all_33_privileged_permissions`. Audience is a
server-declared surface contract, not a principal identity or hierarchy. The
exact declared grant admits regardless of coarse role label; all other 32
grants without it deny. PUBLIC has no privileged grant and all 33 values deny;
DS5 does not invent an anonymous positive route to make the matrix look full.
A permissionless principal cannot fetch any current privileged projection.
Direct URL, coarse role, client header and UI-hidden variants exercise the
server path. A source-derived corruption witness rejects any DS20 high-stakes
permission classified for MACHINE. The G4 case explicitly denies
`platform.view`, `runs.view`, `artifacts.render`, and every other grant without
`mode.analyst`, and permits only the exact expert requirement.

**Acceptance:** one immutable mapping is imported by one real route dependency;
REVIEWER, EXPERT and MACHINE have exact-grant allow and wrong-grant deny
witnesses, while PUBLIC proves the empty mapping and 33/33 privileged denials;
a route requires its exact declared permission, never merely any permission
eligible for an audience; mapping coverage is generic over all 33 enum members;
projection producer audiences are not relabeled; all six source-derived
high-stakes permissions exclude MACHINE; generated symbols/fields are
re-anchored under the same unchanged tuple/per-symbol-per-field line-delta
rule, with any unaccounted drift a STOP; the UI is not
part of the allow decision. Regeneration repeats the same registered exporter
and generated-output commands as C06; no generated-client package file is
hand-edited.

**Expected commit:** `DS5-C07 enforce audience permission boundaries`.

### DS5-C08a — sever test support from production fallback identity

**Measured set:** exactly 4 implementation/test paths plus journal = 5; cap 5:
new `src/test/fixtures/authMe.ts`, `useAuthMe.test.tsx`, shared
`src/test/render.tsx`, the Platform Health story, and journal.

**Red first:** `test_support_never_imports_production_fallback_identity`.
The test harness and story fail until they use an explicit test-only generated-
shape fixture; a fixture can seed tests but is rejected as product identity.

**Acceptance:** no test/story helper depends on `FALLBACK_AUTH_ME`; production
still behaves byte-identically until C08b-R1. This removes the compile-time tail
that would otherwise force C08b-R1 over its cap.

**Expected commit:** `DS5-C08a isolate auth test identity fixtures`.

### DS5-C08b-R1 — N010 fail-closed client identity

**Measured set:** exactly 10 implementation/governed paths plus journal = 11;
cap 11: `api/queryKeys.ts`, `useAuthMe.ts` + test, `AuthzProvider.tsx` + new
test, `app/authz/permissions.ts` + new test, frontend disposition register +
generated report, `architecture/atlas_surfaces/status-retirement-inventory.json`,
and journal. Six downstream production consumers contain 11 default-allow
expressions and remain the separately sized C09a-R1/C09b-R1 boundary.

**Red first:**
`test_authz_provider_denies_loading_error_malformed_401_prior_user_and_tenant_switch_identity`.
It asserts no permission, MFA, collaboration pseudo-flag, or high-stakes CTA.

**Acceptance:** no production `FALLBACK_AUTH_ME`, no infinite-stale identity,
no placeholder grant; query identity partitions by verified auth-session
revision; unknown identity is explicit and empty; dashboard permissions import
the generated 33-value type and the three collaboration literals disappear.
DS20 server identity is consumed, not reimplemented.

**Expected commit:** `DS5-C08b-R1 fail closed on unknown identity`.

### DS5-C09a-R1 — N010 default deny in application chrome

**Measured set:** exactly 10 implementation/governed paths plus journal = 11;
cap 11: `WorkspaceBoundary.tsx`, `Sidebar.tsx`, `Header.tsx`, one new cross-
surface behavioral test, shared C01a scanner/checker/test, frontend disposition
register + generated report, `architecture/atlas_surfaces/status-retirement-inventory.json`,
and journal.

**Red first:** `test_unknown_authz_decision_never_defaults_authority_surface_to_allow`.
Loading, absent provider, error, cached-prior-user and tenant-switch variants
cover every expression in these three consumers; a genuinely permission-free
fixed PUBLIC chrome element is the benign control.

**Acceptance:** one explicit `unknown | verified` Authz state yields a branded
decision only from current verified identity; unknown/deny is not allow.
Permission-free fixed chrome stays visible; all permission-bearing chrome in
this half requires the verified branch. A bounded AST
rule rejects direct `?? true` and conditional-true defaults only in imports of
the decision API; it does not infer equivalent arbitrary program behavior.

**Expected commit:** `DS5-C09a-R1 default deny application chrome`.

### DS5-C09b-R1 — N010 default deny in modes and run surfaces

**Measured set:** exactly 7 implementation/governed paths plus journal = 8;
cap 8: `InterfaceModeProvider.tsx`, `CommandPalette.tsx`,
`RunDetailLayout.tsx`, the C09a-R1-C09b-R1 cross-surface behavioral test,
frontend disposition register + generated report,
`architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.

**Red first:** extend
`test_unknown_authz_decision_never_defaults_authority_surface_to_allow` over
the remaining direct-mode, keyboard and run-route expressions. A fixed
permission-free run chrome control remains visible.

**Acceptance:** all 11 original default-allow expressions across C09a-R1-C09b-R1
commits now require current verified identity; the existing bounded syntax gate
automatically covers the latter importers. No permission-bearing mode, command
or run surface treats unknown as allow; register/report evidence lands with the
three consumers.

**Expected commit:** `DS5-C09b-R1 default deny modes and run surfaces`.

### DS5-C10-R1 — owner-composed weakest-boundary presentation

**Disposition: DEFERRED.** This successor remains deferred and is not
authorized for execution. Its supplemental finding is
`g4-complete-audience-projection-contract`; the contract below remains a
minimum owner-integrate pointer, not a DS5 implementation authorization.

**Ruling re-derivation:** the C06 generated DTO is structural and is not itself
the nominal boundary. C10-R1 extends the existing private-symbol/private-issuer
pattern at the first live client boundary after
`RuntimeApiClient.getGovernedProjection`; it does not export a constructor,
packet type, packet value or selector and does not search source for arithmetic
names. One `G4WeakestBoundaryPresentation.tsx` module owns the live request,
module-private symbol, validator/issuer, WeakSet identity and specialized sink.
Its public component accepts only the run/current-identity inputs—not a packet.
The private adapter checks the exact G4 projection identity, availability
discriminant, source validation, hashes/provenance and the actual complete G4
owner fields (`blocker_refs`, `limitation_refs`, `issue_codes`,
`promotion_scope`, `promotion_state`, `status`, `weakest_boundary_reason`,
`produced_by`) before
issuing a frozen nominal packet to its module-private sink. The generated
projection envelope's separate `may_not_use_for` list remains an explicit
rights-bar veto. It is rendered only by importing the C05b-R1
`AuthoritySemanticCopy` issuer/brand; C10-R1 owns no copy table, fallback string or
parallel semantic issuer and does not invent a `rights_bar` field in the G4 artifact. A
runtime-novel owner status remains explicit
`unrecognized` rather than being silently coerced.

**Measured set:** exactly 7 implementation/governed paths plus journal = 8;
cap 8: new `G4WeakestBoundaryPresentation.tsx` + test; `OverviewTab.tsx` + the
existing `runDetailSurfaces.test.tsx`; frontend disposition register + generated
report; `architecture/atlas_surfaces/status-retirement-inventory.json`; and
journal. C06 supplies the generated G4 DTO. The C01b checker already
derives branded issuer modules from the governed census; the new row brings this
module under that gate without editing the checker. The module deliberately has no TanStack
`useQuery`, `queryOptions`, `queryFn`, query key, local store or persistent
cache, so it does not change the 42-producer C11a-C12b-R1 denominator.

**Red first:** `test_weakest_boundary_presentation_requires_complete_generated_g4_packet`.
The DS5 diagnostics harness proves a complete structural lookalike and one-lane
object cannot occupy the module-private nominal sink without an escape hatch.
Runtime corruptions omit each actual G4 field in turn, explicitly including
`promotion_scope`, or corrupt its owner value; omitting envelope
`may_not_use_for` or a provenance/hash field must also fail before issuance. A
focused live-wiring test proves the
component obtains data only through the canonical generated client call. Prior-
identity, prior-run, superseded-attempt, offline and failed-refetch responses
must withhold the packet immediately. Response `as_of` and
`freshness.basis` are visible on success; `filesystem_mtime` is labeled as a
snapshot observation and never upgraded to owner time. A
runtime-novel status reaches the private sink as `unrecognized`. Duration
averages, chart layout and non-authority numeric reductions remain benign
because C10-R1 does not lint arithmetic identifiers.

**Acceptance:** only the module-private canonical live adapter can issue or
consume the nominal owner-validated G4 packet; its type, symbol, constructor,
value and mutable backing object never cross the module boundary. The public
component derives availability from `{run, verified identity revision, online,
current attempt}` and never renders a retained prior packet by presence.
Complete structural DTOs remain non-assignable to the private sink, and C01b's
bounded escape rule covers the issuer module. Novel owner status is explicit
`unrecognized`; `blocker_refs` and envelope `may_not_use_for` remain visible,
non-compensable vetoes. The wiring test asserts the rights-bar rendering accepts
only C05b-issued `AuthoritySemanticCopy`, and the disposition/report append this
second consumer without changing the residual DS6 `verification_missing` state.
This establishes request-scoped nominal consumption of one
owner-composed result; it makes no claim that client arithmetic was universally
detected. C11a-C12b-R1 continue to govern the unchanged 42 actual TanStack query
producers.

**Deferred expected commit:** `DS5-C10-R1 present owner-composed weakest boundary` (not authorized).

### DS5-C11a — derive cache posture from one real query observation

**Measured set:** exactly 4 implementation paths plus journal = 5; cap 5:
`src/api/cacheDiscipline.ts` + test,
`useDepthNCycleBoardProjection.ts` + test, and journal. The OpenAPI/generated
union and cache-age adapter land in C06. This is the only current query producer
whose payload carries owner `packet.as_of + freshness`.

**Red first:**

- `classifies_preexisting_query_data_as_cached_with_owner_as_of`;
- `marks_retained_stale_data_without_consulting_source_timestamps`;
- `refuses_cached_posture_without_owner_as_of`.

The observation uses QueryObserver lifecycle (`data present`,
`isFetchedAfterMount`, explicit `isStale`, `fetchStatus`). It never compares
payload/source timestamps (`as_of`, `observed_at`, `source_as_of`,
`dataUpdatedAt`, or `ApiMeta.generated_at`) to infer cache age. `isStale` may
carry TanStack's configured lifecycle result; the client does not reconstruct
it from timestamps. Cache state and source freshness remain orthogonal.

**Acceptance:** the live hook emits a typed
`live | cached | stale | unrecognized` observation from the real query lifecycle
plus owner `as_of`; missing owner time is unrecognized/blocked. C11a does not
yet claim a visible presentation.

**Expected commit:** `DS5-C11a derive governed cache posture`.

### DS5-C11b-R1 — render cache posture in the live run surface

**Measured set:** exactly 9 implementation/governed paths plus journal = 10;
cap 10: `TimeSemanticsLabel.tsx` + test, `RunExplainabilityPanel.tsx` + its
governed-projection test, `OverviewTab.tsx` + `runDetailSurfaces.test.tsx`,
frontend disposition register + generated report,
`architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.
`TimeSemanticsLabel` currently renders twice and receives no `cacheAgeLabel`.

**Red first:** `test_migrated_governed_query_never_emits_offline_queued` plus live
surface variants for preexisting cache, stale, missing-`as_of`, novel union and
failed refetch.

**Acceptance:** the real governed consumer visibly renders live/cached/stale
with owner `as_of`; missing `as_of` is explicit unrecognized/blocked; novel
union values stay unrecognized; the migrated governed consumer never renders
`offline_queued`. Register/report transition only after `OverviewTab` passes the
typed observation into the panel.

**Expected commit:** `DS5-C11b-R1 render governed cache posture`.

### DS5-C12a — source-bind query constructions and producers

**Measured set:** exactly 6 implementation/governed paths plus journal = 7;
cap 7: `status_retirement_scan.mjs`, the C01a DS5 checker/test,
`query-cache-policy-register.json` + schema, dashboard `package.json`, and
journal. Current denominators are 43 canonical query-key constructors, 66
direct `useQuery`/`queryOptions` construction calls / 40 files, and 42
`queryFn` producers / 39 files.

**Red first:**
`test_query_construction_and_producer_censuses_are_source_complete`.
Independent corruptions add a 67th `useQuery(existingOptions)` call without a
new `queryFn`, add a 43rd `queryFn`, move/mutate a legacy site, or omit the
producer contract/owner field/owner slice/closure signal. A local function named
`useQuery` and a registered operational counter are benign symbol-resolved
controls.

The register holds two independent source-bound tables—66 construction calls
and 42 producer definitions—rather than pretending to infer which arbitrary
options value reaches which call. Construction rows carry resolved callee,
path/fingerprint and `governed_wrapper | legacy_direct_debt`; producer rows
add query-key owner, exact DTO contract, required owner `as_of`, owner slice,
capability states and executable closure. One C11a construction/producer is the
migration target; 65 calls and 41 producers remain fingerprint-bound debt unless
independent contract evidence proves an operational class.

**Acceptance:** omissions, new/moved/changed calls or producers, stale
fingerprints and unbuildable integrate-contracts fail. Existing legacy rows are
a debt ratchet, not an untyped allowlist. C12a makes no cache-policy runtime
claim and edits none of the 40 call-site files.

**Expected commit:** `DS5-C12a register query construction debt`.

### DS5-C12b-R1 — make the governed query path unrepresentable

**Measured set:** exactly 9 implementation/governed paths plus journal = 10;
cap 10: new `governedQueryPolicy.ts` + test,
`useDepthNCycleBoardProjection.ts` + test, the shared DS5 enforcement test
established in C01a,
query-cache policy register, frontend disposition register + generated report,
`architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.

**Red first:** `test_governed_query_wrapper_forbids_retained_authority_without_owner_as_of`.
Builder corruptions derive posture from request time or pin authority data with
`placeholderData`, `initialData` or infinite stale time; offline/failed refetch
must remove a `never_cache_authority` payload through a real QueryClient. A
typed operational query is the benign control.

**Acceptance:** the wrapper owns the sole registered governed direct
`useQuery` call; new/migrated consumers cannot call raw `useQuery` and must pass
the discriminated policy. Only owner-`as_of` policy may retain authority data;
`never_cache_authority` proves `gcTime: 0`, no placeholder/initial data and
removal on offline/failed refetch. The source tables remain 66 calls/42
producers with one governed wrapper/producer and 65/41 exact legacy debts.
`ApiMeta.generated_at` is never owner time. No claim is made that legacy sites
were migrated or semantically inferred.

**Expected commit:** `DS5-C12b-R1 enforce governed query policy`.

### DS5-C13a — delete authority mutation replay

**Measured set:** exactly 17 implementation/governed path names plus journal =
18; cap 18: `app/offline/db.ts`, `offlineQueueRepository.ts`, deleted
`OfflineQueueProvider.tsx`, `AppProviders.tsx`;
`useQueuedPromotionDecision.ts` renamed to `useLivePromotionDecision.ts` and
its test renamed likewise; `DataIntelligencePanel.tsx` + test; shared DS5 AST
scanner/checker/test; status inventory; dashboard `src/README.md`; frontend
disposition register + generated report; and journal. C13a leaves the now composer-only repository at
its old filename so its importer/test stay green inside the cap. The only entry
queue kinds are `promotion.approve` and `promotion.reject`.

**Red first:**
`test_offline_retryable_promotion_never_queues_terminalizes_or_replays` and
`test_offline_queue_type_rejects_authority_action_kind`. Offline, 408, 429 and
5xx variants cover both current decisions; synthetic publication/reissue/
approval kinds fail the composer-only queue type and direct queue-import rule.
A composer draft is the benign persistence counterexample.

**Acceptance:** the DB version removes the legacy queue store; no queue reader,
writer or replay provider survives; no IndexedDB mutation row and no optimistic
approved/rejected state remain. Retry is an explicit live action through current
server identity, permission, step-up, tenant and producer-state enforcement and
renders denial. Both deleted status definitions retire surgically; the queue
disposition/report transitions; composer persistence remains. C13b-R1 owns SW
proof and naming cleanup. The README removes the deleted provider/mount claim in
this commit, so no stale reference crosses the boundary.

**Expected commit:** `DS5-C13a delete authority mutation replay`.

### DS5-C13b-R1 — prove service-worker and composer-only closure

**Measured set:** exactly 9 implementation/governed path names plus journal =
10; cap 10: rename `offlineQueueRepository.ts` to `composerDraftDb.ts` (two path
names), `composerDraftRepository.ts` + its existing test, `sw.ts` + a new
focused SW test, frontend disposition register + generated
report, `architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.

**Red first:**
`test_service_worker_has_no_authority_sync_or_authenticated_api_cache` plus a
direct import of the renamed composer DB from an authority-mutation module.

**Acceptance:** no queue-named module/API remains; composer repository/test use
the discriminated composer-only DB. The real worker path proves authenticated
API requests are never cached and no authority background-sync registration or
message bridge exists; versioned static-shell caching is benign. Visibility/
online events cannot resurrect mutation replay. Epoch/rule revalidation remains
a DS18 integrate-contract unless the producer carries it. SW/composer
disposition and generated report land together.

**Expected commit:** `DS5-C13b-R1 close service worker and composer DB`.

### DS5-C14a — nominal local-state envelope owner

**Measured set:** exactly 2 implementation paths plus journal = 3; cap 3:
`app/offline/authorityLocalState.ts` + test and journal.

**Red first:** `test_raw_local_state_envelope_cannot_be_issued_or_written`.
Structural lookalikes, absent identity, malformed scope and expired envelopes
fail; a same-scope interaction payload is the benign control.

**Acceptance:** physical key and strict envelope both content-bind family,
tenant and user; writer-owned TTL is checked against an injected clock; absent
identity fails closed; no legacy byte is silently migrated into authority.
`authorityLocalState.ts` owns a module-private symbol and issuer for frozen
`PersistedEnvelope<StoreClass>` values; callers cannot write raw structural
envelopes. Each registered family supplies a concrete typed encode/decode codec,
not a generic `unknown`/`JsonValue` serializer. This makes the registered write
boundary nominal while leaving semantic classification to source-bound rows.

**Expected commit:** `DS5-C14a own nominal local state envelope`.

### DS5-C14b-R1 — bind the composer consumer

**Measured set:** exactly 7 implementation/governed paths plus journal = 8;
cap 8: `composerDraftRepository.ts` + test, `ComposerModeSections.tsx`,
`LaunchRunPage.test.tsx`, frontend disposition register + generated report,
`architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.
C08b-R1 verified tenant/user identity is a dependency.

**Red first:** `test_composer_draft_cannot_cross_tenant_user_or_expiry`.
Legacy unwrapped, malformed, expired, prior-tenant and prior-user bytes never
hydrate. A same-scope non-authority draft is the positive control.

**Acceptance:** composer uses the C14a envelope/codec owner; physical key and
envelope bind family, tenant, user and expiry; no legacy byte silently migrates.
`offline-draft-composer` gains a complete isolation consumer while
`cache-local-storage-state` stays pending until C17b-R1.

**Expected commit:** `DS5-C14b-R1 bind composer local state`.

### DS5-C15a — Clerk persisted codec and identity API

**Measured set:** exactly 2 implementation paths plus journal = 3; cap 3:
`useChatStore.ts`, its test, and journal.

**Red first:** `test_clerk_session_clears_before_cross_identity_rehydrate` and
`test_clerk_persisted_codec_excludes_authority_status_fields`.

**Acceptance:** Zustand storage is identity-keyed, expiry-checked and
`skipHydration`; identity change clears in-memory sessions before rehydrate;
live streaming state is never persisted. The concrete persisted-session codec
excludes all three measured authority-like paths:
`messages[].runStatus`, `messages[].structured.verdict`, and
`messages[].structured.statusChips[]`; hydration must reacquire them from live
state rather than trust stored presence. C15a exports only the typed current-
identity hydration bridge consumed next.

**Expected commit:** `DS5-C15a partition Clerk session codec`.

### DS5-C15b-R1 — mount the Clerk identity bridge

**Measured set:** exactly 5 implementation/governed paths plus journal = 6;
cap 6: `ClerkChatPage.tsx` + new focused test, frontend disposition register +
generated report, `architecture/atlas_surfaces/status-retirement-inventory.json`,
and journal.

**Red first:** `test_clerk_page_binds_current_identity_before_hydration` covers
absent, changed tenant, changed user and expired bytes; no page render observes
prior in-memory sessions.

**Acceptance:** the page is the single identity/scope bridge and calls the
C15a API before hydration. The `cache-clerk-sessions` domain row
remains DS14 `rebind_pending`; DS5 attaches isolation evidence only.

**Expected commit:** `DS5-C15b-R1 mount Clerk identity hydration`.

### DS5-C16a-R1 — causal draft local state

**Measured set:** exactly 5 implementation/governed paths plus journal = 6;
cap 6: `CausalTab.tsx` + test, frontend disposition register + generated
report, `architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.

**Red first:** `test_causal_state_rejects_cross_scope_stale_and_stored_status`.

**Acceptance:** explicit scope enters the shared adapter; causal storage stays
candidate/unidentified and its concrete codec excludes
`graph.edges[].status`, recreating only the interaction-only `unidentified`
display on hydration. The DS8 domain row remains `rebind_pending` with
partition successor evidence.

**Expected commit:** `DS5-C16a-R1 partition causal draft state`.

### DS5-C16b-R1 — dispute interaction local state

**Measured set:** exactly 7 implementation/governed paths plus journal = 8;
cap 8: dispute domain + test, `DisputeRegistryPanel.tsx` + a new focused panel
test, frontend disposition register + generated report,
`architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.

**Red first:** `test_dispute_state_rejects_cross_scope_and_stale_bytes`.

**Acceptance:** dispute persistence serializes its existing branded
`InteractionState` label as interaction-only and cannot feed an authority
presentation slot. The DS9 domain row remains `rebind_pending` with partition
successor evidence.

**Expected commit:** `DS5-C16b-R1 partition dispute interaction state`.

### DS5-C17a-R1 — operator-craft family partition

**Measured set:** exactly 9 implementation/governed paths plus journal = 10;
cap 10: `operatorCraft.ts` + test, `OperatorCraftPanel.tsx`,
`AmbientTelemetryHud.tsx`, the C14a `authorityLocalState.ts` owner + test,
frontend disposition register + generated report,
`architecture/atlas_surfaces/status-retirement-inventory.json`, and journal. Operator craft
is one DS1 unit with four physical families: threshold, annotations, evidence
wallet, and onboarding.

**Red first:** `test_all_operator_craft_families_bind_scope_and_expiry`.
Legacy, malformed, expired, prior-user and prior-tenant bytes fail for every
family; a locale/theme preference is outside this adapter.

**Acceptance:** all four operator families use the nominal scoped envelope and
concrete codecs, binding tenant/user/expiry. Panels consume only hydrated
current-scope state. Domain ownership remains DS14; DS5 attaches isolation
evidence/report without claiming operator semantics rebound.

**Expected commit:** `DS5-C17a-R1 partition operator craft state`.

### DS5-C17b-R1 — source-bind persistence construction and reconcile stores

**Measured set:** exactly 9 governed/checker paths plus journal = 10; cap 10:
shared DS5 TypeScript AST scanner/checker/test, disposition
register/schema/checker/test + generated report,
`architecture/atlas_surfaces/status-retirement-inventory.json`, and journal.
C17b-R1 records the
existing WhatIf deletion and a fresh zero-path/zero-import census for the
DS4-deleted review-attention unit. The measured C00 persistence API universe is
41 declaration-resolved lifecycle/construction sites / 14 production files: 23
Web Storage, 5 Zustand and 13 IndexedDB. C17b-R1 reruns the identical census at its
clean post-C17a-R1 boundary and records the exact source-derived delta before a
negative; a new authority family or edit need outside these governed paths
triggers the sizing stop.

**Red first:**
`test_persistence_construction_census_is_source_complete_and_scoped` covers a
synthetic reintroduced unpartitioned review-attention store; a
direct persistence call absent from the census; a moved fingerprint; and a raw
structural envelope. The wave gate reruns C13a/C15a/C16a-R1 corruption tests for
all six measured status paths. A real `Set.add` lookalike and locale/theme/UI
preference sites are benign symbol-resolved controls.

**Acceptance:** the AST rule resolves real `Storage`, Zustand middleware and
`idb` declarations and requires every current API site to have one content-
bound `storage_construction_census` row. Authority-like rows must call the
private scoped-envelope/registered-codec owner; exact interaction-preference
rows may remain direct, fingerprint-bound benign controls. A new/moved/
unclassified site or authority row outside the adapter fails. The checker does
not infer semantic class; a governed row is explicit adjudication, and source
change forces review. Each row carries stable site ID, path, resolved API
declaration, operation, family/store owner, source fingerprint and
`scoped_authority | interaction_benign | rollout_cache_pending` class. Debt
classes require owner slice, capability states and executable closure signal;
benign rows forbid debt fields.

The current authority-like living denominator is 8 physical families: Clerk,
causal, dispute, composer and four operator keys.
`cache-local-storage-state` transitions only for this bounded adapter/census;
feature rows remain DS8/DS9/DS14. Review-attention becomes
`deleted/strangled` with DS4 commit `bc1d01001` plus fresh census; N015 is at
most `partially_reduced` without live server revalidation. The six known status
paths are closed by C13a/C15a/C16a-R1; dispute status is nominal
`InteractionState`. Nominal authority presentations cannot satisfy registered
codec inputs. Unbranded semantic equivalents remain C01a owner debt, not a
universal storage-flow claim.

**Expected commit:** `DS5-C17b-R1 govern persistence construction`.

### DS5-C18a — strict D5 exposure registry

**Measured set:** exactly 2 implementation paths plus journal = 3; cap 3:
feature-flag registry/test and journal. There are 12 current keys and four
missing consumers. Provider wiring and governed row transitions are isolated in
C18b-R1 so neither child exceeds the binding C00 cap.

**Red first:** `test_strict_flag_registry_rejects_unknown_or_wrong_type_input`.
Parser inputs model remote, window, props, cache and environment variants,
including an old schema and the auth pseudo-flag; C18a does not yet claim those
live sources are wired.

**Acceptance:** one strict schema rejects unknown keys and wrong types with a
typed diagnostic and refuses partial merge; the registry API accepts only typed
rollout state and cannot accept RuntimePermission. This closes the pure
registry/validator unit only. Live source binding, observable provider
diagnostics and version/expiry/scope cache behavior remain explicitly
`consumer_missing` until C18b-R1.

**Expected commit:** `DS5-C18a make flag exposure registry strict`.

### DS5-C18b-R1 — bind every flag source to the strict registry

**Measured set:** exactly 5 implementation/governed paths plus journal = 6;
cap 6: feature-flag provider + test, frontend disposition register + generated
reference report, `architecture/atlas_surfaces/status-retirement-inventory.json`,
and journal.

**Red first:** `test_every_flag_source_uses_strict_registry_and_scoped_cache`.
Remote, window, props, cache and environment sources must all enter through the
C18a parser; a direct partial merge, stale cache, cross-scope cache or unknown
source key fails. A current-scope, unexpired, version-matched registry payload is
the benign control.

**Acceptance:** every live flag source feeds the strict C18a registry; the
provider exposes only the parsed typed state and an observable invalid-source
diagnostic; the cache is version/tenant/user/expiry bound. The four
`consumer_missing` disposition rows remain open until C19-R1, but their producer
and strict-consumer evidence plus the generated report land here.

**Expected commit:** `DS5-C18b-R1 bind flag sources to strict registry`.

### DS5-C19-R1 — wire three flags and retire collaboration

**Measured set:** exactly 13 implementation/governed paths plus journal = 14;
cap 14: `AppShell.tsx` +
`layoutSurfaces.test.tsx`; `surfaceRegistry.ts`; `features/runs/route.tsx` +
`runDetailSurfaces.test.tsx`; `OverviewTab.tsx`; command palette + test; flag
registry + test; frontend disposition register + generated reference report;
and `architecture/atlas_surfaces/status-retirement-inventory.json`. The generic disposition checker and corruption probes are reused
byte-unmodified. The run-detail test is
the registry and direct-route negative, so `surfaceRegistry.test.ts` is not a
second edited proof. The surviving server-backed WhatIf workbench remains five
files and has one Overview consumer; no local WhatIf store returns.

**Red first:** `test_false_flag_blocks_route_deep_link_keyboard_and_cached_manifest`.
Run separately for causal graph, command palette and WhatIf. Collaboration key
absence is the retirement negative; a permission grant cannot make a false
rollout flag true and a flag cannot satisfy permission.

**Acceptance:** three whole-surface gates are real at route, deep-link and
keyboard entry; collaboration key and environment surface are retired; all
four disposition decisions carry successor/consumer or deletion evidence.

**Expected commit:** `DS5-C19-R1 wire and retire D5 flags`.

### DS5-C20 — final ledgers, receipts, and architect handoff

**Measured set:** exactly 6 files; cap 6: this plan, DS5 journal, new closure,
`live-application-readiness-ledger.json`, the generated frontend disposition
reference document, and
`architecture/atlas_surfaces/test_atlas_enforcement.py`. Disposition/status/waist rows and hashes transition in
their owning implementation/regeneration clusters, never as a C20 tail. All
JSON edits are surgical and idempotent.

**Red first:**
`test_ds5_closure_corruption_sweep_covers_every_governed_property` executes the
closure corruption sweep over the governed local properties:
authority-sink census omission/fingerprint drift, type-invalid branded
assignment, unregistered escape syntax, issuer fixture/unlisted/runtime novelty,
illegal module edge, direct raw transport, authored capability discovery,
semantic-ID/review-receipt mismatch, active `ru`, audience deny bypass,
unknown/default-allow identity, changed generated symbol/field, an unissued or
incomplete structural G4 packet assigned to the private nominal sink, cached
payload without visible posture, query construction/producer census omission,
governed query pin, authority queue kind, service-worker authority API cache or
sync registration, raw/unscoped storage construction, cross-tenant/user/expiry
codec hydration across C14b-R1-C17a-R1, persistence-construction census drift, unknown
flag, unbound/unscoped flag source, and flag/permission substitution must each
fail while benign siblings pass. The meta-test imports and executes the real
registered corruption witnesses; it does not merely search for their names.

**Acceptance:** final clean-tree receipt table is complete; every touched row
has evidence and truthful capability state; baseline debt has zero new
identity; fence/lock/generated diffs are exact; independent review has no open
Important/Critical finding; closure explicitly lists what is not claimed.

**Expected commit:** `DS5-C20 close enforcement waist for architect review`.

## Expected cluster commits

| Cluster | Expected subject | Max files |
| --- | --- | ---: |
| C00 | `DS5-C00 plan measured enforcement waist` | 1 |
| C01a | `DS5-C01a census branded authority sinks` | 15 |
| C01b | `DS5-C01b forbid authority escape hatches` | 13 |
| C01c | `DS5-C01c bind authority issuers to owner unions` | 13 |
| C02 | `DS5-C02 make architecture zero recurrent` | 7 |
| C03a-R1 | `DS5-C03a-R1 record raw transport drift` | 7 |
| C03b-R2 | `DS5-C03b-R2 type raw authority transports` | 17 |
| C03b-D1 | `DS5-C03b-D1 record raw-transport deferral` | 7 |
| C04a-R1 | `DS5-C04a-R1 strangle capability fallback` | 11 |
| C04b-R2 | `DS5-C04b-R2 lint authored capability discovery` | 10 |
| C04b-D1 | `DS5-C04b-D1 record capability discovery deferral` | 7 |
| C05a-R1 | `DS5-C05a-R1 separate product and frozen locales` | 11 |
| C05b-R1 | `DS5-C05b-R1 anchor authority copy by semantic ID` | 12 |
| C05b-D2 | `DS5-C05b-D2 record semantic-copy deferral` | 7 |
| C05b-R3 | `DS5-C05b-R3 recover semantic-copy issuer guard` | 13 |
| C06 | `DS5-C06 bridge the three canonical waist unions` | 26 |
| C07 | `DS5-C07 enforce audience permission boundaries` | 26 |
| C08a | `DS5-C08a isolate auth test identity fixtures` | 5 |
| C08b-R1 | `DS5-C08b-R1 fail closed on unknown identity` | 11 |
| C09a-R1 | `DS5-C09a-R1 default deny application chrome` | 11 |
| C09b-R1 | `DS5-C09b-R1 default deny modes and run surfaces` | 8 |
| C10-R1 | `DS5-C10-R1 present owner-composed weakest boundary` (DEFERRED) | 8 |
| C11a | `DS5-C11a derive governed cache posture` | 5 |
| C11b-R1 | `DS5-C11b-R1 render governed cache posture` | 10 |
| C12a | `DS5-C12a register query construction debt` | 7 |
| C12b-R1 | `DS5-C12b-R1 enforce governed query policy` | 10 |
| C13a | `DS5-C13a delete authority mutation replay` | 18 |
| C13b-R1 | `DS5-C13b-R1 close service worker and composer DB` | 10 |
| C14a | `DS5-C14a own nominal local state envelope` | 3 |
| C14b-R1 | `DS5-C14b-R1 bind composer local state` | 8 |
| C15a | `DS5-C15a partition Clerk session codec` | 3 |
| C15b-R1 | `DS5-C15b-R1 mount Clerk identity hydration` | 6 |
| C16a-R1 | `DS5-C16a-R1 partition causal draft state` | 6 |
| C16b-R1 | `DS5-C16b-R1 partition dispute interaction state` | 8 |
| C17a-R1 | `DS5-C17a-R1 partition operator craft state` | 10 |
| C17b-R1 | `DS5-C17b-R1 govern persistence construction` | 10 |
| C18a | `DS5-C18a make flag exposure registry strict` | 3 |
| C18b-R1 | `DS5-C18b-R1 bind flag sources to strict registry` | 6 |
| C19-R1 | `DS5-C19-R1 wire and retire D5 flags` | 14 |
| C20 | `DS5-C20 close enforcement waist for architect review` | 6 |

## Closure battery

At C20 run each command separately and retain parseable output:

```bash
git status --short
git diff --check
python3 architecture/atlas_surfaces/check_status_retirement_inventory.py --check --corruption-probes
python3 architecture/atlas_surfaces/check_atlas_enforcement.py --check --corruption-probes
python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes
python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement architecture.atlas_surfaces.test_frontend_baseline_debt_manifest architecture.atlas_surfaces.test_frontend_disposition_register architecture.atlas_surfaces.test_status_retirement_inventory
uv run --extra runtime --extra ml pytest tests/unit/runtime/http/test_authorization_audience_denials.py tests/unit/runtime/http/test_runtime_permission_vocabulary.py tests/unit/runtime/http/test_governed_projection_api.py tests/unit/runtime/http/test_governed_projection_service.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/http/test_auth_api.py -q
uv run ruff check src/polisyos/runtime/http/audience_permissions.py src/polisyos/runtime/http/authorization.py src/polisyos/runtime/http/routes/governed_projections.py src/polisyos/runtime/http/services/governed_projection_validation_worker.py src/polisyos/runtime/http/services/governed_projections.py tests/unit/runtime/http/test_authorization_audience_denials.py tests/unit/runtime/http/test_runtime_permission_vocabulary.py tests/unit/runtime/http/test_governed_projection_api.py tests/unit/runtime/http/test_governed_projection_service.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
python3 -m tools.cli workspace verify --backend-only
python3 -m tools.cli workspace ci-parity --skip-browser
```

And from the relevant workspaces:

```bash
corepack pnpm --dir packages/runtime-api-client run typecheck
corepack pnpm --dir packages/runtime-api-client run lint
corepack pnpm --dir packages/runtime-api-client run test
corepack pnpm --dir packages/runtime-api-client run format:check
corepack pnpm --dir packages/runtime-api-client run check:architecture
corepack pnpm --dir apps/runtime-dashboard run lint
corepack pnpm --dir apps/runtime-dashboard run lint:enforcement
corepack pnpm --dir apps/runtime-dashboard run check:architecture
corepack pnpm --dir apps/runtime-dashboard run typecheck
corepack pnpm --dir apps/runtime-dashboard run build
corepack pnpm --dir apps/runtime-dashboard run test:components -- --reporter=json --outputFile=/tmp/atlas-ds5-components-vitest.json
python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --vitest-results /tmp/atlas-ds5-components-vitest.json
corepack pnpm --dir apps/runtime-dashboard run test:storybook
corepack pnpm --dir apps/runtime-dashboard run test:a11y
corepack pnpm --dir apps/runtime-dashboard run test:visual
corepack pnpm --dir packages/atlas-ui run lint
corepack pnpm --dir packages/atlas-ui run check:architecture
corepack pnpm --dir packages/atlas-ui run typecheck
corepack pnpm --dir packages/atlas-ui run test
```

The production build, typecheck, DS5-owned/touched tests, generated-client
contract and architecture gates are absolute green. Full component/visual gates
are honest baseline-red only for the exact three DS6 parity identities and the
one DS8 A4 print identity; no new failure or re-baseline is accepted.
The JSON component command is therefore an expected nonzero receipt only when
its parseable output contains those exact three inherited DS6 identities; it is
run separately, never chained past. The following governed comparator must be
green. A missing/timed-out JSON command is a non-receipt. `test_auth_api.py` is
run read-only as shared authorization coverage; it is not a sixth editable
backend test path.

## Explicit Not yet

- No merge, push, rebase, CI change, deployment claim, or backend-engine work.
- No claim that arbitrary TypeScript behavior has been completely analyzed.
  DS5 claims compile-time branded-slot assignability, the bounded syntactic
  escape/construction rules named above, and issuer runtime novelty only.
- No claim that the 12 registered unbranded authority props or 58 direct
  authority-bearing `Badge` sites are migrated; their 39 source-bound debt
  descriptors retain owner slices, capability states and executable closure
  signals. All 103 current benign direct sites are explicit classifications,
  not a claim of future semantic discovery.
- No closure or ordering of terminal kinds or evidence classes; unseen values
  stay opaque and neutral.
- No DS6 `overBudget` parity repair, frozen-set migration, `ru` catalog edit,
  or public locale-support claim.
- No claim that automation understands Ukrainian or certifies translated legal
  meaning. C05b-R1 validates canonical identity and content-bound external-review
  receipts; absent review falls back honestly and remains DS6 debt.
- No DS8 A4 print expectation change and no claim of 18/18 visual green.
- No DS18 universal epoch/staleness chrome. DS5 supplies cache discipline and
  visible existing consumers; it does not invent producer epochs or infer
  cache age from timestamps.
- No universal client recomputation theorem. Deferred C10-R1 accepts only a nominal packet
  issued after the canonical live client validates the complete owner-composed
  G4 response; C11a-C12b-R1 govern one migrated builder and fingerprint-bind the
  other 65 construction sites and 41 producer sites as typed debt with
  producer-side integrate-contracts.
- No theorem that a storage caller classified arbitrary unbranded payload
  meaning correctly. C13a/C15a/C16a-R1-C16b-R1 close the six measured status paths; C17b-R1
  enforces registered constructors, nominal envelopes and concrete codecs.
  Semantic equivalents outside nominal authority types remain attached to the
  C01a typed owner debt rather than being claimed as universally detected.
- No DS9 mandate, approval, review-effectiveness, or promotion-CAS ownership;
  DS20's server halves are consumed, not re-closed.
- No DS12 telemetry/public-record closure; telemetry remains a typed sanctioned
  adapter with its privacy capability still `verification_missing`.
- No N018 review-WebSocket authentication/idle-safe surface closure. The raw
  constructor is governed, while the existing handshake/degradation gap stays
  `bridge_missing` with its named owner and closure signal.
- No ban on fixed curated workspace chrome or typed capability gates; law 12
  forbids open-ended hardcoded capability discovery.
- No claim that a lint, flag, cache hit, translation, or frontend union is an
  authority source.
- No closure of law 11 beyond its audience/permission enforcement half.
