# Independent V6 test-classification review — 2026-10-10

**Verdict:** GO to apply the classification patch for its stated scope. It separates the local partial-checkpoint mechanism witness from the source-positive claim and turns the actual known historical-L2 refusal into a served-reader negative. This is not a V6 positive or closure. Keep V6 source-positive `UNRUN / held`; the current input cannot produce a truthful positive. No tests were run for this review, and the patch remains unapplied.

## Exact review boundary

The patch artifact is `LOCAL/raw/v6-local-negative-external-positive-classification.patch`, SHA-256 `6827e7640c0eb852550febeea069055b58b1a3a8409f194e933657eb5b8202f7`. The target file is still its recorded preimage, `tests/unit/runtime/http/test_control_service_di.py` SHA-256 `78606569994f94ebe0fbc32bafa8385e9dc422f14fba5dd0a5d265f6d4ffb310`; the decision packet is `LOCAL/decisions/v6-test-execution-classification-20261010.md` SHA-256 `31fede402359722b8585ccfa632fdd01cb75097e5cee295ce0fab2b311f97949`.

Source anchors read during the static review:

- `src/polisyos/runtime/http/services/control/generation_cycle.py` — `c4492d44e17df4c18364bf1e23aee3dd9c346d3a12f3b689e341e86c288f35c9`
- `src/polisyos/runtime/quality/design_generation.py` — `3cea32f0016aaccf22cb2aba2216b6ee0aefe777abc6e50548eb063a3bc84411`
- `src/polisyos/runtime/quality/generation_source.py` — `8b399470e10afe538b87f8616b64bbf2bc512327f83c7c4483478f23c233c6bd`
- `tests/integration/runtime_quality/test_configured_candidate_simulation_served.py` — `493cfa355ca545cd8e3c8e7928fc7746cd935ab445ff495019cfeacf14671833`
- `LOCAL/decisions/v6-candidate-alternative-prototype-executed-20261010.md` — `2f81390b8a246aaaafc6f8f77ea3f492d5b765d45f5d5c1d6d1680da40cbf07f`

The baseline decision packet and the earlier independent source-history review are useful context, not evidence of execution of this patch. The latter is `LOCAL/reviews/v3-v6-current-property-independent-20261010.md` at SHA-256 `a4f42f7e4557532e262fcc99d82757324f7f61c3f21159d858ad7fc6d4137c4e`.

## Patch findings

The patch renames the two-sibling fixture mode and test to `local_sibling_mechanism_witness`, makes the sibling node refs visibly local-mechanism refs, and says in the helper and test docstrings that these refs are not source-derived and do not prove V6. It no longer manufactures child profiles/contexts by mapping the root profile onto derived child problems, nor claims resolved child lineage from that fixture. It retains the useful controlled N5 persistence, later sibling error, fresh GET checkpoint and corrupt-artifact refusal as bounded mechanism evidence. This is the right P40 response to the earlier false source-positive: preserve the mechanism observation but stop treating a substituted graph as the property.

The other added assertions preserve the known-withheld selected source through the compiled artifact and fresh GET: `generation_unavailable`, `not_established` child profile, `n4_recursive_source_generation_not_complete`, empty child bindings, and a separately loaded `candidate_scenario_n5_only` source with the registered historical vintage, no forwarded L2 confidence and no credal payload. These are appropriate negative assertions; they do not claim that the candidate-only root N5 is a recursive child result.

I found no static scope escape in the patch: the fake graph is no longer labelled as actual lineage, the exact source-positive assertions were removed from that local witness, and the typed withholding fields remain explicit. The patch must still be followed by its stated focused runtime replay after application; this review alone is not a test receipt.

## Positive gate and exact next check

There is **no existing runnable V6 positive selector** in the reviewed source. The nearest existing integration selector, `tests/integration/runtime_quality/test_configured_candidate_simulation_served.py::test_served_configured_profile_runs_real_n4_through_candidate_n5_and_rejects_drift`, exercises a real root N4/candidate-N5 path. Its test assertions do not cover a derived-child graph or later independent sibling failure. The other integration path in that file asserts the current negative (`generation_unavailable`, no child bindings). The patched unit sibling selector is explicitly only a local mechanism witness. Consequently the phrase “separate input-bound integration gate” in the decision note should remain a proposal/held check, not be counted as an existing test or verification.

The source does have a usable producer seam, so this is not evidence that a new runtime mechanism is required. `compile_and_run_recursive_generation_cycle` accepts `root_n4_generation_client` (`generation_cycle.py:1055`) and passes it to an actual `N4GenerationPort` (`:1296`). It persists and reloads the owner-scoped root source; only an actual `GenerationUnderAResult(status="generated")` proceeds to `derive_n4_candidate_child_problems` (`:1353–1360`). Each resulting child must then resolve its own same-job profile/context handoff before bindings are emitted (`:1380–1437`). The existing source derivation enforces the exact generated-result type and content/lever relationship. Replaying a recorded N4 client while omitting an admitted current-L2 source would simply repeat the previous source-substitution error.

**Next check, once an owner supplies a qualifying current-L2 source and profile tuple:** add or extend one explicitly named integration selector that feeds that tuple through the existing root N4 client seam and actual `compile_and_run_recursive_generation_cycle`; assert the persisted root source is `generated`, derive the children from that exact persisted result, resolve distinct child profiles/contexts under the same job/run/tenant/cell, let the first actual child complete N5, and inject the independent second-child failure only after its exact child ref is selected. Then read the persisted output through a fresh `GET /api/v1/runs/{run_id}` and assert exact root/child N4, context, N5-input and result refs, successful N5 plus exact sibling failure, and refusal after corrupting the referenced child artifact. Preserve `currentness_status=not_established` wherever it is not independently proven, candidate-only authority limits, and no S8/N9/publication claim. Do not restore the old hand-built child list or use `N4CandidateScenarioProposalRun` as `GenerationUnderAResult`.

That selector is not runnable honestly today: the named inputs lack a current-L2 artifact with a source-owner/custody binding, selected profile/purpose, producer/rule version and effective-time/currentness basis. The executed alternative prototype shows the present candidate-only route reaches actual L6-linker refusal, then `n4_recursive_child_source_untyped`; this is the expected withheld boundary, not a failed fresh reader. Classify the external input as `input_missing`/`artifact_missing`, the source-to-CYC02 binding as `bridge_missing`, and the full source-positive check as `verification_missing`/`semantic_test_missing` until the exact source and owner receipt arrive. The existing static test and producer seams do not manufacture that fact.

## P40 and disposition

P40 bucket: **SAME_CLASS_DEEPER**. The class is the whole current-L2 source → generated root result → exact derived children → per-child context/profile → persisted child N5 → fresh GET partial result/error path. The present blocker is the missing admitted source/currentness basis upstream of child production. This patch correctly stops trying to repair that blocker with per-fixture child/profile substitutions and records an honest local mechanism witness. No further patch to this local fixture is warranted. The source-positive remains held for the bounded owner input and the named integration check above.

## Evidence and limits

Read-only commands used:

- `shasum -a 256` over the patch, decision packet, target test, source files, relevant prototype and prior review; output is recorded above.
- `rg -n` over the current unit/integration tests and control-generation source to locate the sibling selector, configured-profile selector, result-status/child-binding assertions, and `root_n4_generation_client` seam.
- `sed` reads of the patch hunks, helper, integration selectors and producer path.

No tests, product commands, Git operations, source edits or generated-artifact updates were performed. The patch artifact SHA is the only reviewed proposed delta; the target product test remains at the preimage SHA stated above. Formal closure is not proposed (`closure_ids=[]`).
