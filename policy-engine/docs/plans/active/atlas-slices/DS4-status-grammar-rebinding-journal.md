---
title: "DS4 Status-Grammar Rebinding Journal"
type: execution-journal
status: in_progress - architect-authorized authority-neutral partial re-cut
created: 2026-07-18
revised: 2026-07-18
slice: DS4
plan: ./DS4-status-grammar-rebinding.md
branch: codex/atlas-ds4-status-grammar
baseline_commit: 71f438ad52f668e1feb7510652ff5fd3b735bd62
execution_base_commit: 61d354f62023460a45c60c913976cdfc4b779cf5
---

# DS4 Status-Grammar Rebinding Journal

## 2026-07-18 — DS4-C00 baseline and contract audit

### Isolation and fence

- Created `.worktrees/atlas-ds4` from `main` at
  `71f438ad52f668e1feb7510652ff5fd3b735bd62` on
  `codex/atlas-ds4-status-grammar`.
- Verified the branch and worktree were clean before the install and all
  baseline commands.
- No source, package, register, ledger, lockfile, or generated-client edit was
  made before the baseline receipt. The first repository edit is the DS4 plan
  and this journal.

### Required reading and pattern pass

Read in order: Revision-3 measured preamble, DS4 scope, inherited baseline debt
table, Phase-A PI-04..PI-06 re-scope, DS0 D2/D3, DS19 register and cluster law,
and DS2 adoption ledger. Also read `CONTRIBUTING.md` and the complete
failure/repair register before design.

Relevant patterns: P04, P05, P06, P08, P10, P13, P15, P27, P28, P29, and
P31-P34. The smallest correct pattern is a generated owner type feeding one
rebound consumer with a negative/e2e semantic proof; a UI-local replacement
enum is rejected.

### Toolchain receipt before edits

| Command                                                             | Result                                                                                                                                                                      |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `corepack pnpm install --frozen-lockfile --ignore-scripts`          | PASS; pnpm 10.33.2; 1,211 packages; frozen lockfile unchanged                                                                                                               |
| `corepack pnpm run typecheck`                                       | PASS                                                                                                                                                                        |
| `corepack pnpm run build`                                           | PASS; 3,871 modules; PWA 101 entries; Vite 13.33 s                                                                                                                          |
| `corepack pnpm run lint`                                            | OBSERVED exit 1; inherited RED; 75 errors, 0 warnings, 22 files; one rule only; exact identities match the checked manifest                                                 |
| `corepack pnpm run test:components`                                 | OBSERVED exit 1; inherited RED; 229 files / 674 tests; 226 files / 669 tests pass; 3 files / 5 tests fail; 77.73 s; JSON identities compare exactly to the checked manifest |
| `corepack pnpm run check:architecture`                              | OBSERVED exit 1; inherited RED; 36 exact violations                                                                                                                         |
| disposition register checker with source-byte and corruption probes | PASS; 261 roots, 200 pending, 23 negatives, 7 censuses                                                                                                                      |

The canonical register checker separately compared cached ESLint JSON against
the exact lint multiset (PASS in 3.88 s) and a fresh Vitest JSON report against
the exact failed-test set (PASS). These are identity receipts, not count-only
comparisons.

Runtime versions: Node `v22.22.2`, pnpm `10.33.2`, Python `3.14.0`, uv
`0.10.6`. The worktree has no executable `.venv/bin/python`; venv-dependent
commands are non-receipts rather than inferred successes.

### Exact inherited failures

- `src/shared/i18n/parity.test.ts`: three count-sensitive catalog assertions
  fail for `panels.agentPipeline.overBudget` in `en`, `uk`, and `ru`.
- `src/shared/ui/A11yCoverage.a11y.test.tsx`: the sole missing companion is
  `OperatorDiagnosticPanel.tsx`.
- `src/app/providers/TemporalCursorProvider.test.tsx > commits canonical URL
params`: expected the April 2026 cursor but received current-time
  `valid_at`/`tx_at` values.

The lint queue contains exactly 75 `policyos/quantity-must-be-wrapped`
diagnostics. The architecture queue contains exactly 36 violations: one
app/workspace feature-internal edge and 35 shared→app/feature edges, including
the quantity, temporal, trust, counterfactual, authored-text, and chart
families.

### Canonical-client precondition result

