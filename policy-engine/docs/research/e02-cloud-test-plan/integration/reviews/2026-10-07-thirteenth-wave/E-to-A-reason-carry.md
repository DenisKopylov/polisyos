# A reason-propagation delta against E's b2 failures

**Read-only delta review.** No tests were run, no refs or source were modified, and no production data was read. E's report at G _build/e02-g-continuation-20261006/E-gates-A-consumers.md describes seven committed JUnit XMLs for E source b2f2f65ea8884a6e2ffa3fc444cdf4bbb9157641, tree 4cbbed1d9392832729cab92c6615f9a1d03a41c7: 1,465 cases, 1,457 pass and 8 fail. These are measured failures for E's b2 tree only.

The A candidate compared here is 2605d13916f4dd38f216419562c04718ba4c2028, tree 9d47203aa2c631f0613d496925e1108438be0183. It and b2 share published base 198076863e143dea9f89f02734b13d50dae3eed5; b2 is not an ancestor of A2605. A2605 is therefore a changed, unrun candidate for these selectors. Do not repeat the eight b2 red outcomes as A2605 test results.

## Exact source comparison

| Path | b2 blob | A2605 blob | Reason-path finding |
|---|---|---|---|
| policy-engine/src/polisyos/runtime/quality/generation_cycle.py | 6ef5c7f8b760a9d76baba446001e3f7a62e29e33 | 2c0dc500c055624687b3b6f9ab74ebba5b3f6881 | The sole S10 reason writer and resolver path changed. |
| policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py | 29459ff167cad1e011a2de626a627b30d0336a01 | ea382413f735bd9f9af3dbd000bff08242626b8d | HTTP compile/run wrapper changed, but no S10, forecast, calibration, S6, or forecast-disposition reason mapping exists here. |
| policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py | 85d24cf2c2233a570ccf1274c6436df7c5aaa218 | b6da993dd1d922e19135f4f78f12775ed5505754 | Lifecycle changes include compiled-run persistence/projection, but no S10-specific reason logic. It is a generic artifact transport, not the reason owner. |
| policy-engine/tests/unit/remediation/test_frc_01.py | 2e70c6bfc908ad4d15096eec9cf5bb0b2b091a80 | 90c70911e6b7e7be78e09d52542f2c52e05b8c10 | Test source was substantially replaced; old b2 failures do not identify current A outcomes. |

Relevant A2605 hunks are in _resolve_s10_empirical_evidence, _s10_empirical_projection, _build_s10_forecast_inputs, and _s10_limitation_refs. In the A blob, _resolve_s10_empirical_evidence returns empirical_evidence_ref_missing when there is no resolver or no raw reference after resolution. _s10_limitation_refs still maps a resolver error to s10://calibration/fail-closed/<error-code>; this behavior was already present in b2 and remains unchanged for resolver-error cases.

A2605 changes the limitation helper in two useful ways:

- It passes the caller's calibration_status into _s10_limitation_refs. If evidence is unbound but the caller supplied a status, S6 now emits a fail-closed insufficient-history ref instead of an empty list.
- For bound evidence with a non-pass calibration status, it emits all projection failure_codes, rather than selecting only the first or falling back immediately to insufficient-history.

These changes address the code shape behind b2 cases 1–3: A2605's new test_missing_calibration_evidence_refs_stays_typed_blocked checks that a direct helper call with dates but no evidence refs/status record remains blocked and gets a generic fail-closed/insufficient-history ref; loaded projections now retain the failure-code list used for floor limits. This is not an execution receipt for A2605, and the direct-helper test deliberately expects generic insufficient-history rather than the old b2 test's exact missing-reference string. In the actual gateway route the resolver can produce the more specific missing-ref code. The new tests do not prove that an ordinary HTTP request traverses that resolver route or that tier and S6 show the same exact reason.

## The reason path that still appears lossy

