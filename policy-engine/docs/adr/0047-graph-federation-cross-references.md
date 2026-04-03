# ADR-0047: Graph Federation with Cross-References

## Status
Proposed

## Date
2026-02-28

## Context
The three graphs (SKG, Dataset Graph, Legal Graph) have fundamentally different update
rhythms: SKG updates weekly via OpenAlex sync, Dataset Graph updates monthly as new data
sources are ingested, and Legal Graph updates ad-hoc when legislative changes are detected.
A single unified graph would require full re-computation on every update from any source,
which is both wasteful and error-prone.

## Decision
1. Each graph is stored and versioned independently as a federated graph.
2. Cross-references between graphs use a `GraphRef` structure containing `(graph_type,
   entity_id, version)` to enable stable pointers across graph boundaries.
3. Variable alignment across graphs is maintained by the `variable_canonizer` in the academic
   module, which maps source-specific variable names to canonical identifiers.
4. Queries that span multiple graphs (e.g., transportability) use a `FederatedQuery` that
   resolves `GraphRef` pointers at query time, ensuring each graph is read at its latest
   consistent version.
5. A unified graph materialization is explicitly rejected in favor of query-time federation.

## Consequences
### Positive
- Each graph can be updated independently without triggering full re-computation of the
  others.
- Version pointers enable reproducibility: a past analysis can be re-run against the exact
  graph versions it originally used.
- Storage efficiency: no redundant data duplication across graphs.

### Negative
- Query-time federation adds latency compared to a pre-materialized unified graph.
- Cross-graph consistency is eventually consistent, not strongly consistent; brief windows of
  inconsistency are possible during concurrent updates.
- The `GraphRef` indirection adds complexity to debugging and tracing.
