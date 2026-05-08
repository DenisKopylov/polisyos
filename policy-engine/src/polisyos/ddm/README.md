# polisyos.ddm

- Last updated: 2026-05-05

Canonical Drift-and-Degradation Monitor package for readiness, incident, shift,
calibration, and root-cause evidence contracts.

The old `polisyos.ddm_15_7` package is a wrapper-only compatibility facade
until 2026-07-31. Schema IDs, YAML contract IDs, and policy IDs that still
contain `ddm_15_7` are compatibility identifiers, not Python package names.
DDM behavior tests and the root facade smoke test live under `tests/unit/ddm`.

## Example

```python
from polisyos.ddm import DriftAndDegradationMonitor

monitor = DriftAndDegradationMonitor()
```

## Entry Points

- `DriftAndDegradationMonitor`
- `DDMWindowResult`
- `PerformanceDegradationEvent`
- `ShiftDetectedEvent`
- `ShiftRiskEvent`
- `IncidentPayload`
- `ModelRegistryReadinessRecord`
- `RegistryGateDecision`
