# ADR-RSR-0136: Foundry Methods Flat vs Catalog

## Status

Accepted

## Date

2026-05-03

## Context

`foundry/methods` has empty domain placeholders next to populated
`foundry/methods/catalog` domain packages. Both shapes imply different
canonical import paths.

## Decision

Phase 1A chooses the catalog-canonical model.

1. `polisyos.foundry.methods.catalog.<domain>.<module>` is the canonical module
   path for implementation code.
2. The documented flat domain API remains available through single-file
   facade modules such as `polisyos.foundry.methods.causal`.
3. Empty `methods/<domain>/__init__.py` placeholder packages are removed.
4. Deep legacy imports below the flat domain facade, for example
   `polisyos.foundry.methods.causal.synthetic_control`, stay removed.

## Consequences

Foundry method discovery and implementation imports get one canonical route
through `catalog`. Public callers that already use the flat domain facade keep
working without preserving empty namespace packages.

## Concrete Impact

- Source: `src/polisyos/foundry/methods/{bayesian,causal,dependence,econometrics,microsim,ml,network,optimization,spatial}.py`.
- Gate: `empty_namespace_gate` fail-closed, with external flat/deep importer
  inventory in
  `architecture/baselines/structure_remediation/foundry_methods_external_importers.json`.
- Owner: `team-foundry`.
- Target phase: `1A`.
- Rollback: restore prior placeholder directories only as sunsetted shims in
  `architecture/shims.toml`.

## Related Decisions

- Extends: ADR-RSR-0129 Empty Placeholder Package Policy.
