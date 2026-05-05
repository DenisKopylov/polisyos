# ADR-RSR-0133: Top-Level Package Size Budget and Facade Pattern

## Status

Proposed

## Date

2026-05-03

## Identifier Note

`RSR-0133` is the Repository Structure Remediation plan-local identifier. The
global ADR number `0133` is already used by Fabric Streaming and Scale
Semantics and is not superseded by this skeleton.

## Context

Large packages with many root-level Python modules mix public API, internal
implementation, runtime glue, and migration compatibility in one namespace.

## Decision

1. Top-level packages target at most 250 files.
2. Package roots target at most five `.py` files.
3. Root `.py` files are limited to facade modules: `__init__.py`, `api.py`, and
   `_api.py` by default.
4. Exceptions require owner, target phase, and sunset in
   `architecture/package_layout.toml`.

## Consequences

`scientist/` and `foundry/` decompositions must go through the Phase 3A safety
net before source moves begin.

## Concrete Impact

- Contract: `architecture/package_layout.toml`.
- Gate: `loose_files_gate`.
- Baseline: `loose_root_modules.json`.
- Owner: `team-architecture`.
- Target phases: `5`, `6`.
- Rollback: revert individual module moves through the codemod rollback plan.

## Related Decisions

- Extends: ADR-0127 Repository Hygiene Gates.
