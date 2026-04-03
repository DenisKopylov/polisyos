# Calibration (`polisyos.foundry.calibration`)

`calibration` - subsystem for fitting Foundry model parameters to empirical targets,
with optional measurement-aware weighting and uncertainty support.

## Role in System

- **Depends on:** `polisyos.foundry.contracts`, `polisyos.foundry.data_plane`, `polisyos.ir.observation`
- **Used by:** calibration workflows, scientist-driven policy tuning, post-fit uncertainty analysis
- Runs on top of compiled `ProgramGraph` / `ExecPlan` and produces calibrated parameter bundles and reports.

## Key Concepts

- **Pure execution loop** - `pure_executor.py` runs calibration without CAS IO in the inner loop.
- **Target alignment** - `preflight.py` prepares, fetches and aligns target series.
- **Loss shaping** - `loss.py` handles weighted target losses and reductions.
- **Measurement-aware extension** - `measurement.py` adds observation bundles and trust/coverage/censoring weights.
- **Auxiliary penalties** - `auxiliary.py` adds interference-aware loss components.
- **Uncertainty outputs** - Hessian/Laplace and envelope conversion remain part of the fit surface.

## Public API

| Type/Function | Description |
|---|---|
| `Calibrator` | Runs the optimization loop and collects diagnostics. |
| `CalibratorInputs` | Bundles graph, registries, targets and optional measurement bundle inputs. |
| `CalibrationReport` | Persisted calibration result with metrics, history and fit quality. |
| `CalibrationTargetBundle` | Runtime-aligned bundle of observation-plane targets. |
| `MeasurementAwareTarget` | Describes a single measurement-aware calibration target. |
| `MeasurementAwareLossConfig` | Controls censoring, lag and regime discounts. |
| `compute_effective_weight()` | Computes trust/coverage/censoring-aware target weights. |
| `DefaultMeasurementAwareLossAdapter` | Default adapter over the measurement-aware loss surface. |
| `AuxLossComponent` | Protocol for auxiliary loss components. |
| `InterferenceLossComponent` | Interference-aware penalty component. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 13 Python files
- Exports: 37
