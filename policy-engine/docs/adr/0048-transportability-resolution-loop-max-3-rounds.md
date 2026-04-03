# ADR-0048: Transportability Resolution Loop with Max 3 Rounds

## Status
Proposed

## Date
2026-02-28

## Context
S-node elimination in transportability analysis may require iterative resolution: adjusting
for one S-node (context-varying factor) via a proxy variable can introduce new dependencies
that reveal additional S-nodes. Without a bound on iterations, the resolution loop could
cycle indefinitely in adversarial graph structures or when proxy chains are deep.

## Decision
1. The `TransportabilityResolutionLoop` executes a maximum of 3 resolution rounds.
2. Each round: identify active S-nodes, attempt elimination via adjustment or proxy
   substitution, re-evaluate the graph for newly revealed S-nodes.
3. Convergence is defined as S-node stability: no new S-nodes appear between consecutive
   rounds.
4. If the loop does not converge within 3 rounds, the result is marked as
   `convergence = False` with `remaining_s_nodes` listing the unresolved factors.
5. The round limit of 3 is a tunable parameter (`max_rounds`) but defaults to 3 based on
   empirical analysis of typical policy transport problems.

## Consequences
### Positive
- Guaranteed termination prevents runaway computation in adversarial or pathological cases.
- 3 rounds is sufficient for the vast majority of real-world transport problems (based on
  analysis of education, health, and labor policy domains).
- Non-convergence is reported explicitly, enabling human review of complex cases.

### Negative
- Some legitimate deep proxy chains (4+ levels) will be reported as non-convergent, requiring
  manual intervention or parameter override.
- The fixed default may need adjustment as more policy domains are onboarded.
- Each additional round multiplies the computational cost of the transport check.
