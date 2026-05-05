# ADR-RSR-0137: Production Data and Fixtures Classification

## Status

Accepted

## Date

2026-05-03

## Context

`production_data/`, loose root data, and runtime run directories blur the line
between committed fixtures, local state, generated evidence, and external
datasets.

## Decision

1. Small deterministic fixtures live under `tests/fixtures/<domain>/` or a
   domain-owned `data_forge/domains/<domain>/fixtures/` directory when they are
   source fixtures for that domain.
2. Large or sensitive snapshots live outside git or behind an explicit DVC or
   artifact reference.
3. Runtime runs live under `.polisyos/runs/` and stay ignored.
4. Every retained generated data path is registered in
   `architecture/generated_artifacts.toml` or a domain artifact contract.
5. Phase 1A classifies `production_data/` as a local production snapshot
   and moves the working copy to `.polisyos/production_data/`.
   Dataset catalog artifacts are grouped under the snapshot directory
   `.polisyos/production_data/datasets_full_phase3full_20260327_183054/`.
6. Phase 1A classifies `relevant_topics_domain_files/` as reviewed catalog
   fixtures and moves them to
   `src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/`.

## Consequences

Phase 1A evicts root data without committing runtime snapshots or build
outputs. Topic CSV fixtures become explicitly registered review fixtures;
production snapshots remain outside git.

## Concrete Impact

- Contracts: `architecture/generated_artifacts.toml`, `architecture/data_policy.toml`.
- Baseline: `build_outputs.json`.
- Owner: `team-data-forge`.
- Target phase: `1A`.
- Rollback: restore evicted data path and assign fixture/external ownership.

## Related Decisions

- Related: ADR-0123 ArtifactRef Governance Metadata.
