# ADR-0092: Harmonic Mean for Confidence Composition in Proxy Chains

## Status

Proposed

## Date

2026-02-28

## Context

When a target variable is reached through a chain of proxy substitutions (e.g.,
variable A proxied by B, which is itself proxied by C), the overall confidence of
the chain must reflect the weakest link. Arithmetic and geometric means over-estimate
chain confidence because they do not sufficiently penalise a single low-confidence
step. Sheaf-theoretic consistency conditions for composing local measurements on
overlapping open sets suggest that the harmonic mean is the natural composition
operator: it is dominated by the smallest input and converges to zero if any link
has zero confidence.

## Decision

1. Adopt the harmonic mean as the default composition operator for confidence scores
   along proxy variable chains. For a chain with individual link confidences
   c_1, c_2, ..., c_n, the composed confidence is: n / (1/c_1 + 1/c_2 + ... + 1/c_n).
2. Implement the composition in `datasets.knowledge.proxy_resolver` and expose it
   as a utility in `ir.analytics.parameters` for reuse.
3. If any link confidence is exactly zero, the entire chain confidence is zero;
   the chain is rejected and the proxy path is not used.
4. The composed confidence value is stored in the `CertificationResult` alongside
   the individual link scores for full traceability.
5. This operator applies only to serial proxy chains; parallel (independent) evidence
   aggregation uses Noisy-OR as defined in ADR-0094.

## Consequences

### Positive

- Properly penalises weak links in proxy chains, preventing overconfident estimates
  from long or fragile substitution paths.

- Grounded in sheaf-theoretic consistency, providing mathematical justification
  beyond ad-hoc heuristics.

- Zero-confidence short-circuit prevents propagation through broken links.

### Negative

- The harmonic mean can be overly conservative when one link is slightly weaker
  than the rest, collapsing the overall score disproportionately.

- Assumes all links contribute equally to chain quality; does not account for
  varying structural importance of different proxy steps.

- Requires all link confidences to be on the same ordinal scale (ADR-0094) to be
  meaningful, adding a calibration dependency.
