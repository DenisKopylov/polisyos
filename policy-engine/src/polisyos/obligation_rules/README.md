# Obligation Rules

- Last updated: 2026-05-23
- Owner: team-policyos-runtime
- Purpose: governed obligation rule catalog for the universal Policy Design Case compilation kernel.
- Allowed contents: typed rule/catalog contracts, governed seed taxonomy, W2.B rule-evolution bridge, catalog persistence helpers, public/audit inspection surfaces, and candidate-to-rule admission guards.
- Boundary: LLM or critic output may enter only as `ObligationRuleCandidate`; it cannot become a governed rule without an explicit `RuleGovernanceDecision`.
- Local verification: `uv run pytest tests/unit/obligation_rules -q`
