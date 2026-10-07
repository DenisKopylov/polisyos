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

## Persisted registry source rebind

Current registry producers emit explicit version 2 under a distinct schema ID.
The original strict schema remains in `integration/model_registry_record.v1.schema.json`;
legacy records retain their historical read/serialization form. New records are
incompatible with the old strict reader. The directional reader matrix, explicit
prerelease-record migration and `team-scientist` rollout ownership are recorded
in [model_registry_gate.md](integration/model_registry_gate.md). Reading or
migrating bytes never restores checker authority.

The monitor reconciles every common field of a shift/calibration pair and of
a degradation/metric-policy pair. A registry projection retains the original
readiness event ID, effective time and expiry separately from calibration
expiry, plus a digest of the exact ordered source inputs. Digests and public
status fields are inspectable candidate evidence, not checker authority.
The admission also recomputes degradation `budget_used` with the existing
`metric_budget_used` owner. Inputs must be finite and the supplied quantity
must equal that canonical result; present labels cannot admit a false clean
budget. This checks the declared metric inputs, not the underlying source law.

After JSON reload, `rebind_calibration_validity` requires the exact report and
audit to refresh calibration validity. Registry eligibility additionally
requires `metric_budget`, `readiness_event`, ordered normalized `shift_events`
and `last_degradation_event`. Missing or mismatched source inputs fail closed;
legacy payloads remain readable. A fresh rebind checks the readiness expiry
at its effective time without substituting the calibration horizon or expiry.
R2 retains its explicit owner-signoff exception; this Python boolean does not
establish institutional signoff authority. Observation-feed completeness and
an external served deployment consumer remain outside this bounded chain.
