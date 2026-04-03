# ADR-0026: Exclude NOTEARS from Default Causal Discovery Stack

## Status
Accepted

## Date
2026-02-28

## Context
Phase 1 formalizes terminology and baseline causal stack decisions for subsequent phases.
Default discovery choices must remain stable, auditable, and operationally predictable for policy workflows.
NOTEARS has known practical instability in target workloads with moderate dimensionality and does not provide a robust default guarantee for DAG validity in this rollout.

## Decision
1. Exclude NOTEARS from the **default** causal discovery stack.
2. Keep default discovery stack as:
   - `causal-learn` (PC/FCI) for cross-sectional settings.
   - `tigramite` (PCMCI family) for time-series settings.
3. Keep DAGMA and other large-scale alternatives in backlog/non-default track.

## Consequences
### Positive
- Reduces baseline instability risk in default discovery pipelines.
- Keeps phase sequencing aligned with selected MVP dependencies.
- Simplifies governance and reproducibility expectations for default workflows.

### Negative
- Users with NOTEARS-specific preferences require non-default integration work.
- Large-scale optimization-oriented discovery remains deferred to backlog alternatives.

## Scope Boundaries
- This ADR only governs the default stack policy.
- It does not forbid future optional adapters behind explicit non-default methods.
