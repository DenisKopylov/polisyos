# Legal Batch Test Authoring

## Purpose

Cover legal batch parsing, normalization, and compatibility behavior.

## Allowed File Categories

Pytest modules, local helpers, and documentation.

## Public/Private Boundary

Prefer canonical Data Forge legal domain imports. Legacy imports are tested only
as shims.

## Naming Convention

Use `test_<contract>.py` and keep scenario names domain-specific.

## Test Location

Tests stay in `tests/unit/data_forge/legal_batch/`.

## Fixture/Data Policy

Use synthetic legal records or reviewed tiny fixtures.

## Generated File Policy

Generated outputs are not committed here.

## Extension Points

Data Forge domain extension tests live with domain extension coverage.

## Deprecation And Shim Policy

Legacy legal-batch tests must point to the canonical domain package.
