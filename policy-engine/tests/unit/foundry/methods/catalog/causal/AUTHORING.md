# Causal Method Catalog Test Authoring Contract

Owner: `team-foundry`
Applies to: `tests/unit/foundry/methods/catalog/causal/**`
Last updated: 2026-05-05

## Purpose

This subtree owns unit and characterization coverage for builtin causal method
catalog behavior.

## Allowed File Categories

- Pytest `test_*.py` modules, local README/AUTHORING/index docs, and tiny
  inline test data.
- No raw datasets, generated benchmark reports, or production source.

## Public/Private Boundary

Tests may reach private helpers only to pin split/refactor behavior. New public
behavior should be asserted through registered method APIs.

## Naming Convention

Use `test_<method_or_concept>.py`. Characterization tests should name the module
or behavior they protect.

## Test Location

This is the canonical unit test mirror for the causal catalog source subtree.

## Fixture/Data Policy

Prefer inline tiny fixtures. Shared data belongs under `tests/_data/` and
golden records under `tests/_golden/`.

## Generated File Policy

Do not commit generated reports here. Store reviewed evidence under
`docs/archive/reports/` if needed.

## Extension Points

Extension plugin smoke tests belong under extension-example tests, not this
builtin source mirror.

## Deprecation And Shim Policy

Keep tests for old method IDs and import shims until their registered sunset.
