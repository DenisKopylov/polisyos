# polisyos.ddm_15_7

- Last updated: 2026-05-05

Compatibility facade for `polisyos.ddm`.

Repository Structure Remediation Phase 4A moved the implementation to the
unversioned `polisyos.ddm` package. This directory intentionally contains only
the root wrapper and this README until the 2026-10-01 shim sunset.

Use `polisyos.ddm` for new imports. Deep `polisyos.ddm_15_7.*` imports are
not supported as public compatibility surface.

## Compatibility Contract

- Owner: `team-architecture`
- Target: `polisyos.ddm` (`src/polisyos/ddm`)
- Sunset: 2026-10-01
- Shim: `ddm-15-7-rename`
- Issue: `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#ddm_15_7-to-ddm`
- ADR: `docs/adr/repository-structure-0135-versioning-out-of-package-names.md`
- Coverage: root facade smoke test only under `tests/unit/ddm_15_7/`

## Entry Points

- `DriftAndDegradationMonitor`
- `DDMWindowResult`
- `PerformanceDegradationEvent`
- `ShiftDetectedEvent`
- `ShiftRiskEvent`
- `IncidentPayload`
- `ModelRegistryReadinessRecord`
- `RegistryGateDecision`