The disposition reason remains a source-level residual for b2 cases 4–8. In A2605, _s10_empirical_projection builds a detailed reason from loaded evidence failure codes. However, when resolution fails, _build_s10_forecast_inputs starts from report-derived calibration_evidence; the report helper already supplies a nonempty forecast_authority_disposition_reason. The builder chooses evidence.get("forecast_authority_disposition_reason") before its fallback. The fallback is the only branch that appends [<empirical_evidence_error>]. Thus, for an unresolved/wrong-kind/wrong-time/wrong-rule reference with a generic report reason present, S6 can retain the typed resolver code while the ForecastSupport authority-disposition reason remains generic. That is the same divergence E observed, though it is not a measured A2605 failure.

The HTTP run_lifecycle.py changes do not repair this: the file has no S10-specific reason code, and the typed compiled-run artifact is passed/persisted generically. Keep the reason writer in A's quality generation-cycle path. Also keep the ForecastSupport forecast_authority_disposition_reason distinct from the run lifecycle's P20 normative disposition artifact; they are different contracts.

A2605's new FRC tests include test_gateway_rejects_temporal_roles_that_disagree_with_loaded_evidence, which checks the S6 time-mismatch ref, and test_gateway_preserves_missing_calibration_metric_as_distinct_from_observed_zero, which exercises a loaded evidence failure reason. Neither asserts that resolver failure codes survive into forecast_authority_disposition_reason. The test for a direct missing-reference helper call asserts the generic insufficient-history ref. No committed A2605 receipt in the reviewed handoff proves these changed tests ran on this candidate.

## Carry decision

- **Cases 1–2 (empty S6 / missing-reference reason):** Do not carry the b2 failures as current A measured reds. The A helper now emits a nonempty fail-closed S6 ref when an explicit status is provided. The direct-helper path intentionally reports generic insufficient-history; the actual gateway has a specific missing-ref code. Exact current gateway behavior is UNRUN, and current tests do not assert that the two paths converge on one reason.
- **Case 3 (floor reason collapsed to generic insufficient-history):** Do not carry as a current measured red. A2605 now returns every projected failure code, which source inspection indicates can preserve calibration_floor_not_met. Exact current positive-floor-failure assertion is UNRUN; the new test's status/denominator coverage is not a substitute for that exact discriminator.
- **Cases 4–8 (resolver reason lost in authority disposition):** The S6 fail-closed mapping remains present and can carry the specific resolver code. The disposition construction still prioritizes the generic evidence reason before the fallback that appends the resolver error. Record this as a current source-level gap / A-owned follow-up, not as an A2605 observed test failure. A should preserve the typed resolution error in the disposition reason at the canonical writer, while retaining the fail-closed tier and S6 ref. Add an exact negative assertion that changes resolver error (missing_ref, unresolved_ref, wrong_kind, wrong_time, wrong_rule) and observes the same decisive reason through the ordinary consumer.
- **HTTP and fresh-read consumer:** b2's old E-owned packet failures do not show that A's current default/HTTP consumer was exercised. A2605 modifies wrapper/lifecycle blobs but does not contain S10 reason-specific logic. Keep the ordinary HTTP reason readback UNRUN; do not label the whole capability consumer_missing because the canonical A producer path exists. The unproved capability slice is reason preservation/consumer verification.

**Minimal next A check after a separately admitted local slot:** use only the current FRC reason selectors at exact A2605, with full module origins and complete output:
1. tests/unit/remediation/test_frc_01.py::test_missing_calibration_evidence_refs_stays_typed_blocked
2. tests/unit/remediation/test_frc_01.py::test_gateway_rejects_temporal_roles_that_disagree_with_loaded_evidence
3. tests/unit/remediation/test_frc_01.py::test_gateway_preserves_missing_calibration_metric_as_distinct_from_observed_zero

Those existing selectors do not cover all five resolver-error/disposition combinations. Extend the narrow test owned by A to assert exact ForecastSupport disposition reason for one source/consumer pair and its reason-changing negative; then enumerate the five fixed resolver variants only if the generic mapping is not constructed from one canonical code path. Do not replay E's 1,465 cases or label the three existing selectors as proof of the five-case matrix. No test was run for this delta review.
