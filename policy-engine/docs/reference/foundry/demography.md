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

Freshness: 2026-10-12  
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
| Historical shim     | `polisyos.ukraine_data.demography`                | Removed in Phase 8; use `polisyos.data_forge.read_api.ukraine` for read APIs                                                       |

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

The sparse hard-margin solver first finds one fractional feasible flow and uses its residual alternating cycles to identify which positive-prior edges can carry mass under the same row and state totals. It removes only edges proved forced to zero before the existing entropic IPF iterations. Margins, prior-based objective values, structural-zero checks, and the configured convergence tolerance remain unchanged. If floating-point residuals do not establish the support safely, the solver keeps the original support and preserves the existing convergence refusal.

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
  `tests/unit/foundry/methods/catalog/survey/test_demographic_consistency.py`

- deterministic/integerized aged sample materialization:
  `tests/unit/foundry/methods/catalog/simulation/test_demography.py`

- read surface and compatibility shim:
  `tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py`

- sparse-flow performance gate:
  `tests/unit/foundry/benchmarks/test_demographic_consistency_perf.py`

## Current Boundaries

- Household formation logic is not part of this surface yet; this is a
  person-level aging engine with donor-based entrants.

- The soft-margin layer is heuristic and subordinate to the exact hard
  demographic constraints.

- The broader Data Forge package is still being migrated; the read surface here
  is intentionally small and stable while the rest of the consolidation
  proceeds.


## Candidate inventory source requests

The experimental polisyos.data_forge.read_api.ukraine facade exports
DemographySourceRequest, InventorySourceRequest, and HistoricalLayoutRequest.
A caller that needs individual role projections can verify the inventory stage
once, construct one request, and pass that same request to the public sibling
readers:

~~~python
from polisyos.data_forge.read_api.ukraine import (
    InventorySourceRequest,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
    load_verified_stage_artifacts,
)

receipt = load_verified_stage_artifacts(
    manifest_path,
    store=store,
    allowed_root=build_root,
    expected_stage="demography_source_inventory",
    required_outputs=("inventory.json",),
)
source = InventorySourceRequest(kind="inventory", stage_receipt=receipt, store=store)
targets = load_reconciled_targets(source=source)
priors = load_transition_priors(source=source)
donors = load_donor_pool(source=source)
~~~

The helper load_demography_candidate_artifacts performs the same verified
inventory read for the aggregate consumer. These inputs stay candidate-only:
the inventory digest and role checks recompute byte membership and declared
cross-member equalities, while source ownership, semantic completeness, units,
and currentness remain not established.

Historical filesystem inputs retain legacy_limited behavior. If and only if
the selected historical layout entirely omits entrant_state_totals, the
reader preserves the previous zero-shaped compatibility projection and records
that its measurement status is not_established. This is not a measured zero.
A present malformed value still refuses, and candidate inventory requests
continue to refuse an absent entrant field. Neither historical compatibility
nor the inventory receipt supplies units, issuer authority, or currentness.


## Public type and migration compatibility

The public experimental read API now represents ``UkraineDemographyArtifacts``
as contract ``data_forge.ukraine.demography.artifacts.v2``. Version 2 requires
``source_evidence``; the supported readers populate it from the selected source.
Callers that directly construct this DTO or validate a v1 payload must migrate to
the v2 contract. Missing evidence is not replaced with a default.

``load_reconciled_targets``, ``load_transition_priors``, and ``load_donor_pool``
return ``DemographyRoleProjection``, a typed ``Mapping[str, object]`` with an
``evidence`` attribute. Existing mapping-style reads continue to work. Code that
requires ``type(result) is dict`` or mutates the reader result must adapt; use
``dict(result)`` when a mutable copy is needed. Projection equality follows the mapping payload and source evidence remains
available through .evidence; results remain read-only. Historical selection
errors retain their prior categories: ValueError for ambiguous or partial
layouts, FileNotFoundError for a missing explicitly selected layout, and the
native JSON decoder error for malformed selected content. A standalone donor read
returns an empty mapping only when no known demographic members are present or a
selected complete layout omits donor; absence intent remains not established. The
reader call signatures and historical path inputs remain supported.
