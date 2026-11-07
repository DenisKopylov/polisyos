# polisyos.calibration

- Last updated: 2026-10-31

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
- `persist_continuous_evaluation` / `load_continuous_evaluation`
- `evaluate_multiclass`
- `fit_calibrator`
- `apply_calibrator`
- `compare_calibrators`
- `to_validation_report`

## Continuous interval/outcome replay

`persist_continuous_evaluation` invokes the existing continuous evaluator on an
immutable snapshot of the effective ordered outcomes, interval sets, levels,
predictive samples and replay options. It stores that snapshot as
`calibration.continuous_inputs` and the resulting report as
`calibration.continuous_evaluation`, both schema `1.0`. The latter carries one
exact selected-profile manifest edge to its inputs. Seeded bootstrap replay
requires an explicit nonnegative integer seed. Both writes and fresh reads
admit at most 1,000,000 expanded bootstrap pair evaluations (repetitions ×
outcomes × interval levels), separately from the bounded payload reads.

`load_continuous_evaluation` uses bounded Core reads, reopens that exact input
profile, reruns the evaluator and compares the complete report. A fresh reader
refuses valid-hash reports with altered coverage, counts, metrics or receipts,
and rejects changed input profiles when an independently expected reference is
supplied. This proves numerical reproduction of the retained effective inputs;
it does not establish their measurement source, issuer, currentness, population
law or causal adequacy. The continuous report's truthfulness remains
`unverified`, `measurement_source_assurance` remains `not_established`, and the
validation adapter remains blocked/fail. Foundry's interval summary accepts an
explicit calibration store for this persisted path; callers without a store
retain the existing candidate-only behavior.

## Selected report and context profiles

The ForecastOwner path retains the exact `BacktestReportRef` returned by the CAS
write and carries each input's `manifest_profile_sha256` into the persisted report
manifest. The empirical-calibration bridge compares context edges by artifact ID,
role, and selected manifest profile. Same report bytes under a sibling manifest
profile therefore do not satisfy the original producer's report-basis edge.

New empirical-calibration evidence uses schema `1.2` to persist these selected
context profiles and its own full input-edge bindings. Schemas `1.0` and `1.1`
remain readable with their historical ID/role edge semantics when their evidence
is reproducible; they are not upgraded or relabeled as producer-selected profile
lineage. A profile digest identifies a
CAS manifest view; it does not establish completeness, semantic adequacy, producer
authority, currentness, issuer, or causal/S10 authority.

## Predictive Evidence Bridge

The root facade lazily exposes the neutral empirical evidence contract:
`EmpiricalCalibrationContext`, `EmpiricalCalibrationEvidenceRef`,
`EvidenceArtifactRef`, `REFERENCE_PROFILES`, and the load/persist/produce helpers.
This bridge imports IR only when selected. Its evidence remains predictive-only:
content binding and profile verification establish the selected view, not
completeness, issuer authority, currentness, causal effects, or S10.

The current reader recomputes report arithmetic and, for the selected
ForecastOwner route, reopens the observed series, training split and forecast
bundle to reconcile every ordered row's target, outcome, prediction and bounds.
Optional member/profile refs add their existing candidate series join. A
same-count row permutation produces `backtest_row_source_mismatch`; missing or
corrupt selected owner inputs produce `backtest_row_source_not_established`.
This stored numerical row relation does not establish source time/currentness,
issuer, population completeness or causal authority. The bridge therefore
retains `backtest_source_not_established`, no empirical availability and no
calibration pass. Counts and rates remain descriptive predictive diagnostics.

Older affirmative evidence that cannot be reproduced under these checks is
refused on fresh read; its CAS bytes remain available for technical inspection.
The Runtime association schema v5 preserves the candidate attachment with null
observed counts/rates, limited owner suitability, and blocked S10 support without
a calibration record. It carries the exact source limitation through publication
and fresh readback; row arithmetic cannot supply public observed-measurement
labels.

## Internal implementation groups

The shared implementation is organized by the existing capability contracts:

- `diagnostics/` owns binary, continuous, and multiclass evaluators plus the
  validation-report adapter. The public package root exports their supported
  operations; direct sibling-module paths are internal.
- `curve/` owns interval-coverage models and calculation. `CalibrationPoint`,
  `CalibrationResult`, and `compute_calibration_curve` retain the historical
  `polisyos.calibration.curve` defining/import identity for callers and serialized
  references.
- `recalibration/` owns fitted calibrator models and fit/apply/compare behavior,
  with its private sklearn compatibility implementation beside that owner.

Foundry callers use the Calibration root facade. This layout preserves the
existing root API and empirical-evidence lazy bridge; it does not claim
that unrelated unclassified package-root files or the full repository gate are
closed.

## Forecast profile member boundary

The shared calibration package remains source-neutral. Runtime quality resolves
the exact EMP-01 `ValueDataProfile` and reopens its activated projection through
the canonical Data Forge source, active overlay, receipt, and passport owner. It
compares the full owner-issued projection, recomputes profile rows, and applies
the current producer's single source-row-per-unit-period and single-dataset
rules before emitting the typed Core `ForecastProfileMemberV1` candidate
receipt for the selected forecast unit and observed series. This candidate join
does not establish source currentness, population completeness, treatment
assignment, a source relation, causal calibration, or authority. The generic
row primitive may represent aggregates, but Runtime intake refuses aggregates
the current owner profile producer would not emit. The legacy profileless route
stays profileless on fresh reads; it is not upgraded from adjacent bytes.
