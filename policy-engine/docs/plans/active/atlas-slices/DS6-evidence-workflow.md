---
plan_id: atlas-ds6-evidence-workflow
title: "DS6 - Evidence Workflow & Instrumentation"
type: slice-plan
status: execution_authorized_light_half
created: 2026-08-11
revised: 2026-08-11
last_verified: 2026-08-11
stability: measured_execution_plan
slice: DS6
baseline_commit: c1a89b6cf0c63573abad6b0ca8374e16b78c47dd
execution_base_commit: c1a89b6cf0c63573abad6b0ca8374e16b78c47dd
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
ds4_plan: ./DS4-status-grammar-rebinding.md
ds4_journal: ./DS4-status-grammar-rebinding-journal.md
ds4_closure: ./DS4-status-grammar-rebinding-closure.md
ds5_plan: ./DS5-enforcement-waist.md
journal: ./DS6-evidence-workflow-journal.md
audiences: [PUBLIC, REVIEWER, EXPERT, MACHINE]
owner: team-frontend
architecture_owner: team-architecture
depends_on:
  - ./DS4-status-grammar-rebinding-closure.md
  - ../../../reference/policy-design-case-failure-patterns.md
---

# DS6 - Evidence Workflow & Instrumentation

**Goal:** Build the machinery that makes Atlas `stable` and `honest` claims
measurable. DS6 owns evidence capture and storage, readiness-to-evidence
reconciliation, health instrumentation, and the honesty-comprehension protocol;
it does not manufacture authority or ship product screens.

**Architecture:** Evidence is a typed, content-bound receipt produced by the
real verification path, persisted under one storage convention, reconciled
against the surface-readiness ledger, and consumed by maturity/CI gates. A
candidate, browser marker, prose table, or absent violation is never promoted
into a pass. Gate predicates are frozen at admission as `recomputed`,
`independently_reconciled`, `consumer_asserted`, `institutionally_supplied`, or
`not_established`; the last three cannot carry an authority-grade gate. The
seven Atlas health metrics and the honesty protocol are measurements, not
policy authority.

**Tech stack:** TypeScript 5, React 19, Vitest, Storybook browser Vitest,
axe-core, Playwright, Node design checks, Python governed-artifact checkers,
JSON Schema, and repository architecture guardrails.

## Binding fence and execution posture

- Worktree: `.worktrees/atlas-ds6`; branch:
  `codex/atlas-ds6-evidence-workflow`; exact current-`main` base:
  `c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`.
- The main checkout's uncommitted
  `src/polisyos/data_forge/read_api/catalog.py` edit and every other uncommitted
  main-checkout byte are foreign to this worktree. Entry status and the scoped
  base diff are recorded in the journal.
- This session may write only this plan/journal,
  `apps/runtime-dashboard/src/shared/i18n/**`, and new probe paths under
  `apps/runtime-dashboard/src/test/a11y/**`.
- This session must not write the shared governed Atlas-surface artifacts named
  under **Deferred execution package**. DS5-C21 owns that contended resource
  until it merges. Required deltas are specified there, not applied here.
- This session must not start Playwright, journeys, visual tests, a dev server,
  Storybook, full lint, full typecheck, full build, or whole-suite Vitest. The
  governed host-contention measurements and exact waiting commands are recorded
  under **Deferred execution package**.
- Allowed verification is focused Vitest over touched files with at most two
  workers and the single-process Node design checks `a11y:contrast`,
  `a11y:motion`, and `a11y:color-blind`.
- No product surface, DS5 path, GY path, a11y denominator, baseline suppression,
  skip, quarantine, tolerance widening, CI edit, merge, push, rebase, force
  push, or stash-as-storage. One scoped commit follows independent review for
  each entered cluster.
- Only DS6-C01-R1 is authorized now, followed by DS6-C07 after its independent
  source review. DS6-C03 through DS6-C06 and DS6-C13 remain stopped behind
  their existing contended/heavy gates and explicit continuation authorization.

## DS6-C00: inherited entry contract and stop gate

DS4 closed and merged at `7f450eb7b`; that commit is an ancestor of the entry
base. DS6 has been unblocked since 2026-08-01 and had no slice plan before this
cluster.

The inherited entry contract is quoted verbatim from
`docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`, DS6:

