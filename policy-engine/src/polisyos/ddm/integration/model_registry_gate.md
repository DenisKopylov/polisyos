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
| `promotion_allowed` | Registry promotion gate |

The mapper, registry builder, and final evaluator consume one typed
applicability projection. The projection is attached to the in-memory
readiness event and carried as a typed private handoff on the registry record;
it is not serialized into an untyped budget dictionary. Its policy identity is
`ddm_15_7_default_readiness_policy_v1` / `v1`; an unknown policy identity or
version is not authority. The serialized registry shape is unchanged: the
projection is reduced to the existing certificate and promotion fields, while
identity, validity, observation-window, and policy failures reduce permission
to `false`.

Precedence is structural and fail-closed:

1. failed empirical certificate, invalid/expired calibration, unresolved or
   unbound trigger, foreign identity, unavailable observation window, or
   unknown policy version is an independent veto;
2. the persisted `promotion_allowed=false` baseline veto is binding for R4/R3;
3. R4/R3 may pass only when the persisted projection remains allowed;
4. R2 may pass only with the documented owner signoff; signoff cannot override
   an independent veto;
5. R1/R0 remain blocked even when a signoff flag is supplied.

`owner_signoff` is an external institutional assertion and is accepted only at
the R2 boundary; it is never used to launder certificate, identity, validity,
observation, policy-version, or R1/R0 failures.

Promotion rules:

| State | Promotion |
| --- | --- |
| R4 | Allowed |
| R3 | Allowed with investigation note |
| R2 | Block expansion unless owner signs off |
| R1 | Block promotion |
| R0 | Block promotion and require rollback/fallback |

The gate must reject readiness updates that cite uncalibrated Track 2.2 shift
events. Required shift fields are `stationarity_regime_id`, `calibration_id`,
`empirical_fp_rate`, and one of `p_value`, `e_value`, or `ert`.
