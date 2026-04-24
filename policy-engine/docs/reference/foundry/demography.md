# Foundry Demography

Related reference pages: [Calibration](calibration.md), [Agent Sim](agent-sim.md), [Methods Catalog](methods-catalog.md).

`T11.6` adds a deterministic-first static-aging surface for microsimulation with
demographic consistency. The implementation is deliberately split across two
layers:

- `survey.demography.*` solves the accounting problem exactly on sparse
  record-to-state flows.

- `simulation.demography.static_aging` turns transition priors, donor pools,
  and macro targets into a materialized aged sample plus optional integerized
  draws.

Freshness: 2026-04-21  
Owner: `@foundry-owners`  
Source of truth: `src/polisyos/foundry/methods/catalog/survey/demographic_consistency.py`,
`src/polisyos/foundry/methods/catalog/simulation/demography.py`,
`src/polisyos/data_forge/read_api/ukraine.py`,
and the linked tests below.

## What Is Implemented

| Layer               | Module                                            | Role                                                                                                                              |
| ------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Deterministic core  | `survey.demography.demographic_consistency@1.0.0` | Exact hard balancing for survivor flows with exits, entrants, structural zeros, and target reconciliation                         |
| Canonical estimator | `survey.demography.cceb@1.0.0`                    | Alias for the cohort-component plus entropic-balancing deterministic core                                                         |
| Additional margins  | `survey.demography.*` soft-constraint inputs      | Heuristic soft-margin fitting for auxiliary cross-tabs such as health or SES after exact demographic balancing                    |
| Orchestration       | `simulation.demography.static_aging@1.0.0`        | Builds sparse candidate flows from origin-state priors, scales donor pools, materializes aged sample, and emits integerized draws |
| Data access         | `polisyos.data_forge.read_api.ukraine`            | Runtime-safe loading of reconciled targets, transition priors, donor pools, and Foundry-ready state composition                   |
| Compatibility shim  | `polisyos.ukraine_data.demography`                | Temporary bridge until the wider Data Forge migration is complete                                                                 |

## Deterministic Contract

The canonical deterministic output is the calibrated flow solution:

- `calibrated_flows`
- `candidate_record_index`
- `candidate_state_index`
- `achieved_state_totals`
- `exit_weights`
- `entrant_state_totals`
- diagnostics for mass balance, convergence, ESS, and structural-zero
  violations

This is the artifact to use for scoring, reproducible CI, and audit trails.

## Stochastic Contract

`simulation.demography.static_aging@1.0.0` accepts `mode="integerized"` or
`mode="stochastic"` and derives discrete draws from the deterministic solution.

- `integerized` emits one controlled integerization draw.
- `stochastic` emits `n_draws` draws.

These draws are downstream approximations. They are not the source of truth for
matching external demographic margins.

## Data Inputs

The runtime-safe Data Forge read surface loads three artifact families:

- reconciled targets: `targets.json`
- transition priors: `transition_priors.json`
- donor pool: `donor_pool.json`

The current loader accepts either:

- `<root>/demography/targets.json` style directories
- flat compatibility names such as `<root>/demography_targets.json`

## Minimal Usage

```python
from polisyos.data_forge.read_api.ukraine import (
    build_static_aging_state,
    load_demography_artifacts,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.catalog import ensure_all_methods_registered

artifacts = load_demography_artifacts("/path/to/demography_bundle")
state = build_static_aging_state(
    base_weights=[1.5, 2.0, 0.8],
    origin_state_index=[0, 1, 1],
    artifacts=artifacts,
)

registry = MethodRegistry.get_instance()
ensure_all_methods_registered(registry)
method = registry.get("simulation.demography.static_aging@1.0.0")
result = method.pure_step(state, {"mode": "deterministic"})
```

## Validation Anchors

- exact accounting, entrants/exits, soft margins:
  `tests/foundry/methods/catalog/survey/test_demographic_consistency.py`

- deterministic/integerized aged sample materialization:
  `tests/foundry/methods/catalog/simulation/test_demography.py`

- read surface and compatibility shim:
  `tests/ukraine_data/test_demography_artifacts.py`

- sparse-flow performance gate:
  `tests/foundry/benchmarks/test_demographic_consistency_perf.py`

## Current Boundaries

- Household formation logic is not part of this surface yet; this is a
  person-level aging engine with donor-based entrants.

- The soft-margin layer is heuristic and subordinate to the exact hard
  demographic constraints.

- The broader Data Forge package is still being migrated; the read surface here
  is intentionally small and stable while the rest of the consolidation
  proceeds.
