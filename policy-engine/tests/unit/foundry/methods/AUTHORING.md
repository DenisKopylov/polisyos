# Foundry Methods Test Authoring

## Purpose

Keep fast unit coverage for Foundry method contracts and taxonomy packages.

## Allowed File Categories

Pytest modules, local conftest helpers, tiny fixtures, and local docs.

## Public/Private Boundary

Prefer canonical subpackage imports. Root compatibility imports are allowed only
in explicit shim tests.

## Naming Convention

Use `test_<subpackage_or_contract>.py`; catalog tests live under
`catalog/<family>/`.

## Test Location

Tests stay in `tests/unit/foundry/methods/`.

## Fixture/Data Policy

Keep fixtures deterministic and small. Shared examples belong under
`tests/_data/` or package-specific catalog fixture dirs.

## Generated File Policy

Generated catalog outputs must be registered before commit.

## Extension Points

Foundry method extension host coverage belongs in tests that name
`polisyos.foundry_methods`.

## Deprecation And Shim Policy

Compatibility tests must name the source shim and canonical target.
