# G decision candidate R3: HTE point estimate when ATE inference is unavailable

**Candidate only; not a product contract, source acceptance, formal finding disposition, or closure.** This revision preserves R2 as an immutable predecessor, corrects the B31 criterion-span digest, and addresses the independent packet review's two requested clarifications. It proposes a minimal new HTE-specific persisted contract because no typed, content-bound ATE inference-basis contract exists in the current source. It does not claim that one already exists.

## Frozen inputs and predecessor chain

- Current source frame: commit `56b45c52a1519299648a6fcf572693e238892fd4`, tree `3cda7077d64f1658cdc09e70fbee299648d70910`, parent `3a300900cb0fc4dc47d1c0f526663cee188327ba`, branch `codex/e02-unified-local-20261009`; tracked tree is clean. This packet does not change source or move HEAD.
- R2 predecessor, unchanged: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/g-choice-hte-ate-inference-unavailable-20261021-r2.md` SHA-256 `b2ccf7e45a60a437b377aaaaec5bb4a1e4f32f396037da771c24026842ff2cd7`.
- Independent R2 review: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/independent-g-choice-hte-ate-inference-unavailable-20261021-r1/review.json` SHA-256 `614326607da364550105847453586a38f8aade2caac263d66328fbd9d341e999`.
- Independent review of the shared adapter R1: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/econml-shared-adapter-independent-review-20261021-r1.md` SHA-256 `9fdd541252d3fcb2416fc0f5e6b9f873dfb3b79d29cb14d69557548bddc5207d`. Its alpha change and callable-pvalue findings concern the pending adapter repair, not a ratified ATE interval law.
- Earlier numerical/API oracle: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/forest-dr-econml-numerical-api-oracle-20261021-r1.md` SHA-256 `3e911e5ced82e67a1c9a2e6559c28193c0ca7bb834675f866ff7d47c8482c46d`.
- Actual pre-repair ForestDR result: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/forest-dr-v11-real-cold-witness-20261021-r1/actual-r3/result.json` SHA-256 `d92d5fe08d07e33921d006e97a9a3ce3a5e8286288eeeb1d5b9a6f9d16eb4b29`; source frame `3a300900cb0fc4dc47d1c0f526663cee188327ba`, tree `37f117ebe8e85c196fddbd1ea443a05bea548bfd`.

## Decision requested

For the shared EconML HTE producer family (CATE, DML, selected S/T/X, and ForestDR), when a fitted model yields a valid point estimate but no usable, supported population-ATE inference result at the requested level, should the new HTE output contract:

1. **Preserve a point-only limited estimate and require a verified inference basis for finite-interval success** (recommended). Extend the existing *candidate* HTE estimate/refusal union with a distinct point-only-limited variant and a typed, content-bound ATE-inference-basis reference on its finite-interval success variant.
2. **Return a typed refusal instead of preserving the point** until a new output contract is accepted. This preserves fail-closed behavior and is smaller operationally, but deliberately loses the usable point from the primary HTE result surface.
3. **Permit a method/profile-specific fallback interval** only after its statistical owner supplies the inference law, scope, assumptions, target, computation and provenance, and G accepts that bounded profile. No such general fallback basis is established here.

The recommendation is option 1. Do not choose a finite CI because a method name, confidence-level field, warning, non-null result, or output shape says one exists. Do not treat missing per-row uncertainty as zero. Keep identification bounds separate from estimator sampling/model uncertainty. A content-bound inference record proves which supported inference output was used for this result; it does not by itself prove causal identification, coverage, calibration, external validity, or publication authority.

## Exact original criterion and its boundary

The criterion is **B31**, one canonical occurrence in EMP-01, source `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md` lines 593–606. The whole-file SHA-256 is `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`. The exact inclusive line-span digest, including line endings, is **`9311ba1b0fb2e6a3f180546c6118406c5781dbbfb57e27b28075b95a92fe371f`**, independently recomputed from the source and matching `closure-decisions/coverage.json` finding index 156.

That criterion requires statistical/model uncertainty to remain distinct from the identification set for the same estimand and unit; it rejects arbitrary proxy widths, loss of non-zero native uncertainty, and treating a method name as a different coordinate. It also states that a zero-width identification set is not, by itself, an error. B31 is held (`ledger_status_historical=held`, `closure_now=not_adjudicated`, `capability_label=absent/unallocated`). This packet does not relabel or close it. B31 motivates the no-loss/no-proxy rule, but is not the HTE source occurrence or proof that a point-only HTE schema already exists.

The earlier packet's B31 span digest was wrong. R3 corrects only the citation, not the source block, acceptance criterion, ownership, or closure status.

## What the current source can and cannot represent

The pinned source files are:

- `ir/analytics/hte.py@f5d416213cca5d80dbfea6c86de9abc7eef091c6c5da6cb50b5851afb4512cfb`.
- `ir/analytics/causal.py@8d9f455691fa394e6c36013821bd3f95be8bd93de2c2abaa898ddd1b28fb6264`.
- `foundry/methods/base.py@a621c597d9f01fdd89f366470c38feb8b457ec07faa7d3251aaa749a4754689e` and `foundry/methods/components/io.py@79172d1619e3424d6282f0d5eaa89fdaf08d65d0de620b078562f1e7b16b86c9`.
- Shared extractor `foundry/methods/catalog/causal/_econml_adapter.py@a7088333e7956d3db0f5cf30cd04a2a039db17f81e030154b8fe4e8c9d27487f`, plus `cate.py@8feaff85e39540a457044e883d2de49b3613d891511b673c2a8cb1a222310ba1`, `dml.py@5bc3d414227c426f2ab1df973196ffe6891905a70782d14a36cb3110f56f4885`, `meta_learners.py@b9868d881a8446edbacb613f6319b875ecd32f92701ea402ba691bbfe9e25e15`, `forest_dr.py@45c1538414083262e1e55a3fe00a7a0f9ddb391e4328115bd3f96cb1d1c9445b`, and `protocols.py@ece93225711e7702b9dace607ab6cf9ab4941baa56bc847e19b3f35c7e8ca44b`.
- Current DML output slots and report path are source-bound in `dml.py` above; the shared HTE consumers are also in `cate.py`, `meta_learners.py`, and `forest_dr.py` above. Current downstream output and packet readers are `scientist/nodes/builtins/simulate/run_causal_evaluation.py@1a58d1736ca2d16b11cf2c6792bf0e4742dd73f57960aa045e55d05b9a7062d6`, `scientist/orchestration/engine/protocol.py@335125a09166458c151d749ca1f8a8548df356f349d288db584c63f2a9000e0f`, and `scientist/nodes/builtins/decide/decision_packet/outcome_sections.py@119f277312b98b532163c1a7c666be181c93dd3b06401b5b03819b2c3e59e755`.

`HTEResult` v1.0 requires finite `ate_ci_lower`/`ate_ci_upper` containing the ATE. Its per-row SE and paired-CI arrays can be empty, but it has no typed inference-basis reference. Its `econml_estimator_class`, `econml_params`, and generic metadata do not prove which inference operation produced the interval. `CausalEffectReport` has a required string `inference_method` and metadata, but these are likewise not a content-bound inference basis.

`CausalEffectReport` requires a point and confidence interval when `status=SUCCESS`. It allows a point with no interval on a non-success status, but the current status enum only has `INPUT_INVALID`, `ASSUMPTION_FAILED`, and `NUMERICAL_FAILURE` beyond `SUCCESS`; none means “the fitted point estimate is available but its ATE inference is unavailable.” Using one would misstate the run. Its non-success uncertainty projection is a non-gating sentinel failure envelope, not a point-only HTE result.

The normal HTE output contract declares both `causal_effect_report` and `hte_result` as required slots. The output coercer rejects a missing declared slot. Therefore a non-success `CausalEffectReport` alone cannot replace `hte_result`, and a success report cannot omit its interval. This is a real output-boundary constraint, not an inference-law decision.

The earlier HTE refusal packet (`implementation-handoffs/LOCAL/decisions/hte-refusal-contract-g-packet-20261010.md@ad1dc5307e75630b00ecd1bf1a71e82abdf82ba37282fa31c64cd6e67a0db32d`) is a candidate, not a production contract. Its illustrative `HTEOutcomeV1` has `Estimate(HTEResult)` and `Refusal`; it has neither a limited point-estimate branch nor an inference-basis field. A source search at the pinned candidate found no production `HTEOutcome` or `ATEInferenceBasis` type. Do not attribute the illustrative candidate union to current source.

There are five shared-extractor call sites: four final HTEResult constructions (CATE, DML, selected S/T/X, ForestDR) and one S/T/X candidate-scoring call that consumes `cate_values` only and does not construct/persist an HTE artifact. This decision covers the four final shared-extractor outputs; it does not fold the fifth scoring call into a new persisted-result count or extend the separate CausalBCF path without evidence.

The source-bound ForestDR witness in the input list actually reached native `ate_inference` and failed at the old per-row `std_point` access. It is an adapter failure, not evidence for a no-inference run, a successful repaired runtime, a supported S/T/X no-bootstrap basis, or a production-positive result. The original R2 packet retains the source and caller crosswalk, optional-bootstrap observation, and the distinction from predictive V4/V7 tasks.

## Minimal proposed content-bound contract

The current source has no persisted, typed inference-basis contract. The following is a *proposal to G*, not an existing serializer, field, ref, owner policy, or claim of availability.

Introduce one HTE-specific, discriminated output contract under a new method identity so the old output slots and HTEResult v1 bytes are not reinterpreted. The illustrative new union is:

```text
HTEOutcomeV2 =
  Estimate {
    method_identity,
    causal_effect_report: CausalEffectReport(status=success),
    result: HTEResultV1,
    inference_basis: ATEInferenceBasisRef
  }
