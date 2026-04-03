# ADR-0064: compute_combined_confidence() = 1 - Prod(1-conf_i)^w_i (Noisy-OR)

## Status
Proposed

## Date
2026-02-28

## Context
Multiple independent evidence sources (literature priors, observational
estimates, sensitivity analyses) each provide a confidence score for a causal
relationship. A principled aggregation function is needed that reflects the
intuition that additional confirming evidence should increase overall confidence
but with diminishing returns. Simple averaging does not capture this, and
weighted sums can exceed 1.0. The Noisy-OR model from probabilistic reasoning
naturally bounds the result in [0, 1] and treats each source as an independent
opportunity to confirm the relationship.

## Decision
1. Implement `compute_combined_confidence()` using the weighted Noisy-OR
   formula: `1 - Prod_i((1 - conf_i) ^ w_i)`.
2. Weights `w_i` default to 1.0 and are configurable per evidence source type
   in the calibration config.
3. Individual confidence values must lie in [0, 1]; values outside this range
   cause a validation error.
4. The function is placed in `ir/analytics/causal.py` and re-exported through
   the IR public API.

## Consequences
### Positive
- Noisy-OR naturally bounds combined confidence in [0, 1] without ad-hoc
  clamping, producing interpretable probability-like scores.
- Weighted exponents allow domain experts to down-weight weaker evidence
  sources (e.g., observational vs. experimental) through configuration.

### Negative
- The independence assumption underlying Noisy-OR may not hold when evidence
  sources share underlying data, leading to overconfident aggregates.
- Non-expert users may find the Noisy-OR formula less intuitive than a simple
  weighted average, requiring additional documentation.
