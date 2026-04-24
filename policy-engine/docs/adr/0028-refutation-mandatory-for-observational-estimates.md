# ADR-0028: Refutation Mandatory for Observational DoWhy Estimates

## Status

Accepted

## Date

2026-02-28

## Context

Phase 3 of SCM v3 introduces robustness requirements for observational causal estimates.
`dowhy_identify_estimate` can return a statistically valid point estimate while still being
fragile to perturbations in treatment assignment, confounding, or sample composition.

Before this ADR, refutation was optional and not enforced by governance profiles.

## Decision

1. Add mandatory DoWhy refutation pipeline (`causal.refutation.dowhy_refute@1.0.0`) for
   successful observational DoWhy estimates.
2. Standardize typed IR output in `CausalEffectReport.refutation_results` with
   `RefutationResult`.
3. Enforce governance checks through `RefutationPass` with profile-dependent severity:

   - `STRICT` -> blocker,
   - `MVP` -> warning.
4. In Phase 3 scope, mandatory checks apply only to DoWhy methods:
   `dowhy_backdoor`, `dowhy_iv`, `dowhy_frontdoor`.

## Consequences

### Positive

- Governance receives machine-checkable robustness signals, not only point estimates.
- DecisionPacket carries explicit refutation summary for downstream consumers.
- Missing or partial refutation can be detected deterministically.

### Negative

- Additional runtime overhead due to four refutation tests.
- Optional dependency drift in DoWhy refuter APIs requires maintenance.

## Compatibility Notes

- `CausalEffectReport` extension is additive (`refutation_results` defaults to empty list).
- Existing consumers remain compatible if they ignore the new fields.
