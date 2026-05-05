# ADR-RSR-0129: Empty Placeholder Package Policy

## Status

Proposed

## Date

2026-05-03

## Identifier Note

`RSR-0129` is the Repository Structure Remediation plan-local identifier. The
global ADR number `0129` is already used by Scientist Claim Ledger and is not
superseded by this skeleton.

## Context

Empty `__init__.py`-only packages can look like valid import namespaces while
real implementation lives elsewhere. `foundry/methods/{domain}/` currently
collides with populated `foundry/methods/catalog/{domain}/` packages.

## Decision

1. Ban empty namespace placeholders when a populated descendant or sibling owns
   the same semantic name.
2. Record the rule in `architecture/package_layout.toml`.
3. Enforce through `empty_namespace_gate`, report-only in Phase 0 and
   fail-closed after Phase 1A.

## Consequences

Imports must target canonical packages or explicit facade re-exports. Placeholder
directories are either removed or converted into time-boxed migration shims.

## Concrete Impact

- Contract: `architecture/package_layout.toml`.
- Gate: `tools/quality/validation/repository_structure_phase0.py`.
- Baseline: `architecture/baselines/structure_remediation/foundry_methods_empty_placeholders.json`.
- Owner: `team-architecture`.
- Target phase: `1A`.
- Rollback: restore placeholder directory from git and re-open the shim entry.

## Related Decisions

- Extends: ADR-0127 Repository Hygiene Gates.
- Related: RSR-0136 `foundry/methods` flat vs catalog.
