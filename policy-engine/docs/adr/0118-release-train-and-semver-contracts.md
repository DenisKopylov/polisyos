# ADR-0118: Release Train and SemVer Contracts

## Status
Proposed

## Date
2026-04-18

## Context

The repository has release fragments, release policy files, ABI snapshots, and
public surface manifests. These need one versioning model so breaking API,
schema, and artifact changes are visible.

## Decision

Adopt release-train discipline:

1. Major subsystems have versioned public surfaces.
2. Breaking public-surface or schema changes require a version bump.
3. Data Forge artifact versions are separate from code versions and recorded as
   `schema_version` and `producer_version`.
4. CHANGELOG output is generated from release fragments.

## Consequences

- Compatibility changes become explicit.
- Artifact reproducibility can cite both data schema and producer code version.
- Release gates can reason about SemVer instead of ad-hoc diffs.

## Related Decisions

- Extends: ADR-0010 (CAS artifact signing) for release artifact governance,
  ADR-0100 (runtime API versioning and deprecation policy).
- Related: ADR-0114 (schema registry), ADR-0123 (ArtifactRef governance),
  ADR-0128 (hermetic reproducibility).
