---
plan_id: DS11-TRUST-POSTURE-DEBT-CLOSURE
title: DS11 trust posture debt closure
status: execution_approved
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
branch: codex/debt-d-ds11-trust-posture
baseline: 784d020148c56e9bfb3a3631909ba11232210a9f
surface_owner: task-d
evidence_owner: task-d
ratified_on: 2026-08-30
---

# DS11 Trust Posture Debt Closure

## Slice mission

Repair only the public-surface behavior demonstrated false by DS11's current page-level
accessibility suite, then reissue the bounded conformance evidence through the existing
trust-posture owner. This slice does not claim human comprehension, source-language
authority, independent accessibility certification, grounded performance, or governed
promotion.

## Ratified constraints

- `W5-K02`: a green page-conformance suite is evidence about the tested surface and
  scope, not evidence of human behaviour or comprehension.
- `W5-K06`: presentation and translation do not create authority absent from the source
  claim and its admitted evidence.
- `S0-K03`: test and record one plane at a time. Do not mix surface conformance,
  evidence admission, institutional countersignature, and claim reaction in one ruling.
- `S0-K06`: protected public claims fail closed on unknown authority. Candidate-grade
  observations may persist only with a declared limitation.
- C13 remains a conjunction: the independent receipt must bind current source bytes,
  printer configuration, computed style, preview, and print/viewport assertions. Task C
  owns the receipt reissue; Task D owns every dashboard source edit in this wave.

## Measured starting point

The historical page receipt is content-bound to 24 collected identities with 20 passing
and four failing. The current suite collects 25 identities; the previously failing open-run
snapshot has already converged. The three still-named failure classes are:

1. `src/test/a11y/color-blind-simulation.spec.ts:122` — semantic token
   distinguishability.
2. `e2e/a11y/routes.a11y.spec.ts:44` — axe `dlitem` structure on the run report.
3. `src/test/a11y/screen-reader-snapshots.spec.ts` — accessible export-action name.

The first execution run must remeasure this set. This plan does not treat the recorded
names as a substitute for current output.

## Surface mechanism

1. Exercise the real page suite without snapshot/update writers.
2. For each observed failure, state the semantic property, the implementation predicate,
   and one divergent case before changing source.
3. Repair the smallest shared source or test expectation that represents the semantic
   property. Do not add accessibility-only labels that hide the actual action or weaken
   the source-language claim.
4. Re-run the affected identity, then the complete page-a11y scope twice independently.
5. Canonicalize and compare the complete collected identity lists; both invocations must
   exit zero and be identical.
6. Append a current, scope-exact receipt binding both runs, the exact dashboard source and
   configuration, schema/tool versions, collection denominator, and W5 limitations.
7. Recompile the public posture through its owner and prove a corrupt binding is rejected.

## Capability chain and status

| Element | Planned evidence |
| --- | --- |
| Contract | Existing claim-posture schema plus the current-conformance receipt schema |
| Producer | No-writer Playwright/Vitest page-a11y runner and receipt compiler |
| Persisted artifact | Append-only content-bound current receipt and governed generated posture |
| Bridge | Existing posture compiler to generated dashboard artifact |
| Consumer | `/trust` route rendering the generated posture |
| Verification | Two independent identical runs, exact receipt node, corrupt-field rejection |
| Surface | Current page-conformance row with explicit W5 limitations |
| Semantic test | Real DOM/axe/token/name failures plus exact rendered posture tests |

Starting label: `verification_missing` and `artifact_missing` for current evidence. A row
cannot move to closed unless every element above is demonstrated. The external countersign
remains `artifact_missing`/`verification_missing` and is not part of this slice.

## Expected source corridor

- `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`
- `apps/runtime-dashboard/src/shared/theme/theme-light.css`
- The exact a11y specification whose expected accessible name is shown stale by current
  product semantics
- Append-only receipt and governed generated artifacts reached through owner commands

Any additional dashboard source path requires an entry in the execution journal stating
the measured failure and why the named corridor is insufficient.

## Acceptance signal

- Both independent invocations of
  `corepack pnpm --filter @polisyos/runtime-dashboard run test:a11y:pages` exit zero.
- Their canonicalized identity sets are identical and state the complete measured
  denominator.
- `test_current_page_conformance_receipt_is_fresh_scope_exact_and_content_bound` exits
  zero against the new append-only receipt.
- A deliberate corrupt-field copy fails the receipt checker.
- The rendered trust posture states only current scoped conformance and preserves the
  external-counter-sign and human-behaviour limitations.
- The C13 conjunction is either green against task C's receipt for final source bytes or
  is handed back with the exact source-binding dependency still open.

## Execution correction — bounded audit receipt surface (appended 2026-08-31)

The public-posture owner discovered during execution accepts only the historical blocked
receipt and is outside Task D's declared write corridor. The row's authoritative register
signal requires two independent green no-writer executions and an append-only,
content-bound current-conformance receipt; it does not require Task D to replace the
historical `/trust` projection. Accordingly, the current receipt is an **audit surface**:
raw runs -> recomputing receipt verifier -> committed receipt. `/trust` remains
conservatively historical/blocked and gains no current-conformance authority in this
wave. No generated posture or posture-compiler bytes are changed.

This appended ruling supersedes step 7 under **Surface mechanism**, the generated-posture
and `/trust` entries in the capability table, and the rendered-posture acceptance bullet
for this task only. The operative chain is runner + two persisted raw runs + strict receipt
+ recomputing verifier + corrupt-field negative + audit receipt surface. W5-K02 and
W5-K06 remain explicit limitations; external countersignature remains not established.