The generated client exposes typed `ProjectionFreshness`
(`packages/runtime-api-client/types.ts:8164`), but its terminal distribution is
an open record (`:4894`), its depth-N evidence class is `string` (`:4886`), its
generation-cycle disposition payload is generic projection JSON (`:5850`), and
it does not export a closed decision-grade type. DS3 semantic tests
intentionally require unseen evidence (`tests/unit/runtime/http/
test_governed_projection_service.py:614`) and terminal (`:649`) labels to pass
through without pinning. `ProjectionFreshness` models source observation and
validity, not the roadmap's cache-age posture.

Result: terminal/evidence transport exists and remains intentionally opaque;
it is `implemented_but_not_orchestrated` for neutral display. The universal
composition grammar is `artifact_missing`, while CGF, decision-grade, and
cache-age fields are also `bridge_missing`/`surface_missing`. DS4 cannot fill
those gaps without recreating a local semantic owner. An attempted UI grammar
would be P04/P05/P27. C00 therefore stops before production edits and requests
either a DS3-class canonical repair that preserves opaque novel values or an
architect-approved partial re-cut.

The architect must also reconcile the denominator conflict: the master debt
table predicts DS4 takes Vitest 5 -> 4 and gives a11y to DS6, while the DS4 brief
requires DS4 to repair the `OperatorDiagnosticPanel` a11y gate. Closing temporal
and a11y yields 5 -> 3.

### Cluster disposition

- C00 plan/journal: ready for scoped verification and commit.
- C01-C20: not started; no red-first test or positive implementation may start
  until the C00 decision is recorded.
- No DS19 disposition row changed because no family was rebound.
- No DS2 material was consumed; all design calls reference ledger IDs only.

### C00 post-edit verification

- Prettier check: PASS for the plan and journal.
- Dashboard typecheck: PASS in 12.71 s.
- Production build and postbuild security: PASS in 18.75 s; 3,871 modules and
  101 PWA precache entries.
- Disposition register, baseline-source-byte verification, and corruption
  probes: PASS in 3.32 s; denominators remain 261 roots, 200 pending, and 23
  seeded negatives.
- Production source, generated client, DS2 ledger, DS19 register, baseline
  manifest, and lockfile remain unchanged. C00 contains documentation only.

## 2026-07-18 — DS4-C01 foundation primitive migration

### Authorization, clean base, and pattern pass

- The architect resolved C00 with an authority-neutral partial re-cut: C01-C20
  may execute using existing typed contracts and neutral presentation swap
  modules, while the missing waist vocabularies remain deferred. The C01
  execution base was clean `61d354f62023460a45c60c913976cdfc4b779cf5` on
  `codex/atlas-ds4-status-grammar`; the measured `71f438ad52f668e1feb7510652ff5fd3b735bd62`
  baseline receipt remains historical evidence, not the C01 checkout base.
- C01 keeps terminal and evidence labels opaque end-to-end. It adds no
  authority/status vocabulary, composition rule, CGF disposition, decision
  grade, or cache-age classification.
- Relevant patterns were P05/P06/P10/P15 (authority and presentation boundary),
  P27/P28 (one owner and strangled legacy), and P29/P33 (behavioral,
  adversarial ownership and surface proof). The correct C01 shape is one
  package owner, direct consumers, deleted predecessors, package import fence,
  and red/green consumer tests.

### Architect rulings carried into execution

- Each absent vocabulary receives exactly one future normalization module. It
  passes owner labels opaquely, returns only presentation-only `unrecognized`
  outside an owner-declared contract, and exports no vocabulary constants:
  cache-age C09, decision-grade C14, and CGF disposition C19 with real-panel
  proof.
- C05 will create the dedicated typed DS4 waist-debt register with exactly
  three DS5-waist-owned rows, each `bridge_missing` and `surface_missing` with
  its exact generated-client anchor. The rows do not enter the 261-entry
  DS1/DS19 estate; C20/final closure flags them for architect insertion into
  the master inherited-debt table.
- C09 owns temporal-cursor root-cause classification and test-clock injection
  repair unless product semantics are wrong. C12 owns the
  `OperatorDiagnosticPanel` a11y census. The three i18n parity identities are
  untouched; the end-state expectation is three failures in one file.

### Red-first receipt

All required tests were added before deleting the old owners and exited RED
for their intended behavioral reasons:

- `oneOwner` found the eight old `shared/ui` exports, the duplicate
  `shared/components/Skeleton.tsx` owner, and legacy primitive-barrel exports.
