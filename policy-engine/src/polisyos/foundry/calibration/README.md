# Calibration (`polisyos.foundry.calibration`)

`polisyos.foundry.calibration` fits Foundry model parameters to observed
targets while keeping a strict boundary between synthetic runtime dynamics and
measurement-aware loss adaptation.

- Last updated: 2026-10-20

Generic calibration diagnostics, recalibration helpers, and validation-report
adapters live in the shared `polisyos.calibration` package. This package owns
Foundry-specific parameter calibration, measurement-aware losses,
identifiability diagnostics, Hessian/UQ helpers, robust-set selection, and
Foundry calibration artifacts.

## Purpose

Use this package when a Foundry workflow needs to compare simulated traces
against empirical anchors, diagnose fit quality, and convert calibration
diagnostics into uncertainty envelopes or post-fit evidence.

## Where to Start

- [measurement.py](measurement.py) for observation-panel compilation, placebo
  materialization, observation-quality metadata, and weight adaptation.

- [pure_executor.py](pure_executor.py) for the no-CAS inner-loop execution path
  used by calibration.

`apply_nodes_batch(states, row_times, row_keys, *, bundle)` is the supported
one-step row-batch bridge. It retains row order and maps each aligned state,
scalar schedule step, and complete PRNG key through scalar `apply_nodes` with
`jax.lax.map`; empty rows, inconsistent state leading dimensions, and keys not
shaped `(rows, 2)` are refused rather than broadcast. Callers own key derivation
(for independent replayable streams, pass `jax.random.split(seed, rows)`). A
time value is one row's current step, not a scan start; repeated steps require
explicit repeated calls. Static selector structure is admitted during
`compile_program`, while inactive rows do not numerically read selector fields.

This executor API does **not** yet select a Calibrator batch objective profile.
`CalibratorInputs` and execution-basis schema 1.1 cannot bind row states, times,
keys, order, and reduction semantics, so scalar calibration remains unchanged.
Persisting a batch fit requires a reader-first versioned basis extension and a
real welfare-consumer reconciliation; a digest or reuse of `controls_seq` is
not a substitute.

- [calibrator.py](calibrator.py) for the optional JAX-backed fit loop.
- [report.py](report.py) for persisted reports and fit diagnostics.
- [identifiability.py](identifiability.py) and [hessian.py](hessian.py) for
  identifiability and second-order diagnostics.

- [../uncertainty/README.md](../uncertainty/README.md) for downstream
  uncertainty propagation.

## Public Entrypoints

| Entrypoint                     | Description                                                                               |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| `Calibrator`                   | JAX-backed optimization loop when calibration extras are importable.                      |
| `Calibrator.run_and_persist(store)` | Runs a config snapshot once and persists its typed report with that exact config edge. |
| `CalibratorInputs`             | Bundles graph, exec plan, targets, registries, and optional measurement bundle inputs.    |
| `CalibrationReport`            | Persisted fit result with metrics, history, and fit quality.                              |
| `CalibrationCoordinateProjection` | Typed calibration coordinate projection from the report owner.                         |
| `persist_posterior_summary_from_method_evidence()` | Persists the existing candidate-only summary from source-bound method evidence. |
| `propagate_selected_posterior_summary()` | Reopens an exact selected summary and separately held method-evidence view before candidate Monte Carlo. |
| `MeasurementAwareTarget`       | Observation-aware target contract.                                                        |
| `MeasurementAwareLossConfig`   | Controls lag, censoring, regime, and shock discounts.                                     |
| `compute_effective_weight()`   | Combines trust, coverage, lag, censoring, and shock metadata into effective loss weights. |
| `diagnose_identifiability()`   | Produces parameter-level identifiability diagnostics.                                     |
| `envelopes_from_calibration()` | Converts calibration outputs into uncertainty-envelope artifacts.                         |

## Persisting a calibration run for a fresh consumer

`Calibrator.run_and_persist(store)` snapshots the exact `CalibrationConfig`, runs that
snapshot once, writes the config artifact, then writes the typed v2 `CalibrationReport`
with an edge built from the complete selected config ref, including a non-default
manifest profile. It returns `(report, report_ref)`; a caller can
place that exact ref under `ExperimentState.inputs["calibration_report_ref"]` for the
registered `PropagateWelfareNode` to reload from CAS. The existing node records the
report ref in its fresh welfare output lineage.

