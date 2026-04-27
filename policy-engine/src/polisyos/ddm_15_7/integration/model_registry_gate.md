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
