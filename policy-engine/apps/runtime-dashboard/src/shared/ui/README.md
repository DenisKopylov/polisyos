# Shared UI

Owner: `team-frontend`
Last updated: 2026-05-05

## Purpose

`src/shared/ui` owns reusable UI primitives and composed UI patterns that are
independent of any one feature route.

## Public API

Import through package-local barrels in `primitives/`, `compounds/`, or the
specific shared UI family. Feature modules must not treat private helper files
as stable API.

## Internal Layout

| Path | Role |
| --- | --- |
| `primitives/` | Base controls and layout primitives. |
| `compounds/` | Reusable multi-part UI patterns. |
| `patterns/` | Cross-flow reusable interaction patterns. |
| `authored-text/`, `quantity/`, `temporal/`, `trust-view/` | Domain-shaped shared renderers. |
| `tokens/`, `responsive/` | UI tokens and responsive helpers. |

## Extension Points

Add a reusable primitive only when at least two feature surfaces need it or
when the design system explicitly owns the pattern. Feature-specific UI stays
under `src/features/<feature>/components/`.

## Tests

Use colocated Vitest tests for shared UI behavior. Visual and accessibility
journeys live under `e2e/` when the pattern is operator-visible.

## Operability Links

- `docs/brand/ATLAS_DESIGN_SYSTEM.md`
- `docs/compliance/A11Y_CONTRAST.md`
- `docs/reference/frontend/workspace-contract.md`

## Known Shims/Deprecations

Renamed primitives must keep export aliases until feature consumers migrate or
the release note documents the removal.
