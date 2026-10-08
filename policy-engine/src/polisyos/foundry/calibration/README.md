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
basis. The configured Scientist bridge below adopts that finite profile. Registered
deterministic income tax is an available synthetic witness, not a calibrated
fiscal model.


### Configured Scientist local-response bridge

The existing `PropagateUncertaintyNode` accepts an opt-in
`params.propagation_response_basis` with `matrix_ref`, the ordered known
`response_slots`, expected registered `response_units`, `parameter_center`, and
`diagnostic_config`. Its expected source is the actual current
`artifacts_index.simulation_result_ref`. The internal reader resolves exact
selected manifests, verifies persisted source/replay state bytes and the
Jacobian, and returns center values recomputed from those same states.

`params.propagation_response_slots` records the full requested alias-to-slot
roster. It must include the matrix's known roster; additional unsupported targets
remain explicitly addressed UNKNOWN/missing-output envelopes. The report keeps
both rosters and refuses to claim a complete mapping when an output is unresolved.
No operational `Metrics` count or latency is used as a scientific state response.

`params.propagation_input_envelope_refs` binds parameter axes to exact persisted
IR envelopes using mandatory selected Core CAS view references. A supplied
selector-free law is refused; an absent optional law remains an addressed gap.
The historical IR persistence helper returns a selector-free three-field DTO and
does not establish this native input profile. Each supplied envelope's `metadata.param_name`, registered
`metadata.unit` and point must match the verified axis/unit/center. Missing laws
hold rows with nonzero coefficients; verified zero-Jacobian local rows retain
the actual center singleton of the local first-order map without inventing a law. A zero local Jacobian does not establish global natural-model constancy. Covariance/law inputs are
caller-declared and handled by the existing propagation dispatcher; Fisher,
weighting and ridge values never become a parameter noise scale.

The projection is the dimensioned **local** response
`y_center + J * (x - parameter_center)`. It preserves response at a zero or
nonzero baseline and does not prove a global affine law. Output intervals are
non-gating heuristic local-linearization ranges, not estimator confidence
intervals or scientific/Runtime admission. Exact source/matrix/input-law views
remain in envelope/report manifests and the updated SimulationResult. The exact propagation-config view binds every output and report. The existing strict three-field IR payload refs are preserved; a finite Node output reader requires a selected top SimulationResult and resolves its complete alias-owned envelope/config/report edges with mandatory selected profile selectors. It checks exact config and supplied-law views consistently across output/report manifests, refusing missing, duplicate, extra or contradictory owned edges before loading envelope bytes. It admits no default-latest selector substitution. Bare
legacy `propagation_sensitivity` keeps its historical relative/additive numerics
as an explicitly non-gating, consumer-asserted hypothesis; it does not establish
a registered dimensional map or a full native mapping. Unmapped legacy siblings also use the addressed UNKNOWN/missing-output profile; they are not emitted as zero-variance Normal constants.

The native synthetic income-tax witness gives balance `4 * rate - 2`, while
`global.tax_rate` remains `0.125` (Jacobian zero). Its declared synthetic input
standard deviation `0.25` gives local balance variance `1`; this fixture is not
empirical calibration, a production law, or authority. Protected production
facts and C11 assembly/admission remain separate owner inputs.

Every newly written Node output/config/report is pinned using the existing CAS manifest-profile derivation and verified against its actual published view. Stripping a selector while retaining output IDs, roles and metadata is a typed refusal; it does not select a default view.
