# Core Security Test Authoring

## Purpose

Keep fast unit coverage for core security primitives and policy helpers.

## Allowed File Categories

Pytest modules, small test helpers, and local documentation.

## Public/Private Boundary

Prefer public security APIs. Deep imports are allowed only for narrowly scoped
unit behavior.

## Naming Convention

Use `test_<capability>.py` and group fixtures near the test that owns them.

## Test Location

Tests stay in `tests/unit/core/security/`.

## Fixture/Data Policy

Use inline fixtures unless a reviewed shared fixture belongs under `tests/_data/`.

## Generated File Policy

Generated outputs are not committed here.

## Extension Points

None.

## Deprecation And Shim Policy

Tests for deprecated security imports must name the shim and sunset in the test
docstring or assertion message.
