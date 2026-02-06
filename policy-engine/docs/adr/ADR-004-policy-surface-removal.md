# ADR-004: Trinity-Only IR Runtime

- Status: Completed
- Date: 2026-02-06
- Extends: `0003-ir-v1-deprecate-remove`

## Context

Legacy surface IR support had already been disabled in runtime execution paths, but dead code, tests, and docs still referenced it. This increased maintenance cost and created ambiguity around the canonical IR.

## Decision

Runtime and test code are now Trinity-only. Legacy surface contracts and compilation entrypoints are removed from active code paths.

## Implemented Changes

1. Removed surface compile branch from Foundry compile resolution.
2. Removed `PolicySurfaceIRRef`; generalized `ProgramGraph`/`LoweredIR` references to `ArtifactRef`.
3. Removed legacy loader options and surface-shape detection from runtime loaders.
4. Removed legacy migration helpers from runtime migration modules.
5. Removed `polisyos.foundry.compiler` legacy module.
6. Deleted legacy migration CLI (`tools/migrate_ir.py`) and archived one-off conversion utility.
7. Updated tests and tools to use `TrinityBundle` and `CompileRequest(input_kind="trinity")`.
8. Added migration guide for downstream integrations.

## Consequences

- Single canonical IR flow: `TrinityBundle -> linker -> compile -> execute`.
- Reduced API surface and lower cognitive load for maintainers.
- External integrations must migrate off legacy surface payloads.
