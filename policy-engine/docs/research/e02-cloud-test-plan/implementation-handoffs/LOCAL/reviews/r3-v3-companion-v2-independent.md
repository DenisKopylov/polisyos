# Independent delta review: R3/V3 companion v2

## Scope

Reviewed the unapplied v2 patch `LOCAL/raw/r3-v3-companion-patch-13e411da-v2.patch`, SHA-256 `55a291a9be60f5040671aecdb9498b2e76dd9195797a63e28052e0c189777f39`, against the preserved v1 review at `LOCAL/reviews/r3-v3-companion-independent.md`. No test or source was edited and no tests were run.

## R3 delta

The v2 change fixes the v1 receiver-observation defect. `_FakeRetrievalService.instances` collects every constructor receiver; the test clears that registry after `ControlPlaneService` construction, excluding its unused `self._retrieval` fake. The test then selects only instances with recorded `resolve` calls and requires a nonempty set. In the inspected NL source path, `_execute_nl_pipeline` creates the local receiver and calls its `resolve`; it is the single `RetrievalService(...)` construction in that method. The assertion checks both DTO and keyword values are exactly `prod_full`, so missing calls, default `None`, and an unrecognized or wrong profile cannot be silently accepted. The four-origin/durable cost assertions remain intact. This is now a receiver-bound behavioral witness, not the v1 field-name/adjacency proxy.

The registry is class-scoped and retains the last observed fake reference after this test, but the only reader is this test, which clears it before constructing its service. No other fake caller reads this registry; reruns also clear it before observation. I found no cross-caller assertion contamination in the current test module. Clearing it in `finally` would avoid retaining the receiver object until the next invocation, but this is a small test-process lifetime detail, not a correctness blocker.

P40 remains the same stale test-double/API class, widened to actual resolved receiver instances. The expected negative behavior is represented in the new witness: no actual resolve call fails the nonempty assertion, while any call with absent, conflicting, or unknown profile values fails exact `prod_full` equality. Existing production conflict/refusal coverage remains separate.

## V3 delta

V3 is unchanged from v1 and remains structurally sound: explicit unauthenticated `401/missing_bearer_token` is preserved; the fixture-issued `acquisition-operator` token with `runs.view` and matching tenant is used for the positive and post-corruption history GETs. No production auth behavior is weakened. This is source review only, not a selector pass.

## Disposition

The v2 patch addresses the v1 blocker and is ready to apply for the designated R3/V3 selectors. Do not report either selector green until actually run. No further source change is required by this review.
