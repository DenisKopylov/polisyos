# polisyos.calibration

- Last updated: 2026-10-14

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

The current reader recomputes arithmetic from report rows and checks the selected
source edges, but does not reconcile each row with its selected forecast and
holdout. It therefore persists a limited result with
`backtest_source_not_established`, no empirical availability or calibration pass.
Its counts and rate are row-only diagnostics. Older affirmative evidence that
cannot be reproduced under this limitation is refused on fresh read; its CAS
bytes remain available for technical inspection. Establishing the row-to-source
relation remains a separate verification capability. The Runtime association
schema v5 preserves the candidate attachment with null observed counts/rates,
limited owner suitability, and blocked S10 support without a calibration record.
It carries the exact source limitation through publication and fresh readback;
row arithmetic cannot supply public observed-measurement labels.

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

Foundry callers use the Calibration root facade. This layout change leaves the
17-name root API and empirical-evidence lazy bridge unchanged; it does not claim
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
