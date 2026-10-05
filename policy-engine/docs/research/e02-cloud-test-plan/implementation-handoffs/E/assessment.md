# E: bounded numerical implementation and integration handoff

This is an E verification aggregate, not G's canonical integration checkpoint.
G should fetch the original topic SHAs in the companion receipts. The aggregate
cherry-picks those implementations for joint regression; original receipt SHAs
intentionally identify the original topic trees. No source ledger status is
changed by this report. No production history or source-law bytes were uploaded.

## Denominator and transferred evidence

The initial command was
`python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit E --failures-only --limit 30`.
It returns three FRC-01 cells, not the E denominator. A complete CSV-aware join
of `results/routes.tsv`, `results/cells.tsv`, and
`full-run/finding-routes.json` resolves 22 bundles, 54 findings, 487 routes,
175 distinct cells and 56 distinct existing test paths. There are no unrouted
E findings. The source register has 49 partial, four held, and one closed
finding (B198). These source statuses remain unchanged.

| Source commit                              | Cells | Transferred state | Source ref                             |
| ------------------------------------------ | ----: | ----------------- | -------------------------------------- |
| `69780761ae091d8fcc6ab8778c7f5f7227eeef0b` |    56 | 55 PASS, 1 FAILED | research_main                          |
| `78187878ee188ff6d27442ba1498bd094da9785b` |    20 | 20 PASS           | e02_execution_base                     |
| `00d946c2b7d052522be092f9c70eb9902f6521c2` |    39 | 38 PASS, 1 FAILED | e02_head                               |
| `5fd3ebcc15637e98bbd4938de5d62ee5004504a8` |    20 | 20 PASS           | see per-job context; no inferred alias |
| `0213101b6d124e6f855b1aff7c442bb0912a61c2` |    40 | 39 PASS, 1 FAILED | integration_head                       |

The failed cells are F04-P095, F08-P097 and F13-P109, each with 5 PASS/2 FAIL.
Their exact event/source/environment/input/backend resolutions are in
[frc.json](frc.json). Source text is institutionally supplied compact evidence;
raw archives were not transferred. A PASS cell is not semantic closure.
For any finding, use `results/query.py --finding ID --details --job-context
--limit 200 --block-limit 200` to resolve its original cells and source lines.
The original committed test blob and inline fixtures identify the accessible
data; custody of source VM inputs and production data remains unestablished.

## Coverage of all 54 findings

"Existing controls" below means candidate native tests on the aggregate and
the scoped family checks in the receipts. It does not establish production
invocation, source-law adequacy, or authority. All unchanged partial findings
retain their residual owner/input requirements.

