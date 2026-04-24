# ADR-0072: Phase 12b full do-calculus via y0/causaleffect bridge, not from-scratch s-ID

## Status

Proposed

## Date

2026-02-28

## Context

Phase 12b requires symbolic identification of causal effects in the presence of
selection bias and transportability constraints (generalised s-ID). Implementing the
full do-calculus engine from scratch would be a multi-month effort with high risk of
correctness bugs in edge cases (hedging, surrogate interventions, nested fixability).
The `y0` library and its companion `causaleffect` R package already implement
Tikka-Karvanen s-ID and Bareinboim-Pearl transportability calculus with peer-reviewed
correctness guarantees. A thin Python bridge can delegate symbolic identification
while keeping the rest of the pipeline in-process.

## Decision

1. Add `y0` (Python, pip-installable) as an optional dependency gated behind the
   `[causal-symbolic]` extra.
2. Build a `Y0IdentificationBridge` adapter in `foundry/methods/causal/` that
   translates our `CausalGraphModel` (rustworkx-backed) into a `y0.graph.NxMixedGraph`
   for identification calls, then maps the resulting `Expression` back to our
   `IdentificationResult` IR.
3. For transportability queries, pass the set of S-nodes from
   `TransportabilityResult.s_nodes` into `y0.algorithm.identify.s_identify`.
4. Retain a simplified in-house backdoor/front-door identifier as a fast-path for
   the common cases (>90% of queries) where full do-calculus is unnecessary.
5. Defer `causaleffect` R bridge to the backlog; `y0` covers the critical path.

## Consequences

### Positive

- Leverages a well-tested symbolic engine, reducing correctness risk substantially.
- Keeps the critical fast-path (backdoor criterion) in pure Python with no extra deps.
- `y0` is pure Python with minimal transitive dependencies.

### Negative

- Adds an optional dependency that must be version-pinned and monitored for breakage.
- `NxMixedGraph` conversion requires a NetworkX intermediate, adding a copy step
  (mitigated by caching the converted graph on the IR artifact).

- Long-term maintainability depends on the `y0` project remaining active.
