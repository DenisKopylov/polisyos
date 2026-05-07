# Shared UI Authoring Contract

Owner: `team-frontend`
Applies to: `apps/runtime-dashboard/src/shared/ui/**`
Last updated: 2026-05-05

## Purpose

This subtree owns reusable UI primitives, composed patterns, and domain-shaped
renderers that are safe for multiple features to share.

## Allowed File Categories

- TypeScript/TSX components, hooks directly tied to shared UI, styles/tokens,
  tests, retained stories, and local docs.
- No feature routes, API calls, generated API types, or build output.

## Public/Private Boundary

Feature modules consume exported shared UI components. Shared UI must not import
from `src/features/`, `src/app/`, or runtime-specific API hooks.

## Naming Convention

Use PascalCase component files and colocated `*.test.tsx` or `*.stories.tsx`.
Family directories use kebab-case only when matching an existing family.

## Test Location

Use colocated tests for primitives and `src/test/` helpers for provider-heavy
rendering. Accessibility coverage belongs in the a11y/e2e suites when needed.

## Fixture/Data Policy

Keep fixture data tiny and local to tests/stories. API payload fixtures belong
in `src/test/contracts/fixtures/`.

## Generated File Policy

No generated files are allowed here.

## Extension Points

Promote UI into this subtree only after confirming it is feature-agnostic.
Feature-specific components stay in `src/features/<feature>/components/`.

## Deprecation And Shim Policy

Keep deprecated exports as wrappers only when migration requires them. Document
removal in release notes or local README before deleting aliases.
