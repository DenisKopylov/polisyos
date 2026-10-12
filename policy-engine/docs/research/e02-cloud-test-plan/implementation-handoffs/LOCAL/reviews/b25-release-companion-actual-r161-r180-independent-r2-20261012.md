# B25 source and release companion: bounded independent review r2

**Disposition: GO for the bounded four-source/test-path change and corrected release fragment.** This is a source and release-companion review, not a B25 closure or capability acceptance. It records the compatibility correction made after the first review and preserves the historical ledger posture.

## Reviewed bytes

The current working tree was at `e635319f150c55b529357888b582ec857220c3a6`. The four mechanism/test paths match the frozen B25 R2 postimages. The release fragment is the corrected post-review version; the single-field correction receipt records the original and final hashes.

| Role | Path | SHA-256 |
| --- | --- | --- |
| Estimator result and repeat-count mechanism | `policy-engine/src/polisyos/foundry/coupling/estimation.py` | `cac2c5a881a5d628182bac6e26a88aeb4169f1ae810d03fe220a7498342e08bb` |
| Registered method serialization | `policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py` | `2dc1b12c4e02d1c20bb25792e6c931039ec1c3cdd9a747abbcd3e040da0d568c` |
| Estimator semantic tests | `policy-engine/tests/unit/foundry/coupling/test_estimation.py` | `85ece3855aee6c6de626c8a9d4170891e04d56c9f6148ded081a7ffdb96c1060` |
| Registered-method serialization test | `policy-engine/tests/unit/foundry/methods/catalog/simulation/test_coupled_policy.py` | `c73d819215318dbd3f95c0d4e8e4a89716d019dbcbb08f0cb6f89143ca77f88d` |
| Corrected release fragment | `policy-engine/release-fragments/unreleased/2026-10-12-e02-b25-smm-repeat-denominators.toml` | `5e8d051ef57e1c5012525b6f074fdffe25f9ec3aa9b034aa2ef718139bfda838` |

The first release-fragment bytes were `d3aa9d960c93ff8f8bf5eccc1fc35dc0de30667ca8ba09d145f751fd70eb4407`. The append-only correction receipt at `LOCAL/raw/b25-release-companion-author-r181-20261012/compatibility-review-correction.json` (`8db85cc360a3db1f2cfce6e65ffb881252c972b25449cac5f35848765dec1ff9`) records that only `compatibility` changed, to distinguish backward-compatible additions from an unchanged constructor signature. The preimage declaration is `LOCAL/raw/b25-release-companion-author-r181-20261012/preimage-declaration.json` (`45e93ec998f77eb338668b521f12f1bc23af1c3c14559014965739b0d93e58ba`).

## Source and surface findings

`SMMResult` gains trailing defaulted fields: `required_moments`, `fitted_moment_counts` with a per-instance dictionary factory, `fitted_repeat_denominator`, and literal-valued `comparison_basis` / `optional_moment_status`. Existing construction forms remain valid; the generated constructor is extended, not unchanged. The estimator counts each required key (including a missing required key as zero) and every key returned by any repeat summary, uses the number of supplied summaries as the repeat denominator, and keeps only the required set in comparability and ranking. The selected fit carries its own counts and denominator. The registered `pure_step` output serializes those selected fields, and its output interpretation describes required-set loss and diagnostic-only optional moments.

The tests exercise partial optional coverage with equal means, seed-order invariance, selection unaffected by optional coverage, and a missing-required-moment candidate that cannot win. The registered-method test verifies the selected counts and denominator cross the `pure_step` serializer. R161 independently confirms all six tests in `test_estimation.py`, the one selected serializer test, and both named SIM03 negative tests passed.

No export declaration, registry, or compile/execute facade file is part of the change; the touched modules’ existing exported names remain unchanged. The release fragment accurately calls the change internal, labels the registered method output, and states that the added fields are compatible/additive. `public_surface_inventory_reviewed = false` remains appropriately explicit. The corrected API and limitations fields describe result diagnostics only and disclaim calibration, causal validity, persisted artifacts, workflow bridges, and external authority.

## Verification receipts and limits

- R161 receipt: `LOCAL/raw/b71-b25-la023-actual-selected-consumers-r161-20261012/command.json` (`98e1b6327f56d1d4e9405651cb37809a78a2f34ea69da148d30589eca7926306`), `junit.xml` (`4e2a036d9601f79ccfa07c8794fe3d68bb4be757ce023f2cdee9b65717ddbe90`), and `stdout.txt` (`baf69a318862187c760f88c40f2b96b7db84ae40d4a0f88ecf2d74284aabb805`). The full selected run has 48 tests and one failure; the nine B25-relevant cases listed above passed. The lone failure is `test_invalid_economics_producer_is_terminal_through_native_bridge_and_cas`, in `test_plg_03.py`, with a JAX branch `float64`/`float32` mismatch in `foundry/plugins/training_adapter.py`; root classifies it as LA1, outside these B25 targets. No ownership or full-suite pass is inferred here.
- R180 Ruff receipt: `LOCAL/raw/b25-native-root-ruff-r180-20261012/command.json` (`c5fbc63227d43a52697741a94c230bd67dbe7b4b89f4ff4427263feaa5de5a9d`). It ran Ruff over the four source/test paths with exit code 0 and empty stdout/stderr; recorded before/after hashes match the reviewed four postimages. This review did not rerun tests, Ruff, JAX, native execution, or persistence checks.

## Scope and disposition

The mechanism change is additive and bounded. It establishes per-returned-summary counts at the estimator and registered method-result boundary; it does not establish an SMM-specific persisted artifact, orchestration bridge, persisted consumer, or external surface. The existing capability label `surface_out_of_scope` and absence of G-acceptance remain in force.

Preserve the prior B25 P40 classification in `LOCAL/reviews/b25-repeat-denominator-author-r2-independent-20261012.md` (`e3dc3e0734baf4e207acc520376eb59350e75edb4fbc2b3c6a40d13597f19980`): estimator repeat-denominator completeness is `NEW_CLASS`; the owner-summary criterion-binding omission is `SAME_CLASS_DEEPER` of LA-033. This review introduces no new P40 code-repair class. Historical ledger status remains `closed`; current closure remains `not_adjudicated`; formal `closure_ids` remain `[]`. No closure decision is made by this review.

The initial compatibility sentence was the only blocking companion issue: “Existing function signatures ... remain unchanged” obscured the generated `SMMResult` constructor extension. The corrected wording now says existing callable parameters and exports remain compatible and that `SMMResult` adds trailing defaulted constructor fields. With that correction read back at the final SHA above, the bounded source-plus-companion review is GO.