- `publicSurface` expected 25 supported runtime exports and received the empty
  package surface.
- `primitiveMigration` expected package foundations and received the empty
  package surface.

### C01 implementation

- Created private `@polisyos/atlas-ui@0.1.0` with root-only exports and local
  typecheck, test, lint, and architecture scripts. Its architecture gate parses
  actual import/export specifiers and rejects dashboard/app/API/backend/client
  edges.
- Moved the eight foundation families into the package, deleted their dashboard
  owners and the duplicate `shared/components/Skeleton` owner/test, and removed
  legacy primitive-barrel exports. Dashboard consumers now import directly from
  `@polisyos/atlas-ui`.
- Inverted `AsyncSection` through its typed dashboard error-presentation slot;
  `LocaleProvider` configures package `TextPresentationProvider`; `BadgeTone`
  is documented presentation-only; `ApiErrorAlert` and `ProvenanceStrip`
  remain dashboard-owned consumers of package `Text`.
- Added the dashboard stylesheet's explicit Tailwind v4 package source and a
  post-build behavioral gate. The gate derives two package-exclusive class
  candidates and verifies their utilities exist in the generated CSS, so the
  source edge cannot be satisfied by a marker-only assertion.
- `ui-primitives-root` remains `rebind_pending`/`pending`; no DS19 root state
  or 261-entry denominator changed in C01. Mechanical import line movement
  refreshed only the affected baseline-lint content hashes/diagnostic anchors
  and two protected-live census line anchors; the debt count and census count
  remain 75 diagnostics and 24 references.

### Verification receipt

| Gate                                      | Result                                                                                                                                                |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| frozen install                            | PASS; lockfile up to date                                                                                                                             |
| atlas-ui lint/typecheck/test/architecture | PASS; 4 files / 7 tests; 10 source files inspected                                                                                                    |
| dashboard typecheck                       | PASS                                                                                                                                                  |
| dashboard foundation component tests      | PASS; 6 files / 11 tests, including `primitiveMigration`                                                                                              |
| route-boundary migration regression       | PASS; 1 file / 6 tests after retargeting the retired-owner test double to `@polisyos/atlas-ui`; product semantics unchanged                           |
| dashboard a11y component coverage         | PASS; 10 files / 10 tests for the moved-family paths; the separate inherited `OperatorDiagnosticPanel` census remains C12-owned                       |
| dashboard full lint JSON                  | inherited 75 errors in 22 files, zero warnings; only `policyos/quantity-must-be-wrapped`; baseline subset comparator PASS after honest anchor refresh |
| dashboard architecture                    | inherited 36 exact violations, no C01 class added                                                                                                     |
| dashboard full Vitest JSON                | inherited 5 failures only; 668 / 673 tests pass and the baseline failure-set comparator is PASS                                                       |
| Vite build + postbuild gates              | PASS; 3,873 modules, 101 PWA precache entries; two package-exclusive Tailwind candidates present in generated CSS                                     |
| disposition register                      | PASS with source-byte binding and corruption probes; 261 roots, 200 `rebind_pending`, 23 seeded negatives, 7 censuses                                 |

The Tailwind source proof was red-first during review: before adding the
explicit package `@source`, the built CSS omitted both
`h-[var(--control-height-sm)]` and `w-3/5`. The same build gate passed only
after the package source entered the real Tailwind scan graph.
The anti-shim re-review added a synthetic wildcard re-export corruption; it
failed against the original owner scanner, then passed after export-declaration
resolution became part of the generic ownership invariant. Button `asChild`
now also has explicit prop, style, and ref-forwarding acceptance coverage.

### Lockfile and fence receipt

- `corepack pnpm install --lockfile-only` was inspected and the unrelated
  `third-party-web` 0.29.0 -> 0.29.2 package/snapshot movement was restored.
  The final semantic diff contains only the `packages/atlas-ui` importer and
  the dashboard `@polisyos/atlas-ui: workspace:*` link.
- The C01 diff is restricted to dashboard sources/package declaration,
  `packages/atlas-ui`, the bounded workspace lockfile importer, DS4 plan and
  journal, and required DS19 baseline-anchor maintenance. Backend, schema,
  generated-client, v15, Russian locale, master-plan, CI, and other-worktree
  paths remain untouched.

## 2026-07-18 — DS4-C02 form primitive migration