This is an internal configuration-to-report binding. It does not bind external
observation authenticity or establish a conditional/noise law, and Hessian-derived
envelopes remain heuristic and gate-ineligible. Calibration execution is still an
explicit library call; the default workflow does not schedule a calibration run.

## Source-bound posterior candidate

`uncertainty_adapter.persist_posterior_summary_from_method_evidence()` accepts Bayesian MCMC
method-evidence only after resolving the producer-issued `method_result_ref` and matching its
exact manifest edge and persisted draw payload reference/hash. It persists the v1.1 summary with
the selected method-evidence manifest profile as lineage. `load_persisted_posterior_summary()`
reopens the CAS artifact and recomputes the named point functional and equal-tail interval from the
retained draws. The summary is candidate-only (`gate_eligible=False`), has no established unit
binding, and is not a calibration report or a causal-effect input. Its actual source → CAS → fresh
reader → Monte Carlo consumer path is covered by
[`tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py`](../../../../tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py).

`MethodBackend.run()` invokes this creator after writing method result and evidence when native
draw evidence is present and matches the persisted result. `JobResult.posterior_summary_refs`
exposes both existing point roles (`posterior_mean`, `posterior_median`) as typed candidate refs;
the consumer still selects the ref and matching role explicitly and supplies its evaluator. No
workflow default, unit binding, calibration authority, or causal-effect authority is implied.

`propagate_selected_posterior_summary()` is available from this package facade. It accepts an exact
profile-bearing summary reference and a separately held exact method-evidence reference, reopens the
selected artifacts through the existing fresh Core reader, checks their full relationship and the
requested point role, then delegates to the existing Monte Carlo consumer. The caller's intended-job
selection remains `consumer_asserted`; the result stays `gate_eligible=False` with unit binding
`not_established`. This library function does not add a workflow default or claim source currentness.
See the [selected-posterior consumption guide](../../../../docs/how-to/selected-posterior-consumption.md)
for its inputs, failure behavior, and usage boundary.

The existing `summarize_bayesian_calibration_posterior()` route now attaches the existing
`PosteriorSamplesCarrier` to each envelope whose mean remains representable inside the credible
interval. It uses exact numeric canonicalization and marks these caller-input-only envelopes
gate-ineligible. A fresh CAS reader and the legacy Monte Carlo consumer are exercised for a
representable single-parameter case. When the posterior mean falls outside its equal-tail interval
(for example, 99 zeros and 100), the helper preserves the mean and interval, retains the samples in
a typed candidate context, omits the incompatible envelope, and reports
`point_outside_credible_interval`; it does not clamp the interval or substitute the median.

Pass `candidate_store` to `summarize_bayesian_calibration_posterior()` to persist the full caller
summary through its existing producer path; the returned summary carries `persisted_candidate_ref`.
The artifact keeps the mean, linear interval, representable envelopes, exact draw carriers, original
input shapes, positional row matrix, and any typed envelope limitations under a caller-input-only
status. The fresh reader recomputes the legacy summary before returning the typed candidate; a stale
point or interval is refused. `consume_persisted_bayesian_calibration_candidate()` sends
representable envelopes through the existing Monte Carlo consumer. An off-interval parameter
returns a typed limitation without evaluation, while multi-parameter caller rows reach the ordinary
consumer and are refused when no source-bound joint law exists. These paths are candidate-only and
do not create method-evidence binding or calibration/causal admission.

The context also preserves the original input shapes and positional row matrix when column lengths
match. `row_relation_status` remains `not_established`: equal length and input order do not prove a
shared joint law. The current Monte Carlo consumer therefore refuses a multi-parameter carrier
set without an existing shared sample identity. Neither this caller-mapped context nor the typed
carrier creates source authority or multi-parameter law admission. The candidate artifact is a
caller-input record; the separate v1.1 HMC path remains source-method-evidence-bound but explicitly
candidate-only and is not default-dispatched.

## Depends On / Depended On By

- Depends on: `polisyos.foundry.contracts`, compile/execute runtime state,
  `polisyos.ir.observation` contracts and bundles, uncertainty adapters, and
  optional JAX/optimization extras.

- Depended on by: Scientist autotune and feedback flows, uncertainty
  propagation nodes, and runtime helpers that reuse the pure-executor path.

## Common Commands

Smoke-tested on 2026-04-17:

