# ADR-0121: Python Monorepo via uv Workspaces

## Status
Proposed

## Date
2026-04-18

## Context

Product code lives in a single `polisyos` package, but Data Forge, Lex,
Scientist, Foundry, Runtime, and tooling have distinct release cycles, owners,
and test surfaces. Today they share one `pyproject.toml` at the product root,
which forces:

- one dependency closure for unrelated subsystems;
- reinstall of heavy extras (ML, torch, runtime) for pure contract work;
- no way to express subpackage versioning or per-subpackage lockfiles;
- integration tests that cannot isolate one layer's deps from another.

`uv` workspaces solve this with a root `pyproject.toml` defining members, one
shared `uv.lock`, but per-member `pyproject.toml` with independent metadata,
optional-dependencies, and entry points.

## Decision

1. Keep one product root at `policy-engine/` with one top-level `pyproject.toml`
   declaring `[tool.uv.workspace] members = [...]`.
2. Introduce workspace members per layer:
   `packages/common`, `packages/ir`, `packages/core`, `packages/data_forge`,
   `packages/fabric`, `packages/foundry`, `packages/lex`, `packages/scholar`,
   `packages/scientist`, `packages/runtime`, `packages/packs`, `packages/tools`.
3. Each member exposes its own `pyproject.toml`, its own optional extras, and
   its own `[project.entry-points]`.
4. The root `uv.lock` remains the single source of truth for pinned versions.
5. Per-layer CI jobs install only the member(s) they exercise, restoring fast
   contract-only lanes (<60 s) and keeping ML/runtime extras opt-in.
6. Migration is phased: contracts in one PR, package moves per layer, layers
   physically move only when their import-linter contract (ADR-0115) is green.

## Consequences

- Contract-only CI jobs become order-of-magnitude faster.
- Subsystem ownership maps 1:1 to a workspace member and a code owner.
- Breaking a layer no longer forces a cross-layer lock refresh.
- Tooling that assumed a single import root must switch to workspace-aware
  commands (`uv run --package <member> ...`).

## Related Decisions

- Extends: ADR-0096 (canonical product root), ADR-0115 (layered architecture).
- Related: ADR-0004 (architecture boundaries import gate).
