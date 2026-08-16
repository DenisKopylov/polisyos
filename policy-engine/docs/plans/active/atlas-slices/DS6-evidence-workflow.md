---
plan_id: atlas-ds6-evidence-workflow
title: "DS6 - Evidence Workflow & Instrumentation"
type: slice-plan
status: in_progress_stopped_on_c10_mechanism_breaker
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
  then C11, then C17. C10 stopped under its mechanism breaker; its ten-path
  candidate is preserved at `573be959890f8e35f72e846e0a37b6eac5fc4396`
  and removed by forward revert
  `a7ae9189147d012fd8a3c80d741ed5c330787672`. Only this plan and journal may
  now record that stop. C11 and C17 were not entered.
- This session must not write the shared governed Atlas-surface artifacts named
  under **Deferred execution package**. DS5-C21 owns that contended resource
  until it merges. Required deltas are specified there, not applied here.
- C16 was explicitly authorized to run, one heavy parent at a time, the exact
  whole-suite Vitest, full lint, full typecheck, production build, opaque
  Storybook browser probe, and component-a11y closeout lanes declared under
  Task 16. That authorization is consumed. The full visual lane, Playwright
  journeys, dev servers, and every other heavy command are not authorized by
  the post-C16 attribution.
- Focused Vitest over touched files and scoped static checks may establish the
  source freeze, but only the serialized Task 16 lanes establish C16 closeout.
- No product surface, DS5 path, GY path, a11y denominator, baseline suppression,
  skip, quarantine, tolerance widening, merge, push, rebase, force push, or
  stash-as-storage. One scoped commit follows independent review for each
  entered cluster.
- C10 is stopped, checkpointed, and forward-reverted. C11 is technically
  unblocked at six instrumentable metrics plus one `not_established` seam, and
  C17's deterministic visual-fixture repair is DS6-owned; neither was entered
  because the authorized order placed both after a landed C10. C03, C04, C06,
  C13's governed transition, and C14 retain the gates stated below and in the
  journal.

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

**Status: entered, stopped by the mechanism-round breaker, checkpointed, and
forward-reverted. No C10 reconciliation, persistence-extension, CI, or
reference byte remains at HEAD.** The stopped ten-path implementation is
preserved at `573be959890f8e35f72e846e0a37b6eac5fc4396` and removed by forward
revert `a7ae9189147d012fd8a3c80d741ed5c330787672`. Both permitted mechanism
repair rounds were consumed. Final independent review found a Blocking
P29/P31/P32/P37 canonical-runner-provenance/single-intake defect, a second
Blocking incomplete-owner-invariant defect at the same persistence boundary,
and an Important non-bidirectional status-contract defect. The round-2
acceptance rule in the checkpoint required any further Blocking or Important
mechanism finding to preserve and stop the attempt; no third repair is
authorized. Focused green receipts exercise admitted cases in the stopped
implementation only and are withdrawn as C10 closure evidence. C10 is not
landed, and its governed projection tail remains deferred.

**Declared path cap: 16; measured stopped-attempt set: 10.** Derive ledger
claims and actual test/evidence
existence from their canonical owners, independently reconcile them, persist
the reconciliation receipt, fail CI for `stable`/`implemented` overclaim, and
surface the result in the governed audit/reference projection.

### Task 11 — DS6-C11: instrument the seven Atlas health metrics

**Status: technically unblocked but not entered after the C10 stop.** Six
metrics can be instrumented against current repository owners; honesty
comprehension/review effectiveness retains C12's instrument seam with every
threshold `not_established`. This is a sequencing nonreceipt, not an INT-R3
block on the other six metrics.

**Declared path cap: 12.** Produce typed, versioned, replayable measurements
for primitive adoption, fail-closed fidelity, audience enforcement,
`surface_missing` closure, evidence coverage, machine-twin parity, and honesty
comprehension/review effectiveness. Unknown, zero, missing, and incomparable
remain distinct.

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

