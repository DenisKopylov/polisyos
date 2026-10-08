# E FRC evidence delta review

Read-only review of docs-only E continuation `2e28bed33d179d1d0f9db4b6cbb3837d809c42c0` (tree `6f3ff36401d8507abc9e099d1cf74ec37f54aad3`) versus `781acab7a66ac7bbbd40d5a007fae22379e32e85`: 336 changed paths, all under implementation handoffs; zero product source, tests, or release-fragment paths. Its new receipts measure the frozen source candidate `64d7444a18c55df7b88b71b7699a2f1b25ca24bd` / tree `aef23574d3162abb19bf5a1c67d02624ff9d4d1d`. Do not attribute results to other G source edits after that freeze.

## Measured source binding and result

`frozen-wave-64d/source-and-owner-inputs/source-freeze-64d7444a.json@2e28` binds the source freeze to G checkpoint `ebae80eaa25482d84bc6ad2e78721bc318bc0228` and E profile source `700f9d5a5e2167787d7042ca11e1ef3bf80ced74`; it records a clean source and complete source reviews. The exact `bkt-frc-s10-and-adjacent-report-consumers.json@2e28` and `cal-and-welfare-consumer-retry.json@2e28` bind to candidate 64d and its tree. Their run receipts record the same tracked-source frame before/after, so these are measured-source observations, not conclusions inferred from a status field.

The resumed calibration/welfare consumer suite at 64d passed **324/324** after its earlier attempt ended by signal `-9`. That retry does not test the missing FRC S10 reason path. The separate BKT/FRC/S10 consumer suite at the same 64d source failed **8/321** (313 passed). One failure is the existing product test `test_missing_calibration_evidence_refs_stays_typed_blocked`. The other seven come from the new external owner packet `frozen-wave-64d/wave/owner-packet/test_a_frc_native_cas_status_reason.py.txt@2e28`:

- Missing empirical ref does not emit the expected `s10://calibration/fail-closed/empirical_evidence_ref_missing` limitation or matching disposition reason.
- Limited evidence with recomputed 0/4 coverage returns `insufficient-history` where the owner packet expects `calibration_floor_not_met`.
- Missing, unresolved, wrong-kind, wrong-time, and wrong-rule refs return the generic “Foundry report was missing” disposition instead of their resolver-specific reason.

The packet exercises A’s `RealValueOwnerGateway` and `_build_s10_forecast_inputs` consumer with E’s `ForecastOwner` fixture and a fresh CAS resolver. Its docstring labels the tests as expected A-owned failures. The measured source still contains the A S10 projection at `runtime/quality/generation_cycle.py` and the unchanged failing assertion in `tests/unit/remediation/test_frc_01.py`; the 64d and 781 blobs for these paths match. The new consumer evidence therefore confirms the earlier A-owned S6/status-reason gap remains on measured source; it does not resolve it.

## E producer result and boundary

The bounded E producer witness remains useful: the prior immutable native result at `1eba9f9e47a82cca1db341314a748b4980e015fc` records 29 PASS / 1 A-owned failure, with a synthetic independent 1..30 forecast oracle, positive 4/4 holdout and changed 0/4 holdout, persisted candidate/evidence artifacts, fresh CAS reads, and a native `RealValueOwnerGateway` consumer. The 64d wave’s added adversarial A packet strengthens the failure evidence; it is not a replacement product patch. The scratch-only A overlay that passed its own tests is not present in 64d and is not product-source acceptance.

The API-owner packet at `final-publication-r4/postfreeze/forecast-api-owner/packet.json@2e28` is bound to 64d/tree aef and says no supported serializer route is available, the identity patch is reviewable but unapplied, and capability state is `surface_missing`. These tests use the native gateway with injected resolver; no default HTTP/served route or production source/issuer authority is demonstrated. E’s bounded predictive evidence must not be promoted into that claim.

Disposition: GO for the bounded E native producer/CAS witness; HOLD/limited for A’s S10 reason projection and for served/public API closure. The independent E result remains code acceptance only, not B32/LA-051 finding closure. This review ran no tests and made no source, test, or Git-ref changes.
