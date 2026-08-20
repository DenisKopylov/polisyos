---
plan_id: atlas-ds6-evidence-workflow
title: "DS6 - Evidence Workflow & Instrumentation"
type: slice-plan
status: c11_review_repair_verified_c10_r1_deferred
created: 2026-08-11
revised: 2026-08-16
last_verified: 2026-08-16
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
- The slice is deny-by-default. DS6-C16 closed at
  `97d0c620836a3e6d33c347a1f7f563aaa9177d0c`. The continuation authorized C10,
  then C11, then the visual-fixture re-cut. C10 stopped under its mechanism
  breaker; its ten-path
  candidate is preserved at `573be959890f8e35f72e846e0a37b6eac5fc4396`
  and removed by forward revert
  `a7ae9189147d012fd8a3c80d741ed5c330787672`. Only this plan and journal may
  record that stop. The later architect ruling gave C10-R1 its own session
  and explicitly authorized C11 independently; C11 is implemented below.
- This session must not write the shared governed Atlas-surface artifacts named
  under **Deferred execution package**. DS5-C21 owns that contended resource
  until it merges. Required deltas are specified there, not applied here.
- C16 was explicitly authorized to run, one heavy parent at a time, the exact
  whole-suite Vitest, full lint, full typecheck, production build, opaque
  Storybook browser probe, and component-a11y closeout lanes declared under
  Task 16. That authorization is consumed. Task 18 separately authorizes its
  exact serialized Playwright visual-fixture, generation, and no-update lanes
  under a 2,400-second ceiling. Playwright journeys, standalone dev servers,
  and every other undeclared heavy command remain unauthorized.
- Focused Vitest over touched files and scoped static checks may establish the
  source freeze, but only the serialized Task 16 lanes establish C16 closeout.
- No product surface, DS5 path, GY path, a11y denominator, baseline suppression,
  skip, quarantine, tolerance widening, merge, push, rebase, force push, or
  stash-as-storage. One scoped commit follows independent review for each
  entered cluster.
- C10 is stopped, checkpointed, forward-reverted, and re-cut as the separately
  authorized C10-R1 vector/basis mechanism. C11 implements six measurements
  plus one `not_established` protocol seam without entering C10-R1. The
  deterministic visual-fixture repair is DS6-owned and separately re-cut as
  C18. C03, C04, C06, C13's governed transition, and C14 retain the gates
  stated below and in the journal.

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
| task-brief P38 (unregistered at this revision) | gate predicates on one marker while deciding a wider semantic property | enumerate every load-bearing variable and test the agreement property rather than the literal `{count}` spelling |

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

**Two independent gates:** (1) DS5 releases all eight governed C03 artifacts
named in the deferred package, after which C03 re-reads their then-current
owners and content-hash anchors; and (2) explicit heavy-lane continuation
authorization permits a whole-suite JSON Vitest run whose green receipt
package is the only source for the resolved Vitest fields. Neither gate
satisfies the other; focused Vitest satisfies neither. GY/host release
authorizes gate 2 but is not a third semantic gate. C16's 317/317-file,
983/983-test receipt discharges gate 2; only the current DS5 owner release
remains. **Declared path cap: 9.**

Own the baseline manifest/schema producer, both relevant governed tests, the
disposition producer/generated register, report, induced status-inventory
re-anchor, and journal. Admit exactly the existing open triple or an
empty/resolved/exit-0 state; reject any other identity or signature. Transition
`baseline-test-i18n-count-debt` to `repaired` only from the measured full-suite
receipt.

### Task 4 — DS6-C04: admit the typed rendered-contrast debt

**Gate:** DS5 releases the current register family and explicit continuation
authorization.
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

**Gate:** C04 typed row exists; C16 has supplied the exact 7/7 browser receipt,
so C04 is the only remaining gate.
**Declared path cap: 6.**

Through the canonical producer, transition the same row to `repaired`, attach
the actual repair/evidence commit, regenerate register/report and induced
status receipt, run corruption probes, and append the journal.

### Task 7 — DS6-C07: define the evidence artifact and storage convention

**Exact path set after review measurement:**

1. `apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts`
2. `apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.test.ts`
3. `docs/reference/frontend/atlas-evidence-artifact.md`
4. this plan
5. the DS6 journal

**Declared path cap: 10; measured candidate set: 5.** Define one strict Zod
runtime schema and inferred TypeScript DTO, bounded authority purpose/denials,
source-specific producer and verifier provenance, rule/schema versions,
the existing `PUBLIC`/`REVIEWER`/`EXPERT`/`MACHINE` audience vocabulary,
separate collection/observation/verification times, P37 predicate provenance,
outcome, a typed reference to the content-bound verification payload, and the
inherited 365-day CAS retention rule. Freeze the storage
convention on the existing `polisyos.core.artifacts.ArtifactStore.put_json`
boundary: its returned `ArtifactRef`/`ArtifactID` is the receipt's immutable
content address, and its default local implementation writes under the existing
`.polisyos/cas` slot. C07 must not implement another writer/CAS, put a circular
self-hash inside the receipt, or edit the already-complete runtime-state and
generated-artifact registries.

The strict parser rejects unknown fields, malformed or missing content refs,
authority-denial drift, collapsed producer/verifier provenance, missing
provenance/time roles, invalid time ordering, and retention drift. A companion
strict verification-payload schema and resolver-side comparator bind evidence
kind, subject, rule, producer/verifier, times, and result after real CAS
resolution. The payload write uses the complete recorded Core CanonSpec with
finite floats admitted and NaN/Infinity rejected; the receipt manifest must
carry the payload through `ArtifactWriteOptions.inputs` role
`verification_payload`.

