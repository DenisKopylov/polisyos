# Shared Charts Authoring Contract

Owner: `team-frontend`
Applies to: `apps/runtime-dashboard/src/shared/charts/**`
Last updated: 2026-05-05

## Purpose

This subtree owns reusable, feature-agnostic chart components and chart tokens.

## Allowed File Categories

- TypeScript/TSX chart source, tests, retained stories, tokens, and local docs.
- No API clients, generated types, feature routes, or build artifacts.

## Public/Private Boundary

The public boundary is `index.ts`. Helpers not exported there are private to
shared charts.

## Naming Convention

Use PascalCase for chart components and kebab-free descriptive names for token
files. Stories/tests mirror the component name.

## Test Location

Use colocated `*.test.ts(x)` and `*.stories.tsx` files.

## Fixture/Data Policy

Keep story data tiny and local to the story/test. Larger fixtures belong under
`src/test/`.

## Generated File Policy

No generated files are allowed in shared charts.

## Extension Points

Promote generic chart primitives through `index.ts`; keep feature-specific
views under `src/features/<feature>/components/`.

## Deprecation And Shim Policy

Renames require export aliases or targeted migration notes until consuming
features have moved.
