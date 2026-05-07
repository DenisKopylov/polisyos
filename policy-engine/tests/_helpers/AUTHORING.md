# Shared Test Helpers Authoring Contract

Owner: `team-quality`
Applies to: `tests/_helpers/**`
Last updated: 2026-05-05

## Purpose

This subtree owns reusable Python helpers for pytest suites.

## Allowed File Categories

- Python helper modules, `__init__.py`, and local README/AUTHORING docs.
- No product source, fixtures, golden records, caches, or generated output.

## Public/Private Boundary

The boundary is test-only. Product code must not import this package.

## Naming Convention

Use snake_case modules named after the test concern they support.

## Test Location

Helpers should be exercised by consuming tests. Add focused helper tests only
when behavior becomes complex.

## Fixture/Data Policy

Helpers may reference `tests/_data/` and `tests/_golden/`, but fixture files do
not live here.

## Generated File Policy

No generated files are allowed here.

## Extension Points

Promote a helper here only after two or more test slices need it.

## Deprecation And Shim Policy

Remove or inline helpers when they become single-consumer compatibility glue.