```bash
uv run python - <<'PY'
import jax.numpy as jnp

from polisyos.foundry.calibration import (
    MeasurementAwareLossConfig,
    compute_effective_weight,
)

weights = compute_effective_weight(
    base_weights=jnp.array([1.0, 1.0], dtype=jnp.float32),
    trust_weight=jnp.array([0.8, 0.6], dtype=jnp.float32),
    coverage_estimate=jnp.array([1.0, 0.0], dtype=jnp.float32),
    censoring_mask=jnp.array([False, True]),
    lag_days_estimate=jnp.array([0.0, 14.0], dtype=jnp.float32),
    schema_regime_id=("regime_a", "regime_b"),
    shock_mask=jnp.array([False, True]),
    config=MeasurementAwareLossConfig(),
)
print(weights["effective_weight"])
PY

uv run python - <<'PY'
from polisyos.foundry.calibration import Calibrator
print(Calibrator is not None)
PY
```

## Test / Verification Commands

```bash
uv run pytest tests/unit/foundry/calibration/test_measurement.py \
  tests/unit/foundry/calibration/test_bijectors.py \
  tests/unit/foundry/calibration/test_hessian.py \
  tests/unit/foundry/calibration/test_pure_executor.py -q

uv run pytest tests/unit/foundry/calibration/test_identifiability.py \
  tests/unit/foundry/calibration/test_multi_start.py \
  tests/unit/foundry/calibration/test_calibrator.py -q
```

## Reference Docs

- [docs/reference/foundry/calibration.md](../../../../docs/reference/foundry/calibration.md)
- [../uncertainty/README.md](../uncertainty/README.md)
- [docs/reference/foundry/numeric-guardrails.md](../../../../docs/reference/foundry/numeric-guardrails.md)
- [docs/adr/0012-uncertainty-envelope-ir-contract.md](../../../../docs/adr/0012-uncertainty-envelope-ir-contract.md)
- [docs/adr/0013-uncertainty-propagation-pipeline.md](../../../../docs/adr/0013-uncertainty-propagation-pipeline.md)
- [docs/adr/0074-numpyro-bayesian-scm.md](../../../../docs/adr/0074-numpyro-bayesian-scm.md)

## Execute-backed local response basis

`identifiability_diagnostic(..., response_slots={"balance": "government.balance"})`
can measure a local Jacobian from actual Foundry replays and persisted scalar
state. Parameter keys are registered `node_id.parameter` entries. Moment and
parameter units come from the exact bound registry; moment/parameter axis order,
source/model/input references, initial and replay StateSnapshot 2.2 nested NPZ/schema
bytes and selected manifests, finite-difference
points, requested execution config, seeds, and actual replay artifacts remain in
the matrix's `response_basis` and manifest lineage.

Each replay overlays only the differentiated node/parameter values on the full
exact source override bundle; the derived bundle retains that selected source ref
as `input.original_parameter_override_bundle_ref`. The fresh reader reconstructs
the merged map and compares the complete replay request with the admitted source
request. A profileless source result remains legacy-limited, and a present source
override without an exact selected manifest profile is refused.


`load_execute_response_basis_candidate()` is the public fresh reader for the
selected response diagnostic. It reopens and recomputes the execute basis and
Jacobian from fresh CAS states before returning `ExecuteResponseBasisCandidate`
with exact selected source identities. The Scientist node carries that complete source map into its propagation report
and output-envelope lineage. The fresh IR reader reconciles every
`response_context.*` manifest edge in both artifacts against the complete source
map. Each edge must preserve its exact selected artifact and profile; the reader
resolves that CAS view and verifies both content bytes and selected-manifest bytes
before returning the candidate projection.

This profile requires explicit inline observed moments and parameter center,
registered global scalar response slots, an explicit current StateSnapshot 2.2
initial state, a persisted sensitivity matrix, and
zero bootstrap/profile repetitions. A callback, an unknown or vector response,
an unbound unit, changed source/config/axis, or incomplete lineage cannot be
substituted for this profile. The existing callback and operational-metrics
paths retain their behavior and produce no execute-state basis.

The basis describes a local numerical response and always has
`gate_eligible=False`. It provides neither a measurement law nor causal,
scientific, or Runtime admission. The IR roster check verifies persisted
identity consistency only; the Scientist adapter does not claim external
source/law/target authority. Registered
deterministic income tax is an available synthetic witness, not a calibrated
fiscal model.


## Execution-input identity for fresh consumers