### Task 13 — DS6-C13: independently verify DS8 adjacent print export

**Owner-discovered path set declared before the browser lane:**

1. this plan
2. the DS6 journal

**Declared path cap: 6; measured candidate set: 2.** Consume DS8's shipped
surface without editing it. The unique real-browser owner is the filtered
`run detail A4 print` case in `e2e/runtime-dashboard.visual.spec.ts`; the
static snapshot checker proves only markers and image shape, not link/report
non-overlap. Run the real Chromium comparison once under the supplied 2,400 s
ceiling. If it is RED, preserve expected/actual/diff evidence and stop: the
closure conjunction is already falsified. If it is GREEN, a second no-update
capture is required for repeatability and semantic non-overlap still needs an
independent verifier.

The current readiness-ledger and disposition-register owners are contended and
therefore unavailable. Ignored Playwright output plus this reviewed record are
the strongest honest result in C13; no governed readiness/audit transition is
written. Failure returns evidence to DS8 and does not authorize a DS6 product
repair. The capability remains `consumer_missing`/`surface_missing` until the
serialized owner family is released and C10/C14 reconcile the evidence.

### Task 14 — DS6-C14: close the evidence workflow slice

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

**Status: re-cut from unentered C17 after owner discovery; not entered because
C10 stopped first. Exact candidate set:**

1. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`
2. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/evidence-promotion-focus-chromium-darwin.png`
3. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/dark-evidence-fabric-chromium-darwin.png`
4. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/mobile-command-center-chromium-darwin.png`
5. this plan
6. the DS6 journal

**Declared path cap: 6; measured candidate set: 6.** The fixture must bind the
three exact response `meta.generated_at` inputs—run context, promotion
candidates, and connectors—to the established visual clock before any snapshot
update. The complete 18-snapshot-call/18-baseline
denominator is then run without updates to enumerate blast radius. Only the
three attributed identities may move; a fourth identity is a new finding, not
permission to re-anchor. After targeted generation, a no-update pass must
restore those three identities and the full visual envelope may retain only
the separately DS8-owned print RED. The DS8 print PNG remains byte-identical.

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
row—to `status: repaired`, retain the seven evidence refs, add the actual
`repair_commit`, and regenerate the same report and induced status receipt.
The C16 receipt is exactly 7/7: one Storybook story passed in 14.02 s, its raw
JSON SHA-256 is
`a608e9b606e50b75bef602136e0f9b0c47406dfedf0f68888b792b781e99eafa`,
and all seven numeric source receipts were admitted atomically. Therefore C06
is now gated only on C04's released register-family write.
This discharges the master sentence that makes the DS4 prose table authoritative
“until DS6 creates one.” It does not enter the Vitest debt-class array, because
the four axe-incomplete clusters were never failing Vitest identities.

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

## Not yet

- No typed contrast row or i18n baseline removal until DS5 releases the
  contended governed owner. C03's green-receipt gate is discharged; C04 and
  C06 now wait only on that release.
- No landed readiness-ledger CI validator or health-metric producer. C10 is a
  stopped, checkpointed, forward-reverted attempt. C11 is not blocked by
  INT-R3 for its first six metrics, but was not entered after C10 stopped; its
  seventh metric retains C12's `not_established` content/threshold seam.
- No DS8 print repair or governed C13 readiness transition; DS6's independent
  visual RED is evidence for the DS8 owner, not repair authority.
- No Russian catalog deletion or active-locale exposure change; DS5 owns the
  latter mechanic and the frozen catalog remains in-tree.
- No standalone interactive Storybook, page-a11y, journey, or full-visual rerun
  is implied by C16. Their C05/C13 receipts retain their original strength.
- No C17/C18 snapshot regeneration occurred. The deterministic fixture repair
  is DS6-owned; its added visual-spec path measured six paths, so C17 remains
  unentered at cap 5 and C18 is declared at cap 6. The three attributed
  snapshots and DS8 print baseline remain byte-unmodified here.
