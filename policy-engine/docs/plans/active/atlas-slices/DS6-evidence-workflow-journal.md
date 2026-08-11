---
plan_id: atlas-ds6-evidence-workflow
title: "DS6 - Evidence Workflow & Instrumentation Journal"
type: execution-journal
status: active_light_half
created: 2026-08-11
last_updated: 2026-08-11
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
  authorization, five-path cap, Russian ruling, and deferred 777/777/0
  expectation; actual whole-suite totals remain controlling and a mismatch must
  stop rather than be copied.
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
(36 ms test body). The focused denominator is 15; the deferred C03 expected
green transition is `777/777/0`, while the committed open state remains
`766/763/3` and the authorized whole-suite receipt still controls.

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

C07's new focused Vitest file induces one exact update to the consolidated C03
handoff. The committed open baseline remains 263 files and 766/763/3 tests. The
C01-R1-only historical expectation at this journal's line above was 263 files
and 777/777/0 tests (+11). The current post-C07 expected resolved receipt is
264 files and 789/789/0 tests (+1 file/+12 tests). The deferred plan now carries
that exact arithmetic; the eventual authorized whole-suite run remains the
authority, and any different measured total is a stop rather than a copied
expectation.

The frozen final allowed wave ran after both reviews and the record-only
arithmetic correction. Focused C07 Vitest passed 1/1 file and 12/12 tests in
749 ms (15 ms test body) with `--maxWorkers=2`. The three single-process Node
checks again exited 0 with `Contrast checks passed`,
`Reduced-motion checks passed`, and `Color-blind checks passed`. No prohibited
gate joined that wave. The final specification record-only recheck found and
closed the older `776` typo above; the journal now has one consistent
C01-only 777 expectation and one current post-C07 789 expectation.

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
the independent numeric axis is not adjudicated. That is the registered P38
property/marker mismatch.

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

The deferred resolved-Vitest expectation is now 265 files / 800 tests: baseline
263/766, plus C01-R1's 11 additional parity cases, C07's +1 file/+12 tests, and
C09's +1 file/+11 tests. This corrects the reviewers' provisional 265/798
arithmetic, which was computed against the superseded 9-test C09 draft. The
full suite was not run, so these are executable control totals, not a green
receipt; measurement during C03 replaces them if it differs.

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
immutable cap of 10. No cap changed. The deferred test arithmetic is unchanged:
the C07 file remains one existing 12-test file, while C09 remains one new
11-test file.

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