### Red-first receipt and owner decision

- Before any positive source edit, the exact `oneOwner` C02 test failed with
  twenty intended findings: ten dashboard implementation owners plus ten
  legacy primitive-barrel exports, with all ten package owners absent.
- Before any positive source edit, the exact dashboard `primitiveMigration`
  C02 test failed because the package runtime surface exposed none of
  `Checkbox`, `Input`, `Label`, `Radio`, `SegmentedControl`, `Select`,
  `Slider`, `Switch`, `Textarea`, or `ToggleButton`.
- The existing implementations were migrated rather than redesigned. Their
  native validity and refs, Radix props, generic string option values, and
  toggle cancellation semantics remain the acceptance contract. No authority
  vocabulary, status union, or semantic classification entered the package.

### Implementation

- Moved all ten form/control owners into `@polisyos/atlas-ui`, exported them
  only through the package root, migrated dashboard consumers/tests/stories to
  direct package imports, deleted the dashboard implementation files, and
  removed the ten legacy barrel exports without a compatibility shim.
- Rebound the existing native Trust View input in
  `BureaucraticArtifactView` to package `Checkbox`; its consumer test proves
  the `atlas-checkbox` owner and the existing query-state transition together.
- Generalized the C01 AST owner scanner across named primitive families while
  retaining its duplicate-owner and package re-export negatives. The package
  public-surface gate now accounts for the ten additional runtime exports.
- Added behavior coverage for label/required validity, forwarded native refs,
  Checkbox change, Radio grouping, Select/Textarea validity, generic opaque
  segmented values, disabled segmented suppression, Radix Switch/Slider
  props, and ToggleButton cancellation/default button posture. Added package
  axe coverage for the whole form family and the required ResizeObserver test
  harness support used by Radix Slider.
- Added only the already-locked Radix Label, Slider, and Switch dependencies
  to the package importer. The unrelated `third-party-web` lockfile resolution
  movement produced by lockfile regeneration was restored before the frozen
  install receipt.
- `ui-primitives-root` remains `rebind_pending`/`pending` until C03; no DS19
  state or denominator changed. Import movement refreshed only the
  `DataIntelligencePanel` baseline content hash/diagnostic anchors and the two
  protected browser-signing census line anchors; lint remains 75 identities
  and the protected census remains 24 references.

### Verification receipt

| Gate                                      | Result                                                                                                                                                |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| frozen install                            | PASS; lockfile up to date; only three existing Radix resolutions added to the `packages/atlas-ui` importer                                            |
| atlas-ui lint/typecheck/test/architecture | PASS; 6 files / 13 tests; 20 source files inspected                                                                                                   |
| dashboard typecheck and production build  | PASS; 3,873 modules, 101 PWA precache entries, postbuild security and package Tailwind-source proof green                                             |
| exact C02 migration test                  | PASS; 1 file / 2 tests, including label focus and required validity through direct package imports                                                    |
| affected dashboard unit tests             | PASS; 7 files / 18 tests; separate BureaucraticArtifactView structural a11y test PASS                                                                 |
| migrated dashboard a11y tests             | PASS; 10 files / 10 tests through the existing shared-UI a11y contour                                                                                 |
| dashboard full lint JSON                  | inherited 75 errors in 22 files, zero warnings, only `policyos/quantity-must-be-wrapped`; baseline subset comparator PASS after honest anchor refresh |
| dashboard architecture                    | inherited 36 exact violations, no C02 class added                                                                                                     |
| disposition register                      | PASS with source-byte binding, current lint identities, and corruption probes; 261 roots, 200 `rebind_pending`, 23 seeded negatives, and 7 censuses   |

The first full-lint run correctly caught four new `import/no-duplicates`
reports in two consumers after the mechanical path migration. Their package
imports were consolidated, and the fresh final lint receipt returned to the
exact inherited 75-identity set. C02 runs affected tests at the cluster
boundary; the next full Vitest baseline comparison remains the C05 wave
boundary required by the committed cadence.

### Fence receipt

- Retired-owner and shared-barrel scans return no form-family consumer,
  test, story, or compatibility path; the package owner test is green.
- The C02 diff is confined to dashboard sources, `packages/atlas-ui`, the
  bounded package-importer lockfile hunk, DS4 journal, and required DS19
  manifest/census anchors. Backend, schemas, generated client, v15 archive,
  frozen Russian locale, master plan, CI, and other worktrees are untouched.

