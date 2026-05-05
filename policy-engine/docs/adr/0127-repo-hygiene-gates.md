# ADR-0127: Repository Hygiene Gates

## Status

Proposed

## Date

2026-04-18

## Context

Repository hygiene currently depends on convention: loose files, accidental
artifacts, secrets, generated drift, oversized modules, and stale shims can all
reappear after a cleanup. A SOTA monorepo needs fail-closed gates for these
classes of regressions.

## Decision

Adopt repo hygiene gates as first-class CI and pre-commit checks:

1. Topology gate from `architecture/topology.toml`.
2. Import-linter gate from `architecture/import_contracts.toml`.
3. Shim sunset audit from `architecture/shims.toml`.
4. Module-size and complexity gate from `architecture/complexity_exceptions.toml`.
5. Generated-artifact drift gate from `architecture/generated_artifacts.toml`.
6. Public-surface snapshot gate from `architecture/public_surface.toml` and
   `architecture/public_surface/*.json`.
7. Secret scanning with gitleaks and optional trufflehog.
8. Dependency and vulnerability checks with deptry, OSV, and SBOM generation.
9. Commitlint for release-train metadata.

## Consequences

- Cleanup work becomes durable instead of cosmetic.
- New exceptions must be registered with an owner and sunset.
- Some local workflows need explicit `--fix` or regeneration commands before
  commit.

## Phase 0 Implementation Note

Repository SOTA Phase 0 refreshed the machine-readable gate baselines on
2026-05-02. Architecture guardrails pass after syncing public-surface and
generated-artifact references. Docs accuracy and security scans are recorded as
report-only baselines until their existing violations have owners, exceptions,
or cleanup phases; Phase 0 does not introduce a new fail-closed gate for those
checks.

## Related Decisions

- Extends: ADR-0004 (architecture boundaries import gate), ADR-0115 (layered
  architecture enforcement).

- Related: ADR-0118 (release train), ADR-0126 (docs lifecycle).
