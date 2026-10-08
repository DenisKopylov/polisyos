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

## Internal interval report consistency

`interval_basis.py` is an internal helper shared by backtest report consumers. It reconciles
finite ordered bounds, actual observed hits, requested/evaluated counts and retained limitations;
its numerical consistency result does not establish scientific sampling law or authority.
The forecast bridge rejects an incomplete interval basis while retaining descriptive conditional
coverage. Complete predictive evidence can still be content-consistent when a separate consumer
bridge is pending; genuine Runtime/S10 admission remains a separate contract.

Scientist governance consumers may reuse this calibration helper. It has no package-root export
and introduces no additional CAS, service or authority registry.
