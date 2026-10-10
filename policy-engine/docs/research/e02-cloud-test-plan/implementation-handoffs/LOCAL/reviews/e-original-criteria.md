# E original-criteria/source-intake oracle

This is a read-only independent source review, not G acceptance, finding closure, or a ledger
change. The original review snapshot below was at HEAD `22ca540`; a recovery reread at HEAD
`80f043c0c007ca14dfd4927f980e391f4fcdc62a` and tree
`a9af1372c08712c3a58a367cad085a4926243f7e` is recorded after the historical tables. The current
verdict remains **partial**: the recovery tree now contains a source/test correction for B175,
while B201/B202 still have source mismatches, B166/B170 need a real runtime/replica consumer
proof, and LA-056 schema/pickle compatibility lacks semantic tests. The
recovery reread also finds that S1 has since corrected the selected-manifest-profile reader in the
shared working tree. Source is still mutable; the final recovery hashes are a working-tree
snapshot, not a source-freeze receipt.

## Pinned inputs and denominators

The current shared branch at review time was `codex/e02-unified-local-20261009`, HEAD
`22ca5401692d41f30c37eca060d132c6353dfa87`, tree
`041632477ed3081da10ec8244b7be0577f645d51`. The branch is attached and HEAD is a root-authored
descendant. Product sources are still being edited by declared peers; this is therefore a
working-tree review snapshot, not a source-freeze receipt. The reviewed source bytes are tied by
SHA-256 in the table below.

After the initial review snapshot, shared HEAD advanced to
`021560651b7ab84857f7cd5ef1ecf08408cd548c`. Two declared peer edits then changed
`orchestrator.py` and `forecast_owner.py`; I inspected those diffs. They add artifact-store
adaptation and stricter uncertainty admission, but do not remove the B166/B170 mocked-runtime
limitation or change the LA-052 empty-comparison semantics. The corresponding digest rows below
identify the current reread bytes. Other source digests remain equal to the reviewed snapshot.
This is still not a source-freeze receipt.

