---
plan_id: atlas-ds6-evidence-workflow
title: "DS6 - Evidence Workflow & Instrumentation Journal"
type: execution-journal
status: in_progress_stopped_on_c10_mechanism_breaker
created: 2026-08-11
last_updated: 2026-08-16
slice: DS6
baseline_commit: c1a89b6cf0c63573abad6b0ca8374e16b78c47dd
plan: ./DS6-evidence-workflow.md
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
---

# DS6 - Evidence Workflow & Instrumentation Journal

This is the append-only execution record for DS6. A missing receipt, skipped
lane, timeout, or output lost to contention is recorded as a non-receipt; it is
never normalized to green.

## Binding review and orchestration rules

- One clean scoped commit per cluster, after independent review. Before every
  commit: `git status -sb` and branch-attachment proof. After every commit:
  re-read HEAD and committed file set from the branch.
- Review findings and implementation constraints cite the governing plan,
  schema, ratified ruling, failure-register row, or landed sibling that sets
  the bar.
- Important/Critical findings are fixed inside the entered cluster and
  re-reviewed. A new mechanism after two mechanism-changing fix rounds stops
  the cluster; test/receipt/docs-only rounds are free and proved by scoped diff.
- Append-only history: no rebase, reset, force push, or stash-as-storage. A
  stopped attempt is checkpointed and forward-reverted.
- Shared generated/governed artifacts are serialized with DS5-C21; browser and
  other memory-heavy lanes are serialized with the GY producer. No agent may
  expand that authority from local judgment.

## DS6-C00 entry receipt — 2026-08-11

### Worktree and branch isolation

Command:

```bash
git worktree add .worktrees/atlas-ds6 -b codex/atlas-ds6-evidence-workflow main
git status -sb
git rev-parse HEAD
git symbolic-ref --short HEAD
```

Receipt: clean attached branch `codex/atlas-ds6-evidence-workflow` at
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`, the current `main` tip at entry.
`git merge-base --is-ancestor 7f450eb7b HEAD` exited 0.

The main checkout was dirty before worktree creation with:

```text
 M policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
 M policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md
 M policy-engine/src/polisyos/data_forge/read_api/catalog.py