> **Inherited entry contract from DS4 (registered 2026-08-01):** DS6 owns the
> two evidence debts DS4 refused to absorb. **(a) Three i18n parity failures**
> (`panels.agentPipeline.overBudget` en/uk/ru in
> `shared/i18n/parity.test.ts:88` — count-sensitive message without ICU plural
> syntax or an allowlist entry). Ruling 2 moved this class from DS5 to DS6; the
> register class is `i18n-count-message-parity` and the baseline comparator
> accepts exactly these three signatures. **(b) Four axe-`incomplete` contrast
> clusters** — C01 neutral `Badge`; C06 `ProvenancePopover` +
> `ProvenanceMiniGraph`; C09 `TimeSemanticsLabel` inheritance; C14
> `CandidateFrame`, `NegativeCertificateCard`, `WeakestLinkExplainer`. These are
> neither violations nor passes: translucent/gradient ancestors defeat computed
> contrast, so axe returns `incomplete`. DS4's automated a11y denominator
> (85/85 component, 21/21 browser) is green *around* them and does not count
> them green. **DS6 lands the real-browser opaque-background probe** that
> computes a WCAG-AA result for each named identity without attributing an
> `incomplete` node to the source — and **creates the typed register row**,
> since DS4 left this class as prose only and prose does not survive a census.
> DS6 also owns independent visual + semantic verification of the DS8-owned
> `adjacent-print-export` regression.

The two debts are the light-half execution target. DS8 print verification is a
separate DS6 obligation, not a third inherited debt and not authorized in this
session.

### Measured entry receipt

All entry measurements are from the complete stated set at the entry base.
Commands and raw receipts are in the journal.

| Set or gate | Receipt | Consequence |
| --- | --- | --- |
| worktree attachment | clean `codex/atlas-ds6-evidence-workflow` at exact base | append-only execution may begin |
| main-checkout isolation | zero DS6 diff for `src/polisyos/data_forge/read_api/catalog.py`; zero uncommitted main bytes copied | foreign work remains excluded |
| tracked repository paths | 9,756 paths; a complete `git grep` over `HEAD` finds zero `DS6-C[0-9]` identities | C00 is the first DS6 cluster; numbering is not inherited |
| locale catalogs | 2,449 string leaves each; identical sorted key sets across en/uk/ru | active parity and frozen continuity can be separated without deleting `ru` |
| count-sensitive messages | 84 per catalog; 56 ICU, 28 invariant-form; three invariant paths absent from the allowlist | the first failed assertion masks two later identities; C01 closes the class, not only the first anchor |
| registered i18n red | 1 file, 4 tests: 1 pass, 3 failures, exactly the registered en/uk/ru `overBudget` signatures | valid red-first receipt; any replacement identity is drift |
| contrast source denominator | four owner clusters, seven declared source identities | DS6 creates a separate 7/7 rendered-contrast receipt; it does not alter 85/85 or 21/21 |

Entry stops at the last clean commit if a foreign main/DS5/GY path appears, a
new baseline identity appears, a cluster exceeds its cap, the probe needs a
product-surface change, or a gate would treat an incomplete/marker as evidence.

## Authority and semantic rulings

1. `docs/brand/ATLAS_SOURCE_OF_TRUTH.md`, D4 at ratification commit
   `7b6933770`, controls locale meaning: `uk` is primary, `en` is
   baseline/fallback, and `ru` is `legacy_continuity_frozen`—not used and not
   deleted. C01-R1 replaces three-way active parity with an active `uk`/`en`
   count-message gate and freezes Russian continuity with exact cardinality,
   sorted-key, and sorted `[path,value]` fingerprints. The frozen assertions,
   not absence from active parity, carry “not deleted” and value continuity.
   DS5 separately owns removal of active `ru` exposure; DS6 does not claim that
   mechanic complete.
2. The DS4 journal's four-cluster table is the contrast class authority until
   DS6 creates a typed row. Its 85/85 component and 21/21 browser receipts stay
   green around the class and never count `incomplete` green.
3. `frontend-baseline-debt-manifest.json` registers only the three observed
   `overBudget` failures. The focused Vitest loop aborts at the first failed
   expectation per locale, so its green repair must also prevent the two
   independently censused later paths from replacing those failures. This is a
   P31 class repair, not baseline expansion.