The immutable E all-54 crosswalk is
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261007/profile-public-boundaries/full54/all54-delta-associations-v2-source11082.json`
@ `7bf53fd0cf69a568b37d8a881e26bfb16c315653` (blob
`502f44eb34c277b11764f89f153df17231864bf6`, SHA-256
`f840b7082a3a6b4e5edb0563b47d197960de2ca728e83813096e7f152236c8fe`). The original-source
denominator is `coverage.json` @ `198076863e143dea9f89f02734b13d50dae3eed5` (282 findings),
with B criteria in `source/B_r19_original.md` (SHA-256
`9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`) and LA criteria in
`source/LA_r09_original.md` (SHA-256
`2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727`). These references all
belong to the same immutable documentation commit above.

I independently enumerated the 54 E rows and joined each E-closed row to the complete coverage
file by finding ID and original criterion line/hash fields. Result: 43 proposed-closed IDs,
43 original criterion occurrences, 282 total coverage findings, and zero E-to-coverage
ID/line/hash-field mismatches. The 43 rows record `retained_E_owner_decision=accepted`, but also
`formal_G_acceptance=false` and `formal_ledger_change=false`; E's 43 proposals do not establish
G closure.

The G-intake candidate is **36**, not 43: B97–B105, B166–B171, B174–B187, B189, B191, B195,
B196, B203, LA-052, and LA-056. The seven E-closed rows still carrying row-specific E work are
B188, B192, B193, B198, B199, B201, and B202. The E crosswalk's `/rows/32`, `/rows/36`,
`/rows/37`, `/rows/42`, `/rows/43`, `/rows/45`, and `/rows/46` state those remaining actions.
B188/B192 need affected sampling-consumer reruns; B193 awaits frozen-wave receipt reconciliation
before G intake; B198 preserves historic closure and reopens only on a defining-property
counterexample; B199 still has affected IR-consumer verification; B201/B202 require the repaired
public boundary to be frozen and independently reviewed before affected native routes. None of
those statuses is changed here.

## Complete original-criterion inventory

The table is derived from the original B/LA source references in the pinned coverage and E
crosswalk, not from the later manual or bundle summaries. All B line ranges are from
`source/B_r19_original.md`; both LA ranges are from `source/LA_r09_original.md`.

| ID | Original lines | Required original property |
| --- | ---: | --- |
| B97 | 2630–2641 | Apply GRID_EXTREME cap before Cartesian materialization; returned prefix owns only admitted rows. |
| B98 | 2642–2653 | Return last completed adaptive round; no hidden post-budget evaluator call. |
| B99 | 2654–2665 | Preserve `allow_large_run`; reject an oversized child block before evaluator admission. |
| B100 | 2666–2677 | Sampling and analysis share the actual distribution, transform, and design fingerprint. |
| B101 | 2678–2689 | Seed reaches supported local RNG; independent stages do not reset global NumPy state. |
| B102 | 2690–2701 | Failed Morris rows retain the original denominator and discard only whole valid trajectories. |
| B103 | 2702–2713 | Multi-output scalar failure policy is applied before PCA; attempted/success/failed/block counts remain truthful. |
| B104 | 2714–2725 | PCA component rank is valid for centered wide, narrow, degenerate, and zero matrices. |
| B105 | 2726–2737 | Morris point and uncertainty effects use identical declared coordinates, units, and scale. |
| B166 | 4316–4327 | The exact immutable pre-cutoff view reaches Scientist; a separate unmasked state is not substituted. |
| B167 | 4328–4339 | Missing predictions remain in the requested denominator; zero/wrong-key comparisons cannot earn a positive grade. |
| B168 | 4340–4351 | Missing interval is unknown, an actual miss is false, availability is separate, and nominal level survives serialization. |
| B169 | 4352–4363 | Scalar/effect intervals are not forecast trajectories without explicit constant-forecast, unit, and time semantics. |
| B170 | 4364–4375 | K requested runs mean K actual calls with distinct replica/seed identity; failures remain visible. |
| B171 | 4376–4387 | Micro RMSE/MAE are partition invariant; macro weights remain a separate estimand. |
| B174 | 4412–4425 | Validate CV fold step/train/cap before loop or index-array materialization. |
| B175 | 4426–4437 | Resolve a defined statistic and finite 1-D observations before any draw/callback; preserve statistic identity on readback. |
| B176 | 4525–4534 | Retain every source/time observation or explicitly refuse it; technical-ID renaming cannot choose value/unit. |
| B177 | 4535–4544 | Synchronize calendar axis with values/masks/metadata; a missing requested time column cannot become positional. |
| B178 | 4545–4554 | Fractional fill stays dtype-stable; empty observed support is not a measured zero. |
| B179 | 4555–4564 | Validate observation/weight axes before broadcasting; avoid turning N comparisons into N². |
| B180 | 4565–4574 | Normalize quality within a target; apply target priority outside it and prove it changes the objective. |
| B181 | 4575–4584 | Zero-support inactive arithmetic has finite primal/reverse gradient without hiding active invalid output. |
| B182 | 4585–4594 | Scale uses the target's observed training support; other targets' dates/placeholders do not affect it. |
| B183 | 4595–4604 | Give each multi-start fresh telemetry context; enabled observability cannot break a later start. |
| B184 | 4605–4614 | One final forward produces matching total/component loss and report traces while staying derivative-connected. |
| B185 | 4702–4711 | Inactive rows make zero callbacks/identity derivatives; active failures and key identity remain real. |
| B186 | 4712–4721 | Nominal, delta, and MC receive the same complete fixed-plus-varying effective kwargs. |
| B187 | 4722–4731 | Align named covariance axes before spectral checks; repair cannot conceal a permutation. |
| B188 | 4732–4741 | Preserve an admitted joint vector law; absence of dependence evidence cannot become an independent product. |
| B189 | 4742–4751 | Do not cast JAX-varying values to Python float; supported affine nodes choose delta. |
| B191 | 4762–4771 | Missing output is an addressed structural gap, not a zero interval; a real constant zero remains allowed. |
| B192 | 4772–4781 | Propagate exact empirical support/weights/ordered joint rows instead of reconstructing Normal from bounds. |
| B193 | 4782–4791 | Mean error uses an independent pilot and frozen N excluding pilot; RQMC error uses independent complete-net replicate means. |
| B195 | 4894–4907 | Separate finite loss from satisfactory/unknown/known-bad raw Hessian; NaN/inf cannot win as unknown. |
| B196 | 4908–4921 | Score the last produced optimizer iterate under a comparable objective or leave it explicitly unscored before winner selection. |
| B198 | 4936–4949 | Changing displayed confidence does not change typed sigma or heuristic/gating limitations. |
| B199 | 4950–4963 | Duplicate envelope references do not increase level or convert credible into confidence interval. |
| B201 | 4978–4991 | Point functional and equal-tail interval are distinct: 99 zeros + 100 gives mean 1 and quantiles [0,0]. |
| B202 | 4992–5005 | Preserve resolvable joint posterior law, row order, weights, units, and lineage; equal marginals do not merge pairings. |
| B203 | 5006–5017 | Reuse Hessian only for exact parameter/objective/weight/seed/dtype/numeric-policy/model identity; otherwise recompute. |
| LA-052 | 3747–3792 | Match persisted requested/eligible/observed pairs to report/receipt; zero comparisons cannot become `approximate_calibrated`. |
| LA-056 | 4141–4171 | Neutral event/budget contracts import without orchestration while public/legacy models, aliases, validators, JSON schema, and old FQN pickle remain compatible. |

## Current source and actual test routes

The routes and selected-ref defect in this section describe the original 22ca review snapshot.
The recovery reread at the end supersedes time-sensitive source findings and provides the current
dependency hashes.

| Findings | Current producer → persistence/bridge → consumer route and source review | Existing exact test routes / status |
| --- | --- | --- |
| B97–B105 | DOE owns `sampling.py`, `adaptive.py`, `analysis.py`, and `multi_output.py`; `SensitivityResult` can be persisted by `ir/analytics/sensitivity.py` and the simulation node, then adapted/loaded by search and decision-packet paths. `SensitivityBridge.analyze_search_space()` is a separate in-memory SALib route. Distinguish those routes: the local DOE correction tests do not by themselves prove artifact/readback consumers. | Current semantic tests include remediation `test_doe_01.py`–`test_doe_03.py`, DOE `test_adaptive.py`, `test_sampling.py`, `test_analysis_enhanced.py`, `test_multi_output.py`, `test_morris_geometry.py`, `test_run_causal_evaluation.py`, and `test_sensitivity_bridge.py`. Not run under the active R4 fit slot. |
| B166–B175 | `BacktestOrchestrator._run_single_scenario()` masks data; `_predict_with_scientist()` persists the masked view, passes its `data_snapshot_ref` into `run_experiment`, reads metric artifacts, then the outer run persists a `BacktestReport`. The current B166 test reads the stored masked snapshot, but replaces `run_experiment`; B170 likewise asserts only that `random_seed` and `n_simulation_runs` are passed. No current `test_native_replay.py` or `native_replay.py` exists. This leaves the real runtime consumer, actual K calls/replica identities, failure retention, and fresh native report readback unproven. | `test_bkt_02.py`, backtesting `test_backtesting.py`, `test_masking.py`, `test_cv.py`, and `test_bootstrap.py` are exact focused paths. The B166/B170 cases in `test_backtesting.py` are mocked at `run_experiment`; they are not the original backend-boundary proof. Not run in this review. |
| B176–B187, B195–B196, B203 | Calibration producer lives in `foundry/calibration/{calibrator,multi_start,pure_executor,uncertainty_adapter}.py`; measurement/loss/forecast sources feed calibration reports and typed uncertainty consumers. Current `calibrator.py` does retain/reuse the selected run's Hessian when the reuse key matches, with recomputation on mismatch; current covariance and MC source paths include named-axis and law handling. These are source observations, not numerical verification. | Existing candidate paths: remediation `test_cal_01.py`–`test_cal_04.py` and `test_cal_06.py` (there is no current `test_cal_05.py`); `foundry/calibration/test_calibrator.py`, `test_multi_start.py`, `test_hessian.py`, `test_pure_executor.py`, and uncertainty `test_covariance.py`. Not run. |
| B188–B193 | At the original 22ca snapshot, the persisted uncertainty reader stripped the selected profile. The recovery reread now sees `load_uncertainty_envelope()` pass the typed `UncertaintyEnvelopeRef` directly to `get_json_artifact(store, ref)`, and a new fresh-CAS test uses the same artifact ID with a selected manifest profile; this closes that concrete reader defect in the current mutable tree, subject to independent rerun after freeze. `PosteriorSamplesCarrier` is supported and `_build_empirical_joint_spec()` consumes empirical rows/weights; missing `joint_sample_id` returns `unestablished_joint_law`. A matching declared ID plus compatible axis/count/weights aligns rows by position but remains `declared_non_authoritative` and non-gating. This does not content-bind paired row identity. Separately, `load_simulation_result_uncertainty_admission()` returns no admitted envelope while `draw_success_ledger_missing` and `draw_basis_verifier_missing`; fail-closed behavior does not implement B193's independent-pilot/frozen-N/RQMC estimator. | `test_uqp_01.py`–`test_uqp_03.py`, `test_monte_carlo_b194.py`, `test_propagate_uncertainty.py`, `test_propagate_welfare.py`, and `test_uncertainty.py` are candidate exact paths. Q0's exclusions retain B188/B192 native consumer reruns and B193 frozen-wave receipt reconciliation. No recovery rerun. |
| B198–B202 | B198's current Hessian adapter emits a typed `ParametricFitCarrier` containing the computed standard deviation; `extract_std()` reads the typed `std` before using interval width, so changing display level need not redefine sigma while the heuristic/no-gate fields remain. B199's aggregator collapses identical bound origins and preserves a shared level/semantics; mixed interval types go to non-statistical bounds. B201 still has an unconditional `lo <= point_estimate <= hi` validator in `UncertaintyEnvelope`; the current calibration summary computes mean and equal-tail quantiles then constructs that envelope, so the 99-zero/one-100 original example still raises. B202's calibration summary retains no `distribution_payload` or exact posterior draw ref. A separate Bayesian sampler does emit a CAS `draws_ref`; that proves a reusable producer exists, not a bridge from this calibration summary to that artifact. The single-parameter carrier and a declared `joint_sample_id` do not bind a paired multi-parameter draw set. | `test_uqs_01.py`, uncertainty `test_covariance.py`, IR `test_uncertainty.py`, `test_calibration_uncertainty_adapter.py`, and Bayesian `test_methods.py` are existing paths. Current adapter tests do not contain the 99-zero/one-100 sentinel or verify calibration-summary draw ref/pair identity after fresh CAS readback. Not run. |
| LA-052 | `compute_calibration_curve()` returns `None` metrics, `not_evaluated`/`incomplete`, and `is_well_calibrated=False` when no curve points exist. `evaluate_continuous()` emits an error issue; `CalibrationDiagnosticsReport.to_truthfulness_receipt()` downgrades absent/incomplete comparisons to `unverified`. The current ForecastOwner route also recomputes numerator/denominator from holdout+persisted forecast intervals, checks diagnostics against those pairs, persists diagnostics and a BacktestReport, and a current test reads the report and bridge evidence back. That route remains `predictive_only`/`bridge_pending` and refuses unbound authority, which is a separate boundary. | `tests/unit/calibration/test_curve.py`, `test_continuous.py`, `tests/unit/ir/analytics/test_calibration_diagnostics_report.py`, and `tests/unit/remediation/test_frc_02_empirical_bridge.py`. The source/test design addresses the original no-comparison positive-label defect; the numerical route was not run here. |
| LA-056 | Current canonical `ddm/contracts/events.py` and `metric_budget.py` exist behind lazy facades. Contract import trap, object-identity aliases, event validator, and budget mapping tests are present. The manual `ddm/integration/shift_event.schema.json` remains tracked with its `anyOf` evidence-channel rule; that rule is not reproduced by the ordinary Pydantic after-validator schema. The current DDM test tree has no `model_json_schema`, `pickle`, `shift_event.schema.json`, or `anyOf` assertions, so that required compatibility facet remains `semantic_test_missing` here. | Pure tests `tests/unit/ddm/test_facade.py` and `test_readiness_mapping.py` passed below. `test_full_acceptance.py` is not part of this lightweight receipt; no schema/pickle negative has been executed. |

## Concrete findings and P40 buckets

1. **B175 — historical source mismatch, corrected in the recovery worktree; same preflight class
   one level deeper.** At the original 22ca snapshot, `_prepare_observations()` lacked an ndim
   check, so a custom statistic could run before NumPy rejected 2-D input. The current recovery
   source now rejects `arr.ndim != 1` with `BootstrapValidationError(code="invalid_dimensions")`
   before callback or RNG construction. `tests/unit/scientist/methods/backtesting/test_bootstrap.py::test_two_dimensional_observations_refuse_before_callback_or_rng`
   exercises both entrypoints with a finite 2-D array and asserts zero callback and RNG calls.
   This is the same validation-before-expensive-work class, not a new class; the second finding
   widened the shared preflight helper. The current code/test bytes are recorded in the recovery
   digest table. They were not rerun in this review because the single native-fit slot remained
   active; this is source/test evidence, not a test-pass receipt.

2. **B166/B170 — verification gap, same mocked-runtime-boundary class; B170 is the second
   occurrence.** Existing current tests replace `run_experiment`, then check the masked snapshot
   ref/contents or copied seed/count parameters. They do not prove that the real runtime loads the
   exact masked ref, makes K actual calls with distinct replica identity, retains failed calls, and
   emits a fresh readable report. Widen one integration test around the real owned runtime/port
   seam to cover both criteria. Falsifier: a same-shaped unmasked/future-row snapshot must fail the
   consumer assertion; a requested K with repeated seeds/replica IDs or dropped failure must fail
   the call/report assertion. Do not count the mocked helper as the original end-to-end proof.

3. **Selected-view reader — historical finding, corrected in the recovery working tree.** The
   22ca snapshot's `load_uncertainty_envelope()` passed only `ref.artifact_id`; the recovery reread
   sees the S1 correction pass the complete typed ref, including `manifest_profile_sha256`, to
   `get_json_artifact`. `tests/unit/ir/test_uncertainty.py::test_uncertainty_loader_preserves_selected_manifest_profile`
   writes same-content refs under different canonicalization profiles (same artifact ID), creates
   a fresh CAS reader, and reads through the selected typed ref. Removing the selector forwarding
   makes that property fail. This is the same shared reference-selector class one level deeper,
   now fixed in source; independent post-freeze execution remains pending. It does not establish
   B193's draw ledger/verifier or every native B188/B192 consumer.

4. **B201 — confirmed source mismatch; same original point/interval-semantic class.** The
   unconditional envelope validator still rejects a point outside bounds. The summary still uses
   posterior mean as point and equal-tail bounds, so the exact 99-zero/one-100 sentinel remains a
   deterministic failure before readback. Keep mean=1 and quantiles [0,0]; distinguish point
   functional from interval semantics rather than widening the interval or silently substituting a
   median. The required negative also preserves finite and ordered interval validation. No NumPy
   numerical run was performed here.

5. **B202 — confirmed producer-side loss; same lossy-summary class, distinct from B192's consumer
   omission.** `summarize_bayesian_calibration_posterior()` receives draw arrays but creates
   envelopes without `distribution_payload` or a ref. The existing HMC producer's persisted
   `PosteriorResult.draws_ref` is a wire-existing reuse path, but no source bridge binds it to these
   calibration envelopes. Reuse that artifact/ref (or inline the existing carrier for bounded
   small data) and preserve axis, weight, unit, order, and lineage. Falsifier: two parameter vectors
   with identical marginals and the same declared ID but reversed rows must not be admitted as one
   paired law after CAS write/read. The source itself says global draw loss is not established;
   this review likewise does not claim the draws vanish everywhere.

6. **B188/B192/B193 — bounded but not established, not false-authority findings.** Without a
   declared joint ID the MC path returns unknown; with an ID it labels the identity
   `declared_non_authoritative` and keeps the output non-gating. B192 has an in-memory carrier
   route, but current fresh-reader profile preservation and a real native served consumer remain
   open. B193's consumer deliberately admits no numeric envelope until content-bound draw success
   rows and a linked verifier receipt exist. These conditions must not be described as proof of
   independent-pilot or RQMC replicate-mean error control.

7. **B198/B199 and LA-052 — source path appears to satisfy the bounded local property; current
   execution still pending.** Typed Normal `std` is used before display width in B198; duplicate
   origin collapse and conservative mixed-semantics behavior in B199 align with the original
   local requirements. LA-052 source sets empty/incomplete comparisons to unverified and its
   existing report/readback tests include empty, partial, measured positive/negative, and
   receipt cases. No new defining B198 counterexample was found. These are code-review observations,
   not G acceptance or test-pass claims.

8. **LA-056 — local contract boundary proved for the executed tests; full compatibility remains
   partial.** The lazy import, alias identity, validators, and readiness mapping tests pass. Schema
   fidelity and supported old-FQN pickle compatibility remain unproved by current DDM tests; the
   manual schema's `anyOf` is specifically load-bearing and must not be replaced by un-compared
   generated schema.

## Test execution and remaining commands

Executed on the current worktree with `PYTHONPATH=src` from `policy-engine/`:

```text
.venv/bin/pytest -q tests/unit/ir/registry/test_refs.py tests/unit/ddm/test_facade.py::test_contract_only_import_does_not_load_ddm_orchestration
10 passed