## 2026-07-18 — C03 clean-boundary preflight stop

- A read-only AST/import census after C02 found living production consumers
  for `Command`, `Dialog`, `Popover`, and `Tooltip`.
- The same census found no production consumer for `DropdownMenu`,
  `ScrollArea`, `Separator`, `Sheet`, or `Tabs`; their only current consumers
  are owner-local tests/stories and the legacy barrel. Those are not the live
  consumer evidence required by the committed C01-C03 one-owner strangle law.
- This is structural rather than a search artifact: the run page's apparent
  tabs are route navigation links; `BottomSheet` is the gesture/snap family
  assigned to C17 rather than a `Sheet` consumer; no product dropdown-menu
  use exists; and generic overflow/divider markup is not evidence that the
  dormant `ScrollArea` or `Separator` owner is consumed.
- Migrating the five dormant owners would therefore create a package-only
  component universe and conflict with the DS2 `component-tabs` and
  `component-scroll-area` rows, which require living consumer evidence before
  adoption. Inventing replacement consumers would exceed the approved rebind
  scope and could change navigation or interaction semantics.
- No C03 production, register, or manifest edit was made. The proposed re-cut
  is C03a for the four consumed families, with aggregate
  `ui-primitives-root` retained as `rebind_pending`/`pending`; the architect
  must adjudicate the dormant five as retirement/use-as-is or name their real
  consumers before the aggregate row can be strangled.

## 2026-07-18 — DS4-C03a living overlay primitive migration

### Red-first receipt and pattern pass

- Before any positive production edit, the exact overlay `oneOwner` assertion
  failed with the intended eight findings: the four dashboard implementation
  owners and four legacy primitive-barrel exports, while all four package
  owners were absent.
- Before any positive production edit, the exact dashboard
  `primitiveMigration` assertion failed because the package runtime surface
  exposed none of the Command/Dialog/Popover/Tooltip families.
- Relevant risks were P06/P27/P28 (canonical ownership and complete legacy
  strangle), P29/P33 (behavioral owner and portal proof), and P10 (semantic
  interaction coverage). The correct pattern is one package owner, direct
  consumers, no compatibility export, real focus/dismissal/portal tests, and
  package-local behavior plus axe coverage.

### Implementation

- Moved the four existing implementations into `@polisyos/atlas-ui`, retained
  their Radix/cmdk props, refs, class semantics, portal behavior, focus
  management, and dismissal behavior, and kept the Command-to-Dialog edge
  wholly inside the package.
- Added optional package-boundary `title` and `closeLabel` presentation props;
  the living CommandPalette and provenance dialog supply their existing
  localized catalog strings, so the package has no dashboard/i18n dependency.
- Migrated every living Command/Dialog/Popover/Tooltip consumer and the four
  dashboard a11y tests to direct package imports. Deleted the four dashboard
  owners and their legacy barrel exports; no wildcard, relative package
  re-export, or compatibility shim remains.
- Added package behavior, public-surface, one-owner, and WCAG AA axe coverage
  for all four families. Added only the already-resolved Radix Dialog,
  Popover, Tooltip, and cmdk dependencies to the atlas-ui importer.
- Left `DropdownMenu`, `ScrollArea`, `Separator`, `Sheet`, and `Tabs` untouched.
  Aggregate `ui-primitives-root` remains `rebind_pending`; C03b owns its mixed
  disposition and no DS19 denominator or register state changed in C03a.

### Verification receipt

| Gate                                      | Result                                                                                                                         |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| frozen install                            | PASS; lockfile up to date; atlas-ui importer-only additions with zero package/snapshot resolution movement                     |
| atlas-ui lint/typecheck/test/architecture | PASS; 24 source files inspected; 8 test files / 22 tests                                                                       |
| exact C03a owner and migration tests      | PASS; real Dialog focus/Escape restoration, Popover outside dismissal, Tooltip Escape dismissal, and body portals              |
| affected dashboard behavior and a11y      | PASS; 6 files / 45 behavior tests and 7 files / 7 WCAG AA axe tests                                                            |
| dashboard typecheck and production build  | PASS; 3,873 modules, 101 PWA precache entries, postbuild security, and package Tailwind-source proof                           |
| dashboard full lint JSON                  | exact inherited 75 errors in 22 files, zero warnings, only `policyos/quantity-must-be-wrapped`; baseline comparator PASS       |
| dashboard architecture                    | exact inherited 36 identities; no C03a class added                                                                             |
| disposition register                      | PASS with source-byte verification and corruption probes; 261 roots, 200 `rebind_pending`, 23 seeded negatives, and 7 censuses |

