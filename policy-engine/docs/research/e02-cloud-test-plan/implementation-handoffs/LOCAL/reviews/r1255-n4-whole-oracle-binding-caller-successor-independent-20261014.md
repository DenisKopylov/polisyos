# R1255 — independent R1245 oracle-binding successor review

**Decision: GO for root to apply this test-only candidate and run the focused integration test.** This is a bounded static review of the oracle and its callers, not a native result or a V2 closure. `closure_ids=[]`.

## Exact slice and reconstruction

The candidate patch is `raw/r1245-n4-whole-oracle-binding-and-caller-successor-20261013/candidate.patch` (SHA-256 `823100354b070f632fabb1044deeae303b1c9425136c177deeb35d5ddc09f08b`). Its manifest, decision, review-inputs, and R1251 readback hashes are recorded in the companion JSON.

The two source files still match their R1235 preimages and the R1251 frame at review time, despite the root’s disjoint 26-path source advance. I reconstructed both virtual postimages in memory from the unified diff and verified their byte counts and SHA-256 values against the manifest. Both parse with Python’s standard-library AST parser. Current branch state is `codex/e02-unified-local-20261009`, HEAD `51f1db1a47d17c6ee3ccedbdf3f2cc85eb8d4960`, tree `5a4d54dcfdb37d2b47373326d1747de8d7014082`; source frame `root-author-source-frame-r1251-20261013.json` SHA-256 `67042261b1e1ec3af938fdd402c76dafa511b1f49123541bdc5593a7dab3defa`.

| Path | Current/R1235 preimage | R1245 virtual postimage |
| --- | --- | --- |
| `policy-engine/tests/_helpers/generic_n4_served_replay.py` | `ba86d5234f9adeeb30f59028210d68c03987e86a085d92a660954ca25d1f5190` | `44e65e07268734778aeb8bc9f591a24a3455a594319e799a0730faa50e8b9f0c` |
| `policy-engine/tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py` | `0a4a0aea753a4f5be80f805e7177db5bb6fd12c6f3b94038aa928715f716b6b7` | `97008f45343b85d2b0fa69cf169929497efb9425c362322a76cae02905ae3068` |

## Oracle and caller review

R1243 identified that the later legacy one-argument function shadowed the recording-bound helper, making the revised call fail before the route. R1245 removes that duplicate/stale body rather than leaving a marker or adding another workaround: the virtual helper AST has exactly one expected-output function and one assertion helper. The old generated-contract hash, disposition-field tuple, and mutable contract-path lookup are absent.

The expected-output helper is keyword-only on the recording ID and content hash and refuses any pair other than the fixed original capture. The assertion helper is keyword-only on those same identity values plus the current `design_problem_ref`; it checks the current parent ref and generated status, the full three-proposal disposition map, the declared candidate/diversity totals, exactly two generated candidates, distinct operator/target groups, and the expected proposal-to-group mapping. It returns the current atom hashes, which the unchanged child join requires to equal each derived child’s `source_atom_refs` in the corresponding operator/target group.

I checked all three executable assertion callers: the preparer’s real N4 result, integration-test preflight, and the served result captured at persistence. Each supplies all required keywords. The first receives ID/hash from the selected recording loaded by `_load_recordings`; the test calls use the prepared object, after asserting its recording equals the canonical selected recording and its ID/hash equal the fixed values. Their problem ref is derived from that prepared problem. The whole `policy-engine/src` and `policy-engine/tests` identifier search finds no other code caller; AST inspection confirms the expected signatures/call shapes. The two integration call edits leave the existing route assertions intact: ordinary POST, worker dispatch, stored completion, fresh GET, two child/profile bindings, two N5 observations, and candidate-only currentness/publication limits.

## Original criterion and source-hash limits

The original CYC-05 source in `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-05.md` quotes B15 from B_r19 lines 375–386: show effective limits and run a small real two-child decomposition through the existing recursion while preserving child relationships/results and not treating a budget stop as completeness. B29 (B_r19 lines 565–578) separately requires normal frontier stop, budget exhaustion, and abstention to retain distinct meanings. R1245 repairs the N4 test oracle only. It does not prove the focused test runs, the exact two-child budget-stop frontier, B29, or the full B15 criterion.

The canonical recording `layer3_gy_design_generation_replay_recordings.json` is SHA-256 `db5f892c19412e74ff78683901dd81e49ebb446f75eb394d254cc75d7c74ae71`. Its selected record ID is `gy_n4_replay_20260704_095710_425807_7bf5552df372`, problem ID `gy_n4_cgf_decisive_capture_1_20260704_092222_049411`, and declared content hash `sha256:107f896fb1fd1c37170b74c88726c07169277d05d3ec5459ceb360919e692cb1`. Recomputing the repository’s documented time-stripped canonical-JSON hash with standard-library code, excluding the stored hash and the configured volatile fields, yields the same value. The parsed capture contains tax relief for `global.tax_rate`, procurement stabilization for `cells.distress_score`, and a credit-guarantee proposal targeting `agents.access_to_credit`. The expected two bound groups and blocked third proposal also match the existing generation-contract row (contract SHA-256 `5ad08223d43ee0b86a70822ab103eabb7d7ff81419e941c6a68cdf6b36c824af`, its compiled problem ref `sha256:92a39b5c7853b1965ce46bbbefc9bd579a0f169da315f35d117e7effd1788fac`). That row is only a static cross-check; R1245 no longer uses a mutable compiled-ref lookup as its oracle.

The recording hash establishes integrity against the committed fixture under the repository’s canonicalization. The record’s `recording_source` label and hash do not independently establish provider authenticity, custodian provenance, or currentness. The candidate correctly leaves those claims outside this test.

## Verification boundary

I did not apply the patch, import product modules, run pytest, or run any native/runtime gate. Root should apply this exact two-file candidate and execute the focused integration test before reporting an actual served positive. The current test-only evidence remains candidate-band; both children completing is the intended positive. The exact two-child budget-stop frontier, B29 terminal projection, external authenticity/currentness, and formal closure remain unestablished.

P40 is the **same oracle-binding class**, widened to the complete helper definition and all three callers; this repair consumes no new ladder round. Relevant patterns are P29/P32/P33/P35/P38/P40/P41. `closure_ids=[]`.
