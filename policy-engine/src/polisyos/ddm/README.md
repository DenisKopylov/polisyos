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

## Source-bound observation replay

`calibration/observations.py` resolves a configured finite replay source and
recomputes its whole trigger/event/budget basis independently of consumer lists.
Its strict source identity, report digest and explicit observation window remain
separate from effective checking time. `[]` alone is a consumer assertion; it
cannot establish observed emptiness. Serialized registry digests do not restore
checker authority. Rebinding resolves the configured source again, and retained
private evidence detects changed or unavailable source bytes before consumption.

Finite replay proves only a bounded software protocol. Its current candidate
validity never grants production promotion. The default monitor has no admitted
production observation source and therefore fails closed. Production integration
still needs the actual source owner, its selected stream/window, delivery and
coverage basis, and currentness evidence; this module does not invent them.
