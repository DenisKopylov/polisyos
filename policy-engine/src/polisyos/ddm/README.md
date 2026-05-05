# polisyos.ddm

- Last updated: 2026-05-03

Canonical Drift-and-Degradation Monitor package for readiness, incident, shift,
calibration, and root-cause evidence contracts.

The old `polisyos.ddm_15_7` package is a wrapper-only compatibility facade
until 2026-10-01. Schema IDs, YAML contract IDs, and policy IDs that still
contain `ddm_15_7` are compatibility identifiers, not Python package names.

## Entry Points

- `DriftAndDegradationMonitor`
- `DDMWindowResult`
- `PerformanceDegradationEvent`
- `ShiftDetectedEvent`
- `ShiftRiskEvent`
- `IncidentPayload`
- `ModelRegistryReadinessRecord`
- `RegistryGateDecision`
