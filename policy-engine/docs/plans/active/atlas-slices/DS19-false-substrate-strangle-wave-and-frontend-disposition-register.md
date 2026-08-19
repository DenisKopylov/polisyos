---
plan_id: atlas-ds19-false-substrate-strangle-wave-and-frontend-disposition-register
title: "DS19 - False-Substrate Strangle Wave And Frontend Disposition Register"
type: slice-plan
status: implementation_complete_no_merge_baseline_red - architect review pending
created: 2026-07-17
revised: 2026-07-17
last_verified: 2026-07-17
stability: executable
slice: DS19
baseline_commit: d01eaa57285c490412599ea65f898d3dbd522b04
parent_reproduction_commit: 7b69337704ad304ec4fa1afb3712f13a493782ba
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
ds0_record: ../../../brand/ATLAS_SOURCE_OF_TRUTH.md
ds1_report: ../../../reference/frontend/atlas-live-application-audit.md
ds1_ledger: ../../../../architecture/atlas_surfaces/live-application-readiness-ledger.json
ds2_ledger: ../../../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json
baseline_debt_schema: ../../../../architecture/atlas_surfaces/frontend-baseline-debt.schema.json
baseline_debt_manifest: ../../../../architecture/atlas_surfaces/frontend-baseline-debt-manifest.json
journal: ./DS19-false-substrate-strangle-wave-journal.md
audiences: [REVIEWER, EXPERT, MACHINE]
owner: team-frontend
architecture_owner: team-architecture
depends_on:
  - ./DS1-live-application-audit.md
  - ../../../reference/frontend/atlas-live-application-audit.md
  - ../../../../architecture/atlas_surfaces/live-application-readiness-ledger.json
  - ../../../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json
  - ../../../reference/policy-design-case-failure-patterns.md
---

