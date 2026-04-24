# ADR-0066: PAG to DAG projection: bidirectional edges to U-dummy nodes for dowhy.gcm

## Status

Proposed

## Date

2026-02-28

## Context

Constraint-based causal discovery algorithms (e.g., PC, FCI) produce Partial
Ancestral Graphs (PAGs) that may contain bidirectional edges (X <-> Y),
indicating the presence of an unobserved common cause. The `dowhy.gcm` API
requires a strict DAG as input and cannot process bidirectional edges directly.
A projection step is needed to convert PAGs into valid DAGs while preserving the
latent-variable semantics so that downstream identification and estimation remain
sound.

## Decision

1. For each bidirectional edge X <-> Y in the PAG, introduce a U-dummy latent
   node U*{XY} with directed edges U*{XY} -> X and U\_{XY} -> Y.
2. U-dummy nodes are tagged with `is_latent=True` in the graph metadata so
   that GCM fitting assigns them appropriate noise models.
3. The projection is implemented in `_graph_projection.py` within the foundry
   causal catalog and is invoked automatically before any `dowhy.gcm` call.
4. Original PAG edge types are preserved in edge metadata for audit and
   governance reporting purposes.

## Consequences

### Positive

- The projection produces a valid DAG that `dowhy.gcm` can consume without
  modification, enabling the full GCM fitting and query pipeline.

- Retaining U-dummy nodes preserves the latent-confounder semantics of the
  original PAG, keeping identification analysis sound.

- Storing original PAG edge types in metadata allows governance passes to
  reason about discovery uncertainty.

### Negative

- Each bidirectional edge adds one node and two edges to the graph, increasing
  memory and computation cost for GCM operations.

- U-dummy nodes require sensible default noise-model assignments, which may
  not be appropriate for all latent-variable scenarios without domain input.
