# ADR-0045: Causal Edge Combined Confidence Formula (Superseded)

## Status

Superseded by ADR-0064

## Date

2026-02-28

## Context

The original combined confidence formula for causal edges used a simple weighted product of
literature confidence and data confidence: `combined = w_lit * lit_conf + w_data * data_conf`.
This linear combination failed to capture the non-linear boost that independent evidence
sources provide: two independent 0.6-confidence sources should yield higher combined
confidence than a single 0.85 source.

## Decision

1. **SUPERSEDED.** This ADR is retained for historical context only.
2. The original formula was: `combined = 0.6 * lit_confidence + 0.4 * data_confidence`.
3. This formula was found to underweight the value of corroborating independent evidence and
   overweight single high-confidence sources.
4. See ADR-0064 for the current Noisy-OR based formula that replaces this approach.
5. All code referencing the old linear formula has been migrated to the Noisy-OR
   implementation in `causal_ensemble.py`.

## Consequences

### Positive

- The linear formula was simple and easy to explain to stakeholders.
- Historical record preserved for understanding the evolution of the confidence model.

### Negative

- The linear formula is no longer in use; any references to it in documentation should be
  updated to point to ADR-0064.

- Transition period required migration of all edge confidence values, which was handled in
  the Phase 5 to Phase 9 migration script.
