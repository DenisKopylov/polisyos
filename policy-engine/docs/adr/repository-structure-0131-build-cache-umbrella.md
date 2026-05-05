# ADR-RSR-0131: Build Output and Cache Umbrella

## Status

Proposed

## Date

2026-05-03

## Identifier Note

`RSR-0131` is the Repository Structure Remediation plan-local identifier. The
global ADR number `0131` is already used by Scientist Readiness Ladder and is
not superseded by this skeleton.

## Context

Generated outputs and caches are scattered across root, product root, release
folders, frontend packages, and tool-specific dot directories.

## Decision

1. Use `_build/` for generated outputs.
2. Use `_cache/` for tool caches.
3. Keep `.polisyos/` for runtime state and `.venv/` for the selected local
   environment.
4. Configure tools to write to the umbrella locations after workspace paths are
   stable.

## Consequences

Developers get one cleanup surface. CI and local commands must be updated to
use the new cache/output paths.

## Concrete Impact

- Contract: `architecture/structure_remediation_gates.toml`.
- Gates: `cache_dir_gate`, `build_output_gate`.
- Baselines: `cache_and_env_paths.json`, `build_outputs.json`.
- Owner: `team-devx`.
- Target phase: `2B`.
- Rollback: restore prior tool output paths and `.gitignore` entries.

## Related Decisions

- Extends: ADR-0127 Repository Hygiene Gates.
