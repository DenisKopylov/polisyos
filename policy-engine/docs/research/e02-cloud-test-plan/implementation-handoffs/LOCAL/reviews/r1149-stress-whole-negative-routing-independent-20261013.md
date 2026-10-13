# R1149 independent review: R1145 stress negative-control routing

**Decision: GO for Root’s narrow native replay of these two test modules.** R1145 corrects the R1143 wrapper-level expectation and pins the distinct direct resolver branches. This is a scoped test-delta qualification only: no pytest/native replay, product imports, or formal closure was performed here.

## Frozen input and exact source qualification

- Worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`
- Current HEAD `5fd4096ab9389d15abcedb00b03b968f6b60c953`, tree/index `d65d5ba135001d29968734cb0bace6fe50a572b8`; tracked source diff was empty.
- Candidate’s declared source frame is R1141: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1141-20261013.json@1484c711f50c356b3707b1d76b98371dfa5ecf01048aa859055bb0768a953fff`. Both changed test preimages at current HEAD match the manifest exactly.
- Candidate manifest: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1145-stress-whole-negative-control-routing-20261013/manifest.json@7e2681e1491eaa6e85a0ae3a1a33f3f59a8c199c9b8bb5b9143b5caf4945c0e5`.
- Patch: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1145-stress-whole-negative-control-routing-20261013/delta.patch@f902c97dade7297de4e43349d5477c788f9b9c0edf8ddb1605e9822cc0e55728`.
- The only changed paths are `test_adversarial.py` (preimage `d39ae3e0…5b55cd3b`, postimage `6cf89a86…f3941ea0`) and `test_phase_d4_runtime_integration.py` (preimage `cc9072f1…561fb38`, postimage `d1ce5d1b…9c88bf6`). Full hashes are in the JSON receipt.
- The previous independent R1143 BLOCK remains preserved at `reviews/r1143-stress-native-basis-schema-test-companion-independent-20261013.md@fc2ec016f0a7dca8243c1c4673d6093fa0ab55afb9785cdc8ffbf0c0bbaf81ca` and `.json@3469d8de1e3fc50aa8bc22e777483c48683021c069a2de8d2995af471b69ad87`.

## Source-path review

The full candidate body is read from the canonical selected candidate ref and reused for the alternate write. The test keeps the intended identity distinction explicit: same artifact ID, different manifest-profile SHA. It then calls `resolve_stress_report_artifact` and now expects `invalid`, exact reason `stress_report_lineage_mismatch`, and no score. This matches the outer consumer: `resolve_stress_report_artifact` validates required report inputs before reaching the direct score resolver; `_manifest_has_input` compares both artifact ID and manifest-profile SHA. The report manifest was already asserted to contain the original candidate ref, so this alternate selected profile fails the wrapper’s exact lineage check.

The two later direct checks now cover the inner resolver separately. A canonical-kind ref with the wrong selected schema reaches `_load_selected_model`; the resolver catches that read failure as `invalid / current_candidate_manifest_invalid`, which the patch pins. A selected ref with the legacy noncanonical kind hits the earlier kind guard and returns `unbound / current_candidate_ref_not_canonical`, also pinned. These are distinct branch outcomes; the assertions do not allow a list of interchangeable reasons.

The D4 test’s wrong schema ref has a selected profile. `_load_stress_test_report` therefore follows `_load_stress_report_source`’s selected-ref path, which reaches `_load_selected_model` and raises `selected_source_schema_name_mismatch`. The revised regex is correct; the later Level-5 invalid assertion is retained.

The finite top-k behavior and its controls remain unchanged: one-versus-ten vulnerability counts, available resolutions, exact occurrence denominator, recomputed score values, mixed-outcome checks, and Level-5 blocker behavior. The delta only moves the single full-body read earlier and strengthens negative-control status/reason assertions.

## P40 and verification

This is the **same P40 class one level deeper** as R1143’s test-control routing finding. R1145 widens the correction across the whole relevant negative-control route: outer report lineage, direct selected-schema refusal, and direct noncanonical-kind refusal. It fixes the class for the bounded test path rather than adding another wrapper-only expectation.

Independent static verification reconstructed both complete postimages in memory from the patch and matched all manifest preimage/postimage byte counts and SHA-256 values. Both passed `ast.parse`. Product Ruff `check` and `format --check` on both complete stdin postimages passed (4/4), invoked from `policy-engine/` with their actual source-relative filenames. The patch’s `git apply --check` receipt is recorded by the author; I did not apply it.

The R1136 JUnit remains prior-source evidence only: 180 cases, 152 passed, 26 failed, 2 skipped (`junit.xml@eeed6c0665d3b78683bb71649cc638509ed1959fba51729a441bc2c80623f325`). Native/pytest replay is **UNRUN**. Root may use this GO for the narrow native replay, not repository acceptance. `closure_ids=[]`.

Pattern pass: P29 behavioral top-k and consumer assertions remain; P37 status reasons correspond to the actual predicates at each resolver layer; P38 the test distinguishes exact lineage from direct kind/schema checks; P40 same class widened to the actual three-branch negative path; P41 R1141 preimages were confirmed unchanged at the current receipt-only HEAD.
