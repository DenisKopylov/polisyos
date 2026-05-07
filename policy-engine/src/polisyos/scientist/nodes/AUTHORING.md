# Scientist Nodes Authoring Contract

Owner: `team-scientist`
Applies to: `src/polisyos/scientist/nodes/**`
Last updated: 2026-05-05

## Purpose

This subtree owns builtin Scientist node implementations and the node extension
host boundary.

## Allowed File Categories

- Product Python node modules, builtin family subpackages, registry helpers,
  and local docs.
- No workflow run outputs, generated reports, or test fixture payloads.

## Public/Private Boundary

The public extension ABI is `polisyos.scientist_nodes`. Builtin implementation
modules are private unless exported by `builtin_nodes()` or wrapped by
`components.py` as a `ComponentProvider`.

## Naming Convention

Builtin family directories use workflow stage names. Node modules use
snake_case action names that match their workflow role.

## Test Location

Tests live in `tests/unit/scientist/nodes/` and integration coverage under
`tests/integration/scientist/`.

## Fixture/Data Policy

Use `tests/_data/scientist/` for shared payloads and inline fixtures for small
node inputs.

## Generated File Policy

No generated files are allowed here. Workflow outputs and traces are local
runtime state or reviewed archive evidence.

## Extension Points

External nodes use the `polisyos.scientist_nodes` entry-point group and must
ship an offline smoke test with component metadata. Builtin nodes must appear
in `components.py` through `builtin_node_components()` so registry bootstrap
and external discovery exercise the same contract.

## Deprecation And Shim Policy

Node ID, state-key, or module renames require workflow compatibility tests and
a sunset note before old references are removed.
