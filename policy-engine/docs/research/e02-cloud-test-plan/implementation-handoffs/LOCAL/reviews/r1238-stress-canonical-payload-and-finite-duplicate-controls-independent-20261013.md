# R1238 — independent review of R1222 R2 stress controls

**Decision: GO for the two focused tests after root applies the virtual patch.** Both repairs make the intended discriminator reachable without changing product code or weakening assertions. The selected-schema variant now preserves producer payload bytes, and the D4 duplicate variant uses actual selected finite reports so the duplicate-component guard, fresh resolver, and Level5 refusal are reached.

## Frozen inputs and exact postimages

- Current frame: `root-author-source-frame-r1235-20261013.json` SHA-256 `e0ee2e79f53de2bb2b975058506307fc3e6973beabffefbb347d93fc994b594d`; HEAD `51f1db1a47d17c6ee3ccedbdf3f2cc85eb8d4960`, tree `5a4d54dcfdb37d2b47373326d1747de8d7014082`, branch `codex/e02-unified-local-20261009`.
- R1218 failure-boundary receipt: `raw/composed-source11-real-consumers-actual-r1218-20261013/full-failure-boundaries.json` SHA-256 `31023fcd2034c05758936a7a4ae809bc0322d4889f468ce6ba252a92d796bbe2`. It records 218 cases (210 passed, 3 failed, 5 errors); the two in-scope failures were the wrong-basis-schema case and the D4 duplicate test.
- Candidate R1222 R2 patch SHA-256 `22ee05f5901696bdea1ff2c95d2d901be16bbded7101eb693ec6aa1b5ca14301`; R2 manifest SHA-256 `c5a3de4e7bf02e88687f21987158d5f0958932b884bea8438125e69589700970`; decision SHA-256 `b885593f0102ca1f9e036dfbae4d91401b03a7e07154cade10562ea036932607`.
- Physical test preimages still match the frame: `test_adversarial.py` `fc3e4612ed80411382393029a42447c47e19d70f012f732dddd0bc33e3b81c79`; `test_phase_d4_runtime_integration.py` `b23d3392b62a5d537a88a73d3e7c9063daeb5c8edffc9b82968bb3f24d7fc2d2`. No production paths are in the patch.
- Reconstructed candidate postimages match the R2 manifest exactly: `test_adversarial.py` `77b5e2fe6f4b6f2d5845e2ee3abbfde5d5dcf0cc2ab74016b7e7bb4cd92b9620` (40,394 bytes); `test_phase_d4_runtime_integration.py` `3ae8926bb79859299694f2cc0a2a99c7535f295d90e4105e3f78c4151a2ed872` (40,634 bytes). Both parse with Python’s standard-library AST. `git apply --check --whitespace=error` passed against the current checkout; no source was written.

## Control 1: schema-only variation of the produced basis

The existing adversarial producer persists `basis.model_dump(mode="json")` as the `StressOutcomeBasis` payload. R2 reads the payload from the actual selected basis artifact, validates that same payload for the other adversarial cases, and persists the unchanged payload under the alternate schema. The negative asserts equal `ArtifactID`, byte-for-byte equal CAS bytes, and a different `manifest_profile_sha256`. It then persists a report that selects that ref and requires `invalid/outcome_basis_unreadable` from the fresh resolver. The changed profile/schema therefore reaches the selected-schema read boundary while the producer body remains constant; it no longer changes both variables before testing the guard.

The neighboring reason-code controls are also tightened for report summary reconciliation, adversarial plan unreadability, stale plan profile, roster mismatch, and incomplete occurrence rows. These are exact source-owned statuses rather than a generic “invalid” result.

## Control 2: duplicate occurrences through the D4 consumer

The old duplicate case had no base report. The owner synthesized an empty unscored base, so merge returned `profile_mismatch` before validating duplicate components. R2 instead selects `stress_refs[1]` and its already-produced finite report as base, and the actual selected report at `stress_refs[0]` as the supplemental source. It asserts the source suite IDs differ, derives the expected scenario denominator and pass count from complete persisted basis rows, and runs a single-supplemental positive control. That control resolves fresh as `available` and recomputes the pass fraction from those rows.

The duplicate variant repeats the same selected supplemental report twice while retaining the finite base. Assertions preserve the full occurrence list and profiles: both supplemental `InputRef` rows remain; the base and both supplemental report rows are present in manifest order; every corresponding basis input is retained; and the persisted component list matches the base plus the two repeated source component groups. The report remains on the finite-binary profile, is `invalid/duplicate_component_id`, has no robustness score, and has no added denominator. A fresh resolver returns the same duplicate reason, and Level5 emits an invalid-score blocker with no score value.

The source resolver checks selected candidate identity before duplicate component IDs, then returns the duplicate guard before loading component bases. In this test the candidate and source refs are real and selected, the report lineage manifest is asserted in full, and the only repeated discriminator is the source component occurrence. Thus the result is not explained by the previous empty-base profile mismatch or a missing/malformed selected ref.

## Classification and limits

**P40: SAME_CLASS_DEEPER.** The two R1218 failures share the same broad test-control-fidelity class: each fixture was intercepted before its intended property. Their causes differ (payload changed during schema mutation; empty-base merge stopped at profile mismatch), and R2 widens both controls in one batch. This is not evidence of a product source defect. The change does not claim broad stress-path closure or S1 closure.

Configured Ruff 0.14.10 check and format pass for both full virtual postimages per the R2 receipts. No product imports, pytest, native run, or stress runtime was executed during this review. The two focused tests and broader fresh-consumer replay remain **UNRUN** until root’s composed wave. No formal closure is proposed; `closure_ids=[]`.
