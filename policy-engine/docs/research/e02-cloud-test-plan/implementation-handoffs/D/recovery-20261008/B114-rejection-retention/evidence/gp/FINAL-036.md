# Fresh affected GP state witness — source 03698439

Tested immutable source `03698439abfb1cb59f763397a182d8e0e393d40d`, tree `dde25e8efa4a8ce5322bdcad176720fa0894a635`. The new B114 rejection ledger changed `get_state`/`set_state`, so the previous numerical PASS was kept separate and the affected witness was run freshly after exact-source review and coordinator resource release. Source/test/profile/lock export and full method AST delta are in `final-036-source-manifest.json`.

**Bounded numerical PASS:** genuine native Gaussian GP posterior agrees with the independent NumPy mean/full latent covariance formula for fitted state, restore, append, checkpoint after conditioning, restore of that checkpoint and next append. Ten-row full fit → condition row 11 → checkpoint/restore → condition row 12 preserves fitted parameters/transforms and the full-refit size/iteration 10, with zero extra MLL fits. Due iteration 60 at interval 50 performs one real MLL fit and passes on its new basis. Maximum passing discrepancies: mean `4.44e-15`, covariance `1.58e-15`.

The unchanged independent harness uses the original synthetic basis and retains its negative lengthscale substitution; markers/native parameters remain unchanged while the altered oracle basis disagrees. This run's rejection ledger is version 1, complete, with no rejected records. Nonempty rejection history and cold/adaptive planning are separate native tester evidence, not a numerical conclusion.

Complete output, actual import origins, PID/wall/RSS, raw synthetic state hashes, and exact input identity are in `final-036-gp-receipt.json`; deciding output/asset integrity was read back. No native four/32-case wave was repeated and no source/tests were changed by this verifier. Previous G032 FAIL and bdc/c1 bounded PASS/removal packets remain preserved.

The fixture is finite, scalar, 1D and synthetic; this establishes engineering conformance within its declared Gaussian/RBF/transformation basis. Production history/issuer/calibration law, installed-artifact GP consumer, universal numerical law, portable replay and formal G closure remain unestablished.
