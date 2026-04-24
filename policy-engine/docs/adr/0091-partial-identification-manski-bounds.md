# ADR-0091: Partial Identification Bounds as Fallback for Non-Transportable Results

## Status

Proposed

## Date

2026-02-28

## Context

When formal transportability analysis concludes that a causal effect is
`NON_TRANSPORTABLE` between source and target populations, the current pipeline
halts with no usable estimate. In many policy-relevant scenarios, a bounded interval
is more useful than no answer at all. Manski (1990) partial identification provides
worst-case bounds on treatment effects under minimal assumptions, offering a
principled fallback that communicates uncertainty without requiring full
transportability.

## Decision

1. When the `transport_check` method returns `NON_TRANSPORTABLE`, automatically
   invoke a `partial_identification` fallback step that computes Manski bounds
   on the average treatment effect.
2. Implement Manski bounds computation in `ir.analytics.partial_identification`,
   producing a `PartialIdentificationResult` IR model with fields: `lower_bound`,
   `upper_bound`, `assumptions`, and `tightening_applied`.
3. Support optional bound tightening via monotone treatment response (MTR) and
   monotone treatment selection (MTS) assumptions when the analyst explicitly
   enables them through the problem frame.
4. The governance pipeline annotates partial identification results with a
   `PARTIAL_ID_FALLBACK` flag so downstream consumers (decision packet, lex
   evaluation) can distinguish bounded from point-identified estimates.
5. Display bounds as intervals in the decision packet rather than point estimates.

## Consequences

### Positive

- Provides actionable (if wide) bounds instead of a dead-end for non-transportable
  cases, increasing the system's coverage of real-world policy questions.

- Manski bounds require minimal assumptions, making them robust by construction.
- Tightening options allow progressive refinement as additional assumptions are justified.

### Negative

- Bounds can be very wide (e.g., [0, 1] for binary outcomes), limiting practical
  usefulness without tightening assumptions.

- Analysts may over-rely on tightened bounds without fully vetting the additional
  assumptions (MTR/MTS), introducing hidden bias.

- Adds a secondary estimation path that must be tested and maintained alongside
  the primary point-identification pipeline.
