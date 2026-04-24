# ADR-0046: Three-Graph Closure for Transportability

## Status

Proposed

## Date

2026-02-28

## Context

Transport analysis -- determining whether a causal effect estimated in one context applies to
another -- requires reasoning about three distinct knowledge sources: scientific literature
(what mechanisms exist), datasets (what variables are measured where), and legal constraints
(what interventions are permissible). Treating these as a single unified graph loses the
provenance and update semantics specific to each source.

## Decision

1. Transportability analysis operates over a Three-Graph Closure: the Scientific Knowledge
   Graph (SKG), the Dataset Graph, and the Legal Constraint Graph.
2. The SKG provides causal edges and mechanism structure; the Dataset Graph provides variable
   availability and measurement quality per context; the Legal Graph provides intervention
   feasibility and effect modification constraints.
3. The closure operation produces a `TransportabilityFrame` that contains: the target causal
   query, the set of S-nodes (context-varying factors), available adjustment sets, and legal
   blocks.
4. Each graph contributes typed constraints to the frame: `CausalConstraint`,
   `DataConstraint`, `LegalConstraint`.
5. The Three-Graph Closure is computed by the `transport_check` foundry method.

## Consequences

### Positive

- Clean separation of concerns: each graph has its own update rhythm, schema, and quality
  guarantees.

- Legal constraints are first-class participants in transport analysis, not afterthoughts.
- The `TransportabilityFrame` provides a single auditable artifact for governance review.

### Negative

- Three-way joins across graphs add complexity to the transport resolution algorithm.
- Cross-graph consistency must be maintained (e.g., variable names must align across all
  three graphs).

- The closure operation may be computationally expensive for large graphs with many contexts.
