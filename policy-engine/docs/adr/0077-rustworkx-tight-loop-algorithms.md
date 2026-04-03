# ADR-0077: rustworkx for in-memory tight-loop algorithms (cycle breaking, resolution loop)

## Status
Proposed

## Date
2026-02-28

## Context
The resolution loop (Phase 9) and `_break_cycles` (Phase 0) are the two hottest graph
algorithm paths in the pipeline. The resolution loop iteratively re-identifies causal
effects after each proxy-variable substitution, calling d-separation and ancestor
queries on every iteration. `_break_cycles` detects and removes feedback edges to
produce a DAG from a potentially cyclic CPDAG/PAG output. Both inner loops currently
use NetworkX, and profiling on a 300-node education-policy graph shows 4.2 seconds
per resolution-loop iteration and 1.8 seconds for cycle breaking. Switching these
specific hot paths to rustworkx (ADR-0073) is the highest-leverage optimisation.

## Decision
1. Rewrite `_break_cycles` in `foundry/methods/causal/graph_reconciliation.py` to
   operate on `rustworkx.PyDiGraph` using `rx.digraph_find_cycle` and
   `rx.topological_sort`.
2. Rewrite the resolution loop's inner d-separation check to use rustworkx's
   `rx.ancestors` and `rx.descendants` with manual Bayes-ball, since rustworkx does
   not yet expose a native `d_separated` function.
3. Implement a `bayes_ball(graph, x, y, z)` utility in `foundry/methods/causal/`
   using rustworkx traversal primitives, with a pure-Python fallback for testing.
4. Benchmark both paths on the 300-node education-policy graph and the 80-node
   health-policy graph; target <500ms per resolution-loop iteration.
5. Retain NetworkX implementations behind a `_FORCE_NX=True` env-var flag for
   regression testing during the transition period.

## Consequences
### Positive
- Expected 8-15x speedup on resolution-loop iterations based on micro-benchmarks.
- Cycle breaking becomes near-instantaneous for graphs under 500 nodes.
- Shared `bayes_ball` utility benefits all downstream d-separation consumers.
### Negative
- Custom Bayes-ball implementation must be extensively tested against NetworkX's
  `d_separated` to ensure correctness.
- Maintaining two code paths (rustworkx + NetworkX fallback) increases test burden.
- rustworkx's index-based API makes debugging less intuitive than NetworkX's labels.