4. Axe's browser-computed `color-contrast` data is the rendered contrast
   authority for the probe. Token math and runtime ancestor blending already
   exist and remain distinct; DS6 will not create a third WCAG calculator.
5. The research-input INT-R3 benchmark thresholds remain `not_established`.
   DS6 may create the instrument/protocol seed but may not invent promotion
   thresholds or encode an unresolved research question as a contract.

## Pattern pass and capability truth

The governing register is
`docs/reference/policy-design-case-failure-patterns.md`.

| Pattern | Entry risk | Correct pattern / acceptance signal |
| --- | --- | --- |
| P01/P02/P03 | prose-only evidence or an unwired validator | producer -> typed persisted receipt -> orchestration bridge -> maturity/readiness consumer -> audit surface, or a precise missing label |
| P05/P15 | test output or LLM prose becomes authority | evidence remains candidate until the real verifier content-binds it; no prose/LLM promotion |
| P07/P08 | unreplayable result or conflated event/valid time | schema/rule version plus explicit collection, observation, and verification times |
| P09/P10 | warning/incomplete treated as closure; semantic test absent | lifecycle is explicit; negative and behavioral witnesses fail for the right reason |
| P27/P30 | a second registry or generic provenance label | extend the canonical governed owner; use source/producer-specific names |
| P29/P33 | marker or taught example passes | run the real path; preserve markers while falsifying opacity, identity, evidence, or ledger premise |
| P31 | patch only the visible `overBudget` assertion | complete count-message census and a class-level rule prevent rotated failures |
| P34 | excluded heavy failure called green | every unrun gate is a named non-receipt with a waiting command |
| P35/P36 | sampled denominator or authority by adjacency | enumerate the complete set and cite the controlling finding/ruling |
| P37 | declared evidence predicate carries a gate | recompute or independently reconcile before authority-grade admission |

At entry, the contrast class is `artifact_missing`, `verification_missing`,
`surface_missing`, and `semantic_test_missing`; the i18n implementation is
`verification_missing` until C01. The full evidence workflow is
`producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing`, `surface_missing`, and `semantic_test_missing`. These
labels close only when their named cluster supplies the capability link.

## Universal cluster protocol

Every entered cluster follows the established DS5 shape:

1. Record `git status -sb`, attached HEAD, preflight file set, current authority
   row, and inherited baseline identities.
2. Add or preserve the named red first. A timeout, missing output, skipped
   browser, or lost log is a non-receipt.
3. Prefer wire-existing, then extend, then consolidate, and only then build new.
4. Persist every evidence/status transition through its canonical producer.
   Never hand-author generated output or copy a source-of-truth vocabulary.
5. Run blast-radius gates and marker-preserving corruption witnesses. Full
   waves run only at the declared serialized boundary.
6. Freeze source, obtain independent review against the named governing
   artifact, repair Important/Critical findings, then commit once.
7. Re-read branch attachment, commit, touched file set, denominators, and gate
   receipts from the branch. Leave the cluster clean.

A cluster measured above its cap stops at the preceding clean commit and is
re-cut with the next continuous number. No cap is enlarged after entry.

**Content-binding sizing law (P31 class fix):** A cluster that writes a
content-bound governed artifact also owns every induced re-anchor of a receipt
that pins it. The induced path counts against the cap. This replaces the
instance-by-instance report accounting with one structural rule for every
disposition-register writer; the induced status-inventory receipt is not an
optional tail or a later-cluster cost.

### Binding review bars

- **Mechanism-round breaker:** a fix round that changes zero bytes in mechanism
  paths (production source plus the checker or scanner implementing the
  mechanism) does not consume the two-fix breaker. Test-only and
  receipt/documentation-only rounds are free; prove the classification with a
  scoped `git diff` over mechanism paths.
- **Behavioral gate:** `policy-design-case-failure-patterns.md` P29/P33 sets the
  bar. The real classifier/verifier runs and the marker-preserving falsification
  turns it red; marker/string/schema-presence checks are insufficient.
- **Predicate provenance:** P37 sets the bar. Every predicate a gate depends on
  is frozen at admission; `consumer_asserted`, `institutionally_supplied`, and
  `not_established` fail closed for authority-grade transitions.
- **Evidence completeness:** the master DS6 deliverable and P01/P02/P03 set the
  bar. A contract without producer, artifact, bridge, consumer, verification,
  and audit/API/dashboard surface is reported with the exact missing labels.
