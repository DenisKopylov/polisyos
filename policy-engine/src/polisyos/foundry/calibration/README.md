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
