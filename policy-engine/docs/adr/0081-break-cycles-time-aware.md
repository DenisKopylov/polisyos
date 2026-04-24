# ADR-0081: \_break_cycles time-aware: skip for PCMCI output (tags={"time-series"})

## Status

Proposed

## Date

2026-02-28

## Context

The `_break_cycles` step in graph reconciliation removes feedback edges to produce a
DAG from a cyclic or partially directed graph. This is correct for cross-sectional
causal discovery outputs (PC, GES), where cycles indicate estimation artefacts. However,
PCMCI (tigramite) and other time-series discovery methods intentionally produce cyclic
summary graphs: an edge X(t-1) -> Y(t) -> X(t+1) is a legitimate temporal feedback
loop, not an artefact. Blindly breaking these cycles destroys valid temporal causal
structure and leads to incorrect identification in Phase 12.

## Decision

1. Add a `tags: set[str]` field to `CausalDiscoveryReport` (IR artifact) that
   discovery catalog entries populate. PCMCI sets `tags={"time-series"}`.
2. `_break_cycles` checks for the `"time-series"` tag; if present, it skips cycle
   breaking entirely and passes the graph through unchanged.
3. Downstream consumers (identification, estimation) that require a DAG must handle
   the time-unrolled representation: the `graph_reconciliation` module provides a
   `unroll_time_graph(summary_graph, max_lag)` utility that expands the summary graph
   into a full-time DAG.
4. The `time-series` tag also signals the estimation layer to use time-series-aware
   estimators (e.g., panel DML from EconML) rather than i.i.d. estimators.
5. If a non-time-series method produces a cycle, `_break_cycles` continues to apply
   its existing heuristic (remove the lowest-confidence edge per cycle).

## Consequences

### Positive

- Preserves legitimate temporal feedback structure from PCMCI.
- `unroll_time_graph` makes the temporal DAG explicit, enabling standard identification.
- Tag-based dispatch is extensible to other discovery-method categories in the future.

### Negative

- Time-unrolled graphs can be large (nodes x max_lag), increasing memory and compute.
- `unroll_time_graph` requires `max_lag` metadata that must be propagated from the
  discovery step.

- Two code paths (skip vs. break) increase test matrix for graph reconciliation.