- **Closure signals:** governed JSON Schema plus the register's established
  simple command-and-condition rows set the bar; no review invents a stronger
  mechanism for a debt-only row.
- **Implementation boundaries:** this plan and the master DS6 section set the
  boundary. Every finding or constraint cites the artifact that establishes
  it. A product-surface repair, denominator edit, or neighboring-slice change
  is refused.
- **Duplication reporting:** when two implementations/artifacts own one concept,
  record both paths, complete counts, canonical authority, migration state, a
  concrete divergence, and comparator status. Report only unless the cluster
  explicitly owns the strangle.
- Any review conflict with a ratified ruling or this plan is a stop-and-ask,
  not a silent selection of the stricter interpretation.

## Cluster cut and declared path caps

Every cap counts unique repository paths, including the journal, generated
reports, and induced content-bound re-anchors. Future clusters enumerate their
exact candidate set before entry; the cap is a ceiling, not permission to fill
it.

### Task 0 — DS6-C00: open the measured slice

**Paths:** this plan and journal. **Declared path cap: 2.**

Acceptance: inherited text is verbatim; both boundaries, standing laws,
pattern pass, full deliverable cut, exact entry base, receipts, and executable
deferred package are present; independent review has no open Important or
Critical finding.

**Expected commit:** `DS6-C00 open evidence workflow slice`.

### Task 1 — DS6-C01: close count parity and freeze Russian continuity

**Paths:** `apps/runtime-dashboard/src/shared/i18n/parity.test.ts` and journal.
**Declared path cap: 2.**

Red first: preserve the registered three `overBudget` failures. Repair the
invariant-count class without rotating failures to the two masked paths.
Separate active `uk`/`en` parity from a SHA-256-bound, exact-cardinality Russian
key-set assertion. A deletion witness must turn that frozen assertion red.
Locale messages and product exposure are unchanged.

Acceptance: the focused file is green; all three registered identities are
gone; no new identity appears; the assertion named
`keeps the legacy-continuity Russian key set frozen` is the durable carrier of
“frozen”; an actual one-key deletion produces a recorded red; independent
review is clean.

**Expected commit:** `DS6-C01 close count parity and freeze Russian keys`.

### Task 1R — DS6-C01-R1: justify count exemptions and repair active plurals

**Paths:** `apps/runtime-dashboard/src/shared/i18n/parity.test.ts`,
`apps/runtime-dashboard/src/shared/i18n/locales/en.json`,
`apps/runtime-dashboard/src/shared/i18n/locales/uk.json`,
`docs/plans/active/atlas-slices/DS6-evidence-workflow.md`, and
`docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md`.
**Declared path cap: 5.**

Replace the key-only count allowlist with path-specific non-empty reasons;
recompute active `en`/`uk` non-ICU count identities through the real ICU helper;
reject missing, blank, stale, and newly introduced identities; and exercise the
real formatter for the eight repaired messages. Parse plural syntax with the
same `IntlMessageFormat` dependency as the formatter so malformed plural
templates fail regardless of an exemption reason. Russian remains
`legacy_continuity_frozen`, outside the active count rule, with the exact
2,449-key, sorted-key, and value-sensitive leaf fingerprints preserved.

Acceptance: the focused parity file has exactly 15 passing tests, including the
three rejection witnesses and eight formatter rows; `ru.json` remains byte
unchanged; independent source review precedes the cluster commit.

**Expected commit:** `DS6-C01-R1 justify count exemptions and repair active plurals`.

### Task 2 — DS6-C02: add the opaque-background contrast probe

**Paths:** the typed classifier/registry, its focused contract test, one
test-only Storybook browser fixture under `src/test/a11y/**`, and journal.
**Declared path cap: 4.**

Red first: classifier tests prove exact C01/C06/C09/C14 -> 1/2/1/3 mapping,
seven unique identities, 7/7 numeric passes, and hard failure for incomplete,
missing, duplicate, unknown, nonnumeric, inapplicable-only, or nonopaque
evidence. An incomplete result has no source-attributed receipt.

The browser fixture renders all seven identities on an asserted opaque
background and uses axe's real `color-contrast` checks. The browser lane is
written but not run in this session. The old 85/85 and 21/21 receipts are not
edited or reinterpreted.