A persisted Foundry calibration run now writes a typed
`CalibrationExecutionInputBasis` alongside the v2 report. Its manifest edge binds
the report to the selected calibration config profile and captures the exact
selected ProgramGraph, ExecPlan, base StateSnapshot, the frozen 25-field scalar
v1.1 input roster, six selected runtime-registry members, ordered target
series/time-axis bytes, resolved parameter payload bytes, declared parameter
spec/unit identities, and report-envelope bytes. The fit and persisted identity
use separate pre-fit copies, so caller mutation after execution cannot change the
recorded input basis. The fresh welfare consumer resolves those selected CAS views,
recomputes the selected registry member content and resolved output identities,
and records a source status in its result. In-memory values and opaque callback
behavior remain typed limitations unless separately resolved through selected
artifacts. A real compile → execute → calibrate → CAS → fresh-consumer fixture
exercises this path, selected parameter/member mutations, and a present-but-falsely
matched runtime member.

This identity is limited to local content and object consistency. For genuine scalar reports, a missing or
legacy basis produces the visible `source_execution_not_established` candidate
limitation; it does not suppress candidate covariance display or make it
gate-eligible. A present malformed, foreign, or mismatching basis refuses the
source-qualified covariance projection rather than falling back to legacy
absence. A matched basis still does not establish external source authenticity,
unit-definition semantics, physical time, split validity, an observation/noise
law, calibration authority, or production currentness. Historical v1 report
bytes remain readable and unchanged.

## Ordered-row Calibrator profile

`CalibratorInputs.ordered_batch_profile` selects `ordered_scalar_mse_v1`: unique
ordered row IDs, full initial states, nonnegative integer scalar schedule steps,
complete legacy uint32 keys `(rows, 2)`, and finite float32/float64 scalar targets
and weights with the exact same row count. Typed JAX/NumPy array carriers must
retain their original dtype under the active JAX precision profile; the constructor
checks that static condition before an outer JIT can erase an unavailable NumPy
dtype, and the executable entry repeats carrier/dtype checks. Abstract PyTree
reconstruction alone is never executable admission. Rows are independent one-step **program
experiments**, not a cumulative scan or a claim of independent observations. All
observations are present; a zero weight removes a row from loss/metric support
without fabricating an observation. Positive effective total support is required.

The actual optimizer, selected report and parameter-connected Hessian use one
forward through `apply_nodes_batch`/scalar `apply_nodes`. Configured absolute MSE
retains the existing pointwise epsilon; target priority multiplies the normalized
row loss outside the reduction. Row weights/support and target priority have an
explicit float32 effective representation. Original weights must also be finite
and nonnegative: a tiny original negative cannot become an admitted negative zero.
Overflow, loss of a positive weight or target priority to effective underflow,
nonpositive support, and a nonfinite candidate refuse. The reused
`pointwise_base_loss` always projects predictions and targets to float32 before
its epsilon-scaled residual calculation, including when the original selected
arrays are float64. Tiny target/prediction residuals can therefore round to zero;
the positive-underflow refusal concerns weights/priority, not a new precision law
for that existing pointwise owner. Integer weights
are unsupported in this first profile, avoiding integer accumulator wrap. Mutable
floating output slots share one float32 or float64 precision; trainables inherit
that precision. No global precision switch is changed. Fit metrics are weighted
residual MSE/MAE/R2 in original units (`n` counts positive-weight rows), distinct
from loss epsilon/priority. Both supported metric consumers use that declared scope.

All input **and returned** state leaves must be finite. In particular, optional
`QueueEventCalendarState.empty()` (+infinite future event times) and
`FeedbackState.empty()` (+/-infinite bounds) are outside this deliberately finite
first profile, even if untouched. This is an explicit profile refusal, not a claim
that those legitimate scalar state types are invalid. Dynamic invalid states,
targets, predictions, weights, support or arithmetic give `valid=False` and
`objective=inf` under eager/JIT. The real optimizer/Hessian/report forward consumes
that validity, including parameter-dependent off-target invalid outputs. Shape,
key, dtype, scalar-target and unsupported-contract errors raise visibly before fit.

Supplied complete fixed row keys are consumed unchanged. Step-derived keys,
multi-start, alternate target providers/raw-target overrides, measurement adapters,
controls, constraints, priors, auxiliary objectives, relative loss, vector or
aggregated metrics, GradNorm and nondefault alignment are explicitly unsupported
batch combinations. Configured horizon/time axis must equal the positional rows;
resampling/reordering refuses before optimization. Ordinary supported scalar
options remain. The profile/evaluation are JAX PyTrees; a stochastic scalar-row,
key/permutation oracle and analytic objective gradient/Hessian exercise the actual
parameter-connected path.

### Selected input and fresh projection

