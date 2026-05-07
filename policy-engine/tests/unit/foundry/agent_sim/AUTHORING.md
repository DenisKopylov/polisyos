# Foundry Agent Simulation Test Authoring

## Purpose

Exercise deterministic agent simulation contracts, metrics, and world helpers.

## Allowed File Categories

Pytest modules, small deterministic fixtures, and local docs.

## Public/Private Boundary

Use public `polisyos.foundry.agent_sim` APIs unless testing a private invariant.

## Naming Convention

Use `test_<simulation_area>.py`.

## Test Location

Tests stay in `tests/unit/foundry/agent_sim/`.

## Fixture/Data Policy

Keep worlds synthetic and small. Shared fixtures belong under `tests/_data/`.

## Generated File Policy

Generated simulation outputs are not committed here.

## Extension Points

Agent-sim extension tests should name the extension host explicitly.

## Deprecation And Shim Policy

Legacy Foundry agent imports are shim-only and must identify their canonical
package.
