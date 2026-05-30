# Scientist Search Test Authoring

## Purpose

Cover Scientist search behavior while imports move to
`polisyos.scientist.methods.search`.

## Allowed File Categories

Pytest modules, local helpers, tiny fixtures, and docs.

## Public/Private Boundary

Use canonical `polisyos.scientist.methods.search` imports. Legacy
`polisyos.scientist.search` imports are retired and appear only in explicit
negative import-surface tests or stable historical schema names.

## Naming Convention

Use `test_<search_contract>.py`; strategy tests may stay under `strategies/`.

## Test Location

Tests stay here until the test taxonomy is physically moved with its owner.

## Fixture/Data Policy

Use synthetic objectives and small local search spaces.

## Generated File Policy

Generated search reports are not committed here.

## Extension Points

Search strategy extension tests should name the strategy boundary explicitly.

## Deprecation And Shim Policy

Retired import tests must prove the legacy `scientist.search` surface is not
resolved.
