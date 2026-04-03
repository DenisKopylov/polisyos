# Foundry Methods Catalog
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

This page documents the Phase 2 causal-method updates that are part of the
public or semi-public Foundry surface.

## When to use this surface

- Use the catalog facades when a planner, authoring flow, or CLI needs to discover what methods exist without importing every backend eagerly.
- Use `rank_method_catalog_entries()` and the `suggest_*` helpers when a workflow needs to choose a runnable method, propose a substitute, or bridge two incompatible signatures.
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
| `suggest_alternative_methods()` | A chosen method is unavailable or not runnable | workflow recovery, recommendation UI |
| `suggest_adapter_methods()` | Two methods do not link directly | linker-assisted DAG repair |
| `authoring_catalog_payload()` | You need a compact family summary instead of the full snapshot | prompt construction, docs authoring |

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
