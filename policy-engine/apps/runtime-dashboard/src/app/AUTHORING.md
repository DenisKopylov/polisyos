# Runtime Dashboard App Shell Authoring Contract

Owner: `team-frontend`
Applies to: `apps/runtime-dashboard/src/app/**`
Last updated: 2026-05-05

## Purpose

This subtree owns app-level shell composition and cross-feature runtime wiring.

## Allowed File Categories

- TypeScript/TSX shell source, provider/state modules, route metadata, tests,
  and local README/AUTHORING docs.
- No generated API types, feature components, snapshots, or build outputs.

## Public/Private Boundary

Feature modules may consume route registration contracts and hooks exported by
the app shell. Shared UI and API modules must not import app internals.

## Naming Convention

Use PascalCase for React components and camelCase or snake-free descriptive
names for hooks/helpers. Route modules stay under `routes/`.

## Test Location

Use colocated `*.test.ts(x)` files or shared helpers under `src/test/`.

## Fixture/Data Policy

Use `src/test/contracts/fixtures/` for API payloads and `src/test/msw/` for
network mocking. Do not add fixtures under `src/app`.

## Generated File Policy

No generated files are allowed here. Generated API types live in
`src/api/types.ts`.

## Extension Points

Add feature routes through `routes.tsx`, workspace metadata through
`workspaces.ts`, and provider composition through `AppProviders.tsx`.

## Deprecation And Shim Policy

Route aliases and provider migrations require tests and a documented sunset
when user-visible URLs or persisted state keys change.
