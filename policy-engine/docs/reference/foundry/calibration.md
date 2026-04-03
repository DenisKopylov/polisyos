# Foundry Calibration
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

Calibration in Foundry now supports measurement-aware weighting: trust,
coverage, lag, censoring, regime boundaries, and shock periods can all reduce
the effective weight of an observed target.

## Boundary Model

Calibration compares two layers that must stay conceptually separate:

- Synthetic dynamics come from `calibration.pure_executor`: a compiled
  `StaticBundle` replays mechanisms over `GlobalState` and returns trace
  tensors.
- Observation semantics come from `MeasurementAwareTarget` and
  `CalibrationTargetBundle`: observed values plus trust/coverage/lag/censoring
  metadata.
- Measurement loss adapts target weights only; it does not mutate simulation
  dynamics. Auxiliary penalties such as `InterferenceLossComponent` consume
  synthetic traces and their own observed spillover metadata.

## Failure Expectations

- `Calibrator.run()` raises `ValueError` for missing targets, inconsistent
  time alignment, unknown constraint paths, or empty trainable-parameter sets.
- `compute_effective_weight()` raises `ValueError` when trust/coverage vectors
  cannot be broadcast to a shared target length.

## Key Concepts

| API | Role |
|-----|------|
| `CalibratorInputs` | Full dependency bundle for optimization |
| `MeasurementAwareTarget` | Observation-aware target contract |
| `MeasurementAwareLossConfig` | Discounting configuration for weak or noisy anchors |
| `compute_effective_weight()` | Combines trust, coverage, lag, censoring, and shock discounts |
| `AuxLossComponent` | Protocol for auxiliary loss terms |
| `InterferenceLossComponent` | Spillover-aware auxiliary penalty |

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

## Reference

::: polisyos.foundry.calibration

::: polisyos.foundry.calibration.measurement

::: polisyos.foundry.calibration.auxiliary

::: polisyos.foundry.calibration.calibrator
