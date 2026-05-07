# Fabric Connector Sources Authoring Contract

Owner: `team-fabric`
Applies to: `src/polisyos/fabric/connectors/sources/**`
Last updated: 2026-05-05

## Purpose

This subtree owns builtin source adapters and source-specific contract helpers
for Fabric connector ingestion.

## Allowed File Categories

- Product Python adapter modules, `_contracts/` metadata, and local docs.
- No secrets, downloaded datasets, local caches, or generated connector output.

## Public/Private Boundary

Source modules are private implementation unless registered by the Fabric
extension/component contract. Public plugin ABI lives in Fabric extension APIs.

## Naming Convention

Use provider or protocol names in snake_case. Shared private helpers use a
leading underscore and must not be imported outside connector packages.

## Test Location

Tests live in `tests/unit/fabric/connectors/sources/` and broader Fabric
connector tests.

## Fixture/Data Policy

Use offline, small fixtures under `tests/_data/fabric/` or connector test
fixtures. Network recordings and provider payload dumps are not committed here.

## Generated File Policy

Connector scorecards, discovery inventories, and replay outputs are local or
archive evidence; generated committed artifacts must be registered.

## Extension Points

Use `polisyos.fabric_connectors` for external providers. Builtin sources must
also expose component metadata through the Fabric component loader when needed.

## Deprecation And Shim Policy

Provider module renames require compatibility tests and an extension ABI
deprecation note with a removal window.
