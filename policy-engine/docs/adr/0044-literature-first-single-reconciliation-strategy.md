# ADR-0044: Literature-First as the Single Reconciliation Strategy

## Status
Proposed

## Date
2026-02-28

## Context
When reconciling a data-driven causal graph (e.g., from PC/FCI discovery) with the
literature-derived SKG graph, multiple strategies are possible: literature-first (prefer SKG
edges, add data-only edges with penalty), data-first (prefer discovered edges, use literature
for validation), or consensus (require agreement from both). Supporting all three in MVP would
cause a complexity explosion in the reconciliation and governance pipelines.

## Decision
1. `LITERATURE_FIRST` is the only reconciliation strategy implemented in MVP.
2. Under LITERATURE_FIRST: SKG edges are accepted with their literature confidence; data-only
   edges are accepted but penalized (confidence *= 0.7); conflicting directions use SKG
   direction with a conflict flag.
3. The `ReconciliationStrategy` enum exists in the codebase with all three variants defined,
   but `DATA_FIRST` and `CONSENSUS` raise `NotImplementedError` if selected.
4. Alternative strategies are tracked in the backlog and gated behind a future ADR.
5. The reconciliation output includes a `strategy_used` field for auditability.

## Consequences
### Positive
- Dramatically reduces implementation and testing surface for MVP.
- Literature-first is the most defensible default for policy analysis where scientific
  consensus should anchor causal claims.
- Clear path to extension: the enum and interface are already in place.

### Negative
- Domains where empirical data is richer than literature (e.g., novel interventions) may
  produce suboptimal reconciled graphs.
- Users cannot override the strategy without code changes until alternatives are implemented.
- Data-only edges receive a fixed penalty that may be too aggressive in some contexts.
