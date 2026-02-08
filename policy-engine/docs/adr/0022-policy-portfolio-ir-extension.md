# ADR-0022: PolicyPortfolio IR Extension

## Status
Accepted

## Context
`PolicySpec` models a single policy configuration. Real policy planning requires selecting
and optimizing combinations of multiple policies under constraints and interaction effects.

## Decision
- Introduce `PolicyPortfolio` IR with:
  - `policies` (list of `PolicySpec`)
  - `interaction_matrix` (pairwise effects)
  - portfolio-level constraints (`required_policies`, `excluded_pairs`, `max_active_policies`)
- Model interaction effects as additive pairwise deltas with clamping instead of global
  multiplicative chains to avoid unrealistic exponential amplification/collapse.
- Add portfolio search space tooling (`PortfolioSearchSpace`) and controller integration
  (`SearchController.run_portfolio_search`).
- Add completeness warnings for sparse interaction matrices.

## Consequences
- Portfolio optimization becomes explicit and auditable in IR.
- Existing single-policy workflows remain valid.
- Search complexity is bounded via enumeration limits and sampling/greedy modes.
