# IR Analytics Test Authoring

## Purpose

Validate IR analytics behavior with fast, deterministic unit tests.

## Allowed File Categories

Pytest modules, small helpers, and local docs.

## Public/Private Boundary

Prefer public `polisyos.ir.analytics` imports. Private imports require a local
regression reason.

## Naming Convention

Use `test_<analytics_contract>.py`.

## Test Location

Tests stay in `tests/unit/ir/analytics/`.

## Fixture/Data Policy

Use synthetic IR objects or reviewed fixtures from `tests/_data/`.

## Generated File Policy

Generated analytics artifacts are not committed here.

## Extension Points

None.

## Deprecation And Shim Policy

Tests for moved analytics modules must use canonical imports unless the test is
explicitly about a shim.
