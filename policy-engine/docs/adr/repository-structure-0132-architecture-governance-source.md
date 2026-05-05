# ADR-RSR-0132: Architecture as Single Governance Source

## Status

Proposed

## Date

2026-05-03

## Identifier Note

`RSR-0132` is the Repository Structure Remediation plan-local identifier. The
global ADR number `0132` is already used by Scientist VOI Compute Law and is not
superseded by this skeleton.

## Context

Architecture governance files are split between `architecture/`, `baseline/`,
and root-level `import_*` / `freeze_policy` files.

## Decision

1. Move import policy, exceptions, baselines, and freeze policy under
   `architecture/`.
2. Keep compatibility shims for old paths with owner and sunset.
3. Treat `architecture/` as the only source for governance contracts.

## Consequences

Validation and import-linter commands must resolve new paths. Old root-level
governance files become wrapper-only compatibility paths until sunset.

## Concrete Impact

- Contracts: `architecture/imports/*`, `architecture/policies/*`.
- Gate: `pyproject_size_gate` and existing architecture guardrails.
- Owner: `team-architecture`.
- Target phase: `1B`.
- Rollback: restore old files and shim entries in one config migration revert.

## Related Decisions

- Extends: ADR-0004 Architecture Boundaries Import Gate.
- Related: ADR-0115 Layered Architecture Enforcement.
