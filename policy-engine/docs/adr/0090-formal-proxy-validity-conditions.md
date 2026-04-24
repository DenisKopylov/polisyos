# ADR-0090: Formal Proxy Validity Conditions

## Status

Proposed

## Date

2026-02-28

## Context

When a target variable is unavailable in the dataset, the system substitutes a proxy
variable. Informal proxy selection leads to biased estimates when the proxy violates
structural assumptions relative to the causal graph. Phase 12 codifies four formal
validity conditions that every proxy must satisfy before it can replace a target
variable in estimation. These conditions are drawn from the measurement error and
proxy variable literature in causal inference.

## Decision

1. Define four mandatory proxy validity conditions, each checked programmatically:

   - **Relevance**: the proxy must be significantly associated with the target
     variable (measured via partial correlation or mutual information above a
     configurable threshold).
   - **Exclusion**: the proxy must not have a direct causal effect on the outcome
     except through the target variable it replaces.
   - **Non-collider**: the proxy must not be a collider on any active path between
     treatment and outcome in the causal graph.
   - **Completeness**: the proxy must cover the same population subgroups as the
     target variable; missingness patterns must not introduce selection bias.
2. Implement these checks in `datasets.knowledge.proxy_resolver`, invoked
   automatically when variable alignment proposes a proxy substitution.
3. A proxy that fails any condition is rejected; the system falls back to partial
   identification bounds (ADR-0091) rather than using an invalid proxy.
4. Validity check results are recorded in the `CertificationResult` IR model for
   audit and reproducibility.

## Consequences

### Positive

- Eliminates a common source of silent bias from invalid proxy substitutions.
- Automated checks reduce reliance on analyst judgement for structural assumptions.
- Graceful fallback to partial identification preserves analysis continuity.

### Negative

- Relevance and completeness checks require sufficient overlapping data, which may
  not always be available, leading to conservative proxy rejection.

- The exclusion and non-collider checks depend on the correctness of the causal
  graph, inheriting any graph specification errors.

- Strict enforcement may reduce the number of usable variables, limiting the scope
  of feasible analyses.
