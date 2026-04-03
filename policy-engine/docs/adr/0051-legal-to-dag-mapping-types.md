# ADR-0051: Legal-to-DAG Mapping Types

## Status
Proposed

## Date
2026-02-28

## Context
Legal constraints affect causal directed acyclic graphs (DAGs) in structurally different
ways. A minimum wage law modifies the effect of education on income; a prohibition on a
substance blocks the mechanism entirely; a mandatory licensing requirement redefines what
counts as the intervention. Treating all legal constraints uniformly would lose this
structural information, producing incorrect transport adjustments.

## Decision
1. `LegalToDAGMapping` defines three mapping types: `effect_modifier`, `mechanism_node`, and
   `intervention_redef`.
2. `effect_modifier`: the legal constraint modifies the strength or direction of an existing
   edge (e.g., minimum wage changes education -> income slope).
3. `mechanism_node`: the legal constraint blocks or introduces a mediating node in the causal
   pathway (e.g., drug prohibition removes substance -> health_outcome pathway).
4. `intervention_redef`: the legal constraint redefines the intervention variable itself
   (e.g., licensing requirements change the meaning of "market entry").
5. In MVP, all three types set `requires_expert_review = True` to ensure human validation of
   the legal-to-DAG translation before it affects downstream analysis.

## Consequences
### Positive
- Structural differentiation enables precise graph modifications rather than blunt blocking.
- The three types cover the empirically observed categories of legal-causal interaction in
  policy analysis literature.
- Expert review requirement in MVP prevents automated misclassification from propagating.

### Negative
- The taxonomy may prove incomplete as more legal systems are analyzed; new types may need to
  be added.
- `requires_expert_review = True` for all mappings creates a human bottleneck in MVP.
- Mapping classification requires both legal and causal inference expertise, which is a rare
  combination.
