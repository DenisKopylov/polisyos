# Final narrow R13 delta reconciliation

## Boundary and denominator

This closes only the two remaining findings, RXE-04 and RXE-06, within the established 13-row denominator: `GYD-16`–`GYD-22` (7 verification rows) plus `P0-ACCEPT`, `P0-REBIND`, `FINAL-FREEZE`, `FINAL-REVIEW`, `FINAL-REPLAY`, and `FINAL-USE` (6 execution rows). I re-read only the updated `FINAL-REVIEW` and `GYD-21` proposal rows; the other 11 rows were not re-reviewed in this delta.

No tests, builds, product sources, production data, or product gates were exercised. This is proposal-level verification only; the actual accepted E02 tree remains not established and no product acceptance is implied.

## Findings

### RXE-04 — CLOSED AT PROPOSAL LEVEL — MEDIUM — `FINAL-REVIEW`

- **Exact anchor:** `preferred-solutions.json#/tasks[task_id="FINAL-REVIEW"].implementation_steps[4..5]`.
- **Counterexample:** A reviewer could declare a bounded residual for a capability that already exists at the canonical owner or relevant consumer surface, thereby continuing instance-level repairs instead of reusing or widening that mechanism.
- **Delta:** Step 5 now requires inspecting the canonical owner and relevant surfaces, confirming that the smallest closing capability does not already exist, and citing source-bound search/consumer evidence. If absence is not established, it requires continuing reuse/widening instead of treating the capability as unavailable. That directly rejects the counterexample and satisfies the P40 residual-absence condition.
- **Smallest coherent fix:** None remains for this proposal gap. The canonical-owner/surface search and its evidence must still be performed when the procedure runs; no such execution evidence was reviewed here.

### RXE-06 — CLOSED AT PROPOSAL LEVEL — MEDIUM — `GYD-21`

- **Exact anchor:** `preferred-solutions.json#/tasks[task_id="GYD-21"].preferred_solution` (final sentence), `.implementation_steps[1]`, and `.acceptance_discriminators[3]`.
- **Counterexample:** If actual consumers alone define applicability, removal of a required GX hardening edge could be normalized as “not applicable” while another validator still consumes the artifact. Separate artifact and validator counts would not reveal the missing required pair.
- **Delta:** The proposal now derives expected artifact×validator pairs independently from the original requirements and native schema/property contracts before reading invocations. It compares expected pairs with actual resolved inputs, prevents actual consumers from declaring away a missing edge, and permits `not_applicable` only when supported by source criteria/contracts—not because execution is missing. The pair-removal discriminator requires pair-level failure even if another validator covers the artifact.
- **Smallest coherent fix:** None remains for the identified denominator gap. At execution, the source-derived expected relation and actual consumed-pair relation must be materialized and compared; this review did not run that reconciliation.

Both remaining findings are closed at proposal level. This result does not establish the accepted-source mappings, canonical-owner availability, validator behavior, or any product gate outcome.