.venv/bin/pytest -q tests/unit/ddm/test_facade.py tests/unit/ddm/test_readiness_mapping.py
8 passed
```

The first command checks ref-model/profile DTO behavior and a negative contract-import boundary;
the second checks DDM alias/validator/budget mapping. They do not establish the E numerical
criteria or schema/pickle compatibility. R4's single heavy/native-fit slot was active, so no
NumPy/SciPy/JAX/SALib/Monte Carlo/native fit or broad downstream test was started.

After source freeze, the minimum current commands are:

```bash
cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/remediation/test_doe_01.py tests/unit/remediation/test_doe_02.py \
  tests/unit/remediation/test_doe_03.py \
  tests/unit/scientist/methods/doe/test_adaptive.py \
  tests/unit/scientist/methods/doe/test_sampling.py \
  tests/unit/scientist/methods/doe/test_analysis_enhanced.py \
  tests/unit/scientist/methods/doe/test_multi_output.py \
  tests/unit/scientist/methods/doe/test_morris_geometry.py \
  tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py \
  tests/unit/scientist/methods/autotune/test_sensitivity_bridge.py

cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/remediation/test_bkt_02.py \
  tests/unit/scientist/methods/backtesting/test_backtesting.py \
  tests/unit/scientist/methods/backtesting/test_masking.py \
  tests/unit/scientist/methods/backtesting/test_cv.py \
  tests/unit/scientist/methods/backtesting/test_bootstrap.py

cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/remediation/test_cal_01.py tests/unit/remediation/test_cal_02.py \
  tests/unit/remediation/test_cal_03.py tests/unit/remediation/test_cal_04.py \
  tests/unit/remediation/test_cal_06.py \
  tests/unit/foundry/calibration/test_calibrator.py \
  tests/unit/foundry/calibration/test_multi_start.py \
  tests/unit/foundry/calibration/test_hessian.py \
  tests/unit/foundry/calibration/test_pure_executor.py \
  tests/unit/foundry/uncertainty/test_covariance.py

cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/remediation/test_uqp_01.py tests/unit/remediation/test_uqp_02.py \
  tests/unit/remediation/test_uqp_03.py \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py \
  tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py \
  tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py \
  tests/unit/ir/test_uncertainty.py

cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/remediation/test_uqs_01.py \
  tests/unit/foundry/uncertainty/test_covariance.py \
  tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py \
  tests/unit/ir/test_uncertainty.py \
  tests/unit/foundry/methods/catalog/bayesian/test_methods.py

cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/calibration/test_curve.py tests/unit/calibration/test_continuous.py \
  tests/unit/ir/analytics/test_calibration_diagnostics_report.py \
  tests/unit/remediation/test_frc_02_empirical_bridge.py \
  tests/unit/ddm/test_facade.py tests/unit/ddm/test_readiness_mapping.py
