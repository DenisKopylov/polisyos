# ADR-RSR-0142: LibCST Module Move Codemod

## Status

Accepted

## Date

2026-05-03

## Context

Phase 5/6 will move many modules. Hand-editing imports and shims is too brittle
for a decomposition that must preserve public FQNs and formatting.

## Decision

1. The reusable codemod is `tools/devx/refactor/move_module.py`.
2. The codemod uses LibCST for Python import rewrites so formatting and comments
   are preserved.
3. It supports `--dry-run`, physical `git mv`, targeted shim generation, import
   rewrites in `src/`, `tests/`, and `tools/`, and text rewrites in
   `packages/runtime-api-client/scripts/`.
4. Generated shim records are appended to `architecture/shims.toml` with
   `type = "python_reexport"`.
5. Star-import re-export shims are forbidden by ADR-RSR-0144.

## Consequences

Module moves become repeatable and reviewable. Dry-run output is the required
review artifact before each Phase 5/6 move batch.

## Related Decisions

- ADR-RSR-0144 JAX/Pydantic Registrations and Re-export Shim Shape.
