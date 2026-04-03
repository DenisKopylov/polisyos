# ADR-0071: InterventionSpec for soft/stochastic interventions from Legal Graph (Phase 11)

## Status
Proposed

## Date
2026-02-28

## Context
Phase 11 integrates legal constraints from Lex into causal inference via the Legal Graph.
Currently, `InterventionSpec` only supports hard `do(X=x)` interventions, which assume
perfect compliance and deterministic policy levers. Real-world policies rarely achieve
full compliance: tax changes face evasion, regulations have enforcement gaps, and
behavioural nudges are inherently probabilistic. Lex already encodes compliance-rate
estimates and enforcement-strength metadata on Legal Graph edges, but there is no
mechanism to propagate those into the causal engine.

## Decision
1. Extend `InterventionSpec` with a `kind` discriminator: `HARD | SOFT | STOCHASTIC`.
2. `SOFT` interventions accept a `shift_distribution` (mean shift + variance) that
   replaces the CPD of the target variable with a location-shifted version of its
   natural distribution rather than a point mass.
3. `STOCHASTIC` interventions accept a `compliance_rate: float` (0-1) drawn from Lex
   edge metadata, modelling the intervention as a Bernoulli mixture of the natural
   and do-world distributions.
4. The `CausalEvaluationNode` dispatcher selects the appropriate DoWhy/EconML estimator
   based on `kind`, falling back to HARD when the downstream estimator lacks soft support.
5. All three kinds produce an `InterventionTrace` audit record that logs the effective
   intervention density for reproducibility.

## Consequences
### Positive
- Policy-effect estimates become more realistic by reflecting partial compliance.
- Lex compliance metadata flows end-to-end into quantitative results.
- Backward-compatible: existing HARD interventions remain the default.
### Negative
- Soft/stochastic identification requires additional assumptions (e.g., monotonicity or
  exclusion restrictions) that must be validated per-study.
- Increases the surface area of `InterventionSpec` serialization and schema versioning.
- Estimator coverage for soft interventions is limited; some method-catalog entries will
  initially raise `NotImplementedError`.