```

The B166/B170 real-runtime proof and B201/B202 persisted calibration-draw/joint-law negative are
not current tests and must be added on the owned route before claiming those end-to-end properties.
The DDM test command must be paired with an actual-schema comparison and a supported-FQN pickle
round-trip (or a bounded documented reason those forms are out of scope); current DDM tests do not
contain those assertions.

## Initial working-tree source digests (22ca snapshot)

The following SHA-256 values identify the exact editable files inspected above; they are not Git
blob IDs and must be refreshed after freeze.

| File | SHA-256 |
| --- | --- |
| `src/polisyos/scientist/methods/backtesting/bootstrap.py` | `724096d5b7425b5964747f4e07804edc5e7dae96b6a0a7587664b2353c09014c` |
| `src/polisyos/scientist/methods/backtesting/orchestrator.py` | `53b99e93d0da5c5a07dd8e9d99cbb50df99a0819b7fb98d31a07c3d195cb4908` |
| `src/polisyos/ir/analytics/uncertainty.py` | `42524f68b959c2140076e8312066aecd69e564692cea010141fc74e1021af1f5` |
| `src/polisyos/ir/registry/refs.py` | `bbac14368f7091bf8135f621999e9b702d711c31a95e87e7ceaa1bd963c8fe72` |
| `src/polisyos/ir/artifacts/io.py` | `2b8805c49aa2446c7930eee7265b30154c5a450955eac57d152123d78441cadc` |
| `src/polisyos/foundry/uncertainty/monte_carlo.py` | `2679d546e048f466ceb96a80d69571ee953d0a402a596d423cc04e2c2d4ac9b1` |
| `src/polisyos/foundry/calibration/uncertainty_adapter.py` | `76a4961b9c32f4a8a021796617d84bbc68420d4ef11548c5f21bf39d21291841` |
| `src/polisyos/calibration/curve.py` | `3e4efb2865b8c2d1a7ed9d3263ae57a84560967f14caecb299716a9c462a04ee` |
| `src/polisyos/calibration/continuous.py` | `abde79ab0573b342b76886c81fb827784d257660477faf01e4019ae23a6fc59c` |
| `src/polisyos/scientist/methods/backtesting/forecast_owner.py` | `f4b2f31b8367a11e6894a0d40658eb854fab8fa9893faef130824ed0c87327f5` |
| `src/polisyos/ddm/contracts/events.py` | `bb61dc020f9c905b7a3b47a9cec4ebdd98b002be5bb5692919bddc117a7a7ab7` |
| `src/polisyos/ddm/contracts/metric_budget.py` | `5f607000142ec570fdbd89297ea00039b7e2b2fef6cf825753eac24e7f4a4cdc` |
| `src/polisyos/ddm/integration/shift_event.schema.json` | `1bb48c1e7bd3531d8a8e81213f392f42fd91649654e41b42a8a4a2fb76045f65` |

Pattern pass: `P01/P02` distinguish typed code or persisted artifacts from a wired consumer;
`P10/P29/P32` require the original semantic boundary, not a marker or mocked input; `P31` favors
the existing carrier and CAS owner; `P35` uses the complete 54/282 denominators; `P37/P38` keep
declared joint IDs and gate predicates separate from content identity; `P40` buckets the repeated
runtime-mock and preflight classes above. Current capability labels for the unresolved slices are
`semantic_test_missing` (B166/B170 runtime, B201/B202 persisted-law negative, LA-056 schema/pickle)
and `producer_missing`/`artifact_missing` for the B193 draw-success ledger and verifier receipt.
No formal G finding status is assigned by this review.

## Recovery reread at the 80f base (source remains mutable)

This addendum supersedes the time-sensitive source conclusions and the old digest table above.
HEAD remained on branch `codex/e02-unified-local-20261009` at `80f043c0c007ca14dfd4927f980e391f4fcdc62a`
(tree `a9af1372c08712c3a58a367cad085a4926243f7e`). The source files below are current
working-tree bytes at this reread, including declared peer work; they are not a frozen commit
snapshot. I made no source, test, config, build, or Git edits. This packet is my only write. No
native or numerical suite was run under the active R4 slot. The previous 10- and 8-test receipts
remain historical 22ca evidence, not a rerun of these current bytes.

The original E intake is unchanged: the all-54 packet is
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261007/profile-public-boundaries/full54/all54-delta-associations-v2-source11082.json`
at commit `7bf53fd0cf69a568b37d8a881e26bfb16c315653`, Git blob
`502f44eb34c277b11764f89f153df17231864bf6`, SHA-256
`f840b7082a3a6b4e5edb0563b47d197960de2ca728e83813096e7f152236c8fe`. Its author-proposed
closed set remains 43 IDs/43 original occurrences; the G-intake candidate remains 36. The seven
E-owned residual rows are B188, B192, B193, B198, B199, B201, and B202. Formal G acceptance and
ledger changes remain zero. The pinned coverage document is commit
`198076863e143dea9f89f02734b13d50dae3eed5` (282 findings); its current checked-out bytes have
SHA-256 `97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01`. The original B/LA
source hashes remain `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5` and
`2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727` respectively.

P40 classes for the recovery items:

- B166 and B170 are the same backtest-to-runtime realization class one level deeper than the
  mocked dispatch checks; B170 is the second occurrence. Widen one real-runtime test cohort to
  cover masked input identity, actual execution count/seed semantics, failures, and fresh report
  readback. This is not a new list of per-finding assertions.
- B201 is a separate point-functional/interval-semantics class. The posterior mean and equal-tail
  interval can legitimately not contain one another; it is not a variant of B202 law loss.
- B202 is the same end-to-end law-preservation class as B192 at a different stage: the summary
  producer drops draws that the later consumer needs. B192's selected-profile reader defect is
  now corrected in the working tree; B202 still lacks a producer-to-reader law-preserving route.
- LA-056 is a new relocation-compatibility class. Schema semantics and old-FQN pickle loading are
  both members of the same public-contract preservation invariant, so cover them as one cohort.
- The selected-manifest-profile issue is the same shared-ref-selector class found earlier, and
  S1 now fixes it in source. Do not count it again as a new defect; independently rerun its
  falsifier after freeze.
- B175's earlier preflight finding is corrected in current source/test as described below; the
  helper-wide ndim check addresses the whole class.

### Current whole-property findings and executable route requirements

**B166: masked historical data must reach the actual computation.** The current orchestrator's
`_predict_with_scientist()` writes a `scientist.backtest.masked_historical_view` and a
`fabric.data_snapshot`, then sets `scientist_state.inputs.data_snapshot_ref` to that snapshot
before calling `run_experiment`. The default workflow's `BuildDataSnapshotNode` returns as soon
as that input ref exists; `BindFoundryInputsNode` then reads the snapshot and builds actual Foundry
input bindings. Its default strict ModelSpec check compares the `TrinityBundle.model_spec` data
snapshot ref with the effective ref, so an ordinary full-history model ref must fail closed when
the backtest supplies a different masked snapshot. Keep that check enabled. `RunSimulationNode`
passes the resolved bindings to `DefaultFoundryPort.execute()` and the real Foundry executor.

The current unit case `test_scientist_dispatch_binds_masked_view_to_backend_input` proves that the
mocked `run_experiment` received a masked ref and that CAS resolves its prefix. It does not prove
the default workflow consumes it. The executable extension belongs in
`tests/unit/scientist/methods/backtesting/test_backtesting.py`, reusing Trinity/Foundry fixture
construction from `tests/unit/scientist/orchestration/workflows/test_engine_default_workflow_p8.py`.
Use one `FileSystemCAS`; wrap the real `run_experiment(state, store=orchestrator._store)` rather
than replacing workflow execution, and spy on `DefaultFoundryPort.execute` by recording the
request and delegating to the original method. Bind a tiny source such as `metric=[1,2,900,901]`
at cutoff 2 through an explicit Foundry rule `metric -> agents.income`. Construct the Trinity
ModelSpec against the exact content-addressed masked snapshot (content identity makes it
reproducible), then assert the real bindings and fresh post-step state contain only `[1,2]`, never
the sentinel values; also supply a stale/full-history ModelSpec ref and assert the strict binder
rejects it before execution. Reconstruct a report through the outer `BacktestOrchestrator.run()`
and read it from CAS so an inner result alone is not counted as the whole receipt.

B166's original criterion also has the no-`intervention_step` branch. If the plan declares an
intervention date or pre-period count, the masker must materialize the corresponding time prefix
from its declared time axis or refuse an unverified boundary. Returning all rows implicitly is not
an acceptable “already truncated” assertion. A supplied already-cut view needs checkable
reference/lineage evidence that binds it to the requested boundary.

**B170: the run count must alter the real plan or explicitly return unsupported.** A complete
source search shows `n_simulation_runs` occurs only in `backtesting/plan.py` (the `ge=1` field)
and `_predict_with_scientist()` (where it is copied into params); there is no product consumer.
That function dispatches `run_experiment` once. In the default Foundry path, `RunSimulationNode`
constructs an `ExecuteRequest` from its bound `FoundryExecConfig`; `FoundryExecConfig.seed` is the
execution seed, while the copied state `random_seed` is not mapped to it. The separate
`RunCausalEvaluationNode` does read `params.random_seed` for its method-run branch, but it consumes
`observational_data_ref`, so that is not proof that the snapshot-bound default Foundry simulation
uses the backtest ref or that K replications ran. Define whether K denotes independent executions,
sampling replicas, bootstrap runs, or another object. For a supported K=3 example, assert three
real ExecuteRequests with distinct run identities and declared random streams, persisted outputs,
and requested/started/completed/failed counts. Force one replica failure and prove the report
retains the failed denominator rather than silently treating one result as three or dropping the
failure. If the product chooses not to support K on this route, return an explicit typed
unsupported outcome. Do not count an exact cache hit as an independent replicate or expand one
scalar into a repeated trajectory. The minimal focused command after the implementation and
freeze is:

