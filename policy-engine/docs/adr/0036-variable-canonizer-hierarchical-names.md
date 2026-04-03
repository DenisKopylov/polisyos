# ADR-0036: Variable Canonizer with Hierarchical Names

## Status
Proposed

## Date
2026-02-28

## Context
Phase 0 knowledge pipeline must merge causal claims from multiple studies into a
unified Structured Knowledge Graph. The same economic or social variable appears
under different names across studies (e.g., "GDP growth", "economic growth rate",
"real GDP change"). Without canonical naming, graph merging produces duplicate
nodes for identical concepts, fragmenting evidence and inflating graph complexity.

## Decision
1. Implement `VariableCanonizer` in `polisyos.academic.knowledge.variable_canonizer`
   with **hierarchical canonical names** (e.g., `economy.growth.gdp_real`).
2. Canonization uses a **seed vocabulary** of known variable hierarchies
   (`seed_variable_alignments.yaml`) as the ground truth for exact matches.
3. For non-exact matches, apply **fuzzy matching** (embedding similarity +
   string distance) to propose canonical mappings.
4. Ambiguous fuzzy matches (similarity below 0.85) are routed to **human review**
   rather than auto-assigned.
5. Canonization results are cached in a **deterministic DuckDB store** for
   consistency across pipeline runs and fast lookup.
6. Hierarchical names use dot-separated segments: `domain.category.variable`.

## Consequences
### Positive
- Consistent variable naming across the SKG, enabling accurate graph merging
  and evidence aggregation.
- Deterministic caching ensures identical inputs produce identical canonical
  names across runs.
- Hierarchical structure supports variable grouping and domain-level queries.

### Negative
- Requires ongoing **seed vocabulary maintenance** as new domains are added.
- Fuzzy matching false positives may merge genuinely distinct variables;
  human review mitigates but does not eliminate this risk.
