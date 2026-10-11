# Independent review: runtime promotion reason-precedence test repair

## Verdict

Static GO for the test-only patch, with the two focused selectors still required after application. The patch changes only the two stale expected reason strings in `tests/unit/runtime/quality/test_promotion_sequence.py`. It does not change a producer, resolver, calibration rule, receipt status, authority claim, or fixture. No test/import/lint/runtime command was run for this review.

P40 bucket: **SAME_CLASS_DEEPER**. The first failure exposed an obsolete expected reason; the second direct assertion in the same module is the same defect. The whole bounded quantity is the two current-receipt assertions found in the test module. The patch updates both rather than creating a per-assertion repair chain. Frozen history that intentionally compares old and current reasons remains unchanged.

## Pinned inputs and scope

- Source-bound deciding capture: base `fd5feb3714fe0395157940027259fe10180db4e0`, tree `5cde4060cd0cf9f13033a9b54ab460adeaf46a26`; the capture recorded 6,160 input paths.
- Command manifest: `LOCAL/raw/batched-blocking-focused-20261010/runtime-promotion-first-real-failure-boundary-20261011/command.json` SHA-256 `9f9dacef1335a0500c66a15d4f75602c4022cf318232adb411dd056c3bd99f49`. It ran `python -B -m pytest -vv --tb=short --maxfail=1` over `test_acquisition_world_growth.py`, `test_graded_outcomes.py`, and `test_promotion_sequence.py`.
- Deciding stdout: `.../stdout.txt` SHA-256 `f3ba26950f1b53f5b969a7637e472f359bba76ced6af00808bc422008f86917b`; JUnit SHA-256 `d8d17c4889192d0ded4aa4a504855eac57e272488ddb782d55c54ed7888f8dd4`; stderr was empty. It collected 177 tests, ran 13 passes, then stopped at the first failure after 40.108594s. The failure was the stale expectation at line 423. The two later expected-reason assertions were not both executed by that run.
- Test preimage SHA-256 `8175f936bc311b80a645681c3b2cf0ee1013ab2d4f66013841182611b725c1a0`; candidate postimage SHA-256 recorded by the patch author `eba17d969546fd412a7b9414cb764c740f81884012c7db26ce536fecc3a0f219`.
- Patch: `LOCAL/linux-profile/raw/runtime-promotion-reason-precedence-20261011.patch`, SHA-256 `c3f341f69ba3b6b7ff6151ac12dba13e24330720a1393091f08e337881441507`.
- Runtime resolver bytes: `grounding_bind.py` SHA-256 `7bcd8296cae2258dd52ce4ea5062d84a95bf65cc0a3609527d47adfb7ad37ec9`; promotion-sequence bytes in the capture `f44a8ebdda14eab958ba7842f4cec0bff8706796943057eac05cbfa85a46bcda`; calibration bytes `23e965c99b0460fe2a803e46baf799778111005d4989c5d3fd0ba1c0e0736671`. Current checkout still has only the known import/comment delta in `promotion_sequence.py`; the resolver-related code is unchanged. The test source itself remains at its captured preimage.

## Source and test relationship

Both affected receipts flow through the test helper `_promotion_input()` to `_cg2_contract_bind()`, which obtains a certificate using `GroundingBindGate.for_contract_testing(...)`. The binding decision constructs `run_admission.synthetic` from `authority_scope == "contract_testing"` (`grounding_bind.py:1227–1230`). The resolver checks `certificate.synthetic or _synthetic_reference(...)` first and returns `synthetic_input_cannot_grant_authority` (`:1403–1404`); `non_production_anchor_scope` is a later branch for a non-synthetic input whose stored scope is non-production (`:1421–1422`). Thus the new expectation matches the live resolver precedence for these synthetic contract-test certificates.

The patch preserves surrounding assertions. In `test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow`, the assertions still require `promoted is False`, `status == "shadow"`, the `contract_testing` lane, `consumer_promotable is False`, no authority trace, zero spend, failed calibration, and the `non_anytime_valid` ledger refusal. The recorded run failed at the old reason assertion before executing the later assertions, so those controls remain to be verified by the post-patch focused run. `test_contract_testing_bind_receipt_is_intrinsically_non_promotable` also still asserts not promoted, contract-testing lane, and non-promotability.

The source retains `non_production_anchor_scope` for the later non-synthetic branch. `check_layer3_gy_promotion_contract.py` deliberately compares an older frozen receipt with that reason to its current synthetic successor with `synthetic_input_cannot_grant_authority`; the patch does not rewrite this history or the source reason branch. No fixture is promoted to production, and no synthetic input is treated as authority.

## Required follow-up and limits

After applying the test-only patch, run the two selectors:

- `test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow`
- `test_contract_testing_bind_receipt_is_intrinsically_non_promotable`

Retain their full output and JUnit. A focused PASS will verify the formerly-unreached ledger and status assertions as well as the second reason assertion; it will not establish production-grade grounding, currentness, or a positive promotion path. No formal G closure is proposed here.
