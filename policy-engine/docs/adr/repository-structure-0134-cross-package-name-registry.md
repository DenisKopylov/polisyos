# ADR-RSR-0134: Cross-Package Shared Name Registry

## Status

Proposed

## Date

2026-05-03

## Context

Directory names such as `governance`, `contracts`, `runtime`, `validation`,
and `methods` repeat across top-level packages without a machine-readable
reason for whether they are valid bounded contexts or accidental collisions.

## Decision

1. Declare allowed shared directory names in `architecture/name_registry.toml`.
2. Require each shared name to state allowed packages, semantic axis,
   disambiguation rule, owner, and target phase.
3. Require unresolved repeated names to appear in `[[rename_backlog]]` with
   owner, target phase, sunset, action, packages, and locations.
4. Treat new unregistered collisions as report-only in Phase 0 and fail-closed
   after Phase 1C.
5. Include top-level package roots in the collision inventory so an inner
   package directory such as `foundry/runtime` is checked against the canonical
   top-level `runtime` package.

## Consequences

Repeated names are still allowed when they are intentional. Ambiguous names get
renamed or assigned to a later implementation phase.

## Concrete Impact

- Contract: `architecture/name_registry.toml`.
- Gate: `name_collision_gate`.
- Baseline: `repeated_directory_names.json`.
- Owner: `team-architecture`.
- Target phase: `1C`.
- Rollback: remove or restore a `shared_name` entry with the associated move
  backlog item.

## Phase 1C Outcome

Phase 1C populates `architecture/name_registry.toml` with bounded-context
entries for the accepted shared names and backlog entries for `runtime`,
`discovery`, `calibration`, `core` under `synthetic_world`, and the
`foundry/methods/causal` placeholder. The `name_collision_gate` is now
configured fail-closed for unregistered collisions.

## Related Decisions

- Extends: ADR-0115 Layered Architecture Enforcement.
