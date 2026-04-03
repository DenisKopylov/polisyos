# ADR-0027: DoWhy as Primary Graph-Based Identify/Estimate Method

## Status
Accepted

## Date
2026-02-28

## Context
Phase 2 of the SCM implementation requires graph-based causal identification and estimation in Foundry.
The existing causal inference catalog lacks a graph-native method that performs `identify_effect` and
`estimate_effect` in one method contract.

DoWhy is already part of the causal optional dependencies and aligns with the project direction for
graph-based identification.

## Decision
1. Introduce `causal.inference.dowhy_identify_estimate@1.0.0` as the primary graph-based
   identify/estimate method in the Foundry causal catalog.
2. Use `GraphCausalData` as the source-of-truth input contract for:
   `data`, `column_names`, `treatment`, `outcome`, and optional graph metadata.
3. Apply graceful degradation if DoWhy is not available at runtime:
   method returns a failure `CausalEffectReport` with explicit `status_reason`,
   but registration and pipeline execution remain functional.
4. Pin DoWhy dependency range to `dowhy>=0.11,<0.13` to reduce API-break risk during Phase 2.

## Consequences
### Positive
- Enables end-to-end graph-based causal identify/estimate in Scientist workflows.
- Keeps runtime stable in environments without optional causal dependencies.
- Adds explicit IR fields (`identified_estimand`, `estimand_type`, `graph_ref`) for lineage and diagnostics.

### Negative
- Introduces dependency-surface management burden for DoWhy version changes.
- Cross-version CI must keep optional dependency behavior verified (available and unavailable paths).

## Compatibility Notes
- New `CausalEffectReport` fields are optional and schema-compatible.
- Existing causal methods and existing report consumers remain backward-compatible.
