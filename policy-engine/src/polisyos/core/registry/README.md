# Registry (`polisyos.core.registry`)

`core.registry` collects the in-memory registry primitives and the CAS-backed registry bundle
builders/loaders used by deterministic runtime paths.

## Role in System

- **Depends on:** `core.artifacts` for CAS-backed storage and `core.components` for fragment discovery.
- **Used by:** `foundry`, `scientist`, `runtime`, `governance`, and bootstrap code that needs typed registries.
- **Boundary function:** keeps registry assembly and materialization consistent across the stack.

## Key Concepts

- **Registry primitives** - `BaseRegistry` and `GenericRegistry` provide the in-memory model.
- **Bundle builders** - `build_registry_bundle` and `build_default_registry_bundle` materialize registries into CAS.
- **Fragment composition** - `builder_from_fragments.py` composes bundles from component IR fragments.
- **Bundle loading** - `loader.py` reads the materialized runtime registries back out of CAS.

## Public API

- primitives: `BaseRegistry`, `DuplicateDecision`, `GenericRegistry`, `GenericRegistrySnapshot`
- builders: `build_registry_bundle`, `build_default_registry_bundle`, `build_registry_bundle_from_components`, `FragmentPrecedencePolicy`
- loaders: `load_registry_bundle`, `load_registry_bundle_payload`, `load_registry_bundle_content`, `RegistryBundleContent`

## Current State

- Last updated: 2026-04-03
- The package tree still centers on `base.py`, `generic.py`, `builder.py`, `builder_from_fragments.py`, and `loader.py`.
- Registry bundles remain the handoff layer between component discovery and runtime registries.
