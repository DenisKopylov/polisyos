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

The deferred resolved-Vitest expectation advances from the post-C09 265/800 to
266 files / 808 tests: C12 adds one file and eight tests. No full suite ran, so
this is expected control arithmetic for C03, not a receipt. C12 adds no
governed-row transition, no receipt kind, and no threshold/stable delta to the
deferred package.

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
later authorized run. The expected 266-file/808-test full-Vitest transition is
still control arithmetic and must be replaced by measurement when C03 runs.

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

## DS6-C15 — numeric-variable plural safety — 2026-08-12

### Entry, gate, and exact cap

`git status -sb` at entry reported a clean attached
`codex/atlas-ds6-evidence-workflow` at
`b15747da633fc52748460de0dea9cbb755140302`, eight commits ahead of
`c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`. C14 remains unentered behind its
heavy/contended predecessors; this continuation directly authorized already-
declared C15 out of sequence and no other cluster. Read-back before editing
measured exactly the five candidate paths declared by the plan: the parity owner, `en.json`,
`uk.json`, plan, and journal. A helper, caller, generated artifact, or second
test owner would therefore have forced C16; none was needed. The C15 source
freeze remains bounded by the five-path cap.

The governing bars are the slice plan's C15 ruling and
`docs/reference/policy-design-case-failure-patterns.md` P29, P31, P35, and P37.
The repository register has no P38 row at this revision, so this record calls
P38 an unregistered task-brief diagnosis rather than laundering it into a
registered finding. The complete census below independently establishes the
predicate mismatch: the old gate decided whole-message plural safety by asking
only whether the literal `{count}` occurred.

### Reproduced population and declared numeric-variable set

The journal's complete read-only structural traversal was replayed before
repair and after the catalog edits. Both runs returned 2,449 leaves per active
catalog, 244 non-`count` interpolation identities / 488 locale strings and 149
distinct variables. The original-risk cohort remains the enumerated 23
identities / 36 path-variable pairs / 72 locale instances, but its current
disposition is 20 neutral label-form messages plus three ICU-plural messages;
the post-repair semantic classifier does not call all 23 agreement-bearing.
The complete identity-variable SHA-256 stayed
`74413518b097e2fda58ed07a02409a41e2395d17d18c3e550115fbc21593a9e0`; the
agreement-pair SHA-256 stayed
`10b722ba7f4776a504eba6b983deface1b607af76fa190f72ff177fe0fabff88`.

The 71-name numeric declaration was derived from that 244-identity universe
and a complete caller/type adjudication of all 82 initially excluded names,
not from the two worked failures. Its sorted-newline key-set SHA-256 is
`c60120b6795593d5f5b84b83353e2c1d02c7ea568e8e48e146942aadbfdf3517`.
Every declaration carries this recorded reason in the canonical
`NUMERIC_VARIABLE_REASONS` map:

- `accepted`: accepted-item numerator; `accuracy`: correctness proportion;
  `act`: Act ordinal; `actual`: measured value/elapsed seconds; `after`: range
  endpoint; `alpha`: statistical scalar
- `artifacts`: artifact cardinality in count-bearing summaries; `attempt`:
  attempt ordinal; `available`: available-profile cardinality; `before`: range
  endpoint; `bindings`: binding cardinality; `bins`: quantile-dot cardinality
- `blocked`: blocked-item tally; `blockers`: blocker tally; `budget`: budget
  denominator; `candidates`: candidate cardinality; `completed`: progress
  numerator; `completeness`: preview proportion formatted as a percentage;
  `confidence`: percentage/out-of-100 quantity
- `cost`: price per million; `depth`: graph/workflow depth; `docs`: document
  cardinality; `duration`: time quantity, possibly preformatted; `durationMs`:
  milliseconds; `eValue`: E-value scalar
- `events`: event cardinality; `fallbacks`: caller array length; `fps`: frames
  per second; `index`: ordinal section/note/timeline position; `info`:
  informational-issue tally; `interval`: preformatted numeric confidence
  range; `lag`: time lag; `latency`: milliseconds
- `level`: confidence percentage; `losers`: population share; `lower`: interval
  bound; `maxNodes`: node-rendering threshold; `minimum`: minimum contrast
  ratio; `needs`: need cardinality
- `nodes`: node cardinality; `observed`: observed budget; `p10`: tenth
  percentile; `p90`: ninetieth percentile; `parameters`: parameter
  cardinality; `percent`: explicit percentage
- `plans`: plan cardinality; `policies`: policy-recommendation cardinality;
  `position`: row ordinal; `positivePct`: positive percentage; `promotions`:
  promotion cardinality; `priority`: typed numeric intervention priority;
  `quality`: quality-floor scalar
