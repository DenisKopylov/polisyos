---
title: "DS4 Status-Grammar Rebinding Journal"
type: execution-journal
status: blocked_before_implementation
created: 2026-07-18
revised: 2026-07-18
slice: DS4
plan: ./DS4-status-grammar-rebinding.md
branch: codex/atlas-ds4-status-grammar
baseline_commit: 71f438ad52f668e1feb7510652ff5fd3b735bd62
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
