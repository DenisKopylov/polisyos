# polisyos.ddm

- Last updated: 2026-05-05

Canonical Drift-and-Degradation Monitor package for readiness, incident, shift,
calibration, and root-cause evidence contracts.

Schema IDs, YAML contract IDs, and policy IDs that still contain `ddm_15_7`
are compatibility identifiers, not Python package names. DDM behavior tests
live under `tests/unit/ddm`.

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