The first full-lint run exposed two `import/no-duplicates` reports in
`GovernancePassGrid` after Tooltip moved beside its existing package Card
import. Consolidating that single import returned the exact inherited lint
identity set; no new lint, architecture, Vitest, or register debt was
manifested.

### Fence receipt

- Retired-owner/import and anti-shim scans are empty for all four families;
  generic one-owner, public-surface, package architecture, and package
  Tailwind-source gates are green.
- The C03a diff is confined to dashboard sources, `packages/atlas-ui`, the
  bounded atlas-ui lockfile importer hunk, and this DS4 journal. Backend,
  schemas, generated client, v15 archive, frozen Russian locale, master plan,
  CI, registers, debt manifests, and other worktrees remain untouched.

## 2026-07-18 — C03b dormant primitive retirement

### Red-first receipt and ruling application

- The compiler-AST census was recomputed across dashboard and workspace
  production TypeScript for direct, barrel, namespace, relative, dynamic, and
  composition imports. `DropdownMenu`, `ScrollArea`, `Separator`, `Sheet`, and
  `Tabs` each had zero production consumers; owner-local a11y fixtures and
  barrels did not count as consumers.
- The first focused checker test failed before the aggregate receipt and source
  transition existed. Positive work then made the checker derive the live
  owner/export/consumer state, bind Git resurrection blobs, and reconcile the
  receipt rather than trusting stored counts.
- During self-review, the mixed receipt was found on the wrong DS1 root. Two
  additional red-first regressions—rejecting a receipt on any non-primitive
  root and requiring the live receipt only on `ui-primitives-root`—failed on
  that state. Moving the receipt to its canonical root made both pass; this is
  now a structural checker invariant and corruption target.
- Independent review then found two P29 bypass classes: marker-only successor
  evidence and a retired symbol exported from a differently named owner file,
  plus computed and delayed dynamic-import access forms. The added negatives
  failed on comments/strings/type-only or unused imports, `Overlay.tsx` alias
  exports, `UI["Tabs"]`, directly chained promises, and a promise assigned
  before `.then`. The checker now resolves actual TypeScript binding symbols,
  follows dynamic-import continuations, scans declarations/exported aliases
  across both owner roots, and rejects shadowed same-name lookalikes. All
  variants pass only after the runtime property is present. The bounded final
  independent re-review approved the fixes with no remaining finding.
- The exact DS2 ledger condition for `component-scroll-area` is: “Archive
  admission alone sunsets nothing. DS4 may remove a mapped loser only after
  generated/source ownership, consumer migration, drift checks, and the owning
  slice's DS6 evidence are complete.” It therefore remains `use_as_is`.
- The exact DS2 ledger condition for `component-tabs` is: “Keep the mapped live
  v4 family as the transitional winner until DS4 routes a real consumer through
  one governed replacement, DS6 passes its negative/browser/accessibility
  evidence, and the old import path is removed.” It therefore remains
  `use_as_is`.
- `DropdownMenu`, `Separator`, and `Sheet` have no exact DS2 adoption row, so
  the architect's default retirement ruling applies.

### Implementation and disposition receipt

- Deleted the three dormant implementation/a11y pairs and their dashboard
  barrel exports. No story or other harness reference existed, and no package
  counterpart or compatibility shim was created.
- Retained `ScrollArea` and `Tabs`, their colocated a11y tests, exports, and
  dependencies without claiming the missing DS6 evidence.
- Bound the retirement to pre-deletion commit
  `caa1ee6e3ab49d559b19dbeeda6308c3598e7183` and all six Git blob IDs. A future
  resurrection is permitted only by recreating the primitive in
  `@polisyos/atlas-ui` together with a real production consumer; the app-tree
  implementations must never be restored.
- Transitioned the aggregate `ui-primitives-root` through the repository's
  completed-rebind encoding and attached one typed mixed receipt. Its
  recomputed accounting is 22 package migrations + 2 dashboard rebounds + 3
  retirements + 2 `use_as_is` = 29. The receipt is report-projected and the
  DS19 root denominator remains 261.
