# Causal Catalog (`polisyos.foundry.methods.catalog.causal`)

`methods/catalog/causal` - canonical causal-method family for discovery,
estimation, transportability, policy learning, diagnostics and strategic response.

## Purpose

Use this package when a Foundry or Scientist workflow needs a registered causal
method, estimator, diagnostic, or graph-discovery helper. The package is a
catalog family, not a public subsystem facade: stable access flows through
method registration, the exported causal names in `__init__.py`, and the
broader `polisyos.foundry.methods` facade.

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

## Internal Layout

- `__init__.py` exposes the supported causal family import surface and delegates
  registration to `_registry_boot.py`.
- `protocols.py`, `_common.py`, and helper contract modules define shared input
  and result shapes. Keep cross-method payloads here only when multiple causal
  families consume them.
- `causal_engine.py`, `id_engine.py`, `constraint_discovery.py`,
  `interference.py`, and `invariance_tests.py` are high-complexity modules
  tracked in `architecture/module_size_budget.toml`.
- Method modules are grouped by concept: identification, estimation,
  diagnostics, discovery, transportability, fairness, policy learning,
  recourse, strategic response, and space-time DSCM.
- Optional backend adapters such as `_econml_adapter.py` and
  `_sklearn_compat.py` must degrade by explicit capability contract.

## Extension Points

- External causal methods use the parent `polisyos.foundry_methods` extension
  point declared in
  [architecture/extension_points.toml](../../../../../../architecture/extension_points.toml).
- Builtin causal methods must register through `_registry_boot.py` and provide
  method metadata compatible with the parent registry snapshot and capability
  matrix.
- Authoring rules live in [AUTHORING.md](AUTHORING.md) and the parent
  [catalog/AUTHORING.md](../AUTHORING.md).

## Tests

- Package-local tests live in
  [tests/unit/foundry/methods/catalog/causal/](../../../../../../tests/unit/foundry/methods/catalog/causal/).
- Use characterization tests before splitting high-complexity modules, for
  example `test_id_engine_characterization.py` for symbolic ID behavior.
- Run the parent Foundry Methods suite when changing registration metadata:

```bash
uv run pytest tests/unit/foundry/methods/catalog/causal -q
uv run pytest tests/unit/foundry/methods/test_registry.py tests/unit/foundry/methods/test_testing_infra.py -q
```

## Operability Links

- [Foundry component SLO](../../../../../../ops/components/foundry/slo.yaml)
- [Foundry component runbooks](../../../../../../ops/components/foundry/runbooks.md)
- [Causal engine architecture](../../../../../../docs/reference/foundry/causal-engine-architecture.md)
- [Run causal analysis how-to](../../../../../../docs/how-to/run-causal-analysis.md)
- [Benchmark regression triage runbook](../../../../../../docs/runbooks/benchmark-regression-triage.md)

## Known Shims/Deprecations

- There are no package-local compatibility shims for `catalog/causal` in
  `architecture/shims.toml` as of 2026-05-06.
- High-complexity modules in this family are covered by
  [architecture/module_size_budget.toml](../../../../../../architecture/module_size_budget.toml)
  with owner `team-foundry` and sunset `2026-12-31`.
- Renaming a method ID, moving an import path, or extracting one of the
  budgeted modules requires a deprecation record, compatibility tests, and a
  registry snapshot check before deletion.

## Current State

- Last updated: 2026-05-06
- Files: 98 Python files
- Exports: 164