Acceptance now: focused non-browser contract passes, source registry is exactly
seven, browser fixture is reviewable, and its skipped execution is a named
non-receipt. Eventual acceptance: the serialized real-browser lane emits 7/7
numeric WCAG-AA receipts with zero violations/incomplete and no source
attribution for any incomplete node.

**Expected commit:** `DS6-C02 add opaque rendered-contrast probe`.

### Task 3 — DS6-C03: rebind the i18n baseline lifecycle

**Gate:** DS5-C21 merged, GY heavy-lane release granted, whole-suite Vitest
receipt green, and explicit continuation authorization. **Declared path cap:
9.**

Own the baseline manifest/schema producer, both relevant governed tests, the
disposition producer/generated register, report, induced status-inventory
re-anchor, and journal. Admit exactly the existing open triple or an
empty/resolved/exit-0 state; reject any other identity or signature. Transition
`baseline-test-i18n-count-debt` to `repaired` only from the measured full-suite
receipt.

### Task 4 — DS6-C04: admit the typed rendered-contrast debt

**Gate:** DS5-C21 merged and explicit continuation authorization.
**Declared path cap: 6.**

Extend the canonical disposition producer; generate the register/report;
exercise its governed tests; induce the status-inventory re-anchor; append the
journal. Create exactly one `baseline_test_debt` supplemental row for seven
source identities. Before the browser receipt it remains
`rebind_pending/open_debt`; prose ceases to be the class authority.

### Task 5 — DS6-C05: execute the serialized heavy evidence wave

**Gate:** explicit GY-lane release. **Declared path cap: 1** (journal receipt
only; a failing source repair is a separately re-cut cluster and may not change
a product surface under this plan).

Run the exact commands in the deferred package. A pass records the separate
7/7 rendered-contrast denominator. A browser failure remains evidence debt;
DS6 does not repair product components in this cluster.

### Task 6 — DS6-C06: close the typed rendered-contrast debt

**Gate:** C04 typed row exists and C05 has a 7/7 browser receipt.
**Declared path cap: 6.**

Through the canonical producer, transition the same row to `repaired`, attach
the actual repair/evidence commit, regenerate register/report and induced
status receipt, run corruption probes, and append the journal.

### Task 7 — DS6-C07: define the evidence artifact and storage convention

**Declared path cap: 10.** Define strict typed receipt DTO/schema, authority
purpose, provenance, rule/schema versions, audience, collection/observation/
verification times, content binding, retention, and canonical storage path.
No `stable` consumer closes here: `bridge_missing` and `consumer_missing`
remain explicit.

### Task 8 — DS6-C08: wire browser, keyboard, and automated evidence capture

**Declared path cap: 10.** Wire existing runners to the canonical artifact
producer/persistence path. Store positive and negative receipts without
expanding a product denominator. Manual AT remains separate.

### Task 9 — DS6-C09: wire manual AT evidence and maturity consumption

**Declared path cap: 10.** Admit human evidence through a typed reviewer/AT
protocol with bounded authority and expiry; wire the component maturity bar to
the evidence store. `stable` without current required evidence fails closed.

### Task 10 — DS6-C10: reconcile the surface-readiness ledger in CI

**Declared path cap: 16.** Derive ledger claims and actual test/evidence
existence from their canonical owners, independently reconcile them, persist
the reconciliation receipt, fail CI for `stable`/`implemented` overclaim, and
surface the result in the governed audit/reference projection.

### Task 11 — DS6-C11: instrument the seven Atlas health metrics

**Declared path cap: 12.** Produce typed, versioned, replayable measurements
for primitive adoption, fail-closed fidelity, audience enforcement,
`surface_missing` closure, evidence coverage, machine-twin parity, and honesty
comprehension/review effectiveness. Unknown, zero, missing, and incomparable
remain distinct.

### Task 12 — DS6-C12: seed the honesty-comprehension protocol

**Declared path cap: 8.** Establish owner, cadence, tasks (“find the weakest
link” and “find the active blockers”), sampling, storage, and low-authority
interpretation. Preserve INT-R3's richer behavioral benchmark and thresholds
as `not_established`; no invented threshold may enter `stable`.

### Task 13 — DS6-C13: independently verify DS8 adjacent print export

