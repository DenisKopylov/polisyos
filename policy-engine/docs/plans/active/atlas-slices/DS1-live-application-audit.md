---
plan_id: atlas-ds1-live-application-audit
title: "DS1 - Live Application Audit"
type: slice-plan
status: active - audit not yet executed
created: 2026-07-16
revised: 2026-07-16
last_verified: 2026-07-16
stability: executable
slice: DS1
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
ds0_record: ../../../brand/ATLAS_SOURCE_OF_TRUTH.md
readiness_schema: ../../../../architecture/atlas_surfaces/surface-readiness-ledger.schema.json
adoption_schema: ../../../../architecture/atlas_surfaces/adoption-ledger.schema.json
audit_report: ../../../reference/frontend/atlas-live-application-audit.md
readiness_instance: ../../../../architecture/atlas_surfaces/live-application-readiness-ledger.json
journal: ../../../superpowers/journals/2026-07-16-atlas-ds1-live-application-audit.md
audiences: [REVIEWER, EXPERT, MACHINE]
backend_co_owner: team-architecture  # classification only; DS1 changes no runtime code
feature_flags: none
depends_on:
  - ./DS0-source-of-truth-freeze-and-governing-decisions.md
  - ../../../brand/ATLAS_SOURCE_OF_TRUTH.md
  - ../../../../architecture/atlas_surfaces/surface-readiness-ledger.schema.json
  - ../../../../architecture/atlas_surfaces/adoption-ledger.schema.json
  - ../../../reference/policy-design-case-failure-patterns.md
  - ../../../reference/frontend/workspace-contract.md
---

# DS1 - Live Application Audit

## Mission And Product

DS1 produces the definitive, code-grounded map of the live PolicyOS frontend
zone before any Atlas migration or v15 adjudication affects it. Its product is
not a list of observations. It is the denominator-complete evidence base that
re-scopes DS3-DS18 and lets the architect revise the Revision 2 roadmap after
Phase A against current code rather than the 2026-06-10 recon snapshot.

The audit classifies what exists. It fixes nothing, flips no flag, adds no
application test, changes no dependency, and makes no readiness claim beyond
the evidence found in the current tree. A route or feature that renders is not
rounded up to `implemented`; every capability link is judged independently.

## Governing Sources And Vocabulary

The audit derives from, in order:

1. the [Revision 2 master plan](../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md),
   especially DS1, the Code-Grounded Technical State, the named hotspots, and
   the Surface Proving Ground;
2. the [surface constitution](../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md),
   especially laws 1-12 and the capability definition of done;
3. the [DS0 governing record](../../../brand/ATLAS_SOURCE_OF_TRUTH.md),
   especially D5's one-registry direction and the four flags currently
   classified `consumer_missing`;
4. the [failure/repair register](../../../reference/policy-design-case-failure-patterns.md).

DS1 reuses, without extension, these schema-owned values:

- adoption verdict: `admit_as_is`, `admit_after_refactor`,
  `wrap_then_strangle`, `reject`, `defer`;
- readiness: `contract_only`, `producer_missing`, `bridge_missing`,
  `consumer_missing`, `verification_missing`, `surface_missing`,
  `semantic_test_missing`, `implemented`;
- capability link: `implemented`, `missing`, `out_of_scope`;
- maturity: `experimental`, `beta`, `stable`, `deprecated`;
- provenance: `live`, `replay`, `fixture_only`;
- audience: `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE`.

The human report carries an adoption verdict for every audit row. The machine
ledger carries the same unit identifiers and the DS0 readiness fields. The
readiness schema is not amended merely to duplicate the adoption vocabulary.

### Aggregate-readiness rule

The report and ledger derive the aggregate readiness honestly from the chain:

1. missing typed contract or a local ungoverned contract -> `contract_only`;
2. consumer expects an absent producer -> `producer_missing`;
3. producer/persistence exists but the governed transport or orchestration
   bridge is absent -> `bridge_missing`;
4. a produced/bridged capability has no live reader -> `consumer_missing`;
5. a visible chain lacks risk-proportionate automated evidence ->
   `verification_missing`;