# DS19 - False-Substrate Strangle Wave And Frontend Disposition Register

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` for independent deletion clusters
> or `superpowers:executing-plans` for sequential execution. Keep one
> controlling agent responsible for route, realtime, register, report, and
> journal edits. Locale, dependency, and lockfile changes are not authorized
> after the isolated baseline-repair commit.

**Goal:** Delete only the frontend units proven false or zero-consumer, retain
every live sibling, and establish one typed disposition authority that forces
each Atlas estate unit toward `use_as_is`, effective rebound, or `deleted`.

**Architecture:** DS19 is a strangler and accounting slice, not a feature
slice. A typed register is seeded from the DS1 readiness and DS2 adoption
ledgers; its validator recomputes current-path and consumer claims from the
checked-out tree. Six independently reviewable deletion clusters remove the
ratified false substrate, while browser signing and all other live consumers
are registered without mutation.

**Tech Stack:** React 19, TypeScript, React Router, Vitest, Vite,
`vite-plugin-pwa`, ESLint JSON diagnostics, JSON Schema Draft 2020-12,
repository architecture guardrails, `rg`, and Git.

## Global Constraints

- Execute in `.worktrees/atlas-ds19/policy-engine` on
  `codex/atlas-ds19-strangle-wave`, starting from clean HEAD
  `d01eaa57285c490412599ea65f898d3dbd522b04`.
- DS19 performs deletion and registration only. It adds no producer, endpoint,
  transport, rebinding, migration store, public claim, or replacement UI.
- A unit with any live production consumer is outside the deletion wave and is
  registered only.
- Browser signing is fully protected by owner ratification. Do not delete or
  rewrite its builders, verifier, public route, tests, or e2e coverage.
- Preserve the live review WebSocket, Operator Craft onboarding, real
  `app/layout` owner, PWA service worker, Clerk `ModeAwareHome`, and API-backed
  Scenario Workbench.
- Preserve the amended D4-A1 posture: English is the authored primary,
  Ukrainian is its translation, and the Russian UI catalog remains in-tree,
  frozen, and unexposed. DS19 does
  not edit any locale catalog; dead-copy adjudication belongs to a later owner.
- A deletion is rejected unless the executor records a fresh census of tracked
  paths, static and dynamic imports, route registrations, identifier strings,
  tests/stories/e2e, package/feature manifests, and generated Vite/PWA output.
- The DS1 report and readiness ledger are immutable `as_of` evidence. Their
  recorded code-path references identify the Phase-A tree at
  `ed74537e803bf92a63f65c407f3806194c0d91fc`; DS1 rows are not rewritten or
  required to masquerade as current paths after a registered deletion.
- Every register transition to `deleted` lands in the same review unit as the
  deletion. A row cannot predeclare deletion, and deleted code cannot land
  without its row transition.
- Absolute-green gates remain absolute for typecheck, production build/PWA,
  postbuild security, affected tests, scoped lint, and changed paths.
- Full lint and full Vitest use the ratified baseline-relative no-regression
  laws below. Baseline-relative acceptance is not a claim that those suites are
  green and does not waive repository merge governance.
- Do not merge or push. DS19 closes as a reviewable no-merge branch; a merge
  requires green protected CI and separate owner/architect approval.

---

## Baseline Receipt And Gate Algebra

The baseline was measured before any deletion. The journal owns the
chronology; this table is the binding execution receipt.

| Surface | Baseline at `d01eaa572` | Law during DS19 |
| --- | --- | --- |
| TypeScript | `typecheck` passed in **11.63 s** | Must remain absolutely green after every cluster |
| Production build | Vite production build, injected PWA service worker, and postbuild security passed in **22.69 s** | Must remain absolutely green; generated manifest, assets, and `sw.js` are then censused |
| ESLint | **75 errors, 0 warnings**; initial full enumeration took about **19 min** and cached JSON refresh took **5.93 s** | Current exact diagnostic identities must be a subset of the checked-in baseline; any new identity is red |
| Vitest | **231 files / 678 tests**; **228 files / 673 tests passed**, **3 files / 5 tests failed**, in **181.12 s** | The five canonical failure identities may persist or disappear; any new identity is red; every cluster-focused test must pass |
| Failure isolation | The same five failures were reproduced on parent `7b6933770` in **1.96 s** | This satisfies the initial P34 origin check only; the changed tree reruns the full suite and compares identities at wave end and closure |

### Exact ESLint identity law

`architecture/atlas_surfaces/frontend-baseline-debt-manifest.json` is the
baseline source of truth and
`architecture/atlas_surfaces/frontend-baseline-debt.schema.json` types it.
For lint, identity is the exact tuple:

```text
(path, rule_id, severity, location, message_or_message_id)
```

At wave end and closure:

```text
current_lint_identities - baseline_lint_identities = empty
current_warning_count = 0
current_error_count <= 75
```

Diagnostic removal is allowed. Count-only comparison is forbidden because a
new error could replace an old one while leaving the total unchanged. An
identity moved by an edited file is new evidence and must be fixed or
explicitly shown to be the same checked-in baseline identity by the canonical
comparator; it is never dismissed manually.

After each cluster, scoped lint runs on every surviving file touched by the
deletion census. That scoped command is absolutely green; it does not replace
the two full baseline-relative comparisons.

### Exact Vitest identity law

The canonical baseline contains five failing tests in three classes:
`i18n`, `A11yCoverage`, and `TemporalCursor`; all are owned by DS4. Failure
identity is the test-file path plus full test name and failure signature.

```text
current_failure_identities - baseline_failure_identities = empty
focused_cluster_failure_identities = empty
```

The denominator is recomputed at wave end and closure because passing test
files may be intentionally deleted and fence coverage may change. Do not force
the post-wave total back to 231 files or 678 tests. A baseline failure may
disappear. A renamed, moved, or differently failing test is new until proven
otherwise by the canonical report comparator.

### No-merge interpretation

The baseline-relative laws authorize controlled progress on a branch with
known inherited debt. They do not relabel red suites as green. If lint or
Vitest remains baseline-red at closeout, the truthful state is
`implementation_complete_no_merge_baseline_red`; the branch can be reviewed
but cannot be merged under repository governance. If both become absolutely
green, the execution journal records that improvement, but the DS19 agent
still does not merge or push.

## Binding Artifacts And Owners

| Artifact | Responsibility |
| --- | --- |
| `architecture/atlas_surfaces/frontend-disposition-register.schema.json` | Strict typed vocabulary and row invariants for `use_as_is`, effective rebound, and `deleted` |
| `architecture/atlas_surfaces/frontend-disposition-register.json` | One canonical current disposition per seeded estate unit |
| `architecture/atlas_surfaces/frontend-baseline-debt.schema.json` | Typed lint/Vitest baseline-debt receipt |
| `architecture/atlas_surfaces/frontend-baseline-debt-manifest.json` | Exact inherited lint and Vitest identities used for no-regression comparison |
| `architecture/atlas_surfaces/check_frontend_disposition_register.py` | Standalone schema/parity/live-reference checker with in-memory corruption probes |
| `docs/reference/frontend/atlas-live-application-audit.md` | Immutable DS1 human snapshot; it remains `as_of` evidence rather than a current path manifest |
| This plan | Executable scope, gates, fences, and closure contract |
| `DS19-false-substrate-strangle-wave-journal.md` | Chronological receipts; never a substitute for machine checks |

The register validator is generic over schema composition, all 261 identities,
DS2 reconciliation, and every stored census. In addition, DS19's named wave
patterns are code-owned so an author cannot omit a decisive identifier from a
stored census. A `deleted` row must prove absence from tracked paths and all
declared consumer surfaces; effective rebound (`rebind_pending` plus a
strangled predecessor) must resolve a successor and a successor consumer.

## Ratified Wave Boundary

| Cluster | Delete | Preserve | Initial DS1 label |
| --- | --- | --- | --- |
| Collaboration | Orphan feature and phantom REST/WS substrate | Review WS and review collaboration surface; flags/permissions/copy/dependencies are disposition-only outside the deletion unit | `contract_only` / `producer_missing` |
| Onboarding | Orphan local tour/provider | Operator Craft onboarding | `consumer_missing` |
| Layout | Empty `features/layout` placeholder | `app/layout/**` | `contract_only` |
| Workers | Three zero-consumer Web Worker modules | Generic worker hook and PWA service worker | `consumer_missing` |
| Clerk | Duplicate unreachable index route | `ModeAwareHome`, Clerk page, public route module, mode | `consumer_missing` / deprecated |
| WhatIf | Latent local parameter/store branch | API-backed Scenario Workbench/editor/validation | `contract_only` |
| Browser signing | Nothing | All builders, verifier, route, tests, and e2e | live consumer: register only |

The 37 uncalled OpenAPI operations and four originally `consumer_missing`
feature flags receive wire-or-retire dispositions only. DS19 does not build,
wire, delete, or otherwise implement those decisions. In particular,
`enableCollaboration` remains in code with a DS5 retire disposition and
`enableWhatIfAnalysis` remains for the live API-backed workbench.

## Universal Cluster Protocol

Every cluster follows these actions in order:

- [x] Record clean status, HEAD, and the current register row.
- [x] Run the cluster's pre-delete census and save the exact command/result in
      the journal.
- [x] Add or run the smallest live-sibling behavior fence before deleting.
- [x] Delete only the enumerated paths and make only the listed shared edits.
- [x] Transition the corresponding register row to `deleted` in the same diff.
- [x] Run the affected tests; zero affected-test failures are allowed.
- [x] Run typecheck and the production build as absolute-green gates.
- [x] Run scoped lint over every deleted/edited file and every referencer
      touched by the fresh census; no scoped diagnostic is allowed.
- [x] Search generated `.vite/manifest.json`, `sw.js`, and built assets for the
      retired identifiers; also prove protected sibling identifiers remain.
- [x] Update the journal with denominators, durations, baseline-relative
      comparison, diff fence, and register-validator result.
- [x] Stop the cluster if any new consumer, route, dynamic import, test/e2e
      dependency, package dependency, generated chunk, or service-worker
      reference appears.

The per-cluster gate, run from `apps/runtime-dashboard`, is:

```bash
corepack pnpm run typecheck
corepack pnpm run build
corepack pnpm exec vitest run <affected tests>
corepack pnpm exec eslint <all surviving files touched by the cluster census>
```

The full baseline-relative lint and complete Vitest suite run at wave end and
again at closure, not after every cluster. `typecheck`, `build`, every affected
test, and every scoped-lint invocation must return zero after each cluster.

The generated-output census runs against:

```text
../../_build/apps/runtime-dashboard/dist/.vite/manifest.json
../../_build/apps/runtime-dashboard/dist/sw.js
../../_build/apps/runtime-dashboard/dist/assets/**
```

## Task 1 - Establish The Disposition Authority And Negative Controls

**Files:**

- Create: `architecture/atlas_surfaces/frontend-disposition-register.schema.json`
- Create: `architecture/atlas_surfaces/frontend-disposition-register.json`
- Create: `architecture/atlas_surfaces/check_frontend_disposition_register.py`
  as the co-located standalone validator authorized by DS19
- Create: the typed baseline-debt manifest/schema and the projected report
- Modify: `DS19-false-substrate-strangle-wave-journal.md`

**Interfaces:**

- Consumes: DS1 readiness rows, DS2 adoption rows, tracked Git paths, resolved
  imports/routes/tests/e2e, and exact consumer references.
- Produces: one typed row per seeded unit with disposition, current evidence,
  successor where applicable, and strangle state; one generic validation
  command used by every later task.

- [ ] Seed the register without changing application behavior. Browser signing
      is `rebind_pending`/protected with a planned DS12 strangle; the six
      clusters remain `delete_pending` until their deletion commits.
- [ ] Add a negative fixture in which a `deleted` row still resolves a tracked
      path. The validator must fail.
- [ ] Add a negative fixture in which a `rebound` row names a successor but no
      consumer. The validator must fail.
- [ ] Add malformed, present-but-unresolvable, dynamic-import, and sibling-
      consumer variants. Each must fail for the property, not a marker string.
- [ ] Remove the corruption and run the validator against the real register;
      it must pass before any deletion starts.

Acceptance signal: one generic register/checker pair covers future rows
without per-cluster code, and its corruption probes demonstrate P29/P31-P33.

## Task 2 - Retire Collaboration Without Touching Review WS

**Delete:**

```text
apps/runtime-dashboard/src/features/collaboration/components/ActivityFeed.tsx
apps/runtime-dashboard/src/features/collaboration/components/CollaborationToolbar.tsx
apps/runtime-dashboard/src/features/collaboration/components/CollaborativeCursors.tsx
apps/runtime-dashboard/src/features/collaboration/components/CommentThread.tsx
apps/runtime-dashboard/src/features/collaboration/components/PresenceBubbles.tsx
apps/runtime-dashboard/src/features/collaboration/components/ShareDialog.tsx
apps/runtime-dashboard/src/features/collaboration/components/index.ts
apps/runtime-dashboard/src/features/collaboration/hooks/useActivityFeed.ts
apps/runtime-dashboard/src/features/collaboration/hooks/useCollaborationSession.ts
apps/runtime-dashboard/src/features/collaboration/hooks/useComments.ts
apps/runtime-dashboard/src/features/collaboration/hooks/usePresence.ts
apps/runtime-dashboard/src/features/collaboration/index.ts
apps/runtime-dashboard/src/features/collaboration/state/useCollaborationStore.test.ts
apps/runtime-dashboard/src/features/collaboration/state/useCollaborationStore.ts
apps/runtime-dashboard/src/features/collaboration/types.ts
```

**Shared edits:**

- `apps/runtime-dashboard/src/app/realtime/types.ts`: remove the four
  `collab.*` channel members, collaboration request union member, and four
  collaboration event/snapshot DTOs; narrow the WebSocket request to review.
- `apps/runtime-dashboard/src/app/realtime/websocketTransport.ts`: remove
  `/api/v1/collaboration/live` and its switch arms; retain
  `/api/v1/review/live` and `review.cursor|lock|presence`.
- `apps/runtime-dashboard/src/app/realtime/realtimeClient.ts`: remove only the
  four `collab.*` dispatch arms.
- `apps/runtime-dashboard/src/features/index.md`: remove the collaboration row.

Flags, permissions, telemetry, locale catalogs, dependencies, and the lockfile
are outside this deletion unit. They remain registered for their owning
slices; the D4-frozen `ru` catalog is not edited.

**Behavior fence:** retain the existing review-collaboration surface test and
prove the surviving transport still builds `/api/v1/review/live` for the three
`review.*` channels. No marker-only test is added.

**Fresh census:**

```bash
git ls-files 'apps/runtime-dashboard/src/features/collaboration/**'
rg -n -S '@/features/collaboration|features/collaboration|/api/v1/collaboration|collab\.(activity|comments|cursors|presence)|CollaborationRealtimeSubscriptionRequest' apps/runtime-dashboard/src apps/runtime-dashboard/e2e packages
rg -n -S '/api/v1/review/live|review\.(cursor|lock|presence)' apps/runtime-dashboard/src/app/realtime apps/runtime-dashboard/src/features/runs
```

**Focused gate:**

```bash
corepack pnpm exec vitest run src/app/realtime/useReviewCollaborationSurface.test.tsx src/features/runs/routes/runDetailSurfaces.test.tsx
```

Acceptance signal: every collaboration feature and phantom REST/WS identifier
is absent from source and built output, while the real review URL/channels and
review surface tests remain live. Disposition-only flags remain unchanged.

## Task 3 - Retire Orphan Onboarding, Preserve Operator Craft

**Delete:**

```text
apps/runtime-dashboard/src/features/onboarding/GuidedTour.test.tsx
apps/runtime-dashboard/src/features/onboarding/GuidedTour.tsx
apps/runtime-dashboard/src/features/onboarding/OnboardingProvider.tsx
apps/runtime-dashboard/src/features/onboarding/index.ts
apps/runtime-dashboard/src/features/onboarding/tours.ts
apps/runtime-dashboard/src/features/onboarding/types.ts
```

There are no shared telemetry, locale, dependency, or lockfile edits in this
cluster. Those residues are outside the registered deletion unit.

**Fresh census and protected sibling:**

```bash
git ls-files 'apps/runtime-dashboard/src/features/onboarding/**'
rg -n -S '@/features/onboarding|features/onboarding|polisyos\.runtime\.onboarding|GuidedTour|OnboardingProvider' apps/runtime-dashboard/src apps/runtime-dashboard/e2e packages
rg -n -S 'polisyos\.operatorCraft\.onboarding|phase36\.onboarding|reading-onboarding|onboarding\.step\.completed' apps/runtime-dashboard/src apps/runtime-dashboard/e2e
```

**Focused gate:**

```bash
corepack pnpm exec vitest run src/features/runs/domain/operatorCraft.test.ts src/features/runs/routes/runDetailSurfaces.test.tsx
```

Acceptance signal: the orphan tour/provider and its own storage key are absent,
while Operator Craft onboarding remains reachable and tested.

## Task 4 - Delete The Empty Feature-Layout Owner

**Delete:**

```text
apps/runtime-dashboard/src/features/layout/components/README.md
```

No feature test, story, type, export, route, package dependency, or feature-
index row belongs to this placeholder.

**Fresh census and focused fence:**

```bash
git ls-files 'apps/runtime-dashboard/src/features/layout/**'
rg -n -S '@/features/layout|features/layout|src/features/layout' apps/runtime-dashboard/src apps/runtime-dashboard/e2e packages
git ls-files 'apps/runtime-dashboard/src/app/layout/**'
corepack pnpm exec vitest run src/app/layout/layoutSurfaces.test.tsx
```

Acceptance signal: `features/layout` is absent and every `app/layout` owner and
test remains untouched.

## Task 5 - Delete Three Zero-Consumer Web Workers, Preserve The PWA Worker

**Delete:**

```text
apps/runtime-dashboard/src/workers/dagLayout.worker.ts
apps/runtime-dashboard/src/workers/dataTransform.worker.ts
apps/runtime-dashboard/src/workers/jsonParse.worker.ts
```

**Shared edit:** change the example in
`apps/runtime-dashboard/src/workers/useWorker.ts` so it demonstrates a generic
worker factory without naming a deleted file. Preserve the hook and its test.

**Fresh census and protected sibling:**

```bash
git ls-files apps/runtime-dashboard/src/workers/dagLayout.worker.ts apps/runtime-dashboard/src/workers/dataTransform.worker.ts apps/runtime-dashboard/src/workers/jsonParse.worker.ts
rg -n -S 'dagLayout\.worker|dataTransform\.worker|jsonParse\.worker|new[[:space:]]+(Shared)?Worker|[?&]worker' apps/runtime-dashboard/src apps/runtime-dashboard/e2e
rg -n -S 'virtual:pwa-register|registerSW|self\.__WB_MANIFEST|navigator\.serviceWorker' apps/runtime-dashboard/src/main.tsx apps/runtime-dashboard/src/sw.ts apps/runtime-dashboard/src/app/providers/OfflineQueueProvider.tsx
corepack pnpm exec vitest run src/workers/useWorker.test.tsx
```

Acceptance signal: no deleted worker filename appears in source, Vite manifest,
chunks, or `sw.js`; PWA registration and the generic hook remain.

## Task 6 - Delete The Duplicate Clerk Index Route

**Delete:**

```text
apps/runtime-dashboard/src/features/clerk/route.tsx
```

**Shared edits:** remove `clerkChatRoute` from
`apps/runtime-dashboard/src/features/clerk/index.ts` and remove its import and
child insertion from `apps/runtime-dashboard/src/app/routes/routes.tsx`.

**Behavior fence:** extend
`apps/runtime-dashboard/src/app/routes/routes.test.tsx` to select the root
route's `children`, assert exactly one `index === true` child, and assert that
child's `handle.routeId` is `dashboard.home`. Do not merely grep for
`clerkChatRoute`.

**Fresh census and focused gate:**

```bash
git ls-files apps/runtime-dashboard/src/features/clerk/route.tsx
rg -n -S 'clerkChatRoute|routeId:[[:space:]]*"clerk\.chat"|@/features/clerk/route\.tsx|index:[[:space:]]*true' apps/runtime-dashboard/src apps/runtime-dashboard/e2e
rg -n -S '@/features/clerk/routes\.public|ClerkChatPage|enableClerkMode' apps/runtime-dashboard/src apps/runtime-dashboard/e2e
corepack pnpm exec vitest run src/app/routes/routes.test.tsx
```

Optional browser preservation receipt:

```bash
corepack pnpm exec playwright test e2e/runtime-dashboard.visual.spec.ts --project=chromium --grep 'clerk chat shell-lite'
```

Acceptance signal: the runtime route tree contains one home index, while the
mode-aware Clerk home and its public chunk remain.

## Task 7 - Strangle Only The Legacy WhatIf Parameter Subgraph

**Delete:**

```text
apps/runtime-dashboard/src/features/whatif/components/ImpactPreview.tsx
apps/runtime-dashboard/src/features/whatif/components/ParameterSlider.tsx
apps/runtime-dashboard/src/features/whatif/components/ScenarioSnapshot.tsx
apps/runtime-dashboard/src/features/whatif/components/WhatIfPanel.tsx
apps/runtime-dashboard/src/features/whatif/components/index.ts
apps/runtime-dashboard/src/features/whatif/state/useWhatIfStore.ts
apps/runtime-dashboard/src/features/whatif/types.ts
```

**Shared edits:**

- In `apps/runtime-dashboard/src/features/whatif/ScenarioWorkbench.tsx`, remove
  the legacy type/`WhatIfPanel` imports, `parameters` and
  `onParametersChange` props/defaults, and the conditional legacy branch.
- In `apps/runtime-dashboard/src/features/whatif/index.ts`, remove only legacy
  type/component/store exports.
- Leave all locale catalogs unchanged; D4 freezes `ru`, and DS19 does not
  create cross-catalog parity churn to delete copy outside the code subgraph.
- Do not add cleanup or migration code for inert
  `polisyos.runtime.whatif` localStorage.
- Preserve `ScenarioWorkbench`, `ScenarioInterventionEditor`,
  `ScenarioValidationPanel`, API scenario/counterfactual hooks, and
  `enableWhatIfAnalysis`.

**Fresh census and focused gate:**

```bash
rg -n -S 'WhatIfPanel|ParameterSlider|ImpactPreview|ScenarioSnapshot|useWhatIfStore|polisyos\.runtime\.whatif|whatIf\.' apps/runtime-dashboard/src apps/runtime-dashboard/e2e
rg -n -S '<ScenarioWorkbench|parameters=|onParametersChange=' apps/runtime-dashboard/src/features/whatif apps/runtime-dashboard/src/features/runs
rg -n -S 'ScenarioWorkbench|ScenarioInterventionEditor|ScenarioValidationPanel|enableWhatIfAnalysis|counterfactual' apps/runtime-dashboard/src apps/runtime-dashboard/e2e
corepack pnpm exec vitest run src/features/runs/routes/runDetailSurfaces.test.tsx
```

Protected browser receipt:

```bash
corepack pnpm exec playwright test e2e/journeys/counterfactual-flow.spec.ts --project=chromium
```

Acceptance signal: the local parameter/store branch and storage key disappear,
while Overview continues to mount the API-backed workbench and its
counterfactual journey passes.

## Task 8 - Register Browser Signing And Remaining Wire-Or-Retire Units

No browser-signing source is writable in this task. The fresh protection
census is:

```bash
git grep -n 'buildSignedPublicDecisionPacket(' -- apps/runtime-dashboard/src
git grep -n 'verifySignedPublicDecisionPacket(' -- apps/runtime-dashboard/src
rg -n -S 'public/decisions/:signedId|buildSignedPublicDecisionPacket|verifySignedPublicDecisionPacket' apps/runtime-dashboard/src apps/runtime-dashboard/e2e
```

The register evidence must include the three live builder consumers:

```text
apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx
apps/runtime-dashboard/src/features/runs/components/OperatorCraftPanel.tsx
apps/runtime-dashboard/src/features/runs/components/PublicationReadinessPanel.tsx
```

It must also include
`features/runs/routes/PublicDecisionViewerPage.tsx`, the
`/public/decisions/:signedId` route, `publicationPacket.ts`, and
`e2e/journeys/trust-framing-negative-traces.spec.ts`. The entry records a live
P05/P10 risk and DS12 successor responsibility; it must not claim
zero-consumer or `deleted`.

Add disposition-only rows for the 37 uncalled OpenAPI operations and all four
consumer-missing flags. Do not implement them. Acceptance signal: every row
names an owner/revisit condition and no application diff is attributed to
this task.

## Task 9 - Close The Wave Without Merging

- [x] Re-run every cluster census against source, tests/stories/e2e, package
      manifests, routes, Vite manifest, built assets, and `sw.js`.
- [x] Re-run the generic disposition validator and all corruption probes.
- [x] Run the dashboard typecheck, lint report/comparison, full Vitest
      report/comparison, and production build. The dashboard architecture
      checker remains baseline-red with 36 violations in files unchanged by
      DS19; it is recorded as no-regression debt, not repaired in this slice.
- [x] Run repository architecture guardrails:

```bash
uv run polisyos-tools architecture guardrails check
```

- [x] Prove `package.json` and `pnpm-lock.yaml` are unchanged after the already
      isolated baseline-repair commit; no deletion-cluster lockfile exception
      exists.

- [x] Verify patch hygiene and branch scope:

```bash
git diff --check
git status --short
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

- [x] Re-open the failure/repair register and record the final pattern pass in
      the journal.
- [x] Mark each completed disposition only after its absence/consumer proof is
      current. Mark browser signing protected/current.
- [x] State the exact truthful closeout:
      `implementation_complete_no_merge_baseline_red` while inherited lint or
      Vitest failures remain, or `review_ready_no_merge` if all gates are
      absolutely green.
- [x] Do not merge, push, publish, or archive the task automatically.

## Logical Review And Commit Boundaries

The future executor should keep these independently rejectable boundaries:

1. typed disposition authority, baseline-debt manifest, negative controls,
   and report projection;
2. collaboration retirement and review-WS fence;
3. orphan onboarding retirement;
4. empty layout placeholder retirement;
5. three worker-module retirement and PWA fence;
6. duplicate Clerk route retirement and route-tree fence;
7. legacy WhatIf subgraph retirement and API-workbench fence;
8. register-only signing/wire-or-retire reconciliation;
9. closeout receipts and no-merge handoff.

No cluster is folded into another merely because its deletion is small: each
has a distinct protected sibling and can be approved or rejected independently.

## Pattern Pass

| Pattern | Existing risk | DS19 closure move | Acceptance signal |
| --- | --- | --- | --- |
| P06 | Audit links and compatibility names can drift toward deleted paths | Pin historical evidence to Phase-A and remove live imports/exports of the predecessor | No current owner points through a deleted compatibility path |
| P13 | A deletion wave could create a schema/report per cluster or migration ceremony for inert storage | One register, one validator, one journal; no localStorage migration or replacement capability | Net source denominator shrinks and governance artifacts stay bounded |
| P27 | Empty/parallel owners obscure the canonical review, onboarding, layout, and scenario homes | Delete parallel owners and explicitly fence canonical siblings | Owner-first census names exactly one surviving owner per concept |
| P28 | Legacy routes, branches, transports, and stores remain callable after the replacement exists | Delete predecessor and its export/route/transport in the same register transition | Fresh source and built-output census cannot reach the predecessor |
| P29 | A hand-authored `deleted` marker could pass while code/chunks still exist | Validator recomputes tracked paths and consumers; build census checks real manifest/SW/assets | Remove-property/keep-marker and corrupt-reference probes fail |
| P31 | Per-row hand checks miss a sibling import, dynamic route, or generated consumer | One generic register validator scans all declared path and consumer surfaces | A sibling-consumer adversarial row fails without new checker code |
| P32 | Evidence path presence is mistaken for proof | Evidence must resolve to the pinned/current content; missing/unresolved evidence fails closed | Present-but-fake and malformed references fail |
| P33 | The named DS1 probe becomes the whole specification | Add dynamic-import, alias, malformed, generated-chunk, and sibling-consumer variants | Near variants fail for the same generic property |
| P34 | Known lint/Vitest failures are dismissed as unrelated | Parent reproduction establishes origin; affected subsets run per cluster and the full manifests are exact-compared at wave end and closure | No new identity and no false green claim; no-merge state remains explicit |

## Closure Contract

DS19 is implementation-complete only when:

- the disposition register is schema-valid, generic-validator-valid, seeded
  from DS1/DS2, and every corruption probe fails as intended;
- each ratified deleted row has no tracked path, static/dynamic import, route,
  identifier, test/story/e2e dependency, manifest/package entry, built chunk,
  or service-worker reference;
- every protected sibling remains present and passes its focused behavior
  fence;
- browser signing remains unchanged and registered with all live consumers;
- typecheck, architecture checks, production build/PWA, postbuild security, and
  focused tests are absolutely green;
- lint and Vitest introduce no identity outside their exact baseline manifests;
- the journal records every command, duration, denominator change, and final
  pattern pass;
- `git diff --check` is clean and changed paths stay within DS19's declared
  fence;
- the final state truthfully says no-merge and no merge or push occurred.

Anything less remains `active`: a deleted row with a reference is not closed,
a protected live consumer removed is a rollback, a count-only baseline
comparison is insufficient, and a baseline-relative pass is never reported as
an absolute-green suite.
