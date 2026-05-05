# ADR-RSR-0130: Workspace Boundary

## Status

Accepted

## Date

2026-05-03

## Identifier Note

`RSR-0130` is the Repository Structure Remediation plan-local identifier. The
global ADR number `0130` is already used by Scientist Research DAG and is not
superseded by this skeleton.

## Context

The repository currently has overlapping workspace and product-root signals:
duplicated caches, duplicated virtual environments, duplicated runtime state,
and root-level scratch/build artifacts.

## Decision

Phase 2A chooses **Variant A: collapse to the product root**.

1. `policy-engine/` is the only PolisyOS product/workspace root for local
   runtime state, Python environment state, lockfiles, cache paths, topology
   scopes, and product-facing documentation.
2. The outer Git repository root remains a repo-control-plane shell for
   GitHub-native files such as `.github/`, root `.gitignore`, and Renovate
   configuration. Ignored editor/agent state may exist locally, but it is not
   product state and is no longer modeled as a second workspace in
   `architecture/topology.toml`.
3. Product-level support and governance documents live under `policy-engine/`:
   `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `SUPPORT.md`.
4. Product-level design and local data material move under `policy-engine/`.
   Bulk data remains ignored by Git and is governed by
   `architecture/data_policy.toml`.
5. Root-level duplicate `.venv`, `.polisyos`, and cache directories are removed.
   The remaining canonical local state lives under `policy-engine/`.
6. A true root monorepo remains deferred until there are multiple independently
   deployable services or independently versioned product packages that justify
   moving product code to `apps/`, `packages/`, and `services/`.

## Consequences

The repository keeps existing `policy-engine/` relative product paths, which
minimizes CI and documentation churn while removing the second local workspace.
Future `uv` and frontend workspace work should happen inside the product root
unless a later ADR explicitly accepts a true root monorepo migration.

Root-level GitHub governance files that must be discovered by GitHub or
repository automation may stay at the outer Git root. Product support policy is
authored once under `policy-engine/` and referenced from repo-control-plane
configuration when needed.

## Concrete Impact

- Contract: `architecture/topology.toml`.
- Gate: `cache_dir_gate` and `build_output_gate`.
- Owner: `team-platform`.
- Target phase: `2A`.
- Rollback: revert the Phase 2A path migration PR.

## Related Decisions

- Extends: ADR-0096 Canonical Product Root and Workspace Boundary.
- Related: ADR-0111 Workspace Root Boundary SOTA Contract.
