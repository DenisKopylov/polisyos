# ADR-0041: Confidence Aggregation via Quality Score and Replication Bonus

## Status

Proposed

## Date

2026-02-28

## Context

Multiple studies may report on the same causal edge (e.g., "education -> income").
A naive aggregation (simple weighted mean of effect sizes) treats all studies equally,
ignoring design quality and the epistemic value of independent replication. We need an
aggregation strategy that rewards higher-quality evidence and the fact that independent
replication substantially increases confidence in a causal claim.

## Decision

1. Each study contributing to a causal edge receives a `quality_score` in [0, 1] based on
   study design: RCT > quasi-experimental > observational > cross-sectional.
2. Aggregation uses `quality_score` as the primary weight, not sample size alone.
3. A `replication_bonus` multiplier (default 1.15 per independent replication, capped at 3
   replications) is applied when multiple independent studies confirm the same direction of
   effect.
4. The combined confidence formula is:
   `confidence = clamp(sum(quality_score_i * effect_i) / sum(quality_score_i) * replication_bonus, 0, 1)`
5. Simple `weighted_mean` aggregation is explicitly rejected as the default strategy.

## Consequences

### Positive

- RCT-backed edges receive appropriately higher confidence than observational-only edges.
- Independent replication is rewarded, aligning with scientific epistemology.
- The formula is transparent and auditable in governance reports.

### Negative

- Requires accurate classification of study design, which adds complexity to the article
  extraction pipeline.

- The replication bonus cap (3) is somewhat arbitrary and may need future calibration.
- Edge cases where a single high-quality RCT conflicts with many low-quality observational
  studies require human review.
