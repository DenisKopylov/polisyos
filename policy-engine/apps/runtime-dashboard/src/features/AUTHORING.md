# Dashboard Feature Module Authoring Contract

Owner: `team-frontend`
Applies to: `apps/runtime-dashboard/src/features/**`
Last updated: 2026-05-05

## Purpose

This subtree owns vertical operator workflows. Features compose app shell,
shared UI/charts, and API hooks without redefining those shared boundaries.

## Allowed File Categories

- TypeScript/TSX feature source, feature-local tests, retained stories,
  domain adapters, route shells, hooks, state, and local docs.
- No generated API types, shared primitives, build output, or raw fixture dumps.

## Public/Private Boundary

`index.ts` is the feature public boundary. Cross-feature imports go through
public barrels; `src/shared` and `src/api` must not import from features.

## Naming Convention

Feature directory names are stable workflow nouns. Components use PascalCase.
Hooks use `use*`. Domain adapters stay in `domain/`.

## Test Location

Use colocated `*.test.ts(x)` files or shared dashboard helpers in `src/test/`.
End-to-end journeys live under `e2e/`.

## Fixture/Data Policy

API payload fixtures belong in `src/test/contracts/fixtures/`. Story fixtures
must be small and local to the story.

## Generated File Policy

No generated files are allowed in feature modules. Generated Runtime API types
stay in `src/api/types.ts`.

## Extension Points

New features follow the domain/components/routes/hooks/API-boundary/tests
convention documented in the README and must register routes in app shell.

## Deprecation And Shim Policy

Feature route, workspace, and persisted-state renames require aliases or
migration notes until consumers have moved.
