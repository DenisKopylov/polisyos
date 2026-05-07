# Scientist Governance Test Authoring

## Purpose

Keep governance behavior covered while preserving pass compatibility.

## Allowed File Categories

Pytest modules, small fixtures, local conftest helpers, and docs.

## Public/Private Boundary

Prefer `polisyos.scientist.governance` canonical imports. Legacy first-level
governance imports belong only in shim tests.

## Naming Convention

Use `test_<governance_area>.py`; pass tests should include `_pass` in the name.

## Test Location

Tests stay in `tests/unit/scientist/governance/`.

## Fixture/Data Policy

Use synthetic governance reports and reviewed tiny fixtures.

## Generated File Policy

Generated reports are not committed here.

## Extension Points

Governance pass extension tests must name `polisyos.scientist_governance_passes`.

## Deprecation And Shim Policy

Shim tests must assert the canonical governance or validation replacement.
