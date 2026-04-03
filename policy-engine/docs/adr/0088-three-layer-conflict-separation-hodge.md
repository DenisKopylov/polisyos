# ADR-0088: Three-Layer Conflict Separation with Hodge Diagnostics

## Status
Proposed

## Date
2026-02-28

## Context
Graph reconciliation merges causal structures from multiple sources (literature,
discovery algorithms, expert elicitation). Conflicts between sources are inevitable:
some are trivially patchable (e.g., a missing edge), others are fundamentally
irreconcilable (contradictory edge directions), and a third class forms cyclic
disagreement patterns that indicate systematic bias. Phase 9 introduces a structured
three-layer decomposition inspired by Hodge theory to classify and handle these
conflicts separately in the reconciliation pipeline.

## Decision
1. Classify every inter-source conflict into one of three layers:
   - **L1 (Patchable)**: missing edges or attributes that can be resolved by union
     or majority vote without logical contradiction.
   - **L2 (Irreducible)**: direct contradictions (e.g., X -> Y vs. X <- Y) that
     require analyst adjudication or confidence-weighted resolution.
   - **L3 (Cyclic)**: sets of conflicts forming directed cycles in the disagreement
     graph, signalling systematic source bias or domain mismatch.
2. Apply Hodge decomposition on the pairwise disagreement matrix to separate
   gradient (L1), harmonic (L2), and curl (L3) components, providing a principled
   mathematical basis for the classification.
3. The `graph_reconciliation` foundry method returns a `ConflictReport` with counts
   and details per layer; L3 conflicts trigger a governance WARNING.
4. L1 conflicts are auto-resolved; L2 conflicts use confidence-weighted majority;
   L3 conflicts are flagged for manual review and excluded from the merged graph.
5. The Hodge diagnostics (gradient/harmonic/curl norms) are persisted in the
   `CausalGraphModel` IR for downstream audit.

## Consequences
### Positive
- Provides a mathematically grounded taxonomy of conflicts instead of ad-hoc rules.
- Auto-resolves trivial disagreements, reducing analyst burden.
- Cyclic bias detection surfaces systematic problems early.
### Negative
- Hodge decomposition adds computational cost proportional to the number of source
  pairs and edges; may be slow for very large graphs.
- The three-layer model is a simplification; some conflicts may not fit cleanly.
- Requires analysts to understand Hodge diagnostics to interpret L3 warnings.