- `quantities`: estimated-quantity cardinality; `rate`: success rate; `ratio`:
  numeric ratio; `required`: required dwell seconds; `rows`: row cardinality;
  `score`: numeric score/floor
- `seconds`: explicit seconds; `selected`: selected-profile cardinality;
  `share`: cohort/population share; `strength`: percentage; `success`:
  successful-outcome cardinality; `target`: section count at one use and an
  identifier/value elsewhere
- `threshold`: E-value/fairness threshold; `total`: count/ratio denominator;
  `upper`: interval bound; `value`: count-bearing at selected Phase 32/34 uses
  and generic elsewhere; `warned`: warning tally; `warnings`: warning tally;
  `winners`: population share

Review replayed all 82 names excluded by the entry draft. It added exactly
four quantitative names from caller/type evidence: `completeness`
(`DataIntelligencePanel.tsx:1119-1124` plus numeric API field), `fallbacks`
(`DataIntelligencePanel.tsx:1108-1114` array length), `interval`
(`CounterfactualMetricChart.tsx:116-124` formatted numeric endpoints), and
`priority` (`shared/lib/domain/trinity.ts:33-41` number-or-null consumed by
`InterventionDetail.tsx:56-60`).

The remaining 78 were adjudicated non-quantity rather than silently omitted.
Sixty-four have direct caller/type/display evidence as text, enum, boolean,
identifier/ref/path/version, or formatted time:
`actor`, `affected`, `alias`, `artifactId`, `artifactKind`, `ast`, `authority`,
`basis`, `code`, `connector`, `coverage`, `createdAt`, `dataset`, `date`,
`direction`, `engine`, `filename`, `focus`, `from`, `hash`, `hints`, `how`,
`kind`, `label`, `lane`, `method`, `methodology`, `metric`, `mode`, `name`,
`namespace`, `needId`, `next`, `outputDir`, `parity`, `passId`, `path`,
`planId`, `promotionId`, `query`, `reason`, `reasons`, `ref`, `requestId`,
`runId`, `scenarioId`, `significance`, `source`, `sourceKind`, `state`,
`status`, `time`, `timestamp`, `title`, `to`, `txAt`, `type`, `updatedAt`,
`validAt`, `verdict`, `version`, `view`, `what`, and `why`. Fourteen lack an
exact literal-key caller at this head but their catalog-owned sibling
vocabulary fixes nonnumeric semantics: ID pair `baseRunId`/`targetRunId`,
enumerated `diff`/`reaction`, categorical `effort`, `likelihood`, and
`residual`, cohort label `group`, policy identifier `policy`, ref-list `refs`,
condition/temporal `known`, `valid`, and `unlock`, and masked structure
`skeleton`. Their caller status is `not_established`; that does not convert
their catalog semantics into quantities. No fifth quantitative addition was
found.

The declaration is the authority; the camel/snake numeric-token matcher is
only an omission backstop. It reports an undeclared matching name at the exact
`locale:path#{variable}` use. A synthetic `recordCount` use went red when
missing or whitespace-declared and green only after a non-empty reason. The
71 names occupy 183 exact active path-variable uses: the 36 original-risk
treatment entries and 147 declared non-agreement entries, each with a non-empty
reason. Exact set subtraction makes any new point of use red even if
punctuation hides adjacency. Their fingerprints prevent silently deleting or
replacing a declaration or point-use disposition. The exact `path#{variable}`
union hash is
`4bc1fc6d6b2600cfbebd509630f3f5ad82276c47e88b38834ce6fa3d526ee858`;
the 147-key non-agreement subset hash is
`2e3c9c18f5980770733df476a5d1427c42208c67f745cd50a408bfa43a6d9cae`.

### Complete 23-identity adjudication

All 23 identities required repair. No artifact establishes a safe numeric
range for an exemption, and a split would require a caller/product path outside
the cap. The resulting complete partition is 20 label-form messages / 33
path-variable pairs, three ICU-plural messages / three pairs, zero splits, and
zero exemptions:

1. `causal.pipeline.stageProgress#{total}` — **label form**. Numerator and
   denominator stay independent with real labels: EN `Completed stages:
   {completed} · total stages: {total}`; UK `Завершені етапи: {completed} · усі
   етапи: {total}`.
2. `common.lineageGraph.threshold#{nodes}` — **ICU plural**. One genuine node
   noun plus Ukrainian verb agreement; `maxNodes` stays a threshold. EN has
   `one/other`; UK has `one/few/many/other`, with neutral label form in `other`.
3. `pages.artifacts.trinity.bindingSummary#{bindings,parameters}` — **label
   form**. Two independent metadata axes: `Bindings: … · Parameters: …` in
   both active catalogs.
