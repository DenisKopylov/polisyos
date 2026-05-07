# Scientist Orchestration Engine Authoring Contract

Owner: `team-scientist`
Applies to: `src/polisyos/scientist/orchestration/engine/**`
Last updated: 2026-05-05

## Purpose

This package owns Scientist workflow execution: node protocol contracts,
checkpointing, retries, budgets, locks, telemetry, state branching, and builtins.

## Allowed File Categories

- Product Python modules and local README/AUTHORING/index docs.
- Builtin engine nodes under `builtins/`, lock adapters under `locks/`, and
  runner helpers under `runner/`.
- No run state, checkpoints, traces, or generated workflow outputs.

## Public/Private Boundary

The public boundary is the documented engine protocol and package facade.
Implementation helpers are private to Scientist orchestration.

## Naming Convention

Use snake_case modules by engine concern: `checkpoint`, `retry`, `telemetry`,
`state_merge`, and similar nouns.

## Test Location

Tests live under `tests/unit/scientist/engine/`,
`tests/unit/scientist/workflows/`, and `tests/unit/scientist/nodes/` depending
on the behavior under change.

## Fixture/Data Policy

Use `tests/_data/scientist/` for small persisted workflow examples and
`tests/_golden/` for reviewed checkpoint/golden compatibility records.

## Generated File Policy

Runtime checkpoints and traces are local runtime state. Do not commit them from
this package.

## Extension Points

Scientist nodes are the extension host. Engine changes must preserve
`polisyos.scientist_nodes` compatibility.

## Deprecation And Shim Policy

The old `polisyos.scientist.engine` path is a compatibility concern during the
orchestration move. Keep shims and tests until the sunset date in architecture
contracts.
