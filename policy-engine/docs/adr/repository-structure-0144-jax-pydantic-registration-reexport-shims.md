# ADR-RSR-0144: JAX/Pydantic Registrations and Re-export Shim Shape

## Status

Accepted

## Date

2026-05-03

## Context

JAX pytree registrations, Pydantic model rebuilds, discriminators, and broad
re-export shims can all introduce import-time side effects. Decomposition shims
must preserve compatibility without importing more than they need.

## Decision

1. Phase 3A inventories top-level registration patterns in planned move files.
2. Decomposition shims must use targeted imports of exported names.
3. `from .new import *` is forbidden in `type = "python_reexport"` shims.
4. `reexport_shim_shape_gate` statically parses shim files registered in
   `architecture/shims.toml` and fails on star imports.
5. Files with top-level registrations must either become lazy-registration
   modules or be shimmed with targeted imports only.

## Consequences

Compatibility shims no longer hide broad import-time side effects, and Phase 5/6
can preserve FQNs without accidentally widening module initialization.

## Related Decisions

- ADR-RSR-0142 LibCST Module Move Codemod.
