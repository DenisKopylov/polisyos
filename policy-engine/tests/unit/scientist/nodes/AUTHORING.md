# Scientist Node Test Authoring Contract

Owner: `team-scientist`
Applies to: `tests/unit/scientist/nodes/**`
Last updated: 2026-05-05

## Purpose

This subtree owns tests for builtin Scientist node behavior and registry
compatibility.

## Allowed File Categories

- Pytest source, shared node fixtures, local README/AUTHORING/index docs, and
  tiny inline fixtures.
- No workflow run outputs, generated reports, or product source.

## Public/Private Boundary

Prefer testing through node registry and protocol outputs. Private node helpers
may be imported only for characterization of planned splits.

## Naming Convention

Use `test_<node_or_behavior>.py`. Builtin family tests mirror
`src/polisyos/scientist/nodes/builtins/<family>/`.

## Test Location

This subtree is the canonical unit test layer for Scientist builtin nodes.

## Fixture/Data Policy

Use `tests/_data/scientist/` for shared payloads and inline fixtures for small
node inputs.

## Generated File Policy

Generated workflow artifacts belong under ignored local state or reviewed
archive evidence, not this test tree.

## Extension Points

External node plugin tests use the `polisyos.scientist_nodes` extension contract
and installable examples.

## Deprecation And Shim Policy

Keep tests for deprecated node IDs and legacy state keys until the shim sunset.
