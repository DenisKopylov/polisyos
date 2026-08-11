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