| Bundle | Findings               | Bounded disposition and backend                                                                                                                                                                                                                                                                               |
| ------ | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| BKT-01 | B166, B169, B170       | Existing historical-view, prediction-kind and replica controls; NumPy/native CAS. Real local history and caller-owned content-bound inputs remain required.                                                                                                                                                   |
| BKT-02 | B167, B168, B171       | Existing complete-comparison, nominal-coverage and micro/macro controls; NumPy/native CAS. Production coverage campaign remains local.                                                                                                                                                                        |
| BKT-03 | B172, B173             | Nonzero per-error support with unavailable statistical test now withholds trust even for zero/tiny mean. Genuine SciPy and backend-denied controls, persisted report readback. NEUTRAL remains descriptive, not a statistical acceptance.                                                                     |
| BKT-04 | B174, B175             | Existing selected-fold CV controls; bootstrap retains the performed statistic identity. NumPy percentile bootstrap; custom callable identity is consumer_asserted and does not establish its mathematical meaning.                                                                                            |
| CAL-01 | B176, B177, B178       | Existing observation/calendar/imputation admission controls; actual native calibration inputs. Missing observations do not acquire support.                                                                                                                                                                   |
| CAL-02 | B179, B180, B181, B182 | Existing effective-loss, axis, weight and masked-scale controls; independent real JAX zero-support primal/gradient/Hessian oracle and divergent unsafe-where control.                                                                                                                                         |
| CAL-03 | B183, B195             | Existing multi-start span lifecycle and eligible-selection controls; native Calibrator/JAX. No served lifecycle claim.                                                                                                                                                                                        |
| CAL-04 | B184, B196, B203       | Existing last-iterate/final-forward/Hessian reuse controls; actual JAX Hessian and explicit analytic inverse comparison.                                                                                                                                                                                      |
| CAL-05 | B185                   | Mapped schedule predicates are refused before numerical emission. Real JAX callbacks, JIT, gradient, Hessian and PRNG controls preserve scalar state-vmap and lax.map behavior. Python tracing is distinct from numerical execution.                                                                          |
| CAL-06 | B197, B198             | Existing tied-parameter/conditional-law controls. B198 remains closed in the source ledger. B197 remains held for a configured served Calibrator and consumer admission.                                                                                                                                      |
| DDM-01 | LA-056                 | Test-only strengthening of actual lazy facade, canonical class/FQN and source-origin controls in fresh child processes; Python/Pydantic. No deployment event/budget authority claim.                                                                                                                          |
| DDM-02 | LA-054, LA-055         | Existing private checker/report/gate/override controls; live feed, principal, deployment and public handoff contracts remain not_established. P40 STOP is retained.                                                                                                                                           |
| DOE-01 | B97, B98, B99          | Existing bounded-generation and declared-round controls; native NumPy/SALib. No undeclared adaptive round is promoted.                                                                                                                                                                                        |
| DOE-02 | B100, B101             | Existing declared distribution design/local RNG controls; genuine SALib, with the Morris positive fixture made geometrically valid.                                                                                                                                                                           |
| DOE-03 | B102, B103, B104, B105 | Shared original Morris geometry admission before point/PCA/EE/stability; whole-trajectory bootstrap; original failed support refused for ranking stability. Genuine SALib 1.5.2, units/order/grid controls, serialized consumer readback. No full Sobol/FAST or unknown-law claim.                            |
| FRC-01 | B32                    | Two failures remain: stale positive witness and A-owned limitation-ref omission. E never edits generation_cycle.py; A recipe is in frc.json.                                                                                                                                                                  |
| FRC-02 | LA-051                 | Genuine NumPy ETS producer preserves method/version and admitted rule binding. Equal forecasts with different holdouts produce 3/3 vs 0/3. Missing evaluation context stays predictive_only/bridge_pending.                                                                                                   |
| PCL-01 | LA-052, LA-053         | Incomplete comparison cannot yield a positive calibration flag; finite/domain checks shared across continuous preparation. Native NumPy coverage/IR readback. Equivalent numeric tests moved to canonical calibration owner; Scientist alias sunset needs its owner.                                          |
| UQP-01 | B186, B189, B190, B191 | Existing real response/full effective-call controls; native JAX/NumPy, including actual uncertainty node controls. This does not identify a served evaluator.                                                                                                                                                 |
| UQP-02 | B187, B188, B192       | Three unequal covariance axes independently verified. Gaussian MC preserves declared joint covariance/singular support for random, Sobol and Halton draws; independent-law negative controls retain variance about 2. Declared Gaussian law is candidate-only. Empirical-law carrier controls remain bounded. |
| UQP-03 | B193, B194             | Existing non-divisible adaptive stop/distribution-width controls; actual MC/JAX draws. Failed-support observer checks float32 and float64 per-draw identity/reasons. B194 remains held for the served evaluator/intake.                                                                                       |
| UQS-01 | B199, B200, B201, B202 | Existing summary/independent-unit controls; native NumPy/Pydantic. Public point/interval functional and ordered joint source-law carrier decisions remain held.                                                                                                                                               |

## Held decisions and local inputs

- B194: owner of the served simulation evaluator must supply a deployment-bound
  selector, actual response call and per-draw outcome identity. The authority
  intake owner must admit the persisted report/envelope for ConfidencePass,
  arbitration and decision packet. The affine frozen-metrics node and internal
  callbacks are bounded witnesses, not an invented served evaluator.
- B197: Calibrator owner must supply the configured served instance, admitted
  source/graph/plan, v2 report and consumer-specific kind/schema intake. Internal
  Calibrator-to-report-to-reopen-to-welfare controls cannot establish this.
  FunnelCalibrationReport is a separate model and must not be substituted.
- B201: public IR owner must choose/version the point functional independently
  of the interval functional. The skewed fixture of 99 zeros and one 100 has
  mean 1 and equal-tail interval [0,0]; an owner decision is required, including
  historical v1.1 replay. E does not invent a functional.
- B202: public IR/source-law owner must choose an existing posterior samples
  carrier or content-bound CAS law reference, preserving axes, weights and
  ordered joint draw identity. Equal marginals with different pairings are a
  divergent control. Production persistence/reload remains local.
- LA-054/LA-055: public DDM model/application validity handoff, model registry,
  real feed, principal and deployment inputs remain unestablished. Preserve
  P40 STOP even when private implementation tests pass.

For G's local check, fetch the exact original implementation SHA, use its
receipt's command and backend versions, and retain a local input manifest with
CAS identifiers/content hashes, schemas, units, time roles, model/plan/rule
versions, axes and ordered draws. Retain private bytes locally. Run the actual
producer, reopen its artifact using the named consumer, and record numerical
support/eligibility and the explicit limitation. Change the defining input
while keeping declaration fields unchanged: holdout history/time/model,
covariance axis order/joint pairing, per-draw failure or original Morris block.
Record the observed divergent result and implementation SHA. A missing owner
decision or producer selector stays held/not_established rather than being
filled with a synthetic replacement. Individual receipts give constructor,
selector, seed and negative-control recipes; they do not request private data
to be transferred to cloud.

## Integration boundaries

All topic branches start at `c40d4acae1ce58b597267255026d9356565828fd`.
A alone applies the producer-to-generation-cycle bridge after a Git checkpoint.
Neither generation_cycle.py nor run_lifecycle.py is changed by E. No main push,
force push, history rewrite, or merge was performed.

