# ADR-0037: Law L -- Edges Without Evidence Support

## Status

Proposed

## Date

2026-02-28

## Context

Phases 5 and 8 construct causal graphs from multiple sources: SKG literature
priors, data-driven discovery, LLM suggestions, and expert input. Some edges
in the resulting graph may lack empirical evidence support entirely -- they
exist based on structural assumptions or LLM suggestions without corresponding
studies, datasets, or expert justification with audit trail.

Edges without evidence support carry higher false-positive risk and may
propagate unfounded causal claims into policy recommendations. Governance
must distinguish well-evidenced structure from speculative structure.

## Decision

1. **Law L**: Every edge in a `CausalGraphModel` must declare its evidence
   support status via the `unsupported_by_evidence` boolean field on
   `CausalEdge`.
2. An edge is marked `unsupported_by_evidence=True` when none of the
   following hold:

   - At least one SKG literature prior supports the edge,
   - At least one data-driven discovery method found the edge stable,
   - An expert-specified edge has a signed audit record.
3. In the **STRICT** governance profile, any `unsupported_by_evidence=True`
   edge in the active causal graph causes the governance pass to **FAIL**.
4. In the **STANDARD** governance profile, unsupported edges produce a
   **WARNING** and are included in the decision packet risk section.
5. The `literature_gate_pass` governance pass enforces Law L at the graph
   level before causal inference proceeds.

## Consequences

### Positive

- Explicit evidence tracking per edge provides full transparency into graph
  provenance.

- STRICT governance prevents unfounded causal claims from reaching policy
  recommendations.

- Decision packets clearly surface which edges lack empirical backing.

### Negative

- May block analyses in data-sparse domains where SKG coverage is thin and
  expert input is limited.

- Requires diligent evidence linking during graph construction to avoid
  false positives on the unsupported flag.
