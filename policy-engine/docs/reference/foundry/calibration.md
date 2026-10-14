# Foundry Calibration

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

Foundry calibration fits model parameters against empirical targets while
preserving a strict boundary between synthetic runtime dynamics and observation
semantics. It covers Phase 3 numeric guardrails and Phase 5 calibration/UQ
frontier work from the Foundry remediation plan.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/calibration/**`, `src/polisyos/foundry/uncertainty/**`, linked ADRs, and the referenced calibration tests

The package facade is intentionally split: measurement/reporting contracts
always import, while the JAX-backed `Calibrator`, bijectors, Hessian helpers,
and pure-executor helpers are exposed only when the optional calibration
imports succeed.

## Phase Coverage

| Source phase | Calibration meaning                                                                                                                                                                                                                                                                                                                                      |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1      | Missing targets, inconsistent alignment, and invalid constraints fail explicitly instead of silently producing a fit.                                                                                                                                                                                                                                    |
| Phase 3      | Measurement-aware loss and bijectors are checked for finite gradients, stable transforms, and NaN/Inf fail-closed behavior.                                                                                                                                                                                                                              |
| Phase 5      | Hessian/Laplace and uncertainty-envelope adapters provide calibration diagnostics. The earlier production-posterior-sampler gap is distinct from current caller-input Bayesian posterior-summary helpers, which can persist/reopen candidate-only summaries but do not provide a production sampler or establish workflow readiness or gate eligibility. |

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

| API                                 | Role                                                                                   |
| ----------------------------------- | -------------------------------------------------------------------------------------- |
| `Calibrator`                        | JAX-backed optimization loop when calibration extras import successfully.              |
| `Calibrator.run_and_persist(store)` | Persists one run with its exact config artifact edge and returns the report ref.       |
| `CalibratorInputs`                  | Bundles graph, exec plan, registries, targets, and optional measurement bundle inputs. |
| `CalibrationReport`                 | Persisted fit result with metrics, history, and fit quality.                           |
| `MeasurementAwareTarget`            | Observation-aware target contract.                                                     |
| `MeasurementAwareLossConfig`        | Discounting configuration for weak or noisy anchors.                                   |
| `compute_effective_weight()`        | Combines trust, coverage, lag, censoring, and shock discounts.                         |
| `AuxLossComponent`                  | Protocol for auxiliary loss terms.                                                     |
| `InterferenceLossComponent`         | Spillover-aware auxiliary penalty.                                                     |
| `calibration.uncertainty_adapter`   | Converts fit diagnostics into governance-ready uncertainty envelopes.                  |

`Calibrator.run_and_persist(store)` executes one copied configuration snapshot, persists
that config, and writes the v2 report with a manifest input edge preserving the exact
selected config view, including a non-default manifest profile. Pass the returned `report_ref` as `calibration_report_ref` to the existing
welfare workflow when a fresh welfare consumer should use it. This is an explicit
library-produced handoff, not an automatic calibration workflow stage. The config edge
binds internal run configuration only; it does not authenticate observed data or
establish a source/noise law. Hessian envelopes remain heuristic and gate-ineligible.

## Failure Expectations

- `Calibrator.run()` raises `ValueError` for missing targets, inconsistent time
  alignment, unknown constraint paths, or empty trainable-parameter sets.

- `compute_effective_weight()` raises `ValueError` when trust/coverage vectors
  cannot broadcast to a shared target length.

- Non-finite calibration losses reduce to `+inf` rather than being reported as
  a valid numeric fit. This is tested in
  `tests/unit/foundry/calibration/test_measurement.py`.

- Hessian-derived Gaussian envelopes are documented as heuristic uncertainty
  unless gate eligibility is explicitly justified. See
  `docs/reference/foundry/numeric-guardrails.md`
  and [`docs/adr/0012-uncertainty-envelope-ir-contract.md`](../../adr/0012-uncertainty-envelope-ir-contract.md).

## Minimal Fit Loop

```python
report, calibration_report_ref = Calibrator(
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
).run_and_persist(store)
```

## Evidence Links

- Measurement-aware weighting and finite gradient:
  `tests/unit/foundry/calibration/test_measurement.py`

- Stable bounded transforms:
  `tests/unit/foundry/calibration/test_bijectors.py`

- Hessian repair and condition-number semantics:
  `tests/unit/foundry/calibration/test_hessian.py`

- Pure executor semantics:
  `tests/unit/foundry/calibration/test_pure_executor.py`

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
