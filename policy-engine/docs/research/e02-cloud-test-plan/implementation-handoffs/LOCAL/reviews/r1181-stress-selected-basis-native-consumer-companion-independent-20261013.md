# R1181 independent review: R1178 selected-basis consumer controls

**Decision: GO for Root’s narrow native replay of the two affected test modules.** The candidate exercises the actual fail-closed wrapper outcome and compares the full selected input sequence, including basis references and duplicate occurrences. Native/pytest remains unrun; this is not acceptance or formal closure.

## Frozen input and footprint

- Worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`
- HEAD `4ba921b8241afa732d69d6b7ef8c6c43af9bc58d`, tree `45e8e04359ac64f554e45cb26ea054f8c857f38e`; tracked source diff empty.
- Source frame `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1172-20261013.json@785f588be67983a6de503efe8fb64307caf1693d5af6134386da718d9974a66b`.
- Candidate manifest `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1178-stress-whole-selected-basis-consumer-controls-20261013/manifest.json@5633d0b1ddb045c4ec0e78d82c0a21f8b7b71b893d295bcdb3935d8da87cdf74`; patch `.../delta.patch@8d7f10b927e897ac7702a484890693f9ad7dd4395c915b633bf32cb5b22f8d33`.
- Both current test preimages match the candidate manifest. Complete virtual postimages independently reconstructed from the patch matched its sizes and hashes. No source, index, or Git writes occurred.

## Source-traced outcomes

In `test_finite_occurrence_basis_is_freshly_recomputed_and_top_k_independent`, the report is a selected, score-bearing report. With `expected_candidate_ref=None`, its outcome-basis edges still resolve; the direct score resolver returns unbound for missing current-candidate context, and the report wrapper converts that result to `invalid / score_claim_without_resolved_basis` because the persisted report claims an available score. The patched assertions pin that wrapper result and absent score. The existing direct legacy-kind case remains a separate `unbound / current_candidate_ref_not_canonical` control. This matches `resolve_stress_report_artifact`’s source path and preserves the distinction between a direct intake refusal and an invalid available-score claim with unresolved basis context.

The D4 writer’s source order is candidate ref, optional existing base report, supplemental refs in their input order, then basis refs for the resulting score components. In this test, the state starts without an existing stress-report ref, and the duplicate call uses a fresh empty `ExperimentState`; therefore the expected full lists correctly contain candidate, supplemental report occurrences, then their outcome-basis refs. The new assertions compare complete `InputRef` lists (role, artifact ID, and manifest-profile SHA), not just role names or counts. The duplicate case checks both repeated supplemental refs and repeated basis edges, while retaining the existing duplicate-component invalid result. The actual merge function extends source components without deduplicating them, so those duplicate basis occurrences are expected.

The earlier top-k, recomputed denominator/score, mixed-outcome, source lineage, and Level-5 checks remain unchanged. `InputRef` is already imported in the test. The actual producer appends all basis refs from `report.score_components` after supplemental refs, matching the new expected order.

## P40 and verification

This is **SAME_CLASS_DEEPER** than the preceding negative-control routing review: the candidate widens the test to the actual wrapper status conversion and the entire emitted selected-input quantity, including the repeated-occurrence case. It closes the relevant test-oracle gap without changing producer behavior or weakening source, candidate-binding, schema, recomputation, top-k, or duplicate-component controls.

Independent static verification reconstructed both complete postimages in memory and matched all manifest preimage/postimage hashes; `ast.parse` passed. Locked Product Ruff `0.14.10` `check` and `format --check` passed for both complete stdin postimages (4/4) from `policy-engine/`, using the real test-relative filenames. `git apply --check` is an author receipt only; the patch was not applied. No product imports, pytest, native, DB, or heavy execution was run.

## R1175 receipt-count correction

The cited raw JUnit is `.../LOCAL/raw/independent-search-stress-grounding-native-consumers-actual-r1175-20261013/junit.xml@5ed47ce70dea58730132e38b53f4db50ab54deff9c551ed26e95242773585101`. Walking its complete 216 `<testcase>` elements gives 153 passed, 58 failures, 5 errors, and 0 skipped; the XML suite attributes agree. The R1178 manifest’s prose says 153 passed, 58 failed, 5 skipped, which mislabels the five error cases. The two targeted stress tests are actual failures in that JUnit; the five errors are separate credal-reference cases. This does not block the narrow replay, but correct the run summary before using its aggregate counts elsewhere.

**Scope:** GO only for Root’s targeted native replay of the affected tests. R1175 is prior-source evidence; no test/native replay was performed for R1178. `closure_ids=[]`.

Pattern pass: P29 the negative wrapper and full manifest properties are behaviorally asserted; P37 absence of expected candidate is degraded to invalid for the available-score claim; P38 complete selected edges and cardinality are checked; P40 the same class is widened over the relevant consumer output; P41 exact preimages are bound to the frozen frame.
