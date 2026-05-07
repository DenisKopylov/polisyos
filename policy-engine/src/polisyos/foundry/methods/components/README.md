# Foundry Method Components

`polisyos.foundry.methods.components` owns chain composition, component-backed
method promotion, and input/output materialization helpers.

## Home

- `composer.py` builds method DAGs and compiled chains.
- `bridge.py` promotes component-registry entries into method registrations.
- `consensus.py` owns cross-method consistency and misspecification diagnostics.
- `io.py` materializes bound inputs and dematerializes method outputs.
- `linker.py` resolves slot bindings and compatibility diagnostics.
- `merge_engine.py` owns deterministic state-delta merge helpers.
- `semantic_validator.py` validates cross-method chain semantics.
- `slot_schema.py` owns semantic slot labels and compatibility registration.

## Registration Boundary

`bridge.py` may call `selection.registry.MethodRegistry.register_lazy()` for
component-backed methods. Catalog family registration remains in
`catalog/*/_registry_boot.py`.
