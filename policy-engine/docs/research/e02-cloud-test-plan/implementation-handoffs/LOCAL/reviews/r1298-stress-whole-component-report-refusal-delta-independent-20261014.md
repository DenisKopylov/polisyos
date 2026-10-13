# R1298 independent review: R1294 refusal-composition successor

**Decision: GO to Root’s bounded focused verification.** The R1294 test-only successor addresses the full same-class sibling set exposed by R1293: it checks the lower component resolver’s exact refusal and the fresh report resolver’s common available-score refusal for each persisted basis negative case. It also checks the missing-candidate cause at both boundaries and preserves the distinct typed partial/no-score outcome. This is a source/test review, not a runtime or pytest pass.

## Exact packet and baseline

- Checkout: branch `codex/e02-unified-local-20261009`, HEAD `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d`, tree `1355896e91789026d21396d2b087c63827ab251b`.
- Source frame: `LOCAL/root-author-source-frame-r1267-20261014.json@a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803` (590 paths).
- Candidate patch: `LOCAL/raw/r1294-stress-whole-component-report-refusal-oracle-successor-20261014/candidate.patch@a5e49676d0d0b73cf3b0e83ed13a6943ac11377ff62cde11353f1b48fe984234`.
- Adjacent manifest: `manifest.json@834f6a6375bd6a3fdac84f35159907b29b5d84ba97a75fc2cac69640d722d7d0`; decision: `decision.md@e5d5a5d5016d306e199e628d1f5fb3659713f9e7d3b5cbd9d84181b2314a81e3`.
- The only footprint is `policy-engine/tests/unit/scientist/search/test_adversarial.py`. The physical preimage hash is `77b5e2fe6f4b6f2d5845e2ee3abbfde5d5dcf0cc2ab74016b7e7bb4cd92b9620`. I reconstructed all six unified-diff hunks in memory against that file; the result is `5dd7672b00044cde1ea0da273bbcb104b17bdc26898298c19a1891b0fc16bdde`, exactly the manifest postimage. No product or candidate file was changed.
- It supersedes R1285’s patch `57612e91d260fffc014ecef937e71ef8c35fb560729c8db48219d6353ae08472`, manifest `17eddb79b5e6925e7ee9eeb82e7daac73da755d97b800c50ac398b5fa1b2271d`, and decision `12fae9bf61ea4231940eea4c9882373cedcbb938481b2621f3fba54f3a194c96`. R1285 remains preserved as the earlier, narrower candidate reviewed BLOCK in R1293.

## Property coverage

I inspected the complete test function in the one-file footprint (the current preimage’s AST contains the full producer/resolver call set) and the exact resolver and producer sources. `run()` calls the real `run_stress_test` with `cas=store`; the producer writes the plan, outcome basis, and report to `FileSystemCAS`, resolves the basis before setting the report’s available score, and persists that report. The negative controls read back the selected producer refs and persist new reports/bases into the same CAS. They do not stop at constructors or marker strings.

The new `assert_basis_refusal` helper performs both checks for each of the four existing basis corruption cases: direct `resolve_stress_score_components` must return its exact status/reason and no score; then `resolve_stress_report_artifact` must freshly read the persisted report and return `invalid / score_claim_without_resolved_basis` with no score. The covered inner causes are:

- Wrong selected plan schema: `invalid / adversarial_plan_unreadable`.
- Wrong outcome-basis schema: `invalid / outcome_basis_unreadable`.
- Missing selected plan profile: `unbound / adversarial_plan_profile_missing`.
- Forged occurrence roster: `invalid / plan_outcome_roster_mismatch`.

The missing-candidate case separately asserts direct `unbound / current_candidate_ref_missing` and the report-level `invalid / score_claim_without_resolved_basis`, both with no score. The forged-roster path passes its actual persisted forged report reference into the helper rather than silently generating a different report. The partial case separately asserts the direct and fresh-report `partial / expected_occurrence_rows_incomplete` results with no score. That preserves the semantic distinction: the report is marked `partial`, not `available`, so the report-level available-claim guard must not collapse it into the invalid-score refusal.

This is the complete current refusal-precedence class in this test, rather than just the first wrong-plan case: the alternate-candidate report is rejected at report lineage validation before component resolution; summary corruption is rejected after successful component resolution; direct wrong-schema/legacy/profileless candidate controls call only the component resolver; and the one/ten and mixed top-k cases are positive controls. The test keeps those separate assertions intact.

## Source and adversarial controls

- The component resolver validates the selected basis and plan, including selected profile, kind/media/schema identity, candidate binding, and the ordered outcome roster. For a missing plan profile it returns `unbound`; malformed selected schema or roster cases return their own component-level refusal.
- The outer report resolver calls the component resolver. When a component result is not available and the persisted report claims `score_status == "available"` or carries a score, it changes the public result to `invalid / score_claim_without_resolved_basis` and clears `robustness_score`. This is intentional precedence, and R1294 now checks both the inner cause and outer public refusal rather than expecting the outer API to preserve the inner code.
- The producer creates the available-score positive from the real plan and finite basis. The selected wrong-plan control reads that persisted plan body, writes it with the same kind/media but a wrong schema profile, and asserts the same content-addressed artifact ID with a different manifest profile. The wrong-basis-schema control retains explicit equality of the original and wrong-profile CAS payload bytes, equal artifact IDs, and different profile hashes. The resolver’s selected-manifest/schema guard remains the actual decision path.
- Assertions check semantic status, reason, and `robustness_score is None`; they do not merely check that reason-code markers exist. The positive producer path and existing recomputation assertions remain. I did not run a property-removal mutant or pytest, because this review is limited to static source/patch inspection and the root task holds test execution for the bounded verification wave.

## P40 and disposition

- **P40: SAME_CLASS_DEEPER, widened.** R1293 found that three sibling cases remained masked after R1285 corrected only one. R1294 changes the test mechanism to cover the four basis-level refusals as a shared component-plus-report check, plus the missing-candidate and partial-status boundary cases. I found no remaining same-class outer-reason assertion in the complete current test function that still expects the inner reason from the report reader.
- **P38:** The component boundary decides whether the selected basis/plan is admissible; the report boundary decides whether a claimed available score is freshly supported. Their outputs intentionally differ for malformed evidence. A wrong-schema basis is one divergent case: inner `outcome_basis_unreadable`, outer `score_claim_without_resolved_basis`, score cleared. The helper asserts both properties.
- No product behavior, score calculation, authority, or schema is changed. This is a GO to a focused root test run only; native/pytest execution remains **UNRUN** by this reviewer, and `closure_ids: []`.
