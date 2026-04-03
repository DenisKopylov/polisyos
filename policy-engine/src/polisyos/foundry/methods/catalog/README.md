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
- **Flat public surface** - high-level packages remain importable without deep legacy shims.
- **Causal is largest** - discovery, estimation, transportability, policy learning and strategic response families live there.
- **Optional dependencies** - families can degrade gracefully when scientific stacks are unavailable.

## Public API

| Type/Function | Description |
|---|---|
| `ensure_all_methods_registered()` | Registers every available catalog family. |
| `ensure_causal_methods_registered()` | Registers causal methods into a registry. |
| `ensure_econometric_methods_registered()` | Registers econometrics methods. |
| `ensure_optimization_methods_registered()` | Registers optimization methods. |
| `ensure_ml_methods_registered()` | Registers ml methods. |
| `ensure_simulation_methods_registered()` | Registers simulation methods. |

→ Full reference: [docs/reference/foundry/index.md](../../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 197 Python files
- Exports: 17