```

The linked worktree began clean. Scoped status/diff for
`src/polisyos/data_forge/read_api/catalog.py` was empty, and the worktree's
tracked byte is the committed base byte. None of the three main-checkout edits
is present in DS6 status, diff, index, or commits.

### Instruction and authority intake

Read completely or through the relevant governing section before design:

- `CONTRIBUTING.md`;
- `docs/reference/policy-design-case-failure-patterns.md`, including P01–P37;
- the master DS6 section and the seven-metric owner table;
- `docs/brand/ATLAS_SOURCE_OF_TRUTH.md`, D4 at `7b6933770`;
- DS4 plan/journal/closure contrast and inherited-debt receipts;
- the current DS5 slice plan/journal shape from its isolated worktree;
- the baseline manifest/schema/checker and supplemental-row producer;
- i18n catalogs/test/consumers; existing axe/Storybook/a11y harnesses.

`corepack pnpm install --frozen-lockfile` completed across six workspace
projects with pnpm 10.33.2. This prevents missing `@polisyos/*` workspace links
from manufacturing false scanner findings. It changed no tracked repository
file.

### Complete-set measurements

- `git ls-files` from the worktree root enumerated 9,756 tracked paths. A
  complete `git grep -E 'DS6-C[0-9]' HEAD` over that tracked tree found zero
  prior DS6 cluster identifier.
- Recursive leaf enumeration found exactly 2,449 string leaves in each of
  en/uk/ru. The sorted key sets are equal at entry.
- Each catalog contains 84 messages with `{count`: 56 ICU plural and 28
  invariant-form. Exactly three invariant paths are absent from the current
  allowlist: `panels.agentPipeline.overBudget`,
  `controlJob.scientistEvents`, and
  `controlJob.humanReviewUnresolved`.
- The loop in `src/shared/i18n/parity.test.ts` aborts at the first failed
  expectation for each locale. Therefore the registered en/uk/ru
  `overBudget` identities mask the two later paths; adding only `overBudget`
  would rotate the three failures and violate the baseline comparator rather
  than close the class.
- The DS4 prose table enumerates four contrast owner clusters and seven unique
  source identities: C01 1, C06 2, C09 1, C14 3. DS4's 85/85 component and
  21/21 browser passing denominators exclude those incomplete nodes.

### Red-first i18n receipt

Command:

```bash
cd apps/runtime-dashboard
corepack pnpm exec vitest run src/shared/i18n/parity.test.ts --maxWorkers=2 --reporter=default
```

Receipt: expected red; 1 file, 4 tests, 1 pass, 3 failures. The failures are
exactly `panels.agentPipeline.overBudget` in en, uk, and ru at the registered
assertion anchor. Duration 2.72 seconds. No implementation byte was changed.

### Entry pattern/capability disposition

Relevant register rows: P01/P02/P03, P05/P15, P07/P08, P09/P10,
P27/P29/P30/P31/P33/P34/P35/P36/P37. The target is a single canonical evidence
chain with real behavioral verifiers, truthful lifecycle, independently
reconciled gate predicates, and exact denominators. Entry labels are recorded
in the plan; no contract-only capability is represented as implemented.

### DS6-C00 review record

The first independent review found three Important and one Minor issue, each
against a named bar:

- master Revision 3.7's measured-timeout law: deferred commands lacked an
  executable first measurement and derived per-suite timeout;
- this plan's sizing law plus P35: the journal's six-path shorthand did not
  enumerate the two induced i18n governed paths;
- this plan's duplication/P35 bars: two zero-duplication conclusions lacked a
  complete-set command, file-type denominator, and comparator state;
- this plan's exact-path cap: C01 used a dashboard-relative instead of
  repository-relative path.

The fix round changed only these two documentation/receipt mechanism paths, so
it is free under the mechanism-round breaker. It added `/usr/bin/time -p` first
measurements and an explicit twice-baseline rounded timeout formula, enumerated
all eight governed paths, recorded the 9,756-path/9,181-text-file duplication
census, and made the C01 path exact. Delta-only re-review closed all four
findings. Independent review receipt `ds6_c00_review_fast` returned CLEAN after
comparison with the current
`docs/plans/active/atlas-slices/DS5-enforcement-waist.md` on
`codex/atlas-ds5-enforcement-waist` at reviewed tip `60a06701c`; its sole
residual is to re-read that governing artifact at C03 entry because the DS5
plan is intentionally absent from this older DS6 base.

## Duplication findings — entry pass

The standing duty found two existing contrast computations, not a reason to
create another:

1. `tools/design/_a11yColor.ts` owns static token contrast math.
2. `apps/runtime-dashboard/src/shared/a11y/ContrastEnforcer.tsx` owns runtime
   ancestor blending, is disabled under tests, and cannot establish a
   gradient-backed contrast result.

Canonical authority for DS6's rendered probe is axe-core's real-browser
`color-contrast` result. Migration is not in scope: the static and runtime
implementations serve different consumers. Concrete divergence: token math
cannot see rendered translucent ancestors, while the runtime enforcer cannot
establish gradient-backed test evidence. No gate currently compares them.

The duplication census walked all 9,756 tracked paths. Its text scope was 9,181
files (`.cjs` 9, `.js` 5, `.json` 1,171, `.md` 1,356, `.mjs` 28, `.py` 5,560,
`.ts` 417, `.tsx` 635). The read-only script selected files by these extensions
from `git ls-files`, then tested complete file contents for the seven exact
source identities, `opaqueBackgroundContrast` / `opaque-background-contrast`,
`COUNT_MESSAGE_ALLOWLIST`, and the three locale imports.

Exactly four files contain all seven contrast source names and all are the
existing master/DS4 plan or closure records; zero tracked text file contains an
opaque-background registry name at entry. This establishes that C02 does not
duplicate a live seven-identity implementation registry within the enumerated
scope; the DS4 prose table remains canonical until the deferred typed row.

Existing Storybook evidence coverage is reused but not edited:
`EvidencePrimitives.stories.tsx` covers most required primitives but lacks the
populated MiniGraph and unavailable WeakestLink states. Extending that
visual-baselined product story would create snapshot contention, so C02 owns a
test-only fixture under the a11y tree.

The same complete census found `COUNT_MESSAGE_ALLOWLIST` in exactly two files:
the implementing `parity.test.ts` and the governed baseline manifest that
quotes its assertion anchor. Exactly two files import all three catalogs:
`LocaleProvider.tsx` (runtime consumer) and `parity.test.ts` (gate). The three
locale JSONs are the message owners; `parity.test.ts` is the sole count-rule
implementation in the enumerated scope, while the manifest is its receipt.
C01 therefore extends the existing gate instead of adding a second scanner.
Concrete divergence is intentional: the manifest freezes only observed failure
signatures, while the gate enumerates the whole live message set. The baseline
comparator checks failures against that manifest; it does not compare the two
implementations because only one is an implementation.

## Consolidated deferred package

The plan's **Deferred execution package** is the executable authority for this
section. The exact contended writes and heavy commands are reproduced there in
one place and are not duplicated here; later receipts append measured output
and do not rewrite the waiting contract.

Current non-receipts:

- the six paths explicitly serialized with DS5-C21 remain byte-unmodified:
  `frontend-disposition-register.json`,
  `frontend-baseline-debt-manifest.json`,
  `status-retirement-inventory.json`,
  `check_frontend_disposition_register.py`,
  `test_frontend_disposition_register.py`, and
  `docs/reference/frontend/atlas-frontend-disposition-register.md`;
- the complete i18n lifecycle writer also requires two induced paths outside
  this session's fence—`frontend-baseline-debt.schema.json` and
  `test_frontend_baseline_debt_manifest.py`; all eight governed paths remain
  byte-unmodified and C03's nine-path cap includes these eight plus the journal;
- the typed rendered-contrast supplemental row does not yet exist, so the DS4
  prose table remains authoritative;
- Storybook browser Vitest, whole-suite component/a11y Vitest, Playwright page
  a11y/journeys/visual, full lint, full typecheck, full build, Storybook build,
  dev server, and interactive Storybook are unrun due to the governed GY
  contention budget;
- the browser portion of the new probe is therefore a non-receipt, not green.
- numeric per-suite heavy-lane timeouts are `not_established`: each exact
  deferred command first records `/usr/bin/time -p` wall time without an outer
  kill, after which the plan requires the explicit twice-baseline/30-second
  rounded controller timeout for every rerun.

## Orchestration note — entry

Three read-only research lanes were separated from the serialized resources:
plan/authority intake, i18n root cause, and contrast-probe design. None wrote a
repository file, index entry, commit, governed artifact, or browser state.
Their complete-set findings were reconciled here before implementation.

C00 owns only the two plan paths. C01 and C02 will each be independently
reviewed and committed. Then this worktree stops at the clean light-half
boundary. DS6-C03 and later remain declared but unauthorized; no local pass or
available idle capacity changes that gate.

## DS6-C01 — count parity and frozen Russian continuity — 2026-08-11

### Entry and red-first binding

C01 entered from clean committed C00 `b28101e42` on the attached DS6 branch.
The declared set is exactly
`apps/runtime-dashboard/src/shared/i18n/parity.test.ts` plus this journal, at
the two-path cap. The governing artifacts are the master DS6 inherited entry
contract, D4 in `docs/brand/ATLAS_SOURCE_OF_TRUTH.md`, and the exact baseline
class in
`architecture/atlas_surfaces/frontend-baseline-debt-manifest.json`.

The C00 focused red remains the entry witness: one file / four tests, exactly
three failures, `panels.agentPipeline.overBudget` for en/uk/ru at the registered
anchor. The baseline comparator in
`architecture/atlas_surfaces/check_frontend_disposition_register.py` accepts
that exact triple and rejects any new identity or assertion-anchor drift.

### Class repair and semantic separation

The complete 2,449-leaf-per-catalog census found 84 count-sensitive messages
per locale: 56 ICU plural messages and 28 invariant-form messages. The existing
allowlist accounted for 25 invariant paths. Because the loop stopped at the
first failed expectation per locale, `overBudget` masked two later paths:
`controlJob.scientistEvents` and
`controlJob.humanReviewUnresolved`. Adding only the registered path was
red-first rejected in design because it would rotate each locale to a new
baseline identity. C01 therefore adds all three complete-census paths to the
existing `COUNT_MESSAGE_ALLOWLIST`; it adds no second scanner and changes no
message or consumer.

This closes the existing syntactic count-message contract; it does not claim a
human-reviewed plural-grammar receipt. The current consumers pass preformatted
strings, and changing them to numeric ICU inputs would cross this session's
product-surface fence. That semantic copy remains `semantic_test_missing`, not
silently closed by the allowlist.

Separately, the old structural test no longer treats Russian as a third active
locale. Active structural parity is exactly `ukKeys == enKeys`. The test named
`keeps the legacy-continuity Russian key set frozen` carries D4's “frozen/not
deleted” meaning with two assertions over the complete Russian set:

- SHA-256 of `JSON.stringify(sortedRuKeys)` equals
  `67b7a921f503f108a9b47e034c31be130911c1fe8b7b9321fa8a163ef8d271a8`;
- exact cardinality remains 2,449.

Removal from active parity therefore does not convert `frozen` into `gone`.
The catalog remains imported, present, content-bound, and byte-unchanged. D4's
separate “not used” runtime mechanic is not claimed: DS5 still owns active
locale exposure, and `SUPPORTED_LOCALES` remains outside C01.

### Frozen-set deletion witness

Pre-witness Russian catalog byte SHA-256:
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`.
Using `apply_patch`, the single
`panels.agentPipeline.overBudget` Russian key was temporarily deleted. The
focused file went RED at the named frozen-set test: expected the admitted
`67b7a921...` fingerprint, received the 2,448-key
`19468df1f7a734c7622510c4d387a9374c25a0f5a49317bdc86e9100b61edab9`.
The other three count-rule cases remained green. This falsifies the frozen
predicate while leaving its test identity/marker intact, satisfying P29/P33.

The same line was restored with `apply_patch`; no checkout, reset, or stash was
used. Post-restore SHA-256 is exactly
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`,
and `git diff -- src/shared/i18n/locales/ru.json` is empty.

### Focused green receipt

Command:

```bash
cd apps/runtime-dashboard
corepack pnpm exec vitest run src/shared/i18n/parity.test.ts --maxWorkers=2 --reporter=default
```

Receipt after restore: PASS, 1/1 file and 4/4 tests; Vitest duration 982 ms,
test body 23 ms. The test denominator remains four. The three registered
failures disappear and no replacement identity appears in this focused file.

Capability truth: the local gate now has implementation plus focused positive
and negative semantic verification. The governed baseline transition remains
`surface_missing`, and whole-suite confirmation remains
`verification_missing`, until the explicitly deferred DS6-C03/heavy wave.
Nothing in C01 promotes the stale open-debt row.

### Duplication, orchestration, and non-receipts

The C00 complete census remains unchanged: one count-rule implementation
(`parity.test.ts`) plus one governed failure receipt in the baseline manifest.
C01 extends the former and defers transition of the latter; no duplicate
scanner, key owner, status, or product locale registry is introduced.

The implementation lane was bounded to the two declared paths; the controller
completed the marker-preserving deletion witness and restoration. Independent
specification and code-quality reviews returned CLEAN with no Blocking or
Important finding. Both independently recomputed 2,449 keys and the admitted
fingerprint; the spec review also recomputed 84 count-sensitive / 56 ICU / 28
invariant messages per catalog, 29 unique allowlist entries, and the exact
2,448-key deletion fingerprint. The quality review confirmed the existing
dashboard test precedent for the Node crypto import and the exact two-path
diff. Its residual is explicit and accepted: this assertion freezes the key
set, not Russian message values, which is the D4/Task-1 structural-set bar and
no stronger semantic-copy claim is made.

The review round changed no implementation byte. This appended receipt is
documentation-only and free under the mechanism-round breaker. A post-review,
source-identical focused rerun passed 1/1 file and 4/4 tests in 978 ms (22 ms
test body). No contended Atlas-surface artifact changed.
No whole-suite Vitest, Storybook/browser, Playwright, dev server, full lint,
full typecheck, full build, or other heavy lane ran; each remains the exact
non-receipt in the consolidated deferred package. Plain-node design checks wait
for the post-C02 blast-radius wave so they run once against frozen light-half
source.

## DS6-C02 — opaque-background rendered-contrast probe — 2026-08-11

### Entry, authority, and red first

C02 entered from clean committed C01 `82cb9ac57` on the attached DS6 branch.
Its exact four-path set is the new typed registry/classifier, focused contract
test, test-only Storybook browser fixture under `src/test/a11y/**`, and this
journal. This equals, but does not exceed, the declared cap.

The authoritative DS4/master denominator remains four owner clusters and seven
source identities: C01 `Badge`; C06 `ProvenancePopover` and
`ProvenanceMiniGraph`; C09 `TimeSemanticsLabel`; C14 `CandidateFrame`,
`NegativeCertificateCard`, and `WeakestLinkExplainer`. The historic 85/85
component and 21/21 browser receipts remain unedited and do not count any of
these sources green. C02 declares a separate eventual 7/7 rendered-contrast
denominator derived only from the frozen typed registry.

Red-first command:

```bash
cd apps/runtime-dashboard
corepack pnpm exec vitest run src/test/a11y/opaqueBackgroundContrast.test.ts --maxWorkers=2 --reporter=default
```

Receipt: expected RED before the classifier existed. Vite failed to resolve
`./opaqueBackgroundContrast`; 1 suite failed, zero tests executed, duration
934 ms. This is missing-implementation evidence, not a browser receipt.

### Pure evidence classifier

`opaqueBackgroundContrast.ts` owns the one typed seven-source registry and an
atomic classifier. An admitted run requires exactly one observation for every
declared source, an established opaque backdrop, zero violation and incomplete
nodes, and at least one axe pass whose actual and required ratios are both
finite numbers with actual >= required. The registry—not raw axe node count—
owns the denominator.

Any missing, duplicate, unknown, nonopaque, violating, inapplicable-only,
nonnumeric, or below-required observation fails the entire run and emits zero
receipts. In particular, an axe `incomplete` produces
`axe_incomplete_unattributed`, whose type and runtime object have no `sourceId`.
Zero violations alone can never manufacture `computed_pass`. This preserves
the DS4 rule that an incomplete node is neither a violation nor a pass and
cannot be attributed to a source identity.

The pre-review focused contract exercised ten behaviors: 1/2/1/3 cluster
mapping and seven unique sources; 7/7 numeric pass; unattributed incomplete;
no-pass; missing; duplicate plus unknown; nonnumeric ratio; below-required
ratio; declared nonopaque input; and non-browser import of the Storybook
adapter. Review then strengthened this to twelve tests and an exact ordered
registry assertion, as recorded below.

### Real-browser fixture written, not executed

`OpaqueBackgroundContrast.stories.tsx` renders the seven real component
identities in the required states: neutral Badge; open untraced
ProvenancePopover; populated ProvenanceMiniGraph; TimeSemanticsLabel;
CandidateFrame with absent authority purpose and declared exclusions;
NegativeCertificateCard with summary/definitions; and WeakestLinkExplainer
with an empty producer list.

The play adapter makes the iframe `html`, `body`, Storybook ancestors, fixture
surface, each source wrapper, and portalled popover background explicit. It
asserts an opaque computed background and `background-image: none` before axe.
It then runs axe-core's real `color-contrast` rule separately over each exact
selector, extracts axe's emitted `contrastRatio` and
`expectedContrastRatio` data (parsing axe's `N:1` required form), and submits
the observations to the pure classifier. It requires an atomic 7/7 receipt.

No WCAG luminance or ratio implementation was added. Axe owns rendered
contrast; `tools/design/_a11yColor.ts` remains the static token calculator and
`shared/a11y/ContrastEnforcer.tsx` remains the runtime ancestor-blending
consumer. The test-only fixture reuses product components but changes no
product source or existing visual-baselined story.

### Focused non-browser green receipt

The same focused command passed after initial implementation: 1/1 file and
10/10 tests, 17 ms classifier-only on the first green and 1.77 s total / 870 ms
test body on the run that also imports the browser adapter without executing
its play function. This is a non-browser contract and module-resolution receipt
only. The post-review 12-test receipt is below.

The serialized browser command remains exactly:

```bash
/usr/bin/time -p corepack pnpm exec vitest run --config vitest.storybook.config.ts src/test/a11y/OpaqueBackgroundContrast.stories.tsx
```

It was not run. Storybook/Chromium and its resulting 7/7 or honest RED are a
`verification_missing` non-receipt under the GY host-contention boundary. The
first authorized `real` value establishes the suite baseline; later controller
timeouts use the plan's twice-baseline, next-30-second rule.

### Governed surface, duplication, and orchestration

The typed supplemental row remains `surface_missing` because all shared
Atlas-surface writers are serialized with DS5-C21. Its exact ID, evidence refs,
field values, generated-owner/report/status paths, open-to-repaired lifecycle,
and browser prerequisite remain the single consolidated deferred block in the
plan. C02 does not create a prose sibling, second register, or Vitest
debt-class entry.

The entry duplication census remains valid. C02 adds the first executable
seven-source registry and uses the existing axe dependency; it does not copy
either existing contrast calculator. The test-only story is intentionally
separate from `EvidencePrimitives.stories.tsx`, whose visual baseline lacks two
required states and is outside the C02 fence. No comparator currently equates
token, runtime-enforcer, and axe results; their distinct consumers and this
concrete divergence remain reported, not “fixed.”

Implementation remained inside the four declared paths. No contended artifact,
product component, catalog,
historical a11y denominator, DS5 path, or GY path changed. No browser,
Storybook, Playwright, dev server, whole-suite Vitest, full lint, full
typecheck, full build, or Storybook build ran. Plain-node design checks run once
in the post-C02 blast-radius wave after review/source freeze.

### Independent review and first fix round

Specification review returned one Important P29/P33/P37 finding: the initial
unit test supplied `opaqueBackdrop: false` directly but did not exercise the
same rendered-DOM predicate used by the browser adapter. Replacing the private
story helper with `return true` would have left all ten tests green. The review
also checked the C06 state split and confirmed that the open untraced Popover
exercises the empty MiniGraph branch while the separate MiniGraph source
exercises populated labels; no extra source or denominator change was needed.

Code-quality review returned two Important findings:

- `NaN`, negative, or fractional violation/incomplete counts were not `> 0`
  and could falsely admit 7/7;
- the registry test froze only length, uniqueness, and 1/2/1/3 cardinality, so
  a component/selector substitution or reorder could stay green.

All three findings are governed by Task 2's hard-failure contract and the
failure register's P29/P33 behavioral-witness bar; malformed counts additionally
exercise P32's present-but-fake evidence case. The batched fix is the first
mechanism-changing review round: the DOM opacity recomputation moved into the
canonical classifier module and is exercised with the source marker retained;
counts must be finite non-negative integers; and the test binds the full ordered
`sourceId/ownerCluster/component/selector` registry plus receipt order.

Red-first review-fix receipt: 12 tests ran, with exactly two expected failures.
The real opacity helper was absent (`hasOpaqueBackground is not a function`),
and malformed counts still produced `status: pass`. After implementing those
properties, 12/12 passed. A separate marker-preserving registry mutation changed
only C01's component from `Badge` to `BadgeMutationWitness`; the exact registry
test went RED 1/12 with the component diff while all other tests passed. The
mutation was restored with `apply_patch`, and the final focused receipt passed
1/1 file, 12/12 tests, 1.74 s total / 839 ms test body. No mutation byte remains.

Delta-only specification and quality re-reviews both returned CLEAN. The spec
review independently exercised the shared DOM opacity helper and confirmed the
empty/populated MiniGraph state coverage. The quality review independently
recomputed all six malformed-count negatives, the full ordered registry and
receipt order, and a fresh 12/12 focused pass. No second mechanism fix round
was required. This review receipt is documentation-only and free under the
mechanism-round breaker.

The browser lane remains a non-receipt; review of source compatibility is not
rendered evidence.

### Frozen-source allowed blast-radius wave

After both reviews closed, the authorized focused pair ran together with at
most two workers:

```bash
corepack pnpm exec vitest run src/shared/i18n/parity.test.ts src/test/a11y/opaqueBackgroundContrast.test.ts --maxWorkers=2 --reporter=default
```

Receipt: PASS, 2/2 files and 16/16 tests in 2.09 s; parity 4/4 (26 ms) and the
opaque-background contract 12/12 (887 ms). The browser-adapter import test ran;
its play function did not.

All three permitted single-process design checks passed unchanged:

- `corepack pnpm run a11y:contrast` — `Contrast checks passed.`
- `corepack pnpm run a11y:motion` — `Reduced-motion checks passed.`
- `corepack pnpm run a11y:color-blind` — `Color-blind checks passed.`

These token/source checks do not close the rendered axe-incomplete class. They
are separate positive receipts around the still-unrun Storybook/Chromium probe.
No heavy or contended lane was started alongside them.

## DS6-C01-R1 — count-message gate correction and active plural repair — 2026-08-11

### Supersession, authority, and complete census

This receipt supersedes C01's 28-entry `Set` and key-only Russian freeze claims.
The complete pre-repair census is **28 = 19 + 4 + 5**: nineteen genuinely
invariant active count-message identities, four mandatory Ukrainian-agreement
defects, and five individually adjudicated English-technical cases. The five
decisions are: pluralize `pages.composer.curatedConstraints` (no tracked caller,
so a future singular caller must not be silently admitted); pluralize
`pages.composer.capabilitiesVisible` (a live caller admits one capability);
pluralize `pages.evidence.totalProfiles` (the card admits zero, one, and many);
retain `panels.reviewCollaboration.reviewers` because its only tracked caller
uses it only for `participants.length > 1` and uses `solo` for singular; and
pluralize `panels.agentPipeline.variants` (its guard admits one). The active
exemption map therefore contains exactly the nineteen invariant identities plus
the retained caller-domain `reviewers` identity, each with a trimmed,
path-specific reason.

Russian is `legacy_continuity_frozen`, not an active count-rule locale. The gate
preserves its 2,449 sorted-key SHA-256
`67b7a921f503f108a9b47e034c31be130911c1fe8b7b9321fa8a163ef8d271a8` and
its sorted `[path,value]` leaf SHA-256
`0426d4ce0397027d25f5a2053bce794b12e31fbe3757d3afefb24de6ba3f45eb`, using
an explicit code-unit path comparator. The catalog byte SHA-256 remains
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`.

### Red/green receipt and exact diff

TDD red ran before either active locale changed:

```bash
corepack pnpm exec vitest run src/shared/i18n/parity.test.ts --maxWorkers=2 --reporter=default
```

Receipt: 1/1 file, 14 tests, 11 expected failures. The new active-locale gate
reported the eight unrepaired identities; eight table-driven formatter rows
showed the literal singular/plural mismatch; the exact-exemption assertion also
reported the unrepaired identities. The frozen Russian and both rejection
witnesses passed. After only the specified `en`/`uk` repairs, the same command
passed 1/1 file and 14/14 tests in 669 ms (32 ms test body).

The exact five-path diff is:

- `apps/runtime-dashboard/src/shared/i18n/parity.test.ts` — map-backed active
  gate, complete-map assertion, real ICU helpers, Russian value fingerprint,
  formatter rows, and two rejection witnesses.
- `apps/runtime-dashboard/src/shared/i18n/locales/en.json` — eight specified
  plural messages repaired.
- `apps/runtime-dashboard/src/shared/i18n/locales/uk.json` — eight specified
  plural messages repaired with `one`/`few`/`many`/`other` forms.
- `docs/plans/active/atlas-slices/DS6-evidence-workflow.md` — C01-R1
  authorization, five-path cap, Russian ruling, and the then-deferred
  777/777/0 estimate. C15's later two-gate correction retires that estimate;
  actual whole-suite measurement remains controlling.
- `docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md` — this
  correction/receipt section.

This is the first mechanism-changing round for DS6-C01-R1: it changes the
count-message gate from a key-presence check to a recomputed active-locale
semantic rule and changes the eight active message semantics. It is not a
receipt-only round. The `flatMap` callback-index defect found in the first
post-repair run was corrected in the test helper invocation; the final receipt
is green.

### Duplication, review state, and non-receipts

The canonical owner remains `parity.test.ts`; this repair extends that gate and
the existing ICU formatter instead of adding a scanner or ICU recognizer. No
product-surface registry, Russian locale, baseline manifest, a11y denominator,
DS5 path, GY path, or contended artifact changed. Independent specification and
quality reviews remain pending before the controller creates the single cluster
commit.

No whole-suite Vitest, Storybook/browser, Playwright, dev server, full lint,
full typecheck, full build, or contended baseline lifecycle writer ran. Those
heavy and contended actions remain non-receipts under the deferred package; C03
through C06 and C13 remain behind their existing gates. Capability truth is a
focused local gate with semantic and negative witnesses; the governed baseline
transition remains `surface_missing` and `verification_missing` pending C03's
authorized whole-suite evidence.

## DS6-C01-R1 — fix round 1 / mechanism-changing round 2 — 2026-08-11

The active plan binding calls the durable Russian assertion
`keeps the legacy-continuity Russian key set frozen`; the test title is restored
to that exact anchor while retaining the value-sensitive leaf fingerprint.

The complete-census denominator is now recorded from the **read-only Node JSON
walk** at pinned working base `2fc42db92c1bf2e40e77157ffb2528b83e717fe9`.
It parsed 3/3 exact catalog JSON paths —
`apps/runtime-dashboard/src/shared/i18n/locales/en.json`,
`apps/runtime-dashboard/src/shared/i18n/locales/uk.json`, and
`apps/runtime-dashboard/src/shared/i18n/locales/ru.json` — traversed 2,449
leaves in each catalog, and enumerated 28 non-ICU `{count}` identities in each.
That complete walk is the denominator receipt for the inherited
**28 = 19 + 4 + 5** census; it is not inferred from a sample or search index.

The real `Intl.NumberFormat("uk-UA").format(1001)` witness is literal
`1 001` (U+00A0). `IntlMessageFormat` selects the Ukrainian `other` branch for
that formatted value and for the nonnumeric unavailable value. The four
agreement-sensitive `other` branches are therefore neutral label/value forms:
`Активні запуски: {count}; …`,
`Decision-bearing запуски, готові до відкриття з fleet: {count}.`,
`Пов'язані needs: {count}`, and `Події: {count}`. One/few/many remain the
specified agreement forms. The existing eight-row table now proves both literal
grouped and unavailable values through the real formatter without adding
per-path test identities.

The count gate still uses the real `isPluralMessage` recognition helper, but
now also constructs `IntlMessageFormat` with the formatter's dependency. A
plural-marker string that fails that parser is a violation even when the map
contains a non-empty reason. The same live helper proves this with
`{count, plural,}`. This closes the prior regex-only/raw-template gap rather
than checking source markers.

Red first, before the four Ukrainian `other` branches and parser-backed gate:
the focused command ran 1/1 file with 15 tests and 5 expected failures — four
literal grouped-string semantic rows selected false singular/genitive forms,
and malformed `{count, plural,}` was admitted by an exemption reason. After the
minimal repair, the same command passed 1/1 file and 15/15 tests in 650 ms
(36 ms test body). The focused denominator is 15. This round recorded a
`777/777/0` C03 estimate against the committed `766/763/3` open state, but it
was never a receipt and C15's later two-gate correction retires it; the
authorized whole-suite measurement controls.

This is DS6-C01-R1's **second and final mechanism-changing round**. Any further
mechanism-changing finding trips the DS6 breaker; review remains pending, no
commit occurred, and all heavy/contended lanes remain non-receipts.

### Final independent review record — documentation-only closeout

The initial specification review raised the P36 durable-anchor drift as
Important and the P35 complete-census denominator gap as Minor. The initial
quality review raised the formatted grouped-string agreement gap and malformed
ICU admission as Important. Mechanism-changing round 2 closed all four
findings.

The scoped quality re-review is **APPROVED** with no new breakage. The
specification review records its two initial findings as **ADDRESSED**. Its
brief-conflict objections were re-verdict clean after the controller-approved
ignored-brief amendment; there is no specification blocker.

This append records review state only and changes no mechanism byte. It is free
under the mechanism-round breaker: source remains at mechanism round 2/2, and
any further mechanism-changing finding still trips the breaker. Commit and the
final focused rerun remain pending; neither is claimed by this documentation
receipt.

## DS6-C07 — evidence artifact storage entry — 2026-08-11

### Clean entry and predeclared path set

`git status -sb` at entry reported the attached
`codex/atlas-ds6-evidence-workflow` branch with no worktree changes at
`b209516687e59a83ed730fc2cea1e95bfb928fa0`. C01-R1 was therefore a clean
preceding commit before C07 entry. The exact C07 candidate set was declared in
the plan before either new implementation path existed: two files under
`apps/runtime-dashboard/src/test/evidence/**`, one frontend reference page,
this plan, and this journal. The measured set is 5 paths against the immutable
cap of 10.

The storage owner is inherited, not invented. The active
`architecture/runtime_state_layout.toml` registers `.polisyos/audits` as
`local_audit_evidence`, ignored with manual-only cleanup, and its `audits`
state slot admits JSON evidence leaves beneath `.polisyos/audits/<audit-id>/`.
`architecture/local_runtime_state.toml` fixes that class at 365 days.
`architecture/generated_artifacts.toml` already registers the whole ignored
`.polisyos/` family. C07 therefore declares a deterministic Atlas subpath under
that slot and changes none of those three complete owners. The same sources
reserve `.polisyos/cas` and `src/polisyos/core/artifacts/**` for the canonical
raw-blob CAS; C07 content-binds its JSON receipt but does not reimplement or
claim to be that CAS.

### Duplication and capability entry census

A complete `git ls-files` walk covered 968/968 tracked `.ts`/`.tsx` paths under
`apps/runtime-dashboard`. An exact receipt-name search found zero existing
`EvidenceReceipt`/`evidence_receipt` owner. `EvidenceArtifactRef` occurs through
six paths but resolves to one definition,
`apps/runtime-dashboard/src/shared/lib/domain/evidence.ts`; it is the product
run-artifact reference (`artifact_id`, optional kind/media type), not a
verification receipt and lacks C07's authority, time, rule, retention, and
verifier fields. Editing or overloading it would cross the product-surface
fence. The new owner is therefore test-evidence-specific, while the existing
Core CAS and runtime-state slots remain canonical for their distinct concepts.

Capability truth at entry is `producer_missing`, `artifact_missing`,
`bridge_missing`, `consumer_missing`, `verification_missing`, and
`surface_missing`. C07 may close the typed contract and its focused semantic
verification only. C08 owns evidence-specific production/persistence and runner
bridges; C09/C10 own maturity/readiness consumers. The remaining missing labels
must survive this cluster.

### Canonical-owner correction before mechanism entry

The first storage preflight above selected `.polisyos/audits` from its
`local_audit_evidence` label. The complete owner comparison then found that this
would still create a second content-addressed writer beside the canonical Core
CAS. `docs/reference/operations/cas-storage.md` and
`src/polisyos/core/artifacts/{protocol.py,store.py,manifest.py}` establish
`ArtifactStore.put_json()`, `ArtifactID` (`sha256:<64hex>`), immutable manifest,
integrity verification, and the default `.polisyos/cas` ABI. The runtime-state
contract reserves `.polisyos/cas` for content-addressed artifacts and
`.polisyos/audits` for audit-chain/projection evidence. P27/P31 therefore change
the pre-implementation ruling: canonical receipt bytes go through Core CAS;
`.polisyos/audits` may hold a later redacted index/projection, not C07's source
artifact.

No test or implementation path existed when this conflict was found; the
scoped diff contained only this plan and journal. The exact five candidate
paths and cap remain unchanged, while their contract now points to the existing
CAS boundary rather than implementing filesystem persistence. This is a
pre-entry source-owner correction, not a mechanism fix round.

The resulting C07 capability target is deliberately `contract_only`. The Zod
schema/parser can verify receipt semantics and preserve a typed content ref,
but a shaped ref is not content evidence under P29/P32. C08 must use the real
artifact store, resolve the referenced verification payload, verify its
manifest/digest, and persist the receipt before `producer_missing`,
`artifact_missing`, or `bridge_missing` can close. C09/C10 still own consumers.

### Red first and minimal contract

The first focused command was:

```bash
corepack pnpm exec vitest run src/test/evidence/atlasEvidenceArtifact.test.ts --maxWorkers=2 --reporter=default
```

It failed 1/1 test file before collection with the expected unresolved
`./atlasEvidenceArtifact` import; zero tests ran in 771 ms. That red binds the
new contract path rather than a pre-existing product failure.

The minimal implementation then added one strict Zod owner and no filesystem
writer. Its ten semantic tests freeze the existing Core CAS boundary; accept a
complete bounded receipt; reject unknown fields, widened authority, a missing
denial, absent/empty producer or verifier, malformed content refs, missing or
misordered time roles, retention drift, result/finding contradictions, and
duplicate/unordered/unknown audiences; and preserve all five P37 classifications
without authority upgrade. The first green ran the same 1/1 focused file with
10/10 tests passing in 699 ms (11 ms test body), at two workers.

The content reference deliberately has only the Core `ArtifactRef` wire fields
plus payload schema identity. The receipt's own `ArtifactID` is not embedded in
its bytes: C08 receives it from the second real `ArtifactStore.put_json()` call.
This avoids a circular self-hash and keeps shaped-reference resolution and
integrity verification as an explicit missing bridge rather than a form-based
C07 claim.

### Measured blast radius and orchestration state

The scoped working diff is exactly the five predeclared paths: the Zod contract,
its focused Vitest file, `docs/reference/frontend/atlas-evidence-artifact.md`,
this plan, and this journal. Measurement is 5 <= the immutable C07 cap of 10;
no `-R1` re-cut is triggered. The implementation is the initial C07 mechanism,
not a review fix round; the two-fix breaker remains unused for this cluster.

No Core CAS implementation, product API/surface, runtime-state registry,
generated-artifact registry, contended Atlas artifact, DS5 path, GY path, or
Russian catalog changed. The six-path `EvidenceArtifactRef` frontend use set
remains a separate product run-artifact reference with one owner, and the
30/30 tracked Python implementation paths under `src/polisyos/core/artifacts`
remain the sole CAS package examined; no concrete duplicate owner or divergent
value was found.

C03 and C04 were not entered because their baseline/disposition register writes
remain contended with DS5-C21. C05 was not entered because it is the prohibited
serialized browser/heavy wave. C06 depends on C04 plus C05's actual 7/7 browser
receipt and is therefore both gated and unavailable. C08 and every later
cluster were not entered because the user authorized only C07 after C01-R1.
No browser, Storybook, Playwright, dev server, full lint, full typecheck, full
build, whole-suite Vitest, Python CAS test, or contended writer ran; each is a
non-receipt, never green. The consolidated deferred package remains the only
execution handoff for the heavy/contended gates.

The allowed plain-Node blast-radius wave ran once from
`apps/runtime-dashboard`: `corepack pnpm run a11y:contrast`,
`corepack pnpm run a11y:motion`, and
`corepack pnpm run a11y:color-blind` each exited 0 with its named passed
receipt. These checks read design tokens and do not turn any prohibited browser
or whole-build gate green. Source is now frozen for independent C07 review.

### Independent review and mechanism fix round 1

The specification review found three Important issues against the Task 7 and
P01/P32/P33 bars: a valid but unrelated CAS payload could satisfy the shaped
reference; producer and verifier identities could collapse; and the reference
page omitted `verification_missing`/`surface_missing` while the journal retained
them. The quality review found one distinct Important issue against Core
`canon_json.py` and P29/P33: default `put_json()` rejects the numeric floats in
the named contrast evidence, so the C08 storage recipe was not executable. Its
minor requested behavioral coverage of all three closed evidence kinds. No
review reported a Blocking finding; both independently confirmed the five-path
cap and no second CAS writer.

The controller's source comparison also found a P30 vocabulary drift before
the batch: C07 had used consumer-purpose labels as audiences even though
`surface-readiness-ledger.schema.json` and the Atlas constitution already own
`PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE`. That drift joined the same fix round.

Red first, the expanded focused file ran 12 tests with the expected 6 failures
and 6 passes in 877 ms. The failures covered the absent payload schema/binding
function, missing complete CanonSpec/input role, old audience vocabulary, and
the new collapsed-verifier/evidence-kind consequences. After the single batch,
the same focused command passed 1/1 file and 12/12 tests in 751 ms (15 ms test
body).

The repair adds a strict, versioned verification-payload envelope; freezes its
Core CanonSpec with finite floats admitted and NaN/Infinity rejected; constrains
the content ref to that exact kind/schema; compares resolved artifact ID plus
evidence kind, subject, rule, producer/verifier provenance, times, and result;
requires distinct producer/verifier component identities; and mandates the
receipt manifest's canonical `inputs` role `verification_payload`. The
valid-but-unrelated witness retains a valid SHA-256 identity and schema markers
while changing each bound semantic field in turn. Audiences now reuse the
four-value Atlas owner, and the full missing-label set is consistent.

This is C07's first mechanism-changing review fix round: the scoped mechanism
diff changes `atlasEvidenceArtifact.ts` and its behavioral test, not only
receipts/docs. It consumes round 1 of the two-fix breaker. Independent delta
re-review and the final allowed verification wave remain pending; no commit is
claimed here.

### Delta re-review and induced deferred arithmetic

The specification delta re-review is **CLOSED** with no remaining Blocking or
Important finding. It independently confirmed the exact payload discriminator,
resolved ID plus six semantic comparisons, canonical receipt-input role,
distinct verifier, full missing-label set, controlled audience vocabulary,
five-path cap, clean whitespace, and a 12/12 focused receipt. The quality delta
re-review is also **CLOSED**: the complete float-admitting/non-finite-rejecting
CanonSpec, all three evidence kinds plus unknown rejection, Zod-v4 binding
helper, and 12/12 focused receipt have no remaining Blocking/Important issue.

At C07's landing, its new focused Vitest file induced a provisional update to
the consolidated C03 arithmetic. The committed open baseline was 263 files and
766/763/3 tests; the C01-R1 estimate was 263 files and 777/777/0 tests (+11),
and the post-C07 estimate became 264 files and 789/789/0 tests (+1 file/+12
tests). These were never receipts. C15's later two-gate correction retires the
whole sequence as future governed values; only the authorized whole-suite
measurement may populate the named holes.

The frozen final allowed wave ran after both reviews and the record-only
arithmetic correction. Focused C07 Vitest passed 1/1 file and 12/12 tests in
749 ms (15 ms test body) with `--maxWorkers=2`. The three single-process Node
checks again exited 0 with `Contrast checks passed`,
`Reduced-motion checks passed`, and `Color-blind checks passed`. No prohibited
gate joined that wave. The final specification record-only recheck found and
closed the older `776` typo above; at that point the journal consistently
recorded the C01-only 777 and post-C07 789 historical estimates. C15 later
retired both as prospective governed values.

A final pre-commit refresh after that record-only correction passed the same
focused C07 Vitest file 1/1 and 12/12 in 758 ms (15 ms test body) with
`--maxWorkers=2`. The three allowed single-process Node design checks again
exited 0 with their named pass messages. This refresh did not run or convert
any deferred heavy lane into a receipt.

## DS6-C09 — residual registration and owner discovery — 2026-08-11

### Clean entry and residual census

`git status -sb` at session entry reported a clean attached
`codex/atlas-ds6-evidence-workflow` at
`85a839f27d1471a348d2f644f24bf599e60b2c61`, five commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. No contended, DS5, GY,
product-surface, or Russian-catalog path was present.

A read-only Node traversal parsed all 2,449 string leaves in each of the exact
active catalogs `locales/en.json` and `locales/uk.json`. It extracted every ICU
or simple interpolation variable, excluded only the exact `count` identity,
and enumerated 244 message identities / 488 locale strings carrying 149
distinct non-count variables. The complete semantic partition is 96 identities
without an adjacent word, 125 word-adjacent but non-agreeing identities, and 23
agreement-bearing identities. The latter contain 36 path-variable pairs / 72
locale path-variable instances.

The complete agreement-bearing set is enumerated rather than sampled. Each
entry names the exact message identity followed by every non-`count` variable
whose numeric value selects an agreeing word:

- `causal.pipeline.stageProgress`: `total`
- `common.lineageGraph.threshold`: `nodes`
- `pages.artifacts.trinity.bindingSummary`: `bindings`, `parameters`
- `pages.dashboard.narrativeAttentionBody`: `blocked`
- `pages.dashboard.narrativeEvidenceBody`: `docs`, `promotions`
- `pages.dashboard.narrativeThroughputBody`: `success`, `total`
- `pages.evidence.runContextSummary`: `needs`, `plans`, `promotions`, `artifacts`
- `pages.runs.evidenceSummary`: `plans`, `promotions`
- `panels.dataIntelligence.focusSummary`: `needs`, `plans`, `promotions`
- `panels.dataIntelligence.lastDiscoverSummary`: `docs`, `candidates`
- `panels.dataIntelligence.resolvedSummary`: `plans`, `candidates`
- `phase32.choreography.artifacts`: `value`
- `phase32.choreography.laneMeta`: `events`
- `phase32.connectors.datasets`: `value`
- `phase32.connectors.facts`: `value`
- `phase32.connectors.profiles`: `value`
- `phase32.freshness.derivedFacts`: `value`
- `phase33.identifiability.impactMeta`: `quantities`, `policies`
- `phase33.stress.summary`: `blocked`, `warned`
- `phase34.approval.blocked`: `value`
- `phase34.auditTrail`: `value`
- `phase34.blockers.slowReview`: `target`
- `shared.charts.quantileDotplot.tailSummary`: `bins`

Those 23 identities are the complete positive classification; the other 221
of the 244 traversed identities are the complete negative classification. The
following exact read-only command, run from `policy-engine/`, reconstructs the
244-identity universe from both catalogs, verifies that all 36 declared
positive pairs exist in that universe, and freezes both sets. The semantic
classification is intentionally visible as data in the command rather than
hidden behind a lexical heuristic:

```bash
node <<'NODE'
const crypto = require('node:crypto');
const fs = require('node:fs');
const root = 'apps/runtime-dashboard/src/shared/i18n/locales';
const locales = Object.fromEntries(['en', 'uk'].map((locale) =>
  [locale, JSON.parse(fs.readFileSync(`${root}/${locale}.json`, 'utf8'))]));
const flatten = (value, prefix = '', out = new Map()) => {
  for (const [key, child] of Object.entries(value)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof child === 'string') out.set(path, child);
    else flatten(child, path, out);
  }
  return out;
};
const catalogs = Object.fromEntries(Object.entries(locales).map(
  ([locale, catalog]) => [locale, flatten(catalog)]));
const pattern = /\{([A-Za-z_][A-Za-z0-9_]*)\s*(?=[,}])/g;
const variables = (message) => [...message.matchAll(pattern)]
  .map((match) => match[1]).filter((name) => name !== 'count');
const rows = [...new Set([...catalogs.en.keys(), ...catalogs.uk.keys()])]
  .sort().flatMap((path) => {
    const names = [...new Set(['en', 'uk'].flatMap((locale) =>
      variables(catalogs[locale].get(path) ?? '')))].sort();
    return names.length ? [{path, variables: names}] : [];
  });
const agreement = {
  'causal.pipeline.stageProgress': ['total'],
  'common.lineageGraph.threshold': ['nodes'],
  'pages.artifacts.trinity.bindingSummary': ['bindings', 'parameters'],
  'pages.dashboard.narrativeAttentionBody': ['blocked'],
  'pages.dashboard.narrativeEvidenceBody': ['docs', 'promotions'],
  'pages.dashboard.narrativeThroughputBody': ['success', 'total'],
  'pages.evidence.runContextSummary': ['needs', 'plans', 'promotions', 'artifacts'],
  'pages.runs.evidenceSummary': ['plans', 'promotions'],
  'panels.dataIntelligence.focusSummary': ['needs', 'plans', 'promotions'],
  'panels.dataIntelligence.lastDiscoverSummary': ['docs', 'candidates'],
  'panels.dataIntelligence.resolvedSummary': ['plans', 'candidates'],
  'phase32.choreography.artifacts': ['value'],
  'phase32.choreography.laneMeta': ['events'],
  'phase32.connectors.datasets': ['value'],
  'phase32.connectors.facts': ['value'],
  'phase32.connectors.profiles': ['value'],
  'phase32.freshness.derivedFacts': ['value'],
  'phase33.identifiability.impactMeta': ['quantities', 'policies'],
  'phase33.stress.summary': ['blocked', 'warned'],
  'phase34.approval.blocked': ['value'],
  'phase34.auditTrail': ['value'],
  'phase34.blockers.slowReview': ['target'],
  'shared.charts.quantileDotplot.tailSummary': ['bins'],
};
const pairs = Object.entries(agreement).sort(([a], [b]) => a.localeCompare(b))
  .flatMap(([path, names]) => names.sort().map((name) => `${path}\t${name}`));
for (const pair of pairs) {
  const [path, name] = pair.split('\t');
  if (!rows.find((row) => row.path === path)?.variables.includes(name))
    throw new Error(`agreement pair absent from census: ${pair}`);
}
const sha = (values) => crypto.createHash('sha256')
  .update(values.join('\n')).digest('hex');
console.log({
  leaves: Object.fromEntries(Object.entries(catalogs)
    .map(([locale, catalog]) => [locale, catalog.size])),
  identities: rows.length,
  locale_strings: rows.length * 2,
  variables: new Set(rows.flatMap((row) => row.variables)).size,
  agreement_identities: Object.keys(agreement).length,
  agreement_pairs: pairs.length,
  agreement_locale_instances: pairs.length * 2,
  all_sha256: sha(rows.map((row) => `${row.path}\t${row.variables.join(',')}`)),
  agreement_sha256: sha(pairs),
});
NODE
```

The read-back output was `en=2449`, `uk=2449`, `identities=244`,
`locale_strings=488`, `variables=149`, `agreement_identities=23`,
`agreement_pairs=36`, and `agreement_locale_instances=72`. The complete
identity-variable universe hash was
`74413518b097e2fda58ed07a02409a41e2395d17d18c3e550115fbc21593a9e0`;
the enumerated positive-pair hash was
`10b722ba7f4776a504eba6b983deface1b607af76fa190f72ff177fe0fabff88`.

`pages.dashboard.narrativeAttentionBody`'s `blocked` axis is one of those 23:
two locale strings and six outer-count branches (two English, four Ukrainian).
The landed formatter witness fixes `blocked` at `7`, so it never exercises the
singular forms `1 blocked packet` / `1 заблокований packet`. The gate admits the
whole message because it sees `{count}` and a valid outer ICU plural even though
the independent numeric axis is not adjudicated. That is the task brief's
unregistered P38 property/marker mismatch.

Measurement corrected one source citation without stopping execution: the
pinned `GY-engine-subordination.md` contains build-discipline sections only
through §3.5.13, not the task brief's named §3.5.14. This journal therefore
records P38's wording as a task-brief input pending its upstream source
artifact; the complete catalog census independently establishes the defect.
DS6-C15 is registered at the next continuous number with an immutable cap of 5.
It does not block C03: the governed `i18n-count-message-parity` debt is exactly
the inherited three `overBudget` failures, while C15 covers a class the old rule
never admitted.

The complete caller search for
`panels.reviewCollaboration.reviewers` found one product caller and one
allowlist reason. The caller currently selects the key only for
`participants.length > 1` and uses `solo` otherwise, but no behavioral witness
binds that guard. The map reason now says `Declared, unenforced`; a brittle
source-string witness was rejected under P29. A scoped diff changes only that
reason string—no catalog, count collector, ICU validator, assertion, or caller
byte—so this is a disclosure-only residual registration and not a third C01
mechanism round.

### C09 owner discovery and exact path declaration

The Atlas surface constitution's component maturity bar is normative and its
definition of done requires manual AT evidence for high-risk stable patterns.
A complete 21/21 path census under `architecture/atlas_surfaces` found exactly
two schemas referencing the shared `componentMaturity` vocabulary and only
`adoption-ledger.schema.json` carrying a structural `stable` conditional. The
actual adoption ledger has 233/233 maturity rows and zero stable; the live
readiness ledger has 261/261 and zero stable; the disposition register has 261
entries and zero maturity fields.

The register is not the maturity owner and explicitly cannot upgrade DS1
readiness. More importantly, it content-binds the adoption ledger SHA-256 and
its contended checker fails on drift. Editing the actual ledger would therefore
induce a forbidden contended re-anchor. C09 proceeds without any ledger,
schema/example, readiness-ledger, or register write.

The exact C09 candidate set is six paths against cap 10: the disclosure-only
parity reason, new `atlasManualAtMaturity.ts` and its focused test, a new manual
AT reference page, this plan, and this journal. The mechanism will import C07's
receipt parser and resolved-payload binder, type only the rule-owned manual-AT
details, separate protocol expiry from storage retention, and evaluate a narrow
manual-AT prerequisite without minting maturity authority. Capability truth
remains `contract_only`; C08 persistence and C10 reconciliation are absent.

### C09 red/green mechanism receipt

Red first, the focused command

```bash
corepack pnpm exec vitest run src/test/evidence/atlasManualAtMaturity.test.ts --maxWorkers=2 --reporter=default
```

failed 1/1 file before collection because the declared
`./atlasManualAtMaturity` owner did not exist; zero tests ran in 1.92 seconds.
The red therefore binds the missing C09 consumer rather than an inherited or
browser failure.

The minimal mechanism reuses C07's strict receipt parser and resolved-payload
semantic binder. It adds only strict rule-owned manual-AT details and the
manual-prerequisite evaluator. Its first focused green passed 1/1 file and 9/9
tests in 1.79 seconds (30 ms test body) with two workers. The behavioral set
proves current reconciled evidence can satisfy only the prerequisite; absent
and expired carry different codes; widened human authority is rejected; a
valid bundle for another subject is rejected; unknown, known zero, and missing
remain distinct; institutionally supplied predicate provenance fails closed;
and marker-preserving payload drift is rejected by the real C07 binder.

The positive fixture still returns `grants_stable: false`. C07's receipt denial
of `component_maturity` and `stable` is retained: the receipt records an
observation, while this independent consumer applies one prerequisite. Because
the fixture is in-memory and no Core CAS integrity call, persistence bridge, or
real reviewer producer exists, the capability remains `contract_only` with the
same missing links declared at entry.

The scoped mechanism diff comprises the new C09 module and its focused test.
The parity path changes only one exemption-reason string and the plan/journal
record orchestration; those three paths do not implement the C09 mechanism.
This is C09 mechanism round 0 (initial implementation), not a review fix round,
and the C01 disclosure remains zero mechanism bytes.

### C09 independent review and mechanism round 1

Independent specification, quality, and owner reviews rejected the first
green. The findings were batched before another expensive wave:

1. The evaluator consumed an invented local maturity claim instead of the
   adoption-ledger component row and its `evidence_refs`. The owner bar is the
   row shape in `architecture/atlas_surfaces/adoption-ledger.schema.json`, the
   shared vocabulary in `surface-readiness-ledger.schema.json`, and the
   constitutional stable requirements in
   `policyos-atlas-surface-constitution-and-frontend-vision.md:418-450`.
2. A shaped in-memory bundle could return `satisfied` even though
   `atlasEvidenceArtifact.ts` explicitly says its C07 binder proves semantic
   equality after resolution, not CAS existence or integrity. That violated
   P32's resolve-bind-verify bar in
   `docs/reference/policy-design-case-failure-patterns.md`.
3. Arbitrary nonempty task/AT strings formed a self-consistent basis. P29 and
   P37 require the complete deciding basis to be independently established and
   falsifiable, not self-declared by the evidence under review.
4. Evaluation could precede `receipt.times.verified_at`, and an expiry could be
   no later than verification. P08 requires those time roles to stay distinct.
5. The residual census recorded only aggregates. P35 requires the complete set
   and reproducible denominator; the exact 23-identity/36-pair enumeration and
   read-only command above close that reviewability gap.
6. The deferred full-Vitest arithmetic omitted C09. The governed transition
   must include every landed focused file/test even though the heavy full run
   remains a non-receipt.

The revised 11-control test was written first against the unchanged round-0
module. The same focused command collected all 11 tests and failed 11/11 in
1.79 seconds: the old API rejected the actual owner-row input before it could
exercise any new result. This is the red for C09 mechanism round 1.

The repair now parses the actual adoption-ledger component-row fields, derives
the expected component/state subject from that owner input, and requires the
row to cite the exact `at_manual` receipt artifact identity. It adds an explicit
versioned task/AT basis seam, compares the complete declared and observed task
and capability sets, keeps receipt-predicate and basis-predicate provenance
separate, rejects evaluation before verification, and requires expiry to
follow verification. Because C08 has not resolved and integrity-verified the
receipt and payload through Core CAS and C10 has not reconciled the basis, a
perfectly shaped bundle now returns
`manual_at_integrity_not_established`/`unverified`; there is no `satisfied`
branch.

The focused command then passed 1/1 file and 11/11 tests in 1.48 seconds (40 ms
test body) with two workers. The new negatives are: actual owner-shaped stable
without evidence; exact owner receipt-ref absence; perfectly shaped but
unverified CAS evidence; unestablished basis; arbitrary `noop` task plus
inadequate `none` AT capability; future verification; and expiry equal to
verification. The original absent/expired distinction, authority bound,
unrelated subject, unknown/zero/missing distinction, institutionally supplied
predicate, and marker-preserving C07 payload drift remain covered. The earlier
9/9 result is historical red/green evidence only and is superseded as a source
receipt by this reviewed 11-test denominator.

The scoped diff still has exactly two C09 mechanism paths:
`atlasManualAtMaturity.ts` and its focused test. The reference page explains
the contract; the plan/journal declare and record it; the parity line remains
disclosure-only. Mechanism round 1 therefore changes the enforcement mechanism
and its tests together. One review repair round remains under the declared
breaker; it is not assumed free.

At C09's landing, the provisional resolved-Vitest arithmetic became 265 files /
800 tests: baseline 263/766, plus C01-R1's 11 additional parity cases, C07's +1
file/+12 tests, and C09's +1 file/+11 tests. This corrected the reviewers'
265/798 draft arithmetic, which used the superseded 9-test C09 draft. The full
suite did not run, so this was never a receipt; C15's later two-gate correction
retires the estimate and leaves the governed fields as named holes.

### C09 mechanism round 2 — canonical P37 vocabulary

The quality delta review found one Important duplication after round 1: C09
copied the five P37 predicate-provenance labels already owned inside C07's
`atlasEvidenceArtifact.ts`. That violates this plan's define-once/reference
law and P27 even though both copies initially had the same values; no exact
comparator could prevent their meanings from drifting later.

Red first, `atlasEvidenceArtifact.test.ts` imported the proposed C07 owner
constant, asserted the exact ordered five-value set, and iterated that owner in
the existing admission witness. Before the owner existed, focused Vitest
collected 12 tests and failed exactly that one witness (`undefined` versus the
five expected values), with 11 passing, in 1.93 seconds (56 ms test body).

The repair exports `ATLAS_PREDICATE_PROVENANCE_VALUES` and
`atlasPredicateProvenanceSchema` from C07, makes the C07 receipt parser consume
that schema, removes C09's local enum, and makes the C09 basis import the same
owner. Focused C07+C09 Vitest then passed 2/2 files and 23/23 tests in 2.55
seconds (91 ms test body) with two workers.

This review fix changes both mechanism sources and the canonical-owner test, so
it is C09 mechanism round 2 and consumes the second/final review-fix allowance.
The source-aware measurement expands the C09 set from six to eight paths—the
C07 owner source and its existing test are the two additions—still below the
immutable cap of 10. No cap changed. This round did not alter its then-current
test arithmetic: the C07 file remained one existing 12-test file while C09
remained one new 11-test file. C15 later retired that arithmetic as a governed
source.

Duplication result: one semantic duplicate was found and consolidated into its
C07 owner. The owner-discovery scans found no second receipt/payload/CAS,
maturity-vocabulary, or manual-AT protocol owner in the C09 blast radius.

### C09 source freeze, independent reviews, and final receipts

After round 2, the exact measured set is eight paths against cap 10: the parity
disclosure; C07 evidence source and existing test; C09 source and new test; the
new reference page; this plan; and this journal. `git diff --check` is clean.
The forbidden/contended set, all three locale catalogs, the adoption ledger and
schema, and the readiness schema have empty scoped diffs. Russian value/key
continuity is exercised again by the green parity test without touching its
bytes.

Three independent frozen-source delta reviews returned no Blocking or
Important findings:

- specification review: focused C07+C09 Vitest 2/2 files, 23/23 tests, 2.35
  seconds total (53 ms + 44 ms test bodies); exact eight-path and boundary
  audits clean
- quality review: focused C07+C09 Vitest 2/2 files, 23/23 tests, 4.52 seconds
  total (112 ms combined test body); canonical vocabulary and all prior
  integrity/basis/time findings closed
- owner/boundary review: focused C07+C09 Vitest 2/2 files, 23/23 tests, 2.58
  seconds total (95 ms combined test body); exact eight-path, owner, and
  forbidden-diff audits clean

The final local blast-radius command ran parity+C07+C09 together with
`--maxWorkers=2` and passed 3/3 files, 38/38 tests in 4.72 seconds (347 ms test
body). The three allowed single-process design checks also exited zero with
their named receipts: `Contrast checks passed.`, `Reduced-motion checks
passed.`, and `Color-blind checks passed.` No browser, Storybook, full Vitest,
full lint, full typecheck, full build, journey, visual, or dev-server lane ran;
each remains a non-receipt under the unchanged heavy-lane boundary.

## DS6-C12 — seed honesty-comprehension protocol — 2026-08-11

### Clean entry, owner discovery, and measured set

C12 entered only after C09 landed and was read back clean at
`122208801d644d6347ff34cb59f74fc2cca2c7c2`, six commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. `git status -sb` showed the
attached branch with no changes. The exact declared/measured C12 set remains
five paths against cap 8: new protocol source, focused test, and reference page,
plus this plan and journal.

The owner-first read established four separate roles:

- the Atlas master DS6 deliverable and Rev-3.4 rider at
  `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1023-1043` make
  DS6/`team-frontend` the instrument owner but reserve behavioral content and
  thresholds to INT-R3
- the exact INT-R3 research row at
  `policy-operations-and-real-world-runtime-backlog.md:453-457` names behavior,
  six metric identities, and operating conditions, while lines 251-255 say
  execution still needs live operators and is only designed now
- C07's `atlasEvidenceArtifact.ts` owns the storage convention and denied-use
  boundary; its three closed evidence kinds do not include generic human
  comprehension, so C12 must not mislabel it as assistive-technology
  `manual_at`
- ADR-0171 and `src/polisyos/runtime/quality/human_review.py` already own review
  time, override, dissent, no-delta, and separation-of-duty effectiveness
  telemetry; C12 must not build a second review-effectiveness family

A complete tracked-file census walked 949 frontend TS/TSX files, 4,951 backend
Python files, and 882 Markdown files. It found zero frontend and zero backend
honesty-comprehension/`AuthorityUIComprehensionBenchmark` owners; the only
three documentation hits were the master, this DS6 plan, and the research
backlog. The exact seed wording had zero frontend/backend hits and only the
master plus this plan in docs. A separate complete 136/136 tracked-file census
under `docs/research/policy-operations` found three INT-R3 prose mentions and
zero `docs/research/policy-operations/int-r3/**` artifact paths; no completion
ledger row exists. INT-R3 content is therefore `not_established`, not merely
unwired.

The same census found one semantic collision rather than a duplicate owner:
`false_pass` already names Policy Design Case adjudication outcomes in the
backend. That token does not define the future operator-comprehension metric or
its threshold. The existing backend review-effectiveness and C07 storage
owners are reused/kept separate; no second C12 protocol, sampler, runner,
receipt, CAS, or threshold owner exists.

### C12 red/green mechanism receipt

Red first, the focused command

```bash
corepack pnpm exec vitest run src/test/evidence/atlasHonestyComprehensionProtocol.test.ts --maxWorkers=2 --reporter=default
```

failed 1/1 file during import because the declared protocol owner did not
exist. Zero tests collected; duration was 790 ms. The red binds the missing C12
contract and not a browser, product, or inherited baseline failure.

The implementation is strict rule-owned verification-payload `details`, not a
new receipt envelope. It aliases C07's exact storage object and denial prefix,
defines no evidence kind or writer, and reports `contract_only`. Its owners are
DS6/`team-frontend` for the instrument, INT-R3 for research content and
thresholds, DS6-C11 for future measurement, and Core `ArtifactStore` for
storage mechanics.

The cadence is quarterly plus two event triggers: before the first stable claim
for an interactive authority surface and after an authority-surface semantic
or profile change. It is explicitly collection scheduling, never validity,
freshness, retention, or a threshold. The exact two tasks point to existing
answer owners (`runtime_projection.weakest_links` and
`closeout_truth.blockers`) and preserve external execution, evidence status,
and PolicyOS reaction as separate planes.

Sampling is preregistered and risk-stratified with frame freeze before
observation. No sample size or completeness claim exists; completeness and its
predicate provenance are `not_established`. A shaped frame/preregistration ref
does not elevate the classifier, and a marker-preserving
`declared_complete=true` field is strictly rejected.

The versioned profile uses generic unique task/metric/condition arrays. The
seed freezes the six INT-R3 metric IDs and four named operating conditions, but
all six thresholds recursively require exact `not_established` status and null
comparator, value, unit, and source. There is no current established branch. A
version-bumped alternate task profile parses through the same schema while
retaining all-null thresholds; that proves envelope replaceability only, not
behavioral adequacy or research admission.

The final focused green passed 1/1 file and 8/8 tests in 755 ms (13 ms test
body) with two workers. The test loops over every metric and rejects each
status/comparator/value/unit/source mutation; rejects missing, duplicate, and
populated invented threshold rows; rejects duplicated task/metric identities;
rejects authority widening and denial removal/reordering; proves shaped sample
refs and asserted/supplied completeness remain non-stable; and keeps missing,
unknown, known zero, incomparable, and recorded observations distinct. Even a
populated observation returns `descriptive_only`, `benchmark_status` and
`stable_bar_effect` `not_established`, `blocking_permitted=false`, and
`grants_stable=false`.

The scoped mechanism diff is exactly the new C12 module plus its test. The
reference and slice records do not implement the mechanism. This is mechanism
round 0 (initial implementation), leaving both review-fix rounds available if
an independent review finds an Important/Critical defect.

At C12's landing, the journal advanced the post-C09 265/800 arithmetic to an
estimated 266 files / 808 tests because C12 added one file and eight tests. No
full suite ran, so this was never a receipt. C15's later two-gate correction
retires that estimate as a future governed value; the C03 fields are named
holes until measurement. C12 adds no governed-row transition, no receipt kind,
and no threshold/stable delta to the deferred package.

### C12 review batch and mechanism round 1

Three independent read-only reviews of the five-path entry delta found four
Important gaps against the artifacts that set the bar:

1. `atlasHonestyComprehensionProtocol.ts` accepted any nonempty sampling ref,
   while C07's `atlasEvidenceArtifact.ts` already owns the exact
   `sha256:<64-lowercase-hex>` identity. A malformed marker could therefore
   pass as a shaped reference, contrary to P32 in
   `policy-design-case-failure-patterns.md` and C07's resolve-bind-verify
   boundary.
2. `atlasHonestyInstrumentProfileSchema` checked uniqueness and internal
   threshold equality but not the complete six-metric/four-condition set from
   the master Rev-3.4 rider and INT-R3 row
   (`policy-operations-and-real-world-runtime-backlog.md:453-457`). Removing a
   metric with its threshold or removing a condition remained green, a
   P29/P33 property gap.
3. The parser allowed changed tasks under the unchanged seed ID/version,
   violating the replay/version bar in P07 and the exact two-task C12 contract.
4. The seed's answer-owner aliases did not bind the repository owners found by
   census. The authoritative source paths are
   `src/polisyos/runtime/http/services/governed_projections.py::_project_depth_n`
   with `terminal.blocking_obligations->domain_runs.<domain>.weakest_links`,
   and
   `src/polisyos/runtime/quality/projection_semantics.py::_s9_closeout_truth`
   with `PolicyDesignCaseProjection.closeout_truth.blockers`. Because C12 does
   not behaviorally verify either producer, each binding must remain
   `predicate_provenance=not_established` under P30/P36/P37.

The four findings were batched into mechanism review-fix round 1. Red first,
the same focused C12 command collected eight tests and failed four while four
passed in 815 ms (18 ms test body): canonical answer bindings mismatched the
alias-only implementation; a required metric plus matching threshold could be
deleted; the generic replacement binding was rejected by the old alias shape;
and malformed sampling refs were accepted. This was a scoped test change over
the C12 mechanism, so it consumed one breaker round rather than claiming a
test-only exemption.

The repair exports `atlasArtifactIdSchema` from C07 and consumes it in C09 and
C12; binds the exact seed identity/version to all seed content; requires every
profile to retain all six metrics and four conditions while permitting
all-null, `not_established` research extensions; and replaces owner aliases
with exact producer/field declarations whose predicate provenance is frozen as
`not_established`. The measured set therefore expands from five to seven paths
against the unchanged cap of 8: C07's artifact source and C09's manual-maturity
source are canonical-owner consolidation edits, not new mechanisms.

After the repair, focused C12 passed 1/1 file and 8/8 tests in 799 ms (15 ms
test body). The importer blast radius then passed C07+C09+C12, 3/3 files and
31/31 tests, in 1.36 s (46 ms aggregate test body), with
`--maxWorkers=2`. The generic deletion witness now loops over every one of the
six required metrics and four required conditions; malformed, uppercase,
short, and wrong-algorithm ArtifactIDs fail; a valid-looking pair remains
descriptive and non-stable. This is mechanism round 1; one review-fix round
remains.

### C12 owner correction and mechanism round 2

The research delta review found one further Important owner-binding error in
round 1: `_s9_closeout_truth` is the S9 consumer adapter that normalizes an
already-existing `projection.closeout_truth` at
`projection_semantics.py:2418-2425,2526-2561`; it does not produce the general
`PolicyDesignCaseProjection.closeout_truth.blockers` field. The complete call
chain shows `build_policy_design_case_projection` calling `_closeout_truth` at
lines 356-367, emitting its result at line 434, and `_closeout_truth` deriving
the blocker rows at lines 2843-2889. The binding therefore belongs to
`src/polisyos/runtime/quality/projection_semantics.py::_closeout_truth`.

This finding entered the second and final mechanism review-fix round. Red first,
changing only the expected producer in the focused witness produced 1/1 failed
file, 1 failed and 7 passed tests, in 646 ms (20 ms test body); the diff showed
the received stale `_s9_closeout_truth` against expected `_closeout_truth`.
The source constant and reference were then corrected across the complete
`_s9_closeout_truth` binding search. The answer remains a low-authority
declaration with `predicate_provenance=not_established`; correcting the owner
does not claim behavioral verification. Both mechanism review-fix rounds are
now consumed.

### C12 final reviews, duplication duty, and orchestration

Two independent round-2 read-only reviews returned no Blocking or Important
finding after the owner correction:

- the specification reviewer traced
  `build_policy_design_case_projection -> _closeout_truth -> closeout_truth`
  at `projection_semantics.py:361-365,434,2843-2889`, confirmed the live
  protocol/test/reference binding and `not_established` provenance, and passed
  C07+C09+C12 3/3 files / 31/31 tests in 3.06 s with two workers
- the research/owner reviewer repeated the call-chain and live-binding search,
  confirmed no receipt kind, CAS/writer, or `manual_at` laundering, and passed
  the same 31/31 denominator in 3.48 s; the seven reviewed file hashes were
  unchanged across its review

A requested third duplication delta re-review produced no receipt because its
review workspace exhausted its execution credit. That non-receipt is not
reported green. Its original Important finding is nevertheless closed by the
generic test that deletes each of all six required metrics and each of all four
required conditions under a non-seed profile, plus the two clean final reviews
above.

The standing duplication pass found one load-bearing duplicate in C12's entry
draft: the `ArtifactID` regex was repeated instead of referenced. It is now
defined once as C07's exported `atlasArtifactIdSchema` and consumed by C07,
C09, and C12. The backend `false_pass` adjudication token is a documented
semantic collision, not an INT-R3 metric owner. No second honesty protocol,
sampler, threshold owner, evidence envelope, receipt kind, CAS, or writer was
found or created.

The final local allowed blast radius passed parity+C07+C09+C12, 4/4 files and
46/46 tests, in 3.65 s (232 ms aggregate test body) with
`--maxWorkers=2`. All three permitted single-process token checks exited zero
with `Contrast checks passed.`, `Reduced-motion checks passed.`, and
`Color-blind checks passed.` `git diff --check`, tracked/untracked whitespace,
the seven-path measurement, and the forbidden/contended/`ru.json` scoped diff
were clean; the Russian byte SHA-256 remained
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`.

No browser, Storybook, `test:a11y:pages`, journey, visual, dev-server, full
Vitest, full lint, full typecheck, or full build command ran. They remain
non-receipts, not green: the browser/full wave remains serialized behind the GY
contention budget, and the deferred package contains the exact commands for a
later authorized run. The former 266-file/808-test estimate is retired; C03's
governed numeric fields remain named holes until that measurement runs.

No later cluster was entered. C03 and C04 still require the contended register
and baseline artifacts and wait for DS5-C21b/C21c plus explicit continuation.
C05, C06, and C13 require the prohibited browser/heavy wave. C08 was not in the
authorized C09-then-C12 sequence and still owns real persistence/integrity;
C10 consequently lacks its required C08 receipt and was not entered. C11 owns
future measurement and still lacks INT-R3 content, a generic reviewer producer,
and actual observations; it was not entered. C15 remains a declared adjacent
P38 debt at cap 5, not part of the repaired three-signature C03 transition.
No contended artifact, product surface, DS5/GY path, or Russian catalog byte
was written.

## DS6-C15 stop record — 2026-08-12

### Entry, measured correction, and attempt

`git status -sb` at entry reported a clean attached
`codex/atlas-ds6-evidence-workflow` at
`b15747da633fc52748460de0dea9cbb755140302`, eight commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. The continuation directly
authorized already-declared C15 out of sequence; C14 remains unentered behind
the heavy/contended workflow. The attempt measured exactly the five capped
paths: parity owner, `en.json`, `uk.json`, plan, and journal. No sixth path was
needed.

The complete catalog census reproduced the landed denominator: 2,449 leaves in
each active catalog, 244 non-`count` interpolation identities / 488 locale
strings, 149 variables, and the original-risk 23 identities / 36 path-variable
pairs / 72 locale instances. Caller/type review of all 82 initially excluded
names corrected the task input's proposed numeric set from 67 to 71: it added
`completeness` (numeric API field formatted as percent), `fallbacks` (caller
array length), `interval` (preformatted numeric CI endpoints), and `priority`
(typed number-or-null). The measured 71 names occupy 183 exact active
path-variable uses: 36 original-risk pairs plus 147 current non-agreement uses.

Red first preserved the intended semantic receipts. Before mechanism code or
catalog edits, seven new witnesses failed while all 15 inherited parity tests
passed. With the generic AST mechanism present and catalogs untouched, active
checks named exactly 36 unsafe pairs in each locale. The attempted repair
adjudicated all 23 identities one by one as 20 label-form messages (33 pairs)
and three ICU-plural messages (three pairs), with no split, exemption, or
nested sixteen-branch message. It kept Russian out of active enforcement; the
frozen key/value assertions stayed green and raw `ru.json` SHA-256 remained
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`.

### Mechanism breaker

Review-fix round 1 closed three independently reproduced findings: ICU-valid
whitespace after `{` escaped discovery; punctuation could masquerade as label
form; and a new use of an already-declared numeric name escaped because only
the fixed treatment map was visited. The round made point-use admission exact
set subtraction over 183 uses, added non-empty reasons for all 147
non-agreement uses, and required same-variable plural ownership or a bounded
label form. Focused parity reached 30/30.

Review-fix round 2 removed parentheses from the post-value label boundary after
`Events: {events} (events)` remained admissible, and added that exact witness.
Focused parity again reached 30/30. The journal then declared both allowed
mechanism review-fix rounds consumed.

Final specification delta review proved the same-class property still false:
the boundary predicate checked only a separator prefix, so every admitted
separator could hide an agreeing noun. Read-only `IntlMessageFormat` AST
reproduction returned `admitted=true` for all four marker-preserving variants:

- `Events: {events}; events`
- `Events: {events}. events`
- `Events: {events} · events`
- `Events: {events} / events`

This is a third mechanism-changing finding against the slice plan's P29/P33
bounded-label bar. Per the standing law, C15 stopped rather than taking a third
fix round. The 30/30 focused run is a receipt for the reverted draft's covered
cases, not evidence that the wider property is repaired.

### Preservation, forward revert, and resulting state

Ordinary append-only history preserves the stopped five-path attempt in
checkpoint `8fd8f9e5d` (`DS6-C15 checkpoint stopped numeric plural attempt`).
Forward-revert `4d7743f07` removes every attempted parity/catalog/plan/journal
byte rather than rewriting the checkpoint. The plan and this stop record are a
new documentation-only cluster after that clean forward revert; they do not
reintroduce the mechanism or active-locale copy. Consequently C15 is **not
landed**, the numeric-variable class remains open, and a future implementation
requires an explicitly authorized re-cut under the next continuous cluster
number. It must not be described as a third C15 fix round.

### C03 second gate and estimate retirement

C03 has two independent gates. First, DS5 must release all eight contended
manifest/schema/checker/test/register/report/status artifacts and C03 must
re-read their then-current content-hash ownership. Second, explicit heavy-lane
authorization must permit this receipt package from
`apps/runtime-dashboard`:

```bash
mkdir -p ../../_build/apps/runtime-dashboard
git rev-parse HEAD
/usr/bin/time -p corepack pnpm exec vitest run --reporter=json --outputFile=../../_build/apps/runtime-dashboard/ds6-c03-vitest.json
```

The first command creates the repository-ignored output directory and supplies
no governed field. Field provenance is separate: the literal timed Vitest
command supplies `command`; Git supplies `revision`; `/usr/bin/time real`
supplies wall duration; JSON supplies Vitest duration, counts, and failure
identities; process status supplies exit code; and the then-current
producer/checker derives the failure hash and resolved failure/debt-class
state. The historical 263/766 -> 264/789 ->
265/800 -> 266/808 arithmetic is superseded as a future governed value. C03's
`command`, `revision`, durations, exit code, file/test totals, failure-set hash,
and empty resolved state remain named holes until the authorized receipt.

### Duplication duty, reviews, and nonreceipts

A complete scan of 951 TS/TSX/JS/MJS/CJS files under
`apps/runtime-dashboard/src` found the exemption/numeric gate only in
`shared/i18n/parity.test.ts`; the sole runtime ICU formatter owner is
`shared/i18n/messages/icu-messages.ts`. No sibling scanner, registry, or
numeric-variable authority exists. The attempt extended those owners and
introduced no duplicate, but the forward revert leaves the repository in its
pre-C15 state. The concrete divergence found was the attempted checker versus
its own separator semantics; final comparator status is failing, not green.

Two delta reviewers found no other Blocking/Important boundary, copy, Russian
freeze, or exact-set issue after round 2, but the final independent
specification finding above controls and stops the cluster. No full/whole-suite
Vitest, browser, Storybook, `test:a11y:pages`, journey, visual, dev server, full
lint, full typecheck, full build, or build-Storybook command ran. Those remain
nonreceipts: the heavy wave is still serialized behind the GY/host release and
C03 additionally lacks the contended-owner release. No contended artifact,
product surface, DS5/GY path, Russian catalog, or denominator was written.

### Restored-state verification and stop-record review

After the forward revert and the documentation-only C03 correction, the final
permitted verification wave ran against the restored implementation state:

- `corepack pnpm exec vitest run src/shared/i18n/parity.test.ts --maxWorkers=2
  --reporter=default` passed 1/1 file and 15/15 tests in 928 ms (55 ms test
  body). This is the pre-C15 parity denominator, not a C15 repair receipt.
- `corepack pnpm run a11y:contrast` exited zero with `Contrast checks passed.`
- `corepack pnpm run a11y:motion` exited zero with `Reduced-motion checks
  passed.`
- `corepack pnpm run a11y:color-blind` exited zero with `Color-blind checks
  passed.`

The focused parity receipt kept the Russian cardinality, key-set fingerprint,
and leaf-value fingerprint green at 2,449,
`67b7a921f503f108a9b47e034c31be130911c1fe8b7b9321fa8a163ef8d271a8`,
and `0426d4ce0397027d25f5a2053bce794b12e31fbe3757d3afefb24de6ba3f45eb`.
The raw `ru.json` SHA-256 read back as
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`.
The complete i18n subtree and every contended path were byte-identical to
entry head `b15747da6` after the forward revert.

The independent documentation review first found that the deferred Vitest
command targeted an ignored but absent output directory. The executable
package now begins with
`mkdir -p ../../_build/apps/runtime-dashboard`; `policy-engine/.gitignore`
owns `_build/`, and the directory-creation command supplies no governed field.
Delta re-review returned no Blocking or Important finding: the two-path diff,
append-only checkpoint/revert history, field-specific C03 provenance, stopped
breaker status, census, duplication result, nonreceipts, and restored
i18n/contended bytes all matched their owners.

Two requested post-revert re-reviews from the earlier mechanism-review agents
were orchestration nonreceipts because their review workspaces exhausted
execution credit. They are not counted as green reviews; the separate
stop-record reviewer supplied the completed independent receipt above. The
final documentation-only file set is exactly this journal and
`DS6-evidence-workflow.md`. No heavy command listed in the deferred package
ran, and C15 remains stopped and open.

## DS6-C15-R1 — declaration-completeness mechanism — 2026-08-12

### Entry, cut, and carried adjudication

`git status -sb` at entry reported a clean attached
`codex/atlas-ds6-evidence-workflow` at
`769c08b35f1e386bd05a873ff0ce61ce9285230f`, 11 commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. The exact declared set is five
paths: `parity.test.ts`, active `en.json`, active `uk.json`, the DS6 plan, and
this journal. That equals cap 5; no helper path was created.

Read-only extraction from checkpoint `8fd8f9e5d` independently reproduced the
mechanism-independent population before any carry-forward edit: 2,449 leaves
per active catalog; 244 non-`count` interpolation identities and 149 variable
names; 71 reasoned quantitative names; and 183 exact quantitative point uses.
The declarations partition without overlap into the 23-path/36-pair review
cohort plus 147 other invariant uses. The cohort remains 33 invariant pairs
over 20 label-form copy paths plus three pluralized pairs/paths; the complete
declaration set is therefore 180 invariant plus three pluralized. Recomputed
key hashes matched the checkpoint: quantitative names
`c60120b6795593d5f5b84b83353e2c1d02c7ea568e8e48e146942aadbfdf3517`,
review cohort
`10b722ba7f4776a504eba6b983deface1b607af76fa190f72ff177fe0fabff88`,
other invariant uses
`2e3c9c18f5980770733df476a5d1427c42208c67f745cd50a408bfa43a6d9cae`,
and their 183-key union
`4bc1fc6d6b2600cfbebd509630f3f5ad82276c47e88b38834ce6fa3d526ee858`.

The 23 repaired English and Ukrainian catalog paths were carried verbatim from
the checkpoint. No leaf was added or removed; 20 messages retain label-form
copy and three retain genuine ICU cardinal plurals. There is no nested 4x4
plural. Label form remains adjudication/copy guidance only and is not read by
the gate.

### Red first and mechanism replacement

The restored entry baseline passed 1/1 parity file and 15/15 tests in 1.25 s
(54 ms test body) with `--maxWorkers=2`. Replaying the preserved checkpoint
implementation/copy first reproduced its covered 30/30 denominator; that was
not treated as a C15-R1 receipt because the stopped text-shape mechanism was
still present.

Before replacing that mechanism, the C15-R1 witnesses ran red with 5 failed and
25 passed tests in 788 ms (78 ms test body). The failures were the intended
contract differences:

- real active English clone plus
  `pages.dashboard.c15R1NewQuantitativeUse = "Events: {events}; events"`
  lacked the named `declaration_missing` result;
- an outer `count` plural and a partially protected sibling branch lacked the
  named `plural_ownership_missing` result;
- blank invariant reasons lacked the named `reason_missing` result; and
- the old text-shape gate rejected legitimate invariant
  `{events} online · {duration}` copy.

The replacement uses one exact 183-key declaration owner. Each value is only
`{classification: "pluralized" | "invariant", reason}`. Per active locale, the
gate recomputes the 71-name point-use set and subtracts declarations in both
directions. Invariant admission reads exact identity and non-empty reason only.
Pluralized admission parses the real ICU AST and requires at least one
same-variable **cardinal** plural selector with every raw occurrence beneath
such a selector through plural/select/tag branches. The numeric-name heuristic
is retained solely as a `numeric-variable-uncovered` worklist; it does not
admit or reject grammatical copy.

After the minimal replacement, focused parity passed 1/1 file and 30/30 tests
in 719 ms (68 ms test body) with two workers. The real-new-string witness also
proves the rejection clears only after the exact point-use declaration with a
non-empty invariant reason is added. This is C15-R1's initial declaration-
mechanism implementation, with zero distinct review finding classes consumed.
A fourth distinct class against this mechanism stops the cluster; punctuation
variants cannot revive the explicitly refused text-shape mechanism.

### Authority boundary, refused mechanism, and current nonreceipts

The positive claim is bounded. Active point-use membership, exact-set
subtraction, and pluralized structural ownership are `recomputed`. The
rule-owned 71-name quantitative census and invariant judgments are
`consumer_asserted` and fingerprinted at admission; their independent semantic
adequacy is `not_established`. Those supplied predicates do not carry the
bounded positive gate. Thus the receipt proves declaration completeness and
the structure of entries marked pluralized; it does not claim automated
grammatical or morphological truth.

Text shape is a refused admission mechanism. The evidence is the stopped C15
sequence: punctuation admitted `Processed ({events}) events`; a narrowed
boundary admitted `Events: {events} (events)`; and each retained separator
(`;`, `.`, `·`, `/`) admitted a following agreeing noun. The inverse rule also
rejects legitimate invariant words after a variable. No punctuation, colon,
separator, adjacency, label, or surrounding-word predicate remains in the
gate.

No full/whole-suite Vitest, browser, Storybook, Playwright, dev server,
journey, visual, full lint, full typecheck, full build, or build-Storybook lane
has run. Each remains a nonreceipt under the unchanged heavy boundary. No
contended artifact, readiness ledger, checker-family file, generated report,
DS5/GY path, product surface, Russian catalog, or denominator was written.
Independent reviews and the final allowed verification wave remain pending at
this point in the journal.

### Initial review batch and three-class repair

Three independent frozen-source reviews reproduced the five-path cap, all
71/183/36/147/23 measurements and four hashes, the 20+3 copy partition, Russian
freeze, exact per-locale subtraction, and absence of a text-shape admission
predicate. Focused review receipts passed 32/32. They found three distinct
declaration-mechanism classes plus one documentation-label correction:

1. a truly omitted `reason` reached `.trim()` and threw rather than returning
   `reason_missing`; the prior witness covered only empty and whitespace text;
2. a same-variable type-5 `select` or non-cardinal type-6 `selectordinal` was
   not counted as an occurrence, so a cardinal plural nested in one sibling
   branch could launder the outer selector; and
3. point-use membership came from a brace regex, so ICU-quoted
   `Events: '{events}'` kept a marker while the runtime AST contained no
   `events` use and the declaration failed to become stale.

The documentation correction assigns canonical P37 labels above. Red first
for the batched mechanism repair ran 34 tests with four expected failures and
30 passes in 827 ms (81 ms test body): the quoted-marker deletion stayed green,
both same-variable selector variants stayed green, an omitted reason threw,
and malformed ICU returned the structural code instead of the new explicit
parse-failure code.

The repair makes the ICU AST the point-use authority. It skips strings with no
opening brace, parses every candidate with `IntlMessageFormat`, recursively
collects argument/select/plural variables, and returns
`message_parse_failed` when a candidate cannot be parsed. This avoids the
pre-existing non-ICU `<runId>` literal while failing closed on malformed
templates that could contain a use. Same-variable select and ordinal selectors
are now recorded as occurrences outside cardinal ownership; a nested cardinal
plural cannot erase them. Missing or non-string reasons now return
`reason_missing`.

After the batched repair, focused parity passed 1/1 file and 34/34 tests in
947 ms (114 ms test body) with two workers. These three distinct classes are
now consumed. Under the user-set breaker, any new distinct declaration-
mechanism class in delta review is the fourth and stops C15-R1; a recurrence of
one of these classes is adjudicated against the existing repair rather than
miscounted as a new class.

The complete 951-file duplication census (360 tracked `.ts`, 591 tracked
`.tsx` under `apps/runtime-dashboard/src`) still finds one declaration/gate
owner in `shared/i18n/parity.test.ts`, one runtime ICU formatter owner in
`shared/i18n/messages/icu-messages.ts`, and no sibling catalog gate/scanner.
It also finds an adjacent English-only `pluralize()` helper in
`features/artifacts/reading-view/MonographLayout.tsx`. That product-surface
manual-morphology residual neither reads the catalogs nor duplicates this gate
and is outside the C15-R1 fence; it is recorded, not edited or called closed.
Final delta re-review and the final allowed wave remain pending here.

### Delta review, final permitted wave, and freeze

All three delta reviewers returned clean. None found a recurrence or a fourth
declaration-mechanism class:

- the specification reviewer independently passed 1/1 focused file and 34/34
  tests in 857 ms (124 ms test body), and confirmed the true omitted-reason,
  AST-membership, and same-variable selector witnesses;
- the quality reviewer independently passed 34/34 and recomputed 71 names and
  183 uses in each active locale, with zero candidate parse failures and the
  same `4bc1fc6d...` declaration-set hash; and
- the boundary reviewer independently passed 1/1 file and 34/34 tests in
  746 ms (113 ms test body), reproduced all four declaration hashes, and
  confirmed exactly five changed paths, 2,449 leaves per active catalog,
  exactly 23 changed catalog leaves, and no fence violation.

After those reviews, the one final allowed wave ran from
`apps/runtime-dashboard`:

- `corepack pnpm exec vitest run src/shared/i18n/parity.test.ts
  --maxWorkers=2 --reporter=default` exited zero: 1/1 file and 34/34 tests,
  903 ms Vitest duration and 109 ms test body;
- `corepack pnpm run a11y:contrast` exited zero with `Contrast checks
  passed.`;
- `corepack pnpm run a11y:motion` exited zero with `Reduced-motion checks
  passed.`; and
- `corepack pnpm run a11y:color-blind` exited zero with `Color-blind checks
  passed.`

The final Russian readback remains 135,673 bytes with raw SHA-256
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`,
2,449 keys/leaves, key-set SHA-256
`67b7a921f503f108a9b47e034c31be130911c1fe8b7b9321fa8a163ef8d271a8`,
and sorted path/value SHA-256
`0426d4ce0397027d25f5a2053bce794b12e31fbe3757d3afefb24de6ba3f45eb`.
It has no diff. The final source set is exactly the declared five paths:
`parity.test.ts`, `locales/en.json`, `locales/uk.json`, the DS6 plan, and this
journal. The active catalogs are byte-identical to checkpoint `8fd8f9e5d`.

No full or whole-suite Vitest, browser, Storybook, Playwright, dev server,
journey, visual, full lint, full typecheck, full build, or build-Storybook lane
ran. Each remains a nonreceipt under the unchanged heavy boundary. No
contended artifact, readiness ledger, checker-family file, generated report,
DS5/GY path, product surface, Russian catalog, or denominator was written.

## DS6-C05 — serialized heavy evidence wave — 2026-08-12

### Entry, serialization, and declared ceilings

`git status -sb` at entry reported a clean attached
`codex/atlas-ds6-evidence-workflow` at
`4748b921113b884a3fe17593bc50c1af300e97f2`, 12 commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. C05 owns this journal only and
therefore enters at its declared path cap of one. The GY/host serialization
gate is released, but the DS5-governed register family remains contended; lane
execution is authorized and governed receipt consumption is not.

The deferred commands run one heavy parent at a time. The following controller
ceilings are supplied at entry, not measured Atlas budget-owner values; each
actual wall time is recorded below and no ceiling is enlarged mid-run:

| Lane | Declared ceiling (s) | Basis |
| --- | ---: | --- |
| whole-suite Vitest | 1,800 | supplied |
| opaque-background Storybook browser Vitest | 1,800 | supplied |
| component Vitest | 1,800 | supplied |
| component a11y Vitest | 1,800 | supplied |
| Playwright a11y pages | 1,800 | supplied |
| Playwright journeys | 2,400 | supplied |
| Playwright visual | 2,400 | supplied |
| full lint | 1,800 | supplied |
| full typecheck | 600 | supplied |
| production build | 300 | measured ceiling supplied by the wave brief |
| Storybook build | 1,800 | supplied |

A command killed by its controller is recorded as a nonreceipt, never a
sample or RED. A completed nonzero process is RED at the exact assertion or
tool failure it reports. A completed zero process is a receipt only for that
entire command; partial output is never rounded to a pass.

### Terminal receipt matrix

Every heavy parent ran serially and terminated below its declared ceiling:

| Lane | Result | Wall (s) | Exact terminal evidence |
| --- | --- | ---: | --- |
| whole-suite Vitest | RED | 410.97 | 315/316 files and 965/966 tests passed; one `LineageGraph.test.tsx` assertion failed |
| opaque-background Storybook browser Vitest | RED, 0/7 | 20.14 | opaque-ancestor precondition failed before any source classification |
| component Vitest | RED | 351.13 | independently reproduced the same 315/316-file, 965/966-test failure |
| component a11y Vitest | GREEN | 87.66 | 84/84 files and 85/85 tests passed |
| Playwright a11y pages | GREEN | 160.94 | 21/21 tests passed |
| Playwright journeys | RED | 17.02 | collection failed before any test: `en.json` lacked the Node JSON import attribute |
| Playwright visual, admitted rerun | RED | 131.47 | 14/18 tests passed; four baselines failed |
| full lint | RED | 1,182.94 | 11 errors, zero warnings |
| full typecheck | RED | 17.41 | four TypeScript errors |
| production build | RED | 16.11 | stopped at the same typecheck errors; Vite/post-build did not run |
| Storybook build | GREEN | 19.25 | 3,809 modules transformed and static Storybook emitted |

The first whole-suite execution lost its terminal after writing a complete
JSON report. It is a nonreceipt, never a timing sample or RED; the admitted
rerun above persisted stdout, stderr, and process status in ignored scratch.
The first visual execution is a separate setup RED: it completed nonzero in
122.05 s, before any test, with `Timed out waiting 120000ms from
config.webServer` because the inherited runtime web server spent its startup
window creating a worktree `.venv`. That command-created directory was moved
immediately and intact to the authorized ignored
`_build/apps/runtime-dashboard/.venv-online`; no `.venv` remains at worktree
root and no tracked path changed. The admitted visual rerun bound that
environment with `UV_NO_SYNC=1` and the worktree `src` on `PYTHONPATH`.

The attempted offline scratch bootstrap is a setup nonreceipt: it terminated
in 0.16 s because `jaxlib==0.8.2` was absent from the local cache. Page a11y
and journeys therefore used the existing main-checkout environment read-only
with `UV_NO_SYNC=1` while importing all PolicyOS code from this worktree via
`PYTHONPATH`. No dependency sync or source write occurred there.

### Whole-suite authority and C03 consequence

The admitted whole-suite JSON receipt is the authority; none of the retired
263/766, 264/789, 265/800, or 266/808 projections is a comparator. Its exact
fields are:

```json
{
  "revision": "4748b921113b884a3fe17593bc50c1af300e97f2",
  "command": "/usr/bin/time -p corepack pnpm exec vitest run --reporter=json --outputFile=../../_build/apps/runtime-dashboard/ds6-c03-vitest-run2.json",
  "wall_duration_seconds": 410.97,
  "vitest_duration_seconds": 409.6055888671875,
  "exit_code": 1,
  "test_files": {"total": 316, "passed": 315, "failed": 1},
  "tests": {"total": 966, "passed": 965, "failed": 1},
  "pending_tests": 0,
  "todo_tests": 0,
  "raw_json_sha256": "0988d754c551b92fe2d782da7875d1c594e42028aa853bb7c0324683f3880d64"
}
```

The exact failure identity is
`apps/runtime-dashboard/src/shared/ui/LineageGraph.test.tsx` / `LineageGraph
> renders the threshold fallback when the graph exceeds the configured size`,
at assertion line 28. The assertion expects `Graph has 3 nodes, which is above
render threshold (2).`; the rendered catalog value is `Graph nodes: 3; render
threshold: 2.`. C15-R1 changed that copy while preserving the earlier focused
gate, so this is a measured importer-test RED, not one of the repaired
`i18n-count-message-parity` identities.

Measurement changes the deferred delta: there is **no admissible C03 resolved
transition** from this receipt. Its numeric holes are filled above, but
`exit_code=1`, a nonempty failure set, and the new identity forbid
`disposition: resolved`, empty failures, or removal of the governed count-debt
class. The content-bound `failure_set.sha256` remains for the then-current
contended producer/checker to derive from the exact identity; DS6 does not
invent that governed value in prose. C03 now still has both independent gates:
the DS5 register-family release and a future authorized **green** whole-suite
receipt. This RED discharges measurement uncertainty, not the green gate.

### Browser contrast, other REDs, and visual evidence

The opaque-background story returned 0/7, exactly: its single story failed at
`OpaqueBackgroundContrast.stories.tsx:213` because
`hasOpaqueBackground(element)` was false while checking the controlled
harness, before the source-classification loop could emit any of seven atomic
receipts. It is not 5/7, 6/7, or a partial pass. C06 remains gated on both the
contended C04 row and a future 7/7 browser receipt.

The full visual lane failed four exact identities: `evidence promotion focus`
(2,685 pixels reported before timeout), `dark evidence fabric` (532 pixels),
`mobile command center` (369x3,700 expected versus 369x3,680 actual; 28,414
pixels), and DS8-owned `run detail A4 print` (724x2,113 expected versus
770x13,229 actual; 691,799 pixels). The print artifacts read back as:

- expected SHA-256
  `a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`;
- actual SHA-256
  `fa6a35be9c9893f1ed856f2a320293b4f71440caf497cffefcb3c29b5af7f8c5`;
- diff SHA-256
  `e48184223d3fcd0bd24b7c8fa6b1243b760d5e42966b86b5c4e021ab4851e50a`.

C13 still owns the independent filtered DS8 verdict and runs after C08; this
full-wave result is enabling evidence, not a substitute for that cluster.

Full lint reported nine errors in `shared/i18n/parity.test.ts` (one
`consistent-generic-constructors`, six `no-unsafe-enum-comparison`, and two
`vitest/no-conditional-expect`) plus two deprecated `passthrough()` uses in
`atlasManualAtMaturity.ts`. Full typecheck reported two invalid
`ds6-browser-fixture` author literals in the opaque story and two possibly
undefined `badgeEntry` accesses in `atlasManualAtMaturity.test.ts`. Production
build inherited the same typecheck RED and made no downstream build claim.
Journeys failed at module collection, so no journey test is counted green.

### Blocked list, duplication duty, and nonreceipts

- C03 waits for both a green replacement receipt and the DS5-owned governed
  register/manifest family. No transition text can honestly claim resolved.
- C04 waits for the same DS5 release; its exact row remains declared.
- C06 waits for C04 and a future 7/7 browser receipt; the measured result is
  0/7.
- C10 waits for C08 persistence, integrity verification, and reconciliation.
- C11 waits for INT-R3 content, a producer, real observations, and researched
  thresholds; none is invented.

The complete deferred-command census enumerated all 11 timed lane commands.
Two of 11—whole-suite JSON Vitest and `test:components`—deliberately execute
the same 316-file default `vitest.config.ts` population with different
receipt/reporting settings. `apps/runtime-dashboard/vitest.config.ts` is the
single canonical population owner; both package commands already point there,
so migration state is `shared_owner`, not `duplicate_implementation`.
Concrete divergence is only receipt shape and worker/report options: JSON plus
unbounded workers for C03 versus default reporter plus two workers for the
component receipt. Comparator status is measured equal: both returned the same
315/316-file, 965/966-test `LineageGraph` failure. Component a11y is a distinct
84-file population owned by `vitest.a11y.config.ts`. The execution overlap is
therefore outside the plan's two-implementation/artifact duplication class;
no second gate, scanner, configuration owner, or strangle target was found.

All listed lanes reached a terminal state; there is no killed-ceiling
nonreceipt. The lost first whole-suite terminal and failed offline environment
bootstrap remain explicit nonreceipts. A dev server and interactive Storybook
were not run independently; only command-managed servers ran. No governed
artifact, contended register-family path, readiness ledger, checker, generated
report, `src/polisyos/**`, Russian catalog, product surface, DS5/GY path, or
denominator was edited.

## DS6-C08 — automated evidence capture — 2026-08-12

### Owner discovery, entry cut, and source reports

C08 entered from the clean attached branch at
`8a9e320588ba3378b4596a609bca3762501e577f`, 13 commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. Read-only owner discovery found
that persistence does not require a `src/polisyos/**` edit. The public Core
contract already supplies `ArtifactStore.put_json`, `get_bytes`,
`get_manifest`, and `verify`; the backend-neutral construction path is
`build_artifact_store(ArtifactStoreConfig.from_env())`. The dashboard's
`scripts/serve_fixture_runtime_api.py` is the existing app-local precedent for
importing the public PolicyOS package boundary. The runtime artifact HTTP
surface is inspection-only for this purpose and is not a substitute writer.

The C08 cut measured eight paths against cap ten. It entered with seven; the
installed workspace has Vite but no `vite-node` executable, so the failed
direct invocation demonstrated that a small app-local launcher is structurally
required. The cap is unchanged:

1. `apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts`;
2. `apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.test.ts`;
3. `apps/runtime-dashboard/src/test/evidence/captureAtlasEvidence.ts`;
4. `apps/runtime-dashboard/scripts/capture_atlas_evidence.mjs`;
5. `apps/runtime-dashboard/scripts/persist_atlas_evidence.py`;
6. `docs/reference/frontend/atlas-evidence-artifact.md`;
7. the DS6 plan; and
8. this journal.

No package command or Core implementation path is needed. The MJS launcher
uses the installed Vite module loader and owns no evidence semantics. The TypeScript
producer owns runner normalization and the existing C07 schemas; the
executable TypeScript bridge owns file/process I/O; the Python adapter consumes
the public Core store and owns no CAS layout, hash, manifest, or verifier.

Two serialized real-run machine reports were acquired at revision
`8a9e320588ba3378b4596a609bca3762501e577f` for the capture path:

- `/usr/bin/time -p corepack pnpm exec playwright test
  e2e/a11y/keyboard-journeys.spec.ts --project=chromium --reporter=json`
  completed GREEN in 39.45 s. The report records exactly one expected test,
  zero skipped/unexpected/flaky tests, runner duration 37,944.837 ms, and the
  exact keyboard decision-packet journey passing. Its 3,925 raw bytes have
  SHA-256
  `050bc0ca4d925f78bc66fdc653fd7454f319dce7d92fc1552a8e23094d1ff7bd`.
- `/usr/bin/time -p corepack pnpm exec vitest run --config
  vitest.storybook.config.ts
  src/test/a11y/OpaqueBackgroundContrast.stories.tsx --reporter=json
  --outputFile=../../_build/apps/runtime-dashboard/ds6-c08-opaque-vitest.json`
  completed RED in 39.32 s. The report records 0/1 story tests and preserves
  the opaque-ancestor precondition failure before any of seven source receipts;
  therefore its semantic result is exactly 0/7, never a partial pass. Its
  2,678 raw bytes have SHA-256
  `a03c5da2ebb0f60b1259e6bec3f77c10ce3e60671b07602e948db56d5a6a4572`.

The first keyboard command named the nonexistent
`src/test/a11y/keyboard-journeys.spec.ts` entry path. It completed nonzero in
15.06 s with “No tests found”; it is a setup RED and is not admitted as an
evidence observation. The corrected report above is separate. No ceiling was
exceeded and the runner parents remained serialized.

### Persistence implementation and admitted artifacts

The runner normalizer accepts only the two closed profiles and their complete
test identities. It recomputes every individual outcome and the summary from
the runner JSON, rejects a summary/file-status contradiction or a partial
population, and checks the exact declared runner command. The opaque story is
atomic: its one story admits either all seven source observations or none. The
real failure therefore carries `declared=7`, `admitted=0`, and
`mode=all_or_nothing`; it is not represented as 0/1 at the evidence-class
boundary.

P37 is field-specific. Test population, result, findings, atomic denominator,
and raw-report SHA are `recomputed`; the runner identity is
`independently_reconciled` against the exact profile/test population.
Playwright JSON exposes version 1.59.1 and that version is recomputed. The
Vitest JSON does not encode its version, so `vitest-browser@4.1.5` and the
declared rule identity remain `institutionally_supplied`. Neither the git
revision nor shell argv is encoded in these runner reports, so those two
provenance fields are also `institutionally_supplied` and are not used to turn
the result green. The C07 receipt's decisive runner-result predicate remains
`recomputed`. Observation, collection, and verification are distinct: runner
start, runner finish, and the later capture/verification clock populate the
three roles respectively.

The app-local Python adapter delegates identity, canonicalization, write,
manifest construction, and integrity to Core. Its behavioral focused witness
uses an isolation-local ignored CAS, persists the exact raw report, payload,
and receipt, resolves and verifies all three, checks the raw-to-payload
`runner_report` edge and payload-to-receipt `verification_payload` edge, then
corrupts the raw-report blob while retaining its manifest and proves the real
Core verifier fails. A separately shaped but unresolved result, changed
lineage edge, digest mismatch, and valid unrelated resolved payload all fail
before admission.

Review found four trust-boundary defects before the admitted reissue: caller
selection of a bridge or Python executable was a sibling intake around Core;
the raw report stopped at a digest string rather than a resolvable lineage
edge; a hand-authored verifier version did not content-bind the executing
implementation; and `classification=public` contradicted the non-public
audience and local paths in the diagnostic. The closed mechanism now fixes the
adapter and interpreter, persists the exact raw bytes as the payload's sole
input, binds the ordered five implementation paths by per-file and aggregate
SHA-256, and has Python independently recompute that set before writing. All
three manifests carry Git commit
`8a9e320588ba3378b4596a609bca3762501e577f` and repository-wide `dirty=true`;
the dirty capture is reproducible by exact bytes, not represented as a clean
revision. The manifests classify all three artifacts `internal` and state the
actual encryption posture exactly: mode `none`, not enforced, not verified.
Their 365-day manual-cleanup contract is retained. No public/export claim is
made.

After those review fixes, the two final serialized launcher invocations were
rerun against the already-recorded runner JSON; no runner, browser, server, or
journey lane was rerun. From `apps/runtime-dashboard`, the exact commands were:

```bash
node scripts/capture_atlas_evidence.mjs --profile keyboard_playwright --report ../../_build/apps/runtime-dashboard/ds6-c08-keyboard-playwright-run2.json --revision 8a9e320588ba3378b4596a609bca3762501e577f --command-json '["/usr/bin/time","-p","corepack","pnpm","exec","playwright","test","e2e/a11y/keyboard-journeys.spec.ts","--project=chromium","--reporter=json"]' --cas-root ../../_build/apps/runtime-dashboard/ds6-c08-cas-admitted-20260813 > ../../_build/apps/runtime-dashboard/ds6-c08-keyboard-capture-admitted-20260813.json
node scripts/capture_atlas_evidence.mjs --profile opaque_storybook --report ../../_build/apps/runtime-dashboard/ds6-c08-opaque-vitest.json --revision 8a9e320588ba3378b4596a609bca3762501e577f --command-json '["/usr/bin/time","-p","corepack","pnpm","exec","vitest","run","--config","vitest.storybook.config.ts","src/test/a11y/OpaqueBackgroundContrast.stories.tsx","--reporter=json","--outputFile=../../_build/apps/runtime-dashboard/ds6-c08-opaque-vitest.json"]' --cas-root ../../_build/apps/runtime-dashboard/ds6-c08-cas-admitted-20260813 > ../../_build/apps/runtime-dashboard/ds6-c08-opaque-capture-admitted-20260813.json
```

They persisted these actual reports under the ignored isolated CAS. Both
captures carry implementation aggregate
`d92065244560b8e177323688e0c3564d37709e24141a38d107c57b1bb6a0845b`:

| Profile | Runner result | Atomic receipt | Raw ref | Payload ref | Receipt ref | Capture JSON SHA-256 |
| --- | --- | ---: | --- | --- | --- | --- |
| `keyboard_playwright` | pass, 1/1 | 1/1 | `sha256:050bc0ca4d925f78bc66fdc653fd7454f319dce7d92fc1552a8e23094d1ff7bd` | `sha256:76cdfe158a60f506ea8b84f3a2e91866132bcf5b2f65f3d3817c0390b9341b3a` | `sha256:9bd31f4e8a1c956cf637c288c6df373d7c20130de66c2701489b7be7483e9f24` | `fb22852ffc832d969de044f9a4b70877d592f8ad1557cd506a186c3ade06d30d` |
| `opaque_storybook` | fail, 0/1 story | **0/7** | `sha256:a03c5da2ebb0f60b1259e6bec3f77c10ce3e60671b07602e948db56d5a6a4572` | `sha256:717e5f1d456f477d3c2777add0dd4a174cb4d2245c71ccb0dabeb52042e848e9` | `sha256:3d4956e159c567d49f0da900e38b27279a01365d3c28fd9cf9de80eeb5c00a29` | `b5195b439646bbac78ccb0de0e08b4f238c3eada30e2cfed935d40926efae05f` |

All six raw/payload/receipt integrity reports are `ok=true`; each payload
manifest names the exact raw report as its `runner_report` input, each resolved
receipt semantically binds the resolved payload, and each receipt manifest
names that payload as its exact `verification_payload` input. Integrity green means
the observations are authentic to this capture path, not that their test
outcomes are green. The opaque outcome remains fail/0-of-7, so C06 remains
gated on a future 7/7 observation as well as C04.

The honest capability label moves from `contract_only` to
`implemented_but_not_orchestrated`. A real producer, persisted artifacts,
explicit runner-to-CAS bridge, Core integrity verification, and semantic
rebinding now exist. Neither runner invokes capture automatically, no readiness
consumer reconciles the receipts, and no external surface projects them;
`consumer_missing` and `surface_missing` remain. C10's C08 integrity
prerequisite is now available, but C10 is not entered in this explicitly
ordered C05/C08/C13 session.

### C08 duplication duty, implementation receipts, and nonreceipts

The complete post-cut dashboard denominator is 1,130 paths: the 1,125 tracked
entry paths plus five new implementation paths, partitioned as 392 `.ts`, 592
`.tsx`, 17 `.mjs`, 9 `.cjs`, 2 `.py`, 1 `.sh`, and 117 other paths. Exact
search over the 1,013 executable/source paths found one C07 receipt contract,
one C08 runner normalizer/producer, one semantics-free MJS loader, one
TypeScript file/process bridge, and one Python Core-store adapter. There was no
entry `put_json()` caller, `FileSystemCAS` caller, or evidence persistence
owner in the dashboard. Migration state is `new_consumer_of_existing_core`;
Core remains canonical and no duplicate CAS/hash/manifest/verifier exists.

The first focused round was RED at 21/23 because dynamic module loading tried
to load an `http:` URL under the Storybook/Vitest environment. Static module
ownership closed it. The next focused round passed 23/23; the behavioral Core
round passed 24/24. A command-binding test initially exposed seven dependent
failures because the synthetic fixture still used a placeholder argv; that
fixture was corrected to the declared profile. After the trust-boundary batch,
the frozen focused receipt is C07+C08 2/2 files, 28/28 tests, including the
live Core corruption and provenance-mismatch witnesses. Focused ESLint over
the three TypeScript implementation paths plus the MJS loader is green. Ruff
check and format-check are green. Scoped basedpyright is 0 errors with 35
JSON-boundary warnings. The app TypeScript check has zero C08-owned errors but
remains RED on four pre-existing C02/C09 errors: two invalid
`ds6-browser-fixture` author values and two possibly-undefined `badgeEntry`
uses. This is a nonreceipt for full app typecheck, not a C08 green.

Independent review was adversarial rather than claim-only. Initial spec and
quality reviews found the override, raw-lineage, verifier-provenance,
classification, stale-receipt, P37, and type/lint findings above. The final
five-path delta review read the fixed intake, three-artifact lineage,
corruption witness, independently reconciled implementation provenance,
governance, and P37 classifications and returned CLEAN. Its independent
receipts were 28/28 focused tests, scoped ESLint, focused strict TypeScript,
Ruff check/format, and Python AST parse. A final read-only two-hunk review of
the repository-wide dirty predicate also returned CLEAN.

Three implementation-tool attempts are nonreceipts: `corepack pnpm exec
vite-node ...` failed because `vite-node` is not installed; Node's native type
stripper could not resolve extensionless TypeScript imports; and the first
capture attempt correctly stopped after detecting that JSON key ordering is
not semantic equality. The measured eighth path,
`scripts/capture_atlas_evidence.mjs`, uses the installed pinned Vite loader and
the admitted final invocations ran serially without those failures. A pair of
pre-admission Vite-loader trials overlapped and one emitted an HMR-port warning;
their artifacts are superseded and are not the admitted receipts above.
The final Python verification first repeated `policy-engine/` in a path while
already running from that directory and returned Ruff `E902`; that harness
invocation is a nonreceipt. The corrected command is the Ruff green recorded
above.

No contended artifact, readiness ledger, checker family, generated report,
`src/polisyos/**`, product surface, Russian catalog, DS5/GY path, or test
denominator was edited. No whole-suite, browser, journey, visual, full lint,
full typecheck, full build, Storybook-build, or design-token lane was rerun
after C08 implementation; the C05 terminals remain receipts only for their
recorded revision, while every omitted post-C08 lane is a nonreceipt.

## DS6-C13 — independent adjacent-print-export verification — 2026-08-13

### Owner discovery, entry cut, and lane declaration

C13 entered from clean attached commit
`075eedb3bd5cdfdee4c6a664f0fc3af18a50767d`, 14 commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. The measured cut is this plan and
journal only, 2 paths against cap 6. The product snapshot, visual spec,
readiness ledger, disposition register, DS8 CSS, and every Core path are
read-only inputs.

Owner discovery found one real-browser comparator for
`run-detail-a4-print.png`: `e2e/runtime-dashboard.visual.spec.ts` lines
571–581. Its Chromium screenshot threshold is 100 pixels and retry count is
zero. The static `tools/design/check-print-snapshots.ts` owner checks markers,
existence, and dimensions but cannot establish generated-link/report
non-overlap. The binding debt requires both semantic non-overlap and two
consecutive no-update A4 captures; a RED first run falsifies that conjunction
and does not need a second run. The expected snapshot entered byte-unchanged at
724x2113, 231,141 bytes, SHA-256
`a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`.

The first command, run from `apps/runtime-dashboard`, was:

```bash
UV_PROJECT_ENVIRONMENT=../../_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=../../src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'run detail A4 print$' --output=../../_build/apps/runtime-dashboard/ds6-c13-print-run-1
```

Its controller ceiling was the supplied 2,400 s. This attempt completed setup
RED in 4.09 s with zero tests: Playwright starts the fixture server from the
policy-engine root, so the relative `UV_PROJECT_ENVIRONMENT` resolved outside
the worktree and the server could not import `uvicorn`. It created one
unintended environment at
`/Users/deniskopylov/polisyos/.worktrees/_build/apps/runtime-dashboard/.venv-online`;
that exact directory was moved to Trash as
`atlas-ds6-unintended-venv-online-20260813-0956` and is recoverable. No
out-of-fence scratch remains. This setup RED is not a visual verdict.

The corrected command uses absolute environment identities while keeping the
same one-test selector and 2,400 s ceiling:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'run detail A4 print$' --output=../../_build/apps/runtime-dashboard/ds6-c13-print-run-2
```

### Terminal verdict and evidence

The corrected command completed visual RED, exit 1, in 55.87 s (`user 27.21`,
`sys 3.54`), safely below the supplied ceiling. It ran exactly one Chromium
test with zero retries. The screenshot assertion ran 15.1 s and reported:

- expected: 724x2113, 231,141 bytes, SHA-256
  `a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`;
- actual: 770x12991, 3,185,010 bytes, SHA-256
  `e1c7f7060c860575d8c389896f1f447b5add264025d7bf2446686dd8f5458d0d`;
- diff: 770x12991, 1,048,673 bytes, SHA-256
  `ad0a9b1177e11eb1803713f3e35697320001af11e04364fb8b041ef35fc47b85`;
- measured difference: 685,932 pixels, ratio 0.07, against the declared
  100-pixel maximum.

Measurement corrects the inherited 770x13229 actual for this run; that was the
separate C05 observation, not a value to force onto C13. The relevant product
inputs — visual spec, expected snapshot, `styles.css`, `styles/print.css`, and
`MonographLayout.tsx` — have zero diff from C05 revision `4748b9211` to this
run. Even so, C05 produced a 770x13229 actual with SHA-256
`fa6a35be9c9893f1ed856f2a320293b4f71440caf497cffefcb3c29b5af7f8c5`,
while C13 produced 770x12991 and SHA-256
`e1c7f7060c860575d8c389896f1f447b5add264025d7bf2446686dd8f5458d0d`.
Thus both the
100-pixel visual bar and repeatability fail; this is not a stable no-update
capture. The first real C13 result falsifies the conjunctive closure, so no
second targeted run was executed.

Visual inspection confirms that the actual artifact is the extremely long run
detail surface rather than the committed A4 reading-view expectation. It does
not independently compute link and report bounding boxes. Therefore the exact
semantic predicate “no generated link URL overlaps report content” remains
`not_established`, not silently inferred from URL text or screenshot presence.
That semantic nonreceipt cannot rescue the already-RED visual conjunction.
The verdict is **DS8 regression reproduced; closure failed**. C13 changes no
DS8 surface and returns the evidence to `team-design`.

### C13 duplication duty, blocked list, and nonreceipts

The complete dashboard print-style denominator is 13 tracked `.css` files.
Exactly two active rules emit `attr(href)`: the canonical print owner
`src/styles/print.css:82-86` and `src/styles.css:1609-1613`, even though
`styles.css:11` already imports the canonical owner and
`docs/brand/PRINT_AND_EXPORT.md:31-32` names it as the global entrypoint. The
copies have concrete drift: angle-bracket/8pt/`word-break: break-all` versus
parenthesis/0.8em/`#666`; the later rule shadows part, but not all, of the
first. Migration state is `duplicate_active`, comparator status is
`visual_red`, and the DS8-owned strangle target is the second emission owner.
C13 records but does not repair this product duplication. The complete E2E
denominator is 18 tracked TypeScript files and 18 `toHaveScreenshot` calls;
exactly one call owns `run-detail-a4-print.png`.

Blocked state after the serialized wave:

- C03 still needs a GREEN authoritative whole-suite Vitest receipt and release
  of the contended register/baseline manifest. C05's RED 315/316-file,
  965/966-test measurement is authoritative for that run but cannot support a
  repaired/empty governed transition; C08 subsequently added focused tests.
- C04 remains blocked on DS5's register-family release.
- C06 remains blocked on both C04 and a future exact 7/7 opaque-background
  observation; C05/C08 preserve the current browser result as 0/7.
- C10 now has C08 persistence/integrity evidence, but reconciliation was not
  entered and its consumer/surface remain missing.
- C11 remains blocked on INT-R3 content, a producer, and real observations;
  every threshold stays `not_established`.
- C13 has an independent RED verdict, but its governed readiness transition is
  blocked on the contended readiness/register family and DS8 owns the repair.

Nonreceipts are explicit: the 4.09 s setup RED ran zero tests; semantic
non-overlap has no independent bounding-box verifier; no second targeted
capture ran after the first real RED; and no governed readiness/audit artifact
was written. No C05 lane, C08 capture, whole suite, other browser lane, lint,
typecheck, build, Storybook build, or design-token check was rerun for C13.
No contended artifact, readiness ledger, checker family, generated report,
`src/polisyos/**`, product surface, Russian catalog, DS5/GY path, or denominator
was edited.

Independent C13 review returned CLEAN with no Blocking or Important finding.
It independently read the failed-status artifact, all three PNG dimensions,
byte sizes and SHA-256 values, the trace's 685,932-pixel/0.07 comparison, the
unique test owner and 100-pixel limit, the no-diff product inputs, the C05
repeatability counterexample, the two-path cap/fence, and every nonreceipt. It
confirmed that semantic non-overlap remains `not_established`; it ran no lane
and changed no file.

## DS6-C16 — deferred-lane diagnostic closure — 2026-08-14

### Entry, measured cut, and exact diagnostic census

`git status -sb` at entry reported a clean attached
`codex/atlas-ds6-evidence-workflow` at
`41a2020d5c2097c30c94807737ba6d3a80323d2e`, 15 commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. C16 measures exactly seven
paths against declared cap 7: `LineageGraph.test.tsx`, `parity.test.ts`,
`atlasManualAtMaturity.ts`, its focused test, the opaque Storybook fixture,
the DS6 plan, and this journal. No helper, catalog, product component, governed
Atlas artifact, Core path, C10 path, DS5/GY path, or Russian locale joins the
cut.

The C05 receipts reproduce as sixteen diagnostics, not twenty: one whole-suite
assertion, four TypeScript errors, and eleven lint errors. Production build
repeated the same four TypeScript errors before Vite and therefore contributes
no additional identity. The exact individual adjudication is:

| # | Diagnostic | Adjudication and repair |
| ---: | --- | --- |
| 1 | `LineageGraph.test.tsx:28`, stale threshold sentence | C15-R1 importer-test fallout; update only the assertion to the current label-form render, `Graph nodes: 3; render threshold: 2.` |
| 2 | opaque fixture line 39, invalid `author` literal | C02 test-fixture contract defect; use the architecture-owned candidate author `drafter` |
| 3 | opaque fixture line 166, propagated invalid authored block | same typed fixture value reaches `CandidateFrame`; the single owner correction closes this second compiler diagnostic |
| 4 | maturity test line 39, `badgeEntry` possibly undefined | C09 test proof does not carry its top-level guard through the helper closure; construct the constant through a throwing owner-row resolver |
| 5 | maturity test line 52, same possibly-undefined entry | same resolver closes the second array-spread diagnostic without a non-null assertion |
| 6 | parity line 729, `consistent-generic-constructors` | static generic-placement diagnostic; move the type argument to `new Set<...>()` |
| 7 | parity line 736, first enum comparison | static AST traversal typing diagnostic; route simple value elements through a typed AST-type set |
| 8 | parity line 736, second enum comparison | same typed set/structural-options traversal; no admitted identity changes |
| 9 | parity line 743, tag enum comparison | use the AST's real `children` discriminator |
| 10 | parity line 875, plural enum comparison | use the real `options` plus `pluralType` discriminators; same-variable cardinal ownership is unchanged |
| 11 | parity line 894, select enum comparison | use the real `options` discriminator without weakening the selector occurrence rule |
| 12 | parity line 909, tag enum comparison | use the same real `children` discriminator in the ownership walk |
| 13 | parity line 1152, conditional `expect` | compute the optional grouped witness conditionally, then compare unconditionally |
| 14 | parity line 1158, conditional `expect` | include the unavailable-form result in that same unconditional comparison |
| 15 | maturity nested evidence-ref `.passthrough()` deprecation | admission-sensitive C09 refactor; replace with Zod's exact `.loose()` successor only after characterization |
| 16 | maturity owner-row `.passthrough()` deprecation | same admission-sensitive replacement at the outer owner boundary |

Focused reproduction was exact. `tsc -p tsconfig.app.json --noEmit` exited 2 in
19.27 s with only diagnostics 2–5. Scoped ESLint over the five implementation
paths exited 1 with diagnostics 6–16, exactly eleven errors and zero warnings.
The C05 whole-suite JSON remains the red-first receipt for diagnostic 1.

### Admission characterization, static-round ruling, and focused repair

Before changing either deprecated Zod call, a new behavioral characterization
ran against `.passthrough()`: the architecture-shaped valid owner and the same
owner carrying unknown top-level and nested evidence-ref keys both remained
admitted and reached the identical fail-closed
`manual_at_integrity_not_established` result. Focused C09 Vitest passed 12/12
in 1.23 s. Zod 4.4.2's local implementation constructs both `.passthrough()`
and `.loose()` with the same `catchall: unknown()` definition; after the two
replacements the same 12/12 witness remains green. This proves the admitted set
used by C09 is unchanged rather than inferring equivalence from the deprecation
text.

The nine parity findings are classified **non-behavioral static diagnostics**,
not dropped logic. Their scoped diff changes only TypeScript discriminators,
generic placement, and test assertion structure. It changes zero active or
frozen catalog bytes, declaration identities, fingerprints, failure codes, or
governed artifacts. The complete focused repair wave passed 4/4 files and
62/62 tests: parity 34/34, C09 12/12, the opaque classifier 12/12, and
LineageGraph 4/4. Scoped ESLint over all five implementation paths exited zero,
and app TypeScript exited zero in 41.72 s. Under the repaired breaker predicate,
this lint-only round does not consume a C15-R1 mechanism round; the behavioral
denominators and governed bytes are proven unchanged.

### Opaque fixture diagnosis and pre-closeout nonreceipt

The C05/C08 0/7 receipt fails before source classification. Read-only owner
tracing identifies the controlled `body` ancestry as the first fixture member
with a dashboard `background` transition: the harness sets opaque color/image
and immediately samples computed style while that transition may retain the
gradient or an in-flight alpha. The strict `hasOpaqueBackground` function is
not defective and its SHA-256 remains
`c54524c59102c38e02eafdf6cc690ca8896dd1a0262b243138f71e271aa0d225`.
The fixture disables the transition on every controlled ancestor while still
assigning an actual opaque white background. No predicate, source selector,
component, denominator, or axe classifier changes.

An attempted pre-repair diagnostic Storybook run did not execute the story: it
was killed after the supplied 300 s ceiling and is a harness nonreceipt, never
a contrast result or timing sample. The command wrapper delivered the signal
late and `/usr/bin/time` recorded 373.75 s; the ceiling is not raised and that
duration is not admitted as an Atlas sample. Its observed shared-host regime
was eight logical CPUs, load averages 2.63/3.49/3.51, no other DS6 heavy
parent, and multiple idle external Playwright MCP processes. The final
source-frozen lane will use a hard process-group controller at the same 300 s
ceiling.

At this point the measured tracked set is six paths because this journal entry
is the seventh declaration path being appended. `ru.json` remains byte
identical at SHA-256
`578a454329989fe3e6feddd3ec2e612b6e8954a72251717f1aba9b135e456b35`,
and every contended/Core/C10 path has zero diff. Independent source review and
the serialized closeout wave remain pending; no green heavy-lane claim is made
here.

### Opaque fixture measured diagnosis, breaker-safe repair, and reviews

The first hard-controller browser execution corrected the earlier
source-only diagnosis: disabling transitions and assigning opaque white to the
entire controlled ancestry did establish every `hasOpaqueBackground`
precondition. The story then reached classification and returned one
`axe_incomplete_unattributed`, not an ancestor failure. Unattributed axe
diagnostics identified the node as the CandidateFrame authored-text decoration
`<span aria-hidden="true">⊙</span>` with axe 4.11.4's exact message
`Element content contains only non-text characters`. This finding is outside
the seven text-foreground predicates; it is not converted into a pass.

The first attempted remedy excluded every `aria-hidden` descendant. Independent
quality/spec review rejected that open class under P31/P33/P37: a future
text-bearing hidden subtree could bypass the text rule. The repaired fixture
instead recomputes one exact live-DOM exception: one CandidateFrame `SPAN`,
trimmed content exactly `⊙`, no Unicode letter/number, and exact cardinality.
Only that HTMLElement is excluded. The single `runTextContrast` adapter first
enumerates an `aria-hidden` source root plus all its descendants and fails
closed on every other text-bearing node. Two marker-preserving witnesses invoke
that same adapter: a newly appended textual descendant and an
`aria-hidden=true` source root both turn red, then restore the DOM. Every
remaining axe incomplete remains source-unattributed and makes the atomic
receipt count zero.

The browser chronology is retained at true strength:

- the late-signalled 373.75 s attempt remains a killed harness nonreceipt;
- 17.52 s, 15.54 s, 11.83 s, and 11.35 s diagnostic runs were RED while the
  unattributed axe reason was narrowed to the exact glyph;
- a 5.91 s 7/7 run was invalidated by review because its `aria-hidden`
  exclusion was an open class;
- a 29.51 s run was RED because an axe-only low-contrast textual witness did
  not establish the intended declaration property;
- a 14.57 s 7/7 run was invalidated when review found the witness bypassed the
  default adapter and did not cover a source root; and
- the final bounded run completed GREEN at exact 7/7 in 14.02 s. Its one
  Storybook file/test passed, raw JSON is 163,320 bytes, and SHA-256 is
  `a608e9b606e50b75bef602136e0f9b0c47406dfedf0f68888b792b781e99eafa`.

`hasOpaqueBackground`, the classifier, and the frozen registry remain
byte-identical; the predicate SHA-256 is
`c54524c59102c38e02eafdf6cc690ca8896dd1a0262b243138f71e271aa0d225`.
Final replacement spec and adversarial-quality reviews were both CLEAN. Their
predecessor continuation attempts ended in tool-quota errors and are review
nonreceipts, not approvals. Boundary review remained CLEAN on the exact
seven-path cap and all forbidden scopes.

### Serialized closeout receipts and regime

Every admitted run used a hard process-group controller, one DS6 heavy parent
at a time. The regime label is
`shared_host_uncontrolled_external_load_one_ds6_heavy_parent`; every run saw
eight logical CPUs. Load values are the 1/5/15-minute averages sampled before
launch. No run exceeded its supplied ceiling and no ceiling moved in flight.

| Lane | Ceiling (s) | Result | `/usr/bin/time real` (s) | Launch load 1/5/15 | Exact receipt |
| --- | ---: | --- | ---: | --- | --- |
| whole-suite Vitest JSON | 1,200 | GREEN | 515.40 | 7.57 / 11.88 / 12.98 | 317/317 files; 983/983 tests; 0 failed/pending/skipped/todo |
| full typecheck | 300 | GREEN | 14.85 | 99.38 / 79.36 / 44.58 | all app/node/tools `tsc --noEmit` projects exited 0 |
| production build | 300 | GREEN | 20.75 | 70.76 / 74.24 / 43.73 | typecheck, 3,885-module Vite build, PWA, postbuild security, and Atlas Tailwind-source check exited 0 |
| full lint | 2,400 | GREEN | 19.18 | 41.52 / 66.56 / 42.17 | complete configured ESLint population, zero errors/warnings; warm-cache sample, not compared to C05 cold time |
| opaque Storybook probe | 300 | GREEN | 14.02 | 6.32 / 13.03 / 13.46 | exact 7/7 atomic computed-pass receipts; zero violations/incompletes in the seven custom source observations |
| component a11y | 300 | GREEN | 30.39 | 22.82 / 58.59 / 40.37 | unchanged 84/84 files and 85/85 tests |

The whole-suite JSON is the authority, not any retired estimate. It contains
317 test-result files and 983 assertions, all passed; Vitest duration is
512.9371760253906 s; raw JSON is 368,353 bytes with SHA-256
`0621a29ad48454fa57c232206f2eec26267e82ad5285879dacc02bf29ebe79ec`.
The run exercised the independently reviewed five-code-path C16 source delta
above entry HEAD `41a2020d5c2097c30c94807737ba6d3a80323d2e`; that binary diff has SHA-256
`800225190d7a47f68b585db206d6b634bd1c7787ab27bb9c5b8e8e1f5fc2bf8a`.
No nonexistent pre-commit Git SHA is invented; the register's
`repair_commit` is filled from the landed C16 commit.

The concurrent scoped-ESLint/app-TypeScript preflight after the first fixture
edit had no regime capture and overlapped; it is admitted only as a source
syntax check, never as a timing or closeout receipt. The serialized full
typecheck and full-lint rows above are the sole closeout receipts.

The raw Storybook automatic a11y meta-report separately retains three
unattributed incomplete nodes, including one `color-contrast` incomplete for
the exact excluded `aria-hidden` `⊙` glyph. They are outside the seven custom
source observations and are neither attributed source receipts nor silently
counted green; the custom story's atomic result remains exact 7/7.

### C03 transition, blocked list, and duplication duty

C16 discharges C03's green-receipt gate. The exact pending governed values are
`exit_code=0`, `test_files={317,317,0}`, `tests={983,983,0}`,
`wall_duration_seconds=515.40`,
`vitest_duration_seconds=512.9371760253906`, and empty RFC8785/JCS
`failure_set.sha256=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The literal command and raw receipt hash are recorded in the plan. The
then-current released producer/checker must recompute those values; DS6 did not
write the contended manifest.

Current gates are therefore:

- C03 waits only for DS5's register/baseline-manifest family release; its green
  whole-suite gate is discharged.
- C04 waits for the same register-family release.
- C06 has exact 7/7 and now waits only for C04's released typed row.
- C10 has C08 persistence/integrity evidence but is deliberately unentered
  until the next clean-tree session; reconciliation consumer/surface remain
  missing.
- C11 still needs INT-R3 content, a producer, and real observations; every
  threshold remains `not_established`.
- C13 retains the independent visual RED and waits for the DS8 repair plus the
  released readiness/register owner before any governed transition.

Duplication census denominator was all 1,015 tracked dashboard `src` paths,
including all 954 tracked TS/TSX source files (363 `.ts`, 591 `.tsx`). The
C15-R1 numeric declaration/gate has one owner,
`shared/i18n/parity.test.ts`; the contrast capability has one registry and
classifier plus its focused test and Storybook consumer; C09 maturity has one
contract owner plus its focused test. No sibling semantic owner was found.
The product-local English `pluralize()` in `MonographLayout.tsx` remains an
adjacent out-of-catalog finding, not a duplicate catalog gate. The complete
13-file CSS denominator still has exactly two active `attr(href)` emitters,
`src/styles/print.css:84` and `src/styles.css:1611`; their
`duplicate_active` DS8 ownership and strangle target are unchanged.

Nonreceipts remain explicit: no page-a11y, journey, full-visual, Storybook
build, interactive Storybook/dev-server, or C10 lane was rerun in C16; no
contended register/manifest/readiness/checker/report, `src/polisyos/**`, Russian
catalog, product component, DS5 path, or GY path was written. The C05/C13
receipts for the omitted lanes retain their original strength and are not
silently promoted.

## Post-C16 read-only visual attribution and C17 registration

C16 landed clean as `97d0c620836a3e6d33c347a1f7f563aaa9177d0c`,
16 commits ahead of `c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`.
Branch readback showed exactly its seven declared paths and an empty working
tree. The subsequent attribution ran no browser, server, build, or product
mutation; only this plan and journal register its finding.

The controlling comparison is DS4-C19b's clean `470a802d4` visual receipt
versus C05's admitted run at `4748b9211`. The DS4 journal records 17/18 with
only DS8's `run detail A4 print` red. C05's raw stdout (25,135 bytes, SHA-256
`19e0279e59d862a37d800d79d976129e85e25d03ebdfb39c997b43ad3c8d637f`),
stderr (13,462 bytes, SHA-256
`b853f29a2ec3e263eb42d64c22b4a4cc0f55fdc10d14ea14f924b4f6ca537ede`),
and exit file (`1`, SHA-256
`4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`)
establish 14/18 and four failures. The DS8 print identity remains causally
separate; the three newly attributed identities are:

| Identity | C05 comparison | C15-R1 visible input | Additional finding |
| --- | --- | --- | --- |
| `evidence promotion focus` | expected/actual 1094x8529; 2,685 pixels reported before the 5 s stability timeout | `pages.evidence.runContextSummary`, `panels.dataIntelligence.focusSummary`, `phase32.freshness.derivedFacts` | selected response `meta.generated_at` drifted from the August 1 baseline to August 12 |
| `dark evidence fabric` | expected/actual 1094x6521; stable 532-pixel delta | `phase32.freshness.derivedFacts` | the same response-metadata drift |
| `mobile command center` | expected 369x3700, actual 369x3680; stable 28,414-pixel delta | attention, throughput, and evidence narrative bodies | fully explained by the C15-R1 copy/wrapping change |

The committed expected PNGs are byte-identical to C05's retained expected
artifacts and have SHA-256, respectively,
`cfdc138b4438d6d6e18683dd958aa19f6c434fc681a29291bdf16cddf30df429`,
`4a5e8d8eac993401ca9d47790ea9d8470554d06eb7708e2e5c9945f5193e8727`,
and `40436c0cbdc3b7db02bc6cd155e0f5874eb85dd4db827f36f08a848853d42c4d`.
Their C05 actual hashes are
`af8468393572f8b4f96bc63de61fac70e58422ee8d5dc24c42b8bcb9708e5d82`,
`6b2735bad47b767a759379d9b25745df49bbd7ce23c061cd8eac2a8833cd0a35`,
and `23cab2cb08f15b1ee668faf1de5a4a81a4ba2dc1ec214d29981c7b575a49557d`.
The three baseline Git blobs (`8ea8707a...`, `eb31eefd...`, `7b396812...`),
the visual spec (`a0d296a3...`), and the four relevant consumers remain
byte-identical from DS4 through C05 and current HEAD. The spec and baseline
files therefore did not introduce the regressions.

The live introducing commit for every C15-R1 copy delta is
`4748b921113b884a3fe17593bc50c1af300e97f2` (`DS6-C15-R1 gate
quantitative-use declarations`). The English catalog moved from SHA-256
`9f0da15ea28d8f0b1ebe9cd39b1643ba7280e6fc720d54ab9237ab33ee132f01`
to `e31c826d8c689c7a6350e30de48c4dc321cb673a34ebbdfa2315dfbf96ba5825`.
The exact copy first appeared in stopped checkpoint `8fd8f9e5d`, was fully
removed by forward revert `4d7743f07`, and was persistently reintroduced by
C15-R1. A direct formatter comparison confirms C01-R1's fixture-selected
`Unavailable` attention branch and `2` queue branch render the same text as
DS4, so C01-R1 is not the visual introducing commit. There is no DS5
attribution.

The evidence-page cases also disclose a second, shared defect with no
post-DS4 introducing commit. C05's retained response traces show every
connector `last_health_check` is null. `EvidenceFabricPage.tsx:169-173`
therefore selects run-context or promotion-candidate `meta.generated_at`, and
`productionSlice.ts:206-207` falls back to that selected response time.
Production `ApiMeta.generated_at` receives its `_utc_now` default at
`src/polisyos/core/contracts/runtime.py:289-299`. DS4-C19b froze browser time
and bureaucratic timestamps, but its visual harness did not bind the selected
response metadata across process starts; its same-process receipt did not
establish cross-start repeatability. The repair belongs to the shared
visual-harness/DS4-C19b lineage and must not change production `ApiMeta`
semantics. It is outside DS6's backend fence. Re-anchoring the two evidence
snapshots before that harness owner makes the fixture deterministic would
preserve a moving expectation.

DS6 therefore registers **C17 — reconcile C15-R1 visual baselines**, declared
cap 5: the three exact snapshot PNGs plus this plan and journal. C17 is not
entered. Its first gate is the shared visual harness deterministically binding
the selected evidence-response metadata; its second is explicit authorization
for the real visual lane. It may then generate only the three snapshots and
must restore their passes plus the inherited full-lane envelope, with only the
separately DS8-owned print identity allowed to remain red. The timed-out
evidence-promotion actual is a comparator RED, not a stable re-anchoring
receipt.

Duplication readback remains unchanged over all 13 tracked dashboard CSS
files: exactly two active `attr(href)` emitters remain at
`src/styles/print.css:84` and `src/styles.css:1611`. They are DS8-owned
`duplicate_active`; `styles.css` remains the strangle target. No duplicate
visual-baseline owner was found. The attempted read-only `tsx` formatter
helper was unavailable and is a tooling nonreceipt; the same four renderings
were then reproduced with the installed plain-Node `intl-messageformat`
runtime. No full visual, targeted visual, server, or shared-fixture repair ran,
and no snapshot, product, catalog, Core, contended, DS5, or GY byte changed.

## DS6-C10 stop record — 2026-08-16

C10 entered on the explicit C10 → C11 → C17 continuation with a declared cap
of 16 and measured exactly ten candidate paths. Two bounded mechanism repair
rounds were consumed. The final source freeze had focused C07/C08/C10
**47/47**, route behavior **10/10**, scoped lint/type/Python checks, and one
live launcher PASS, but two independent final reviews rejected the mechanism.
Those green results remain receipts for admitted cases in the stopped attempt;
they are withdrawn as C10 closure evidence.

The final findings are set against the round-2 acceptance fence preserved in
checkpoint `573be959890f8e35f72e846e0a37b6eac5fc4396` and against P29, P31,
P32, and P37 in
`docs/reference/policy-design-case-failure-patterns.md`:

1. **Blocking — canonical-runner provenance and single-intake gap.** The
   checkpoint's positive `routeTestReport()` fixture in
   `atlasSurfaceReadinessReconciliation.test.ts` constructs purported Vitest
   JSON in memory and persists it through the real adapter.
   `_derive_c10_route_test_receipt()` derives assertion facts from those
   supplied bytes while `_validate_c10_raw_binding()` consumes caller-supplied
   `process_exit_code`. CAS hashing proves the supplied bytes and shaped
   consistency, not execution by the fixed launcher or the OS exit.
   `C10_FIELD_PROVENANCE` nevertheless labels the route receipt and process
   exit `independently_reconciled`. Both final reviewers reproduced this
   P29/P31/P32/P37 defect.
2. **Blocking — incomplete pre-CAS owner invariant.** The checkpoint's
   `_c10_entries()` checks selected identity, maturity, and readiness
   vocabulary only. A reviewer invalidated all ten claimed date/uniqueness
   constraints and removed `chain.semantic_test`;
   `_c10_canonical_reconciliation()` still returned `pass`, no findings, and
   the canonical counts. That falsifies the round-2 statement that a single
   pre-CAS choke point independently recomputes the complete admitted owner
   semantics.
3. **Important — non-bidirectional status contract.** The checkpoint's
   `c10DetailsMatch()` forces `fail` when a negative predicate exists but does
   not require `pass` when none exists and does not exclude C10 `incomplete`.
   Canonical zero-finding PASS facts mutated to `fail` or `incomplete` with an
   unrelated finding pass the exported TypeScript payload and binding
   contract, although Python later rejects them.

All three are mechanism findings; the test/docs-only breaker exemption does
not apply. The breaker is consumed (**2/2**), so no third repair was attempted.
Ordinary history preserves the full ten-path candidate at
`573be959890f8e35f72e846e0a37b6eac5fc4396` and removes it in forward revert
`a7ae9189147d012fd8a3c80d741ed5c330787672`. A root-scoped comparison proves
that the revert tree is byte-identical to pre-entry HEAD
`a84556865454a506b80ca5e12aadf9c932f4d07e`.

C10 is not landed. Its producer, artifact, bridge, CI consumer, verification,
surface, and governed projection tail remain absent at HEAD. C11 is not
INT-R3-blocked for six metrics, and the deterministic visual-fixture repair is
DS6-owned; both remained unentered solely because the authorized sequence
placed them after a landed C10. Owner discovery measured the visual repair's
honest future set as the visual spec, three attributed PNGs, plan, and journal
(six paths). The cap-5 C17 declaration therefore remains unentered and the
work is re-cut as C18 at cap 6 under the continuous-number sizing law.

The heavy-lane timing record gains no new sample. The existing lint samples
remain cold **1,182.94 s** and warm shared-`_cache` **19.18 s** (**62x**); a
future ceiling uses `2 x p95` for the matching host/cache regime, not a margin
over the minimum. No C11/C17/C18 implementation, heavy lane, contended
artifact, baseline, DS8 print byte, `src/polisyos/**`, product surface, DS5
path, or GY path changed. The duplicate census is unchanged: exactly two
active `attr(href)` emitters over 13 tracked dashboard CSS files, DS8-owned
with `src/styles.css` the strangle target.

Earlier sections' “current” and “blocked” lists remain chronological snapshots
of their cluster landings; this stop record is the later controlling state.

## DS6-C11 — Atlas health-metric instrumentation entry — 2026-08-16

### Clean entry, refused predecessor, and exact fence

`git status -sb` at entry showed the attached
`codex/atlas-ds6-evidence-workflow` branch with no changes at
`b856d4e1f735c8158d93504cdb6d5c7d5ab8a81f`, 20 commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. C11 measures exactly seven
candidate paths against its immutable cap of 12: the new health-metric contract
and focused test, a fixed MJS producer, the existing app-local Core persistence
adapter, a reference page, this plan, and this journal. No helper path is
created; a future structural need for one still fits the cap but must be
measured before entry.

C10-R1 is not entered. The architect ruling classifies the stopped findings as
one refused mechanism: independently verified facts were accepted from
supplied report bytes, exit status, or declared basis, and then collapsed into
one boolean. The three witnesses are the canonical-runner-provenance/single-
intake gap, the incomplete pre-CAS owner invariant, and the non-bidirectional
status contract recorded in the preceding stop section. The plan records the
two future per-claim bases and explicitly identifies the PV-K01 analogy as an
internal C10-R1 ruling rather than an extension of that public ratification.

The C11 production intake applies the lesson structurally: callers may select
only the closed C11 operation. They cannot supply report bytes, a repository
root, producer path, exit status, or observation basis. The Python adapter
invokes the fixed repository producer and observes its own child exit/stdout.
Review later found that process selection and authority admission were not yet
closed; the repair entry below is the controlling mechanism description.

### Owner discovery and complete denominators

The bars are the master health table at lines 1642-1652, the INT-R3 rider at
lines 1035-1043, C07's storage convention in
`atlasEvidenceArtifact.ts:31-56`, C12's exact instrument seam, and P07, P10,
P29, P31, P32, P35, and P37 in the failure-pattern register.

- The complete DS1 readiness owner has 261/261 entries, SHA-256
  `11f4898f547283968f97f8778a2b29cf15520214151ea65b1a69bc6072f3e812`;
  its strict schema SHA-256 is
  `f884cc3b9522b5a291f7b3d1a1e4256a243df603d9d16aa6510d183582d9beab`.
  Neither owner contains an exhaustive decision-bearing-render/DS4-primitive
  relation or a blocker/abstention/out-of-envelope/stale-cached render-state
  classifier. Primitive adoption and fail-closed fidelity are therefore
  `unknown`, not zero and not missing; their denominator predicates are
  `not_established`.
- The complete audience-denial proxy file has six test functions and SHA-256
  `ada70a43798605e4d62274078dcf29b6946c792f7f0701cf47df5e8c16932ce3`.
  Its own module contract says DS5 owns the final audience mapping. Six proxies
  are not the complete audience-scoped endpoint set and source presence is not
  a test-run receipt, so audience enforcement is `unknown`.
- The canonical cluster-map validator ran read-only and returned PASS with
  27/27 cells implemented, zero open/incomplete cells, zero open-cell closure
  rows, and emitted-report SHA-256
  `aa3d5e9c9e5ed5891fcc9def053803e9b4d49c25b1a52fcdd086ba3245ae5959`.
  The map SHA-256 is
  `b9409bc276d77d60919fab996ced4d01189c276eb38edad1eaa23e831edd69f4`.
  Review rejected the initial cited-report basis because it did not bind a
  resolvable artifact and verifier provenance. The repair below reruns the
  canonical validator as a subordinate closed recomputation and admits this
  row only as `observed_by_instrument/recomputed`.
- The complete adoption ledger has 233/233 entries and zero `stable` rows,
  SHA-256
  `8e253a971d87119c7685efdf64895a364ffb253d19694dbc743dd697b4057545`.
  Its schema SHA-256
  `5ae69e709ed569dcae677b5b9778c96f783b1e61c587f161cd68222cffc62085`
  requires both browser and `at_manual` evidence for every stable row. Eligible
  zero and covered zero form `0/0`, so evidence coverage is `incomparable` with
  null ratio/ranking, never a vacuous 100% pass.
- Across the same complete 261 rows, 193 carry MACHINE audience and five are
  `implemented`; the strict one-key-set schema has no shipped-surface/twin
  relation or twin-test receipt. Those fields are refused proxies and the
  missing structured relation makes machine-twin parity `missing`.
- C12's actual imported profile freezes six behavioral metric identities and
  six threshold rows, all `not_established` with null comparator, value, unit,
  and source. Its research source and observation artifact are absent. C11
  therefore records `protocol_seam_only` plus observation `missing`, without
  inventing a threshold or stable-bar effect.

The initial duplication note used a narrower matcher and is superseded by the
complete repair census below. C07/Core remain the one CAS/storage owner and C11
adds no evidence receipt, kind, hash implementation, or second CAS.

### Corrected contended package and nonreceipts at entry

C03, C04, and C06 are complete executable deltas once DS5 releases the
then-current owner family. C13 is not executable: it is a `NO WRITE` until DS8
repairs the regression, semantic non-overlap is independently established, and
two consecutive stable no-update captures exist. The package is ready for
three executable transitions plus one held no-write, not four governed
transitions. No C10-R1 projection delta exists.

No browser, visual, Storybook, full Vitest, full lint, full typecheck, full
build, page-a11y, journey, dev-server, contended owner, `src/polisyos/**`,
Russian locale, product surface, DS5 path, GY path, or DS8 print byte was
touched at entry. Each unrun lane is a nonreceipt, never green.

### Red-first, implementation, and mechanism classification

The focused C11 test was written before its owner. The first run failed in
2.07 seconds because `./atlasHealthMetrics` did not exist; no test executed.
That is the ordinary red-first receipt for the missing contract and producer,
not a product regression.

The implementation then established exactly the seven declared paths:

- a strict `polisyos.atlas.health-metric-report@1.0.0` contract whose ordered
  tuple rejects an added, removed, or renamed metric identity;
- six repository-derived metric rows plus C12's exact seventh protocol seam,
  retaining `unknown`, observed zero, `missing`, and `incomparable` as separate
  closed variants;
- one fixed no-argument MJS producer which reads the complete canonical owners
  and runs the canonical cluster-map validator;
- one closed `persist_atlas_health_metrics` operation in the existing C08
  adapter. Its request is exactly `{"operation":"persist_atlas_health_metrics"}`;
  report, repository-root, producer-script, exit-code, basis, and arbitrary
  extra intake fail before execution;
- exact raw producer stdout persisted as `atlas_health_metric_report`, plus one
  `atlas_health_metric_snapshot` whose sole Core CAS input is that report under
  `measurement_report`. This introduces neither a C07 evidence kind nor a C07
  receipt and leaves `src/polisyos/**` untouched;
- a reference projection that documents current denominators, state semantics,
  replay bindings, denied uses, and the honest
  `implemented_but_not_orchestrated` capability label with
  `consumer_missing` and `surface_missing`.

This was the pre-review mechanism. Review demonstrated that PATH and
`NODE_OPTIONS` could replace or alter the process that emitted rows, and that
the cited surface basis lacked sufficient provenance for an observed zero.
The repair entry below supersedes this description without entering C10-R1.

Two static findings were adjudicated before repair. ESLint rejected the test's
two-argument Vitest `expect`, and TypeScript rejected assigning a deliberately
invalid union member into a fixed tuple slot. Scoped diffs changed only the
test witness: the assertion now preserves stderr in the compared object and a
typed helper mutates the invalid candidate through `unknown`. Neither changed
production logic, a governed byte, nor a test outcome; both are
non-behavioral test-harness diagnostics, not mechanism findings. The C11
enforcement and persistence mechanism therefore consumed no mechanism repair
round for either finding.

### Verification receipts and capability strength

The focused C11 run passed **13/13** in 5.52 seconds, including the exact
seven-identity rejection, all four state distinctions, no-ranking comparison,
six observation-vs-one-cited-report bases, the incomplete audience and MACHINE
proxies, five forbidden public-intake fields, and a real temporary Core CAS
round trip with a negative lineage mutation.

The importer/blast-radius run passed **49/49** across four files in 11.71
seconds: C07 artifact contract 12/12, C08 automated capture/persistence 16/16,
C12 honesty protocol 8/8, and C11 health metrics 13/13. This proves the existing
C07/C08 operation still persists, resolves, verifies, and binds its original
receipt path after the adapter gained the closed C11 branch.

The app TypeScript project (`tsconfig.app.json`, not the three-project full
typecheck) passed with no diagnostics. Scoped ESLint over the C11 TS, test, and
MJS producer passed with zero warnings. Offline Ruff 0.15.22 and Python bytecode
compilation passed for the modified adapter. The fixed MJS producer emitted
seven typed rows in the exact current sequence:
`unknown/unknown/unknown/zero/incomparable/missing/missing`, with the seventh
labelled `protocol_seam_only`.

An independent executable smoke invocation used a fresh temporary filesystem
CAS, passed with exit zero, persisted seven rows, verified the report and
snapshot, and returned the exact `measurement_report` lineage plus
`implemented_but_not_orchestrated` / `consumer_missing` /
`surface_missing`. Its artifact identities are run-specific because the report
binds the observation time and current dirty posture; the terminal receipt,
not a copied identifier in this journal, is the authority.

Tooling nonreceipts are explicit. `uv run --frozen python -m ruff` found no
Ruff module in the worktree environment; `uvx --offline ruff` was then the
available pinned-cache route and passed. One first Ruff call used an
app-relative path from inside the app and returned `E902` (path absent); the
corrected same-file invocation passed. A broad Prettier check reported the two
long-lived append-only plan/journal files as unformatted, so no bulk rewrite of
their historical bytes was taken; the two new TS files, MJS producer, and new
reference page were formatted directly. These are tooling/path nonreceipts,
never metric or product failures.

No aggregate health PASS, stable grant, blocking authority, consumer, CI
orchestration, or governed surface projection exists. C11 is therefore
`implemented_but_not_orchestrated`; the missing chain is explicit rather than
hidden behind the persisted artifacts.

### Pre-review duplication duty and nonreceipts (superseded)

The quoted “three backend lexical hits” was a sampled classification, not the
complete matcher result, and is withdrawn. The controlling repair census below
walks the exact denominator and classifies all 13 matches. No second C07
receipt/evidence-kind family or Core CAS is introduced. C12 remains the reused
honesty instrument. The two active `attr(href)` print emitters remain the
previously registered DS8-owned duplication and are untouched by C11.

At the C11 freeze the later controlling dependency state is:

- C03 waits only for DS5's register/baseline-family release; C16 already
  discharged its green whole-suite gate.
- C04 waits for the same register-family release.
- C06 waits for C04's typed row; C16's exact 7/7 receipt already discharged the
  browser gate.
- C10-R1 requires its own clean-tree session under the per-claim vector/basis
  ruling recorded above.
- C13 remains a `NO WRITE` until DS8 repairs the print regression, semantic
  non-overlap is independently established, two consecutive stable no-update
  captures exist, and the readiness/register owner is released.
- C14 remains last, after the preceding closure obligations.

C18 is the separately authorized deterministic-fixture and re-anchor cluster,
not a C11 dependency or a reason to widen this seven-path cut.

No full Vitest, full three-project typecheck, full lint, build, browser,
Storybook, page a11y, journey, visual, dev server, design-token lane, contended
governed artifact, readiness ledger, `src/polisyos/**`, product surface, Russian
locale, DS5/GY path, visual baseline, or DS8 print byte ran or changed in C11.
Each unrun lane remains a named nonreceipt, never green.

## DS6-C11 review repair entry — 2026-08-16

Independent review reopened C11 on two Blocking and four Important mechanism
findings. The repair stays below the immutable cap of 12 and declares exactly
ten paths before adding one structural owner and its locked validator
dependency:

1. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts`
2. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts`
3. `apps/runtime-dashboard/scripts/measure_atlas_health.mjs`
4. `apps/runtime-dashboard/scripts/persist_atlas_evidence.py`
5. `apps/runtime-dashboard/scripts/validate_atlas_health_sources.py`
6. `pyproject.toml`
7. `uv.lock`
8. `docs/reference/frontend/atlas-health-metrics.md`
9. the DS6 plan
10. this journal

The new path is the domain-named, shared canonical-source validator used by
both the fixed MJS producer and the Python admission chokepoint. It is required
to apply the complete DS1/DS2 Draft 2020-12 schemas with format checking and
local reference resolution without creating a caller-selectable source path.
The test-toolchain extra adds the already locked `jsonschema` implementation
as a direct dependency so the fixed `.venv/bin/python` path is reproducible;
dependency declaration and lockfile are both part of this ten-path cut.
The repair closes P05/P07/P10/P29/P31/P32/P33/P35/P37: raw process output is a
candidate, Python admission is the sole limited-descriptive emission, exact
metric identities own their status/basis/state combinations, and no cited
report is promoted into an observation or independent reconciliation.

Red/green receipts, the complete duplication denominator, and all explicit
nonreceipts are recorded after the repair source freezes.

### Review-repair red/green and authority result

The first adversarial repair run collected 18 tests and failed seven in 11.70
seconds: the old cited surface basis was still accepted, cross-metric
status/basis/state substitutions passed, `not_established` rows accepted an
observed zero, no full-schema helper existed, raw report authority was not
candidate-only, a caller-PATH fake Node ran, and a `NODE_OPTIONS` preload ran.
Those are mechanism RED receipts, not hypothetical assertions. The first
post-repair focused receipt was 19/19; it is retained as chronology, not the
controlling final receipt. A separate provenance witness was also red first,
1 failed/18 skipped in 8.23 seconds, before the snapshot bound the isolated
source-validator toolchain and environment; it then passed 1/1 in 8.37
seconds. The final repair added the duplicate readiness/adoption identity and
mixed-state surface-binding witnesses; the controlling focused receipt is the
21/21 test-extra receipt recorded below.

The repaired flow has two deliberately different authority bands. The fixed
MJS/TypeScript report is `candidate_only`, authoritative for nothing, and
explicitly denied descriptive measurement. The Python adapter resolves Node
only through its module-owned absolute allowlist, executes the resolved binary
with a fixed minimal environment, and rejects every caller-selected report,
root, script, exit, or basis. Both the producer and admission execute the
fixed `.venv/bin/python -I` source validator with the same minimal environment.
The validator applies the complete DS1 and DS2 Draft 2020-12 schemas, including
formats, unique arrays, additional-property rejection, locally bound external
definitions, and the stable-evidence conditional, before any projection. The
adapter reruns it, recomputes every exact row, and is the single
`limited_descriptive_admission` chokepoint.

All seven metric identities now own their exact instrumentation status, basis,
predicate provenance, measurement variant, known-fact shape, scope, source-ref
set, and threshold shape. Primitive adoption, fail-closed fidelity, and
audience enforcement are `instrumented/not_established/unknown`; surface
closure is `instrumented/recomputed/zero|measured`; evidence coverage is
`instrumented/recomputed/incomparable|zero|measured`; machine parity is
`instrumented/not_established/missing`; honesty is
`protocol_seam_only/not_established/missing`. Every C12 threshold remains
`not_established` with null comparator, value, unit, and source. The surface
zero is now a subordinate closed recomputation, never a cited or independently
reconciled fact.

The report and snapshot have distinct Core manifest producers. Only the
snapshot admits the matched rows; it binds the raw report artifact/digest,
validator identity and implementation ref, Python and `jsonschema` versions,
JSON Schema dialect, executable/script/stdout digests, fixed environments,
complete owner/schema refs, admission ref, and exact measurements. Its actual
revision comparator walks every bound owner, schema, validator, producer, and
admission path. It derives the enclosing worktree prefix with `git rev-parse
--show-prefix` before requesting the recorded bytes, so product-relative bound
paths resolve as `policy-engine/<path>` at this worktree root. It records
`revision_resolvable` only for current bytes equal to the recorded Git blobs;
otherwise it records `source_hash_bound_only` and the exact non-revision paths.
The behavioral witnesses prove one clean product-relative path resolves and one
absent path degrades. This is source resolvability, not a historical rerun or
cross-snapshot replay consumer.

### Complete repair census

The complete backend denominator is **2,560 tracked recursive Python paths,
including `__init__.py`**. It was measured with the executable command
`git ls-files -- ':(glob)src/polisyos/**/*.py' | wc -l`; the case-insensitive
literal matcher is `health_metric`, measured with
`git grep -i -l -e 'health_metric' -- ':(glob)src/polisyos/**/*.py' | wc -l`.
It has exactly **13 path hits**, all classified:

1. `src/polisyos/fabric/_adapters/observability.py` is generic runtime
   telemetry emission.
2. `src/polisyos/runtime/http/services/governed_projection_validation_worker.py`
   validates the separate Layer-3 health-ledger projection.
3. `src/polisyos/runtime/http/services/governed_projections.py` projects that
   separate Layer-3 owner.
4. `src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py`
   owns the G0 health-ledger inventory.
5. `src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py`
   owns the G1 delta.
6. `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py` owns
   the G2 delta.
7. `src/polisyos/runtime/quality/proving_ground/proof_carrying_analytics_search.py`
   owns the G3 delta.
8. `src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py`
   consumes the G4 promotion delta.
9. `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`
   owns the G5 dependency snapshot/delta.
10. `src/polisyos/runtime/quality/proving_ground/region_widening.py` owns the G7
    widening delta.
11. `src/polisyos/runtime/quality/proving_ground/health_metric_governance.py`
    owns G8 health-metric governance.
12. `src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py` owns
    the GL delta.
13. `src/polisyos/runtime/quality/required_reference_resolver.py` resolves the
    cross-stage Layer-3 health references.

They are one telemetry adapter, two projection/validation consumers, nine
Layer-3 stage owners/consumers, and one cross-stage reference resolver; none is
the seven-metric C11 frontend instrument. The hidden-aware tracked-plus-
untracked dashboard denominator is **1,007** relevant `.ts`, `.tsx`, `.mjs`,
or `.py` paths, measured with
`rg --files --hidden -g '*.ts' -g '*.tsx' -g '*.mjs' -g '*.py' apps/runtime-dashboard | wc -l`.
The case-insensitive C11 matcher
`rg -i -l --hidden -g '*.ts' -g '*.tsx' -g '*.mjs' -g '*.py' 'ATLAS_HEALTH_METRIC_IDS|polisyos\\.atlas\\.health[_-]metric|primitive_adoption|surface_missing_closure|machine_twin_parity' apps/runtime-dashboard | wc -l`
returns exactly **3** paths: the C11 typed owner, its focused test, and the
existing persistence adapter:

1. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts` — typed
   C11 contract/measurement owner;
2. `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts` —
   focused C11 semantic and adversarial consumer; and
3. `apps/runtime-dashboard/scripts/persist_atlas_evidence.py` — existing
   bounded persistence/admission bridge.

The MJS is a semantics-free fixed launcher and the new Python helper is the
single shared canonical-source validator; neither is a C11 lexical match under
this deliberately narrower matcher. C07/Core remain the sole CAS and receipt
owners; no second receipt, evidence kind, hash implementation, or CAS was
added.

### Frozen verification receipts and nonreceipts

The controlling root test-extra bootstrap receipt was
`uv run --frozen --extra test python -I apps/runtime-dashboard/scripts/validate_atlas_health_sources.py --corruption-probes`.
It installed 14 locked packages and left no tracked diff; because that command
has no `--offline`, it is not an offline claim. Its focused C11 receipt passed
21/21 in 15.25 seconds (14.20 seconds in Vitest tests), replacing the earlier
19/19 and temporary-site-path receipts at that time; the later 22/22
replay-prefix receipt below is now controlling.

An earlier fresh focused rerun used
`corepack pnpm exec vitest run src/test/evidence/atlasHealthMetrics.test.ts --maxWorkers=2 --reporter=default`
and passed 1/1 files, **21/21 tests**, in 16.22 seconds (15.36 seconds tests;
16.85 seconds wall). It includes the complete **nine** canonical-owner
corruption probes, duplicate readiness/adoption identity rejection, mixed-state
surface binding, a real filesystem Core CAS round trip, report/snapshot lineage
mutations, the fake-PATH Node witness, the real `NODE_OPTIONS --require`
preload witness, and the revision-binding witness. The importer/blast-radius
rerun used the four C07/C08/C12/C11 files with two workers and passed 4/4 files,
**57/57 tests** in 15.93 seconds (16.25 seconds tests; 16.50 seconds wall): 12
C07, 16 C08, eight C12, and 21 C11.

The app `tsconfig.app.json` check passed with no diagnostics in 12.78 seconds;
scoped ESLint passed with zero warnings in 8.54 seconds; Python bytecode
compilation passed. `uv run --frozen --extra lint --extra test python -m ruff
check apps/runtime-dashboard/scripts/persist_atlas_evidence.py
apps/runtime-dashboard/scripts/validate_atlas_health_sources.py` reported `All
checks passed!`; this command provisioned its lint tooling and is not an offline
claim. `uv lock --check --offline` resolved the locked 416-package graph in
23 ms.

The separate fresh-temporary-filesystem CAS smoke exited zero and verified both
artifacts. The exact run-specific refs were report
`sha256:73ac27704c914c4e48d4bf140b20154648a4e86f84fb7526359553a8561cb0cf`
and snapshot
`sha256:561cb9b0c36b5a4ec1e54233668b2be6ed41dda31acbc67aed4e8d697f5ac22b`;
the lineage role was exactly `measurement_report`, metric count seven, report
authority `candidate_only`, snapshot authority
`limited_descriptive_admission`, both CAS verifications true, and capability
`implemented_but_not_orchestrated` with `consumer_missing` and
`surface_missing`. Because the ten-path candidate is dirty/untracked and the
bound `pyproject.toml` and `uv.lock` are included, the honest replay result is
`source_hash_bound_only` with **17 checked paths and six non-revision C11
paths**. This earlier CAS receipt is superseded by the replay-prefix repair
receipt below.

### Replay-prefix repair receipt

The worktree-root replay defect was reproduced from the `policy-engine` cwd:
`git show HEAD:apps/runtime-dashboard/scripts/persist_atlas_evidence.py` exits
128, while `git show HEAD:policy-engine/apps/runtime-dashboard/scripts/persist_atlas_evidence.py`
exits 0. The generic revision-byte comparator now derives that prefix rather
than treating product-relative bindings as worktree-relative paths. Its
behavioral witnesses prove `CONTRIBUTING.md` is `revision_resolvable` at HEAD
and an absent bound path is `source_hash_bound_only`.

The fresh temporary-filesystem CAS receipt after that repair is report
`sha256:a94a08810b1d3682f982af1b2aea36ed5a9b3d594d7ecdbbb048041a2ec5b3c5`
and snapshot
`sha256:8f32d9a252aaf46eff39d7c09bf8bfa03b0e1913ad0e2e4a9de1503f31c23257`.
It checks 17 bound paths and returns `source_hash_bound_only` for exactly six:
`apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts`,
`apps/runtime-dashboard/scripts/measure_atlas_health.mjs`,
`apps/runtime-dashboard/scripts/validate_atlas_health_sources.py`,
`apps/runtime-dashboard/scripts/persist_atlas_evidence.py`, `pyproject.toml`,
and `uv.lock`. The status remains limited descriptive admission with
`implemented_but_not_orchestrated`, `consumer_missing`, and `surface_missing`;
this repair changes source resolvability only.

The fresh focused C11 rerun passed 1/1 file and **22/22 tests** in 18.28
seconds (17.29 seconds tests; 18.94 seconds wall). The C07/C08/C12/C11 importer
rerun, restricted to two workers, passed 4/4 files and **58/58 tests** in
18.03 seconds (18.44 seconds tests; 18.61 seconds wall): 12 C07, 16 C08,
eight C12, and 22 C11. `tsc -p tsconfig.app.json --noEmit`, scoped ESLint,
Python compilation, Ruff, and `uv lock --check --offline` all passed; none of
those checks is a browser, full-suite, or orchestration receipt.

Historical provisioning nonreceipts remain evidence, not green receipts. The
post-temporary-`.pth`, pre-provision isolated-Python attempt failed with
`ModuleNotFoundError` for `jsonschema`; the temporary ignored site-path file was
removed before freeze and is not a delivered path. Separately,
`uv sync --offline --frozen --extra test` could not provision the already
locked `rpds-py` transitive because its Python 3.14 wheel was absent from the
offline cache. The later root `uv run --frozen --extra test ...` bootstrap
receipt above supersedes neither failure as history, but it supplies the
test-extra prerequisite for C11 acceptance. A fresh environment must bootstrap
the locked `test` extra before invoking the isolated validator.

No full Vitest, full three-project typecheck, full lint, build, browser,
Storybook, page-a11y, journey, visual, dev server, architecture guardrail,
contended governed artifact, readiness/adoption owner, `src/polisyos/**`,
Russian locale, DS5/GY path, C10 implementation, C18 path, visual baseline, or
DS8 print byte ran or changed. Those lanes remain nonreceipts. C11 stays
`implemented_but_not_orchestrated`; its consumer and governed surface remain
missing, and no aggregate PASS, stable grant, blocking authority, or C10-R1
mechanism exists.

## DS6-C18 deterministic visual-fixture stage — 2026-08-16

Entry was clean and branch-attached at C11 landing `dec77a050` on
`codex/atlas-ds6-evidence-workflow`, 21 commits ahead of the bound base. C18's
immutable cap remains six paths: the visual spec, the three named DS6 PNGs,
this plan, and this journal. This stage intentionally changes only the spec and
two records. The three DS6 PNGs and the DS8-owned print PNG remain
byte-unmodified; comparator, tolerances, product, backend, and runtime API
semantics are outside this stage.

### Pre-fixture authority and complete denominator

The already-run baseline command from `apps/runtime-dashboard` was exactly:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --output=../../_build/apps/runtime-dashboard/ds6-c18-01-pre-fixture-full
```

The no-update run returned 14 passed / four failed across all 18 screenshot
tests in `real 117.26` seconds. `uptime` before was load averages
`3.97 5.26 4.55`; after was `6.64 5.98 4.93`. The supplied ceiling was 2,400
seconds and the exact regime was
`shared_host_uncontrolled_external_load_one_ds6_heavy_parent`. The output root
is `../../_build/apps/runtime-dashboard/ds6-c18-01-pre-fixture-full`. This is a
complete one-run live mismatch census at `dec77a050` under that host regime;
it does not prove repeat stability, authorize a snapshot update, or describe
post-fixture behavior. The four RED identities were
`evidence-promotion-focus.png`, `dark-evidence-fabric.png`,
`mobile-command-center.png`, and DS8-owned `run-detail-a4-print.png`.

A Node script read the complete visual spec and snapshot directory rather than
sampling search output. Its path denominator was one
`apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`; its file-type
denominator was all `.png` files in the adjacent `-snapshots` directory. It
returned exactly 18 screenshot calls and exactly 18 PNGs with these complete
call identities:

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

The corresponding baseline directory contained the same 18 stems with the
platform suffix `-chromium-darwin.png`; there was no missing or extra PNG.
The C18 witness is a nineteenth Playwright test but adds no screenshot call,
so the governed image denominator remains 18/18. Before installing the helper,
the targeted owner grep was:

```bash
rg -n "VISUAL_CLOCK_TIME|meta\\.generated_at|evidence-context|promotion/candidates|control/data/connectors" apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts
```

It returned only the visual-clock constant, the existing connector APIRequest
fetch, the two existing artifact timestamp substitutions, and the browser
clock installation. It returned no response-`meta.generated_at` binding for
run evidence-context, promotion candidates, or connectors.

### RED-first behavioral witness and fixture

The witness fetches all three real response paths through `page.evaluate` in
the browser: the run evidence-context URL built from
`fixtureMetadata.core_run_id`, `/api/v1/control/data/promotion/candidates`, and
`/api/v1/control/data/connectors`. It asserts each returned
`meta.generated_at` equals the existing `VISUAL_CLOCK_TIME`. Before the shared
helper existed, the exact RED command was:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'binds visual response metadata to the visual clock$' --output=../../_build/apps/runtime-dashboard/ds6-c18-02-witness-red
```

It failed 1/1 for the intended missing behavior: received
`2026-08-16T11:43:33.955264Z`, expected
`2026-01-01T00:00:00.000Z`. `/usr/bin/time` recorded `real 12.36`, `user
5.29`, `sys 0.74`; before/after loads were `2.91 4.74 4.60` and
`3.25 4.72 4.60`. The output root was exactly
`../../_build/apps/runtime-dashboard/ds6-c18-02-witness-red`.

The minimal implementation adds one shared visual response-metadata route
fixture, installed in `beforeEach` before navigation. It registers only the
three exact path patterns and accepts only GET; any nonmatching method/path
falls through. Each handler calls `route.fetch()` for the real response,
requires an object `meta` and a nonempty string `meta.generated_at`, then
fulfills a copied payload whose sole value change is
`meta.generated_at = VISUAL_CLOCK_TIME`. It does not widen any visual
comparator or tolerance.

The exact GREEN command was the same except for its unique output root:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'binds visual response metadata to the visual clock$' --output=../../_build/apps/runtime-dashboard/ds6-c18-03-witness-green
```

It passed 1/1 in Playwright's 15.9 seconds; `/usr/bin/time` recorded `real
16.57`, `user 6.47`, `sys 1.33`. Before/after loads were `3.13 4.53 4.53`
and `3.64 4.57 4.54`; output was exactly
`../../_build/apps/runtime-dashboard/ds6-c18-03-witness-green`. Both targeted
runs used the supplied 2,400-second ceiling and the baseline's exact
`shared_host_uncontrolled_external_load_one_ds6_heavy_parent` regime.

The pre-reanchor blast expectation remains the same complete set: the 14
baseline-green identities stay green, the three DS6-attributed identities stay
RED until their separate snapshot generation, and DS8's print identity stays
RED and byte-unmodified. That is explicitly an expectation, not a post-fixture
receipt; the full post-fixture no-update lane is not run in this stage. No
snapshot generation, targeted PNG update, full visual rerun, DS8 print repair,
comparator/tolerance change, product/backend change, staging, or commit occurs.

Pattern closeout for this stage: P08 separates production response time from
the visual test clock; P29/P33 are satisfied by a RED-first behavioral witness
over real route responses rather than authorial markers; P35 is satisfied by
the complete one-spec/18-call and one-directory/18-PNG census. Snapshot
re-anchor and full-envelope verification remain open by design rather than
being reported as green.

The lightweight source-freeze checks then passed: focused Vitest over
`src/test/contracts/visualRegressionHarness.test.ts` and
`src/app/surfaces/visualFixtureHarness.test.ts` returned 2/2 files and 6/6
tests in 2.55 seconds; scoped ESLint over the visual spec returned zero
warnings; scoped Prettier reported the spec formatted; and
`tsc -p tsconfig.app.json --noEmit` returned no diagnostics. The static visual
harness behaviorally re-read the spec and snapshot directory and kept the
18-call/18-PNG relation one-to-one. These are source checks, not browser-image,
post-fixture blast, snapshot-generation, or stability receipts.

## DS6-C18 re-anchor and closeout continuation — 2026-08-16

This continuation supersedes only the earlier stage's open-status statements;
it does not rewrite their historical strength. The same declared cap remains
six paths: the visual spec, the three named DS6 PNGs, this plan, and this
journal. The DS8 print PNG, visual comparator/configuration, product sources,
backend sources, and runtime API remain outside the write set.

All browser runs below used one DS6 heavy parent, the supplied 2,400-second
ceiling, and regime
`shared_host_uncontrolled_external_load_one_ds6_heavy_parent`. Their common
literal prefix, from `apps/runtime-dashboard`, was:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium
```

The suffix was the selection/update option, if any, plus the exact `--output`
root named in the table. A GREEN update run is generation, never verification;
a missing load endpoint is a timing-substrate nonreceipt, never an invented
sample. No run was killed and no run exceeded the ceiling.

| Run/output suffix | Selection and true-strength receipt | `real` seconds | Load before -> after |
| --- | --- | ---: | --- |
| `04-post-fixture-full` | full no-update RED, 15/19; exact four screenshot REDs remained evidence promotion, dark evidence, mobile command center, and DS8 print | 70.32 | `2.74 3.52 4.05` -> `3.99 3.73 4.07` |
| `05-targeted-update` | three target tests GREEN under `--update-snapshots`; generation only, later superseded | 30.05 | `3.91 3.72 4.07` -> `4.18 3.77 4.06` |
| `06-targeted-no-update` | RED 1/3: mobile green, evidence and dark RED because wall-clock freshness lag advanced | 40.69 | missing pair: timing sample nonreceipt |
| `07-clock-red` | clock witness RED 0/1: `clock.install()` produced `2026-01-01T00:00:00.917Z`, not the fixed instant | 26.63 | `4.77 4.30 4.24` -> `7.35 5.00 4.50` |
| `08-clock-green` | same witness GREEN 1/1 after `page.clock.setFixedTime()` | 13.76 | `6.22 4.87 4.46` -> `5.67 4.83 4.46` |
| `09-post-clock-full` | full no-update RED 16/19; only evidence, dark, and DS8 print remained RED | 61.58 | `2.36 3.15 3.77` -> `3.15 3.25 3.76` |
| `10-authoritative-update` | target GREEN 3/3 under `--update-snapshots`; authoritative generation, not verification | 25.73 | `3.06 3.23 3.75` -> `3.40 3.29 3.75` |
| `11-authoritative-targeted-no-update` | target GREEN 3/3 on then-current source; later helper changes superseded it | 29.94 | `3.40 3.29 3.75` -> `8.53 4.57 4.19` |
| `12-final-full-no-update` | full RED 17/19: evidence promotion oscillated and DS8 print remained RED | 59.26 | before `8.08 4.55 4.18`; immediate after missing, so timing pair nonreceipt |
| `13-layout-diagnostic` | 6/6 diagnostic-only run; not a closure or screenshot receipt | 37.46 | pair not captured: timing sample nonreceipt |
| `14-data-intelligence-diagnostic` | 1/1 diagnostic-only run; not a closure receipt | 23.48 | before `5.01 4.79 4.43`; immediate after missing, so timing pair nonreceipt |
| `15-catalog-readiness-green` | evidence-promotion readiness condition GREEN 1/1 | 15.00 | `4.09 4.57 4.38` -> `3.41 4.37 4.31` |
| `16-final-targeted-three` | interim target GREEN 3/3; later generic-helper source change superseded it | 27.72 | `4.12 4.44 4.34` -> `6.43 5.00 4.55` |
| `17-stability-window-red` | test returned GREEN 1/1 because Playwright assertions auto-waited; invalid RED design and therefore a behavioral-witness nonreceipt | 11.62 | pair not captured: timing sample nonreceipt |
| `18-stability-window-red` | corrected direct witness RED 0/1: received `initial`, expected `settled` | 13.06 | `3.22 4.15 4.28` -> `3.33 4.12 4.26` |
| `19-stability-window-green` | generic quiet-window witness GREEN 1/1; later review showed it did not yet prove the full post-mutation interval and used wall time, so it was superseded | 12.05 | `2.83 3.95 4.19` -> `2.75 3.84 4.15` |
| `20-final-targeted-three` | target GREEN 3/3; superseded by the monotonic-clock delta | 19.87 | `2.69 3.81 4.13` -> `3.12 3.80 4.12` |
| `21-final-full-no-update` | full RED 19/20, sole DS8 print; superseded by the monotonic-clock delta | 64.03 | `2.95 3.75 4.10` -> `4.01 4.01 4.17` |
| `22-monotonic-stability-green` | strengthened quiet-window witness GREEN 1/1 on current source | 17.18 | `5.99 4.53 4.33` -> `4.88 4.39 4.28` |
| `23-final-targeted-three` | current-source target GREEN 3/3; functional receipt valid, but missing pre-load makes its timing sample incomplete | 26.67 | before missing; after `4.02 4.15 4.19` |
| `24-final-full-no-update` | controlling complete RED 19/20; sole failure DS8 `run detail A4 print` | 68.48 | `4.02 4.15 4.19` -> `4.97 4.35 4.26` |
| `25-final-targeted-three-with-load-pair` | controlling target GREEN 3/3 on current source | 29.39 | `4.97 4.35 4.26` -> `6.04 4.67 4.37` |

Run 22 and the two controlling final runs logged a nonfatal Prometheus exporter
bootstrap warning (`Errno 48`, address already in use). The visual web server
continued, every selected test executed, and Playwright emitted terminal
results; the exporter is therefore an unavailable ancillary telemetry
nonreceipt, not a visual-test failure or a killed lane.

### Root-cause and property record

The response fixture alone was necessary but not sufficient. First,
`page.clock.install()` fixed the initial time and then advanced `Date`, while
the UI computes connector freshness as current wall time minus the frozen
response timestamp. Run 07 proved the drift; `page.clock.setFixedTime()` fixed
wall time while leaving timers live, and run 08 proved both properties.

Second, run 12 exposed a test-harness readiness defect. Its final retained
evidence actual was byte-identical to the 8,529 px baseline, but an earlier
8,497 px sample made the comparator RED. The shorter image was an exact pixel
prefix; only a 32 px tail was absent. The complete trace placed the old
`waitForStableRender` return about 102 ms before the catalog GET. The 250 ms
debounce in `DataIntelligencePanel` then enabled the catalog request and added
one 16 px knowledge-weave line plus its 16 px gap. The final evidence test
registers the exact catalog response wait before navigation, requires a 2xx
typed response, observes response-derived text inside the real knowledge panel,
and only then enters the generic render-stability check.

P38 is explicit here: the required property is a continuously settled render;
the prior implementation tested one equal signature pair. The debounced
catalog mutation is the measured divergent case. The generic repair samples
the complete markup/font/bounds signature every 50 ms, uses runner
`performance.now()` for elapsed time, resets the quiet clock on every observed
change, and requires 500 ms continuously quiet. The twentieth Playwright test
mutates real text and height after 150 ms, records the browser monotonic
mutation time, and asserts both the final DOM and at least 500 ms elapsed after
that mutation. Run 18 is the meaningful RED; run 22 is the current-source
GREEN. Run 17 is retained as the exact test-design nonreceipt rather than
rounded into RED evidence.

The three-response fixture remains exact: GET run evidence-context for
`fixtureMetadata.core_run_id`, GET promotion candidates, and GET connectors.
Each handler fetches the real response, requires object `meta` and nonempty
string `meta.generated_at`, then shallow-copies only that field to
`VISUAL_CLOCK_TIME`. The metadata witness fetches all three through the real
browser path. There is no comparator/tolerance/product/API relaxation.

### Re-anchor authority and current visual envelope

The exact authoritative generation command was:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --grep '(evidence promotion focus|dark evidence fabric|mobile command center)$' --update-snapshots --output=../../_build/apps/runtime-dashboard/ds6-c18-10-authoritative-update
```

Generation is not verification. The current-source closure sequence, followed
by the timing-complete target repeat, was:

```bash
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --grep '(evidence promotion focus|dark evidence fabric|mobile command center)$' --output=../../_build/apps/runtime-dashboard/ds6-c18-23-final-targeted-three
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --output=../../_build/apps/runtime-dashboard/ds6-c18-24-final-full-no-update
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/_build/apps/runtime-dashboard/.venv-online UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas-ds6/policy-engine/src /usr/bin/time -p corepack pnpm exec playwright test --config=playwright.visual.config.ts --project=chromium --grep '(evidence promotion focus|dark evidence fabric|mobile command center)$' --output=../../_build/apps/runtime-dashboard/ds6-c18-25-final-targeted-three-with-load-pair
```

The target returned 3/3. The complete spec returned 19/20 across 20 tests and
18 screenshot identities. Its sole RED was DS8-owned `run detail A4 print`:
724x2113 expected, 770x13229 actual, exactly 691,742 differing pixels at ratio
0.07 against `maxDiffPixels: 100`. That exact RED is the C13/DS8 result, not a
C18 failure or repair permission. It proves the C18 fixture introduced no
fourth moved baseline.

The complete one-spec/one-directory P35 census is now 20 Playwright tests, 18
`toHaveScreenshot` calls, and the same 18 distinct committed PNG stems—no
missing, extra, or duplicate baseline. Final authorized baseline artifacts are:

| Baseline | Dimensions | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| evidence promotion focus | 1094x8529 | 1,994,425 | `03e69c28aeda2baf2caca233b050c31193b0b327f269ef32cf27c3f34a73e667` |
| dark evidence fabric | 1094x6521 | 873,550 | `f5a8c3257cb070bc276827c1cefcc6fc9f85864af20f3f56d531d394fcc0d98f` |
| mobile command center | 369x3680 | 326,520 | `23cab2cb08f15b1ee668faf1de5a4a81a4ba2dc1ec214d29981c7b575a49557d` |

The DS8 print baseline remains 724x2113, 231,141 bytes, SHA-256
`a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`,
and git blob `104ef3c896c3897de48252409494b867b0820f66`. The visual config remains
byte-identical to HEAD at SHA-256
`869a74240ea22ad7cdf93a296d8aaabc6ee20f5201e86d62e2a554dac6c4e15f`;
all five existing `maxDiffPixels: 100` print comparators are unchanged.

### Duplication, capability strength, package, and remaining order

The complete adjacent visual owner census has one screenshot call for each of
the 18 PNG identities; C18 creates no duplicate snapshot owner. The complete
tracked dashboard CSS denominator remains 13 files and exactly two active
`attr(href)` emitters: `src/styles/print.css:84` and `src/styles.css:1611`.
They remain `duplicate_active`, DS8/team-design owned, with `styles.css` the
registered strangle target. C18 does not edit either emitter or the DS8 print
baseline.

C18 is a deterministic test-harness repair plus independently executed visual
evidence, not a new governed C07 receipt or orchestration bridge. Its ignored
Playwright outputs are execution evidence, not CAS-persisted artifacts. No C07
capture, C08 orchestration, C10 reconciliation, readiness-ledger transition,
or public surface is inferred from a green screenshot.

The contended package remains **ready**: C03, C04, and C06 are three executable
append-only transitions after a fresh owner/hash reread when the register
window opens; C13 is an exact held `NO WRITE` until DS8 repairs print,
independent semantic non-overlap is established, and two stable no-update A4
captures exist. There is no C10-R1 projection delta.

The post-session blocked/order list is exact:

- C03, C04, and C06 wait on the register-family release; C03's green-suite gate
  and C06's honest 7/7 contrast gate are already discharged.
- C10-R1 requires its own clean-tree session using per-claim disposition/basis;
  the refused aggregate reconciled Boolean remains forbidden.
- C13's governed transition waits on DS8's print repair and the named semantic
  plus two-capture gates.
- C14 is last.
- C11 is landed as `implemented_but_not_orchestrated`; its honesty content,
  observations, and every threshold remain `not_established`, not a blocker on
  the six current descriptive measurements.

The final static/fence/read-back receipts follow after the frozen six-path
candidate is rerun and independently reviewed. No claim below this line is
pre-authorized by the browser receipts above.

### Frozen-source and fence receipts

After the final monotonic quiet-window source freeze, four independent source
checks ran in parallel because they share no browser/server/fixture process:

- focused Vitest over `visualRegressionHarness.test.ts` and
  `visualFixtureHarness.test.ts`: 2/2 files and 6/6 tests GREEN, 204 ms test
  body, Vitest duration 4.70 s, `real 5.81`;
- scoped ESLint over the visual spec: exit 0, `real 4.80`;
- scoped Prettier check over the visual spec: exit 0, `real 1.22`;
- `tsc -p tsconfig.app.json --noEmit`: exit 0, `real 24.81`.

`git diff --check` returned exit 0. The corrected read-only TypeScript-AST and
filesystem census returned exactly six dirty paths, 20 `test(...)` calls, 18
literal `toHaveScreenshot(...)` calls, 18 unique names, and 18 matching PNG
files. It separately walked all 13 tracked dashboard CSS files and returned
only `src/styles/print.css:84` and `src/styles.css:1611` as `attr(href)`
emitters. The scoped forbidden-path diff was empty for the Russian catalog,
visual config, DS8 print baseline, `src/polisyos/**`, and every named
register/report/status/readiness/baseline-manifest owner.

Two earlier census command attempts are explicit tooling nonreceipts. The
first trimmed the leading porcelain status byte and therefore misparsed one
path; the second assumed `git ls-files` used the same prefix semantics with and
without a pathspec and therefore found zero CSS files. Both exited before
emitting a complete census and changed no file. The corrected command retained
the exact same six-path source set and produced the denominator above; neither
failed harness attempt is treated as product RED or evidence.

Pre-commit readback was branch-attached at
`dec77a050e3ddefc647e46cf4fc053c84c008d97`, 21 commits ahead of
`c1a89b6cf`, with exactly the six declared C18 paths modified and no untracked
or staged path. Independent review and the post-commit branch readback remain
the only outstanding landing gates.

## DS6-C18 bounded-fixture closeout — 2026-08-18

This continuation is the active C18 record. It supersedes the preceding
continuation's current-mechanism, current-census, authoritative-generation,
controlling-envelope, and ready-to-land statements without rewriting any
historical run. C18 is **verified and ready to land**; its commit and
post-commit branch readback are pending.

The exact cap-6 candidate is:

1. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`
2. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/evidence-promotion-focus-chromium-darwin.png`
3. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/dark-evidence-fabric-chromium-darwin.png`
4. `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/mobile-command-center-chromium-darwin.png`
5. `docs/plans/active/atlas-slices/DS6-evidence-workflow.md`
6. `docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md`

The visual contract-harness experiment was restored to HEAD and is not in the
candidate. The frozen visual-spec SHA-256 is
`9b634763d8708e0e00d20998e0928f43ad6157b7c0cd7ec690b1ff20d2ae9361`.
The complete source/filesystem census is **19 Playwright tests**, **18 literal
`toHaveScreenshot` calls**, **18 unique literal screenshot names**, and **18
PNG files**. Independent source reviews are CLEAN. No C18 commit SHA exists
yet; recording one before the landing readback would be an invented receipt.

### Final mechanism and refused mechanism

The final mechanism is bounded fixture determinism. One fixture registers only
the exact GET run-evidence-context, promotion-candidates, and connectors
routes. Each handler calls `route.fetch()` for the real response, requires an
object `meta` and nonempty string `meta.generated_at`, and fulfills a copied
payload whose only changed value is `meta.generated_at = VISUAL_CLOCK_TIME`.
`page.clock.setFixedTime()` freezes wall time while live timers continue. The
browser route/clock witness fetches all three real responses. The promotion
capture registers the exact catalog response before navigation, validates its
typed result, and observes response-derived readiness copy. Playwright's
direct `toHaveScreenshot` remains the canonical raster comparator. Comparator,
threshold, tolerance, production response, API contract, and DS8 print bytes
are unchanged.

The sampled/event/prototype/compositor-stability gate is **REFUSED**. This is a
P31/P38 class finding, not a collection of missing hook instances: JavaScript
activity is a proxy for compositor pixels and cannot prove the raster property.
The evidence accumulated in order:

- the sampled DOM signature missed a 250 ms asynchronous mutation;
- event and prototype variants missed WAAPI construction, `MediaList`,
  computed-style effects, aliased raw capture, and retained-proxy cleanup;
- an observer that ended before `toHaveScreenshot` did not observe the
  screenshot transaction, while moving it around the matcher still supplied
  no discriminator for compositor-only or browser-internal raster change.

Adding another hook would repeat the refused mechanism. The final source
therefore removes the generic gate and its twentieth test, restores the visual
contract harness to HEAD, fixes only the known drifting fixture inputs, and
leaves pixel equality to the real Playwright comparator.

### Preserved experimental receipts and nonreceipts

Runs 01–25 above retain exactly their historical strength. In particular, run
17 remains a behavioral-witness **nonreceipt**: Playwright assertion autowait
made the proposed RED test GREEN without exercising the break. It is neither a
RED nor evidence for the refused gate. Runs 26–34 are preserved below as
noncontrolling mechanism exploration; none authorizes the final PNGs:

| Run/output suffix | True-strength receipt | `real` seconds | Load before -> after |
| --- | --- | ---: | --- |
| `26-event-gate-red` | RED: sampled gate returned 460 ms against required >=500 ms | 15.58 | `2.87 3.24 3.00` -> `3.48 3.36 3.05` |
| `27-event-gate-green` | interim event-gate GREEN 1/1; later structural review superseded the mechanism | 13.51 | `3.14 3.75 3.47` -> `2.99 3.67 3.45` |
| `28-structural-review-red` | helper/tooling **nonreceipt**: `expect: Property 'then' not found`; the async helper accidentally exposed Playwright's expectation proxy to Promise assimilation, so no intended property was measured | 12.38 | before `2.20 2.46 2.87`; after missing, timing pair nonreceipt |
| `29-structural-review-red` | RED: sibling-overlay mutation returned 408 ms against required >=500 ms | 12.62 | `2.63 2.49 2.84` -> `2.60 2.49 2.83` |
| `30-structural-review-green` | interim document-observer GREEN 1/1; later paint review superseded the mechanism | 15.07 | `2.25 2.42 2.80` -> `2.58 2.49 2.81` |
| `31-paint-review-red` | RED: canvas-only paint mutation returned 403 ms against required >=500 ms | 15.47 | `2.66 2.48 2.66` -> `2.80 2.52 2.67` |
| `32-paint-review-green` | interim enumerated-paint-hook GREEN 1/1; later completeness review superseded the mechanism | 16.27 | `2.50 2.47 2.64` -> `2.58 2.50 2.65` |
| `33-transaction-red` | RED: delayed stylesheet replacement settlement time was missing | 18.54 | `2.00 2.15 2.33` -> `1.65 2.06 2.29` |
| `34-transaction-green` | RED: transaction reported visual activity during screenshot emission | 17.21 | `2.11 2.15 2.20` -> `2.16 2.16 2.20` |
| `34b-transaction-green` | RED: `CSSRuleList` iteration was misclassified as visual activity | 17.27 | `2.60 2.25 2.22` -> `2.38 2.22 2.21` |
| `34c-transaction-green` | same `CSSRuleList` false-positive RED after the next repair | 17.33 | `2.47 2.24 2.22` -> `3.02 2.37 2.27` |
| `34d-transaction-green` | RED: quiet-window duration was 459 ms against required >=500 ms | 63.90 | before `1.93 2.20 2.21`; after missing, timing pair nonreceipt |
| `34e-transaction-green` | experimental witness GREEN 1/1; subsequent review refused the mechanism, so this is not admission or generation authority | 23.24 | `4.58 2.83 2.44` -> `3.88 2.88 2.47` |

Two command-design attempts also remain explicit tooling nonreceipts. A
Playwright invocation/configuration using unsupported `minWorkers` did not
exercise the intended browser property. A root-launched TypeScript AST command
could not resolve the app-local `typescript` package and emitted no complete
census. Neither is a product RED, timing sample, source-review receipt, or
permission to change the fixture. The two earlier porcelain/CSS census
nonreceipts recorded above likewise remain nonreceipts.

### Source-frozen generation and verification

Every final browser lane used supplied ceiling 2,400 seconds and regime
`shared_host_uncontrolled_external_load_one_ds6_heavy_parent`; the load triple
is the 1/5/15-minute average captured immediately before and after. No run was
killed and none exceeded its ceiling.

| Run/output suffix | True-strength receipt | `real` / `user` / `sys` seconds | Load before -> after |
| --- | --- | ---: | --- |
| `35-final-source-update` | targeted GREEN 3/3 under `--update-snapshots`; **authoritative generation only**, never verification | `38.50 / 39.94 / 5.28` | `2.00 2.32 2.37` -> `3.80 2.70 2.50` |
| `36-final-source-targeted-no-update` | targeted no-update GREEN 3/3; controlling target verification | `26.77 / 26.04 / 3.38` | `3.57 2.67 2.49` -> `3.93 2.81 2.55` |
| `37-final-source-full-no-update` | genuine full RED 17/19: scenario composer oscillated between 1094x453 and 1094x3877, and DS8 print remained RED | `103.86 / 167.83 / 22.25` | `3.71 2.82 2.55` -> `10.53 6.01 3.85` |
| `38-scenario-stability-diagnostic` | isolated scenario GREEN 1/1; diagnostic control, not a full-envelope receipt | `20.83 / 14.56 / 1.59` | `8.34 5.75 3.79` -> `6.47 5.51 3.76` |
| `39-final-source-full-no-update-rerun` | controlling full expected RED 18/19; sole failure DS8-owned `run detail A4 print` | `93.69 / 157.67 / 20.47` | `6.03 5.43 3.75` -> `6.62 5.74 4.03` |

Run 37 is not rounded away: it is a genuine RED whose extra scenario failure
did not reproduce in isolation or in the controlling full rerun. Run 39's sole
failure compared the expected 724x2113 DS8 print against actual 770x13229 and
reported exactly 691,791 differing pixels. Run 35 is the only authoritative
generation; run 36 verifies the three C18 targets; run 39 defines the final
visual envelope. The three re-anchored baselines remain:

| Baseline | Dimensions | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| evidence promotion focus | 1094x8529 | 1,994,425 | `03e69c28aeda2baf2caca233b050c31193b0b327f269ef32cf27c3f34a73e667` |
| dark evidence fabric | 1094x6521 | 873,550 | `f5a8c3257cb070bc276827c1cefcc6fc9f85864af20f3f56d531d394fcc0d98f` |
| mobile command center | 369x3680 | 326,520 | `23cab2cb08f15b1ee668faf1de5a4a81a4ba2dc1ec214d29981c7b575a49557d` |

The DS8 print baseline remains byte-unmodified at SHA-256
`a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`
and git blob `104ef3c896c3897de48252409494b867b0820f66`. Thus the fixture blast
radius remains the two evidence pages, while the re-anchor radius is those two
plus the C15-R1 mobile-copy baseline; no fourth DS6 baseline moved.

### Ready package, blocked order, duplication, and timing law

The four contended executable deltas remain **READY**. C03, C04, and C06 are
three append-only governed transitions once the register window opens, each
beginning with a fresh owner/hash readback. C13 is the fourth prepared delta
and remains exact `NO WRITE` until DS8 supplies its print repair, independent
semantic non-overlap, and two stable no-update captures. There is no C10-R1
projection delta.

The active blocked/order list is:

- C03, C04, and C06 wait on the register-family release; C03's green-suite and
  C06's honest 7/7 contrast gates are already discharged;
- C10-R1 requires its own clean-tree session under the per-claim
  disposition/basis vector; the refused single reconciled Boolean remains
  forbidden under the recorded PV-K01 analogy/ruling;
- C13 waits on the DS8 repair, semantic result, and two captures;
- C14 is last.

C11 remains `implemented_but_not_orchestrated`. The honesty-comprehension
content, observations, and every threshold remain `not_established`; none is
silently collapsed into zero or a stable bar.

The standing duplication census remains the complete 13 tracked dashboard CSS
files and exactly two active `attr(href)` print emitters:
`src/styles/print.css:84` and `src/styles.css:1611`. They remain DS8-owned
`duplicate_active` debt; `styles.css` is the registered strangle target. The
18 screenshot names remain one-to-one with the 18 PNGs, so C18 creates no
duplicate snapshot owner.

The final frozen-source static wave is GREEN: focused Vitest over
`visualRegressionHarness.test.ts` and `visualFixtureHarness.test.ts` returned
2/2 files and 6/6 tests (`real 6.14`, 146 ms test body); scoped ESLint returned
exit 0 (`real 4.24`); scoped Prettier returned exit 0 (`real 1.39`); and the app
TypeScript project returned exit 0 (`real 19.68`). The independent TypeScript
AST/filesystem census recomputed 19 tests, 18 literal screenshot calls, 18
unique names, 18 PNGs, and exact one-to-one parity. `git diff --check` and the
protected-path diff were empty. These are source/fence receipts, not browser
or CAS evidence.

One duplication-command attempt was a tooling nonreceipt: it quoted the
newline-separated 13-file CSS list as one `rg` path and produced an I/O error.
The corrected complete command piped the same sorted `git ls-files`
denominator through `xargs rg`; it returned exactly the two emitters above.
An independent final review also first launched a policy-root pathspec from
the dashboard directory and therefore received an empty `CSS_COUNT`; its
policy-root retry reproduced 13 files and the same two emitters. Both failed
invocations changed nothing and supply no zero, count, or timing claim.
Another final review first used a nonexistent `e2e/visualRegressionHarness.test.ts`
path and Git object names without the monorepo's `policy-engine/` prefix; those
lookups errored and supplied no byte-identity receipt. Its corrected retry used
`src/test/contracts/visualRegressionHarness.test.ts` and
`HEAD:policy-engine/...`, reproducing the HEAD-identical harness SHA-256
`16199c3a1b9b3f869f65d7c0c714cc5d3f4ca9b1f0d1f405959de1f4808e86b6`
and DS8 print blob `104ef3c896c3897de48252409494b867b0820f66`.
The final receipt audit's optional owner-hash command also misspelled
`test_frontend_baseline_debt_manifest.py` with a hyphen, so that invocation
hashed only its first three inputs and supplied no eight-owner hash census.
The prior existence loop had already found all eight owners; the corrected
retry hashed all eight. The misspelled command changed nothing and is not an
owner-identity, package-readiness, or timing receipt.

Lint retains two measured regimes: cold **1,182.94 s** and warm shared-cache
**19.18 s**, a **62x** spread. A future ceiling is `2 x p95` of successful
runs in the matching regime, never a margin over the minimum; no timing sample
without its load/cache regime is promoted. C18's commit and post-commit branch
readback remain pending.

## DS6-C10-R1 per-claim readiness reconciliation entry — 2026-08-18

C10-R1 entered in isolated worktree `.worktrees/atlas-ds6-c10r1` on attached
branch `codex/atlas-ds6-c10r1-readiness-reconciliation` at current `main`
`f6374868456dc45bedf197e53701bd83d7921daa`. That base contains
`fa708f2bc656be52e62ff80a7ca2b112d89694a5` as an ancestor plus the docs-only
P39 registration. The root checkout's foreign
`src/polisyos/data_forge/read_api/catalog.py` modification remains untouched.

Under P39 the pre-entry measure is four mechanism paths: the new typed
reconciler, its semantic/CI test, the fixed launcher, and the existing
persistence/projection adapter. The mandatory companions held outside the cap
are this journal, the DS6 plan, and the reviewer reference. The mechanism is
therefore **4/16** and the complete candidate cut is **seven paths**. No
mechanism is split across commits to make the count smaller. The fresh
mechanism repair budget begins at **0/2**.

The C11 persistence boundary was remeasured against current `main`, not
inherited from the stopped attempt. The unchanged
`validate_atlas_health_sources.py` applied the complete canonical owners and
reported 261 readiness rows, five top-level `implemented` claims, 233 adoption
rows, and zero `stable` adoption claims. Relative to this executing C10-R1
session those four counts and the full-schema acceptance are `recomputed`.
The stopped `incomplete-pre-CAS-owner-invariant` finding was measured against a
pre-C11 persistence boundary; it remains evidence about that superseded
boundary, not a statement about the mechanism entered here. C10-R1 reuses the
landed C11 full-schema validator byte-for-byte and makes its result a
prerequisite at both producer and persistence admission.

The entered contract adds the three approved corrections. Cited execution
status and cited findings constrain one another in both directions, with
separate named reds for `pass` plus findings and for `fail`/`incomplete` plus
zero findings. Observation has three states: `observed`; `not_observed` only
after the canonical check completed negatively; and
`observation_unavailable` with its reason when owner, route, or harness
execution was unavailable. CI fails the last two under distinct codes. A
synthetic `stable` row is the mandatory negative control for the live zero-row
arm.

The CI exit code is the **only** place a conjunction over rows may exist. It is
a gate, not a claim. It is never written to an artifact, never given a field
name, never surfaced in the projection or the reviewer reference, and never
carried as a receipt outcome, provenance label, or aggregate status. The
required falsifier removes that exit-code calculation and compares artifacts;
any artifact-byte change would expose the refused aggregate under a new name.

Setup receipts and nonreceipts are explicit. `corepack pnpm install
--frozen-lockfile` installed the complete locked 1,211-package workspace from
the local store in 15.1 seconds and changed no tracked byte. The mandated
`uv sync --offline --frozen --extra test` created an isolated environment but
stopped because the `jaxlib==0.8.2` CPython 3.14 macOS wheel was absent from the
offline cache; that zero-source-byte attempt is a tooling nonreceipt. The
worktree then linked the existing DS6 repository-managed environment, whose
`jsonschema 4.25.1` installation let the unchanged source validator reproduce
the 261/5 and 233/0 owner counts above.

The pre-source focused baseline ran the C11 health test and canonical route
test: route behavior passed **10/10** and the combined run passed **31/32** in
25.28 seconds. The sole C11 failure expected dirty candidate paths
`pyproject.toml` and `uv.lock`, while the clean committed base honestly returned
an empty `non_revision_paths` list. No C10 path or tracked byte existed yet, so
this is a pre-existing clean-worktree C11 test nonreceipt, not a C10 result or a
consumed mechanism round. It is not repaired or excluded here without a scoped
ruling.

## DS6-C10-R1 mechanism review round 1 — 2026-08-18

The first mechanism candidate is preserved at
`b0e557c04b920aa8bb0d81b6c09dd198ad76bafc`. It changed exactly the four
predeclared mechanism paths, so the P39 measure remains **4/16**; the later
reviewer-reference commit `2120daeebbf72a5b130c4f6dcd0a05f19be24d09`
changes one mandatory companion outside that count. Focused pre-review
verification was 20/20 C10 semantic tests, 10/10 nested canonical route tests,
TypeScript app/tools projects exit 0, scoped ESLint exit 0, Ruff check exit 0,
and `git diff --check` exit 0. Those are candidate receipts, not review
closure.

Three independent read-only terra/luna reviews inspected the same frozen
candidate before any repair. They are one mechanism round, not three: a round
is a candidate-and-repair cycle, and no source changed between reviews. The
fresh counter is therefore **1/2 consumed**. Findings and classifications:

- Blocking, old class instance:
  `canonical-runner-provenance-and-single-intake-gap`. The operation bound the
  Node executable and canonical test source but not the resolved
  `node_modules/vitest/vitest.mjs` entry, version, and bytes.
- Important, old class instance: `non-bidirectional-status-contract`. The
  exported observed-basis schema allowed `observation_unavailable` with a
  passed assertion, and completed observations did not require a non-null
  runner-report digest.
- Blocking, new C10-R1 CI-boundary class: one discovered Vitest test looped
  across every row, creating a hidden conjunction before the Vitest/CI process
  exit. The artifact-independence test only proved non-mutation, not one
  separately discovered gate result per row.
- Important, new P37/P38 integrity class: both Node and Python validated one
  owner read, then enumerated a later loosely read owner using only cardinality
  equality. A same-cardinality post-validation mutation could therefore sever
  owner validation from the enumerated bytes.
- Important, new P32 class: `consistent_with_cited_report` accepted a
  hash-shaped artifact declaration and supplied facts without resolving and
  digesting actual cited bytes. Its CI ineligibility prevented authority
  escalation but did not make the basis name true.
- Important test finding, no mechanism-round effect: the owner corruption
  witness checked probe names after accepting any validator error, rather than
  proving the clean owner and each targeted property-specific red through the
  real validator.
- Minor test finding, no mechanism-round effect: aggregate absence used a key
  regex that could miss a differently named field; the repair must assert the
  complete allowed report/projection shapes.

The root pre-repair audit added one new P38 mechanism case to the same batch:
the route assertion name bound `/launch` (and its four siblings) but did not
bind the ledger title's declared target. A same-source, different-target title
could therefore stay `observed` against the real route test. The repair must
inspect the imported runtime route object and bind both declared endpoints as
well as the behavioral assertion.

The focused C10 suite and both reviewer diagnostic runs changed no tracked
byte. One reviewer repeated the known pre-existing C11 clean-tree nonreceipt:
the combined health test remained 31/32 because its revision-byte control
expected dirty `pyproject.toml`/`uv.lock` paths on a clean committed base. It is
not a C10 finding or round. No source repair had begun when this classification
was recorded.

## DS6-C10-R1 mechanism review round 2 — 2026-08-18

The round-1 repair candidate is preserved at
`2c1df24b4b8e19a8edf1ea6d2c1d000fc045f84d`. It still changed exactly the four
then-declared mechanism paths. Before review, the root focused run recomputed
27/27 C10 semantic witnesses in 25.18 seconds, the app TypeScript project
returned exit 0, scoped ESLint and Ruff returned exit 0, Python compilation and
`git diff --check` returned exit 0, and the branch readback found the stable
control plus the cited-byte and runtime-import bindings in that commit. These
are `recomputed` candidate receipts, not a reconciliation outcome.

Three independent read-only terra/luna reviews inspected that same frozen
commit before any next edit, so they form mechanism round 2 rather than three
rounds. Two reviewers independently falsified the exported CI helper by
supplying a shape-valid positive observation with fabricated runner/report
hashes; it returned green without resolving the closed persistence result.
This Blocking/Important mechanism finding consumes round **2/2**. It is an
instance of the already named
`canonical-runner-provenance-and-single-intake-gap`, now at a sibling CI
consumer, with P31/P32 authority-by-shape. The final permitted repair removes
that public claim-shaped intake and makes each CI case look up its row only in
the admitted projection produced by the fixed operation.

The same frozen review returned one Important P29/P33 test finding with no
mechanism-round effect: the synthetic `stable` test merely relabelled an
implemented negative, so deleting the actual stable producer arm would not
make it red. The final test must construct the row through the real stable
producer branch, make the real Python stable admission accept only its
unavailable basis, and then observe the distinct unavailable CI code.

The remaining review claims were classified before repair:

- Vite loader provenance was unbound. This is another instance of the existing
  canonical-runner provenance class and is accepted for repair, together with
  pre/post content checks for ordinary Node and Vitest mutation.
- Duplicate JSON object names were accepted by the reused canonical-owner
  validator. Python admission already rejects them in the ledger, but not in
  the schema; this is a new P32 ambiguous-source class and is accepted for a
  generic parser-level rejection plus a real `_load_json` witness.
- Treating any nonzero Vitest suite exit as every row's negative/unavailable
  fact is classified as a non-finding under the changed contract. A different
  test or cleanup failure is a conjunction over unrelated assertions; copying
  it onto each passing row recreates the refused aggregate. The owned per-row
  assertion status remains the fact.
- Persisting the raw Vitest suite report is classified as a non-finding. The
  report is internal runner transport; the exact extracted row fact, runner,
  test/source identities, and provenance are already content-addressed in the
  claim report. Persisting the suite-level `success` conjunction would violate
  the CI-only boundary.
- A malicious concurrent swap-and-restore of installed Node/Vitest bytes is
  outside the repository gate's threat model. The final repair detects
  ordinary between-phase mutation with pre/post hashes; host immutability
  remains an execution-regime assumption, never an artifact claim.

The reviewers' reported focused reruns were independently reconciled as 27/27
in 25.79 and 26.7 seconds; they are semantic-suite receipts, not a readiness
PASS. No review changed a tracked byte. Adding the already reused
`validate_atlas_health_sources.py` parser to the mechanism is declared before
touch under P39: the mechanism measure becomes **5/16**, the mandatory
companions remain three, and the complete cut becomes **eight paths**. The
budget is exhausted. Any Blocking or Important mechanism finding against the
next frozen candidate is classified as a third-round finding, preserved, and
stopped without another repair.
