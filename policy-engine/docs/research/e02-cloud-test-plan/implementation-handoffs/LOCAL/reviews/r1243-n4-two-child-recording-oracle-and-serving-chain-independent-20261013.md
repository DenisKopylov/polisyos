# R1243 — independent review of the R1229 R2 N4 two-child candidate

**Decision: BLOCK this virtual candidate before native execution.** The intended recording-bound semantic join is stronger than the stale-ref oracle, but the helper postimage defines `_assert_original_second_capture_generation_result` twice. Python binds the later, old-signature definition, so the updated fixture call raises `TypeError` before the ordinary POST is reached.

## Bound inputs and reconstruction

- Current branch: `codex/e02-unified-local-20261009`; HEAD `51f1db1a47d17c6ee3ccedbdf3f2cc85eb8d4960`, tree `5a4d54dcfdb37d2b47373326d1747de8d7014082`.
- Source frame: `LOCAL/root-author-source-frame-r1235-20261013.json` at SHA-256 `e0ee2e79f53de2bb2b975058506307fc3e6973beabffefbb347d93fc994b594d`. Its physical-postimage map names 575 source paths; both candidate preimages below match the frame exactly. The parent identifies this as receipt-only advancement from R1210.
- Candidate: `LOCAL/raw/r1229-n4-two-child-real-producer-consumer-readiness-20261013/candidate-r2.patch`, SHA-256 `57e877aa2607e91e39a51dd78a2dea0760815d10f54ab17c9b53b7abc9966579`; manifest SHA-256 `ea38421e7f62a843c9fc2cd90973625e8da173c1aab00afbe8584de98348793c`; decision SHA-256 `54596d2729f0353d980f4afdceb1d0cfc47253736d5f5a2eb61c1cc8ce20995c`.
- I reconstructed the two-file virtual postimage in memory and parsed both files with the standard-library AST parser. No source, index, or Git state was changed; no product imports or tests were run.

| Path | Current preimage SHA-256 | Reconstructed R2 postimage SHA-256 |
|---|---|---|
| `policy-engine/tests/_helpers/generic_n4_served_replay.py` | `ba86d5234f9adeeb30f59028210d68c03987e86a085d92a660954ca25d1f5190` | `9434bdb227639c0be0cf1b390531a8363fe0b2f447ba3f9c05143feaa903c583` |
| `policy-engine/tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py` | `0a4a0aea753a4f5be80f805e7177db5bb6fd12c6f3b94038aa928715f716b6b7` | `97008f45343b85d2b0fa69cf169929497efb9425c362322a76cae02905ae3068` |

## Blocking defect

The helper postimage contains definitions at lines 188–255 and 276–310. The first accepts `design_problem_ref`, `recording_id`, and `recording_content_hash`; the later definition accepts only `design_problem_ref`, so it shadows the new function at module load. The revised `prepare_generic_n4_served_replay` call passes all three keyword arguments. Therefore the selected integration test fails during `prepare_generic_n4_served_replay`, before its ordinary `POST /api/v1/control/runs/nl`; Python reports unexpected `recording_id` for the bound later function. The integration test's own preflight/served calls also pass the new keywords and would hit the same shadowed binding.

The stale body also retains the old contract lookup by current `design_problem_ref` and refers to `_ORIGINAL_DISPOSITION_FIELDS`, which R2 removes. Those stale references reinforce that the old body must be removed, not merely left unreachable by convention. The required repair is one canonical definition with the new recording identity parameters, with all callers matching it and no references to removed constants; then rerun the exact selected test before claiming the route.

## What is sound in the intended change, and what remains unproved

R2's replacement oracle binds the selected immutable recording ID and content hash, then checks the live generated result by complete proposal-disposition mapping and proposal-to-candidate-ID-to-operator/target group. The child join binds the generated candidate atoms to actual derived child groups and source atom refs. This fixes the R998 stale-selector mechanism in principle and is materially stronger than comparing against an old candidate hash or a contract row keyed by a recompiled parent ref.

The integration test is structured to exercise a real recorded request through ordinary control-run POST, persisted worker dispatch, N5/CAS production, and a fresh run GET, rather than supplying a caller-authored child graph. That is only a static reading of the candidate: R2's manifest says runtime and pytest were not run, and the shadowing defect prevents reaching the route as written. Do not transfer the historical R998 result to this source state as a pass.

The exact two-child positive expects both children to complete. The separate first-child-success / later-sibling-stop budget frontier remains evidenced only by a three-child synthetic overlay, so this candidate does not establish the exact two-child budget-stop property in B15; B29 and external authenticity/currentness are also outside this test. Candidate profiles/source remain limited test evidence, not production authority; the decision correctly leaves `closure_ids` empty.

## Pattern disposition

- **P40 bucket: NEW class.** R998 failed because a historical oracle selected by the recompiled `design_problem_ref`. R2 changes that intended selector but introduces a distinct Python name-binding defect: a duplicate stale function shadows the replacement. Do not treat the new binding failure as proof that the semantic join itself is wrong; remove the duplicate definition and re-evaluate the exact route.
- **P29/P33/P38:** the candidate has a real producer/consumer-shaped test design, but a static AST parse is not a runtime witness. The divergent case is the duplicate definition: markers and the new function body exist, while Python calls the later old body. Native verification must execute the selected test and show the request reaches the intended producer and fresh consumer.
- **P35/P41:** scope is the two manifest-listed files and their exact frame-bound preimages; no claim is made about a full-suite denominator or a current native gate. The source frame confirms the candidate inputs are unchanged at this review boundary.

**Closeout:** BLOCK until the shadowing definition is removed or replaced, then perform the exact focused native run with its complete output. `closure_ids=[]`.
