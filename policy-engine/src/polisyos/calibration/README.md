# polisyos.calibration

- Last updated: 2026-10-06

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
- `persist_continuous_evaluation` / `load_continuous_evaluation`

## Predictive evidence entrypoints

Scientist imports the typed profile, context, candidate references and
producer/readback functions from `polisyos.calibration`. These lazy exports
resolve to the canonical `forecast_bridge` objects; they introduce no second
implementation or authority. Generic diagnostics retain their existing API.

`forecast_bridge` persists and reloads empirical evidence independently of the
ETS owner result. A configured `ForecastCalibrationProfile` content-binds an
exact persisted forecast request and an explicit coverage threshold. The
profile is supplied by runtime composition; its presence establishes no
admission or institutional issuer identity.

The separate `ForecastCandidateReceipt` links that profile, request, and
empirical evidence in the same CAS. Its loader replays source positions,
ordered forecast/outcome pairs, split, horizon, method/rule, times, seed and
counts. It always retains `verifier_provenance="not_established"` and predictive
purpose denials. A owns trusted profile admission, independent verification,
default orchestration, and fresh served readback. The internal receipt is not
an S10 verification result.

## Internal continuous-pair persistence

`continuous.persist_continuous_evaluation` stores the ordered outcome/interval
pairs and their diagnostic report through the configured artifact store.
`continuous.load_continuous_evaluation` resolves both artifacts, checks their
kind and schema, and recomputes the report and receipt from those pairs. A bare
report JSON cannot establish that pair-aware readback. Requested, eligible and
observed counts retain their respective denominators when a level is missing.

The econometrics summary helper uses this route when given an artifact store.
The current method-runner path does not supply that store, so persisted
diagnostics are implemented but not orchestrated there. Ordered positions and
caller-declared source, split, horizon and time metadata do not establish
production source authority or a gating verdict.
