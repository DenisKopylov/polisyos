# ADR-0069: Collider (selection bias) check in _try_eliminate_s_node_simplified

## Status
Proposed

## Date
2026-02-28

## Context
Selection bias arises when conditioning on a collider (a node caused by both
treatment and outcome, or their descendants) opens a spurious path between
treatment and outcome. The graph reconciliation module includes a helper
`_try_eliminate_s_node_simplified` that attempts to remove selection nodes (S-
nodes) from the causal graph when they are deemed safe to ignore. Without an
explicit collider check, this simplification can incorrectly remove nodes whose
conditioning introduces bias, producing invalid causal estimates.

## Decision
1. Before eliminating any S-node, `_try_eliminate_s_node_simplified` must run a
   collider detection check: verify that the candidate node is not a collider
   on any active path between treatment and outcome.
2. If the candidate S-node is identified as a collider, elimination is blocked
   and the node is retained with a `selection_bias_risk=True` flag.
3. The collider check uses d-separation queries on the current graph state,
   reusing the existing `dowhy` graph utilities.
4. Nodes flagged with `selection_bias_risk` are surfaced in the governance
   report for analyst review.

## Consequences
### Positive
- Prevents incorrect S-node elimination that would introduce selection bias
  into downstream causal effect estimates.
- Flagging risky nodes in the governance report provides transparency about
  potential bias sources without silently discarding information.

### Negative
- The additional d-separation query per candidate S-node adds computational
  overhead to graph reconciliation, especially on large graphs.
- Conservative retention of collider S-nodes may leave graphs larger than
  necessary, increasing GCM fitting time.
