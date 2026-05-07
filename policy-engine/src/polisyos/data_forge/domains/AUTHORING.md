# Data Forge Domains Authoring Contract

Owner: `team-data-forge`
Applies to: `src/polisyos/data_forge/domains/**`
Last updated: 2026-05-05

## Purpose

This subtree owns build-time Data Forge domain implementations and builtin
domain registration.

## Allowed File Categories

- Product Python modules, small reviewed product seed assets, domain-local
  README/AUTHORING docs, and registered fixture metadata.
- No production downloads, local caches, or generated build outputs.

## Public/Private Boundary

Domain packages are private build-time implementation unless exported by the
domain extension contract. Runtime consumers use `polisyos.data_forge.read_api`.

## Naming Convention

Use stable domain nouns for first-level directories. Batch pipelines live under
`<domain>/batch/`; knowledge/reference helpers live under explicit subtrees.

## Test Location

Tests live under `tests/unit/data_forge/` with domain mirrors where useful.

## Fixture/Data Policy

Small reviewed product seed assets may stay package-local when registered.
Test fixtures belong under `tests/_data/` or `tests/_golden/`.

## Generated File Policy

Generated domain outputs are local by default. Promote only reviewed summaries
or registered generated artifacts.

## Extension Points

External domains use `polisyos.data_forge_domains`; builtin domains should keep
component metadata in the registered loader.

## Deprecation And Shim Policy

Domain renames require compatibility shims or migration notes when saved
manifests, checkpoints, or fixtures reference old paths.
