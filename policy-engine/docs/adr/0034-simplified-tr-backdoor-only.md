# ADR-0034: Simplified Transportability -- Backdoor-Only (Phase 12a)

## Status
Proposed

## Date
2026-02-28

## Context
Phase 12 requires transportability analysis to assess whether causal effect
estimates from a source context can be validly applied in a target context.
Full do-calculus-based transportability is NP-hard in general and requires
specialized graph algorithms (e.g., from the y0/causaleffect libraries) that
are not yet production-ready in the policy-engine stack.

In practice, the majority of policy questions involve interventions where the
backdoor criterion is sufficient for identification, and transport analysis
reduces to checking whether the adjustment set variables have comparable
distributions across contexts.

## Decision
1. **Phase 12a** implements simplified transportability using the **backdoor
   criterion only**: check whether the backdoor adjustment set is valid in
   both source and target contexts, and whether covariate distributions are
   sufficiently similar.
2. Transport confidence is computed from context distance metrics on the
   backdoor variables (see ADR-0039).
3. **Full do-calculus transportability** (front-door, instrumental variable,
   and general identification) is deferred to the **Phase 12b backlog**,
   to be implemented via y0/causaleffect integration.
4. Queries that require non-backdoor identification are flagged with
   `transport_method="unsupported"` and routed to manual review.

## Consequences
### Positive
- Tractable transport analysis covering the majority of policy-relevant
  causal queries without NP-hard graph algorithms.
- Clear scope boundary: Phase 12a ships a useful transport capability
  without blocking on complex do-calculus implementation.
- Manual review fallback ensures no query is silently dropped.

### Negative
- Some valid transport queries that require front-door or IV identification
  cannot be automated and require manual analyst intervention.
- Phase 12b implementation is necessary for full coverage of do-calculus
  transportability.
