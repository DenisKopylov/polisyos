# IR Analytics Authoring Contract

Owner: `team-ir`
Applies to: `src/polisyos/ir/analytics/**`
Last updated: 2026-05-05

## Purpose

This package defines IR-level analytical contracts, causal semantics,
uncertainty surfaces, diagnostics, bridges, and proof artifacts.

## Allowed File Categories

- Product Python modules and package-local README/AUTHORING/index docs.
- `ddl/` support files when they are versioned analytical contracts.
- No runtime state, large datasets, or frontend code.

## Public/Private Boundary

The public API is the package facade plus documented bridge and contract
exports. Underscore modules and one-off helpers are private implementation.

## Naming Convention

Use snake_case module names by analytical concept. New modules should expose
typed models or pure helpers; avoid catch-all utility modules.

## Test Location

Use `tests/unit/ir/` for unit and contract coverage. Interoperability bridge
tests live in `tests/unit/ir/test_interoperability_bridges.py`.

## Fixture/Data Policy

Small examples belong under `tests/_data/` or `tests/_golden/`. Do not commit
derived experiment outputs inside this package.

## Generated File Policy

Generated schemas and references belong under `schemas/` or `docs/reference/`
and must be listed in generated-artifact contracts.

## Extension Points

IR analytics exposes bridge contracts for external analytical ecosystems, but
does not host plugin discovery directly.

## Deprecation And Shim Policy

Public model or bridge renames require public-surface and schema compatibility
updates, plus a shim entry when old imports remain supported.
