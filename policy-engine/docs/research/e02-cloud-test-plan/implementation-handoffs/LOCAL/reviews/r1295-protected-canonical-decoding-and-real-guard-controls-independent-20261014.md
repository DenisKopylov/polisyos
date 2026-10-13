# R1295 — independent review of the protected canonical-decoding fixture delta

## Verdict

**Static review: GO. Runtime acceptance: PARTIAL / UNRUN.** I found no material defect in the one-file candidate. It corrects the fixture's two persisted-model reads to use the already-established selected Core artifact reader before Pydantic validation, while retaining the intended lineage attack and both protected consumers. The patch is still unapplied and must pass the parent-owned composed runtime/native wave.

## Exact target and source boundary

- Candidate base: `codex/e02-unified-local-20261009`, HEAD `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d`, tree `1355896e91789026d21396d2b087c63827ab251b`.
- Source frame: `root-author-source-frame-r1267-20261014.json` SHA-256 `a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803`.
- Patch SHA-256: `94e8969d05a57277c709eb4cf31b8dafa3305304ba40fc94a53454d01824fa87`; one changed path, `tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py`.
- I independently read and hashed all 12 paths in the packet's protected source context. Every current file hash matches both the R1267 frame and the packet manifest (12/12); no companion source changes are hidden in this test-only delta.
- In-memory reconstruction of the import and two reader changes yields the declared test postimage `7945ea808ed01c4e04e33ef47fe38d9ac79689667519df6524f8c7772b3b6a30`. No repository source was changed.

## Property and test-oracle review

The historical R1276 failure is concrete: the fixture fed Core-canonical float tag objects into `model_validate_json`, which rejected both `high_confidence_validity_threshold` and `high_confidence_confidence_threshold` before the candidate-suite lineage guard ran. The candidate uses `load_core_json_artifact(store, selected_ref)` followed by `model_validate` for both the candidate and evaluation. This is the same decoder-before-typed-validation pattern already used by `_validate_predecessor` and the runtime consumer. `load_core_json_artifact` is an existing public `polisyos.core.artifacts` facade export; it resolves the selected manifest/profile, binds the payload identity, decodes Core tags, and checks declared-profile conformance.

The candidate-suite-edge mutation remains discriminating rather than shape-based. It writes the altered candidate and evaluation through the real producer APIs with selected refs; checks that the candidate payload bytes stay identical while its selected manifest profile changes; checks candidate/evaluation kind, media type, producer and schema; independently checks that only the candidate's benchmark-suite input edge differs; keeps the evaluation edge bound to the alternate candidate and original suite; and asserts the exact wrapped cause `claim_adjudication_predecessor_manifest_lineage_mismatch` at both replay and promotion. The new reader changes occur before those assertions and eliminate the prior pre-guard type failure.

The six parameterized variants remain in the same test and mutate distinct conditions: profileless suite history; unavailable selected profile; alternate suite profile with same payload; suite payload identity conflict; candidate suite-edge mismatch; and evaluation/candidate selected-ref mismatch. The first five are rejected at their corresponding selected-profile, resolution, payload, or lineage boundary; the sixth reaches the exact evaluation-candidate ref comparison. All six still exercise both `successor.verifier.replay_champion(...)` and `registry.consider_promotion(...)`, and the test checks the mutated persisted registry bytes are unchanged after both refusals. For the candidate-edge case, the inner cause is pinned; the other cases intentionally assert the common protected refusal wrapper rather than freezing each internal reason string.

No later assertion hides the two prior decoder failures: both persisted model reads on the changed fixture path are corrected, and the candidate-edge branch explicitly pins the target lineage failure. Other mutation cases do not perform these two local raw-byte model parses. The complete producer fixture retains selected refs for the suite, candidate, evaluation, and signed inputs; the tests remain fixture-level evidence only and do not establish an external evaluator issuer.

## P40 bucket and residuals

This is `SAME_CLASS_DEEPER` in the R1213 protected selected-source test-oracle class. The author widened the repair over the full affected quantity in this fixture branch—both persisted candidate and evaluation reads—instead of fixing only the first parse that failed. I found no third raw CAS-to-Pydantic read in that branch requiring another instance patch.

Residual: the patch has not been run through pytest/native after the change. Static source review cannot prove that the composed environment produces the intended per-case runtime causes. Keep `closure_ids=[]`; external issuer authority and formal G adjudication remain outside this test.

## Commands and actions

Read-only review only. I inspected the exact patch, R1276 failure output, the 12 frozen context files, Core selected-artifact decoding, the fixture producers, the protected verifier, registry promotion, and runtime intake. I performed no product imports, tests, native/DB execution, source/test edits, or Git mutations. Initial HEAD/status reads were used only to establish the review base.