6. an internal capability lacks its required audience surface ->
   `surface_missing`;
7. structural evidence exists but the authority/fail-closed negative or
   semantic assertion is missing -> `semantic_test_missing`;
8. `implemented` is allowed only when every required link is implemented or
   explicitly `out_of_scope`, including negative and semantic tests.

The DS0 schema has no `artifact_missing` aggregate value. Where persistence is
the first absent sublink, the chain records `persisted: missing`, the reason
names the failure-register label, and aggregate readiness is
`bridge_missing`; DS1 does not mint a ninth readiness value.

Adoption verdict and readiness are orthogonal. For example, a useful live
surface may be `wrap_then_strangle` and `semantic_test_missing` at once.

## Binding Boundary And Isolation

Work continues only in `.worktrees/atlas-ds0` on
`codex/atlas-ds0-source-of-truth`, stacked on DS0 HEAD `1afee84f8`. Writable
paths are limited to:

- `docs/plans/active/atlas-slices/**`;
- `architecture/atlas_surfaces/**`;
- this one new DS1 journal,
  `docs/superpowers/journals/2026-07-16-atlas-ds1-live-application-audit.md`;
- `docs/reference/frontend/**`;
- the Revision 2 Atlas master plan, only for evidence-backed snapshot and
  scope corrections produced by this audit.

Read-only evidence zones are `apps/**`, `packages/**`, `frontend/**`,
`e2e/**`, and `src/polisyos/runtime/http/**`. Forbidden zones remain
`docs/plans/active/layer3-slices/**`,
`architecture/policy_design_case/**`, `tools/quality/**`, and
`production_data/**`. The `.worktrees/gy-n10/` worktree and its branch are
never entered or modified.

Existing test, story, build, and static tooling may run only when it adds
material evidence and does not require installation or source changes. Before
and after each such command, `git status --porcelain` is captured. Any tool
mutation is reverted from the DS1 worktree and recorded; mutation is never
committed.

## Deliverable Locations

