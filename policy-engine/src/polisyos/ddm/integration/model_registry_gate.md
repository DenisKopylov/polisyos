# DDM-15.7 Model Registry Gate

The model registry stores DDM-15.7 readiness as a deployment gate, not as a
dashboard-only annotation.

Required registry fields:

| Field | Meaning |
| --- | --- |
| `readiness_state` | `R4`, `R3`, `R2`, `R1`, or `R0` |
| `readiness_score` | 0-100 score derived from worst active risk |
| `primary_metric_budget_used` | Current primary metric budget consumption |
| `active_calibration_id` | Calibration artifact that certified FP behavior |
| `stationarity_regime_id` | Declared regime under which FP claims are valid |
| `active_incident_id` | Linked incident or `null` |
| `promotion_allowed` | Persisted baseline permission; for R4/R3, `false` is a binding veto |
| `calibration_validity` | Optional durable projection of checker context; it is not authority by itself |
| `readiness_event_id`, `readiness_effective_at`, `readiness_expires_at` | Original readiness event and distinct readiness time roles |
| `source_binding_digest` | Digest of exact ordered source DTOs; not a self-authenticating receipt |

`calibration_validity` carries the calibration and detector identities, stationarity
regime, canonical report digest, verifier id/version, effective time, expiration,
configured and observed invalidation triggers, observation status, current status,
and checker reasons. `observation_status=unavailable` is distinct from an observed
empty trigger list. A legacy payload with no projection is
`calibration_validity_not_established`.

The projection is an inspectable persisted record, not a self-authenticating
permission. A reloaded record can become current only through
`rebind_calibration_validity` with the exact `CalibrationReport`, matching
`CalibrationAudit`, effective `now`, and observed-trigger context. The rebind
recomputes the canonical report digest and validity result, compares the
persisted report identity/digest, and emits a current projection before
attaching fresh private checker evidence. Effective time, observed triggers,
status, and reasons therefore reflect the new rebind context rather than a
stale payload. Missing context, tampered identity/digest, unavailable
observations, or a mismatch remain fail-closed; an unavailable observation
still preserves the deterministic `calibration_expired` reason when the
current time is past `valid_until`.

Promotion after reload additionally requires the original `readiness_event`,
`metric_budget`, ordered normalized `shift_events`, and enriched
`last_degradation_event`. The existing producer compares all shared calibration
and metric-policy fields, and rebind compares the full source-bound projection.
Public field mutation cannot modify the private checker projection. Legacy
records missing their source or time projection stay non-gating. Readiness
expiry is checked separately at the fresh calibration check's effective time;
an expired readiness event cannot gain a new TTL by refreshing calibration.

Promotion rules:

| State | Promotion |
| --- | --- |
| R4 | Allowed only when the persisted permission is `true` and checker evidence is valid |
| R3 | Allowed with investigation note only when the persisted permission is `true` and checker evidence is valid |
| R2 | Block expansion unless owner signs off |
| R1 | Block promotion |
| R0 | Block promotion and require rollback/fallback |

The evaluator treats a persisted `promotion_allowed=false` as a fail-closed
`persisted_readiness_veto` for R4 and R3. `owner_signoff` does not override
that veto in those states. The documented R2 owner-signoff exception remains
limited to R2 and does not remove the certificate or calibration-validity
checks; R1 and R0 remain blocked.

The gate must reject readiness updates that cite uncalibrated Track 2.2 shift
events. Required shift fields are `stationarity_regime_id`, `calibration_id`,
`empirical_fp_rate`, and one of `p_value`, `e_value`, or `ert`.