4. `pages.dashboard.narrativeAttentionBody#{blocked}` — **label form inside
   the existing count plural**. `blocked packets: {blocked}` / `заблоковані
   packet: {blocked}` avoids a 4x4 nested branch product while preserving the
   outer run agreement.
5. `pages.dashboard.narrativeEvidenceBody#{docs,promotions}` — **label form**.
   Two independent technical-count axes become `docs added: …` and `promotion
   candidates …: …`.
6. `pages.dashboard.narrativeThroughputBody#{success,total}` — **label form**.
   The decisive two-axis/no-`count` case becomes `successful outcomes:
   {success} · total runs: {total}` and the Ukrainian equivalent.
7. `pages.evidence.runContextSummary#{needs,plans,promotions,artifacts}` —
   **label form**. Four compact independent axes use `Needs`, `Plans`,
   `Promotions`, and `Artifact refs` labels.
8. `pages.runs.evidenceSummary#{plans,promotions}` — **label form**. Both axes
   use `Plans/Promotions` and `Плани/Промоції` labels.
9. `panels.dataIntelligence.focusSummary#{needs,plans,promotions}` — **label
   form** after the arbitrary `{focus}` token.
10. `panels.dataIntelligence.lastDiscoverSummary#{docs,candidates}` — **label
    form**. Independent fetched-doc and returned-candidate counts use labels.
11. `panels.dataIntelligence.resolvedSummary#{plans,candidates}` — **label
    form**. Independent resolved-plan and candidate counts use labels.
12. `phase32.choreography.artifacts#{value}` — **label form** because generic
    `value` cannot own a global plural rule: `Artifacts/Артефакти: {value}`.
13. `phase32.choreography.laneMeta#{events}` — **label form** beside the
    preformatted duration: `Events/Події: {events}`.
14. `phase32.connectors.datasets#{value}` — **label form**:
    `Datasets: {value}`.
15. `phase32.connectors.facts#{value}` — **label form**:
    `Connector facts/Факти через connector: {value}`.
16. `phase32.connectors.profiles#{value}` — **label form**:
    `Profiles: {value}`.
17. `phase32.freshness.derivedFacts#{value}` — **label form**:
    `Derived facts/Похідні факти: {value}`.
18. `phase33.identifiability.impactMeta#{quantities,policies}` — **label
    form**. Both slash-separated axes receive independent labels.
19. `phase33.stress.summary#{blocked,warned}` — **label form**:
    `Blocks/Блокування` and `Warnings/Попередження` are fixed labels.
20. `phase34.approval.blocked#{value}` — **label form**:
    `Approval blocks/Блокування approval: {value}`.
21. `phase34.auditTrail#{value}` — **label form**:
    `Audit events recorded/Записані audit events: {value}`.
22. `phase34.blockers.slowReview#{target}` — **ICU plural**. This exact
    `target` is a section count; EN uses `one/other`, UK uses
    `one/few/many/other`, and `other` is neutral label form.
23. `shared.charts.quantileDotplot.tailSummary#{bins}` — **ICU plural**. Bin
    count selects the dot noun; EN uses `one/other`, UK uses
    `one/few/many/other`, and percentile values stay independent.

No case requires forbidden nested ICU. The only pressure point is
`narrativeAttentionBody`, and its independently quantified blocked axis is now
neutral label/value copy. This follows C01-R1's already-landed Ukrainian
fractional-`other` idiom rather than inventing a sixteen-branch message.

### Red-first receipts and mechanism-round classification

The clean-entry baseline passed 1/1 focused file and 15/15 inherited tests in
1.39 seconds (83 ms test body) with `--maxWorkers=2`. Before implementing the
new functions or touching either catalog, seven new witnesses failed and all
15 inherited tests stayed green: 1/1 file, 7 failed / 15 passed, 949 ms total
(41 ms test body). Those witnesses cover exact-point unknown-variable
reporting, different-variable plural laundering, partial sibling repair,
missing/blank treatment reason, malformed ICU despite exemption, exact 23/36
registry shape, and complete active-catalog enforcement.

After the generic AST mechanism and the complete declarations were present but
before copy repair, the same focused command returned exactly 36 unsafe pairs
for EN and 36 for UK: 1/1 file, 2 failed / 21 passed, 1.27 seconds total (68 ms
test body). It named both `narrativeThroughputBody` axes and still named
`narrativeAttentionBody#{blocked}` despite the valid outer `{count}` plural.
That is the marker-preserving P29/P33 witness. Following only the 23 adjudicated
copy repairs and live-formatter expectations, the command passed 1/1 file and
28/28 tests in 2.58 seconds (175 ms test body). That was the pre-review green
receipt and was superseded when review changed the mechanism.

