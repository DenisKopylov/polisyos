# ADR-0086: SUTVA Assumption Check Pass

## Status

Proposed

## Date

2026-02-28

## Context

The Stable Unit Treatment Value Assumption (SUTVA) underpins most causal inference
estimators in the foundry. SUTVA requires that one unit's treatment does not affect
another unit's outcome -- an assumption routinely violated by market-wide, network, or
spillover-prone policies. Without an explicit gate, the pipeline silently produces
biased estimates for interventions where interference is likely. Phase 8 introduces a
governance pass that flags SUTVA-sensitive scenarios before estimation proceeds.

## Decision

1. Add `SutvaCheckPass` to the governance pass pipeline, executed after DAG
   reconciliation and before any estimator invocation.
2. The pass emits a `WARNING` severity (not `BLOCK`) when the policy scope is
   classified as market-wide, network-affecting, or when the treatment variable's
   metadata indicates potential interference.
3. Introduce a `sutva_assumed: bool` flag on `ProblemFrame` that analysts must
   explicitly set to `true` to acknowledge the assumption. When the flag is absent
   or `false`, the pass appends a structured advisory to the governance report.
4. Downstream estimators may read `sutva_assumed` to switch to interference-robust
   methods (e.g., partial interference models) in future phases.

## Consequences

### Positive

- Makes a commonly violated assumption visible in every analysis run.
- Provides an auditable record that the analyst considered interference.
- Opens a clear extension point for interference-aware estimators.

### Negative

- Adds an extra governance step that may slow iteration for simple analyses.
- Classification of "market-wide" scope relies on heuristics that can produce
  false positives, requiring analyst override.

- The WARNING-only severity means the pass cannot prevent biased results on its
  own; it depends on analyst diligence.
