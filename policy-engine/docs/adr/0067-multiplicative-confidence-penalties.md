# ADR-0067: Multiplicative confidence penalties Prod(1-p_i) instead of additive

## Status

Proposed

## Date

2026-02-28

## Context

Governance passes and sensitivity analyses may flag issues that reduce
confidence in a causal estimate (e.g., failed refutation, high sensitivity to
unobserved confounders, SUTVA violations). These penalties need to be combined
into a single discount factor applied to the base confidence score. Additive
penalty schemes (confidence - sum(p_i)) can drive confidence below zero and
require ad-hoc clamping. A multiplicative scheme naturally stays in [0, 1] and
models the intuition that each penalty independently reduces the surviving
confidence.

## Decision

1. Compute the combined penalty factor as `Prod_i(1 - p_i)` where each `p_i`
   is a penalty in [0, 1].
2. The final penalised confidence is `base_confidence * Prod_i(1 - p_i)`.
3. Penalties are recorded in the governance report with their source pass name
   and magnitude for auditability.
4. A penalty of 1.0 from any single source drives the result to zero,
   functioning as a hard veto.

## Consequences

### Positive

- Multiplicative combination naturally stays in [0, 1] without clamping,
  producing well-behaved probability-like scores.

- Each penalty is interpretable as a fractional reduction, making it easy to
  trace which governance pass had the largest impact.

- A single veto penalty (p_i = 1.0) cleanly zeroes out confidence, providing
  a natural hard-gate mechanism.

### Negative

- Many small penalties compound aggressively (e.g., ten 10% penalties reduce
  confidence to ~35%), which may be overly conservative in practice.

- The multiplicative model assumes penalty independence; correlated penalties
  (e.g., two tests failing for the same underlying reason) will double-count.
