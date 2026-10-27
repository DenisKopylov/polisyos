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

## Observation and applicability boundary

A caller trigger list, including `[]`, is diagnostic input and cannot prove
observation completeness. The private checker requires a separately configured
source. The concrete `FiniteCalibrationObservationSource` enumerates a selected
finite replay file, binds all invalidation entries and consumed shift/degradation
and budget inputs, and reports `completeness_provenance=recomputed` only relative
to that finite source. Source selection is configured out of band; a public
registry payload cannot select the resolver or its path. Changes to source bytes
invalidate retained evidence; rebind reopens the actual source rather than
re-signing public digests or a consumer list. Last-event labels must agree with
the actual consumed basis. Immutable tuples and detached private digests prevent
in-place projection mutation from changing both sides of a comparison.

The finite source has `authority_scope=finite_replay_only`. A valid candidate
projection from it remains visible, but the final gate returns
`finite_replay_observation_not_production_authority`. No production observation
owner is supplied by this change. Until a legitimate owner resolves coverage,
selection and currentness, default production eligibility remains
`not_established`. This limitation preserves the LA-055 policy table; its
conditional state/signoff/veto logic is tested separately from the missing
observation precondition and cannot be used as a production grant.
