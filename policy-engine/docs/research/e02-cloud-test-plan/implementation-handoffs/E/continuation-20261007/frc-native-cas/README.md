# FRC native ETS/CAS witness and A owner packet

The native `test_frc_01.py` positive now invokes the admitted `ForecastOwnerRequest` through
`ForecastOwner.run`, persists separate candidate-receipt and empirical-evidence artifacts in one
configured CAS, opens a fresh store, and consumes the refs through `RealValueOwnerGateway` with the
canonical loader. The independent oracle reads source rows and the separately persisted issued
intervals: linear training rows 1–30 produce bounds 31–34, and matching holdout rows yield 4/4 hits.
Six distinct time roles and source/method refs survive the fresh read. The old fictional mapping is
retained as a refusal control.

The shared fixture lives in `tests/_helpers/forecast.py`; the previous `_configured` alias remains
in the ForecastOwner tests for replay of existing packets. Core artifacts/canon use the existing
Core root bindings. No E producer source or A shared source is changed by this slice.

`a-owner-contract.json` records the available typed input and the remaining A default/HTTP path.
`a-status-reason.patch.txt` has three focused hunks for A review; it is a packet, not an applied
change to `generation_cycle.py`. `a-status-reason-tests.py.txt` contains seven real-CAS cases:
missing ref, resolved 0/4 floor failure, and five native resolver-refusal cases. The resolver reason
must remain the same across blocked tier, S6 limitation and disposition; stale estimator prose must
not overwrite it. The original native missing-ref test keeps its corrected, explicit reason
assertion and remains a failure until A applies an equivalent fix.

The independent-patch overlay is a separate diagnostic. Its PASS cannot be reported as an actual
A default/HTTP PASS. A must independently resolve and bind the admitted profile/request/source,
metric/unit/scale, split/horizon, pairs/counts/threshold, rule/purpose and six times, then persist its
own verifier decision and re-verify it on a fresh served read. E's candidate receipt, producer flags
and `verifier_provenance=not_established` do not supply that authority. Causal, treatment assignment,
policy and production recommendation purposes remain denied.

The scoped production-history follow-up is read-only and local only where a model-specific
calibration claim requires it. This synthetic native fixture proves generic wiring and numerical
coverage; it does not supply production history or institutional profile admission. Historical
finding ledger status remains partial; code review, check status and finding disposition are
separate. The implementation handoff pins the exact source and complete deciding outputs.

`independent-review/` contains the immutable reviewer’s moderate outputs and oracle scripts,
with each verbatim copy bound in `independent-output-copy-index.json`. `validate.py` recomputes
the complete saved output denominator, byte identities, JUnit outcomes and candidate tree,
and rejects four deliberate corruptions. Raw CAS fixture directories remain outside Git.
