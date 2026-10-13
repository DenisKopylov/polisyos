# Independent delta review: R715 Core JSON producer conformance

**Disposition:** `GO_FOCUSED_NATIVE_WAVE` for the R715 successor, with no closure IDs. This review is scoped to the static-quality delta from previously reviewed R714; it does not claim a clean strict mypy run or production/API acceptance.

## Bound inputs and exact composition

- R715 full successor patch: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r3-core-json-producer-conformance-r715-ruff-type-successor-20261013/candidate.patch` @ `febe20bd679385e564ae0dcbd5fe42b38c9400b0343c442fa463e27c919cc189`.
- R715 manifest: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r3-core-json-producer-conformance-r715-ruff-type-successor-20261013/manifest.json` @ `bc37b05288f82a97dedc0b7c879d102192cff297a3828ffcb1f128ccdf6aa2a5`.
- Prior R714 patch/manifest: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r3-core-json-producer-conformance-r714-20261013/candidate.patch` @ `7870481b1100a7b442d2c6dd938b0dd40a06f996f9acaa5937ed4807934a2a88` / `f434dfccb11ff63e16c21a8b696de1da47d5fc7eba082398b2c612e9da5d104f`. Independent R714 whole-class review: `reviews/core-json-producer-r714-independent-review-r746-20261013.md` @ `42807d018ced2141d748d90a04c3b96fab88133166b31480bf221d3b45cbf714`.
- Source frame: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r752-20261013.json` @ `a139743c1f9d965ab5b0cd8e284938f722c5729955d17b7b8aa10060df7ccfea`; HEAD `9e90b725395723789c5bac428c772c199a835cea`, tree `e94e85fb2db3dbc4b96424698f019cf827341a14`.
- R715 preserves the exact R714 10-path footprint and all 10 preimage bindings. Nine existing current preimages match; the new test target remains absent. All 10 R715 virtual-tree postimages match the manifest. Six target paths intersect the 498-path R752 frame. `git apply --check` returned 0. The candidate is still unapplied.
- Comparing R714 and R715 manifests: the 5 companion postimages are byte-identical. Only the 5 mechanism postimages differ, due to the typing/internal-name/import-order changes below. No writer/test/doc semantic surface expands or disappears.

## Delta and property review

The semantic mechanism is unchanged from R714. In `common/canonical_profile.py`, the shared decode/re-encode helper now uses `TypeVar` `_T` so the decoded value is preserved in its return type and passed to the encoder with the matching type. In `core/canon/canon_json.py`, the Core wrapper is renamed from `validate_core_json_payload_conformance` to private `_validate_core_json_payload_conformance`; the three Core writers update only their import and call spelling. Import order and the shared module docstring are adjusted. The profile guard, exact-byte predicate, selected-profile behavior, direct writer placement before `put_bytes`, tests, and raw `put_bytes` boundary are unchanged. The helper remains callback-driven, so Core and IR retain their own codec functions/tag policies.

The full postimage map shows identical R714/R715 bytes for `core/artifacts/README.md`, `core/artifacts/protocol.py`, and the three test files. The five changed mechanism postimages are in the manifest; no new class of escape or P40 repair round is introduced. Classification: **SAME_CLASS_STATIC_QUALITY_SUCCESSOR**, not a new semantic finding.

## Static receipts and P41 status

The configured Ruff receipt is `ruff-results-r2.json` @ `f10147d96bc27efed98f8f88e4c9cac111a08ed38fde8a90a54df8ef21bd440a`: exit 0, all 9 changed Python postimages returned 0. I read the receipt only; I did not rerun Ruff.

The focused strict mypy candidate receipt is `mypy-results-r2.json` @ `0de223fb4d15113f515c07935d5ca60f428bec2bd66f99e1fd1d663d15df3c5d` and the physical-preimage comparison is `mypy-baseline-results.json` @ `d28908dc1aa7734797042ec4e91e4c18c0b6f258e8d3826dc6452c67fb704a8a`. Both return 1 with 17 diagnostics across the same 5-file scope; the normalized diagnostic-message multisets match exactly (zero new/removed messages). **Mypy is not green.** Under P41 this red cannot be called inherited: the 5 changed mechanism files intersect the complete 5-file mypy input set, rather than having zero overlap. Record it as a comparative no-new-diagnostic result with owner/status not established, not as a clean or inherited typecheck. Full typecheck and native tests remain outstanding.

## Limits

No product imports, runtime tests, backend execution, build, source/index/Git writes, or heavy commands were run. The R714 semantic review and its bounded `put_bytes` residual remain applicable unchanged; this delta does not close that residual or any formal capability. Proceed to the focused native wave only.
