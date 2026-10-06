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
- `causal_engine/`, `id_engine/`, and `interference/` are split packages. Their
  public entrypoints remain package imports; implementation helpers belong to
  the corresponding leaf modules. `constraint_discovery.py` and
  `invariance_tests.py` remain modules tracked in `architecture/module_size_budget.toml`.
- Method modules are grouped by concept: identification, estimation,
  diagnostics, discovery, transportability, fairness, policy learning,
  recourse, strategic response, and space-time DSCM.
- Optional backend adapters such as `_econml_adapter.py` and
  `_sklearn_compat.py` must degrade by explicit capability contract.

## Extension Points

### Causal engine and interference compatibility surface (LA-020)

The existing `causal_engine` package explicitly exports `CausalEngine` and
`DataReadinessBlockedError`. The engine class is defined in `causal_engine.api`;
the exception belongs to `_causal_engine_contracts`. Direct and star imports
keep those object identities and serialized module addresses.

The `interference` package explicitly exports `BipartiteInterferenceEstimator`,
`NetworkAIPWEstimator`, `PartialInterferenceEstimator`,
`SpatialInterferenceEstimator`, `InterferenceAugmentedGraph`,
`InterferenceIdentificationResult`, `build_block_stratified_network_causal_data`,
`build_interference_topology_contracts`, and `identify_interference_effect`.
Estimator implementations belong to `interference.api`, graph/result contracts
to `_interference_contracts`, and identification helpers to
`interference.identification`.

Historical test callers still use `causal_engine._make_dummy_identification_result`
and patch `causal_engine.mz_id_algorithm`, `id_with_oracle_fallback`,
`id_star_algorithm`, and `idc_star_algorithm`. These bindings remain addressable
outside `__all__`; the identification mixin consumes the patch targets at runtime.
The interference facade similarly retains `_ReductionErrorBoundPlan`,
`_SimplicialSupportGate`, and `_TopologyCertificatePlan` for existing test callers.
New internal tests should import helpers from their leaf owners. Retiring these
compatibility names requires an API-owner decision and a consumer migration;
adding a service import to a leaf does not extend the package API.

The measured compatibility window retains these existing package bindings;
this continuation retires no public or historical patch target. Ordinary
internal helper callers use `causal_engine.artifacts`, while dedicated ABI
controls still exercise the historical facade aliases. The repository public
surface manifest determines which broader entrypoints are `public_stable`;
retained test helpers are not promoted to that classification. A future removal
requires the existing owner/deprecation process and its supported caller basis.

Use qualified package imports and canonical owner FQNs for loader/config/docs
consumers. The former `id_engine.py`, `causal_engine.py`, and `interference.py`
sibling files were already absent at the E02 base; no filename shim is supplied.
`find_spec` and its normal Python loader resolve the nonempty packages. A
`runpy`/`spec_from_file_location` client opening a retired filename receives the
normal missing-file error and must migrate its explicit configuration. These
libraries do not declare command-line `__main__` entrypoints. Runtime method
discovery and third-party plugin loading retain their separate maintained
contracts; a computed import AST candidate is not evidence that such a client
actually invoked this facade. Wheel/sdist tests must run outside the checkout
and bind archive, installed resource and canonical-object identities.

The native `test_api_01.py` checks imports, explicit exports, incidental names,
and reload cleanup. `test_facade_consumers.py` exercises a real Scientist
identification consumer, engine/result serialization, supported patch execution
and restoration, leaf FQNs, and runtime documentation generation. These are
bounded ABI witnesses, not DoWhy/EconML backend or real-data validity receipts.

### Method registration

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

## RDD Runtime Support Boundary

The runtime `RegressionDiscontinuity` method currently supports the ordinary
uncorrected local-polynomial estimator. Its omitted `bias_correction` value is
therefore equivalent to the explicit `False` profile and is reported as such
in `method_params`.

An explicit `bias_correction=True` request is a typed non-success until a
validated RBC backend is available. The method does not relabel the ordinary
fit as robust bias corrected, and a quadratic local fit is not an RBC
implementation. The refusal keeps the missing `rdrobust` capability visible;
it does not block the supported uncorrected estimator.

Local WLS uses vector weighting and a small Gram matrix rather than materializing
an observation-sized diagonal matrix. This preserves the existing residual
covariance convention and point/standard-error semantics while keeping the
fixed-order fit linear in the number of observations. The separate causal
statistical-validity benchmark contract must not be read as evidence that the
runtime default provides RBC or finite-sample coverage.

## Current State

- Last updated: 2026-05-06
- Files: 98 Python files
- Exports: 164
