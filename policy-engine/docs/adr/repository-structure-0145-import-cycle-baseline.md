# ADR-RSR-0145: Import Cycle Baseline

## Status

Accepted

## Date

2026-05-03

## Context

Scientist and Foundry already contain lazy import patterns that may work only
because of `TYPE_CHECKING` guards, local imports, or facade indirection. Moving
modules without a cycle baseline can turn those latent cycles into import-time
failures.

## Decision

1. Phase 3A snapshots the Scientist/Foundry import graph in
   `architecture/baselines/structure_remediation/import_graph_pre_decomp.json`.
2. Pre-existing strongly connected components are recorded in
   `architecture/imports/lazy.toml`.
3. `import_cycles_gate` fails when a new non-lazy cycle signature appears.
4. Phase 5/6 may resolve existing cycles, but may not introduce unregistered
   cycles.
5. The baseline records `collector_mode`. In this workspace Phase 3A uses the
   deterministic internal AST collector because `pydeps` and `import-linter`
   are not required dev dependencies.

## Consequences

Lazy cycle behavior is explicit and reviewable before decomposition starts.

## Related Decisions

- ADR-RSR-0143 Decomposition Blueprint Contract.
