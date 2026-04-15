# Foundry Methods Catalog
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

This page documents the Phase 2 causal-method updates that are part of the
public or semi-public Foundry surface.

## When to use this surface

- Use the catalog facades when a planner, authoring flow, or CLI needs to discover what methods exist without importing every backend eagerly.
- Use `rank_method_catalog_entries()` and the `suggest_*` helpers when a workflow needs to choose a runnable method, propose a substitute, or bridge two incompatible signatures.
- Use `advise_methods()` when the workflow needs one code-level answer to “which methods fit this problem?” together with ranked payload rows and a filtered capability matrix.
- Use `link_methods()` and `check_linkable()` before materializing a DAG edge so compatibility failures happen at planning time rather than deep inside execution.
- Use `bootstrap_method_registry_from_components()` when method providers arrive through the component registry instead of direct imports.

## Architecture Layers

| Layer | Contract | Responsibility |
|-------|----------|----------------|
| Method protocol | `FoundryMethod`, `MethodSignature`, `MethodMetadata` | Declares slots, parameters, backend, determinism tier, and use/not-use guidance |
| Backend runner | `MethodRunner`, `MethodDispatcher`, `MethodResult` | Executes one protocol-compliant class on JAX/NumPy/solver/Bayesian runtimes and records timing/reproducibility |
| Specialization/cache | `Specialization`, `BackendSpec`, `CompilationCache`, `RegistryPersistenceLayer` | Reuses compiled variants for the same static params, shapes, and backend fingerprint; caches registry metadata separately from compiled kernels |
| Evidence/artifacts | `MethodArtifact`, `ChainArtifact`, `ExecutionEvidence`, `store_*()` | Persists immutable receipts linking source/signature hashes, specialization keys, chain structure, input/output state refs, RNG, and device info |

## Method Families

The catalog families below expose estimators with short method-level
`when_to_use`, `when_not_to_use`, and assumption metadata. The package facades
register methods lazily so docs/tooling can inspect namespace structure without
constructing every backend dependency eagerly.

## High-Signal Entry Points

| API | Use it when | Main consumer |
|-----|-------------|---------------|
| `ensure_*_methods_registered()` | A registry needs one family loaded lazily | CLI, docs, registry boot, snapshots |
| `rank_method_catalog_entries()` | You need an ordered shortlist from catalog metadata | planners, prompt payloads, authoring tools |
| `advise_methods()` | You need a full machine-readable advisor answer instead of only a ranked list | planners, docs, CLIs |
| `suggest_alternative_methods()` | A chosen method is unavailable or not runnable | workflow recovery, recommendation UI |
| `suggest_adapter_methods()` | Two methods do not link directly | linker-assisted DAG repair |
| `build_method_capability_matrix()` | You need a machine-readable capability/export view over the catalog | docs, CI, release gates |
| `authoring_catalog_payload()` | You need a compact family summary instead of the full snapshot | prompt construction, docs authoring |

## Truthfulness Rubric

Foundry catalog rows now carry a `truthfulness_tier` so docs and planners do not present every method as the same implementation depth.

| Tier | Meaning | Presentation rule |
|------|---------|-------------------|
| `heuristic_baseline` | Fast proxy, heuristic, or baseline implementation | Treat as a baseline, not as equivalent depth to production estimators or trainable systems |
| `structural_scoring` | Structural, diagnostic, identification, or scoring-oriented logic | Use for screening, planning, or diagnostics unless downstream evidence says otherwise |
| `production_method` | Production-oriented estimator/mechanism surface with explicit runtime/dependency posture | Safe default for ordinary planning and execution flows |
| `frontier_trainable` | Trainable or frontier implementation with stronger runtime/dependency assumptions | Present with higher operational cost/risk and do not collapse it into baselines in UI/docs |

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
result = advise_methods(snapshot, query)
rows = build_method_capability_matrix(snapshot, runnable_only=True)
```

## Namespaced Methods

| Method surface | Namespace / version | Role |
|----------------|---------------------|------|
| Measurement error | `causal.measurement_error` | Measurement-error metadata propagation and proxy-boundary diagnostics |
| Strategic response | `causal.strategic` v`1.0.0` | Strategic closure, equilibrium enumeration, fallback handling |
| Policy learning | `causal.targeting` v`1.0.0` | Optimal policy learning and policy-tree extraction |

## Reference

### ABI and Backend Contracts

::: polisyos.foundry.methods

::: polisyos.foundry.methods.backends.protocol

::: polisyos.foundry.methods.backends.dispatch

::: polisyos.foundry.methods.specialization

::: polisyos.foundry.methods.cache

::: polisyos.foundry.methods.artifacts_parts

::: polisyos.foundry.methods.catalog_snapshot

### Family Facades

::: polisyos.foundry.methods.catalog

::: polisyos.foundry.methods.catalog.causal

::: polisyos.foundry.methods.catalog.econometrics

::: polisyos.foundry.methods.catalog.ml

::: polisyos.foundry.methods.catalog.bayesian

::: polisyos.foundry.methods.catalog.network

::: polisyos.foundry.methods.catalog.simulation

::: polisyos.foundry.methods.catalog.causal.measurement_error

::: polisyos.foundry.methods.catalog.causal.strategic

::: polisyos.foundry.methods.catalog.causal.policy_learning
