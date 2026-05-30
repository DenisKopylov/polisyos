# Scientist Orchestration Engine Test Authoring

## Purpose

Validate canonical Scientist engine behavior after the Wave 4 orchestration move.

## Allowed File Categories

Pytest modules, local helpers, small fixtures, and docs.

## Public/Private Boundary

Use canonical `polisyos.scientist.orchestration.engine` imports. The legacy
`polisyos.scientist.engine` import surface is retired.

## Naming Convention

Use `test_<engine_area>.py`; runner tests may live in runner-specific files.

## Test Location

Tests stay in `tests/unit/scientist/orchestration/engine/`.

## Fixture/Data Policy

Checkpoint fixtures must be tiny and registered when committed.

## Generated File Policy

Generated runtime outputs are not committed here.

## Extension Points

Node extension registration is out of scope for this subtree.

## Deprecation And Shim Policy

Tests should use canonical imports; retired shim paths are covered only by
negative import-surface assertions.
