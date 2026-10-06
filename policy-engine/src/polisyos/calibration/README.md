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

`load_foundry_calibration_report` is the canonical Foundry CAS reader exported
under an explicit name. The legacy uncertainty Node consumes this entrypoint
to verify report kind, schema, payload and configured companion refs before
dispatch. It does not load a FunnelCalibrationReport or grant source/fit authority.

Scientist imports the typed profile, context, candidate references and
producer/readback functions from `polisyos.calibration`. These typed exports
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

New internal forecast requests use schema version `2.0`, explicit `target_unit`
and `target_scale="source_native"`. The producer resolves a canonical Fabric
`DataSchema` before numerical execution and binds the target field, unit,
decimal storage scale and schema ref through prediction, training and evidence
lineage. `source_native` preserves source values without conversion; a metric
name or display label cannot supply a unit. The candidate reader repeats that
coordinate binding from fresh CAS bytes. Historical v1 request/evidence replay
is retained, while new execution refuses missing schema or unit/scale inputs.

`ForecastOwnerResult.to_s10_input_fields(store)` reopens the candidate and
adapts its empirical ref, candidate ref, rule and six temporal roles to A's
existing input fields. Its output is neutral and retains predictive denials;
A still owns trusted verification and default/HTTP composition.

## Internal continuous-pair persistence

`continuous.persist_continuous_evaluation` stores the ordered outcome/interval
pairs and their diagnostic report through the configured artifact store.
`continuous.load_continuous_evaluation` resolves both artifacts, checks their
kind and schema, and recomputes the report and receipt from those pairs. A bare
report JSON cannot establish that pair-aware readback. Requested, eligible and
observed counts retain their respective denominators when a level is missing.

The econometrics summary helper uses this route when given an artifact store.
The configured NumPy/econometrics method execution passes its trusted store
through the dispatcher and runner to all three interval summaries and returns
their persisted refs in derived artifacts. This boundary remains non-gating.
Ordered positions and
caller-declared source, split, horizon and time metadata do not establish
production source authority or a gating verdict.