```bash
cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/scientist/methods/backtesting/test_backtesting.py \
  tests/unit/scientist/orchestration/workflows/test_engine_default_workflow_p8.py
```

The command is required evidence, not run in this recovery review.

**B201: keep point functional and equal-tail interval distinct.** The current adapter computes the
posterior mean and central equal-tail quantiles, then constructs `UncertaintyEnvelope`. Its
validator still unconditionally requires `lo <= point_estimate <= hi`. The original 100 draws
with 99 zeros and one 100 therefore produce mean 1 and 90% bounds `[0,0]`, then raise. This is a
current producer/contract mismatch. Preserve mean 1 and exact quantiles `[0,0]`; represent the
point functional explicitly or make the envelope contract semantics-aware. Do not widen the
interval or quietly substitute median for mean. A lightweight synthetic-array regression in
`tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py` should assert the actual
summary, serialize/read its typed envelope, and preserve finite/ordered interval validation.

**B202: connect the summary producer to the law owner and fresh reader.**
`summarize_bayesian_calibration_posterior()` receives all draws but builds `UncertaintyEnvelope`
objects without `distribution_payload` or a draw ref; a source census finds the summary helper
has no production call site beyond its unit test. The existing Bayesian producer
`canonical_draws_artifact()` already canonically encodes `chain/draw/parameter` order, `<f8`
dtype, payload, digest, and ref; the advanced sampler returns the posterior draw payload/ref in
`result.artifacts["posterior_draws"]`. Reuse that owner artifact and connect its exact persisted
ref/selector to the calibration envelope. For small single-parameter arrays the existing
`PosteriorSamplesCarrier` is reusable; the multi-parameter route must retain actual shared rows,
weights, unit, parameter/sample axes, ordering, and provenance, not merely attach one declared
joint ID to independent scalar carriers. Bind the fresh consumer to exact content identity.

Two small counterexamples separate property from markers. For marginal law identity, compare
A=`40×0, 30×(-1), 30×(+1)` with B=`70×0, 11×(-1), 11×(+1), 4×(-sqrt(4.75)), 4×(+sqrt(4.75))`.
Both have N=100, mean 0, the same sample variance, and central 90% interval `[-1,1]`; yet
`P(X=0)` is 0.40 versus 0.70. For pairing, use `x=(-1,-1,1,1)` and `y=x` versus reversed `y`;
the marginals are identical while `corr(x,y)` is +1 versus -1. Persist both through CAS and
fresh-read them. A declared shared ID with one parameter's rows reversed must not reconstruct the
same joint law. These are pure synthetic-array tests; no Bayesian sampler or fit is required.
Current typed routes are `tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py`
and `tests/unit/ir/test_uncertainty.py`; add the source-to-artifact/readback negative there or in a
mirrored focused test. The direct helper in `test_methods.py` that runs a real sampler is not a
lightweight substitute and was not run.

**Selected-view S1 update.** Current `load_uncertainty_envelope()` passes the complete typed ref
to `get_json_artifact(store, ref)`. The new
`tests/unit/ir/test_uncertainty.py::test_uncertainty_loader_preserves_selected_manifest_profile`
creates same-content refs with different canonicalization profiles (same artifact ID), converts
the selected ref to `UncertaintyEnvelopeRef`, and reads from a fresh `FileSystemCAS`. Removing
profile forwarding must make this scenario fail. This is substantive source/test evidence for the
whole selector property, not a generated assertion that the field name exists. I did not rerun it
after the peer change; root freeze should include it in the fresh wave.

**LA-056: verify public schema and historical pickle resolution.** Current source has a neutral
canonical `ddm/contracts/events.py` and `metric_budget.py`, lazy public facades, and forwarding
modules. Existing tests establish contract-only imports, aliases and model validators, but no DDM
test references `model_json_schema`, the manual `shift_event.schema.json`, or pickle. That file's
`anyOf` is a load-bearing “at least one of p_value/e_value/ert” rule; the Pydantic after-validator
enforces the same evidence and `empirical_fp_rate` conditions at runtime, but generated JSON
schema alone does not encode the cross-field validator. Keep the manual schema and compare actual
behavior. Add one compatibility cohort in `tests/unit/ddm/test_facade.py`,
`test_readiness_mapping.py`, or `test_contract_compatibility.py`: validate the manual draft-2020-12
schema with `FormatChecker`; have the schema and model accept p-only, e-only, and ert-only payloads;
have both reject no evidence, all-null evidence, missing `empirical_fp_rate`, invalid ranges,
bad timestamps, and unknown properties. Include a property-removal case that removes an evidence
branch while leaving the rest of the schema unchanged and must reject its witness. Also inspect
canonical event and budget generated schema fields/constraints against the actual models without
replacing manual schema semantics with a marker or regenerated file.

Exercise legacy pickle globals for
`polisyos.ddm.integration.events.ShiftDetectedEvent` and
`polisyos.ddm.readiness.readiness_mapper.MetricBudgetPolicy`. Prefer frozen bytes from the old
FQNs. If unavailable, temporarily set the canonical class `__module__` only during `pickle.dumps`
to create a stream naming the old module, restore it in `finally` before loading, then assert
`pickle.loads()` resolves to the canonical class and preserves full model state/equality. A
canonical-only pickle round-trip proves no old-path compatibility. This is class relocation
compatibility, not authorization to alter the scientific DTO fields. The existing lightweight
base command is:

```bash
cd policy-engine && PYTHONPATH=src .venv/bin/pytest -q \
  tests/unit/ddm/test_facade.py tests/unit/ddm/test_readiness_mapping.py
```

Include the new compatibility module/pytest case in the post-freeze command. Nothing was executed
for schema/pickle in this recovery review.

**Current correction for B175.** `bootstrap_metric()` and
`bootstrap_scenario_metrics()` now both call `_prepare_observations()` before statistic evaluation
or RNG construction, and that helper rejects `ndim != 1` with `invalid_dimensions`. The current
test `tests/unit/scientist/methods/backtesting/test_bootstrap.py::test_two_dimensional_observations_refuse_before_callback_or_rng`
passes a finite 2-D array through both entrypoints and asserts zero callback/RNG calls. This is a
real preflight property test, not a field marker. Source/test code now covers the prior finding;
the test was not rerun under the active R4 restriction.

### Refreshed dependency hashes

These are SHA-256 hashes of the current working-tree bytes at this recovery reread; pinned source
documents are identified by commit/blob separately. They must be refreshed after the declared
peer source freeze. Paths are repo-root-relative.

