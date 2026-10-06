# Independent S10 verifier review

This review covers candidate `331cffecd64a98152a9933e0f3f3d19caae53dfb` at tree `fc9321208b738924fb4118c8ce25f0ce130b2cd3`, based on `198076863e143dea9f89f02734b13d50dae3eed5`. The attached source worktree was at receipt commit `320cecb698f9b1ebd7fd37350e3bf6da3086066f`, whose parent is the candidate. The E producer was inspected at the exact commit `5bd27323ecb0935a38908d2b09fa652762c5e4ea`, not an older ancestor.

This was a read-only source review. I read the implementation, the six test cases, the exact E source, the closure decision, and the implementation handoff. I ran no tests, no numerical ETS checks, and made no changes to product source.

## Findings

### Model/policy references are not resolved by A

The property is that model and policy scope members exist as the expected CAS objects before A treats their scope binding as verified. The current code checks only repeated IDs and roles: report-manifest edges at `forecast_verification.py:255-275`, report/evidence metadata at `:481-503`, and the scope-binding payload at `:899-914`. It never resolves the model or policy refs from CAS.

A content-valid report, empirical-evidence artifact, and scope-binding artifact can therefore repeat the same `model_spec_ref` and `policy_spec_ref` IDs while the referenced CAS objects are missing or have wrong kinds. The marker checks still agree. The exact E producer normally resolves the pair in `forecast_owner.py:513-517`; A’s independent check cannot rely on that producer path for a forged receipt.

This is a P38 proxy boundary for any statement that A verified model/policy scope. It does not invalidate the bounded numeric replay because the result remains `predictive_only` and `source_scope_status=not_established`. To claim scope binding, A should resolve both members, verify manifest identity, expected `ir.model_spec` / `ir.policy_spec` kind, JSON profile, and content bytes/digest. The falsifier should remove or change the actual member while preserving all report and scope-binding markers; A must block.

### C source admission remains absent

A resolves the typed `fabric.data_snapshot` and then calls `_resolve_json(store, snapshot.data_ref)` without an expected kind or an admitted C profile (`forecast_verification.py:193-207`). `DataSnapshot.data_ref` is a generic `ArtifactRef` (`core/contracts/fabric.py:161-173`). Consequently, a hash-valid JSON artifact of another kind can supply a metric vector and support numeric replay without proving C admission, source scope, unit, valid-time, version, or completeness.

The E producer uses the same generic resolution at the reviewed `5bd27323e...` source (`forecast_owner.py:519-532`), so this is a missing source-admission boundary rather than an A-only regression. The candidate explicitly keeps scope, unit, and source-time `not_established` and returns a predictive-limited result. A’s closure decision requires an admitted profile binding those fields and says a positive served witness is UNRUN without a compatible admitted series (`closure-decisions/A.md:129-143`). Retain that limitation until the actual C profile is wired and tested.

## Numeric replay assessment

I found no source-level bypass in train-only ETS replay or paired holdout/count/rate recomputation. A reads the request’s split from the content-resolved series, runs the registered ETS method on the training slice, verifies the stored training slice against those source bytes, and checks each reported prediction, interval, and held-out observation against the replay. It recomputes the hit count, horizon denominator, pass rate, and threshold, and checks the persisted uncertainty bundle against replayed intervals and sample counts.

This conclusion is source inspection only; no tests or numerical execution were performed by this reviewer. The existing six tests are bounded isolated controls. They do not establish a CAS-backed positive, forged content-valid scope mutation, or served POST-to-GET lifecycle. The handoff correctly labels the property basis `not_established`, the candidate `implemented_but_not_orchestrated`, full CAS-backed positive `verification_missing`, and served lifecycle `semantic_test_missing`.

## Review disposition

The code supports only a limited predictive recomputation proposal. Do not claim S10 credibility, C-admitted source scope, model/policy content binding, or default served orchestration from this candidate. The review JSON alongside this report records the pinned commits, findings, falsifiers, and unrun boundaries.

## Delta addendum: model/policy CAS resolution

This addendum reviews only candidate `263729e956c74e123695bd97edee0001d970aae3`, tree `e84673a5cc2439aab5e3af7f12986bc5778589b3`, with receipt commit `be8f8d53597b8cdd480a28b9ab023c34facf5726` and base `198076863e143dea9f89f02734b13d50dae3eed5`. The source worktree was clean at review. I did not run tests, ETS, or numerical checks.

The prior P38 model/policy finding is closed for a supplied pair. `_verify_resolved_chain` calls `_validate_model_policy_content` before the evidence/report chain (`forecast_verification.py:189-192`). The helper rejects incomplete or duplicate refs, resolves the request IDs using canonical `ir.model_spec` / `ir.policy_spec` kinds, and passes the content through `_resolve_json` integrity checks and `load_model_spec` / `load_policy_spec` (`:471-510`). This closes the old marker-only divergence: retaining report and scope-binding IDs while removing a CAS member or changing its kind/content no longer satisfies the new member-resolution predicate.

The delta adds five focused source tests: a valid pair, unknown Core fields for each spec type, a wrong model manifest kind, and an incomplete pair. The updated handoff records 11 focused tests passed at the new candidate; I inspected that receipt but did not replay its tests. No numerical or full-chain positive result is claimed.

Disposition is **GO for a limited predictive-recomputation proposal only**. The separate C-source boundary remains open: no admitted profile binds source scope, unit, valid-time, version, or completeness. Default gateway/HTTP orchestration and read-time GET re-verification also remain absent. Therefore this is **NO-GO for full scoped S10 credibility or served acceptance**. The publishability recommendation is `source_pending_g_not_accepted`; the model/policy fix does not change the original C/default-bridge limits or establish capability closure.
