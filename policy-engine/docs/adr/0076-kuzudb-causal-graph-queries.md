# ADR-0076: KuzuDB for causal graph Cypher queries, aligned with fabric/world/materialize/kuzu.py

## Status

Proposed

## Date

2026-02-28

## Context

Causal graphs in PolicyOS serve two roles: algorithmic (d-separation, identification)
and analytical (ad-hoc queries like "which confounders lie on all backdoor paths between
X and Y?"). The algorithmic role is well-served by rustworkx (ADR-0073), but the
analytical role demands a query language. Cypher is the de-facto standard for property
graph queries, and KuzuDB is an embeddable, in-process graph RDBMS with Cypher support
that we already use in `fabric/world/materialize/kuzu.py` for the world-state
knowledge graph. Re-using KuzuDB avoids introducing a second graph database and keeps
the operational surface small.

## Decision

1. Extend the existing KuzuDB instance in `fabric/world/materialize/kuzu.py` with a
   `causal_graph` node table and `causal_edge` relationship table, using the same
   connection pool and lifecycle management.
2. Implement `CausalGraphKuzu` in `ir/analytics/causal_graph_kuzu.py` as a read-only
   projection: on each `CausalGraphModel` materialisation, sync nodes and edges into
   KuzuDB with full attribute fidelity (edge type, mechanism source, confidence).
3. Expose a `query_causal_graph(cypher: str) -> list[dict]` function for downstream
   consumers (governance passes, Lex transport-constraint checks).
4. DDL schemas live in `ir/analytics/ddl/` and are versioned alongside the IR schema
   snapshots.
5. Write-path remains rustworkx-only; KuzuDB is a materialised read replica for
   queries, not the source of truth.

## Consequences

### Positive

- Reuses existing KuzuDB infrastructure, avoiding a new operational dependency.
- Cypher enables expressive path queries that are cumbersome with imperative graph APIs.
- In-process embedding means zero network overhead for queries.

### Negative

- Materialisation step adds latency (~50ms for 500-node graphs) on every graph update.
- Cypher query correctness is not statically checked; malformed queries fail at runtime.
- KuzuDB's Cypher dialect has minor deviations from Neo4j's openCypher standard.
