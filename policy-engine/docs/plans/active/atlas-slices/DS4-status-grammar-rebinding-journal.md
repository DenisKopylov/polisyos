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
