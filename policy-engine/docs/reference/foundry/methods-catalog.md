# Foundry Methods Catalog

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

The Foundry method catalog is the typed ABI for reusable scientific
computations. It covers the Phase 2 execution-kernel ABI, Phase 4 capability and
replay metadata, and the Phase 5/6 frontier method surfaces.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/methods/**`, `src/polisyos/foundry/methods/catalog/**`, and generated `MethodCatalogSnapshot` inputs from `src/polisyos/foundry/methods/catalog_snapshot.py`

## When to Use This Surface

- Use catalog facades when a planner, authoring flow, or CLI needs to discover
  methods without eagerly importing every backend dependency.
- Use `rank_method_catalog_entries()` and `advise_methods()` when a workflow
  needs a runnable method recommendation with backend, fidelity, determinism,
  and truthfulness metadata.
- Use `link_methods()` and `check_linkable()` before materializing a DAG edge so
  compatibility failures happen at planning time.
- Use `build_method_capability_matrix()` when docs, CI, or operators need a
  machine-readable view of runnable and blocked methods.
- Use `bootstrap_method_registry_from_components()` when providers arrive
  through the component registry instead of direct imports.

## Generated Inputs

This page is manual, but its inventory claims are grounded in generated
`MethodCatalogSnapshot`, capability-matrix, and operator-evidence payloads.
Regenerate those inputs with the Python APIs that back the CLI:

```bash
uv run python - <<'PY'
from polisyos.foundry.methods.catalog_snapshot import (
    build_method_capability_matrix,
    build_method_catalog_snapshot,
    build_method_operator_evidence,
)

snapshot = build_method_catalog_snapshot(run_id="docs")
print(snapshot.snapshot_id)
print(len(build_method_capability_matrix(snapshot, runnable_only=True)))
print(build_method_operator_evidence(snapshot, runnable_only=True)["runnable_count"])
PY
```

The operator CLI mirrors these surfaces through `polisyos-foundry catalog`,
`capabilities`, `evidence`, and `advisor`. For machine-readable automation,
prefer the Python APIs above: current CLI `--json` runs may include registry
bootstrap logs before the JSON document on stdout.

## Architecture Layers

| Layer | Contract | Responsibility |
|---|---|---|
| Method ABI | `FoundryMethod`, `MethodSignature`, `MethodMetadata` | Declares slots, params, backend, determinism tier, and use/not-use guidance. |
| Registry/discovery | `MethodRegistry`, family `ensure_*_methods_registered()` functions | Loads methods lazily and keeps version resolution explicit. |
| Backend dispatch | `MethodRunner`, `MethodDispatcher`, `MethodResult` | Executes one protocol-compliant method on JAX, NumPy, solver, Ray, or Bayesian-style runtimes. |
| Specialization/cache | `Specialization`, `BackendSpec`, `CompilationCache` | Reuses compiled variants for static params, shapes, and backend fingerprint. |
| Evidence/artifacts | `MethodArtifact`, `ChainArtifact`, `ExecutionEvidence` | Persists immutable receipts linking source/signature hashes, chain structure, RNG, and device metadata. |

## High-Signal Entry Points

| API | Use it when |
|---|---|
| `ensure_all_methods_registered()` | A registry needs every shipped catalog family loaded. |
| `build_method_catalog_snapshot()` | Release gates, docs, or operators need an immutable registry snapshot. |
| `build_method_capability_matrix()` | A consumer needs runtime applicability and replay metadata. |
| `advise_methods()` | A planner needs a ranked answer to "which methods fit this problem?" |
| `suggest_alternative_methods()` | A selected method is unavailable or not runnable. |
| `suggest_adapter_methods()` | Two methods do not link directly. |
| `authoring_catalog_payload()` | Prompt or docs generation needs a compact family summary. |

## Truthfulness Tiers

Catalog rows carry `truthfulness_tier` so docs and planners do not present every
method as the same implementation depth.

| Tier | Meaning | Presentation rule |
|---|---|---|
| `heuristic_baseline` | Fast proxy, heuristic, or baseline implementation. | Present as a baseline, not a production estimator. |
| `structural_scoring` | Structural, diagnostic, identification, or scoring logic. | Use for screening, planning, or diagnostics. |
| `production_method` | Production-oriented estimator/mechanism surface with explicit runtime posture. | Safe default for ordinary planning and execution flows. |
| `frontier_trainable` | Trainable or frontier method with stronger dependency/runtime assumptions. | Present with operational cost and risk. |

## Advisor Example

```python
from polisyos.foundry.methods import (
    DataCharacteristics,
    MethodAdvisorQuery,
    MethodSelectionCriteria,
    advise_methods,
    build_method_capability_matrix,
    build_method_catalog_snapshot,
)

snapshot = build_method_catalog_snapshot(run_id="R_docs")
query = MethodAdvisorQuery(
    criteria=MethodSelectionCriteria(
        preferred_family="causal.treatment_effects",
        required_data_modalities=("cross-section",),
        minimum_fidelity_tier="high",
    ),
    data=DataCharacteristics(n_obs=10000, has_instrument=False),
    runtime_budget_ms=250.0,
    limit=5,
)
answer = advise_methods(snapshot, query)
rows = build_method_capability_matrix(snapshot, runnable_only=True)
```

## Representative Families

This table is intentionally high-signal, not exhaustive. For the full current
inventory, use `build_method_catalog_snapshot()` or the `polisyos-foundry`
catalog/capabilities surfaces above.

| Family | Primary namespaces | Notes |
|---|---|---|
| Causal | `causal.*` | Identification, estimation, bounds, sensitivity, DTR, transport, strategic response, frontier causal methods. |
| Bayesian/UQ | `bayesian.*`, `validation.*`, `sensitivity.*` | Current shipped methods plus research-gated posterior-sampling roadmap. |
| ML | `ml.*` | Classical and frontier nuisance, representation, survival, clustering, and transformer-style methods. |
| Policy | `policy.*` | Welfare, MCDA, fiscal/macro/public-finance frontier surfaces. |
| Distributional | `distributional.*` | Inequality, poverty, mobility, and distributional-effect support. |
| Optimization | `optimization.*` | LP/MILP/convex/sequential/multiobjective and game-theory surfaces. |

## Evidence Links

- Selection advisor:
  `tests/foundry/methods/test_selection_advisor.py`
- Catalog snapshot:
  `tests/foundry/test_catalog_snapshot.py`
- Backend determinism:
  `tests/foundry/methods/backends/test_backend_determinism.py`
- Cross-backend consistency:
  `tests/foundry/methods/test_cross_backend_consistency.py`
- Causal estimator protocol:
  [`docs/adr/0018-causal-estimator-protocol.md`](../../adr/0018-causal-estimator-protocol.md)

## Reference

### ABI and Backend Contracts

::: polisyos.foundry.methods

::: polisyos.foundry.methods.backends.protocol

::: polisyos.foundry.methods.backends.dispatch

::: polisyos.foundry.methods.specialization

::: polisyos.foundry.methods.cache

::: polisyos.foundry.methods.artifacts

::: polisyos.foundry.methods.catalog_snapshot

### Family Facades

::: polisyos.foundry.methods.catalog

::: polisyos.foundry.methods.catalog.causal

::: polisyos.foundry.methods.catalog.econometrics

::: polisyos.foundry.methods.catalog.ml

::: polisyos.foundry.methods.catalog.bayesian

::: polisyos.foundry.methods.catalog.network

::: polisyos.foundry.methods.catalog.optimization

::: polisyos.foundry.methods.catalog.policy