| File | SHA-256 |
| --- | --- |
| `policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json` | `97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01` |
| `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md` | `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5` |
| `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md` | `2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727` |
| `policy-engine/src/polisyos/scientist/methods/backtesting/plan.py` | `4e68219b6f8e3e5a6d3f9e921662b773757e732a822df27cb333150bde624fce` |
| `policy-engine/src/polisyos/scientist/methods/backtesting/masking.py` | `24483fed9ee006f0cc9ce3396fb96ad7ae247a7515e01d067daac550ff5bd0d6` |
| `policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py` | `53b99e93d0da5c5a07dd8e9d99cbb50df99a0819b7fb98d31a07c3d195cb4908` |
| `policy-engine/src/polisyos/scientist/methods/backtesting/bootstrap.py` | `eb8ae5af0f32881b41a5fd229666050c81ad9790ff6f3deea28ebb407b25c47f` |
| `policy-engine/src/polisyos/scientist/orchestration/workflows/default.py` | `fb6d0c3b328db0785b85402aabadfca5de64ddfb973ca0e8904f7ad71030bd9c` |
| `policy-engine/src/polisyos/scientist/orchestration/workflows/builder.py` | `39b0a80bf4e336e42f60a32f44011869309b74f1d1297cab6705298320b26c95` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py` | `383b3cbc50d8206a77091ec0fc3af970e59bb14b153ebc24fe015f3a1ef2ec53` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py` | `d8821a51d417d90edc265eabbc9c544ca04e5602fe613094425a3fb8c95812dc` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py` | `4d03be430b29334f6e4aea32f02e065044881b17519f17bffe2bd232ce4c783b` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py` | `d5baee1836115d8757ae80e3c6f7d7ea6e7c9b831128685bd41c4447c1466744` |
| `policy-engine/src/polisyos/scientist/adapters/foundry_bridge.py` | `c65da18921a1f868f513180d5dd404e9c566ba380737c4f977817cd2530422f7` |
| `policy-engine/src/polisyos/foundry/data_plane/bindings.py` | `67f724b4707781bf361f0bbf59cefaa77e4f6dfd31fce94dcdedd31aa96d53ee` |
| `policy-engine/src/polisyos/foundry/execute/api.py` | `083d9692e173f45b21206a83081f6b4afa501788b545dddbaaec2cbcc64d355f` |
| `policy-engine/src/polisyos/core/contracts/foundry.py` | `02a038f9e8272fe168f5c5a3d9ea46919e1f4309fa308693bb8fe63d08c0438d` |
| `policy-engine/src/polisyos/scientist/api.py` | `8c18960085bb5c519fa9fcfe7f7a57aad8413151c4fffbd22120a38ed1110ff3` |
| `policy-engine/src/polisyos/scientist/compute/runner.py` | `9f2d3fad636d5b1125d77afe584d568bee4ee13e9fce3ddeb73e7478d27dfd77` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_backtesting.py` | `e90af4e42093ff1f846747785f04d8ec61e0ee7d68e5fcc7d2807e021d703633` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_bootstrap.py` | `1e1a7d787a79075746d4000931837391f45d6f2a437edf94f532aab1db727ab4` |
| `policy-engine/tests/unit/scientist/orchestration/workflows/test_engine_default_workflow_p8.py` | `748769cad9161b4e0dd77f134c66e5a2b6b7cabeefa4f5bfd27c19678a831549` |
| `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py` | `83c1d54bdb5bcd931abe2b6f95fcc4a8630a26f0d45f668b616a960478604c0e` |
| `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py` | `76a4961b9c32f4a8a021796617d84bbc68420d4ef11548c5f21bf39d21291841` |
| `policy-engine/src/polisyos/ir/analytics/uncertainty.py` | `6d0b1d550581d6a1305ec70335ccde5cccb88422a3cf6fabe03923afd0540ab5` |
| `policy-engine/src/polisyos/ir/registry/refs.py` | `bbac14368f7091bf8135f621999e9b702d711c31a95e87e7ceaa1bd963c8fe72` |
| `policy-engine/src/polisyos/ir/artifacts/io.py` | `2b8805c49aa2446c7930eee7265b30154c5a450955eac57d152123d78441cadc` |
| `policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py` | `2679d546e048f466ceb96a80d69571ee953d0a402a596d423cc04e2c2d4ac9b1` |
| `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/advanced.py` | `2a2db025e2f187b6ad70eee1a90f288347ece06b797d9af7bf3b2583547f4b11` |
| `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/protocols.py` | `be9ae1dd65693ec818fd36d2bf2d88b36f86c15e4706e5966399ae6bc353d86e` |
| `policy-engine/tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py` | `868a42e317bed65571cde0aa9d9846153bf32a8b476e41fbed6648f013cab50b` |
| `policy-engine/tests/unit/ir/test_uncertainty.py` | `e143a946fe90d9a466f4b5cf60b9f586acaf272ec35feffb7613e346ee6d208a` |
| `policy-engine/tests/unit/foundry/methods/catalog/bayesian/test_methods.py` | `87e8c1ebcee419ce0eb13bf47a904e65539135209bd8c42e71db2a2452592d77` |
| `policy-engine/src/polisyos/ddm/contracts/events.py` | `bb61dc020f9c905b7a3b47a9cec4ebdd98b002be5bb5692919bddc117a7a7ab7` |
| `policy-engine/src/polisyos/ddm/contracts/metric_budget.py` | `5f607000142ec570fdbd89297ea00039b7e2b2fef6cf825753eac24e7f4a4cdc` |
| `policy-engine/src/polisyos/ddm/__init__.py` | `adbf26cc868a931b8ad4b2951558a065a52169a5d55acb3993e137d6657322fc` |
| `policy-engine/src/polisyos/ddm/integration/__init__.py` | `426bfbc35a951ff24434e755720fc7592ec27386ce046a7db3d05d07baff62b8` |
| `policy-engine/src/polisyos/ddm/integration/events.py` | `894151bedc3046b2b41c469f15b42565818162dbd8d7a3d2d587a36ebcc9eb50` |
| `policy-engine/src/polisyos/ddm/integration/shift_event.schema.json` | `1bb48c1e7bd3531d8a8e81213f392f42fd91649654e41b42a8a4a2fb76045f65` |
| `policy-engine/src/polisyos/ddm/readiness/__init__.py` | `cbd5315749bc31f57206b1a35b9c87e7ad066e4e43524fbece3077bfb2acbc13` |
| `policy-engine/src/polisyos/ddm/readiness/readiness_mapper.py` | `040c993e244c868c897456429738e5140c9607eae4157cca33b70c849f9ca7d0` |
| `policy-engine/tests/unit/ddm/test_facade.py` | `9a1cb844e71ea17c4ae3baf78964954f1d3cb251be2d3c0ba493f4355e66737e` |
| `policy-engine/tests/unit/ddm/test_readiness_mapping.py` | `eb802a8ad8435695812b4a059172923ac0c46b3f64335b1fca9778d4b184656b` |

The B175 code/test hashes above identify a current source implementation and adversarial test,
not an executed result. The E review itself makes no formal G adjudication or closure.

## Delta reread after DDM compatibility tests and the native backtest route

This appendix supersedes the earlier LA-056 “schema/pickle tests missing” statement for the
reviewed DDM paths. At reread time HEAD was root-authored descendant
`a49909826cf87f164dae36c26b21fb5d188ca835` (tree
`bdce171c3fa6a3fc7781b42ea2523af1c0c5f2ab`). LA-056 tests were committed in
`704082ef53d8e5aca645fd814b9c85b5db3e5168` (tree
`820db8cf6994f916e8d07592da9ac5befc877d80`, parent `80f043c0c007ca14dfd4927f980e391f4fcdc62a`).
`git diff --quiet 704082ef HEAD -- <DDM source and three test paths>` returned 0, so the
committed DDM denominator was unchanged by subsequent peer work. Backtesting orchestrator/unit
changes and the new native integration test were still dirty/uncommitted at this reread; their
hashes below identify only the current working-tree candidate and are not a freeze receipt. Other
declared peer edits remain outside this oracle.

### LA-056: observed compatibility evidence and one bounded semantic gap

The original criterion is `coverage.json#/findings/117/criterion_refs/0` (ID LA-056, original
source hash `846f644e4daca7f4a4828a626a08dbf8e659d06028fc902b85878a690b3ac801`); source text is
`source/LA_r09_original.md` lines 4141–4171, pinned with the E packet above. It requires neutral
contract ownership/imports and preserved event/budget public identities, aliases, validators,
wire forms, exports, schema semantics, and supported legacy pickle FQNs. The latest addition is
`tests/unit/ddm/test_contract_compatibility.py`; facade/readiness tests are extended. Production
contract classes and the manual `shift_event.schema.json` were not changed by commit 704082ef.

Fresh command from `policy-engine/`, using only the repo-owned environment:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/ddm/test_contract_compatibility.py \
  tests/unit/ddm/test_facade.py \
  tests/unit/ddm/test_readiness_mapping.py