- Kept `apps/runtime-dashboard/package.json` and `pnpm-lock.yaml` byte-identical
  to C03a. The original DS4 lock exception is addition-only; removing now-unused
  direct dependency declarations is not required to retire the source owners
  and is therefore outside this cluster's bounded lock change.

### Verification receipt

| Gate | Result |
| --- | --- |
| focused register behavior | PASS; 14 tests, including wrong-root, count-drift, revived/renamed-owner, package-only resurrection, blob-drift, marker-only/shadowed successor evidence, and all required import-form probes |
| disposition register | PASS with source-byte verification and corruption probes; 261 roots, 8 censuses, 200 `rebind_pending`, 15 deleted, 25 retire, 5 `use_as_is`, 16 wire, 23 negatives, 11 findings |
| atlas-ui lint/typecheck/test/architecture | PASS; 8 files / 22 tests and 24 source files inspected |
| retained primitive a11y | PASS for `ScrollArea` and `Tabs` |
| structural a11y census | honestly RED only for the inherited `OperatorDiagnosticPanel.tsx` identity assigned to C12; no C03b identity was added |
| dashboard primitive migration | PASS; 1 file / 3 tests |
| dashboard typecheck and production build | PASS; 3,867 modules and 101 PWA precache entries; postbuild security and package Tailwind-source checks pass |
| dashboard full lint JSON | exact inherited 75 errors in 22 files, zero warnings, only `policyos/quantity-must-be-wrapped`; baseline subset comparator PASS |
| dashboard architecture | exact inherited 36 identities; no C03b edge added |
| frozen install | PASS with the committed lockfile unchanged |

### Fence receipt

- Source, a11y fixture, barrel-export, package-counterpart, and production
  consumer scans enforce the retirement and retention choices from live syntax.
- The C03b diff is confined to dashboard source deletion, the owned DS19
  register/schema/checker/report, its focused test, and this journal. Backend,
  schemas, generated client, v15 archive, frozen Russian locale, master plan,
  lockfile, and other worktrees remain untouched.

## 2026-07-19 — DS4-C04 ratified DTCG token projection

### Red-first receipt and pattern pass

- Before the adapter existed, the nine exact package parity tests and both
  projector-drift suites failed at their absent generated/projector imports.
  The dashboard parity suite failed all nine gap assertions because the package
  exports were absent. Four behavioral owner tests then failed on the living
  Theme, Density, HighContrast, and ReducedMotion hard-coded values.
- The first independent review found three P29/P33 defects: regeneration could
  bless invalid DTCG, the live parity proof sampled values, and generated
  contrast/motion/print CSS omitted behavior. Four validator regressions were
  recorded RED against unknown type, missing type/value, malformed compound
  value, and a nested token sibling. Three generic behavior comparisons were
  recorded RED against the incomplete high/forced-color, reduced-motion, and
  print projections before the positive repair.
- Four bounded re-reviews then exposed deeper instances of the same class.
  Persistent RED cases now prove official-schema-invalid composite fields,
  metadata, names, and cubic-bezier x coordinates cannot pass the direct
  writer; canonical DTCG color alpha and the standard `none` component cannot
  collapse to opaque or `NaN` CSS. Contrast-more and both reduced-motion paths
  remain complete, while forced-color/print parity compares ordered rules
  within each cascade layer. A reversed same-context source-order adversary
  fails even though the former merged-map comparator stays equal. A full-suite
  RED also found a route test's total package mock hiding new descriptor
  exports; it is now a partial mock.
- Relevant risks were P06/P27/P28 (one future token authority without a second
  runtime owner) and P29/P33 (real projection, complete parity, and adversarial
  corruption rather than marker checks). `token-root-component` remains
  explicitly deferred under DS2; its live theme aliases are classified by the
  parity gate and are not silently admitted into C04.

### Implementation

- Added the one-way package topology
  `tokens/{source,modes}/*.tokens.json -> src/tokens/project.ts ->
  src/generated/{tokens.css,tokens.ts,tailwind.ts,figma.json,manifest.json}`.
  All twelve sources are valid DTCG 2025.10 documents with structured standard
  values; CSS behavior lives only in `org.polisyos.atlas` projection metadata.
  Both generation and checking run the pinned official schema first. The
  direct projector also validates the complete supported source subset,
  including recursive metadata/name constraints and standard compound-value
  bounds. It proves any redundant CSS value equals the canonical DTCG value
  (including alpha and `none`), hashes every source byte, and compares the
  complete output set.
