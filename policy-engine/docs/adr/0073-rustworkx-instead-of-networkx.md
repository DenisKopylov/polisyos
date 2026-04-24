# ADR-0073: rustworkx instead of NetworkX for graph computations (Phases 0/9/12)

## Status

Proposed

## Date

2026-02-28

## Context

Phases 0, 9, and 12 perform intensive graph operations: cycle detection, d-separation
queries, topological sorting, ancestor/descendant lookups, and Markov-blanket
extraction. NetworkX, while ergonomic, is implemented in pure Python and becomes a
bottleneck on causal graphs with 200+ nodes and dense latent-variable projections.
Profiling shows that `nx.d_separated` and `nx.ancestors` account for 35-40% of wall
time in the resolution loop. rustworkx (formerly retworkx) is a Rust-backed graph
library with a NetworkX-compatible API surface and 10-50x speedups on common
algorithms.

## Decision

1. Adopt `rustworkx` as the primary in-memory graph backend for `CausalGraphModel`,
   `_break_cycles`, and all `foundry/methods/causal/` graph algorithms.
2. Store the canonical graph as a `rustworkx.PyDiGraph` with node/edge attribute dicts
   mirroring the current NetworkX schema.
3. Provide a `to_networkx()` escape hatch on `CausalGraphModel` for interop with
   libraries that require NetworkX (e.g., `y0`, `dowhy` internals).
4. Replace `nx.ancestors`, `nx.descendants`, `nx.d_separated`, and
   `nx.topological_sort` with their `rustworkx` equivalents throughout the codebase.
5. Gate the dependency as non-optional; rustworkx ships manylinux/macOS wheels with
   no build-time Rust toolchain requirement.

## Consequences

### Positive

- 10-50x speedup on graph-heavy hot paths (cycle breaking, resolution loop, d-sep).
- rustworkx is maintained by the Qiskit team at IBM with active releases.
- Attribute-dict API keeps migration mechanical and low-risk.

### Negative

- Two graph representations must coexist during the migration window.
- rustworkx has a smaller ecosystem of third-party extensions than NetworkX.
- Developers need to learn rustworkx's index-based node referencing model, which
  differs from NetworkX's label-based model.
