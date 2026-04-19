# ADR-0114: Schema Registry and Evolution Rules

## Status
Proposed

## Date
2026-04-18

## Context

Pydantic models and JSON Schema snapshots already exist, but Data Forge
publication boundaries need a versioned schema registry with compatibility
rules, migrations, and frontend/backend codegen drift gates.

## Decision

Create a schema registry for Data Forge and topology contracts:

1. Schemas are identified by `(name, version)`.
2. Evolution rules are `BACKWARD`, `FORWARD`, or `FULL`.
3. Breaking changes require an explicit migration.
4. CI regenerates JSON Schema and generated TypeScript/Python outputs and fails
   on drift.

## Consequences

- Artifact compatibility becomes testable.
- Frontend and runtime contracts can rely on a single source of truth.
- Golden tests can evolve toward structural compatibility checks when byte
  equality is too brittle.

## Related Decisions

- Extends: ADR-0005 (ABI schema gate versioning), ADR-0108 (IR schema catalog).
- Related: ADR-0118 (release train), ADR-0122 (lakehouse snapshots), ADR-0123
  (ArtifactRef governance), ADR-0125 (quality regime).
