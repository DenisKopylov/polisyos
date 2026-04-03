# ADR-0093: Dynamic Transportability with Time-Stationarity Flag

## Status
Proposed

## Date
2026-02-28

## Context
Standard transportability theory assumes that causal mechanisms are stable over time.
Many policy-relevant effects, however, involve lagged or time-varying mechanisms:
a tax change may take years to affect behaviour, and the causal structure itself may
shift between the source study period and the target implementation period. Phase 12
extends the transportability framework to explicitly model temporal assumptions,
preventing silent misapplication of static transportability results to dynamic
settings.

## Decision
1. Add an `assumes_time_stationarity: bool` flag to the `TransportabilityResult` IR
   model. When `true`, the result is valid only if causal mechanisms have not changed
   between source and target time periods.
2. The `transport_check` foundry method sets this flag based on whether the source
   and target problem frames differ in their temporal windows by more than a
   configurable threshold (default: 5 years).
3. When `assumes_time_stationarity` is `true` and the temporal gap exceeds the
   threshold, the governance pipeline emits a WARNING advising the analyst to
   verify mechanism stability or supply time-series evidence of stationarity.
4. Introduce an optional `lag_structure` field on `ProblemFrame` where analysts can
   declare expected effect delays (e.g., "24 months to steady state"), enabling
   future phases to incorporate lagged effect models.
5. Legal evaluation (lex) surfaces the time-stationarity assumption in the
   transport constraints report for regulatory reviewers.

## Consequences
### Positive
- Makes temporal assumptions explicit, preventing silent misapplication of
  static transportability results to dynamic policy contexts.
- The configurable threshold allows domain-specific calibration of what counts
  as a meaningful temporal gap.
- The `lag_structure` field provides a foundation for future dynamic causal models.
### Negative
- The 5-year default threshold is arbitrary and may not suit all policy domains
  (e.g., technology policy may shift in months, demographic policy in decades).
- Verifying time stationarity requires longitudinal data that may not be available,
  making the warning difficult to resolve in practice.
- Adds complexity to the already rich transportability result model.
