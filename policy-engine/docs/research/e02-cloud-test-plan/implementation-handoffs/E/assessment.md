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
