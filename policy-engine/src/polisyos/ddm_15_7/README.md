# polisyos.ddm_15_7

- Last updated: 2026-05-03

Compatibility facade for `polisyos.ddm`.

Repository Structure Remediation Phase 4A moved the implementation to the
unversioned `polisyos.ddm` package. This directory intentionally contains only
the root wrapper and this README until the 2026-10-01 shim sunset.

Use `polisyos.ddm` for new imports. Deep `polisyos.ddm_15_7.*` imports are
not supported as public compatibility surface.

## Entry Points

- `DriftAndDegradationMonitor`
- `DDMWindowResult`
- `PerformanceDegradationEvent`
- `ShiftDetectedEvent`
- `ShiftRiskEvent`
- `IncidentPayload`
- `ModelRegistryReadinessRecord`
- `RegistryGateDecision`
