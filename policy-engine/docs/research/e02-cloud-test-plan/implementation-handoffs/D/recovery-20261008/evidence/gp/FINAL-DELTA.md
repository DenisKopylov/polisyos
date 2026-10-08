# Independent GP final delta

Tested immutable C11 `bdc94a82d2bc911f61e729635ebe2eb03774848f`, tree `b99374f46dd6971daf47fd200549e98d32f23f23`, from a Git source/test/profile/lock export. Later C11 `c1bffbd531b9b2c4339f073416c95d42d90ee317` has exactly identical named GP source/tests/conftests/helpers/profile/lock blobs, recorded in `latest-c1b-GP-input-equality.json`.

**Bounded numerical PASS and four affected native PASS.** Genuine native MLL fit/SingleTaskGP posterior agrees with independently computed NumPy Gaussian mean/full latent covariance for original fit, pre-append restore, native append, post-conditioning checkpoint restore, and second append after that restore. Maximum passing discrepancy is mean `4.44e-15`, covariance `1.58e-15` (explicit tolerance `rtol=2e-7`, `atol=2e-8`).

The transform-sensitive case uses full fit of ten observations at iteration 10, conditions observation 11, persists/restores, then conditions observation 12. Fitted parameters/transforms stay exactly equal; the actual full-fit size/iteration remain 10, with zero extra MLL fits. Scheduled iteration 60 at interval 50 invokes one real fit and passes the formula on its new basis. No fit is forbidden when the declared growth/schedule requires it.

**Specific removal detects the repair.** In another isolated source export only the two persisted full-refit counter restoration assignments are removed; metadata/state fields, real model-state load and conditioning remain. Initial fitted/restored and native append numerical positives still pass. Restored append performs one extra real fit and differs from the fixed-basis oracle. The new native checkpoint test fails with `[8,9]` actual MLL training sizes versus `[8]`. Both exit-1 removal commands are expected property falsifiers, not failing candidate gates.

Full commands, PID/wall/RSS, stdout/stderr/JUnit, fixed basis and synthetic model-state asset hashes are indexed in `final-gp-receipt.json`. Old G032 numerical positives and restored-append FAIL remain separately preserved in `baseline-receipt.json`.

This is a synthetic 1D GaussianLikelihood/ConstantMean/unit-amplitude RBF engineering witness; it establishes neither calibration nor scientific authority. Legacy snapshots lacking the recorded continuation basis/counters are explicitly rejected, not reconstructed. No production history/transfer CAS law, installed-artifact GP consumer, universal rounding law, cross-backend bit identity or portable G-freeze replay is claimed. Formal closure and source acceptance remain G decisions. Verifier made no product source/test changes.