| Artifact | Role |
| --- | --- |
| `docs/reference/frontend/atlas-live-application-audit.md` | Canonical human audit: denominators, every unit row, hotspot evidence, negatives, and Plan-Impact Appendix |
| `architecture/atlas_surfaces/live-application-readiness-ledger.json` | First real, non-example population of the DS0 readiness schema; one entry per audit unit |
| `docs/plans/active/atlas-slices/DS1-live-application-audit.md` | This executable spec and closure contract |
| `docs/superpowers/journals/2026-07-16-atlas-ds1-live-application-audit.md` | Checkpoint log; updated before each audit-cluster commit |
| `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Corrected June-snapshot rows and evidence-backed downstream scope deltas only |

No second audit schema, generated prose projection, application fixture, or
bespoke validator is created (P13/P29). The report is the readable projection
of the same unit IDs as the ledger.

## Exhaustiveness Law And Recomputed Denominators

The 2026-06-10 figures are hypotheses, not inputs. DS1 recomputes every
denominator from the checked-out tree and records the exact command or parsing
rule, exclusions, measured count, snapshot delta, and `audited N of N` proof.

| Snapshot dimension to reconcile | Full-set construction |
| --- | --- |
| TS/TSX files and LOC | All tracked `*.ts`/`*.tsx` under the live frontend zones; report generated/vendor exclusions separately; LOC uses one recorded physical-line rule |
| Test files | All tracked frontend `*.test.*`, `*.spec.*`, Playwright/e2e test files, and package-side frontend tests; categories are disjoint and totals are set-derived |
| Routes | Route-object/path declarations and route components in `apps/runtime-dashboard`, plus the reference shell's declarations; aliases, redirects, index routes, and parameterized routes are rows |
| Feature modules | Every immediate `apps/runtime-dashboard/src/features/*` directory plus any feature entry file at that level |
| Shared UI families | Public exports and immediate families under `src/shared/ui`; root components and compound directories are reconciled into a membership list so no implementation file is unowned |
| OpenAPI operations | Every method/path operation in the checked-in OpenAPI source used to generate the client; operation IDs and generated-client presence are cross-checked |
| Hand-written fetches | Every `fetch`, `EventSource`, `WebSocket`, and equivalent raw transport construction outside sanctioned API/transport owners; exact call site and exemption rationale required |
| UI-local status vocabularies | Every frontend enum, string union, `as const` value map, or schema enum that expresses status/readiness/authority-like state; interaction-only values are still inventoried and classified |
| Feature flags | Every declared manifest key, every env/window/remote/cache/provider input, and every auth-derived override key; consumers are discovered independently from declarations |
| Stories | Every tracked Storybook story file in the frontend zone |
| A11y evidence | Every `.a11y.test.*`, axe invocation, keyboard/browser a11y suite, and manual-AT evidence reference; automated checks are not relabeled manual evidence |
| E2E/visual evidence | Every tracked e2e journey, a11y spec, visual spec, and committed snapshot family; record what assertion it actually proves |

Coverage is proved by set difference, not by narrative confidence:

```text
discovered_ids - report_row_ids = empty
report_row_ids - discovered_ids = empty (except declared aggregate estate rows)
report_row_ids - ledger_surface_ids = empty
ledger_surface_ids - report_row_ids = empty
duplicate(report_row_ids) = empty
duplicate(ledger_surface_ids) = empty
```

Sub-sampling is permitted only within a demonstrably uniform evidence family,
such as per-component a11y files that invoke the same harness. The report must
still list the family's full membership and count, state the deterministic
sampling rule, inspect at least the first, median, and last ordered member plus
every outlier, and limit the inference to the uniform property actually
observed. Unit disposition, chain status, and existence are never sampled.

## Audit Unit Inventory

Every discovered unit receives a stable ID, report row, readiness-ledger row,
adoption verdict, maturity, audience, chain links, owner/slice, evidence refs,
reason, and explicit `not_yet`. Families may aggregate files only under the
membership rules below.

### Routes and shells

- every `apps/runtime-dashboard` route, including `/`, auth/onboarding,
  workspace routes, parameterized artifact/public routes, redirects, and
  catch-all boundaries;
- every `apps/runtime-reference-shell` route or, if it has no router, each
  top-level shell view that functions as a route;
- for each route: route declaration, rendered feature, data sources,
  permission/flag boundaries, error/loading/offline state, tests, audience,
  and outbound links.

### Feature modules

- every member of `apps/runtime-dashboard/src/features/*`;
- public entry points, hooks, domain types, API use, stores/persistence,
  route/shell consumers, tests/stories, flags/authz, and authority posture;
- orphan feature modules remain rows and are findings, never dropped.

### Shared UI component families

- every public root component and every immediate compound family under
  `apps/runtime-dashboard/src/shared/ui`;
- membership reconciles public exports, implementation files, stories,
  a11y/unit tests, and styles; any unowned file is an audit finding;
- maturity is judged against the constitution. `stable` requires the full
  typed/token/state/keyboard/a11y/owner/evidence bar, including manual AT for
  high-risk patterns. Story or axe presence alone is not sufficient.

### API operations and phantom census

- every checked-in OpenAPI operation receives a row, even when the UI has no
  consumer; consumed and unconsumed sets are both published;
- every UI call is normalized to method + path template and matched against
  the server route and generated client;
- unmatched UI calls are phantom candidates; unmatched server/OpenAPI
  operations are consumer-missing candidates, not automatically product debt;
- dynamic path builders, base URLs, vite proxies, SSE, and WebSocket paths are
  resolved separately so string-shape differences do not hide mismatches.

### Raw fetch and local-status retirement inventories

- every hand-written network call outside `src/api/` and sanctioned transport
  owners is reported at exact file:line with method, path, payload class,
  authority risk, and future DS5 disposition;
- every UI-local status definition is reported at exact definition lines with
  all consumers, its classification (interaction/domain/authority-adjacent),
  the generated/runtime counterpart if any, and the divergence set. The three
  `DisputeStatus` definitions are verified independently rather than assumed.

### Flags, transports, adjacent surfaces, and evidence estate

- all 12 manifest flags, their full source precedence, all consumers, and the
  `/auth/me` override path are audited against D5; the four DS0
  `consumer_missing` claims are confirmed or refuted from current references;
- generated OpenAPI client, raw fetch, SSE, WebSocket, workers, offline queue,
  service worker/cache scopes, storage, and retry/revalidation paths each get
  a transport row;
- `packages/cli` styleguide and print/export paths receive existence-and-chain
  checks only, matching D6; DS1 does not re-adjudicate their slice assignment;
- all unit, contract, story, a11y, visual, e2e, and snapshot evidence is
  inventoried. The report distinguishes what exists from what it proves and
  names the DS6 evidence location/workflow that is still missing.

## Named Hotspot Sections

The audit report contains each section below even if the recon claim is
refuted.

### Public decision packet and browser signing

For `public/decisions/:signedId`, trace the packet from builder to URL to
verification UI. Record the exact `signatureForPayload` algorithm and input,
all creation and verification call sites, every link producer/consumer, route
audience, payload claims, storage/transport, and whether any live or published
artifact depends on it. Quantify the blast radius. Seed DS12's first negative:
a forged or self-signed browser payload must not render `Verified`, with the
exact target test location, setup, and expected pre-fix failure.

### Candidate/authority laundering

Audit `causal`, `whatif`, `lex`, `composer`, and `clerk` separately. For every
engine/LLM-derived output, identify producer class, API/transport, rendered
component, current clothing/copy, and the precise authority slot at risk.
Every P15/P05 finding has file:line evidence and a red-first negative assigned
to DS4, DS8, DS10, DS12, or DS14 as appropriate.

### Authorization and human integrity

Enumerate every mutating runtime HTTP endpoint and match it to:

- the server-side identity dependency and permission/role/tenant denial;
- the client visibility/permission check, if any;
- the audience class it would require under DS5;
- fixture identity reach;
- step-up-auth requirement for approval, promotion, publication, revocation,
  acquisition, override, destructive/export, and other high-stakes actions.

The result is the full UI-hides-but-server-allows list, not selected examples.
Compare server and client permission vocabularies value by value. Seed P26/P05
negatives for every uncovered high-stakes class; do not fix an endpoint.

### Offline, cache, and authority queues

Inventory every service-worker cache rule, runtime cache, local/session/Indexed
DB repository, offline queue producer, queued action, flush trigger, retry,
conflict handling, and revalidation step. Confirm `useQueuedPromotionDecision`
and discover sibling authority-bearing actions. Propose the DS5 policy as a
classification matrix: cacheable data + required as-of rendering; never-cache
data; queueable non-authority intent; authority action barred unless live
state and permission are revalidated before execution.

### Workers and client-side derivations

Enumerate every worker and authority-adjacent client derivation, including
`dataTransform.worker.ts` and `projectionFailClosed.ts`. Classify layout,
sorting, filtering, formatting, and form-shape validation as permitted only
when they do not create authority. Flag local support, publishability,
admissibility, promotion, weakest-boundary, signature, or evidence-status
recomputation with exact call sites and owning negative.

### Off-contract channels

Inventory both `include_in_schema=False` SSE endpoints, the review WebSocket
hub, every client SSE/WS subscription, and every collaboration REST path.
Match route, transport schema, auth, reconnect/error behavior, consumer, and
degraded UX. The report states whether collaboration REST is truly phantom in
the checked-out server tree rather than inheriting the recon conclusion.

### Flags and shadow shipping

Recompute declarations and references, map every input and precedence edge,
and compare every key against D5 owner/intent/sunset. Confirm or refute
`enableCausalGraph`, `enableCollaboration`, `enableCommandPalette`, and
`enableWhatIfAnalysis` as `consumer_missing`. Flag any flag that changes
authorization or authority rather than exposure/rollback.

### Public telemetry

Trace telemetry initialization, environment configuration, DSN/release/user
context, breadcrumbs, captured errors/events, scrubbing/filtering, and route
scope. Record what data may leave the browser, destination ownership, whether
PUBLIC routes initialize it, and whether third-party network transmission is
disabled, conditional, or live. Feed the evidence into DS12's no-tracker
posture without asserting network behavior the static config cannot prove.

## Seeded Red-First Negative Specification

Every finding tagged P15, P05, P26, or P04 gets a precise, implementation-ready
negative spec in the report. Each spec contains:

| Field | Required content |
| --- | --- |
| Negative ID | Stable `DS1-N###` identifier referenced from finding and plan impact |
| Pattern and owner | One or more of P04/P05/P15/P26; owning slice among DS4/DS5/DS9/DS12/DS14 (DS8/DS10 may consume but not replace the named owner) |
| Target location | Exact future test file or closest existing suite to extend |
| Setup | Concrete payload, identity, flag/cache/offline state, producer class, and route/component |
| Forbidden outcome | The authority/status/action that must never render or execute |
| Expected red state | What the current code does, tied to evidence, so the test would fail before repair |
| Passing condition | Observable post-fix behavior and the real producer/permission boundary it must exercise |
| Sibling variants | At least one adjacent consumer/input so the future fix closes the class (P31/P33) |

Specs only are written. DS1 does not add tests to read-only zones.

## Plan-Impact Appendix

The report closes with an architect-oriented appendix. Every row contains a
finding ID, evidence, current assumption, required DS3-DS18 scope change,
dependencies/owner, and effort direction (`decrease`, `unchanged`, `increase`,
or `re-cut-required`) with a reason. It includes:

- current features/routes/transports that map to no slice;
- slice assumptions contradicted by code;
- dead, orphaned, duplicate, or phantom paths that should strangle rather
  than migrate;
- scope that already exists and should be wired/rebound instead of rebuilt;
- effort changes caused by measured denominators or hidden authority/authz/
  offline blast radius;
- a corrected version of every affected Code-Grounded Technical State row;
- the exact master-plan edits made by DS1, with no unrelated roadmap rewrite.

The appendix is an input to the post-Phase-A master-plan revision. It does not
pre-approve that revision or alter the DS2 adjudication outcome.

## Pattern Pass

| Pattern | Audit risk already present or possible | Smallest correct audit control / acceptance signal |
| --- | --- | --- |
| P01 | rendered units are called implemented without a producer/bridge chain | every unit has all nine link states and an honest aggregate readiness |
| P04 | local status definitions disappear into narrative or become a new audit enum | exhaustive definition/consumer census; only DS0 vocabulary in outputs; divergences get DS4 negatives |
| P05 | client projections, browser signatures, fixture data, or UI hiding appear authoritative | purpose/producer/consumer traced; every leak gets exact evidence and a negative spec |
| P10 | story, snapshot, axe, or schema shape is treated as semantic readiness | evidence estate records what each test actually proves; `stable` and `implemented` remain gated |
| P13 | the audit creates new registries or per-feature governance artifacts | one report, one existing-schema ledger, one plan, one journal |
| P15 | fluent engine/LLM output is not traced to its rendered authority slot | causal/whatif/lex/composer/clerk each receive a complete laundering section and negatives |
| P26 | client visibility or a click is treated as accountable human authorization | every mutating endpoint, identity fallback, permission deny, offline action, and step-up need is enumerated |
| P29 | hand-authored counts self-attest to exhaustiveness | denominators are recomputed; discovered/report/ledger set differences must be empty |
| P31/P33 | only the named recon example is checked | each hotspot search expands to sibling sites; negative specs include sibling variants |
| P34 | a tool mutation or pre-existing failure is casually excluded | pre/post status capture and completed isolation before any exclusion |

The audit itself is a DS1 evidence artifact and therefore
`implemented_but_not_orchestrated` relative to DS6's future behavioral ledger
validator. Its JSON Schema validation proves shape, not truth. Exhaustive set
reconciliation and evidence refs are DS1's proportionate P29 control.

## Execution Checkpoints And Commits

1. **Executable spec** - create this plan and the unique DS1 journal; verify
   links/fence; commit before audit execution.
2. **Inventory and denominators** - recompute every snapshot denominator,
   freeze stable unit IDs/membership, and journal the exact commands; commit
   the report's coverage skeleton.
3. **Routes, features, UI, and evidence estate** - audit every route, feature,
   shared UI family, reference-shell view, test/story/a11y/e2e family, plus
   CLI/print existence; update ledger rows and journal; commit.
4. **API, transports, authz, offline, and flags** - complete bidirectional
   API census, raw-fetch/status retirement inventories, mutation/permission
   matrix, cache/queue/worker/off-contract/telemetry analysis; update ledger
   and journal; commit.
5. **Laundering hotspots and negatives** - complete public-signing and five
   engine/LLM surface traces; seed every P04/P05/P15/P26 negative; commit.
6. **Plan impact and closeout** - correct the master snapshot, finish the
   DS3-DS18 impact appendix, validate the ledger, resolve links, reconcile
   coverage sets, rerun the pattern pass, prove the path fence and clean tree,
   update journal, and commit.

## Closure Contract

DS1 closes only when all of the following are true:

- [ ] The June snapshot reconciliation table contains every required
      dimension, exact measured denominators, reproducible methods, and
      `audited N of N` coverage.
- [ ] Every runtime-dashboard route and every reference-shell route/view has
      a report and ledger row.
- [ ] Every `features/*` module has a report and ledger row.
- [ ] Every shared/UI public component family has a membership-complete report
      and ledger row; maturity follows the constitution rather than story/axe
      presence.
- [ ] Every checked-in OpenAPI operation is classified as UI-consumed or
      consumer-missing; every UI network call is matched to a server route or
      reported as off-contract/phantom.
- [ ] Every hand-written fetch/transport call outside sanctioned owners is
      listed at exact file:line.
- [ ] Every UI-local status vocabulary definition and its consumers are
      inventoried; all `DisputeStatus` definitions and divergences are shown.
- [ ] All feature flags and override/source paths are reconciled against D5,
      including a current verdict for the four `consumer_missing` claims.
- [ ] Generated client, SSE, WS, workers, offline queue, service worker/cache,
      storage, and retry/revalidation paths are fully inventoried.
- [ ] CLI and print/export existence checks are complete without changing D6.
- [ ] The entire test/story/a11y/e2e/snapshot estate is counted and mapped to
      what it actually proves; any sampling is declared under the uniform
      family rule.
- [ ] Each named hotspot has its own evidence-bearing section and exact
      file:line references.
- [ ] Every P04/P05/P15/P26 finding has a red-first negative spec with target,
      setup, expected current failure, passing behavior, and sibling variant.
- [ ] The Plan-Impact Appendix covers all DS3-DS18 scope effects, features with
      no slice, contradicted assumptions, strangle candidates, and effort
      changes; affected master snapshot rows are corrected.
- [ ] `architecture/atlas_surfaces/live-application-readiness-ledger.json`
      validates against the unchanged DS0 schema and contains exactly the
      report's stable unit-ID set.
- [ ] All touched Markdown file links resolve; no report claim lacks evidence
      or a reproducible method.
- [ ] Existing tools, if run, left the tree unchanged or were isolated and
      reverted with the result recorded.
- [ ] `git diff --check main...HEAD` is clean; every changed path is inside
      the DS0+DS1 fence; `git status --porcelain` is empty.

Closure does not mean any finding is repaired, any flag is governed in code,
any status is rebound, any endpoint is secured, or any public record is safe
to publish. Those claims remain with the named downstream slices.

## Targeted Verification

The machine instance is validated with the DS0 command shape:

```bash
uv run --with check-jsonschema check-jsonschema \
  --schemafile architecture/atlas_surfaces/surface-readiness-ledger.schema.json \
  architecture/atlas_surfaces/live-application-readiness-ledger.json
```

Closeout also checks:

- JSON parseability, unique `surface_id` values, and report/ledger set parity;
- exact denominator inventories against report row IDs;
- changed-doc local links and referenced code files;
- `git diff --check main...HEAD`;
- `git diff --name-only main...HEAD` against the explicit fence;
- `git status --porcelain` for a clean worktree.

No pytest, application build, browser run, or dependency install is required
for closure. Existing targeted tools may run only under the read-only law.
