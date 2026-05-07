# Data Forge Test Authoring Contract

Owner: `team-data-forge`
Applies to: `tests/unit/data_forge/**`
Last updated: 2026-05-05

## Purpose

This subtree owns unit and characterization tests for Data Forge source and
domain behavior.

## Allowed File Categories

- Pytest source, `conftest.py`, local README/AUTHORING/index docs, and tiny
  inline fixtures.
- No generated pipeline outputs, downloaded data, or product source.

## Public/Private Boundary

Prefer public or package-documented APIs. Private helper imports are allowed
only for characterization during planned module splits.

## Naming Convention

Use `test_<behavior>.py` or domain mirror paths matching the source domain.
Phase tests retain `test_phase<N>_*.py` names.

## Test Location

This subtree is the canonical Data Forge unit layer. Shared fixture data lives
under `tests/_data/`.

## Fixture/Data Policy

Use small reviewed fixtures under `tests/_data/data_forge/` or inline literals.
Do not commit raw domain harvests.

## Generated File Policy

Generated outputs and benchmark reports stay under ignored local roots unless
promoted as archive evidence.

## Extension Points

Domain plugin compatibility uses `polisyos.data_forge_domains` and should be
covered with installable example smoke tests when externalized.

## Deprecation And Shim Policy

Keep shim tests until the sunset entry is removed from architecture shim
contracts.
