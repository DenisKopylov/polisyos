# ADR-0065: Cycle breaking via time-lag conversion (not edge deletion)

## Status
Proposed

## Date
2026-02-28

## Context
Causal graphs constructed from observational data or literature extraction
sometimes contain cycles (e.g., A -> B -> A), which violate the DAG requirement
of structural causal models. A naive approach deletes the weakest edge in each
cycle, but this discards genuine causal information and can alter identifiability
of treatment effects. Time-lag conversion preserves all edges by unrolling cyclic
relationships into a temporal DAG (A_t -> B_{t+1} -> A_{t+2}), reflecting the
fact that feedback loops operate over time rather than instantaneously.

## Decision
1. When a cycle is detected during graph reconciliation, apply time-lag
   conversion: split each node involved in a cycle into time-indexed copies.
2. Edge weights and metadata are preserved on the time-indexed edges.
3. The maximum unroll depth defaults to 3 and is configurable in the
   calibration config.
4. If unrolling exceeds the maximum depth without resolving all cycles, the
   graph is flagged for manual review via the governance pipeline.
5. Edge deletion is explicitly prohibited as a cycle-breaking strategy in the
   foundry's graph reconciliation module.

## Consequences
### Positive
- All causal relationships are preserved, avoiding information loss that
  occurs with edge deletion strategies.
- Time-lagged representation more accurately models real-world feedback
  dynamics in policy domains (e.g., economic indicators).

### Negative
- Time-lag unrolling increases graph size quadratically with unroll depth,
  potentially impacting GCM fitting performance on large graphs.
- The choice of unroll depth is a modelling assumption that can affect
  identification results; no single default suits all domains.
