# Catalog Batch Authoring Contract

Owner: `team-data-forge`
Applies to: `src/polisyos/data_forge/domains/catalog/batch/**`
Last updated: 2026-05-05

## Purpose

This subtree owns offline catalog ingestion, source registry processing,
deduplication, graph building, quality checks, and publication helpers.

## Allowed File Categories

- Product Python modules and small reviewed source registry metadata.
- Local README/AUTHORING docs.
- No raw external harvests or generated run outputs.

## Public/Private Boundary

Public use flows through Data Forge domain APIs and documented batch commands.
Implementation modules are private to the catalog domain.

## Naming Convention

Use snake_case modules by pipeline stage: `harvester`, `normalizer`, `qc`,
`publish`, and similar stage nouns.

## Test Location

Tests live in `tests/unit/data_forge/domains/catalog/` and the broader
`tests/unit/data_forge/` suite.

## Fixture/Data Policy

`source_registry.yaml` is a reviewed seed input. Additional fixtures belong
under `tests/_data/` unless they are package-owned product seed assets.

## Generated File Policy

Generated catalog outputs are local by default. Promote summaries through
`docs/archive/reports/` or generated-artifact contracts.

## Extension Points

Data Forge domain plugins use `polisyos.data_forge_domains`; this subtree is a
builtin catalog implementation.

## Deprecation And Shim Policy

Renamed batch modules or source registry fields require migration notes and
compatibility tests before old names are removed.