exit 0; 22 test cases passed
```

The interpreter was `policy-engine/.venv/bin/python` 3.14.3 with Pydantic 2.12.5 and jsonschema
4.25.1. The manual schema is loaded from the real tracked file and validated with Draft 2020-12
and a format checker. The positive/negative matrix covers each evidence channel, absent/all-null
evidence, missing empirical false-positive rate, numeric bounds, invalid timestamp, and unknown
properties. The removal control deletes only the `p_value` anyOf branch while keeping field
markers and proves that a p-only witness which both original model/schema accept is rejected by
the weakened schema. This is a property-removal probe for the manual evidence disjunction.

Legacy FQN pickle tests temporarily set the canonical class `__module__` to each old path only
while `pickle.dumps()` builds bytes naming that global, restore the canonical module in `finally`,
then `pickle.loads()` and compare exact canonical type, Python `model_dump`, `model_fields_set`,
and `__dict__`. Historical source inspection at the parent of relocation commit
`3624fd88228b086f253028a8b8dca16a89f1289d` (`cc78098dc3b904ed398ce423a4f86777fe65fcf7`)
confirms `ShiftDetectedEvent` existed at
`polisyos.ddm.integration.events.ShiftDetectedEvent` and `MetricBudgetPolicy` at
`polisyos.ddm.readiness.readiness_mapper.MetricBudgetPolicy`; the relocation diff moves the same
field/validator bodies to `ddm.contracts`. The test genuinely checks current legacy-global
resolution and full current instance state for both old paths. It is synthetic compatibility
evidence, not a fixture emitted by the historical class or a prior Pydantic release; historical
byte-level compatibility remains bounded to the old module/global lookup and current instance
state.

One concrete wire/model coverage gap remains within the same relocation-compatibility class
(P40: same class one level deeper; widen the contract test rather than treating it as a new
class). The matrix always includes the model defaults `event_type` and `diagnostic_only`.
Removing both from an otherwise-valid p-only event makes the manual schema reject it, while
`ShiftDetectedEvent.model_validate()` accepts it and fills defaults (`event_type` literal and
`diagnostic_only=False`). Direct probe output:

```text
manual_schema_valid_without_defaulted_keys=False
model_valid_without_defaulted_keys=True
resolved_defaults=ml.track_2_2.shift_detected.v1 False
default_dump_schema_valid=True
```

The defaults serialize back to a schema-valid full event, so this is not evidence that ordinary
model output violates the wire schema. It is evidence that model input acceptance is broader
than the manual required-key profile. The external schema explicitly requires both keys while
the Python defaults provide ergonomic construction, so preserve and pin this existing
wire-stricter/model-default boundary in the test matrix rather than changing either DTO or schema.
The current matrix does not yet include that separate expected-validity case. Do not replace the
manual schema with generated Pydantic output: its `anyOf` is load-bearing and generated DTO
schema still does not express the cross-field evidence rule. No formal LA-056 closure is proposed
by this review.

### B166/B170: real producer/bridge evidence and residual whole-property work

Original sources are `coverage.json#/findings/82/criterion_refs/0` (B166 source hash
`fca923e26ad0c81b5a1097f0c5b09b3a85434faf70826001b2e5d6c676e8a541`) and
`#/findings/87/criterion_refs/0` (B170 source hash
`ebd468778c34a525226f1631f17dbb9eb3e040a6c9a5d96d038620576528181a`), from pinned B source
lines 4316–4327 and 4364–4375. The new dirty candidate test is
`tests/integration/scientist/methods/backtesting/test_backtest_foundry_replicas.py`; the runtime
owner is `src/polisyos/scientist/methods/backtesting/orchestrator.py`.

Source inspection confirms this is no longer only the earlier `run_experiment` stub route. The
integration constructs one real CAS and registry, persists a `TrinityBundle` whose `ModelSpec`
names the masked `DataSnapshotRef`, binds that bundle to the plan, runs actual
`run_experiment()` through `DefaultFoundryPort.execute()` into `foundry.execute.api.execute()`,
and captures the actual `FoundryInputBindings`/bound state at the real port boundary. With a date
cutoff at `t2`, raw values `[1,2,900,901]` bind as `[1,2]`; the test loads the persisted snapshot
and proves both post-cutoff sentinels are absent. Missing and unresolved cutoff controls refuse
before masked-snapshot persistence/Foundry execution, and a full-history model snapshot mismatch
fails at `bind_foundry_inputs` before any Foundry call.

For K=3, source creates distinct run IDs and seeds `base_seed + index`, sets the per-run workflow
count to one, and the wrapper copies that seed into an explicit `FoundryExecConfig.seed` on a
fresh `ExecuteRequest`. `DefaultFoundryPort` directly calls `foundry.execute.api.execute`; that
API resolves the explicit config seed, passes the resolved seed into `execute_program_graph`,
and persists `seed_source:exec_config.seed` in `SimulationResult.notes`. The integration checks
the three physical request seeds, distinct request objects/run IDs, workflow report identities,
simulation/metrics refs, and one CAS cohort with requested/started/execution/completed/failed
counts. The source intentionally refuses to project multiple runs into a single statistic and
returns a degraded naive report with `scientist_replica_projection_unsupported`; individual
simulation and metrics refs remain in the persisted cohort. This supports explicit unsupported
projection while retaining the denominator/artifacts; it does not establish a statistical
distribution or sufficient-statistic consumer.

Two integration assertions are still needed for the whole original route. First, `run()` persists
`BacktestReport` and its manifest links the cohort, but the new test only reads the in-memory
report and manifest. Load the written report through
`polisyos.ir.analytics.backtest.load_backtest_report()` using the `BacktestReportRef` for
`report.cas_artifact_id`; assert scenario `replica_cohort_ref`, degradation reason, and values
survive fresh CAS deserialization. Second, current real-port K=3 test is all-success; existing
unit failure coverage uses a fake Foundry port. Add an isolated K=3 route test which fails one
replica at the `DefaultFoundryPort.execute` seam while the other two delegate to the real method,
then read the cohort/report back and assert requested=3, terminal completed+failed=3, failed
replica identity and no success projection. This would prove orchestration failure retention
through the actual bridge, while explicitly not claiming a native numerical/backend failure.

P40 classification: B166 and B170 remain the same backtest-to-real-runtime boundary class, with
B170 the deeper replica/failure-retention facet. Widen the one real integration route to fresh
report readback and a controlled port failure; do not count further seed/call assertions as
separate ladder rounds. No numerical fit or heavy suite was run because the single native-fit
slot was assigned elsewhere. This is source/test review of mutable q1 candidate bytes, not a
pass receipt or G acceptance.

### Refreshed source/test byte references for this reread

Original-source document hashes and the 43-row E/36-row G-intake denominator remain as pinned
above. These are current working-tree hashes for the reviewed source/test dependencies; mutable
backtesting files are not frozen.