The additional composition readback slice is limited to E's backtesting
consumer. The intentional core ref normalization writer belongs to B/STA-01;
it is preserved. A real repeated ReconcileCausalGraphNode call also exposes
the same missing normalization in its precomputed-alignment and query hook
readers. Those Scientist paths need G to assign their owner; they are not
silently patched by E.

Full repository architecture/CI checks are reported separately from numerical
properties. Multiple repository-wide invocation scans ended with SIGKILL or
explicit termination after observed resource growth and produced no candidate
verdict. Receipts mark ERROR, never PASS. Red architecture/CI results have
attribution not_established unless both exact slice-base replay and a zero
input-denominator intersection prove otherwise. Numerical processes were not
artificially capped; actual wall time, RSS, environment and outputs are retained.

The companion aggregate receipt supplies frozen check SHAs, complete deciding
outputs, remote branch/PR readbacks, environment differences, integration commit
mapping and the final numerical/global-gate outcomes.

## Frozen aggregate results and published topics

The tested aggregate is `c0f8ab8cdad33a239be542ce23c1648f72707bc5`, tree
`fffe19a0f752efdc2caed549fd0219d56ef0d5fc`. Later commits append receipts and
this report; the product source, tests, configuration, architecture, schemas,
release fragments and apps are byte-identical to that tested checkpoint.

- Final 59-file regression: **654 PASS, 2 FAIL, 0 errors/skips**, 656 collected.
  Wall 122.42 s, peak child RSS 2,451,684 KiB. Both FRC01 failures remain in the
  command. Composition's earlier four failures are repaired.
- Architecture guardrails: **FAIL**, exit 1, wall 250.56 s, peak child RSS
  1,102,448 KiB. Full output identifies deep import creep and generated runtime
  OpenAPI/trust posture drift. Attribution remains `not_established`; no
  inherited exemption or check weakening was used.
- Independent adaptive/coverage/bootstrap witness: **PASS**, plus 78 native
  outcomes. Both precisions stop constant output at 60/240; six broad-normal
  runs reach 240. Actual distribution widths .06045–.08442 exceed target .01,
  while the mean-SE proxy .00239–.00545 would incorrectly satisfy it. Every
  515/508 failed draw identity, input digest and typed outcome reconciles.
  Complete coverage has 50/80/90 hits out of 100, ECE=0; incomplete comparison
  stays unverified with ECE=0. Mean bootstrap is 25 with CI [17,32]; median is
  0 with CI [0,0]. A maximum callable declared as median remains only
  consumer_asserted.
- Independent composition review: **15 native PASS + 12 controls PASS**,
  including genuine producer, all six typed readers and CAS reopen. Shared
  Scientist intake still drops valid core refs; its falsifier and owner recipe
  are preserved for G.

| Slice                                    | Draft PR                                               | Implementation checkpoint                  |
| ---------------------------------------- | ------------------------------------------------------ | ------------------------------------------ |
| DDM facade verification                  | [11](https://github.com/DenisKopylov/polisyos/pull/11) | `c13b7be010825b46e6282b8035e9ca8ef6c8735f` |
| Bootstrap statistic identity             | [12](https://github.com/DenisKopylov/polisyos/pull/12) | `dafe95e15cff5992b5b9133a35e1e1297de03e87` |
| Forecast producer binding                | [13](https://github.com/DenisKopylov/polisyos/pull/13) | `45a7b1be8951cad62e45b4c560bad88a1a8c0c53` |
| Morris geometry and trajectory bootstrap | [17](https://github.com/DenisKopylov/polisyos/pull/17) | `e468822ef5eb0096f3a1692da1fdd85843581203` |
| Gaussian covariance and failed support   | [22](https://github.com/DenisKopylov/polisyos/pull/22) | `f07058a3eb782463eedce65a6d0d54c332a46efe` |
| Mapped schedule refusal                  | [24](https://github.com/DenisKopylov/polisyos/pull/24) | `bbc40582786b2e9c898aa7dd23b89dbac3062059` |
| Complete finite predictive calibration   | [25](https://github.com/DenisKopylov/polisyos/pull/25) | `1b2aa525bdb74b90ca444eb411bf230c13a9b50a` |
| Unavailable bias test trust refusal      | [28](https://github.com/DenisKopylov/polisyos/pull/28) | `a4781aef87e9b3c8c44eedb51fc88119567afc59` |
| Composition ref readback                 | [32](https://github.com/DenisKopylov/polisyos/pull/32) | `6a7c96535fea02b3108728cf5e27d1955f65f6ea` |

All nine PRs are draft and target `codex/e02-integration`. Exact remote heads,
complete implementation chains and per-slice tree identities are in
[aggregate-verification.json](aggregate-verification.json). G should apply
original topics or the aggregate once, without duplicate cherry-picks. Fetch
these branch refs explicitly: the cloud clone's configured refspec only fetches
main. Full deciding stdout and portable witness inputs are committed under
`root-checks/`; their SHA256 values are bound in the aggregate receipt.