`run_and_persist` publishes `foundry.calibration_ordered_input`, schema
`polisyos.foundry.CalibrationOrderedBatchInput` **1.0**, before fitting, then
reopens and consumes exactly that selected full input. Its manifest has one
selected config and every ordered full StateSnapshot **2.2** edge. The owner checks
config payload/header version equality, complete unique edges, selected row bytes,
wrapper schedule step, row values/dtypes, keys, targets, weights and the complete
profile hash. Returned foreign writer selections refuse before the fit starts.
Locally materialized snapshots establish local bytes, not external provenance.

Execution basis **1.2** selects that input and binds its content to the 26-field
runtime roster. Scalar bases **1.0/1.1** retain their existing meaning and the
public 25-field v1.1 roster. Optional new fields are omitted from old wire bytes.
A fresh basis reader resolves the selected full input rather than trusting inline
basis weights or a self-declared digest. Required bytes are read before integrity
classification: missing/denied selected evidence is `not_established`, while present
malformed content and known contradictions are `mismatch`. Both remain unqualified. Backend identity records JAX/jaxlib,
backend name, machine architecture, x64 mode, actual default PRNG implementation
and Threefry partitionability. Legacy uint32 two-word keys require Threefry2x32;
other default implementations refuse. The producer and fresh reader use one numeric
settings owner; a changed split algorithm is profile-unavailable, not a false source
contradiction. A different/unavailable profile
returns `not_established`; it does not report a product mismatch or silently cast.
The initial implementation requires compatible numeric runtimes for a deciding
replay, not production data or a particular Mac path.

Batch report **2.1** carries typed `CalibrationOrderedBatchReport` objective/input
scope and selected input identity. Its writer requires exact config/basis edges;
`serialize_calibration_report_v1` refuses projecting a batch report as old scalar
bytes. Genuine **1.0/2.0** reports remain readable and omit the new optional field.
Unknown report versions refuse rather than reusing an earlier interpretation.
A fresh selected 2.1 view without a basis remains curvature-only. Replacing both
the basis and its hashes cannot replace the original report's selected input.
These bindings do not attest an adversarially rewritten whole history: they prove
the current selected relation and recomputed numerical projection, not an issuer's
historical invocation.

The shared `replay_ordered_batch_report_projection` owner reopens the selected
report, input, config, graph, plan, registry, base state and actual selected
parameter inputs. It performs **one final forward**, applies reported fitted
parameters and recomputes model values, configured loss/priority and fit metrics.
It does not rerun optimization or Hessian calculation or certify an optimum.
Fresh welfare uses this replay after its existing simulation/source reconciliation;
changed model/loss/metric values refuse against unchanged selected inputs.

### Consumers and statistical boundary

Fresh welfare carries the typed generic-loss scope into the actual covariance
owner even when the basis is absent or unavailable. For calibration fields it
withholds an interval with `calibration_generic_batch_inference_unavailable` while
retaining the point result. Source mismatch is separately diagnosed. An unrelated
separately supplied uncertainty component remains usable; its actual mean,
quantile and welfare-weight projection are tested independently. Raw spectrum,
rank/conditioning, repair count, compute precision and exact/fallback cause remain
visible. Finite-difference convergence is `not_established` unless demonstrated.
Generic Hessians supply curvature diagnostics; finite repaired covariance and
source matching establish no likelihood, sampling/independence law or inferential
admissibility. Existing scalar heuristic envelopes remain candidate/gate-ineligible.

The execute-state response sibling requires the selected report manifest version
to equal its supported typed payload version, reads genuine scalar bases1.0/1.1
through the versioned owner and explicitly refuses batch report2.1/basis1.2 with
`ordered_batch_response_basis_not_supported` through the real node, producing no
propagation artifact. Its single starting-state experiment cannot reinterpret rows.

`CalibrationMetaEvaluator` accepts the existing scalar report/dict runner shape and
also `(report, selected_report_ref)` from `run_and_persist`. A new batch report needs
the selected ref/store and the shared fresh replay before its fit metrics can be
scored. Missing or mismatching source withholds the split's objective and promotion,
recording `not_established`/`mismatch`, limitation codes and selected refs in existing
`BenchmarkEvaluation` notes/metadata. Successful scoring remains candidate-grade;
its condition-number score is a curvature diagnostic, not inferential calibration.
Legacy2.0 scoring behavior is unchanged. An unavailable incumbent metric is not a
measured zero.