The scoped mechanism diff contains `parity.test.ts` plus both active catalogs;
therefore this is a mechanism-changing C15 implementation round, not a free
test-only or documentation-only round. It is C15's initial implementation, not
a third C01-R1 repair round. Independent review remains required before the
cluster commit, and any review repair will be classified from a newly frozen
mechanism-path diff under the plan's two-fix breaker.

### C03 two-gate correction and estimate retirement

C03 has two independent gates. First, DS5 must release the eight contended
manifest/schema/checker/test/register/report/status artifacts and C03 must
re-read their then-current content-hash ownership. Second, explicit heavy-lane
authorization must permit this JSON-producing whole-suite command from
`apps/runtime-dashboard`:

```bash
git rev-parse HEAD
/usr/bin/time -p corepack pnpm exec vitest run --reporter=json --outputFile=../../_build/apps/runtime-dashboard/ds6-c03-vitest.json
```

Only that green receipt package may populate the holes. The literal second
command supplies `command`; `git rev-parse HEAD` supplies `revision`;
`/usr/bin/time`'s `real` supplies `wall_duration_seconds`; Vitest JSON supplies
Vitest duration, file/test counts, and failure identities; runner process
status supplies `exit_code`; and the then-current producer/checker derives
`failure_set.sha256` and the empty resolved failure/debt-class state.
Focused Vitest and DS5 release satisfy neither other gate. The historical
263/766 -> 264/789 -> 265/800 -> 266/808 arithmetic above records what was
estimated at those earlier checkpoints; C15 supersedes every one as a future
governed value. They are not C03 inputs. `parent_reproduction` remains
historical provenance, never a substitute receipt.

This adjacent numeric-variable class does not broaden the registered
`baseline-test-i18n-count-debt`: that governed row remains exactly the three
inherited `overBudget` signatures. C15 changes the future whole-suite
population but contributes no projected denominator, hash, duration, exit
code, or resolved state to C03.

### Independent review batch and mechanism round 1

Three independent read-only reviews froze the five-path draft. Their
Blocking/Important findings cite the slice C15 ruling and failure-register
P29/P31/P33/P35/P37:

- the mechanism reviewer proved two marker-preserving bypasses: ICU-valid
  whitespace after `{` escaped the discovery regex, and parenthesized or
  colon-prefixed agreeing copy could satisfy the draft punctuation predicate;
  it also found that the blank-reason witness used a variable absent from the
  declaration
- the specification and boundary reviewers independently proved that a new
  use of an already-declared numeric name escaped because the unsafe checker
  visited only the fixed 36 treatment keys; the injected empty-rule witness
  did not prove the missing-identity path
- the specification reviewer classified the complete 82-name remainder and
  found the four quantitative omissions recorded above
- both specification/boundary reviewers caught the false `C14 closed`
  statement; Git history contains no C14 commit and the heavy closeout remains
  deferred, while the continuation directly authorizes C15
- the boundary reviewer separated C03 field provenance because Vitest JSON
  cannot supply Git revision, `/usr/bin/time real`, literal command, or process
  status; it also corrected the post-repair 23/36 wording from present
  agreement to original-risk cohort

These findings entered C15's first mechanism review-fix round. The scoped
mechanism-path diff is nonempty: `parity.test.ts` gained whitespace-aware
discovery, exact 183-use set subtraction, 147 reasoned non-agreement entries,
colon-plus-bounded label proof, missing-identity and punctuation witnesses, and
the complete 71-name declaration; both active catalogs changed the one ratio
copy into two real labels. This is not a free test/documentation round. One
mechanism review-fix round remains under the breaker.

Red receipts during the repair were kept as findings, not called regressions:
the tightened colon predicate first returned 2 failed / 27 passed because the
old `Stages: completed/total` ratio did not give `total` its own label; the
first missing-identity implementation then returned 2 failed / 28 passed and
reported 82 EN / 80 UK pre-existing numeric uses because it had not yet
enumerated their non-agreement disposition. Two-label copy and the exact
147-entry reason map closed those structural gaps. After the complete review
repair, focused parity passed 1/1 file and 30/30 tests in 1.07 seconds (77 ms
test body) with `--maxWorkers=2`. This receipt supersedes the pre-review 28/28
green and is still subject to delta re-review.

Delta review found one remaining P29/P33 punctuation admission: the
post-label boundary accepted parentheses even though the complete 33-pair live
label-form AST census needs only end-of-message, `.`, ` ·`, or ` /`. That let
`Events: {events} (events)` keep the colon marker while restoring an agreeing
noun. Removing parentheses from the admitted boundary and adding that exact
witness changes the mechanism, so it consumes C15's second and final review-fix
round. The same record-only correction updated the stage-progress reason from
the superseded single `Stages:` label to the actual separate numerator and
denominator labels. Any further Blocking/Important mechanism finding now trips
the breaker and stops C15 rather than opening a third fix round.
