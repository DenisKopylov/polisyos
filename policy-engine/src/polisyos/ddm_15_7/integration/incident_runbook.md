# DDM-15.7 Incident Runbook

Use this runbook when the readiness mapper emits `R2`, `R1`, or `R0`.

## Triage

1. Confirm the active `stationarity_regime_id` has not expired.
2. Check whether the alert is driven by realized performance, estimated
   performance, calibrated shift evidence, data quality, or a critical slice.
3. Attach Track 2.2 localization: affected features, affected slices, upstream
   versions, and detector calibration id.
4. Check label delay p50/p90 before interpreting realized metric gaps.

## Actions

| State | Action |
| --- | --- |
| R2 | Open investigation ticket, increase label sampling, run shadow retrain |
| R1 | Freeze rollout, trigger challenger/shadow retrain, require owner sign-off |
| R0 | Roll back or route to fallback, page owner, block registry promotion |

## Guardrails

- Drift-only alerts normally map to `R3` or `R2`, not `R0`.
- Hard data contract failures can bypass statistical FP calibration.
- Retraining is not the default fix for schema, logging, threshold, or upstream
  data-quality failures.
- Close the incident only after the registry state returns to `R4` or `R3` with
  a valid calibration artifact.
