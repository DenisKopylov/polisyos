# Uncertainty (`polisyos.foundry.uncertainty`)

`uncertainty` - propagation layer for mapping input uncertainty envelopes to
output metric uncertainty in Foundry simulations.

## Role in System

- **Depends on:** `polisyos.ir.analytics.uncertainty`, JAX
- **Used by:** Scientist uncertainty propagation nodes and calibration post-fit analysis
- Sits after execution and before downstream reporting/aggregation.

## Key Concepts

- **Dispatcher** - selects delta, Monte Carlo or auto propagation strategy.
- **Delta method** - Jacobian-based propagation for differentiable simulations.
- **Monte Carlo** - sampling-based propagation when analytic assumptions fail.
- **Aggregation** - envelope merging for multi-strategy or multi-run outputs.
- **Config-driven fallback** - strategy choice is explicit and inspectable.

## Public API

| Type/Function | Description |
|---|---|
| `PropagationConfig` | Configures confidence and propagation strategy. |
| `PropagationDispatcher` | Selects and executes propagation strategies. |
| `PropagationResult` | Output record for a propagated metric envelope. |
| `PropagationStrategy` | Protocol for propagation implementations. |
| `QuasiMCSampler` | Quasi-Monte-Carlo sampler for sampling-based propagation. |
| `aggregate_envelopes()` | Combines multiple envelopes into one. |
| `compute_first_order_indices()` | Sensitivity helper for variance attribution. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 11 Python files
- Exports: 9