- Projected all nine ratified gaps: ADR-047 warm light/dark values, eight z
  layers, light/dark post-reference and nine chart aliases, all 35 values for
  each density, the `1280` token/`1281` runtime breakpoint asymmetry,
  light/dark/system descriptors, full high/contrast-more/forced-color tokens
  and layer-preserving rule graphs,
  the `240ms` CSS/`180ms` helper motion asymmetry plus complete reduced-motion
  rules, and complete imported print `@page`, utility, shell, deck,
  hide/keep/layout/link/export behavior with source-order overrides retained.
- The package root exports pure typed descriptors and aliases only. Generated
  CSS is committed parity evidence and is not a root side effect. No React mode
  provider, dashboard dependency, deep export, central CSS adoption, or C17
  responsive migration was added.
- Rebound the four living providers to package descriptor values while keeping
  DOM mutation, storage, feature flags, media subscriptions, state, telemetry,
  and React contexts in their existing dashboard owners. The behavioral test
  substitutes sentinel descriptors, proving the values are consumed rather
  than merely duplicated.
- The live parity test is outside the runtime `src` architecture graph and uses
  PostCSS to compare complete admitted maps and normalized rule graphs in both
  directions. Its dynamic non-hand-picked corruption fails while source
  markers remain. The DS2 `token-root-component` deferral is an exact 50-name
  inventory for each light/dark source, not a prefix loophole; any newly
  unclassified alias is treated as admitted and fails parity. Unproved radius,
  shadow, spacing, and typography leaves were removed from the future-authority
  source rather than silently projected.
- `designTokens.ts`, `chartTheme.ts`, `motion.ts`, all living CSS, and all
  central consumers remain byte-unchanged. `ui-tokens` remains
  `rebind_pending`; C17/DS6 still own compatibility-projection and sunset
  evidence. The raw Tailwind z-index census remains 19 uses in 15 files and is
  not misreported as migrated.

### Verification receipt

| Gate | Result |
| --- | --- |
| frozen install and lock proof | PASS; six workspaces already current; `pnpm-lock.yaml` and dashboard dependency declarations byte-identical to C03b |
| deterministic projection | PASS; official DTCG 2025.10 schema precedes generate/check; regenerate leaves all five artifacts exact; source/output/manifest/unregistered-sibling, malformed composite/metadata/name, CSS-equivalence, alpha/`none`, cubic-bound, and direct-writer corruptions fail |
| atlas-ui gates | PASS; typecheck, lint, architecture (27 source files), and 10 test files / 50 tests |
| dashboard owner/parity tests | PASS; 3 files / 22 tests, including ordered contextual nine-gap parity, the source-order adversary, four sentinel owner bindings, and the partial-mock route regression |
| dashboard design/a11y token gates | PASS; Atlas-v4 238-pair drift, motion, print, reduced-motion, contrast, and color-blind checks |
| dashboard typecheck and production build | PASS; 3,868 modules, postbuild security, package Tailwind-source proof, and 101 PWA precache entries |
| dashboard full lint JSON | exact inherited 75 errors in 22 files, zero warnings, only `policyos/quantity-must-be-wrapped`; baseline comparator PASS |
| dashboard full Vitest | PASS baseline-relative after a two-worker run: 228 files / 688 tests, 225 files / 683 tests pass, and only the five inherited identities remain; an earlier host-starved attempt and its focused-green timeout are non-receipts |
| dashboard architecture | exact inherited 36 identities after moving the parity harness outside runtime `src`; zero C04 edge added |
| disposition register | PASS with source-byte verification and corruption probes; 261 roots, 8 censuses, 200 `rebind_pending`, and 23 seeded negatives |

### Fence receipt

- The C04 diff is confined to dashboard providers/tests/tooling,
  `packages/atlas-ui`, and this DS4 journal. The register is unchanged because
  `ui-tokens` honestly remains pending; debt manifests are unchanged at
  `75/22`, five Vitest identities, and 36 architecture identities.
- Backend `src/**`, schemas, generated runtime client, v15 archive, frozen
  Russian locale, master plan, lockfile, main, and other worktrees remain
  untouched. Full `designTokens.ts` sunset is not claimed; it still requires
  C17 consumer completion and DS6 evidence.
