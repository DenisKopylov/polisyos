# Methods (`polisyos.foundry.methods`)

`methods` - declarative method subsystem for typed ABI, registry/discovery, DAG
composition, specialization and backend dispatch in Foundry.

## Role in System

- **Depends on:** `polisyos.core`, `polisyos.ir`, backend-specific scientific stacks
- **Used by:** Foundry execution graph and Scientist method-oriented nodes
- Provides the public method surface for reusable computations independent of Trinity mechanisms.

## Key Concepts

- **Typed ABI** - `FoundryMethod`, `MethodSignature`, `MethodMetadata`, slots and parameters.
- **Registry and discovery** - `MethodRegistry` plus file-system/entry-point discovery.
- **Composition** - DAG composition and linker-based slot compatibility checks.
- **Resolution** - version policies and compatibility rules live in `resolution.py`.
- **Backends** - method execution can route to JAX, NumPy or solver-style backends.
- **Catalog snapshot** - registry state can be captured and persisted for reproducibility.

## Public API

| Type/Function | Description |
|---|---|
| `FoundryMethod` | Base protocol for typed methods. |
| `MethodRegistry` | Thread-safe registry with version resolution. |
| `MethodComposer` | Builds method DAGs and ordered execution chains. |
| `SlotLinker` | Checks and links slot compatibility. |
| `MethodDispatcher` | Executes methods across supported backends. |
| `ensure_all_methods_registered()` | Boots all catalog families into a registry. |
| `build_method_catalog_snapshot()` | Captures a registry snapshot for reproducibility. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 271 Python files
- Exports: 139
