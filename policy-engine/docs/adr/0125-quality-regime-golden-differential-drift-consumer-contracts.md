# ADR-0125: Quality Regime for Data Forge Assets

## Status

Proposed

## Date

2026-04-18

## Context

Golden snapshots are necessary before moving legacy pipelines, but they are not
enough for LLM-derived, embedding-derived, and upstream-source-driven data.
Exact byte equality is too brittle when extraction models or source payloads
change, while pure smoke tests miss semantic regressions.

## Decision

Data Forge quality uses four complementary gates:

1. Golden snapshots for deterministic compatibility during package moves.
2. Differential tests that compare old and new pipelines on the same inputs
   with per-field tolerances.
3. Drift monitors that compare distributions across snapshots for embeddings,
   extracted claims, graph topology, and row coverage.
4. Consumer contracts where Fabric, Runtime, Lex, Foundry, and Scientist declare
   the fields, freshness, schema versions, and governance metadata they require.

All four live under `polisyos.data_forge.kernel.quality` and emit contract
evidence into published snapshot manifests.

## Consequences

- LLM and upstream-data non-determinism can be handled structurally instead of
  by weakening all tests.

- Consumers can fail closed before reading stale or incompatible artifacts.
- Data Forge domain migrations cannot close while their old-vs-new differential
  evidence is missing.

## Related Decisions

- Extends: ADR-0113 (asset-centric pipeline model), ADR-0114 (schema registry).
- Depends on: ADR-0122 (lakehouse snapshots), ADR-0123 (ArtifactRef governance).
- Related: ADR-0062 (knowledge snapshot id input ref), ADR-0095 (canonical SCM
  test fixtures).
