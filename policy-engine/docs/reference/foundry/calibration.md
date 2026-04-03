# Foundry Calibration
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

Calibration in Foundry now supports measurement-aware weighting: trust,
coverage, lag, censoring, regime boundaries, and shock periods can all reduce
the effective weight of an observed target.

## Key Concepts

| API | Role |
|-----|------|
| `CalibratorInputs` | Full dependency bundle for optimization |
| `MeasurementAwareTarget` | Observation-aware target contract |
| `MeasurementAwareLossConfig` | Discounting configuration for weak or noisy anchors |
| `compute_effective_weight()` | Combines trust, coverage, lag, censoring, and shock discounts |
| `AuxLossComponent` | Protocol for auxiliary loss terms |
| `InterferenceLossComponent` | Spillover-aware auxiliary penalty |

## Reference

::: polisyos.foundry.calibration

::: polisyos.foundry.calibration.measurement

::: polisyos.foundry.calibration.auxiliary

::: polisyos.foundry.calibration.calibrator
