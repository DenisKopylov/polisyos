# Foundry Calibration

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

Foundry calibration fits model parameters against empirical targets while
preserving a strict boundary between synthetic runtime dynamics and observation
semantics. It covers Phase 3 numeric guardrails and Phase 5 calibration/UQ
frontier work from the Foundry remediation plan.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/calibration/**`, `src/polisyos/foundry/uncertainty/**`, linked ADRs, and the referenced calibration tests

The package facade is intentionally split: measurement/reporting contracts
always import, while the JAX-backed `Calibrator`, bijectors, Hessian helpers,
and pure-executor helpers are exposed only when the optional calibration
imports succeed.

## Phase Coverage

| Source phase | Calibration meaning |
|---|---|
| Phase 1 | Missing targets, inconsistent alignment, and invalid constraints fail explicitly instead of silently producing a fit. |
| Phase 3 | Measurement-aware loss and bijectors are checked for finite gradients, stable transforms, and NaN/Inf fail-closed behavior. |
| Phase 5 | Hessian/Laplace and uncertainty-envelope adapters are the current UQ bridge; Bayesian calibration remains research-gated until a production posterior sampler is available. |

## Boundary Model

- Synthetic dynamics come from `calibration.pure_executor`: a compiled
  `ProgramGraph` and `ExecPlan` replay mechanisms over `GlobalState` and return
  trace tensors.
- Observation semantics come from `MeasurementAwareTarget` and
  `CalibrationTargetBundle`: observed values plus trust, coverage, lag,
  censoring, regime, shock, and identification metadata.
- Measurement loss adapts target weights only. It does not mutate simulation
  dynamics.
- Auxiliary penalties such as `InterferenceLossComponent` consume synthetic
  traces and their own observed spillover metadata.

## Key APIs

| API | Role |
|---|---|
| `Calibrator` | JAX-backed optimization loop when calibration extras import successfully. |
| `CalibratorInputs` | Bundles graph, exec plan, registries, targets, and optional measurement bundle inputs. |
| `CalibrationReport` | Persisted fit result with metrics, history, and fit quality. |
| `MeasurementAwareTarget` | Observation-aware target contract. |
| `MeasurementAwareLossConfig` | Discounting configuration for weak or noisy anchors. |
| `compute_effective_weight()` | Combines trust, coverage, lag, censoring, and shock discounts. |
| `AuxLossComponent` | Protocol for auxiliary loss terms. |
| `InterferenceLossComponent` | Spillover-aware auxiliary penalty. |
| `calibration.uncertainty_adapter` | Converts fit diagnostics into governance-ready uncertainty envelopes. |

## Failure Expectations

- `Calibrator.run()` raises `ValueError` for missing targets, inconsistent time
  alignment, unknown constraint paths, or empty trainable-parameter sets.
- `compute_effective_weight()` raises `ValueError` when trust/coverage vectors
  cannot broadcast to a shared target length.
- Non-finite calibration losses reduce to `+inf` rather than being reported as
  a valid numeric fit. This is tested in
  `tests/foundry/calibration/test_measurement.py`.
- Hessian-derived Gaussian envelopes are documented as heuristic uncertainty
  unless gate eligibility is explicitly justified. See
  `docs/FOUNDRY_NUMERIC_GUARDRAILS.md`
  and [`docs/adr/0012-uncertainty-envelope-ir-contract.md`](../../adr/0012-uncertainty-envelope-ir-contract.md).

## Minimal Fit Loop

```python
report = Calibrator(
    CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=state_snapshot,
        mechanism_registry=mechanism_registry,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        selector_field_registry=selector_field_registry,
        parameter_loader=load_params,
        measurement_bundle=measurement_bundle,
    )
).run()
```

## Evidence Links

- Measurement-aware weighting and finite gradient:
  `tests/foundry/calibration/test_measurement.py`
- Stable bounded transforms:
  `tests/foundry/calibration/test_bijectors.py`
- Hessian repair and condition-number semantics:
  `tests/foundry/calibration/test_hessian.py`
- Pure executor semantics:
  `tests/foundry/calibration/test_pure_executor.py`
- Uncertainty propagation ADR:
  [`docs/adr/0013-uncertainty-propagation-pipeline.md`](../../adr/0013-uncertainty-propagation-pipeline.md)
- NumPyro Bayesian SCM ADR:
  [`docs/adr/0074-numpyro-bayesian-scm.md`](../../adr/0074-numpyro-bayesian-scm.md)

## Reference

::: polisyos.foundry.calibration

::: polisyos.foundry.calibration.measurement

::: polisyos.foundry.calibration.auxiliary

::: polisyos.foundry.calibration.calibrator

::: polisyos.foundry.calibration.hessian

::: polisyos.foundry.calibration.uncertainty_adapter
