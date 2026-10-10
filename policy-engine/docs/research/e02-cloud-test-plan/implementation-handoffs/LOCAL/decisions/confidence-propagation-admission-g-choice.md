# G choice: confidence admission for propagated uncertainty

## Decision requested

Should PolicyOS ever admit propagated simulation intervals as policy-gating confidence evidence, and if so, which independently trusted verifier may attest the exact source/input/draw/output basis? Until that authority and producer handshake are selected, keep the current status: propagated intervals are candidate diagnostics and remain blocked from normative confidence admission.

## Current evidence

- `src/polisyos/ir/analytics/uncertainty.py:2177-2180` says the current producer does not persist successful draw-to-input identity rows or a trusted verifier receipt. The consumer binds the selected simulation, envelope, report, and manifests, recomputes available draw-count and sample-summary checks, then returns no admitted envelope.
- `src/polisyos/ir/analytics/uncertainty.py:2323-2327` explains and emits `draw_success_ledger_missing` and `draw_basis_verifier_missing` as final limitations. The present API therefore has no genuinely admitted positive result to reuse in a test.
- `src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py:456-515` emits the current report payload and persists it without manifest input edges. The consumer’s `_check_report_lineage` at `src/polisyos/ir/analytics/uncertainty.py:2439-2454` requires the report to bind the metric envelope and at least one input envelope. This is an additional producer-to-consumer gap before an admitted positive could exist.
- The former “healthy” test envelope supplied `identification_verified`, `proof_status`, `verifier_role`, and a fabricated digest as envelope metadata. Those fields do not establish an appointed verifier or content-bound evidence. The repaired tests retain the no-envelope empty-result positive, classify this metadata-only envelope as typed limited, and exercise the real `PropagateUncertaintyNode` → persisted CAS → `ConfidencePass` path; the actual producer output still includes the draw-ledger/verifier limitations.

The tests record behavior only. The controlled propagation input and calibration test data are not external evidence and make no authority or production-currentness claim.

## Smallest closure if a positive gate route is authorized

1. Ratify a typed, append-only successful-draw record bound to the exact selected simulation view, each input-envelope view and bytes, draw identity, output metric/value, and the denominator/failed-draw records.
2. Appoint or identify the verifier authority and its scope, version, provenance, and trusted receipt format; the verifier must independently recompute the denominator and content bindings rather than accept producer metadata.
3. Have the propagation producer persist report input lineage to the exact input and output envelopes, and emit the draw-to-input record plus verifier receipt.
4. Have the confidence consumer resolve and content-bind those records and verify the appointed provenance before using the interval for a gate. Missing, malformed, wrong-scope, stale, or tampered evidence must remain typed limited.
5. Add a real producer → CAS → verifier → confidence-consumer positive test and mutate each binding/receipt while leaving labels intact to prove refusal.

This is new verification/authority work, not a test-fixture patch. Without the decision in step 2, the smallest honest state is `verification_missing`; a positive admission test would have to invent a verifier, external fact, or authority law.

## Pattern pass

P05/P10/P29/P31/P37/P38/P40 apply. The old fixture tested metadata labels where the consumer’s property is independently admitted evidence. The repair preserves a real negative and the no-input optional positive, while the real-producer test asserts the current limitation. Do not add a route-specific exception or treat another self-labeled envelope as a new class. An unverified producer result remains `verification_missing`; its caller may use the existing typed limitation but cannot promote it to gate authority.
