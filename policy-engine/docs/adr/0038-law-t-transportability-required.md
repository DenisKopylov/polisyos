# ADR-0038: Law T -- Transportability Required for External Estimates

## Status
Proposed

## Date
2026-02-28

## Context
Phases 8 and 12 enable reuse of causal effect estimates across different policy
contexts. A `CausalEffectReport` produced in one country, time period, or
demographic may not be valid in another context due to differences in covariate
distributions, institutional structures, or latent confounders.

Unrestricted reuse of external estimates without transport analysis risks
invalid policy conclusions -- e.g., applying a Nordic education policy effect
estimate to a Sub-Saharan African context without assessing contextual
differences.

## Decision
1. **Law T**: Any `CausalEffectReport` originating from an external context
   that is used in a policy recommendation **must** pass a
   `TransportabilityRequired` governance check.
2. The `transportability_required_pass` in the scientist governance pipeline
   verifies that a `TransportabilityResult` exists for every external estimate
   referenced in the decision packet.
3. Transport analysis must produce a `transport_confidence` score. Estimates
   with `transport_confidence < 0.3` are **rejected** in all governance
   profiles.
4. Between 0.3 and 0.6, the estimate is flagged with a **transport warning**
   in the decision packet.
5. "External context" is defined as any source context where
   `ContextProfile.distance_to(target) > 0.0` (see ADR-0039).

## Consequences
### Positive
- Prevents naive cross-context extrapolation of causal effect estimates.
- Ensures every policy recommendation accounts for contextual validity of
  its evidence base.
- Transport confidence scores provide quantified uncertainty about
  generalizability.

### Negative
- Increases pipeline complexity: every external estimate requires a
  corresponding transport analysis step.
- May slow down rapid policy analysis when transport data is unavailable
  for the target context.
