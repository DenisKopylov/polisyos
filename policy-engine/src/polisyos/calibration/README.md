# polisyos.calibration

- Last updated: 2026-05-03

Calibration diagnostics package for binary, multiclass, and continuous
calibration checks plus fit/apply helpers for recalibration workflows.

The package root is an experimental public facade. Treat implementation modules
as internal unless their symbols are exported from `polisyos.calibration`.

This is the canonical shared home for generic calibration diagnostics,
recalibration helpers, and validation-report adapters. Foundry-specific
parameter calibration remains in `polisyos.foundry.calibration`; DDM
drift-monitor calibration remains in `polisyos.ddm.calibration`; Scientist
orchestration modules may import this shared diagnostics API without owning a
separate `scientist/calibration` package root.

## Entry Points

- `evaluate_binary`
- `evaluate_continuous`
- `evaluate_multiclass`
- `fit_calibrator`
- `apply_calibrator`
- `compare_calibrators`
- `to_validation_report`
