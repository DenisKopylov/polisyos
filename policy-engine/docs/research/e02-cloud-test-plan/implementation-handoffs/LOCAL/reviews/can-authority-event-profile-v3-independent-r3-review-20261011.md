# CAN authority event profile V3 r3 independent review

Disposition: **GO to apply as candidate-only source**. This is an independent source review, not runtime verification, G acceptance, integration publication, or finding adjudication. `closure_ids` remains empty.

## Exact candidate and admission

- Checkout HEAD: `0390c44e7f9871122c21afa78af844cbafaa1d0e` (tree `33e1305efb43bb01960faf65808449cc4bd7a891`).
- Patch: `implementation-handoffs/LOCAL/raw/can-event-profile-v3-final-composition-r3-20261011/net.patch` @ SHA-256 `44fd136d425dba460d84be81ddeeb39e5c9c3fe8942f477dd5d66ce49c09a1cc`.
- Composition: `implementation-handoffs/LOCAL/raw/can-event-profile-v3-final-composition-r3-20261011/composition.json` @ SHA-256 `a2607b4dccce9bf20d8df4c321a0a55a1cfbc90154cb70d653925dddd80568a2`.
- Static check: `implementation-handoffs/LOCAL/raw/can-event-profile-v3-final-composition-r3-20261011/source-static-check.json` @ SHA-256 `852bb1f5a4472f1c72fefdedb10e366c406bc65dd434e2345b1370570b8d04fe`.
- All 18 existing file preimages in the 19-path manifest matched the checkout; the added release fragment has no preimage. `git apply --check` passed. No product source was applied by this reviewer.

## Reviewed behavior

The r3 patch closes the prior review escapes at shared mechanisms:

- The event resolver and authority reconciliation use one fixed event manifest check covering exact kind, schema name/version, and `application/json` media type. The adversarial test binds a same-byte `text/plain` manifest profile into an authority payload and asserts that the actual `reconcile_authority_ref` consumer refuses it.
- Report-profile extraction preserves suppliedness. Explicit `None` at either the outer report or nested diagnostic-event field is malformed and mismatches a selected envelope profile; genuine field absence remains the profileless compatibility case.
- The legacy-v2 test makes the actual default event and payload manifest views profileless, preserves the stored event bytes and durable event identity, and exercises `reconcile_authority_ref` through its passing consumer path.

These are meaningful controls for the exact prior same-class-deeper findings. The patch continues to state that profile selection proves neither producer authority nor live currentness; filtered inventory remains scoped to the visible selected artifact and active tenant.

## Remaining verification and authority limits

Author-provided Ruff/AST/static admission is not a runtime receipt. The focused event-profile, reconciliation, consumer/removal, and composed-stack tests remain **UNRUN** until root's single frozen replay. Legacy profileless compatibility in the described v2 case is source/test coverage only until that replay passes. No external issuer, production custody/currentness, or authority claim is established by this code review.

Recommended deciding replay: the relevant artifact-store, authority-envelope and authority-reconciliation tests on the exact composed source; retain full output, and include the same-byte wrong-media refusal plus profileless-v2 consumer control. A marker-preserving removal of the shared media check should make the negative control fail.

This review accepts no formal G closures; independently classify each linked finding occurrence after the composed run.
