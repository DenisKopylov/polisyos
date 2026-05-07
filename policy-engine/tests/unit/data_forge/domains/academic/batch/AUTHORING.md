# Academic Batch Test Authoring

## Purpose

Validate academic batch-domain behavior without reaching external services.

## Allowed File Categories

Pytest modules, small inline fixtures, and local docs.

## Public/Private Boundary

Prefer domain public builders. Private imports require a focused regression
reason in the test name or docstring.

## Naming Convention

Use `test_<source_or_builder>.py`.

## Test Location

Tests stay in `tests/unit/data_forge/domains/academic/batch/`.

## Fixture/Data Policy

Use tiny synthetic records; larger examples belong in `tests/_data/`.

## Generated File Policy

Generated snapshots are not committed here.

## Extension Points

Domain extension behavior belongs in Data Forge domain extension tests.

## Deprecation And Shim Policy

Shim tests must identify the canonical domain path and sunset.