| File | SHA-256 |
| --- | --- |
| `policy-engine/tests/unit/ddm/test_contract_compatibility.py` | `89ee7b3414a41a2eb769f753b4616b0683fde513a9a95571811d759067a76e25` |
| `policy-engine/tests/unit/ddm/test_facade.py` | `8ec5c49f05af963762f8fdb583ce71ea6258a3ef5300bc51d51ff782a3ee4491` |
| `policy-engine/tests/unit/ddm/test_readiness_mapping.py` | `2e42c1f75113a8a443610e143497a2d9a0356154119da83bc564075bba9e0f95` |
| `policy-engine/src/polisyos/ddm/contracts/events.py` | `bb61dc020f9c905b7a3b47a9cec4ebdd98b002be5bb5692919bddc117a7a7ab7` |
| `policy-engine/src/polisyos/ddm/contracts/metric_budget.py` | `5f607000142ec570fdbd89297ea00039b7e2b2fef6cf825753eac24e7f4a4cdc` |
| `policy-engine/src/polisyos/ddm/integration/shift_event.schema.json` | `1bb48c1e7bd3531d8a8e81213f392f42fd91649654e41b42a8a4a2fb76045f65` |
| `policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py` | `a5e8d90d02b6314a112f85adb6876e85c2528f8b37d83f1e8c0215c6467306cc` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_backtesting.py` | `5df3a2adafae439ddef016e37bf1e17c731972fcc641fbbafca01a3f85588600` |
| `policy-engine/tests/integration/scientist/methods/backtesting/test_backtest_foundry_replicas.py` | `2569d4a22de21063c296248654c15fff2da2a2ad7ca496493f64d93cd317369f` |
| `policy-engine/src/polisyos/foundry/execute/api.py` | `083d9692e173f45b21206a83081f6b4afa501788b545dddbaaec2cbcc64d355f` |
| `policy-engine/src/polisyos/foundry/execute/_internal/posture/__init__.py` | `0e8b542bb50f2ba617d1ffb1aa6ecbc6be826597d03ca4d79de4b12bb39171d5` |
| `policy-engine/src/polisyos/ir/analytics/backtest.py` | `dba991d316581ac662f2d0b7e3f79a8831d8461409475c1fe949075b40ff49e6` |

### B201/B202 current candidate delta

The original criteria remain B201 lines 4978–4991 and B202 lines 4992–5005 in pinned
`source/B_r19_original.md` (the coverage refs/hashes are in the inventory above). The mutable
candidate now adds `ir/analytics/posterior_summary.py`, `MonteCarloPropagator.propagate_posterior_summary()`,
and `foundry/calibration/uncertainty_adapter.persist_posterior_summary_from_method_evidence()` /
`load_persisted_posterior_summary()`. A new integration test
`tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py` runs the native HMC
method through `run_job`, reads its persisted `scientist.method_evidence`, builds the candidate
summary, fresh-reads it from CAS with method-evidence lineage/profile checks, then sends exact
paired rows through the Monte Carlo consumer and asserts evaluator inputs/output draws. I did
not run it because it executes native HMC while the root-owned heavy slot is active.

The source/test shape now materially improves the prior B201/B202 evidence:

- B201's 99-zero/one-100 witness is represented in a v1.1 summary with separately named mean,
  median, equal-tail interval, and selected point. The new consumer never coerces that output to
  `UncertaintyEnvelope`; the test also asserts that the old envelope rejects mean 1 with bounds
  [0,0]. This is a candidate path only, and explicitly stays `gate_eligible=False` and
  `unit_binding_status=not_established`.
- B202's source parser recomputes canonical bytes/hash/ref and reads common chain/draw axes in C
  order; `PosteriorSummaryV11` retains exact draw values and original payload, and the consumer
  constructs a content-digested joint input matrix from aligned named rows. The unit adversary
  uses same marginal arrays with reversed pairings and demonstrates distinct ordered joint rows.
  Weights are explicitly rejected rather than dropped, and unit meaning is left unknown rather
  than inferred. The new native-HMC integration also checks method-evidence artifact and selected
  manifest-profile lineage through fresh CAS load and consumer output.

The original B201/B202 entrypoint remains unresolved. The existing
`foundry/calibration/uncertainty_adapter.py::summarize_bayesian_calibration_posterior()` still
sets envelope `point_estimate` to `np.mean(draws)`, bounds to equal-tail quantiles, and creates an
`UncertaintyEnvelope` without a `PosteriorSamplesCarrier` or a source ref. Its known 99-zero/one-
100 input therefore still conflicts with the existing envelope point-in-interval validator, and
that adapter still drops the draw rows for the existing envelope consumer. The new method-
evidence path has no production source callsite (`rg` shows definitions plus docs/tests only), so
the integration test proves a parallel candidate route, not that the original calibration
producer now preserves and hands off its existing draws. B201/B202 remain **partial** until the
original adapter route is wired to the new summary/carrier and a real consumer, or the work is
explicitly bounded to method-evidence HMC candidates with the legacy calibration route held out.

P40: this is the same B201 point-versus-interval and B202 lossy-source classes one level deeper,
not a new class. Widen the producer/consumer mechanism or state the bounded residual. Smallest
remaining discriminatory test: send 99 zeros plus one 100 through the original public calibration
adapter and verify mean=1 and equal-tail [0,0] remain separately representable; for B202, feed its
actual existing producer's paired source into a fresh persisted consumer and reverse only one
parameter's row order while retaining equal marginals, proving the consumer changes the joint
output or rejects the broken content binding. Do not run a native fit just to fabricate this
small deterministic sample; isolate it at the existing adapter input seam. No G adjudication is
made here.

Working-tree byte refs for the new candidate and remaining original adapter route:

| File | SHA-256 |
| --- | --- |
| `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py` | `fe2dcb4a6c78653876810930846ff6d470f19ce1c6e180d7b780af21ae4dda1a` |
| `policy-engine/src/polisyos/ir/analytics/posterior_summary.py` | `76f02f2c0064147b6b26999ef1d7e5706dfbee7f17109c2d103ea515f27e82b0` |
| `policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py` | `17d6c76e872d64abcd551d0b60586dfc1917e886e93eaca88deddb62bc885560` |
| `policy-engine/tests/unit/ir/analytics/test_posterior_summary.py` | `08d380e1eb3934b37b13083c431c7b87159c7574df78ff29e3fde50f6b7f0dbb` |
| `policy-engine/tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py` | `7c9081c2f2c3313c3ae9767ea13d4c21da0ab77e339ace3d81c8c1901beb7b92` |
| `policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` | `0e2030f2e8db51f4374442ae67cd51548328bea812920000805eb5a3171deea4` |
| `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/protocols.py` | `be9ae1dd65693ec818fd36d2bf2d88b36f86c15e4706e5966399ae6bc353d86e` |
| `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/advanced.py` | `2a2db025e2f187b6ad70eee1a90f288347ece06b797d9af7bf3b2583547f4b11` |

### Current E delta reread: B166/B170, B201/B202 (mutable source snapshot)

This reread keeps the original-source bindings above: B166 is coverage finding 82 / criterion
occurrence 0, B170 is finding 87 / occurrence 0, B201 is finding 121 / occurrence 0, and B202 is
finding 122 / occurrence 0. In E's immutable 54-row source packet these are rows 10, 14, 45, and
46 respectively. The 43 E author proposals and 36 G-intake candidate subset remain inventories,
not formal decisions; nothing in this review changes the 0 formal G closures.

P40 buckets up front: B166 and B170 are the **same** backtest-to-runtime class, one level deeper
at actual replica dispatch, fresh report readback, and failure retention. B201 and B202 remain
their **separate original classes** (point-functional versus interval semantics; lossy source and
joint-law preservation). The new uncertainty artifact limitations are not a new class. This
snapshot is read-only, mutable, and is not a test receipt or a closure decision.

The q1 route source now has two real-bridge integration cases in
`tests/integration/scientist/methods/backtesting/test_backtest_foundry_replicas.py`. The success
case calls the actual `run_experiment()`/`DefaultFoundryPort` route three times; it checks the
masked CAS `DataSnapshotRef` at the bound Scientist state, excludes post-cutoff sentinels, checks
three distinct requests/run IDs and seeds 31–33, reads the `BacktestReport` freshly from CAS, and
checks the persisted cohort remains linked and projection is explicitly unsupported. A second
case raises at the middle real-port seam and delegates the other two calls to real execution; its
fresh report/cohort readback asserts requested=3, completed=2, failed=1, failure identity, and
naive/degraded output. That is meaningful coverage for both original criteria, with the bounded
interpretation that the controlled exception is not a native backend failure. Root still reserves
the native K=3 positive and failed-replica run; both remain **UNRUN**, so these source assertions
are not runtime evidence. Current mutable hashes: `orchestrator.py`
`82b3594a3d122d34fcf3a125c0ff4abd51dbda024857a79dee7b8c93c05bb42e`;
`test_backtest_foundry_replicas.py`
`5d883f6686d1e92f2851c91f87b8e992c3311a2b7a7f06c72ad8e59f18c9fd70`.

The latest `uncertainty_adapter.py` readback adds `candidate_store` to the original legacy
`summarize_bayesian_calibration_posterior()` producer. If a point mean lies outside its equal-tail
interval and the caller supplies a store, it persists an off-interval, caller-input-only candidate
and returns `persisted_candidate_ref`. The candidate has separate `posterior_mean` and
`numpy_quantile_linear` declarations, exact draw carriers/input shapes/row matrix, and explicit
unit, row, source, and gate limitations. Its loader recomputes the original summary from the
retained inputs and rejects a stale point/interval. In the 99-zero/one-100 witness, this avoids
constructing the invalid envelope and keeps mean 1 and interval [0,0] distinct. This materially
improves the B201 producer-to-CAS candidate path; it does not authorize the summary or establish a
downstream consumer. The separate HMC/method-evidence v1.1 path does not replace the legacy
calibration producer.

B202 remains partial at the required paired-law route. The legacy summary retains a caller-side
row matrix and per-parameter carrier, explicitly with `row_relation_status=not_established` and
`source_binding_status=caller_input_only`. The off-interval candidate is persisted only when
there is an off-interval limitation; ordinary representable multi-parameter pairing cases do not
get this artifact through the new option. The actual legacy `MonteCarloPropagator.propagate()`
still refuses multiple carriers without one shared `joint_sample_id` (`unestablished_joint_law`),
so the reversed-pairing source rows do not reach a consumer output. Per-parameter CAS carriers
cover the representable single-parameter case but do not preserve one selected joint artifact,
weights/source lineage, or a consumable pair identity. The HMC v1.1 source-bound candidate uses a
different producer. This is the same original B202 law-preservation class; bounded explicit
refusal is honest but leaves the original multi-parameter consumer property unverified/unavailable.

No tests were run in this reread. S3 was still editing when read, and the instruction was to wait
for S3 readiness before changed tests. Current source fingerprints at the reread: legacy adapter
`9736739f5532150455110b704e4424d9b9a69f1ea28ec1b53c1aa05326c5ffe4`, posterior-summary owner
`76f02f2c0064147b6b26999ef1d7e5706dfbee7f17109c2d103ea515f27e82b0`, Monte Carlo consumer
`6365388d6c8fc64398e41ce61393a377b1813799c9293c68a927f18a6b6f8e2a`. Recheck these hashes
after source freeze before attaching any execution receipt.
