# Scientist Agent Test Authoring

## Purpose

Validate agent behavior without making network or model-provider calls.

## Allowed File Categories

Pytest modules, test doubles, small fixtures, and local docs.

## Public/Private Boundary

Prefer public Scientist agent APIs. Private imports are allowed for deterministic
agent-state regressions.

## Naming Convention

Use `test_<agent_or_tool>.py`.

## Test Location

Tests stay in `tests/unit/scientist/agent/`.

## Fixture/Data Policy

Use synthetic prompts and local test doubles only.

## Generated File Policy

Generated model outputs are not committed here.

## Extension Points

Node-extension integration belongs under Scientist node tests.

## Deprecation And Shim Policy

Moved Scientist imports should use canonical Wave 4 homes unless the test is
about a public shim.
