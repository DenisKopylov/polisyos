# Methods Catalog (`polisyos.foundry.methods.catalog`)

`methods/catalog` - canonical tree of Foundry V2 method implementations grouped
by domain family and registered into the shared `MethodRegistry`.

## Role in System

- **Depends on:** `polisyos.foundry.methods`
- **Used by:** Foundry method execution, Scientist orchestration, registry bootstraps
- Keeps domain-specific implementations in one place while preserving flat public imports.

## Where to Start

- [mechanism/families.py](mechanism/families.py) is the canonical owner for
  mechanism-family specifications and catalog lookup; the retained
  [../../mechanisms/design.py](../../mechanisms/design.py) path is a direct
  compatibility facade for existing callers.

## Key Concepts

- **Domain families** - causal, econometrics, optimization, simulation, survey, ml, and more.
- **Bootstrap registration** - each family exposes `ensure_*_methods_registered()`.
- **Catalog snapshots** - `snapshot.py` captures immutable registry inventories for docs, CI, and release evidence.
  The ordinary Foundry builtin discovery path binds its existing loader target to
  the public Core `DeclaredBuiltinLoader`, so candidate provenance carries the producer-bound
  name, target, and group in v2. Discovery and catalog admission use the same helper to
  resolve the effective selected spec; the consumer compares the full declaration against
  that source rather than trusting the manifest's claim. The exported `(target, callable)`
  `BUILTIN_LOADER` remains available for compatibility; explicit replacement loaders retain
  their existing callable behavior and v1 provenance shape. Ambient evidence remains quarantined.
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
  source-kind and selected-artifact comparison require a Foundry environment
  receipt whose whole-statement ref is recomputed at every use and whose
  retained marker bytes reconcile. The receipt remains candidate evidence.
  Marker replay fails closed when any variable used by a selected lock
  expression is absent from the supplied mapping, and diagnose binds both its
  tracked data and reducer/digest/tool producer paths to the source freeze.

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

- Sparse demographic balancing computes a fractional feasible flow, then removes only positive-prior edges proven forced to zero by the hard margins before the existing entropic IPF solve. The original priors still define objective and structural-zero diagnostics.

- Last updated: 2026-09-02
- The Foundry dependency-only reducer and read-only diagnostic are implemented;
  the shared persisted GY-DEF22 companion and its orchestration bridge remain
  `producer_missing` until the N8 producer is wired.
- Refusal persistence is `not_established` because the owner-resolved,
  request-bound receipt store is `absent/unallocated`.
- Runtime-subtree cutoff authority is `absent/unallocated`; two matching walks
  would remain candidate observations rather than an authority-grade cutoff.
