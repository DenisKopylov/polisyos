# Causal Catalog (`polisyos.foundry.methods.catalog.causal`)

`methods/catalog/causal` - canonical causal-method family for discovery,
estimation, transportability, policy learning, diagnostics and strategic response.

## Role in System

- **Depends on:** `polisyos.foundry.methods`, `polisyos.ir.analytics.causal`
- **Used by:** Foundry method execution, Scientist causal nodes and policy-analysis workflows
- This is the largest method family in the catalog and the main home for causal research/runtime bridges.

## Key Concepts

- **Estimation families** - DiD, RDD, synthetic control, SCM, AIPW, TMLE and related estimators.
- **Discovery and identification** - constraint discovery, DAGMA, query validation and graph reconciliation.
- **Transportability** - transport checks, symbolic identification and parameter transfer helpers.
- **Strategic response** - `strategic.py` now models solve/bundle/summary flows for response design.
- **Policy learning** - `policy_learning.py` and adjacent estimators support downstream decisioning.
- **Measurement error** - `measurement_error.py` and adapter layers expand noisy-observation handling.
- **Space-time DSCM** - `space_time_dscm.py` adds field-valued DSCM contracts, operator edges,
  controlled diffusion-reaction simulation, finite-element SPDE g-computation, optional
  continuous-time IPW/DR diagnostics, and mesh/time-step sensitivity reports.
- **Capability contracts** - optional backends degrade by contract instead of silently changing semantics.

## Public API

| Type/Function                        | Description                                             |
| ------------------------------------ | ------------------------------------------------------- |
| `ensure_causal_methods_registered()` | Registers the causal family into a registry.            |
| `register_causal_methods()`          | Returns the canonical list used by the bootstrap.       |
| `CausalEngine`                       | Core engine for causal graph/effect orchestration.      |
| `CausalEstimator`                    | Base protocol for causal estimators.                    |
| `DoWhyIdentifyEstimate`              | Identification-plus-estimation path.                    |
| `DoWhyRefute`                        | Refutation / placebo diagnostics.                       |
| `StrategicSolveResult`               | Result model for strategic response solving.            |
| `solve_strategic_response()`         | Solves the strategic response bundle.                   |
| `build_strategic_response_bundle()`  | Builds the strategic response input bundle.             |
| `OptimalPolicyLearner`               | Learner for policy-selection oriented causal workflows. |
| `CheckTransportability`              | Transportability gate for cross-context use.            |
| `transport_bounds()`                 | Computes transportability bounds.                       |
| `SpaceTimeSPDEGComputation`          | FEM SPDE g-computation for ST-DSCM policy spillovers.   |
| `simulate_reaction_diffusion_response()` | Validation helper for nonlinear reaction-diffusion systems. |

→ Full reference: [docs/reference/foundry/index.md](../../../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-25
- Files: 98 Python files
- Exports: 164