**Declared path cap: 6.** Consume DS8's shipped surface without editing it;
run independent visual and semantic verification, persist evidence, and wire
the appropriate readiness/audit consumer. Failure returns evidence to DS8; it
does not authorize a DS6 product repair.

### Task 14 — DS6-C14: close the evidence workflow slice

**Declared path cap: 6.** Run the full serialized closure battery, corruption
probes, readiness reconciliation, duplication census, and independent review;
publish exact capability labels and nonreceipts. No missing link is called
complete.

## Expected cluster commits

| Cluster | Expected subject | Max files |
| --- | --- | ---: |
| C00 | `DS6-C00 open evidence workflow slice` | 2 |
| C01 | `DS6-C01 close count parity and freeze Russian keys` | 2 |
| C01-R1 | `DS6-C01-R1 justify count exemptions and repair active plurals` | 5 |
| C02 | `DS6-C02 add opaque rendered-contrast probe` | 4 |
| C03 | `DS6-C03 rebind i18n baseline lifecycle` | 9 |
| C04 | `DS6-C04 admit rendered-contrast evidence debt` | 6 |
| C05 | `DS6-C05 record serialized evidence wave` | 1 |
| C06 | `DS6-C06 close rendered-contrast evidence debt` | 6 |
| C07 | `DS6-C07 define evidence artifact storage` | 10 |
| C08 | `DS6-C08 wire automated evidence capture` | 10 |
| C09 | `DS6-C09 bind manual AT evidence to maturity` | 10 |
| C10 | `DS6-C10 reconcile readiness evidence in CI` | 16 |
| C11 | `DS6-C11 instrument Atlas health metrics` | 12 |
| C12 | `DS6-C12 seed honesty comprehension protocol` | 8 |
| C13 | `DS6-C13 verify adjacent print export` | 6 |
| C14 | `DS6-C14 close evidence workflow` | 6 |

## Deferred execution package

This is one consolidated, executable handoff. It is descriptive only in this
session; no listed governed artifact or heavy lane is touched.

### Contended governed writes after DS5-C21

**I18n lifecycle, DS6-C03.** Apply through the existing producer/checker, not a
hand edit:

1. `architecture/atlas_surfaces/frontend-baseline-debt-manifest.json`:
   `vitest.disposition` `rebind_pending -> resolved`; `exit_code` `1 -> 0`;
   `test_files` `{total:263,passed:262,failed:1} ->
   {total:263,passed:263,failed:0}`; `tests`
   `{total:766,passed:763,failed:3} -> {total:777,passed:777,failed:0}`;
   `failure_set.sha256`
   `533b0f74d085c34acb3b3dbbffd8a8fa056b023e1b96f93a464902682a9b94dd
   -> 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`;
   remove the complete sole `i18n-count-message-parity` debt-class object so
   `debt_classes=[]`. Preserve `parent_reproduction`; refresh command/timing
   fields only from the actual full run. If totals differ, stop and record the
   measured values rather than copying these expected totals.
2. `architecture/atlas_surfaces/frontend-baseline-debt.schema.json`: admit
   exactly two Vitest lifecycle shapes—the current exact open triple and the
   empty/resolved/exit-0 shape. Reject mixed disposition, nonzero exit, nonempty
   failures, or any debt class in the resolved shape.
3. `architecture/atlas_surfaces/check_frontend_disposition_register.py`:
   replace the fixed “exactly three survive” premise with the two-state
   lifecycle; retain exact-identity/signature rejection for the open state and
   reject every new failure in the resolved state; make the supplemental
   rationale lifecycle-neutral.
4. `architecture/atlas_surfaces/test_frontend_baseline_debt_manifest.py` and
   `architecture/atlas_surfaces/test_frontend_disposition_register.py`: prove
   the exact open triple and empty resolved state pass; synthetic fourth,
   changed anchor, and mixed lifecycle fail through the real checker.
5. `architecture/atlas_surfaces/frontend-disposition-register.json`: generated
   supplemental row `finding_id=baseline-test-i18n-count-debt` changes
   `status: open_debt -> repaired`; its rationale states that the full Vitest
   receipt has an empty failure set; attach the actual repair commit.
6. `docs/reference/frontend/atlas-frontend-disposition-register.md`: regenerate
   the same row and aggregate counts from the canonical producer.
7. `architecture/atlas_surfaces/status-retirement-inventory.json`: regenerate
   the induced content-bound receipt/hash after the disposition register
   changes.

