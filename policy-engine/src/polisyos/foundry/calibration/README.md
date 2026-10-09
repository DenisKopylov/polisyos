# Calibration (`polisyos.foundry.calibration`)

`polisyos.foundry.calibration` fits Foundry model parameters to observed
targets while keeping a strict boundary between synthetic runtime dynamics and
measurement-aware loss adaptation.

- Last updated: 2026-08-28

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
| `CalibratorInputs`             | Bundles graph, exec plan, targets, registries, and optional measurement bundle inputs.    |
| `CalibrationReport`            | Persisted fit result with metrics, history, and fit quality.                              |
| `MeasurementAwareTarget`       | Observation-aware target contract.                                                        |
| `MeasurementAwareLossConfig`   | Controls lag, censoring, regime, and shock discounts.                                     |
| `compute_effective_weight()`   | Combines trust, coverage, lag, censoring, and shock metadata into effective loss weights. |
| `diagnose_identifiability()`   | Produces parameter-level identifiability diagnostics.                                     |
| `envelopes_from_calibration()` | Converts calibration outputs into uncertainty-envelope artifacts.                         |

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
the matrix's `response_basis` and manifest lineage. The internal companion reader
recomputes that basis and the Jacobian/weighting/Fisher matrices from fresh CAS
states before returning them.

This profile requires explicit inline observed moments and parameter center,
registered global scalar response slots, an explicit current StateSnapshot 2.2
initial state, a persisted sensitivity matrix, and
zero bootstrap/profile repetitions. A callback, an unknown or vector response,
an unbound unit, changed source/config/axis, or incomplete lineage cannot be
substituted for this profile. The existing callback and operational-metrics
paths retain their behavior and produce no execute-state basis.

The basis describes a local numerical response and always has
`gate_eligible=False`. It provides neither a measurement law nor causal,
scientific, or Runtime admission. An uncertainty/Scientist adapter must select
and validate its own source/law/target contract before consuming this internal
basis; this producer does not implement that cross-owner adapter. Registered
deterministic income tax is an available synthetic witness, not a calibrated
fiscal model.