These are additive Foundry contracts and scoped Scientist consumers; no Core/CAS,
IR DTO or HTTP/client implementation is changed. Root owns public inventory and
any generated/schema companion review. The release review flag stays false until
that work actually occurs. Source proposals, runtime verification, independent
review, and G acceptance are separate states.


### Selected source availability

`read_calibration_source()` is the shared typed intake in the existing execution-basis
owner. It uses Core's exact manifest resolver, selected-profile verification reader,
and canonical JSON read before a domain decoder. `CalibrationSourceRead` reports
only `matched`, `not_established`, or `mismatch`; it introduces no artifact/wire enum
and grants no source, issuer, statistical, currentness, or calibration authority.
Welfare, autotune and the scalar response reader use the same classification.

Absent exact selection, absent manifest profile qualifier, unavailable selected
view/blob/access/backend capability, or a candidate-only Core canonical declaration
is `not_established`. A readable default view does not fill that gap. Duplicate
role edges, conflicting complete selections, known wrong kind/schema/version,
malformed present typed payload, and content/integrity contradictions are `mismatch`.
A `FileNotFoundError` or typed denial remains unavailable even when explicitly
wrapped by an owner; arbitrary error-message text never supplies the classification.
Structural payload contradictions remain mismatches rather than being relabeled absent.

`load_calibration_execution_input_basis()` retains genuine scalar legacy direct
reading for historical display. That compatibility route does not qualify a source;
new batch bases require selected input resolution. Qualification consumers call
`read_calibration_execution_input_basis_source()` instead, so a profileless readable
basis remains a visible legacy/candidate limitation. Unknown selected report/basis
versions and manifest/payload version disagreements refuse. The report2.1 marker
still withholds generic batch inference even when a source cannot be established.


### Media and strict typed admission

Typed selected JSON uses Core's `validate_core_model_json_artifact`, including its
schema-directed JSON tuple/native adaptation and strict field types. A numeric
string is not a numeric wire value. `read_calibration_model_source(model=...)` delegates
that operation; untyped canonical maps do not acquire an invented model contract.
NPZ uses media-neutral CAS integrity and the existing snapshot decoder, with no JSON
canon requirement. `read_calibration_registry_source()` reuses Core composition,
derives consumed members from its content contract and applies their strict owners.
Welfare/response classify supplied reports at actual node intake before dependent
evaluation; ordinary absent optional welfare input stays optional. Supported scalar
basis display includes selected no-canon history without qualifying it as evidence.


### Required typed owners and raw boundaries

`read_calibration_model_source()` requires the actual Pydantic owner before any
decoder/consumer runs. Its model cannot default to `None`. `read_calibration_source()`
serves canonical raw maps, reference metadata and binary bytes; it accepts no model
argument. Its single media-independent result owner permits the unchanged raw
payload through Core's actual native-value codec, selected binary bytes, or exact
selected `ArtifactRef`/`ArtifactManifest` metadata. Direct or nested Pydantic domain
models are refused even for an NPZ source. Metadata is content-bound to the selected
view; a different reference or manifest is not an exemption. The result owner does
not invent a JSON-only scalar whitelist or require JSON canon on binary data.

`read_calibration_config_source()` lives beside `put_calibration_config` and binds
strict Core JSON adaptation to that producer's kind/schema and header/payload
version relation. Batch, scalar welfare, response and batch-report writer use this
one owner. Graph/plan/snapshot and producer captures carry their actual model owners;
response source-specs explicitly bind all six current source models. Raw mechanism
parameter maps retain their actual dynamic mechanism contract, not a fabricated DTO.
Legacy scalar basis display remains separate from qualified admission.

`CONSUMERS.md` and the complete AST matrix in the R7 handoff distinguish those
boundaries; call/keyword counts are not acceptance criteria. The scalar2.0 witness
uses actual welfare/response nodes and coherent selected lineage with only a config
numeric field changed to a string. Both outcomes precede the joint assertion; all
runtime/negative/control evidence still requires execution on composed source.

The R7 raw-boundary discriminator reuses the actual producer NPZ from the existing
fresh welfare fixture. Valid bytes, exact ref/manifest and typed JSON continue;
decoders returning a coercively constructed `CalibrationConfig`, a nested DTO or
foreign metadata are refused before a matched value is exposed. A Core-native
date/Decimal/bytes positive and changed-raw-payload negative exercise the JSON owner.
Both the positive and the property-removal red remain UNRUN until composed execution.
The contract concerns the complete current selected-source intake, not a sandbox
for arbitrary decoder code or proof about every future Python serialization type.