A shaped `sha256:` reference remains a declaration, not proof: no runner is
wired, no CAS artifact is created, and no `stable` consumer closes here.
`producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
evidence `verification_missing`, and `surface_missing` remain explicit until
C08/C09. Acceptance requires focused Vitest green, marker-preserving semantic
negatives (including a valid-but-unrelated resolved payload), an unchanged
five-path measurement, and independent specification and quality review with
no open Important/Critical finding.

### Task 8 — DS6-C08: wire browser, keyboard, and automated evidence capture

**Owner-discovered path set declared before mechanism entry:**

1. `apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts`
2. `apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.test.ts`
3. `apps/runtime-dashboard/src/test/evidence/captureAtlasEvidence.ts`
4. `apps/runtime-dashboard/scripts/capture_atlas_evidence.mjs`
5. `apps/runtime-dashboard/scripts/persist_atlas_evidence.py`
6. `docs/reference/frontend/atlas-evidence-artifact.md`
7. this plan
8. the DS6 journal

**Declared path cap: 10; measured candidate set: 8.** Read-only owner discovery
found the complete persistence and integrity surface already in
`src/polisyos/core/artifacts`: `ArtifactStore.put_json`, `get_bytes`,
`get_manifest`, and `verify`, plus the backend-neutral
`build_artifact_store(ArtifactStoreConfig.from_env())` configuration/factory
pair. The dashboard already has an
app-local Python bridge which imports PolicyOS through the public package
boundary in `scripts/serve_fixture_runtime_api.py`; C08 follows that boundary
without editing `src/polisyos/**`. The runtime artifact HTTP surface is an
inspector, not the evidence writer, so routing capture through it would invent
a second owner.

The measured cut adds one app-local MJS launcher after entry because the
installed workspace has Vite but no `vite-node` executable; a command which
cannot load the typed bridge is a nonreceipt, not wiring. The launcher uses the
installed Vite module loader and contains no evidence semantics. Wire exact,
rule-owned Playwright and Storybook/Vitest report profiles to one
strict normalization seam, then pass the normalized C07 payload and receipt to
the app-local bridge. The bridge must use the existing Core store for three
bound artifacts: exact raw runner bytes via `put_bytes`, the normalized payload
via `put_json` with the raw artifact as its sole `runner_report` input, and the
receipt via `put_json` with the payload as its sole `verification_payload`
input. It resolves and integrity-verifies all three, decodes canonical JSON
with the Core decoder, and returns the resolved payload and receipt for C07
semantic binding. A raw report's digest, exact test denominator, outcome, and
findings are recomputed from the machine report; caller-supplied outcome or
artifact identity is not admitted. The runner identity is reconciled against
the exact profile/test population. Playwright exposes and therefore recomputes
its version; the Vitest JSON does not expose a version, so that profile version
and the rule identity remain explicitly `institutionally_supplied` and cannot
turn the result green.

The exact five implementation paths that parse, launch, persist, and bind the
receipt are byte-hashed into the normalized payload. The TypeScript producer
computes the ordered per-file hashes and aggregate; the fixed Python adapter
independently recomputes the same set before any write and places the current
Git revision plus repository dirty bit in all three Core manifests. A dirty capture
is traceable to exact bytes but is not represented as a cleanly replayable
revision. Automated diagnostic artifacts are classified `internal`; their
manifests explicitly state that at-rest encryption is not enforced or verified,
matching the receipt's non-public audience rather than laundering local paths
as public material. Positive and negative reports are both persisted. Manual
AT remains separate and C09's maturity consumer is not invoked.

Required negatives reject a report whose summary contradicts its individual
results, an undeclared or incomplete test population, malformed runner JSON,
a sibling bridge/interpreter override, changed implementation provenance, raw
runner corruption, an integrity or manifest-lineage failure, and a
CAS-resolved payload that does not semantically bind to its receipt. Capability
stays `contract_only` until a real report is persisted, resolved, and
integrity-verified. Even after that receipt, C08 is only
`implemented_but_not_orchestrated` with
`consumer_missing` and `surface_missing`: this explicit capture command is not
automatic runner orchestration, and C10 owns readiness reconciliation.

### Task 9 — DS6-C09: wire manual AT evidence and maturity consumption

**Exact candidate paths declared before mechanism entry:**

1. `apps/runtime-dashboard/src/shared/i18n/parity.test.ts` — residual disclosure
   only; the existing `reviewers` exemption becomes explicitly
   `declared, unenforced`, with no count-gate mechanism change
2. `apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts` — C07's
   canonical P37 vocabulary owner, exported for reuse
3. `apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.test.ts` —
   exact-set comparator for that canonical vocabulary
4. `apps/runtime-dashboard/src/test/evidence/atlasManualAtMaturity.ts`
5. `apps/runtime-dashboard/src/test/evidence/atlasManualAtMaturity.test.ts`
6. `docs/reference/frontend/atlas-manual-at-maturity.md`
7. this plan
8. the DS6 journal

**Declared path cap: 10; measured candidate set: 8.** The entry set was six;
independent review found that the C09 basis had copied C07's load-bearing P37
vocabulary, so the measured owner-aware set added the canonical C07 source and
its existing focused test without enlarging the cap. Owner discovery walked
all 21 tracked paths under `architecture/atlas_surfaces`: exactly two schemas
mention the shared `componentMaturity` definition and only
`adoption-ledger.schema.json` carries a `stable` conditional. The normative bar
is the Atlas surface constitution; the adoption ledger carries DS2 maturity
claims but is not production-readiness authority. Its 233/233 entries contain
zero `stable` claims; the live-readiness ledger's 261/261 entries also contain
zero, and the disposition register has no maturity field. The actual adoption
ledger is byte-hash-bound into the contended register, so changing it would
induce a forbidden re-anchor. C09 therefore changes none of those owners.

Extend the C07 contract rather than minting another evidence shape: strict
rule-owned `manual_at` payload details plus a maturity-prerequisite consumer
that accepts the actual adoption-ledger component-row shape, requires its exact
`at_manual` receipt reference, parses the C07 receipt, semantically binds its
C07 verification payload, and matches the exact component/state subject. The
human receipt retains C07's denial of `component_maturity` and `stable`; the
independent consumer applies the bar and cannot itself grant overall maturity.
Protocol expiry is a separate `expires_at` time evaluated against an injected
`evaluated_at`; evaluation cannot precede C07 verification, expiry must follow
verification, C07's 365-day storage retention is never reused as evidence
validity, and no freshness duration is invented.

For an authority-grade prerequisite, `consumer_asserted`,
`institutionally_supplied`, and `not_established` predicate provenance fail
closed under P37. The same classification applies separately to the complete
task/AT basis: an arbitrary task or an inadequate AT capability set cannot
substitute for an independently reconciled versioned profile. The evaluator
preserves distinct named results for absent, expired, not-yet-valid,
invalid-expiry, authority-bound excess, subject mismatch, unknown status,
known zero, owner-reference absence, basis absence/mismatch, and missing CAS
integrity.

C09 has no `satisfied` path yet. C07's semantic binder expressly does not prove
CAS existence or digest integrity, C08 persistence/integrity is absent, and C10
has not resolved the basis or reconciled the full maturity bar. A perfectly
shaped in-memory bundle therefore fails closed as
`manual_at_integrity_not_established`. Capability truth is `contract_only`
with `producer_missing`, `artifact_missing`, `bridge_missing`, actual-evidence
`verification_missing`, and `surface_missing`.

### Task 10 — DS6-C10: reconcile the surface-readiness ledger in CI

**Status: C10-R2 landed locally on
`codex/atlas-ds6-c10r1-readiness-reconciliation` on 2026-08-18 and is
controlling for the per-claim CI gate and governed Core CAS claim-basis audit
projection on that branch.** Mechanism source is frozen at
`c186885010ad74d995d438f928e61b74de8a61d3` after one of two fresh repair
rounds and a clean three-adversary delta review. Existing Vitest discovery now
gates every top-level `maturity=stable` or `readiness_state=implemented` row:
only its own admitted `observed_by_reconciler/observed` basis is green;
completed negative, unavailable, cited, missing, or extra rows are red under
their row-level contracts. The audit projection exposes every row and its own
basis and is authoritative only for `surface_readiness_claim_basis_audit`.
Neither surface grants a `stable`/`implemented` claim or an aggregate
reconciliation result.

R2 continued from preserved R1 mechanism candidate
`6906777f4dfc13c3ee81e6a60dc4eacf7f5aa0fd` and its docs-only stop record. R1
stopped correctly after classifying `transitive-runner-closure-unbound` as
another instance of `canonical-runner-provenance-and-single-intake-gap`. R2
made that runner-integrity boundary explicit and used **1/2** fresh mechanism
rounds; further transitive runner examples remain limitation evidence, not
repairs. The preserved stopped attempt at
`573be959890f8e35f72e846e0a37b6eac5fc4396` and its forward revert
`a7ae9189147d012fd8a3c80d741ed5c330787672` remain evidence only. No
surface-readiness `stable` claim is made.

**C10-R1 refused mechanism — recorded, not entered in the C11/C18 session.**
`PV-K01` is ratified for public verification: it requires separately
reportable dimensions and rejects an unqualified public `Verified` Boolean
(`docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md`,
§4.1 and §7). The 2026-08-16 architect ruling extends that law's *shape* to
C10's internal case; this is a C10-R1 ruling, not a ratification beyond
PV-K01's public subject. C10-R1 refuses the mechanism “inspect supplied report
bytes plus a supplied exit code, then mint one `independently_reconciled`
Boolean.” Its evidence is the three stopped findings:

1. supplied Vitest bytes and caller-supplied process exit were labelled
   independently reconciled (`canonical-runner-provenance-and-single-intake-gap`);
2. canonical owner constraints could be falsified while the supplied
   reconciliation remained positive (`incomplete-pre-CAS-owner-invariant`);
3. supplied `fail` or `incomplete` status could coexist with canonical
   zero-finding PASS facts (`non-bidirectional-status-contract`).

C10-R1 must instead report each claim separately with exactly one basis:
`observed_by_reconciler` only when that process ran the canonical check through
a closed path with no report/exit/basis intake, or
`consistent_with_cited_report` with the cited artifact identity, digest,
producer/verifier provenance, and execution status recorded. No number or
conjunction of cited-report consistencies composes into an observation,
aggregate reconciliation PASS, or stable authority. The refused Boolean must
not return under another field, receipt outcome, provenance label, or aggregate
status.

**Declared path cap: 16; measured stopped-attempt set: 10.** Derive ledger
claims and actual test/evidence
existence from their canonical owners, independently reconcile them, persist
the reconciliation receipt, fail CI for `stable`/`implemented` overclaim, and
surface the result in the governed audit/reference projection.

**C10-R1 P39 entry measure.** The cap initially applied to four mechanism paths: the
typed per-claim reconciler, its semantic/CI test, the fixed launcher, and the
existing persistence/projection adapter. Three mandatory record companions are
named and held outside that count: this plan, the DS6 journal, and the reviewer
reference. Round 2 found ambiguous duplicate-key intake at the already reused
canonical-owner validator, so that validator is declared as a fifth mechanism
path before repair. The current mechanism measure is therefore **5/16** and the
complete candidate cut is eight paths. A newly discovered mechanism path is
remeasured before it is touched; a mechanism set above 16 stops for a ruling
and is never split across commits to fit.

**C10-R2 declared threat model.** Every `observed_by_reconciler` basis persists
the exact `attestation_scope` value: “observed_by_reconciler attests intake
closure: this process produced the row through a closed path by running each
available applicable canonical check itself and recording any unavailable
claim check as unavailable; no report, exit code, status, or basis was supplied
by a caller, and runner code being unmodified on disk is not attested.” This is
one per-row intake statement, not a runner-integrity claim or aggregate status.
Report and projection schemas are versioned `2.0.0` for the new required field.

**Named residual — `transitive-runner-closure-unbound`.** Classification:
declared bounded runner-integrity limitation. Closure owner:
**`absent/unallocated`**; `team-frontend` owns the reference/artifact surface,
not the absent closure capability. Exact scenario: a modified transitively
loaded Vite or Vitest chunk can forge module loading or passing JSON while the
recorded entry path, package version, and entry SHA-256 remain valid. This does
not reopen any caller, report, exit-code, status, basis, environment-selection,
or sibling-consumer intake; those remain closed and separately witnessed. The
smallest closing capability is an out-of-band runner identity—such as a signed
build artifact or attestation produced outside this repository—that binds the
runner/module closure and is independently verified before admission.

The required absence falsifier walked the complete 9,870 tracked-file
denominator. Supply-chain candidate terms occurred in 386 files. Four producer
term occurrences appeared in three files: three real release/build producer
occurrences in two workflow/template files plus one operability-checker string.
The only verifier-pattern occurrence was an unrelated TEE platform-attestation
protocol; zero qualifying consumer/verifier paths bind the C10 runner or its
module closure. Capability existence and those counts are `recomputed`; actual
external release-attestation execution is `not_established`. The residual is
therefore a limitation, not an omitted repository capability.

The gated unit is one row for each top-level `maturity=stable` or
`readiness_state=implemented` claim. Each row carries exactly one discriminated
basis. `observed_by_reconciler` has three results: `observed`, `not_observed`
after a completed canonical negative, or `observation_unavailable` with a
reason when the canonical check could not run. The last two are distinct CI
reds. `consistent_with_cited_report` carries artifact identity, digest,
distinct producer/verifier provenance, execution status, and findings. Its
status/facts contract is bidirectional: `pass` with findings is named red, and
`fail` or `incomplete` without findings is separately named red. A valid cited
row remains reportable but is never observation-eligible. A synthetic `stable`
row is the live negative control for the otherwise empty gate arm.

The CI exit code is the **only** place a conjunction over rows may exist. It is
a gate, not a claim. It is never written to an artifact, never given a field
name, never surfaced in the projection or the reviewer reference, and never
carried as a receipt outcome, provenance label, or aggregate status. Its
falsifier deletes the CI exit-code calculation and proves that every persisted
artifact and projection byte retains the same per-row information.

The three independent reviews of frozen candidate `b0e557c04` form one
mechanism round because no repair occurred between them. Round 1 classified
the unbound resolved Vitest entry and one-way observed status/facts relation as
new instances of the already named
`canonical-runner-provenance-and-single-intake-gap` and
`non-bidirectional-status-contract`. New classes were a hidden row conjunction
inside one Vitest case, a validated-owner/read-later TOCTOU gap, and cited
artifact consistency asserted from hash-shaped fields without resolving the
cited bytes. A root pre-repair P38 audit also found that the assertion identity
bound the legacy source path but not the ledger-declared redirect target. The
owner-probe specificity and aggregate-key heuristic are test findings, not
mechanism rounds. All are repaired together before the second candidate is
reviewed; a Blocking or Important mechanism finding on that candidate consumes
round 2.

The three independent reviews of frozen round-1 repair candidate `2c1df24b4`
form mechanism round 2 because no source changed between them. Round 2 found
one accepted Blocking/Important mechanism class: the exported CI helper parsed
a caller-fabricated `observed_by_reconciler` shape and could return green
without resolving the closed persistence result. That is a new sibling
instance of the already named
`canonical-runner-provenance-and-single-intake-gap`, with P31/P32 at the CI
consumer. The final repair removes that sibling intake; CI discovers each row
only from the admitted projection returned by the fixed operation.

The same batch accepts loader/source hardening as instances of that old class:
bind the Vite module loader plus pre/post Node and Vitest bytes, and make the
canonical validator reject duplicate JSON keys before schema interpretation.
The stable negative control finding is P29/P33 test incompleteness, not a
mechanism round: it must construct the synthetic row through the actual stable
producer arm and exercise the real Python admission constraint. Two review
proposals are classified as non-findings under the changed contract. A nonzero
suite exit beside a passing row assertion is an unrelated-test conjunction and
must not be copied onto every row; the owned per-row assertion fact governs.
The raw suite report is an internal runner transport, while the exact per-row
fact and its provenance are the persisted claim basis; persisting the suite's
aggregate `success` would violate the CI-only conjunction boundary. A
swap-and-restore by a concurrent writer with control of installed executables
remains outside this repository gate's threat model, while ordinary mutation
is closed by pre/post content checks.

Terminal review of frozen final candidate `6906777f4` returned no
Blocking/Important mechanism finding from two reviewers and one Important
mechanism finding from the independent CAS/provenance reviewer. The concrete
falsifier modifies a loaded Vite chunk such as
`vite/dist/node/chunks/config.js`, or a Vitest `dist/chunks/*` dependency,
while leaving the bound entry and package files unchanged. The modified code
can forge module loading or a passing JSON assertion report while all recorded
entry hashes remain green. This is the terminal third finding described in the
status paragraph. One additional P29 test-only finding remains recorded: the
stable admission witness exercises the valid stable-unavailable row but does
not corrupt its stable-specific reason to prove that Python branch red. The
stop precludes even that post-freeze test edit. The expensive verification wave
was not launched after the stop and supplies no receipt.

**C10-R2 review and wave outcome.** Frozen R2 candidate `c1354ec7a` received
one Important bucket-A finding: its universal threat-model sentence falsely
said the stable-unavailable row had run a canonical claim check. That intake
self-attestation defect consumed R2 round 1. Repair `c18688501` instead says
the process runs every available applicable check and records an unavailable
claim check as unavailable; its stable witness pins runner, report, assertion,
and route facts to null. Three delta reviewers returned no Blocking or
Important intake finding. Their repeated transitive-chunk falsifiers are
bucket-B examples of the named residual and consume no round. R2 ends at
**1/2** rounds used.

The serialized whole-suite rerun completed under its declared 1,800 s ceiling
in 100.03 s wall. Its complete denominator is 319 test files and 1,038 test
assertions: 318 files/1,037 assertions passed, and one file/one assertion
failed. C10 passed 33/33 and the earlier C08 scratch setup nonreceipt was gone.
The sole remaining red is the pre-existing C11 clean-worktree test pin that
expects dirty `pyproject.toml`/`uv.lock` replay paths; R1 had reproduced and
classified it before C10 source existed. It is not repaired or excluded here.
The repository-wide Vitest process therefore remains red for that recorded C11
nonreceipt, while the discovered C10 gate itself is controlling: each of the
five current rows independently supplies its own observed-positive basis, and
no multi-row result is emitted. The unrelated suite exit is not copied into
any claim, projection, status, or receipt outcome.

The final P39 measure remains **5/16 mechanism paths plus 3 mandatory record
companions**, eight paths in the complete `main..HEAD` cut. No mechanism was
split to fit the cap. The current full ledger denominator remains 261 rows,
with five `implemented` and zero `stable`; those are separately recomputed
owner counts, not a composed readiness result.

### Task 11 — DS6-C11: instrument the seven Atlas health metrics

**Revision 3.22 closure repair status: the P38 test repair candidate is
implemented and the focused suite is GREEN 22/22. Its release remains
`not_established` until the containing commit's attached-branch readback.**

The measured closure cut is one mechanism path plus this plan and the journal
as mandatory record companions. On a clean attached revision, red-first was
21/22: the sole failure expected `pyproject.toml` and `uv.lock` in
`replay.non_revision_paths`, although both files exist in `HEAD` and their
current bytes match it. The producer defines the authoritative six-file
`HEALTH_IMPLEMENTATION_PATHS` tuple, and this governed test already asserts
that exact persisted tuple directly. The repair removes only the transient
revision-state expectation. It does not assert an empty replay set or weaken
replay semantics: the absent-path witness, clean-versus-absent exact result,
and inconsistent status/path-set rejection remain exercised. P40 is **0/2**;
P39 subtracts the two record companions and leaves one mechanism path, within
C11's declared cap of 12.

**Status: review repair implemented and verified 2026-08-16; not orchestrated.
Exact declared repair path set: ten paths, below the declared cap of 12.**

1. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts`
2. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts`
3. `apps/runtime-dashboard/scripts/measure_atlas_health.mjs`
4. `apps/runtime-dashboard/scripts/persist_atlas_evidence.py`
5. `apps/runtime-dashboard/scripts/validate_atlas_health_sources.py`
6. `pyproject.toml`
7. `uv.lock`
8. `docs/reference/frontend/atlas-health-metrics.md`
9. this plan
10. the DS6 journal

Six metrics are instrumented against current repository owners; honesty
comprehension/review effectiveness retains C12's instrument seam with every
threshold `not_established`. The current owner-derived states are: primitive
adoption `unknown`; fail-closed fidelity `unknown`; audience enforcement
`unknown`; `surface_missing` closure known zero at `0/27`; evidence coverage
`incomparable` at `0/0` stable components; machine-twin parity `missing`; and
honesty comprehension `protocol_seam_only` with its observation `missing`.
These are descriptive measurements, never one aggregate PASS or ranking.

**Declared path cap: 12.** Produce typed, versioned, replayable measurements
for primitive adoption, fail-closed fidelity, audience enforcement,
`surface_missing` closure, evidence coverage, machine-twin parity, and honesty
comprehension/review effectiveness. Unknown, zero, missing, and incomparable
remain distinct. The public C11 persistence operation accepts no caller report,
repository root, producer script, exit status, or basis. It invokes the fixed
repository producer itself through an allowlisted absolute Node realpath and a
minimal environment, observes its terminal status and stdout, and then treats
that stdout as candidate input only. The fixed source validator applies the
complete DS1 and DS2 Draft 2020-12 owner schemas, including local reference,
format, uniqueness, additional-property, and stable-evidence constraints,
before projection. The Python adapter reruns that fixed validator in an
isolated repository Python process, recomputes and matches every exact row, and
is the single limited-descriptive admission point. It persists the exact
candidate report plus one content-bound admitted snapshot through Core CAS.
The snapshot reuses C07's canon, governance, retention, integrity, and lineage
convention without adding a C07 evidence kind or receipt.

The fixed producer emits
`polisyos.atlas.health-metric-report@1.0.0`; the existing Python persistence
adapter stores that candidate report plus one content-bound
`polisyos.atlas.health-metric-snapshot@1.0.0`. The snapshot's sole CAS input is
the report with role `measurement_report`; its distinct admission producer
binds the report digest, exact admitted measurements, validator/toolchain/
environment provenance, owner/schema/producer/verifier hashes, and an actual
revision-byte comparator result. Every row is `observed_by_instrument`, while
its exact metric schema separately fixes the predicate provenance to
`recomputed` or `not_established` and fixes the only allowed status,
measurement variant, known facts, and threshold shape. A dirty or untracked
binding records `source_hash_bound_only`, never historical replay. The stored
capability is honestly `implemented_but_not_orchestrated`, with
`consumer_missing` and `surface_missing`. The typed authority, replay, current
denominators, and acceptance commands are documented in
`docs/reference/frontend/atlas-health-metrics.md`.

**Acceptance prerequisite and controlling receipt.** A fresh C11 environment
must bootstrap the locked `test` extra before the isolated source validator
runs; the acceptance command intentionally does not claim offline operation.
The controlling current focused receipt is 22/22 tests (with nine
canonical-owner corruption probes and clean/absent revision-byte witnesses),
superseding the earlier 21/21 and 19/19 review-repair receipts. The current
dirty/untracked ten-path repair binding checks 17 bound paths and reports
`source_hash_bound_only` for exactly six C11 paths: the typed instrument, MJS
producer, source validator, persistence adapter, `pyproject.toml`, and
`uv.lock`.

### Task 12 — DS6-C12: seed the honesty-comprehension protocol

**Exact final path set after review measurement:**

1. `apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts`
2. `apps/runtime-dashboard/src/test/evidence/atlasManualAtMaturity.ts`
3. `apps/runtime-dashboard/src/test/evidence/atlasHonestyComprehensionProtocol.ts`
4. `apps/runtime-dashboard/src/test/evidence/atlasHonestyComprehensionProtocol.test.ts`
5. `docs/reference/frontend/atlas-honesty-comprehension-protocol.md`
6. this plan
7. the DS6 journal

**Declared path cap: 8; measured candidate set: 7.** The five-path entry set
expanded during review without enlarging the cap: C07 now exports its canonical
`ArtifactID` schema, and both C09 and C12 consume that one owner instead of
redeclaring the load-bearing reference shape. Complete owner discovery
found no protocol implementation across 949 tracked frontend TypeScript files
or 4,951 tracked backend Python files. The research tree has 136 tracked
policy-operations files, three INT-R3 prose mentions, and no INT-R3 artifact or
completion row. The master and research backlog are therefore design inputs,
not delivered benchmark content.

Establish DS6/`team-frontend` as instrument owner, INT-R3 as research-content
and threshold owner, DS6-C11 as future measurement owner, and Core
`ArtifactStore` as persistence owner. The cadence is quarterly plus before the
first interactive-authority stable claim and after an authority-surface
semantic/profile change; cadence is collection scheduling, not TTL, validity,
or a stable threshold. The two seed tasks are exactly “find the weakest link”
and “find the active blockers”. Their expected-answer bindings name the exact
existing producer and field, but remain `predicate_provenance=not_established`:
C12 does not behaviorally verify either Python producer. Responses preserve
external execution, evidence status, and PolicyOS reaction as three distinct
planes.

Sampling is preregistered and risk-stratified with a frame frozen before
observation. Sample size, frame completeness, representativeness, and the
completeness predicate remain `not_established`; even C07-valid
`sha256:<64-lowercase-hex>` frame/preregistration identities cannot elevate
them without resolve-bind-verify. The protocol aliases C07's exact storage
convention and denied-use prefix but creates no receipt, evidence kind, CAS, or
writer.
C07's closed `manual_at` kind means assistive-technology evidence and must not
be reused to mislabel a generic human comprehension session.

The exact seed ID/version is content-bound to its two tasks, answer bindings,
three response planes, six metrics, four conditions, and null threshold rows.
Other independently versioned profiles remain generic so INT-R3's later
behavioral battery can replace the seed without changing the outer envelope,
but every profile must preserve the six named metric identities and four
operating-condition identities; researched additions are allowed only while
every threshold stays exactly `not_established` with null comparator, value,
unit, and source. The
current schema has no established-threshold branch. Missing, unknown, known
zero, incomparable, and recorded observations remain distinct, but every
interpretation is descriptive-only, nonblocking, and cannot grant stable.
Capability truth is `contract_only` with `producer_missing`,
`artifact_missing`, `bridge_missing`, `consumer_missing`, actual-evidence
`verification_missing`, and `surface_missing`.

### Revision 3.22 debt-row execution — DS5 run-deck residual

**Status: honestly stopped before mechanism entry. Live measurement disproves
the recorded border-box-height cause; no CSS or snapshot byte changed.**

The closed DS5 owner's residual is executable under Revision 3.22 without
transferring correctness ownership. The governed no-update Chromium comparator
reproduced 1,094×820 expected against 1,094×821 actual with 4,178 differing
pixels. The independent no-writer diagnostic then established that the live
evidence slide is already an exact 1,094×820 CSS border box: computed and
offset height are 820 px, `box-sizing` is `border-box`, client and scroll
height are both 818 px, and direct-child content overflow is zero. At DPR 1,
the box starts and ends at fractional Y coordinates 3,920.75/4,740.75; the
in-memory locator PNG is 1,094×821. The divergence is therefore fractional
screenshot clipping/rasterization, not a border-box-height defect.

The authorized repair condition is false, so CSS adjustment would be a P38
proxy repair. The run-deck residual remains open, no three-match closure wave
is run, and the governed snapshot remains byte-unchanged. P40 is **0/2**
because no mechanism was entered. P39 arithmetic is zero mechanism paths plus
this plan and the journal as mandatory record companions. The visual lane was
explicitly relinquished after the stopped measurement.

### Task 13 — DS6-C13: independently verify DS8 adjacent print export

**Revision 3.22 execution status: the scoped product repair is released at
`1fc07ed01a3cd3d5cfd9dc4a04b1ad89d0d141cd` after attached-branch
readback, and its narrow current-surface semantic guard is GREEN. DS8/
`team-design` design adjudication remains owed, and the governed A4 comparison
is RED. The C13 governed transition therefore remains blocked, C14 is not
executable, and DS6 remains open.**

**Current measured path set:**

1. `apps/runtime-dashboard/src/styles/print.css`
2. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`
3. this plan
4. the DS6 journal

**Declared path cap: 6.** Revision 3.22's debt-row execution rule supersedes
the older no-product-edit fence for this registered co-owned row: DS6 may
execute its independently verifiable closure signal while DS8/`team-design`
retains correctness ownership and still owes design adjudication. P39
arithmetic is two mechanism paths plus two mandatory record companions. The
CSS repair and its generic real-browser semantic verifier are mechanism; this
plan and the journal are companions outside the mechanism count. Two mechanism
paths fit the cap.

The complete current rendered link set under the print surface contains one
17,206-byte `/public/decisions/` target. The landed scoped rule suppresses
only that target's pseudo-content and preserves every current rendered
ordinary printed destination. Its independent Chromium guard is GREEN. For
this measured surface, the sole generated signed-target string is absent and
therefore cannot overlap the report; this is not an unbounded claim about
future target patterns or direct URL text in report content. Measurement
nevertheless falsified the prior claim that this target caused the whole
13,269-pixel height: suppressing it yields 12,966 pixels, and even suppressing
every link target yields 12,918. The governed expected image remains 724×2,113,
so the first post-repair no-update capture is a completed RED receipt and no
second capture is run. The snapshot is not rewritten and no report content is
hidden to fit it.

C13 requires all three conjuncts: a content-bound scoped repair release,
independently established semantic non-overlap, and two consecutive GREEN
no-update A4 captures. The repair-release predicate is `recomputed` and true
at the commit above. The narrow current-surface signed-target predicate is
`recomputed` and true: the complete rendered denominator has one generated
signed target and its pseudo-content is absent. The capture predicate is
`recomputed` and false: the first no-update comparison is RED, so no second
capture is run. Therefore no register, readiness-ledger, report, or status
transition is authorized, the register family remains released, and the
capability remains `consumer_missing`/`surface_missing`. C14 cannot close DS6
while this remains true.

The closing owner reread is unchanged: disposition register
`c50bd201…c00a`, report `f5b80c7f…f4bc`, status inventory
`25430ee8…d80`, baseline manifest `8c86ea3e…ff55`, and readiness ledger
`4b64f092…ae13`. C13 did not acquire the family lock because its capture gate
was already false.

### Task 14 — DS6-C14: close the evidence workflow slice

**Revision 3.22 status: not executable. C13's capture conjunct is false, so no
closure battery, family write, or slice-close claim is authorized. DS6 remains
open.**

**Declared path cap: 6.** Run the full serialized closure battery, corruption
probes, readiness reconciliation, duplication census, and independent review;
publish exact capability labels and nonreceipts. No missing link is called
complete.

### Task 15 — DS6-C15: close numeric-variable plural-safety gap

**Status: entered, stopped by the mechanism-round breaker, checkpointed, and
forward-reverted. No C15 implementation or active-catalog byte remains at
HEAD.** The measured candidate paths were:

1. `apps/runtime-dashboard/src/shared/i18n/parity.test.ts`
2. `apps/runtime-dashboard/src/shared/i18n/locales/en.json`
3. `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`
4. this plan
5. the DS6 journal

**Declared path cap: 5.** This is the next continuous cluster after C14. A
complete read-only walk of all 2,449 string leaves in each active catalog found
244 message identities carrying a non-`{count}` interpolated variable: 488
locale strings and 149 distinct variable names. The complete partition is 96
identities with no adjacent word, 125 word-adjacent but non-agreeing identities,
and 23 agreement-bearing identities comprising 36 path-variable pairs and 72
locale path-variable instances. `pages.dashboard.narrativeAttentionBody`'s
`{blocked}` is 1/244 of the wider identities and 1/23 of the agreement-bearing
set; it occurs in two locale strings and six outer-count ICU branches. The
current witness fixes `blocked` at `7`, so singular agreement is untested.

The unregistered task-brief P38 diagnosis is that the gate decides whether the
whole message is plural-safe but predicates admission on the literal `{count}`
marker. At this pinned head, the named GY-plan source has sections only through
§3.5.13; P29, P31, P35, and P37 are the registered bars, while the complete
catalog census independently establishes the P38-shaped defect.

Entry measurement corrected the declared numeric-variable population from 67
to 71 names after a complete caller/type audit found `completeness`,
`fallbacks`, `interval`, and `priority`. Those names occupy 183 exact active
path-variable uses: the original-risk 36 pairs plus 147 current non-agreement
uses. The attempted general mechanism used exact point-use set subtraction and
per-variable ICU AST checks; two review-fix rounds closed whitespace,
missing-identity, branch-ownership, and punctuation variants. Final delta
review nevertheless proved that every admitted post-value separator could
still hide an agreeing noun (`;`, `.`, `·`, or `/` followed by a word). That
third mechanism finding tripped the two-fix breaker. Ordinary history preserves
the five-path attempt as a checkpoint and a later forward-revert; no third fix
round is permitted inside C15. A future continuation must explicitly re-cut
and authorize the mechanism rather than treating the reverted 30-test draft as
landed evidence.

### Task 15-R1 — DS6-C15-R1: gate quantitative-use declarations

**Status: entered by explicit continuation on 2026-08-12. Declared path cap:
5.** The exact path set remains the parity owner, `locales/en.json`,
`locales/uk.json`, this plan, and the DS6 journal. A helper module would be a
sixth path and therefore forces another re-cut; C15-R1 does not create one.

C15-R1 carries forward the checkpoint's complete adjudication rather than
repeating it: 71 reasoned quantitative variable names and 183 exact point-use
declarations. The latter comprise the original 23-path/36-pair review cohort
(33 `invariant`, three `pluralized`) plus 147 other reasoned `invariant` uses,
for 180 invariant and three pluralized declarations in total. The active copy
partition remains 20 label-form messages plus three genuine ICU-plural
messages, with no split, exemption, or forbidden 4x4 nested plural. Label form
is guidance for reviewers and copy authors; it is not an admission predicate.

The gate proves the bounded, decidable property **declaration complete for the
declared 71-name quantitative population**. For each active locale separately,
it recomputes every point-use identity, subtracts the 183-key declaration set
in both directions, and fails on an undeclared use or stale declaration. Every
declaration is exactly `pluralized` or `invariant` and carries a non-empty
reason. A `pluralized` declaration additionally parses the real ICU message
and proves that a cardinal plural owned by that same variable protects every
raw occurrence through every select/plural/tag branch. An `invariant`
declaration is admitted by exact membership plus its reason only; the gate does
not inspect punctuation, adjacency, separators, labels, or surrounding words.
The numeric-looking-name scan remains a point-of-use adjudicator worklist for a
name outside the 71-name census and never decides grammatical safety.

Predicate provenance is explicit under P37: active point-use membership and
same-variable cardinal-plural ownership are `recomputed`. The rule-owned
quantitative-name and invariant declarations are `consumer_asserted` and
fingerprinted at admission; their independent semantic adequacy is
`not_established`. Neither supplied predicate carries the bounded positive
gate, so this gate is not described as an automated plural-safety proof. Its
claim is that every in-scope use was declared and that every declaration marked
`pluralized` actually has the stated structure.

**Refused mechanism — do not re-attempt.** A text-shape predicate cannot decide
whether a following word declines. The stopped C15 supplied three independent
members of that one mechanism class: punctuation admitted
`Processed ({events}) events`; narrowing the boundary still admitted
`Events: {events} (events)`; and every retained separator (`;`, `.`, `·`, `/`)
admitted `Events: {events}<separator> events`. Conversely, forbidding a word
after a variable rejects legitimate invariant copy such as
`{completed}/{total} stages` and `{count} online`. These findings set P29/P31/
P33's bar: no text-shape predicate, narrowed separator set, or morphological
guess may participate in this gate's admission decision.

Red-first acceptance requires three named failures: a `pluralized` declaration
with any occurrence outside its same-variable plural returns
`plural_ownership_missing`; an `invariant` declaration with a missing or blank
reason returns `reason_missing`; and a real newly-added active-catalog use of a
known quantitative variable absent from the exact declaration set returns
`declaration_missing`. The Russian catalog remains outside active enforcement
and must retain its 2,449-key cardinality, key-set fingerprint, leaf-value
fingerprint, and raw bytes. A fourth distinct finding class against this
declaration mechanism stops the cluster; another separator variant belongs to
the already-refused text-shape class and cannot reopen that mechanism.

Initial independent review found and the first batched repair closed three
distinct declaration-mechanism classes: omitted reasons threw instead of
returning `reason_missing`; a same-variable `select`/`selectordinal` could
launder a cardinal plural nested in one branch; and brace-regex discovery
disagreed with the runtime ICU AST for quoted arguments. Point-use membership
is now AST-derived with malformed templates failing closed, every same-variable
non-cardinal selector is an occurrence requiring cardinal ownership, and
missing/non-string reasons return the named code. Those three classes consume
the allowance: any new distinct mechanism class in delta review is the fourth
and stops C15-R1.

This adjacent class does **not** block C03. The governed
`baseline-test-i18n-count-debt` / `i18n-count-message-parity` row is exactly the
three inherited `overBudget` failures; C15 covers numeric variables that rule
never admitted. The `reviewers` exemption is separately marked
`declared, unenforced` now and no caller-source marker is mistaken for a
behavioral witness.

### Task 16 — DS6-C16: close deferred-lane diagnostics

**Exact path set declared before repair entry:**

1. `apps/runtime-dashboard/src/shared/ui/LineageGraph.test.tsx`
2. `apps/runtime-dashboard/src/shared/i18n/parity.test.ts`
3. `apps/runtime-dashboard/src/test/evidence/atlasManualAtMaturity.ts`
4. `apps/runtime-dashboard/src/test/evidence/atlasManualAtMaturity.test.ts`
5. `apps/runtime-dashboard/src/test/a11y/OpaqueBackgroundContrast.stories.tsx`
6. this plan
7. the DS6 journal

**Declared path cap: 7; measured candidate set: 7.** C16 closes the sixteen
diagnostics emitted by C05's previously deferred whole-suite, typecheck,
production-build, and lint lanes: one C15-R1 importer assertion, four C02/C09
TypeScript errors, and eleven C15-R1/C09 lint errors. The build's four repeated
TypeScript errors are the same diagnostics, not four more. The C02 opaque
browser precondition is a separate fixture defect: its repair must make the
controlled Storybook ancestry actually opaque while leaving
`hasOpaqueBackground` byte-identical and retaining the atomic seven-source
denominator. If that requires loosening the predicate, the cluster stops.

The two deprecated Zod calls are an admission-sensitive refactor. The valid
owner payload and a payload with unknown top-level and nested evidence-ref
keys must have identical admission behavior before and after the replacement;
any changed admitted set stops the cluster. The nine parity findings are
classified from a scoped mechanism diff: a static-only round is free under the
mechanism breaker only if the 34-test behavioral result and every governed
catalog byte are unchanged. A finding that exposes dropped logic is a
mechanism finding and must remain within this seven-path cut.

Source freezes before one serialized closeout wave. Supplied controller
ceilings are 1,200 s for whole-suite Vitest, 2,400 s for lint, and 300 s each
for typecheck, production build, opaque Storybook browser Vitest, and component
a11y. Every duration is recorded with its observed host regime; a killed run
is a nonreceipt, and a ceiling overrun is a finding rather than permission to
raise the ceiling. Closure requires the complete whole suite, typecheck,
production build, lint, and opaque probe to finish green. Component a11y is
rerun as the inherited 85/85 denominator receipt; it is not a substitute for
the separate browser result.

The opaque lane's first classified RED established one additional fixture
boundary: axe 4.11.4 reports CandidateFrame's visible, `aria-hidden` `⊙`
decoration as manual-review non-text. The fixture may exclude only that exact
live-DOM node (one `SPAN`, exact content and cardinality asserted). The real
adapter fails closed on every other text-bearing `aria-hidden` source root or
descendant, and descendant/root adversarial witnesses invoke that same adapter.
This is a bounded text-rule scope, not an incomplete-to-pass conversion;
every remaining incomplete still produces zero source receipts.

**Suspended-gate cause:** a deferred heavy-lane fence silently suspends a
standing gate unless every excluded gate is named at the point of use with its
owner and re-entry condition; otherwise the omission is rediscovered only by
paying for the lane (GY-DI2/P38).

The post-C16 read-only attribution identified the three non-print visual
baselines that regressed after DS4's 17/18 receipt. Task 17 records their
introducing commit, mixed shared-fixture finding, owner, and cap; none is part
of C16's repair set. The later C10 attempt is preserved and forward-reverted
under its consumed mechanism breaker.

### Task 17 — DS6-C17: reconcile C15-R1 visual baselines

**Status: declared from post-C16 read-only attribution; not entered. Exact
candidate path set:**

1. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/evidence-promotion-focus-chromium-darwin.png`
2. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/dark-evidence-fabric-chromium-darwin.png`
3. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/mobile-command-center-chromium-darwin.png`
4. this plan
5. the DS6 journal

**Declared path cap: 5.** DS4-C19b's clean receipt at `470a802d4` was 17/18,
with only DS8's `run detail A4 print` red. C05 at C15-R1 revision
`4748b921113b884a3fe17593bc50c1af300e97f2` measured 14/18. The visual spec,
all three baseline PNGs, and their consuming components are byte-identical
from DS4 through C05; the persistent changed input is C15-R1's active-English
label-form copy. `evidence promotion focus` binds
`pages.evidence.runContextSummary`, `panels.dataIntelligence.focusSummary`,
and `phase32.freshness.derivedFacts`; `dark evidence fabric` binds
`phase32.freshness.derivedFacts`; `mobile command center` binds the three
dashboard attention/throughput/evidence narrative bodies. The same strings
first appeared in stopped checkpoint `8fd8f9e5d`, were removed by forward
revert `4d7743f07`, and were persistently reintroduced by C15-R1. C01-R1's
fixture-selected branches render byte-identical text and are not an
introducing visual change.

The two evidence-page baselines also expose a separate shared fixture defect.
Their connector records carry `last_health_check=null`, so
`EvidenceFabricPage` selects run-context or promotion-candidate response
`meta.generated_at`, and `buildFreshnessBraidView` uses that selected response
time as its fallback observation. `ApiMeta.generated_at` is supplied by the
production `_utc_now` default in `src/polisyos/core/contracts/runtime.py`; DS4
froze the browser clock but did not bind this visual-fixture response metadata
across process starts. There is therefore no post-DS4 introducing commit for
the timestamp drift. This is a shared visual-harness/DS4-C19b finding, not
permission to change production `ApiMeta` semantics and not a DS5 change. The
repair is DS6 visual-harness work, not a production-backend repair.

Owner discovery established that deterministically binding the selected
evidence-response metadata requires the real visual-spec fixture path. That is
a sixth path in addition to the three PNGs and two records. C17 therefore
measured above its declared cap before entry and was not entered. Under the
sizing law the cap is not enlarged: the work is re-cut below with the next
continuous number. The C05 evidence-promotion capture timed out before a stable
final comparison, so its actual PNG is not re-anchoring authority.

### Task 18 — DS6-C18: fix the visual fixture, then re-anchor C15-R1 deltas

**Status: verified and ready to land; commit and post-commit branch readback
remain pending. Exact re-cut set:**

1. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`
2. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/evidence-promotion-focus-chromium-darwin.png`
3. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/dark-evidence-fabric-chromium-darwin.png`
4. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/mobile-command-center-chromium-darwin.png`
5. this plan
6. the DS6 journal

**Declared path cap: 6; measured candidate set: 6.** The contract-harness
experiment was restored to HEAD and is not a C18 path. The retained mechanism is
bounded fixture determinism, not a claim that JavaScript can prove compositor
pixel stability: three exact GET responses—run evidence context, promotion
candidates, and connectors—are fetched through `route.fetch()`, fail closed on
missing or malformed `meta.generated_at`, and replace only that value with the
established visual clock. `page.clock.setFixedTime()` freezes wall time while
live timers continue. A browser witness exercises all three real routes; the
promotion capture additionally waits for and validates the catalog response
and observes response-derived readiness. Playwright's direct
`toHaveScreenshot` remains the canonical raster comparator. No wrapper,
sampling admission rule, comparator relaxation, or tolerance change remains.

The complete denominator is one spec with **19 tests**, **18 literal
`toHaveScreenshot` calls**, **18 unique screenshot names**, and **18 PNGs**.
The frozen visual-spec SHA-256 is
`9b634763d8708e0e00d20998e0928f43ad6157b7c0cd7ec690b1ff20d2ae9361`.
Independent source reviews are CLEAN. Only the three attributed PNG identities
moved; the DS8 print PNG and visual configuration remain byte-identical.

#### C18 deterministic fixture and closeout receipt

The pre-fixture no-update baseline ran from `apps/runtime-dashboard` with one
heavy DS6 parent and the supplied 2,400-second ceiling:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --output=../../_build/apps/runtime-dashboard/ds6-c18-01-pre-fixture-full
```

It returned RED with 14 passed and four failed in `real 117.26` seconds. The
before/after `uptime` load triples were `3.97 5.26 4.55` and
`6.64 5.98 4.93`; the regime was exactly
`shared_host_uncontrolled_external_load_one_ds6_heavy_parent`. Its true
strength is one complete live no-update mismatch census at this HEAD and in
that regime. It is not a stability receipt, snapshot-generation authority, or
post-fixture result. The four failures were `evidence-promotion-focus.png`,
`dark-evidence-fabric.png`, `mobile-command-center.png`, and the separately
DS8-owned `run-detail-a4-print.png`.

The complete source-derived denominator is one visual spec containing exactly
18 screenshot calls and one snapshot directory containing exactly 18 PNGs:

1. `command-center-shell.png`
2. `scenario-composer-dark.png`
3. `run-detail-summary.png`
4. `evidence-promotion-focus.png`
5. `clerk-chat-shell-lite.png`
6. `dark-evidence-fabric.png`
7. `mobile-command-center.png`
8. `mobile-run-detail-overview.png`
9. `logo-mark-16-32-48.png`
10. `run-deck-content-slide.png`
11. `ds4-candidate-clothing.png`
12. `ds4-fixture-only-boundary.png`
13. `ds4-evidence-primitives.png`
14. `decision-reading-view-a4-print.png`
15. `run-detail-a4-print.png`
16. `bureaucratic-document-a4-print.png`
17. `policy-compare-a4-print.png`
18. `scenario-a4-print.png`

The retained nineteenth test behaviorally fetches the real run
evidence-context, promotion-candidates, and connectors responses and binds
their `meta.generated_at` values to the visual clock. Before the fixture it
failed on live time; after the fixture it passed. The post-fixture sequence
also proved that `page.clock.install()` was the wrong clock operation because
it advanced wall time, while `setFixedTime()` preserves a fixed `Date` and live
timers. The promotion page's 250 ms debounced catalog query is handled at its
point of use by awaiting the exact GET, validating its typed response, and
observing response-derived copy before the direct screenshot assertion.

The source-frozen authoritative sequence is:

- run 35, `ds6-c18-35-final-source-update`: targeted generation GREEN 3/3,
  `real 38.50`, `user 39.94`, `sys 5.28`, loads
  `2.00 2.32 2.37` -> `3.80 2.70 2.50`;
- run 36, `ds6-c18-36-final-source-targeted-no-update`: targeted verification
  GREEN 3/3, `real 26.77`, `user 26.04`, `sys 3.38`, loads
  `3.57 2.67 2.49` -> `3.93 2.81 2.55`;
- run 37, `ds6-c18-37-final-source-full-no-update`: genuine full-envelope RED
  17/19, `real 103.86`, because `scenario composer` oscillated between
  1094x453 and 1094x3877 while the known DS8 print remained RED;
- run 38, `ds6-c18-38-scenario-stability-diagnostic`: isolated scenario GREEN
  1/1, `real 20.83`, showing the extra run-37 failure was not a stable C18
  baseline delta;
- run 39, `ds6-c18-39-final-source-full-no-update-rerun`: controlling full
  expected RED 18/19, `real 93.69`; its sole failure is DS8-owned `run detail
  A4 print`, 724x2113 expected versus 770x13229 actual with exactly 691,791
  differing pixels.

Every run used supplied ceiling 2,400 seconds and regime
`shared_host_uncontrolled_external_load_one_ds6_heavy_parent`; no run was
killed and none exceeded its ceiling. Run 35 is generation only, run 36 is the
targeted verification receipt, and run 39 is the controlling full envelope.
Run 37 remains a genuine RED rather than being erased by the control. The
journal preserves all earlier runs and nonreceipts at their original strength.
The enumerated fixture blast radius is exactly the two evidence baselines,
while the re-anchor radius is those two plus the C15-R1 mobile copy baseline;
no fourth DS6 identity moved.

Final DS6 baseline SHA-256 values are `03e69c28aeda2baf2caca233b050c31193b0b327f269ef32cf27c3f34a73e667`
(evidence promotion), `f5a8c3257cb070bc276827c1cefcc6fc9f85864af20f3f56d531d394fcc0d98f`
(dark evidence), and `23cab2cb08f15b1ee668faf1de5a4a81a4ba2dc1ec214d29981c7b575a49557d`
(mobile command center). The DS8 print baseline remains byte-identical at
SHA-256 `a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`
and git blob `104ef3c896c3897de48252409494b867b0820f66`.

**Refused mechanism.** A generic sampled/event/prototype/compositor-stability
gate is refused for C18. Repeated P31/P38 review showed one class: JavaScript
activity is a proxy for compositor pixels, not the property. Sampling missed a
250 ms asynchronous mutation; event/prototype variants missed WAAPI
construction, `MediaList`, computed style, aliased raw capture, and retained
proxy cleanup; an observer ending before the matcher did not cover the
screenshot transaction. Closing those instances still cannot discriminate an
unchanged raster from compositor-only or browser-internal work. No later
cluster should re-attempt that gate by adding another hook. C18 instead fixes
the known drifting inputs at the fixture and leaves raster comparison to
Playwright.

Pattern closeout: P08 separates response time and fixed wall time; P29/P33 are
closed by the browser route/clock witness and response-derived readiness; P35
is closed by the complete 19-test/18-call/18-name/18-PNG census. P31/P38 record
the refused generic gate rather than laundering a proxy into admission. The
two active `attr(href)` print emitters stay registered as DS8-owned duplicate
debt rather than being changed here. The exact candidate remains six paths;
the commit and post-commit branch readback are pending.

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
| C15 | `DS6-C15 close numeric-variable plural safety` | 5 |
| C15-R1 | `DS6-C15-R1 gate quantitative-use declarations` | 5 |
| C16 | `DS6-C16 close deferred-lane diagnostics` | 7 |
| C17 | `DS6-C17 reconcile C15-R1 visual baselines` | 5 |
| C18 | `DS6-C18 fix visual fixture and re-anchor C15-R1 deltas` | 6 |

## Deferred execution package

This is one consolidated, executable handoff. The governed writes remain
descriptive until DS5 releases their owners. C05 executed the original heavy
package and C16 executed the diagnostic closeout subset; their measured
receipts below supersede the earlier waiting state without authorizing any
governed write.

### Contended governed writes after DS5-C21

**I18n lifecycle, DS6-C03.** Apply through the existing producer/checker, not a
hand edit:

1. `architecture/atlas_surfaces/frontend-baseline-debt-manifest.json`:
   transition `vitest.disposition` `rebind_pending -> resolved` and remove the
   complete sole `i18n-count-message-parity` debt-class object from the C16
   authorized green whole-suite receipt package. Its resolved values are:
   `command=/usr/bin/time -p corepack pnpm exec vitest run --reporter=json
   --outputFile=../../_build/apps/runtime-dashboard/ds6-c16-vitest-final.json`,
   `wall_duration_seconds=515.40`,
   `vitest_duration_seconds=512.9371760253906`, `exit_code=0`,
   `test_files={total:317,passed:317,failed:0}`,
   `tests={total:983,passed:983,failed:0}`, and the RFC8785/JCS empty-array
   `failure_set.sha256=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
   The raw JSON receipt SHA-256 is
   `0621a29ad48454fa57c232206f2eec26267e82ad5285879dacc02bf29ebe79ec`.
   The register's `repair_commit` is the landed C16 commit, not a projected
   pre-commit revision field. Preserve
   `parent_reproduction` as historical provenance; it is not a substitute
   receipt. The field-specific sources below are the only admissible producers
   of those resolved values.
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

**C09 maturity consequence.** C09 adds no governed-row transition. In
particular, the contended `unit_id=evidence-manual-at` row retains its
current value. C08 now supplies real CAS persistence and integrity, so the
remaining reason is specifically C10's absent
reconciliation consumer and surface. C09 contributes no projected C03 field;
the C16 receipt measures the resulting population. Upgrading the row without
C10 would be a false capability claim under P01 and P32.

**C12 protocol consequence.** C12 likewise adds no governed-row transition and
does not add a C07 receipt kind. INT-R3 content, a generic reviewer producer,
persistence, measurement, and reconciliation are absent, so the protocol
remains `contract_only`. C12 changes the future whole-suite population but
contributes no projected C03 field; the authorized receipt measures it. No
future threshold or stable-bar effect is included in the deferred write.

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
row—to `status: repaired`, retain the three evidence refs that cover the seven
source identities, add the actual `repair_commit`, and regenerate the same
report and induced status receipt.
The C16 receipt is exactly 7/7: one Storybook story passed in 14.02 s, its raw
JSON SHA-256 is
`a608e9b606e50b75bef602136e0f9b0c47406dfedf0f68888b792b781e99eafa`,
and all seven numeric source receipts were admitted atomically. Therefore C06
is now gated only on C04's released register-family write.
This discharges the master sentence that makes the DS4 prose table authoritative
“until DS6 creates one.” It does not enter the Vitest debt-class array, because
the four axe-incomplete clusters were never failing Vitest identities.

**Contended-package readiness.** Four prepared executable deltas are **READY**:
C03, C04, and C06 are separate append-only transitions once the register
window opens, and each begins by rereading current owners and content-hash
anchors; C13 is the fourth delta and is an exact `NO WRITE` hold until DS8
supplies a repair, an independently established semantic-non-overlap result,
and two consecutive stable no-update captures. No C10-R1 projection delta
exists at HEAD. The package is therefore three governed writes plus one
executable held no-write, not four governed transitions.

### Serialized heavy-lane package and measured execution

Run from `apps/runtime-dashboard` after the explicit release, serially in the
order shown. `/usr/bin/time -p` is part of each first authorized command so its
`real` value is the suite's one measured wall-time baseline:

```bash
mkdir -p ../../_build/apps/runtime-dashboard
git rev-parse HEAD
/usr/bin/time -p corepack pnpm exec vitest run --reporter=json --outputFile=../../_build/apps/runtime-dashboard/ds6-c03-vitest.json
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

The first three lines form C03's governed receipt package and run only after
both C03 gates are satisfied. The first line creates the repository-ignored
output directory and supplies no governed field. Source provenance is
field-specific: the literal third command supplies `command`; the second line,
`git rev-parse HEAD`, supplies `revision`;
`/usr/bin/time`'s `real` supplies `wall_duration_seconds`; the Vitest JSON
supplies Vitest duration, file/test counts, and failure identities; runner
process status supplies `exit_code`; and the then-current manifest
producer/checker computes `failure_set.sha256` and the resolved
failure/debt-class state. No control arithmetic or focused run supplies a
governed hole, and no assumed empty-set hash is copied.

C05 established the first measured wave and C16 used the hard ceilings declared
under Task 16; no ceiling was raised in flight. The C16 journal records each
`real` duration with its host regime. A killed run remains a harness
nonreceipt, not a timing sample or product regression.

Lint now has two measured regimes: C05's cold run was **1,182.94 s** and C16's
warm shared-`_cache` run was **19.18 s**, a **62x** spread. That is the measured
price of DS-INFRA-1's shared-cache state. A future ceiling is derived from
`2 x p95` of successful runs in the matching regime, never from a margin over
the minimum; a sample without its host/cache regime is not a usable timing
sample.

`corepack pnpm run storybook` and any standalone dashboard dev-server command
remain unrun; the targeted Storybook browser runner managed its own browser.
The original reason for waiting was not OOM risk or ordinary slowdown: the
governed host-contention budget measured
the same GY writer at 194.9–426.3 seconds (2.2x) and a full Atlas module at
393–754 seconds (1.9x). Concurrent heavy work can push the governed writer past
its cap and make policy interpret contention as a product regression. The C16
receipts explicitly record the released shared-host regime rather than erasing
that distinction.

## Slice standing (recorded 2026-08-18)

**DS6's executable set is exhausted. The slice is `blocked_on_another_plan`, not closed, and its
closure cluster `C14` is deliberately not entered.**

Landed: `C00`, `C01`, `C01-R1`, `C02`, `C05`, `C07`, `C08`, `C09`, `C11`, `C12`, `C13` (verification
only), `C15-R1`, `C16`, `C18`, and `C10-R2`, which landed in `main` at `fa1f3e4d0` after `C10-R1`
stopped under the mechanism-round breaker. `C17` is superseded by `C18` and stays unentered.

Every remaining cluster is blocked on a slice DS6 does not own:

| cluster | blocker | owning slice |
| --- | --- | --- |
| `C03`, `C04`, `C06` | the governed writes stay descriptive until the register owners are released | DS5, at `C21` |
| `C13` governed transition | a print repair, an independently established semantic-non-overlap result, and two consecutive stable no-update captures | DS8 |
| `C14` | all of the above | — |

**Reopening is fully specified and needs no re-derivation.** When DS5-C21 releases the owners, `C03`,
`C04` and `C06` run as three separate append-only transitions, each beginning by rereading current
owners and content-hash anchors. When DS8 supplies its repair and the two stable captures, `C13`'s
governed transition follows. `C14` closes after both.

**Carried out of the slice, with owners:**

- `transitive-runner-closure-unbound` — `absent/unallocated`. `observed_by_reconciler` attests intake
  closure, not runner integrity under local code modification. Closing it needs an out-of-band runner
  identity, which a falsifier over all `9,870` tracked files showed does not exist here.
- The `C11` clean-worktree test pin, registered in the Atlas master plan's inherited-Vitest-failures
  row. It is a **defect in that test**, not a non-receipt: the measurement succeeded and the
  expectation is wrong.
- The `scenario composer dark theme` visual-lane instability, and the DS8 A4 print baseline, both
  under their own owners.

## Not yet

- No typed contrast row or i18n baseline removal until DS5 releases the
  contended governed owner. C03's green-receipt gate is discharged; C04 and
  C06 now wait only on that release.
- No landed readiness-ledger CI validator. C10 is a stopped, checkpointed,
  forward-reverted attempt and C10-R1 requires its own clean-tree session. C11
  now persists six instrumented measurements plus the seventh C12 seam; INT-R3
  content, observations, and every honesty threshold remain
  `not_established`.
- No DS8 print repair or governed C13 readiness transition; DS6's independent
  visual RED is evidence for the DS8 owner, not repair authority.
- No Russian catalog deletion or active-locale exposure change; DS5 owns the
  latter mechanic and the frozen catalog remains in-tree.
- No standalone interactive Storybook, page-a11y, or journey rerun is implied
  by C16 or C18. Their C05 receipts retain their original strength; C18 owns
  only the exact visual lanes recorded under Task 18.
- C17 remains unentered because the fixture path measured the cap-5 proposal
  at six paths. C18 is the verified, ready-to-land cap-6 replacement: it
  deterministically re-anchors the three DS6-attributed PNGs. Its commit is
  pending. The DS8 print baseline remains byte-unmodified and RED under its
  existing owner.
