# Methods Catalog (`polisyos.foundry.methods.catalog`)

`methods/catalog` - canonical tree of Foundry V2 method implementations grouped
by domain family and registered into the shared `MethodRegistry`.

## Role in System

- **Depends on:** `polisyos.foundry.methods`
- **Used by:** Foundry method execution, Scientist orchestration, registry bootstraps
- Keeps domain-specific implementations in one place while preserving flat public imports.

## Key Concepts

- **Domain families** - causal, econometrics, optimization, simulation, survey, ml, and more.
- **Bootstrap registration** - each family exposes `ensure_*_methods_registered()`.
- **Catalog snapshots** - `snapshot.py` captures immutable registry inventories for docs, CI, and release evidence.
- **Flat public surface** - high-level packages remain importable without deep legacy shims.
- **Causal is largest** - discovery, estimation, transportability, policy learning and strategic response families live there.
- **Optional dependencies** - families can degrade gracefully when scientific stacks are unavailable.
- **Dependency authority** - tracked Foundry registries bind the N8 root,
  extras, lock, resolver, digest domains, and source-freeze predicate. The
  production boundary currently returns the typed
  `owner_enforced_runtime_subtree_cutoff_not_established` refusal before any
  environment sync or candidate projection.
- **Dependency discriminant** - `resolve_dependency_discriminant()` recomputes
  the complete selected lock closure from tracked dependency bytes without
  reading production data. `diagnose_dependency_environment()` compares
  ephemeral installed coordinates generically and is non-decisive. Ambient
  observations carry name/version only and cannot establish source identity;
  selected-artifact comparison requires a content-bound Foundry environment
  receipt reconciled against its retained marker bytes and remains candidate
  evidence.

## Public API

| Type/Function                              | Description                               |
| ------------------------------------------ | ----------------------------------------- |
| `ensure_all_methods_registered()`          | Registers every available catalog family. |
| `ensure_causal_methods_registered()`       | Registers causal methods into a registry. |
| `ensure_econometric_methods_registered()`  | Registers econometrics methods.           |
| `ensure_optimization_methods_registered()` | Registers optimization methods.           |
| `ensure_ml_methods_registered()`           | Registers ml methods.                     |
| `ensure_simulation_methods_registered()`   | Registers simulation methods.             |
| `MethodCatalogDependencyAuthorityRequest`  | Supplies only purpose, source freeze, and absolute request coordinates. |
| `build_method_catalog_runtime_identity()`  | Resolves the negative-only Foundry dependency authority. |
| `build_method_catalog_provenance_manifest()` | Resolves the same authority before candidate provenance. |

→ Full reference: [docs/reference/foundry/index.md](../../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-09-02
- The Foundry dependency-only reducer and read-only diagnostic are implemented;
  the shared persisted GY-DEF22 companion and its orchestration bridge remain
  `producer_missing` until the N8 producer is wired.
- Refusal persistence is `not_established` because the owner-resolved,
  request-bound receipt store is `absent/unallocated`.
- Runtime-subtree cutoff authority is `absent/unallocated`; two matching walks
  would remain candidate observations rather than an authority-grade cutoff.