| EstimateLimited {
    method_identity,
    point: HTEPointEstimateV1,
    status: "limited",
    reason_code: "inference_unavailable"
  }
| Refusal {
    method_identity,
    causal_effect_report: CausalEffectReport(status=non-success),
    reason_code: typed_refusal_code
  }
```

Each variant is a complete value for a single required `hte_outcome` slot. The `EstimateLimited` branch contains a point estimate and optional CATE values/diagnostics, but has no ATE CI fields and is not an `HTEResultV1`. The `Refusal` branch remains for an attempt that produced no valid point/result (for example the already scoped backend-import refusal); it is not the branch for an available point with unavailable inference. The `Estimate` branch requires both the unchanged strict HTEResult value and the new typed inference-basis reference. The new contract identity and public FQN are not allocated here.

If G requires the old separate report slot in the new identity, the limited branch also needs a new typed HTE limited-report contract/status. Do not encode it as current `NUMERICAL_FAILURE`, `ASSUMPTION_FAILED`, or `SUCCESS`; do not use a nullable `hte_result` or a metadata flag as conditional-output semantics. The one-slot union is the narrower proposal because it gives the consumer a real discriminant. Its adoption still requires explicit adaptation of Foundry output validation, persistence, causal-evaluation consumers, fresh readers, the HTE decision-packet/API surface, and generated/schema surfaces. A new FQN/version preserves saved compositions and old artifacts; old bytes remain readable under their original meaning.

The proposed `ATEInferenceBasisV1` should be a portable typed artifact/ref, not a serialized Python/EconML object and not a free-text label. At minimum it must content-bind:

1. The approved basis profile/version and immutable profile digest, with an owner-reviewed method-specific protocol identity. A `basis_kind="native"`, method name, model label, or `inference_method` string alone is not evidence.
2. The selected method FQN/ABI and estimator profile/version/digest, the exact fit/invocation reference, and the content-bound input/evaluation-population reference. Include the estimand, unit, target/population role, and relevant attempt time so a result cannot be rebound across a different target or epoch.
3. The supported inference operation and configuration actually used (for example the native population-summary protocol or an explicitly selected bootstrap profile), its parameters and requested alpha/confidence level, and a typed reference/digest to the observed inference output that supplied the bounds.
4. The finite lower/upper values and interval semantics, plus the exact HTEResult reference/digest whose ATE bounds must equal that observed output. The consumer must recompute the input/result/profile references, method/ABI match, alpha/config match, digest integrity, and bound equality from resolved artifacts; a self-attested status or adjacent metadata cannot satisfy the check.
5. Producer/source/runtime provenance and a verification receipt/version that identifies the validator and rule used. If the selected estimator/run or source binding is unavailable, the consumer cannot accept the finite interval as a verified Estimate.

This contract verifies the provenance and binding of the interval to the selected run; it does **not** assert that a nominal CI is calibrated or causally identified. G still needs the relevant method/profile owner to say which inference protocol is supported for which target and assumptions. If that external statistical basis is not supplied and accepted, that profile cannot appear in the success allowlist, regardless of a finite interval or content hash.

## Legacy interval-guard residual

The pinned current adapter computes a guarded SE from cross-row CATE dispersion and optional row SEs, substitutes zero for absent within-row variance, and uses the existing fixed `1.96` multiplier both to create the no-native fallback and to widen any finite interval whose guard is larger. Thus a valid native interval can be widened by an unratified CATE-derived rule. This behavior predates the pending R1 repair; the independent adapter review identifies it as a residual and R1's alpha-dependent multiplier as a separate unauthorized semantic delta.

The mechanical adapter repair should retain the legacy `1.96`/guard behavior until G decides otherwise and label it explicitly as an unqualified limitation. That preserves the existing source behavior while avoiding a false claim that the guarded output is a native interval unchanged. **This packet does not accept the guard as a supported inference basis.** In the proposed new success variant, the output bounds must match the accepted inference output exactly. If the legacy guard changes the bounds, that result cannot be called basis-verified Estimate unless G separately ratifies the transformation; until then it remains limited/unqualified. No global CI law or migration is inferred from preserving the legacy behavior.

## Reuse-first alternatives and migration

| Route | Reuse and required change | Impact |
|---|---|---|
| Extend the existing *candidate* HTE union (recommended) | Reuse its idea of a versioned Estimate/Refusal discriminator, retain HTEResult v1 within the Estimate branch, add an explicit `EstimateLimited` point-only branch and a required content-bound basis ref to success. Replace the new FQN's fixed report/result slot pair with one required union slot; update consumers and surface. | Bounded to the HTE family but requires a new identity, serializer/reader and surface migration. It expresses all three states without null/NaN/sentinel CI or a generic status expansion. |
| Reuse CausalEffectReport alone | No safe implementation: current success requires a CI; non-success statuses do not mean inference-unavailable; the report does not satisfy the declared HTE output slot. | Reject as insufficient. Add a proper HTE union or explicitly decide the more invasive report/slot ABI change. |
| Refuse point-only output for now | Reuse the existing typed refusal pattern in the candidate union, preserving the refusal reason while withholding the point from primary output. | Smaller data contract, but loses a valid candidate point and must still satisfy the new required HTE outcome slot and consumer surface. |
| Method-specific fallback | Reuse an actual supported native or configured inference procedure only where its method/profile owner supplies the inferential assumptions, target, alpha, computation, covariance/dependence handling, provenance and scope. Persist its basis as above. | No basis is currently admitted. No global CATE-dispersion/Wald fallback, no external validity, and no calibration claim. |

Migration is append-only: keep old method FQNs, HTEResult v1 decoding, and saved artifacts at their original semantics; add a new identity for the new union; never retrofit old bytes with a basis ref or reinterpret their finite fields. A later inference result is a new attempt/artifact, not an upgrade of an older point-only result. The existing output-aware refusal candidate is reusable as the `Refusal` branch only after its source verification and consumer path are actually adopted; it does not itself carry this `EstimateLimited` state.

## Acceptance signals and falsifiers if G selects option 1

1. Run an actual supported HTE profile whose selected fit has no population-ATE inference output. The producer must persist `EstimateLimited` with the point/input/method/time lineage, a typed `inference_unavailable` reason, and no ATE bounds. A fresh Foundry/Scientist reader and the decision packet must show a limited point; absence of the old HTE section alone is not a pass.
2. Run one actual supported profile with a recorded native or configured basis. Resolve the basis artifact, verify current method/ABI/profile and input/target bindings, alpha/config, source inference result, result digest, and exact output-bound equality. Only that variant may be `Estimate`.
3. Hold the point and CATE values fixed while removing inference availability. The outcome must change from `Estimate` to `EstimateLimited`; it may not remain green because method/status labels or finite-CI markers remain.
4. Tamper independently with the basis digest, profile/ABI, input or target ref, alpha, source interval, and HTEResult bounds while retaining labels/shape markers. The consumer must fail closed for each mismatch. Keep the CATE-guard case separate: if it changes the interval without an admitted transformation basis, the verifier must not accept the result as unchanged native inference.
5. Exercise every member of the four-method shared-extractor family and its fresh consumer. The internal S/T/X candidate-scoring call remains an explicitly non-persisted fifth call site. Keep the separate CausalBCF path out of this denominator unless a complete source census adds it.

The older R2 standard-library arithmetic prototype remains only a falsifier for why “missing uncertainty → zero within variance → tiny finite interval” is not evidence. It is not a CI oracle, product runtime receipt, or acceptance test.

## Status, authority, and present capability labels

- Current `HTEResult` success shape: present; no content-bound inference basis ref: **not established**.
- Point-only HTE typed outcome and consumer bridge: **absent/unallocated**; the previous HTEOutcome is a decision candidate only.
- Supported method/profile inference law and external statistical owner evidence: **not established**. A genuine source-bound result and profile must be supplied; a model name or result label cannot supply it.
- Inference-basis verification and point-only consumer/API/dashboard surface: **verification_missing / consumer_missing / surface_missing** for this proposed branch until implemented and replayed.
- Legacy CATE-variance guard: may widen a native CI; **unqualified legacy residual**, not a new basis and not a formal closure. The pending adapter source repair remains independently reviewable for the `.stderr`, p-value, SHAP and shape issues.
- B31 remains held and not adjudicated. V4/V7 predictive-calibration routes remain separate and do not supply causal-estimator inference law. No G acceptance or formal finding closure is claimed.

Pattern pass: P04 (estimate/limited/refusal distinction), P05 (no self-labeled basis as authority), P10/P14 (inferential adequacy and evidence independence), P29/P37/P38 (real producer-consumer verification, recomputed content binding, falsify marker-preserving tampering), and P31/P40 (cover the complete shared family instead of one estimator). The required gate predicates are recomputed from resolved refs and actual bytes; the underlying statistical assumptions/calibration remain institutionally supplied or not established and cannot turn the gate green by themselves.

## Exact source and criterion pins

- Base frame: `56b45c52a1519299648a6fcf572693e238892fd4` / `3cda7077d64f1658cdc09e70fbee299648d70910`.
- Correct B31 source: `B_r19_original.md@9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`; lines 593–606 exact span `9311ba1b0fb2e6a3f180546c6118406c5781dbbfb57e27b28075b95a92fe371f`.
- Coverage/closure binding: `closure-decisions/coverage.json@97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01`; finding index 156 says one B31 occurrence, held, not adjudicated, absent/unallocated. `closure-decisions/A.md@3ba7cfab2c905bcb139f6616be3451266ff50846321865a48688e88f9ea780ba`; `semantic-decisions.md@4db948eec96a2e60bc46ecd7111498e0ae54ed310236dc1eddf157473377b4e0`.
- E02 task denominator pointer used in prior packet: `execution-prompts/unified-local-2026-10-09/TASKS.json@a37c75cfe09d33c1f50379d5bbfd04bdb728c990e832aec3bf19c0d17035734c`. V4/V7/LA-051 are not recast as causal ATE inference findings.
- Original HTE refusal candidate: `implementation-handoffs/LOCAL/decisions/hte-refusal-contract-g-packet-20261010.md@ad1dc5307e75630b00ecd1bf1a71e82abdf82ba37282fa31c64cd6e67a0db32d`.
- Source-bound previous fit result: `forest-dr-v11-real-cold-witness-20261021-r1/actual-r3/result.json@d92d5fe08d07e33921d006e97a9a3ce3a5e8286288eeeb1d5b9a6f9d16eb4b29`; pre-repair only.

No source imports, tests, numerical fit, canonical changes, or formal closure adjudication were performed for R3. The next check is an independent delta review against the frozen R2 packet and the cited source frame, followed by G's independent decision.
