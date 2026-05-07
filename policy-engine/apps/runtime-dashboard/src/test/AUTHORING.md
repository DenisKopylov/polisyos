# Runtime Dashboard Test Authoring Contract

Owner: `team-frontend`
Applies to: `apps/runtime-dashboard/src/test/**`
Last updated: 2026-05-05

## Purpose

This subtree owns frontend-only helpers and fixtures for dashboard tests.

## Allowed File Categories

- TypeScript/TSX test helpers, MSW handlers, accessibility helpers, reviewed
  JSON fixtures, and local docs.
- No production components, generated API types, coverage output, or Playwright
  reports.

## Public/Private Boundary

Only test files may import from `src/test`. Production code must not depend on
test helpers or fixtures.

## Naming Convention

Use descriptive helper names and keep API payload fixtures named after the
runtime endpoint or hook they verify.

## Test Location

Vitest tests remain colocated with source or under test helper slices. E2E
fixtures live under app-level `e2e/` when they are browser journey specific.

## Fixture/Data Policy

JSON fixtures are small reviewed contract payloads. Do not add anonymized
production responses or raw logs.

## Generated File Policy

No generated files are allowed here unless registered as frontend contract
fixtures. Coverage and reports belong under ignored `_build/` roots.

## Extension Points

New fixtures are added through `contracts/fixtures/` and consumed by contract
tests or MSW handlers.

## Deprecation And Shim Policy

Old fixtures stay only while compatibility tests need them; remove them with
the corresponding hook/API migration.