**Rendered contrast, DS6-C04/C06.** Extend the canonical supplemental-finding
producer in `check_frontend_disposition_register.py`, exercise it in
`test_frontend_disposition_register.py`, generate
`frontend-disposition-register.json`, regenerate
`docs/reference/frontend/atlas-frontend-disposition-register.md`, and re-anchor
`status-retirement-inventory.json`. The exact new row before browser closure is:

```json
{
  "finding_id": "baseline-test-a11y-rendered-contrast-incomplete-debt",
  "finding_kind": "baseline_test_debt",
  "disposition": "rebind_pending",
  "status": "open_debt",
  "evidence_refs": [
    "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.ts",
    "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.test.ts",
    "apps/runtime-dashboard/src/test/a11y/OpaqueBackgroundContrast.stories.tsx"
  ],
  "owner_slice": "DS6",
  "decision_date": "2026-08-11",
  "rationale": "C01/C06/C09/C14 comprise seven declared source identities. Axe incomplete nodes are neither passes, source-attributed receipts, nor denominator members; closure requires 7/7 numeric WCAG-AA receipts on an opaque real-browser background."
}
```

After the real-browser 7/7 receipt, transition that same row—never a second
row—to `status: repaired`, retain the seven evidence refs, add the actual
`repair_commit`, and regenerate the same report and induced status receipt.
This discharges the master sentence that makes the DS4 prose table authoritative
“until DS6 creates one.” It does not enter the Vitest debt-class array, because
the four axe-incomplete clusters were never failing Vitest identities.

### Heavy lanes waiting for the GY release

Run from `apps/runtime-dashboard` after the explicit release, serially in the
order shown. `/usr/bin/time -p` is part of each first authorized command so its
`real` value is the suite's one measured wall-time baseline:

```bash
/usr/bin/time -p corepack pnpm exec vitest run --config vitest.storybook.config.ts src/test/a11y/OpaqueBackgroundContrast.stories.tsx
/usr/bin/time -p corepack pnpm run test:components -- --reporter=default --maxWorkers=2
/usr/bin/time -p corepack pnpm run test:a11y:components -- --maxWorkers=2
/usr/bin/time -p corepack pnpm run test:a11y:pages
/usr/bin/time -p corepack pnpm run test:journeys
/usr/bin/time -p corepack pnpm run test:visual
/usr/bin/time -p corepack pnpm run lint
/usr/bin/time -p corepack pnpm run typecheck
/usr/bin/time -p corepack pnpm run build
/usr/bin/time -p corepack pnpm run build-storybook
```

The first authorized measurement runs without an outer kill budget; the test
runners' existing per-test semantics are not widened. Immediately after each
first receipt, record `real` in the journal and set that suite's explicit
controller timeout to `ceil(real * 2 / 30) * 30` seconds (twice the measured
wall time, rounded up to the next 30 seconds) for every later rerun in this
slice. A later timeout is a harness non-receipt and stop signal; it is not
silently enlarged or reported as product regression. Numeric timeout values
are presently `not_established` because running the only admissible measurement
is prohibited by this session's heavy-lane boundary.

`corepack pnpm run storybook` and any dashboard dev-server command remain
unrun unless an interactive diagnosis is separately authorized; the commands
above do not require a manually started server. The reason for waiting is not
OOM risk or ordinary slowdown: the governed host-contention budget measured
the same GY writer at 194.9–426.3 seconds (2.2x) and a full Atlas module at
393–754 seconds (1.9x). Concurrent heavy work can push the governed writer past
its cap and make policy interpret contention as a product regression. Until
release, every command above is a non-receipt, never green.

## Not yet

- No typed contrast row or i18n baseline removal until DS5-C21 releases the
  contended governed owner.
- No browser, Storybook, full suite, full lint/typecheck/build, journey, visual,
  dev-server, or product-surface claim until the GY lane releases the heavy set.
- No readiness-ledger CI validator, health-metric producer, manual AT maturity
  bridge, honesty threshold, or adjacent-print verification in C00-C02.
- No Russian catalog deletion or active-locale exposure change; DS5 owns the
  latter mechanic and the frozen catalog remains in-tree.
- No claim that seven source identities pass until the real-browser receipt is
  7/7. The non-browser classifier contract proves only the gate semantics.
