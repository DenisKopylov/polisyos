# Causal Method Catalog Authoring Contract

Owner: `team-foundry`
Applies to: `src/polisyos/foundry/methods/catalog/causal/**`
Last updated: 2026-05-05

## Purpose

This subtree owns the causal method family: discovery, identification,
estimation, transportability, diagnostics, policy learning, and strategic
response methods.

## Allowed File Categories

- Product Python modules implementing causal methods and helpers.
- Local README/AUTHORING/index docs.
- No notebooks, raw datasets, or generated experiment output.

## Public/Private Boundary

Public methods are those registered by `register_causal_methods()` or exported
through the causal catalog README. Helper modules are private to the family.

## Naming Convention

Use snake_case names tied to one causal concept, estimator, diagnostic, or
bridge. Large-module extraction should preserve old import shims only when
registered in shim policy.

## Test Location

Tests live in `tests/unit/foundry/methods/catalog/causal/` and should mirror
new method modules by concept.

## Fixture/Data Policy

Use small deterministic inputs inside tests or under `tests/_data/`. Do not
commit research datasets, run logs, or benchmark reports beside source.

## Generated File Policy

Catalog inventory is generated from registration functions and method metadata.
Committed generated evidence must be registered before landing.

## Extension Points

External causal methods use the `polisyos.foundry_methods` extension point and
must provide compatibility metadata plus an offline smoke test.

## Deprecation And Shim Policy

Renamed method IDs and split modules require a deprecation entry, compatibility
tests, and a removal date before deleting the old import path.
